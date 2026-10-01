"""Day 4: build transparent album documents for semantic search."""

from __future__ import annotations

import argparse
import json
import sys
import sqlite3
import os
from collections import Counter
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding


ROOT = Path(__file__).parent
_database_override = os.getenv("AI_TASTE_DATABASE_PATH", "").strip()
DEFAULT_DATABASE = (
    Path(_database_override).expanduser()
    if _database_override
    else ROOT / "taste.db"
)
DEFAULT_MANIFEST = ROOT / "album_match_manifest.json"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_CACHE = ROOT / ".cache" / "fastembed"
NON_TASTE_TAGS = {
    "1001 albums you must hear before you die",
    "best of 2016",
    "dabeat",
    "favourite albums",
    "masterpiece",
}


def load_album_documents(
    database_path: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    tag_source: str = "musicbrainz",
) -> list[dict]:
    """Build accepted-album documents from one explicitly selected tag source."""
    if tag_source not in {"musicbrainz", "lastfm"}:
        raise ValueError("tag_source must be 'musicbrainz' or 'lastfm'")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("albums"), list):
        raise ValueError("V2 album manifest must contain an albums list")

    selected_mbids = [
        album["release_group_mbid"]
        for album in manifest["albums"]
        if album.get("status") == "accepted"
    ]
    if not selected_mbids:
        raise ValueError("V2 album manifest contains no accepted albums")
    if len(selected_mbids) != len(set(selected_mbids)):
        raise ValueError("V2 album manifest contains duplicate release-group MBIDs")

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    placeholders = ", ".join("?" for _ in selected_mbids)

    albums = {
        row["release_group_mbid"]: {
            "release_group_mbid": row["release_group_mbid"],
            "title": row["title"],
            "release_year": row["release_year"],
            "cover_url": row["cover_url"],
            "artists": [],
            "tags": [],
        }
        for row in connection.execute(
            f"""
            SELECT release_group_mbid, title, release_year, cover_url
            FROM albums
            WHERE release_group_mbid IN ({placeholders})
            ORDER BY title, release_group_mbid
            """,
            selected_mbids,
        )
    }

    missing_mbids = set(selected_mbids) - albums.keys()
    if missing_mbids:
        connection.close()
        examples = ", ".join(sorted(missing_mbids)[:5])
        raise ValueError(
            f"{len(missing_mbids)} accepted albums from {manifest_path.name} "
            f"are missing from the database; examples: {examples}"
        )

    for row in connection.execute(
        """
        SELECT aa.release_group_mbid, ar.name
        FROM album_artists AS aa
        JOIN artists AS ar ON ar.artist_mbid = aa.artist_mbid
        ORDER BY aa.release_group_mbid, aa.credit_order
        """
    ):
        if row["release_group_mbid"] in albums:
            albums[row["release_group_mbid"]]["artists"].append(row["name"])

    for row in connection.execute(
        """
        SELECT release_group_mbid, normalized_tag
        FROM album_tags
        WHERE source = ?
        ORDER BY release_group_mbid, tag_rank
        """,
        (tag_source,),
    ):
        if row["release_group_mbid"] not in albums:
            continue
        tags = albums[row["release_group_mbid"]]["tags"]
        if row["normalized_tag"] not in tags:
            tags.append(row["normalized_tag"])

    connection.close()

    documents = []
    for album in albums.values():
        year = album["release_year"] if album["release_year"] is not None else "unknown"
        album["document"] = "\n".join(
            [
                f'Title: {album["title"]}',
                f'Artist: {", ".join(album["artists"])}',
                f"Release year: {year}",
                f'Community tags: {", ".join(album["tags"])}',
            ]
        )
        documents.append(album)

    return documents


def embed_documents(documents: list[dict]) -> np.ndarray:
    """Turn every album document into one fixed-length dense vector."""
    model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(MODEL_CACHE))
    vectors = model.embed([album["document"] for album in documents])
    return np.asarray(list(vectors), dtype=np.float32)


