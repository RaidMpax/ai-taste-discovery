"""Run a small, deterministic offline comparison of recommendation signals."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

import numpy as np

from recommend import candidate_features, choose_recommendations
from semantic_search import (
    DEFAULT_DATABASE,
    MODEL_NAME,
    build_taste_profile,
    embed_documents,
    load_album_documents,
)


TIER_ORDER = ("Safe", "Explore", "Wildcard")
METHOD_DEFINITIONS = {
    "embedding_only": "Rank all non-seed albums by cosine similarity to the Taste Profile.",
    "embedding_plus_tags": (
        "Rank all non-seed albums by the existing Safe score: "
        "0.70 × profile similarity + 0.20 × bridge similarity "
        "+ 0.10 × tag familiarity."
    ),
    "full_ranking": (
        "Use the current Safe / Explore / Wildcard eligibility rules and "
        "tier-specific score; show up to the requested limit per tier."
    ),
}


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _pairwise_cosine_distance(
    items: list[dict], vectors: np.ndarray, index_by_mbid: dict[str, int]
) -> float | None:
    distances = []
    for left_index in range(len(items)):
        left = vectors[index_by_mbid[items[left_index]["release_group_mbid"]]]
        left_norm = max(float(np.linalg.norm(left)), 1e-12)
        for right_index in range(left_index + 1, len(items)):
            right = vectors[index_by_mbid[items[right_index]["release_group_mbid"]]]
            right_norm = max(float(np.linalg.norm(right)), 1e-12)
            cosine = float(np.dot(left, right) / (left_norm * right_norm))
            distances.append(1.0 - min(1.0, max(-1.0, cosine)))
    return _mean(distances)


def _serialize_item(
    candidate: dict, tier: str | None, rank: int, score: float
) -> dict:
    return {
        "release_group_mbid": candidate["release_group_mbid"],
        "title": candidate["title"],
        "artists": candidate["artists"],
        "tier": tier,
        "rank": rank,
        "ranking_score": float(score),
        "embedding_similarity": float(candidate["embedding_similarity"]),
        "bridge_similarity": float(candidate["bridge_similarity"]),
        "bridge_tags": candidate["bridge_tags"],
        "new_tags": candidate["new_tags"],
    }


def _metrics(
    items: list[dict], vectors: np.ndarray, index_by_mbid: dict[str, int]
) -> dict:
    primary_artists = [
        item["artists"][0] if item["artists"] else "(unknown)" for item in items
    ]
    artist_counts = Counter(primary_artists)
    similarities = [item["embedding_similarity"] for item in items]
    return {
        "recommendation_count": len(items),
        "unique_album_count": len(
            {item["release_group_mbid"] for item in items}
        ),
        "unique_primary_artist_count": len(artist_counts),
        "top_primary_artist_share": (
            max(artist_counts.values()) / len(items) if items else None
        ),
        "mean_profile_similarity": _mean(similarities),
        "mean_pairwise_cosine_distance": _pairwise_cosine_distance(
            items, vectors, index_by_mbid
        ),
    }


def evaluate_recommendation_variants(
    documents: list[dict], vectors: np.ndarray, favorite_titles: list[str], per_tier: int
) -> dict:
    """Compare two simple global baselines with the full tiered recommender."""
    if per_tier < 1:
        raise ValueError("per_tier must be at least 1")
    if len(documents) != len(vectors):
        raise ValueError("Document and embedding counts must match")

    profile = build_taste_profile(documents, vectors, favorite_titles)
    candidates = candidate_features(documents, vectors, profile)
    tier_results = choose_recommendations(candidates, per_tier)
    index_by_mbid = {
        album["release_group_mbid"]: index
        for index, album in enumerate(documents)
    }
    comparison_limit = 3 * per_tier

    embedding_ranked = sorted(
        candidates,
        key=lambda item: (
            -item["embedding_similarity"],
            item["release_group_mbid"],
        ),
    )[:comparison_limit]
    tag_ranked = sorted(
        candidates,
        key=lambda item: (-item["safe_score"], item["release_group_mbid"]),
    )[:comparison_limit]

    method_items = {
        "embedding_only": [
            _serialize_item(item, None, rank, item["embedding_similarity"])
            for rank, item in enumerate(embedding_ranked, start=1)
        ],
        "embedding_plus_tags": [
            _serialize_item(item, None, rank, item["safe_score"])
            for rank, item in enumerate(tag_ranked, start=1)
        ],
        "full_ranking": [
            _serialize_item(item, tier, rank, item["final_score"])
            for tier in TIER_ORDER
            for rank, item in enumerate(tier_results[tier], start=1)
        ],
    }

    methods = {}
    embedding_ids = {
        item["release_group_mbid"] for item in method_items["embedding_only"]
    }
    for method, items in method_items.items():
        methods[method] = {
            "definition": METHOD_DEFINITIONS[method],
            "metrics": _metrics(items, vectors, index_by_mbid),
            "overlap_with_embedding_only": (
                len(embedding_ids & {item["release_group_mbid"] for item in items})
                / len(embedding_ids)
                if embedding_ids
                else None
            ),
            "items": items,
        }

    full_items = method_items["full_ranking"]
    tier_means = {
        tier: _mean(
            [
                item["embedding_similarity"]
                for item in full_items
                if item["tier"] == tier
            ]
        )
        for tier in TIER_ORDER
    }
    available_means = [tier_means[tier] for tier in TIER_ORDER]
    monotonic_separation = (
        all(value is not None for value in available_means)
        and available_means[0] >= available_means[1] >= available_means[2]
    )

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "catalogue_size": len(documents),
        "embedding_model": MODEL_NAME,
        "profile": {
            "favorite_titles": profile["favorite_titles"],
            "aggregation_method": profile["aggregation_method"],
        },
        "settings": {
            "per_tier": per_tier,
            "baseline_result_limit": comparison_limit,
        },
        "quality_labels_available": False,
        "interpretation_limit": (
            "These are ranking diagnostics, not evidence of user preference or "
            "recommendation accuracy. Review the listed albums manually and use "
            "Taste Battle feedback for future exploratory analysis."
        ),
        "tier_separation": {
            "mean_embedding_similarity_by_tier": tier_means,
            "safe_ge_explore_ge_wildcard": monotonic_separation,
        },
        "methods": methods,
    }


def render_markdown_report(report: dict) -> str:
    def display(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    lines = [
        "# V2 Offline Recommendation Evaluation",
        "",
        f"Generated: {report['generated_at']}",
        f"Catalogue: {report['catalogue_size']} accepted albums",
        f"Embedding model: `{report['embedding_model']}`",
        f"Favorite albums: {', '.join(report['profile']['favorite_titles'])}",
        f"Seed aggregation: `{report['profile']['aggregation_method']}`",
        "",
        "## Ablation summary",
        "",
        "| Method | Results | Mean taste similarity | Mean pairwise distance | Unique lead artists | Top artist share | Overlap with embedding-only |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, result in report["methods"].items():
        metrics = result["metrics"]
        lines.append(
            f"| {method} | {metrics['recommendation_count']} "
            f"| {display(metrics['mean_profile_similarity'])} "
            f"| {display(metrics['mean_pairwise_cosine_distance'])} "
            f"| {metrics['unique_primary_artist_count']} "
            f"| {display(metrics['top_primary_artist_share'])} "
            f"| {display(result['overlap_with_embedding_only'])} |"
        )

    lines.extend(
        [
            "",
            "## Full-ranking tier separation",
            "",
            "Mean profile cosine similarity by displayed tier: "
            + ", ".join(
                f"{tier} {display(value)}"
                for tier, value in report["tier_separation"][
                    "mean_embedding_similarity_by_tier"
                ].items()
            )
            + ".",
            "",
            "## Results to inspect manually",
            "",
        ]
    )
    for method, result in report["methods"].items():
        lines.append(f"### {method}")
        lines.append("")
        for item in result["items"]:
            tier = f" / {item['tier']}" if item["tier"] else ""
            artist = ", ".join(item["artists"]) or "Unknown artist"
            lines.append(
                f"- {item['rank']}. {artist} — *{item['title']}*{tier}; "
                f"score {item['ranking_score']:.3f}, "
                f"embedding {item['embedding_similarity']:.3f}, "
                f"bridge tags: {', '.join(item['bridge_tags']) or 'none'}"
            )
        lines.append("")

    lines.extend(
        [
            "## Reading this report",
            "",
            report["interpretation_limit"],
            "",
            "When reviewing results, check for wrong album matches, seed albums "
            "reappearing, repetitive lead artists, tier mismatches, and weak or "
            "forced tag bridges. More pairwise feedback is needed before drawing "
            "conclusions about user preference.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--favorite", action="append", required=True)
    parser.add_argument("--per-tier", type=int, default=3)
    parser.add_argument("--json-out", type=Path, default=Path("EVALUATION_REPORT_V2.json"))
    parser.add_argument("--markdown-out", type=Path, default=Path("EVALUATION_REPORT_V2.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    documents = load_album_documents(args.database)
    vectors = embed_documents(documents)
    report = evaluate_recommendation_variants(
        documents, vectors, args.favorite, args.per_tier
    )
    args.json_out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_out.write_text(render_markdown_report(report), encoding="utf-8")
    print(f"Wrote {args.json_out} and {args.markdown_out}")


if __name__ == "__main__":
    main()
