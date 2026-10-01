"""Small, isolated comparison of album tags from three providers.

Reads the existing catalogue in SQLite read-only mode. All sample, API cache,
and experiment outputs are written under this directory. It never writes to
the catalogue database or the production embedding/recommendation files.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np


EXPERIMENT_DIR = Path(__file__).resolve().parent
ROOT = EXPERIMENT_DIR.parents[1]
DATABASE_PATH = ROOT / "taste.db"
MANIFEST_PATH = ROOT / "album_match_manifest.json"
CACHE_PATH = EXPERIMENT_DIR / "api_cache.json"
SAMPLE_PATH = EXPERIMENT_DIR / "sample_albums.json"
SOURCE_DATA_PATH = EXPERIMENT_DIR / "tag_source_data.json"
IMPACT_PATH = EXPERIMENT_DIR / "recommendation_impact.json"
USER_AGENT = "AI-Taste-Discovery-tag-source-test/0.1 (https://github.com/RaidMpax/ai-taste-discovery)"
REQUEST_DELAY_SECONDS = 1.1
SAMPLE_SIZE = 50
RANDOM_SEED = 20260930

GENRE_QUOTAS = {
    "pop": 8,
    "electronic": 8,
    "rock_alt": 8,
    "hiphop_rnb": 8,
    "experimental": 7,
    "latin": 4,
    "other": 7,
}
TAG_COUNT_QUOTAS = {"none": 2, "sparse": 3, "medium": 4, "rich": 41}


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_tag(tag: str) -> str:
    value = " ".join(tag.strip().casefold().split())
    # Match the project's small, existing alias map without changing it.
    return {"inide": "indie", "jpop": "j-pop", "trip hop": "trip-hop"}.get(value, value)


def primary_genre(tags: list[str]) -> str:
    normalized = [normalize_tag(tag) for tag in tags]
    has_korean_pop = any(tag in {"k-pop", "kpop", "korean"} for tag in normalized)
    rules = [
        ("experimental", ("experimental", "avant-garde", "avant garde", "noise", "deconstructed", "drone")),
        ("latin", ("reggaeton", "dembow", "spanish", "salsa", "bachata", "latin")),
        ("hiphop_rnb", ("hip-hop", "hip hop", "rap", "r&b", "rnb", "rhythm and blues", "soul", "trap")),
        ("electronic", ("electronic", "synthpop", "synth-pop", "techno", "house", "ambient", "hyperpop", "dance music", "electro")),
        ("rock_alt", ("rock", "indie", "punk", "metal", "shoegaze", "post-punk", "grunge", "alternative")),
        ("pop", ("pop", "k-pop", "kpop", "dance-pop")),
    ]
    counts: Counter = Counter()
    for tag in normalized:
        for category, words in rules:
            # “Latin pop” is not enough to call a Korean/K-pop album Latin music.
            if category == "latin" and has_korean_pop and tag == "latin pop":
                continue
            if any(word in tag for word in words):
                counts[category] += 1
                break
    if not counts:
        return "other"
    priority = {name: index for index, (name, _) in enumerate(rules)}
    return min(counts, key=lambda category: (-counts[category], priority[category]))


def tag_count_bucket(count: int) -> str:
    if count == 0:
        return "none"
    if count <= 3:
        return "sparse"
    if count <= 7:
        return "medium"
    return "rich"


def load_catalogue() -> list[dict]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    accepted_mbids = {
        item["release_group_mbid"]
        for item in manifest["albums"]
        if item.get("status") == "accepted"
    }
    # mode=ro makes accidental SQL writes fail instead of touching taste.db.
    connection = sqlite3.connect(DATABASE_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    albums: dict[str, dict] = {}
    for row in connection.execute(
        "SELECT release_group_mbid, title, release_year FROM albums ORDER BY title"
    ):
        mbid = row["release_group_mbid"]
        if mbid in accepted_mbids:
            albums[mbid] = {
                "release_group_mbid": mbid,
                "title": row["title"],
                "release_year": row["release_year"],
                "artists": [],
                "lastfm_tags": [],
            }
    for row in connection.execute(
        """SELECT aa.release_group_mbid, ar.name
           FROM album_artists aa JOIN artists ar ON ar.artist_mbid = aa.artist_mbid
           ORDER BY aa.release_group_mbid, aa.credit_order"""
    ):
        if row["release_group_mbid"] in albums:
            albums[row["release_group_mbid"]]["artists"].append(row["name"])
    for row in connection.execute(
        """SELECT release_group_mbid, raw_tag, normalized_tag, tag_rank
           FROM album_tags WHERE source='lastfm'
           ORDER BY release_group_mbid, tag_rank"""
    ):
        item = albums.get(row["release_group_mbid"])
        if item is not None:
            item["lastfm_tags"].append(
                {
                    "name": row["normalized_tag"],
                    "raw_name": row["raw_tag"],
                    "normalized_name": row["normalized_tag"],
                    "rank": row["tag_rank"],
                    "count": None,
                }
            )
    connection.close()
    if len(albums) < SAMPLE_SIZE:
        raise RuntimeError(f"Only {len(albums)} accepted albums found in the read-only catalogue")
    return list(albums.values())


def sample_catalogue(albums: list[dict]) -> list[dict]:
    rng = random.Random(RANDOM_SEED)
    # Avoid obviously damaged display strings in the tiny qualitative sample;
    # the production catalogue itself is left untouched and the issue is noted.
    albums = [
        item for item in albums
        if "\ufffd" not in item["title"]
        and all("\ufffd" not in artist for artist in item["artists"])
    ]
    by_genre: dict[str, list[dict]] = {name: [] for name in GENRE_QUOTAS}
    for album in albums:
        album["sample_genre_stratum"] = primary_genre(
            [tag["name"] for tag in album["lastfm_tags"]]
        )
        album["sample_tag_count_stratum"] = tag_count_bucket(len(album["lastfm_tags"]))
        by_genre.setdefault(album["sample_genre_stratum"], []).append(album)

    selected: list[dict] = []
    selected_ids: set[str] = set()
    genre_counts: Counter = Counter()
    bucket_counts: Counter = Counter()
    decade_counts: Counter = Counter()

    def choose(pool: list[dict]) -> dict | None:
        pool = [item for item in pool if item["release_group_mbid"] not in selected_ids]
        if not pool:
            return None
        def score(item: dict) -> float:
            bucket = item["sample_tag_count_stratum"]
            bucket_need = max(TAG_COUNT_QUOTAS[bucket] - bucket_counts[bucket], 0)
            genre = item["sample_genre_stratum"]
            genre_need = max(GENRE_QUOTAS[genre] - genre_counts[genre], 0)
            year = item["release_year"]
            decade = f"{year // 10 * 10}s" if year else "unknown"
            return (
                (bucket_need / max(TAG_COUNT_QUOTAS[bucket], 1)) * 0.55
                + (genre_need / max(GENRE_QUOTAS[genre], 1)) * 0.25
                + (1.0 / (1 + decade_counts[decade])) * 0.15
                + rng.random() * 0.05
            )
        return max(pool, key=score)

    # Reserve sparse-tag examples first, then fill genre quotas. The catalogue
    # itself is tag-rich, so this slight oversampling makes the missing-tag
    # behavior observable without turning the sample into a tag-poor dataset.
    for bucket in ("none", "sparse", "medium"):
        target = TAG_COUNT_QUOTAS[bucket]
        for _ in range(target):
            picked = choose([item for item in albums if item["sample_tag_count_stratum"] == bucket])
            if picked is None:
                break
            selected.append(picked)
            selected_ids.add(picked["release_group_mbid"])
            genre_counts[picked["sample_genre_stratum"]] += 1
            bucket_counts[bucket] += 1
            year = picked["release_year"]
            decade_counts[f"{year // 10 * 10}s" if year else "unknown"] += 1

    # Fill the genre strata while the density-bucket scorer prefers still-needed
    # tag counts and decades. If a stratum is too small, the final pass fills it.
    for genre, target in GENRE_QUOTAS.items():
        while genre_counts[genre] < target and len(selected) < SAMPLE_SIZE:
            picked = choose(by_genre.get(genre, []))
            if picked is None:
                break
            selected.append(picked)
            selected_ids.add(picked["release_group_mbid"])
            genre_counts[genre] += 1
            bucket_counts[picked["sample_tag_count_stratum"]] += 1
            year = picked["release_year"]
            decade_counts[f"{year // 10 * 10}s" if year else "unknown"] += 1

    # Fill remaining slots by the same deterministic balancing rule.
    while len(selected) < SAMPLE_SIZE:
        picked = choose(albums)
        if picked is None:
            break
        selected.append(picked)
        selected_ids.add(picked["release_group_mbid"])
        genre_counts[picked["sample_genre_stratum"]] += 1
        bucket_counts[picked["sample_tag_count_stratum"]] += 1
        year = picked["release_year"]
        decade_counts[f"{year // 10 * 10}s" if year else "unknown"] += 1

    # Stable order makes generated cache and report diffs easy to inspect.
    selected.sort(key=lambda item: (item["sample_genre_stratum"], item["title"].casefold(), item["release_group_mbid"]))
    return selected


def request_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def is_sandbox_network_error(error: Exception) -> bool:
    return "WinError 10013" in str(error) or getattr(getattr(error, "reason", None), "winerror", None) == 10013


def extract_provider_tags(entries: list[dict]) -> list[dict]:
    tags = []
    seen: set[str] = set()
    for entry in entries:
        name = entry.get("name") or entry.get("tag")
        if not isinstance(name, str) or not name.strip():
            continue
        normalized = normalize_tag(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        tags.append(
            {
                "name": name.strip(),
                "normalized_name": normalized,
                "count": entry.get("count"),
            }
        )
    return tags


def fetch_musicbrainz(sample: list[dict], cache: dict) -> tuple[dict, bool]:
    results = cache.setdefault("musicbrainz", {})
    for index, album in enumerate(sample, start=1):
        mbid = album["release_group_mbid"]
        cached = results.get(mbid)
        if cached and cached.get("status") == "ok":
            continue
        url = f"https://musicbrainz.org/ws/2/release-group/{mbid}?" + urlencode(
            {"inc": "tags+genres", "fmt": "json"}
        )
        try:
            response = request_json(url)
            if response.get("id") != mbid:
                results[mbid] = {"status": "id_mismatch", "tags": []}
            else:
                tags = extract_provider_tags(response.get("tags", []) + response.get("genres", []))
                results[mbid] = {"status": "ok", "tags": tags}
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            results[mbid] = {"status": "network_blocked" if is_sandbox_network_error(error) else "error", "error": str(error)[:240], "tags": []}
            write_json(CACHE_PATH, cache)
            if is_sandbox_network_error(error):
                for remaining in sample[index:]:
                    results.setdefault(remaining["release_group_mbid"], {"status": "not_attempted_after_network_block", "tags": []})
                return results, False
        write_json(CACHE_PATH, cache)
        print(f"MusicBrainz {index}/{len(sample)}: {album['title']}", flush=True)
        if index < len(sample):
            time.sleep(REQUEST_DELAY_SECONDS)
    return results, all(results.get(item["release_group_mbid"], {}).get("status") == "ok" for item in sample)


def fetch_listenbrainz(sample: list[dict], cache: dict) -> tuple[dict, bool]:
    results = cache.setdefault("listenbrainz", {})
    pending = [item for item in sample if results.get(item["release_group_mbid"], {}).get("status") != "ok"]
    for batch_start in range(0, len(pending), 10):
        batch = pending[batch_start : batch_start + 10]
        ids = [item["release_group_mbid"] for item in batch]
        url = "https://api.listenbrainz.org/1/metadata/release_group/?" + urlencode(
            {"release_group_mbids": ",".join(ids), "inc": "tag"}
        )
        try:
            response = request_json(url)
            for mbid in ids:
                album_data = response.get(mbid, {})
                entries = album_data.get("tag", {}).get("release_group", [])
                results[mbid] = {"status": "ok", "tags": extract_provider_tags(entries)}
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            status = "network_blocked" if is_sandbox_network_error(error) else "error"
            for mbid in ids:
                results[mbid] = {"status": status, "error": str(error)[:240], "tags": []}
            write_json(CACHE_PATH, cache)
            if is_sandbox_network_error(error):
                for remaining in pending[batch_start + len(batch) :]:
                    results.setdefault(remaining["release_group_mbid"], {"status": "not_attempted_after_network_block", "tags": []})
                return results, False
        write_json(CACHE_PATH, cache)
        print(f"ListenBrainz batch {batch_start // 10 + 1}: {len(batch)} release groups", flush=True)
        if batch_start + 10 < len(pending):
            time.sleep(REQUEST_DELAY_SECONDS)
    return results, all(results.get(item["release_group_mbid"], {}).get("status") == "ok" for item in sample)


def album_tags(album: dict, provider_data: dict, provider: str) -> list[dict]:
    if provider == "lastfm":
        return album["lastfm_tags"]
    return provider_data.get(album["release_group_mbid"], {}).get("tags", [])


def source_statistics(sample: list[dict], provider_data: dict, provider: str, complete: bool) -> dict:
    if provider == "lastfm":
        statuses = ["ok"] * len(sample)
    else:
        statuses = [provider_data.get(item["release_group_mbid"], {}).get("status", "missing") for item in sample]
    if not complete:
        return {"complete": False, "request_statuses": dict(Counter(statuses)), "tags_available": None}
    counts = [len({tag["normalized_name"] for tag in album_tags(item, provider_data, provider)}) for item in sample]
    return {
        "complete": True,
        "albums_with_tags": sum(count > 0 for count in counts),
        "coverage_percent": round(sum(count > 0 for count in counts) / len(sample) * 100, 1),
        "average_tags_per_album": round(sum(counts) / len(counts), 2),
        "median_tags_per_album": float(np.median(counts)),
        "tag_count_distribution": dict(sorted(Counter(counts).items())),
        "tag_count_buckets": {
            "0": sum(count == 0 for count in counts),
            "1-3": sum(1 <= count <= 3 for count in counts),
            "4-7": sum(4 <= count <= 7 for count in counts),
            "8+": sum(count >= 8 for count in counts),
        },
        "request_statuses": dict(Counter(statuses)),
        "tags_available": sum(counts),
    }


def build_document(album: dict, tags: list[dict]) -> dict:
    unique: dict[str, dict] = {}
    for tag in tags:
        name = tag.get("normalized_name")
        if not name:
            continue
        if name not in unique or (tag.get("count") or 0) > (unique[name].get("count") or 0):
            unique[name] = tag
    if tags and all(isinstance(tag.get("count"), (int, float)) for tag in tags):
        names = sorted(unique, key=lambda name: (-(unique[name].get("count") or 0), name))
    else:
        names = list(unique)
    year = album["release_year"] if album["release_year"] is not None else "unknown"
    text = "\n".join(
        [
            f"Title: {album['title']}",
            f"Artist: {', '.join(album['artists'])}",
            f"Release year: {year}",
            f"Community tags: {', '.join(names)}",
        ]
    )
    return {**album, "tags": names, "document": text}


def tag_quality_category(tag: str) -> str:
    value = normalize_tag(tag)
    if (
        re.fullmatch(r"\d{4}", value)
        or re.match(r"^(best of|best albums of|aoty|favourite albums|favorite albums|collection|albums?)\b", value)
        or re.search(r"\b\d+\s*[+–-]?\s*wochen\b", value)
        or re.match(r"^me\s+\d{2}[–-]\d{2}$", value)
        or value in {"366", "offizielle charts", "musikexpress.de", "artist on cover", "bookmarked", "listen", "skipless albums"}
        or re.match(r"^ph_\d+_stars?$", value)
    ):
        return "potentially_noisy_or_metadata"
    if any(word in value for word in ("dream pop", "shoegaze", "trip-hop", "trip hop", "indietronica", "post-punk", "art pop", "hyperpop", "deconstructed club", "cloud rap", "jazz rap", "neo-soul", "neo soul", "synthpop", "alt-country", "avant-garde")):
        return "specific_subgenre"
    if any(word in value for word in ("female vocalists", "male vocalists", "korean", "japanese", "british", "american", "latin", "k-pop", "j-pop", "spanish")) or re.fullmatch(r"(19|20)\d{2}s", value):
        return "scene_era_or_cultural"
    if any(word in value for word in ("dreamy", "ethereal", "melancholic", "melancholy", "dark", "warm", "atmospheric", "uplifting", "yearning", "nostalgic", "moody")):
        return "mood_or_aesthetic"
    if value in {"pop", "rock", "electronic", "hip-hop", "hip hop", "rap", "r&b", "rnb", "jazz", "folk", "soul", "country", "metal", "classical", "indie", "alternative", "reggae", "latin"}:
        return "broad_genre"
    return "other_or_unclassified"


def source_quality_summary(sample: list[dict], provider_data: dict, provider: str, complete: bool) -> dict:
    if not complete:
        return {}
    categories: Counter = Counter()
    albums_with_specific = 0
    for album in sample:
        tags = list({tag["normalized_name"]: tag for tag in album_tags(album, provider_data, provider)}.values())
        categories.update(tag_quality_category(tag["normalized_name"]) for tag in tags)
        if any(tag_quality_category(tag["normalized_name"]) in {"specific_subgenre", "mood_or_aesthetic", "scene_era_or_cultural"} for tag in tags):
            albums_with_specific += 1
    return {"heuristic_tag_categories": dict(sorted(categories.items())), "albums_with_specific_or_contextual_tags": albums_with_specific}


def choose_seed_cases(sample: list[dict]) -> dict[str, list[str]]:
    rng = random.Random(RANDOM_SEED + 1)
    available = {genre: [item for item in sample if item["sample_genre_stratum"] == genre] for genre in GENRE_QUOTAS}
    for items in available.values():
        rng.shuffle(items)
    title_counts = Counter(item["title"].casefold() for item in sample)
    def two(genre: str) -> list[str]:
        chosen = []
        artists = set()
        for item in available.get(genre, []):
            primary_artist = item["artists"][0].casefold() if item["artists"] else ""
            if title_counts[item["title"].casefold()] == 1 and primary_artist not in artists:
                chosen.append(item["title"])
                artists.add(primary_artist)
            if len(chosen) == 2:
                break
        return chosen
    cases = {
        "Pop (broadly tagged)": two("pop"),
        "Alternative / indie": two("rock_alt"),
        "Electronic": two("electronic"),
        "Experimental": two("experimental"),
    }
    mixed = []
    for genre in ("pop", "hiphop_rnb", "experimental"):
        for title in two(genre):
            if title not in mixed:
                mixed.append(title)
                break
    cases["Mixed taste"] = mixed
    return {name: titles for name, titles in cases.items() if titles}


def compare_recommendations(sample: list[dict], provider_data: dict, provider_complete: dict) -> dict:
    # Imports stay local so the data-coverage part can still run without loading
    # the full UI or any generative-model client.
    sys.path.insert(0, str(ROOT))
    from recommend import candidate_features, choose_recommendations
    from semantic_search import MODEL_CACHE, MODEL_NAME, build_taste_profile
    from fastembed import TextEmbedding

    provider_variants = ["lastfm"]
    if provider_complete.get("musicbrainz"):
        provider_variants.append("musicbrainz")
    if provider_complete.get("listenbrainz"):
        provider_variants.append("listenbrainz")
    if provider_complete.get("musicbrainz") and provider_complete.get("listenbrainz"):
        provider_variants.append("combined")

    documents_by_provider: dict[str, list[dict]] = {}
    def tags_for_source(album: dict, source: str) -> list[dict]:
        source_data = provider_data.get(source, {}) if source != "lastfm" else {}
        return album_tags(album, source_data, source)

    for provider in provider_variants:
        docs = []
        for album in sample:
            if provider == "combined":
                entries = tags_for_source(album, "musicbrainz") + tags_for_source(album, "listenbrainz")
                deduplicated = []
                seen = set()
                for entry in entries:
                    key = entry["normalized_name"]
                    if key not in seen:
                        deduplicated.append(entry)
                        seen.add(key)
                entries = deduplicated
            else:
                entries = tags_for_source(album, provider)
            docs.append(build_document(album, entries))
        documents_by_provider[provider] = docs

    # Reuse the project's exact model. Its files already exist in .cache; the
    # experimental vectors stay in memory and are not written to the catalogue.
    model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(MODEL_CACHE))
    output = {
        "embedding_model": MODEL_NAME,
        "embedding_cache_reused": str(MODEL_CACHE.relative_to(ROOT)),
        "vector_storage": "in-memory only; no vector or database write",
        "providers": {},
        "seed_cases": choose_seed_cases(sample),
    }
    for provider in provider_variants:
        docs = documents_by_provider[provider]
        vectors = np.asarray(list(model.embed([item["document"] for item in docs])), dtype=np.float32)
        variants_result = {"embedding_shape": list(vectors.shape), "cases": {}}
        for case_name, favorite_titles in output["seed_cases"].items():
            if not favorite_titles or any(title.casefold() not in {d["title"].casefold() for d in docs} for title in favorite_titles):
                continue
            profile = build_taste_profile(docs, vectors, favorite_titles)
            candidates = candidate_features(docs, vectors, profile)
            tiers = choose_recommendations(candidates, per_tier=3)
            profile_scores = np.asarray([candidate["profile_similarity"] for candidate in candidates])
            nearest = sorted(candidates, key=lambda item: item["profile_similarity"], reverse=True)[:5]
            variants_result["cases"][case_name] = {
                "seed_albums": favorite_titles,
                "top_profile_neighbors": [
                    {"title": item["title"], "artists": item["artists"], "similarity": round(item["profile_similarity"], 4)}
                    for item in nearest
                ],
                "tiers": {
                    tier: [
                        {
                            "title": item["title"],
                            "artists": item["artists"],
                            "final_score": round(item["final_score"], 4),
                            "bridge_tags": item["bridge_tags"][:4],
                        }
                        for item in items
                    ]
                    for tier, items in tiers.items()
                },
                "eligible_candidate_count": len(candidates),
                "profile_similarity_median_in_sample": round(float(np.median(profile_scores)), 4) if len(profile_scores) else None,
            }
        output["providers"][provider] = variants_result
    return output


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Reading the catalogue in SQLite read-only mode…", flush=True)
    catalogue = load_catalogue()
    sample = sample_catalogue(catalogue)
    write_json(SAMPLE_PATH, {
        "sample_size": len(sample),
        "selection_method": "deterministic stratified sample: Last.fm tag density + broad genre family + decade balancing; damaged replacement-character display strings excluded from this sample only",
        "random_seed": RANDOM_SEED,
        "album_ids_are_musicbrainz_release_group_mbids": True,
        "albums": sample,
    })
    cache = read_json(CACHE_PATH, {"musicbrainz": {}, "listenbrainz": {}})
    print(f"Selected {len(sample)} albums. Fetching MusicBrainz release-group tags (<=1 request/sec)…", flush=True)
    mb_data, mb_complete = fetch_musicbrainz(sample, cache)
    print("Fetching ListenBrainz release-group tag metadata in small batches…", flush=True)
    lb_data, lb_complete = fetch_listenbrainz(sample, cache)

    stats = {
        "Last.fm": source_statistics(sample, {}, "lastfm", True),
        "MusicBrainz": source_statistics(sample, mb_data, "musicbrainz", mb_complete),
        "ListenBrainz": source_statistics(sample, lb_data, "listenbrainz", lb_complete),
    }
    if mb_complete and lb_complete:
        # Combined stats use the same exact normalized-name de-duplication used in embedding text.
        combined_counts = []
        for item in sample:
            names = {
                tag["normalized_name"]
                for tag in album_tags(item, mb_data, "musicbrainz") + album_tags(item, lb_data, "listenbrainz")
            }
            combined_counts.append(len(names))
        stats["MB + LB"] = {
            "complete": True,
            "albums_with_tags": sum(count > 0 for count in combined_counts),
            "coverage_percent": round(sum(count > 0 for count in combined_counts) / len(sample) * 100, 1),
            "average_tags_per_album": round(sum(combined_counts) / len(combined_counts), 2),
            "median_tags_per_album": float(np.median(combined_counts)),
            "tag_count_distribution": dict(sorted(Counter(combined_counts).items())),
            "tag_count_buckets": {
                "0": sum(count == 0 for count in combined_counts),
                "1-3": sum(1 <= count <= 3 for count in combined_counts),
                "4-7": sum(4 <= count <= 7 for count in combined_counts),
                "8+": sum(count >= 8 for count in combined_counts),
            },
            "request_statuses": {"ok": len(sample)},
            "tags_available": sum(combined_counts),
        }

    source_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(sample),
        "sample_mbids": [item["release_group_mbid"] for item in sample],
        "coverage": stats,
        "tag_quality": {
            "Last.fm": source_quality_summary(sample, {}, "lastfm", True),
            "MusicBrainz": source_quality_summary(sample, mb_data, "musicbrainz", mb_complete),
            "ListenBrainz": source_quality_summary(sample, lb_data, "listenbrainz", lb_complete),
        },
        "api_data_file": CACHE_PATH.name,
        "lastfm_data_note": "Loaded from the existing SQLite catalogue; no Last.fm API calls were made.",
    }
    write_json(SOURCE_DATA_PATH, source_data)

    impact = {"status": "not_run", "reason": "MusicBrainz / ListenBrainz requests did not both complete"}
    if mb_complete and lb_complete:
        print("Embedding only the 50 test albums with the existing FastEmbed model…", flush=True)
        impact = compare_recommendations(sample, {"musicbrainz": mb_data, "listenbrainz": lb_data}, {"musicbrainz": mb_complete, "listenbrainz": lb_complete})
        impact["status"] = "complete"
        write_json(IMPACT_PATH, impact)
    write_json(SOURCE_DATA_PATH, source_data)
    write_json(CACHE_PATH, cache)
    print(f"Wrote experiment data under {EXPERIMENT_DIR}", flush=True)
    print("Coverage:", json.dumps(stats, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