def cosine_scores(vectors: np.ndarray, query_vector: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between one query and every album vector."""
    vector_norms = np.linalg.norm(vectors, axis=1)
    query_norm = np.linalg.norm(query_vector)
    denominator = np.maximum(vector_norms * query_norm, 1e-12)
    return (vectors @ query_vector) / denominator


def find_album_indices(documents: list[dict], titles: list[str]) -> list[int]:
    """Resolve user-facing titles to vector-row indices."""
    title_to_index = {
        album["title"].casefold(): index for index, album in enumerate(documents)
    }
    missing = [title for title in titles if title.casefold() not in title_to_index]
    if missing:
        available = ", ".join(album["title"] for album in documents)
        raise ValueError(f"Unknown album(s): {', '.join(missing)}. Available: {available}")
    return [title_to_index[title.casefold()] for title in titles]


def is_taste_tag(tag: str) -> bool:
    """Remove only obvious metadata/popularity tags from profile summaries."""
    return tag not in NON_TASTE_TAGS and not (len(tag) == 4 and tag.isdigit())


def build_taste_profile(
    documents: list[dict], vectors: np.ndarray, favorite_titles: list[str]
) -> dict:
    """Average normalized seed vectors and expose inspectable taste signals."""
    favorite_indices = find_album_indices(documents, favorite_titles)
    favorite_vectors = vectors[favorite_indices]
    norms = np.maximum(np.linalg.norm(favorite_vectors, axis=1, keepdims=True), 1e-12)
    normalized_favorites = favorite_vectors / norms
    profile_vector = normalized_favorites.mean(axis=0)
    profile_vector /= max(np.linalg.norm(profile_vector), 1e-12)

    tag_counts = Counter(
        tag
        for index in favorite_indices
        for tag in dict.fromkeys(documents[index]["tags"])
        if is_taste_tag(tag)
    )
    ranked_tags = sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
    seed_albums = [
        {
            "release_group_mbid": documents[index]["release_group_mbid"],
            "title": documents[index]["title"],
            "artists": documents[index]["artists"],
            "release_year": documents[index]["release_year"],
            "tags": [tag for tag in documents[index]["tags"] if is_taste_tag(tag)],
        }
        for index in favorite_indices
    ]
    years = [
        album["release_year"]
        for album in seed_albums
        if album["release_year"] is not None
    ]
    return {
        "favorite_indices": favorite_indices,
        "favorite_titles": [documents[index]["title"] for index in favorite_indices],
        "vector": profile_vector,
        "top_tags": ranked_tags[:10],
        "seed_albums": seed_albums,
        "shared_tags": sorted(tag for tag, count in tag_counts.items() if count >= 2),
        "distinctive_tags": sorted(tag for tag, count in tag_counts.items() if count == 1),
        "release_year_range": [min(years), max(years)] if years else None,
        "aggregation_method": "mean_of_l2_normalized_seed_vectors_then_l2_normalize",
    }


def rank_for_profile(
    documents: list[dict], vectors: np.ndarray, profile: dict, top_k: int
) -> list[dict]:
    """Rank candidates by centroid and retain the nearest favorite as a diagnostic."""
    profile_scores = cosine_scores(vectors, profile["vector"])
    favorite_scores = np.column_stack(
        [cosine_scores(vectors, vectors[index]) for index in profile["favorite_indices"]]
    )
    favorite_index_set = set(profile["favorite_indices"])
    profile_tags = {tag for tag, _ in profile["top_tags"]}
    results = []
    for index in np.argsort(profile_scores)[::-1]:
        if index in favorite_index_set:
            continue
        nearest_position = int(np.argmax(favorite_scores[index]))
        album = documents[index]
        results.append(
            {
                "title": album["title"],
                "artists": album["artists"],
                "profile_score": float(profile_scores[index]),
                "nearest_favorite": profile["favorite_titles"][nearest_position],
                "nearest_favorite_score": float(favorite_scores[index, nearest_position]),
                "shared_profile_tags": sorted(profile_tags.intersection(album["tags"])),
            }
        )
        if len(results) == top_k:
            break
    return results


def find_similar_albums(
    documents: list[dict], vectors: np.ndarray, query_title: str, top_k: int
) -> list[dict]:
    query_index = next(
        (
            index
            for index, album in enumerate(documents)
            if album["title"].casefold() == query_title.casefold()
        ),
        None,
    )
    if query_index is None:
        available = ", ".join(album["title"] for album in documents)
        raise ValueError(f"Unknown album: {query_title}. Available: {available}")

    scores = cosine_scores(vectors, vectors[query_index])
    ranked_indices = np.argsort(scores)[::-1]
    results = []
    query_tags = set(documents[query_index]["tags"])
    for index in ranked_indices:
        if index == query_index:
            continue
        album = documents[index]
        results.append(
            {
                "title": album["title"],
                "artists": album["artists"],
                "score": float(scores[index]),
                "shared_tags": sorted(query_tags.intersection(album["tags"])),
            }
        )
        if len(results) == top_k:
            break
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--album", help="Album title to use as the search query")
    parser.add_argument(
        "--favorite",
        action="append",
        help="Favorite album title; repeat this option to build a Taste Profile.",
    )
    parser.add_argument("--top-k", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.top_k < 1:
        raise SystemExit("--top-k must be at least 1")
    if args.album and args.favorite:
        raise SystemExit("Use either --album or --favorite, not both")

    documents = load_album_documents(args.database)
    if args.favorite:
        vectors = embed_documents(documents)
        try:
            profile = build_taste_profile(documents, vectors, args.favorite)
            results = rank_for_profile(documents, vectors, profile, args.top_k)
        except ValueError as error:
            raise SystemExit(str(error)) from error

        print(f"Model: {MODEL_NAME}")
        print(f"Embedding matrix: {vectors.shape[0]} albums x {vectors.shape[1]} dimensions")
        print(f'Favorites: {", ".join(profile["favorite_titles"])}')
        tags = ", ".join(
            f"{tag} ({count})" for tag, count in profile["top_tags"]
        )
        print(f"Profile tags: {tags or 'none'}")
        print("\nCandidates nearest to the profile centroid:")
        for rank, result in enumerate(results, start=1):
            artists = ", ".join(result["artists"])
            shared = ", ".join(result["shared_profile_tags"]) or "none"
            print(
                f'{rank}. {artists} — {result["title"]} '
                f'(profile={result["profile_score"]:.4f}, '
                f'nearest favorite={result["nearest_favorite"]} '
                f'{result["nearest_favorite_score"]:.4f}, '
                f"shared profile tags: {shared})"
            )
        return

    if args.album:
        vectors = embed_documents(documents)
        print(f"Model: {MODEL_NAME}")
        print(f"Embedding matrix: {vectors.shape[0]} albums x {vectors.shape[1]} dimensions")
        print(f"\nMost similar albums to: {args.album}")
        try:
            results = find_similar_albums(documents, vectors, args.album, args.top_k)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        for rank, result in enumerate(results, start=1):
            artists = ", ".join(result["artists"])
            shared = ", ".join(result["shared_tags"]) or "none"
            print(
                f'{rank}. {artists} — {result["title"]} '
                f'(cosine={result["score"]:.4f}, shared tags: {shared})'
            )
        return

    for index, album in enumerate(documents, start=1):
        print(f"\n--- Album document {index}/{len(documents)} ---")
        print(album["document"])


if __name__ == "__main__":
    main()
