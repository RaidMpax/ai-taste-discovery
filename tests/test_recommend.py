import unittest

import numpy as np

from recommend import (
    build_battle_pairs,
    build_battle_participants,
    candidate_features,
    choose_recommendations,
    resolve_battle_tournament,
)


def candidate(mbid, similarity, bridge, bridge_tags, novelty, new_tags, title=None):
    return {
        "release_group_mbid": mbid,
        "title": title or mbid,
        "profile_similarity": similarity,
        "bridge_similarity": bridge,
        "bridge_tags": bridge_tags,
        "novelty_ratio": novelty,
        "new_tags": new_tags,
        "safe_score": similarity,
        "explore_score": similarity,
        "wildcard_score": similarity,
    }


class CandidateFeatureTests(unittest.TestCase):
    def test_exposes_signals_and_weighted_score_components(self):
        documents = [
            {
                "release_group_mbid": "seed",
                "title": "Seed",
                "artists": ["Seed Artist"],
                "tags": ["dream pop", "indie", "shoegaze"],
            },
            {
                "release_group_mbid": "candidate",
                "title": "Candidate",
                "artists": ["Candidate Artist"],
                "tags": ["dream pop", "indie", "electronic"],
            },
        ]
        vectors = np.asarray([[1.0, 0.0], [0.8, 0.6]], dtype=np.float32)
        profile = {
            "favorite_indices": [0],
            "favorite_titles": ["Seed"],
            "vector": np.asarray([1.0, 0.0], dtype=np.float32),
        }

        result = candidate_features(documents, vectors, profile)[0]

        self.assertEqual(result["bridge_tag_overlap_count"], 2)
        self.assertAlmostEqual(result["tag_familiarity"], 2 / 3)
        self.assertAlmostEqual(result["embedding_distance"], 0.2)
        self.assertAlmostEqual(
            sum(result["score_components"]["Safe"].values()), result["safe_score"]
        )
        self.assertAlmostEqual(
            sum(result["score_components"]["Explore"].values()), result["explore_score"]
        )
        self.assertAlmostEqual(
            sum(result["score_components"]["Wildcard"].values()), result["wildcard_score"]
        )


class TierAssignmentTests(unittest.TestCase):
    def test_assigns_tiers_and_full_pool_ranks_before_display_limit(self):
        candidates = [
            candidate("safe-first", 0.90, 0.80, ["a", "b"], 0.10, [], "Shared title"),
            candidate("safe-second", 0.80, 0.75, ["a", "b"], 0.20, []),
            candidate("wild-first", 0.10, 0.70, ["a"], 0.70, ["x", "y"], "Shared title"),
            candidate("wild-second", 0.20, 0.65, ["a"], 0.60, ["x", "y"]),
            candidate("explore", 0.71, 0.55, ["a"], 0.75, ["x", "y"]),
            candidate("unassigned", 0.40, 0.40, [], 0.50, []),
        ]

        results = choose_recommendations(candidates, per_tier=1)
        by_id = {item["release_group_mbid"]: item for item in candidates}

        self.assertEqual(len(results["Safe"]), 1)
        self.assertEqual(by_id["safe-first"]["assigned_tier"], "Safe")
        self.assertEqual(by_id["safe-first"]["tier_rank"], 1)
        self.assertEqual(by_id["safe-second"]["tier_rank"], 2)
        self.assertTrue(by_id["safe-first"]["shown_in_ui"])
        self.assertFalse(by_id["safe-second"]["shown_in_ui"])
        self.assertEqual(
            by_id["safe-first"]["median_profile_similarity"],
            by_id["unassigned"]["median_profile_similarity"],
        )
        self.assertEqual(by_id["safe-second"]["final_score"], by_id["safe-second"]["safe_score"])
        self.assertEqual(by_id["wild-first"]["assigned_tier"], "Wildcard")
        self.assertEqual(by_id["explore"]["assigned_tier"], "Explore")
        self.assertIsNone(by_id["unassigned"]["assigned_tier"])
        self.assertIsNone(by_id["unassigned"]["final_score"])

    def test_empty_candidates_and_invalid_limit(self):
        self.assertEqual(
            choose_recommendations([], 2),
            {"Safe": [], "Explore": [], "Wildcard": []},
        )
        with self.assertRaisesRegex(ValueError, "at least 1"):
            choose_recommendations([], 0)


def battle_candidate(mbid, tier, rank, similarity, bridge_tags):
    return {
        "release_group_mbid": mbid,
        "assigned_tier": tier,
        "tier_rank": rank,
        "embedding_similarity": similarity,
        "bridge_tag_overlap_count": bridge_tags,
    }


class TasteBattlePairTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            battle_candidate("safe-1", "Safe", 1, 0.90, 1),
            battle_candidate("safe-2", "Safe", 2, 0.80, 2),
            battle_candidate("explore-1", "Explore", 1, 0.79, 4),
            battle_candidate("explore-2", "Explore", 2, 0.70, 3),
            battle_candidate("wild-1", "Wildcard", 1, 0.78, 0),
        ]

    def test_tier_contrast_strategies_pair_the_intended_tiers(self):
        safe_explore = build_battle_pairs(self.candidates, "safe_vs_explore")
        explore_wildcard = build_battle_pairs(
            self.candidates, "explore_vs_wildcard"
        )

        self.assertTrue(safe_explore)
        self.assertTrue(
            all(
                left["assigned_tier"] == "Safe"
                and right["assigned_tier"] == "Explore"
                for left, right in safe_explore
            )
        )
        self.assertTrue(
            all(
                left["assigned_tier"] == "Explore"
                and right["assigned_tier"] == "Wildcard"
                for left, right in explore_wildcard
            )
        )
        self.assertEqual(
            safe_explore,
            build_battle_pairs(self.candidates, "safe_vs_explore"),
        )

    def test_signal_contrast_uses_close_similarity_and_different_tag_overlap(self):
        pairs = build_battle_pairs(self.candidates, "similarity_vs_tag_overlap")
        participants = build_battle_participants(
            self.candidates, "similarity_vs_tag_overlap"
        )

        self.assertTrue(pairs)
        for left, right in pairs:
            self.assertLessEqual(
                abs(left["embedding_similarity"] - right["embedding_similarity"]),
                0.08,
            )
            self.assertNotEqual(
                left["bridge_tag_overlap_count"],
                right["bridge_tag_overlap_count"],
            )
        for index in range(0, len(participants), 2):
            left, right = participants[index : index + 2]
            self.assertLessEqual(
                abs(left["embedding_similarity"] - right["embedding_similarity"]),
                0.08,
            )
            self.assertNotEqual(
                left["bridge_tag_overlap_count"],
                right["bridge_tag_overlap_count"],
            )

    def test_unknown_battle_strategy_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown Taste Battle strategy"):
            build_battle_pairs(self.candidates, "random")

    def test_tournament_is_balanced_and_returns_a_winner_after_three_matches(self):
        participants = build_battle_participants(
            self.candidates, "safe_vs_explore"
        )
        self.assertEqual(
            [item["release_group_mbid"] for item in participants],
            ["safe-1", "explore-1", "safe-2", "explore-2"],
        )
        choices = {
            ("explore-1", "safe-1"): "explore-1",
            ("explore-2", "safe-2"): "safe-2",
        }

        next_match = resolve_battle_tournament(participants, choices)
        self.assertFalse(next_match["complete"])
        self.assertEqual(next_match["completed_matches"], 2)
        self.assertEqual(next_match["round_number"], 2)
        self.assertEqual(
            {
                next_match["left"]["release_group_mbid"],
                next_match["right"]["release_group_mbid"],
            },
            {"explore-1", "safe-2"},
        )

        choices[("explore-1", "safe-2")] = "safe-2"
        result = resolve_battle_tournament(participants, choices)
        self.assertTrue(result["complete"])
        self.assertEqual(result["winner"]["release_group_mbid"], "safe-2")
        self.assertEqual(result["total_matches"], 3)

    def test_eight_albums_need_at_most_seven_choices(self):
        candidates = [
            battle_candidate(f"safe-{index}", "Safe", index, .9 - index * .01, 2)
            for index in range(1, 5)
        ] + [
            battle_candidate(
                f"explore-{index}", "Explore", index, .8 - index * .01, 1
            )
            for index in range(1, 5)
        ]
        participants = build_battle_participants(candidates, "safe_vs_explore")
        choices = {}

        for _ in range(7):
            state = resolve_battle_tournament(participants, choices)
            if state["complete"]:
                break
            left_id = state["left"]["release_group_mbid"]
            right_id = state["right"]["release_group_mbid"]
            choices[tuple(sorted((left_id, right_id)))] = left_id

        result = resolve_battle_tournament(participants, choices)
        self.assertTrue(result["complete"])
        self.assertEqual(result["completed_matches"], 7)
        self.assertEqual(result["total_matches"], 7)


if __name__ == "__main__":
    unittest.main()
