"""Day 6: transparent Safe / Explore / Wildcard recommendation rules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from rag import (
    build_context,
    embed_chunks,
    generate_why_this,
    load_review_chunks,
)
from semantic_search import (
    DEFAULT_DATABASE,
    build_taste_profile,
    cosine_scores,
    embed_documents,
    is_taste_tag,
    load_album_documents,
)


def candidate_features(
    documents: list[dict], vectors: np.ndarray, profile: dict
) -> list[dict]:
    """Calculate semantic and tag evidence without assigning a tier yet."""
    profile_scores = cosine_scores(vectors, profile["vector"])
    favorite_indices = profile["favorite_indices"]
    favorite_scores = np.column_stack(
        [cosine_scores(vectors, vectors[index]) for index in favorite_indices]
    )
    favorite_index_set = set(favorite_indices)

    favorite_tag_sets = [
        {tag for tag in documents[index]["tags"] if is_taste_tag(tag)}
        for index in favorite_indices
    ]
    all_favorite_tags = set().union(*favorite_tag_sets)

    candidates = []
    for index, album in enumerate(documents):
        if index in favorite_index_set:
            continue

        candidate_tags = {tag for tag in album["tags"] if is_taste_tag(tag)}
        shared_tags = candidate_tags.intersection(all_favorite_tags)
        new_tags = candidate_tags - all_favorite_tags
        novelty_ratio = len(new_tags) / max(len(candidate_tags), 1)

        shared_by_favorite = [
            candidate_tags.intersection(tags) for tags in favorite_tag_sets
        ]
        bridge_position = max(
            range(len(favorite_indices)),
            key=lambda position: (
                len(shared_by_favorite[position]),
                favorite_scores[index, position],
            ),
        )
        bridge_tags = shared_by_favorite[bridge_position]
        familiarity = min(len(bridge_tags) / 3, 1.0)
        bridge_similarity = float(favorite_scores[index, bridge_position])
        profile_similarity = float(profile_scores[index])

        # These are deliberately simple heuristics, not learned probabilities.
        safe_score = (
            0.70 * profile_similarity
            + 0.20 * bridge_similarity
            + 0.10 * familiarity
        )
        novelty_balance = 1.0 - abs(novelty_ratio - 0.65)
        explore_score = (
            0.55 * profile_similarity
            + 0.20 * bridge_similarity
            + 0.10 * familiarity
            + 0.15 * novelty_balance
        )
        wildcard_score = (
            0.45 * bridge_similarity
            + 0.25 * familiarity
            + 0.30 * max(0.0, 1.0 - profile_similarity)
        )

        candidates.append(
            {
                "title": album["title"],
                "artists": album["artists"],
                "profile_similarity": profile_similarity,
                "bridge_favorite": profile["favorite_titles"][bridge_position],
                "bridge_similarity": bridge_similarity,
                "shared_tags": sorted(shared_tags),
                "bridge_tags": sorted(bridge_tags),
                "new_tags": sorted(new_tags),
                "novelty_ratio": novelty_ratio,
                "safe_score": safe_score,
                "explore_score": explore_score,
                "wildcard_score": wildcard_score,
            }
        )

    return candidates


def choose_recommendations(candidates: list[dict], per_tier: int) -> dict:
    """Assign every candidate once, then limit how many results are displayed."""
    median_similarity = float(
        np.median([candidate["profile_similarity"] for candidate in candidates])
    )

    safe_pool = [
        candidate
        for candidate in candidates
        if candidate["profile_similarity"] >= median_similarity
        and candidate["bridge_similarity"] >= 0.65
        and len(candidate["bridge_tags"]) >= 2
        and candidate["novelty_ratio"] <= 0.60
    ]
    assigned_titles = {item["title"] for item in safe_pool}

    wildcard_pool = [
        candidate
        for candidate in candidates
        if candidate["title"] not in assigned_titles
        and candidate["profile_similarity"] <= median_similarity
        and candidate["bridge_tags"]
        and candidate["bridge_similarity"] >= 0.55
    ]
    assigned_titles.update(item["title"] for item in wildcard_pool)

    explore_pool = [
        candidate
        for candidate in candidates
        if candidate["title"] not in assigned_titles
        and candidate["bridge_tags"]
        and len(candidate["new_tags"]) >= 2
    ]

    safe = sorted(
        safe_pool, key=lambda item: item["safe_score"], reverse=True
    )[:per_tier]
    explore = sorted(
        explore_pool, key=lambda item: item["explore_score"], reverse=True
    )[:per_tier]
    wildcard = sorted(
        wildcard_pool, key=lambda item: item["wildcard_score"], reverse=True
    )[:per_tier]

    return {"Safe": safe, "Explore": explore, "Wildcard": wildcard}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument(
        "--favorite",
        action="append",
        required=True,
        help="Favorite album title; repeat this option for multiple favorites.",
    )
    parser.add_argument("--per-tier", type=int, default=3)
    parser.add_argument(
        "--explain-tier",
        choices=("Safe", "Explore", "Wildcard"),
        help="Generate Why This? for one result in this tier",
    )
    parser.add_argument(
        "--explain-rank",
        type=int,
        default=1,
        help="One-based result rank to explain within --explain-tier",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.per_tier < 1:
        raise SystemExit("--per-tier must be at least 1")
    if args.explain_rank < 1:
        raise SystemExit("--explain-rank must be at least 1")

    documents = load_album_documents(args.database)
    vectors = embed_documents(documents)
    try:
        profile = build_taste_profile(documents, vectors, args.favorite)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    candidates = candidate_features(documents, vectors, profile)
    recommendations = choose_recommendations(candidates, args.per_tier)

    print(f'Favorites: {", ".join(profile["favorite_titles"])}')
    for tier, items in recommendations.items():
        print(f"\n{tier}")
        if not items:
            print("  No candidate met this tier's evidence rules.")
            continue
        for rank, item in enumerate(items, start=1):
            artists = ", ".join(item["artists"])
            shared = ", ".join(item["bridge_tags"])
            new = ", ".join(item["new_tags"][:4]) or "none"
            print(f'  {rank}. {artists} — {item["title"]}')
            print(
                f'     profile={item["profile_similarity"]:.4f}; '
                f'bridge={item["bridge_favorite"]} '
                f'({item["bridge_similarity"]:.4f})'
            )
            print(f"     bridge tags: {shared}; new tags: {new}")

    if not args.explain_tier:
        return

    tier_items = recommendations[args.explain_tier]
    if args.explain_rank > len(tier_items):
        raise SystemExit(
            f"{args.explain_tier} has only {len(tier_items)} result(s); "
            f"cannot explain rank {args.explain_rank}"
        )

    recommendation = tier_items[args.explain_rank - 1]
    chunks = load_review_chunks(args.database)
    if not chunks:
        raise SystemExit("No licensed review chunks are available")
    review_model, review_vectors = embed_chunks(chunks)
    rag_result = build_context(
        documents,
        chunks,
        review_vectors,
        review_model,
        recommendation["bridge_favorite"],
        recommendation["title"],
        top_k=2,
    )
    try:
        explanation = generate_why_this(
            rag_result,
            tier=args.explain_tier,
            recommendation=recommendation,
        )
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error

    print(
        f'\nWhy This? — {args.explain_tier} #{args.explain_rank}: '
        f'{recommendation["title"]}'
    )
    print(json.dumps(explanation, ensure_ascii=False, indent=2))
    print("\nSources")
    for source in rag_result["sources"]:
        print(
            f"{source['source_id']} | {source['album_title']} | "
            f"{source['source']} | {source['source_url']}"
        )


if __name__ == "__main__":
    main()
