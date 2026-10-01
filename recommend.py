"""Day 6: transparent Safe / Explore / Wildcard recommendation rules."""

from __future__ import annotations

import argparse
from itertools import combinations, product
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


BATTLE_POOL_LIMIT = 24
BATTLE_SIMILARITY_GAP = 0.08
BATTLE_TOURNAMENT_SIZE = 8


def candidate_features(
    documents: list[dict], vectors: np.ndarray, profile: dict
) -> list[dict]:
    """Calculate inspectable semantic, tag, novelty, and score signals."""
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
        embedding_distance = 1.0 - profile_similarity

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
                "release_group_mbid": album["release_group_mbid"],
                "title": album["title"],
                "artists": album["artists"],
                "profile_similarity": profile_similarity,
                "embedding_similarity": profile_similarity,
                "embedding_distance": embedding_distance,
                "bridge_favorite": profile["favorite_titles"][bridge_position],
                "bridge_similarity": bridge_similarity,
                "shared_tags": sorted(shared_tags),
                "bridge_tags": sorted(bridge_tags),
                "bridge_tag_overlap_count": len(bridge_tags),
                "tag_familiarity": familiarity,
                "new_tags": sorted(new_tags),
                "novelty_ratio": novelty_ratio,
                "novelty_balance": novelty_balance,
                "safe_score": safe_score,
                "explore_score": explore_score,
                "wildcard_score": wildcard_score,
                "score_components": {
                    "Safe": {
                        "embedding": 0.70 * profile_similarity,
                        "bridge": 0.20 * bridge_similarity,
                        "tag_familiarity": 0.10 * familiarity,
                    },
                    "Explore": {
                        "embedding": 0.55 * profile_similarity,
                        "bridge": 0.20 * bridge_similarity,
                        "tag_familiarity": 0.10 * familiarity,
                        "novelty_balance": 0.15 * novelty_balance,
                    },
                    "Wildcard": {
                        "bridge": 0.45 * bridge_similarity,
                        "tag_familiarity": 0.25 * familiarity,
                        "embedding_distance": 0.30 * max(0.0, embedding_distance),
                    },
                },
                "assigned_tier": None,
                "tier_rank": None,
                "final_score": None,
                "median_profile_similarity": None,
                "shown_in_ui": False,
                "assignment_reason": "未满足任何档位规则。",
            }
        )

    return candidates


def choose_recommendations(candidates: list[dict], per_tier: int) -> dict:
    """Assign eligible candidates once, then limit how many are displayed."""
    if per_tier < 1:
        raise ValueError("per_tier must be at least 1")
    for candidate in candidates:
        candidate["assigned_tier"] = None
        candidate["tier_rank"] = None
        candidate["final_score"] = None
        candidate["median_profile_similarity"] = None
        candidate["shown_in_ui"] = False
        candidate["assignment_reason"] = "未满足任何档位规则。"
    if not candidates:
        return {"Safe": [], "Explore": [], "Wildcard": []}

    median_similarity = float(
        np.median([candidate["profile_similarity"] for candidate in candidates])
    )
    for candidate in candidates:
        candidate["median_profile_similarity"] = median_similarity

    safe_pool = [
        candidate
        for candidate in candidates
        if candidate["profile_similarity"] >= median_similarity
        and candidate["bridge_similarity"] >= 0.65
        and len(candidate["bridge_tags"]) >= 2
        and candidate["novelty_ratio"] <= 0.60
    ]
    assigned_ids = {item["release_group_mbid"] for item in safe_pool}

    wildcard_pool = [
        candidate
        for candidate in candidates
        if candidate["release_group_mbid"] not in assigned_ids
        and candidate["profile_similarity"] <= median_similarity
        and candidate["bridge_tags"]
        and candidate["bridge_similarity"] >= 0.55
    ]
    assigned_ids.update(item["release_group_mbid"] for item in wildcard_pool)

    explore_pool = [
        candidate
        for candidate in candidates
        if candidate["release_group_mbid"] not in assigned_ids
        and candidate["bridge_tags"]
        and len(candidate["new_tags"]) >= 2
    ]

    tier_pools = {
        "Safe": (
            safe_pool,
            "safe_score",
            "profile 相似度 ≥ 中位数；bridge 相似度 ≥ 0.65；bridge 标签 ≥ 2；新颖比例 ≤ 0.60。",
        ),
        "Explore": (
            explore_pool,
            "explore_score",
            "未分入 Safe 或 Wildcard；存在 bridge 标签；至少 2 个新标签。",
        ),
        "Wildcard": (
            wildcard_pool,
            "wildcard_score",
            "未分入 Safe；profile 相似度 ≤ 中位数；有 bridge 标签；bridge 相似度 ≥ 0.55。",
        ),
    }
    results = {}
    for tier, (pool, score_key, reason) in tier_pools.items():
        ranked = sorted(pool, key=lambda item: item[score_key], reverse=True)
        for rank, candidate in enumerate(ranked, start=1):
            candidate["assigned_tier"] = tier
            candidate["tier_rank"] = rank
            candidate["final_score"] = candidate[score_key]
            candidate["shown_in_ui"] = rank <= per_tier
            candidate["assignment_reason"] = reason
        results[tier] = ranked[:per_tier]

    return results


