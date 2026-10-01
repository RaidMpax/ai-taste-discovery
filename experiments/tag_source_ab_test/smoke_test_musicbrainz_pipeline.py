"""Run five local profile/recommendation/RAG smoke cases after tag migration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from rag import (
    build_context,
    build_taste_analysis_context,
    embed_chunks,
    generate_taste_analysis,
    generate_why_this,
    load_review_chunks,
)
from recommend import candidate_features, choose_recommendations
from semantic_search import (
    DEFAULT_DATABASE,
    build_taste_profile,
    embed_documents,
    load_album_documents,
)


SMOKE_PROFILES = {
    "mainstream pop": ["BRAT", "HIT ME HARD AND SOFT", "30"],
    "alternative / indie": ["OK Computer", "Is This It", "Punisher"],
    "electronic": ["Dummy", "Untrue", "Vespertine"],
    "experimental": ["Homogenic", "LONG SEASON", "The ArchAndroid"],
    "mixed taste": ["MOTOMAMI", "Madvillainy", "Vespertine"],
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument(
        "--live-gemini",
        action="store_true",
        help="Make one Taste Analysis and one Why This? API call for the pop case.",
    )
    args = parser.parse_args()

    documents = load_album_documents(args.database)
    album_vectors = embed_documents(documents)
    review_chunks = load_review_chunks(args.database)
    review_model, review_vectors = embed_chunks(review_chunks)

    cases = []
    live_gemini = {"status": "not_requested"}
    for label, favorite_titles in SMOKE_PROFILES.items():
        profile = build_taste_profile(documents, album_vectors, favorite_titles)
        candidates = candidate_features(documents, album_vectors, profile)
        tiers = choose_recommendations(candidates, per_tier=3)
        analysis_context = build_taste_analysis_context(
            profile, review_chunks, review_vectors, review_model, top_k_per_seed=1
        )

        tier_results = {}
        first_why_context = None
        for tier in ("Safe", "Explore", "Wildcard"):
            recommendations = tiers[tier]
            tier_results[tier] = [
                {
                    "title": item["title"],
                    "artist": ", ".join(item["artists"]),
                    "bridge_tags": item["bridge_tags"],
                    "profile_similarity": round(item["profile_similarity"], 4),
                }
                for item in recommendations[:1]
            ]
            if recommendations:
                context = build_context(
                    documents,
                    review_chunks,
                    review_vectors,
                    review_model,
                    favorite_titles[0],
                    recommendations[0]["title"],
                    top_k=2,
                )
                if "[STRUCTURED FACTS]" not in context["context"]:
                    raise RuntimeError(f"{label}: Why This? context is incomplete")
                if tier == "Safe":
                    first_why_context = (tier, recommendations[0], context)

        cases.append(
            {
                "taste": label,
                "seeds": favorite_titles,
                "seed_count": len(profile["seed_albums"]),
                "taste_analysis_context_built": bool(analysis_context["context"]),
                "taste_analysis_review_sources": len(analysis_context["sources"]),
                "recommendation_counts": {
                    tier: len(items) for tier, items in tier_results.items()
                },
                "recommendations": tier_results,
                "why_context_built_for_each_populated_tier": True,
                "example_why_review_sources": (
                    len(first_why_context[2]["sources"]) if first_why_context else 0
                ),
            }
        )

        if args.live_gemini and label == "mainstream pop":
            if first_why_context is None:
                live_gemini["status"] = "no_safe_recommendation"
            else:
                tier, recommendation, why_context = first_why_context
                live_gemini = {}
                try:
                    generate_taste_analysis(analysis_context)
                    live_gemini["taste_analysis"] = "passed"
                except Exception as error:
                    live_gemini["taste_analysis"] = f"failed: {type(error).__name__}"
                try:
                    generate_why_this(
                        why_context,
                        tier=tier,
                        recommendation=recommendation,
                    )
                    live_gemini["why_this"] = "passed"
                except Exception as error:
                    live_gemini["why_this"] = f"failed: {type(error).__name__}"

    no_tag_seed = next((album for album in documents if not album["tags"]), None)
    no_tag_seed_result = None
    if no_tag_seed:
        profile = build_taste_profile(
            documents, album_vectors, [no_tag_seed["title"]]
        )
        candidates = candidate_features(documents, album_vectors, profile)
        recommendations = choose_recommendations(candidates, per_tier=3)
        no_tag_seed_result = {
            "seed_title": no_tag_seed["title"],
            "artist": ", ".join(no_tag_seed["artists"]),
            "tag_count": 0,
            "recommendation_counts": {
                tier: len(items) for tier, items in recommendations.items()
            },
        }

    report = {
        "catalogue_size": len(documents),
        "album_embedding_shape": list(album_vectors.shape),
        "album_embedding_finite": bool(album_vectors.size and np.isfinite(album_vectors).all()),
        "review_chunks": len(review_chunks),
        "review_embedding_shape": list(review_vectors.shape),
        "tag_source": "musicbrainz (loader default)",
        "cases": cases,
        "no_tag_seed_edge_case": no_tag_seed_result,
        "live_gemini": live_gemini,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