def build_battle_pairs(
    candidates: list[dict], strategy: str
) -> list[tuple[dict, dict]]:
    """Build deterministic evaluation pairs from tier rank or signal contrast."""
    if strategy not in {
        "safe_vs_explore",
        "explore_vs_wildcard",
        "similarity_vs_tag_overlap",
    }:
        raise ValueError(f"Unknown Taste Battle strategy: {strategy}")

    def top_tier(tier: str) -> list[dict]:
        return sorted(
            (item for item in candidates if item["assigned_tier"] == tier),
            key=lambda item: item["tier_rank"],
        )[:BATTLE_POOL_LIMIT]

    if strategy == "safe_vs_explore":
        safe = top_tier("Safe")
        explore = top_tier("Explore")
        pairs = list(product(safe, explore))
        return sorted(
            pairs,
            key=lambda pair: (
                pair[0]["tier_rank"] + pair[1]["tier_rank"],
                pair[0]["release_group_mbid"],
                pair[1]["release_group_mbid"],
            ),
        )

    if strategy == "explore_vs_wildcard":
        explore = top_tier("Explore")
        wildcard = top_tier("Wildcard")
        pairs = list(product(explore, wildcard))
        return sorted(
            pairs,
            key=lambda pair: (
                pair[0]["tier_rank"] + pair[1]["tier_rank"],
                pair[0]["release_group_mbid"],
                pair[1]["release_group_mbid"],
            ),
        )

    eligible = [
        item
        for tier in ("Safe", "Explore", "Wildcard")
        for item in top_tier(tier)
    ]
    pairs = [
        (left, right)
        for left, right in combinations(eligible, 2)
        if left["bridge_tag_overlap_count"] != right["bridge_tag_overlap_count"]
        and abs(left["embedding_similarity"] - right["embedding_similarity"])
        <= BATTLE_SIMILARITY_GAP
    ]
    return sorted(
        pairs,
        key=lambda pair: (
            abs(pair[0]["embedding_similarity"] - pair[1]["embedding_similarity"]),
            -abs(pair[0]["bridge_tag_overlap_count"] - pair[1]["bridge_tag_overlap_count"]),
            pair[0]["release_group_mbid"],
            pair[1]["release_group_mbid"],
        ),
    )


def build_battle_participants(
    candidates: list[dict], strategy: str, max_players: int = BATTLE_TOURNAMENT_SIZE
) -> list[dict]:
    """Choose a balanced, deterministic power-of-two tournament field."""
    if max_players < 2:
        raise ValueError("A Taste Battle tournament needs at least two players")
    first_round_pairs = []
    seen_ids = set()
    for left, right in build_battle_pairs(candidates, strategy):
        pair_ids = {left["release_group_mbid"], right["release_group_mbid"]}
        if pair_ids.isdisjoint(seen_ids):
            first_round_pairs.append((left, right))
            seen_ids.update(pair_ids)
            if len(first_round_pairs) >= max_players // 2:
                break
    if not first_round_pairs:
        return []

    # Preserve the pairing rule in round one, then keep only complete brackets.
    match_count = 1
    while match_count * 2 <= len(first_round_pairs):
        match_count *= 2
    return [
        album
        for pair in first_round_pairs[:match_count]
        for album in pair
    ]


def resolve_battle_tournament(
    participants: list[dict], choices_by_pair: dict[tuple[str, str], str]
) -> dict:
    """Return the next unfinished match, or the tournament winner."""
    if len(participants) < 2 or len(participants) & (len(participants) - 1):
        raise ValueError("Tournament participants must be a power of two, at least two")

    total_matches = len(participants) - 1
    current_round = list(participants)
    completed_matches = 0
    round_number = 1
    while len(current_round) > 1:
        winners = []
        for match_index in range(0, len(current_round), 2):
            left = current_round[match_index]
            right = current_round[match_index + 1]
            pair_key = tuple(
                sorted((left["release_group_mbid"], right["release_group_mbid"]))
            )
            chosen_mbid = choices_by_pair.get(pair_key)
            if chosen_mbid not in pair_key:
                return {
                    "complete": False,
                    "left": left,
                    "right": right,
                    "round_number": round_number,
                    "completed_matches": completed_matches,
                    "total_matches": total_matches,
                }
            winners.append(
                left if chosen_mbid == left["release_group_mbid"] else right
            )
            completed_matches += 1
        current_round = winners
        round_number += 1

    return {
        "complete": True,
        "winner": current_round[0],
        "round_number": round_number - 1,
        "completed_matches": total_matches,
        "total_matches": total_matches,
    }


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
