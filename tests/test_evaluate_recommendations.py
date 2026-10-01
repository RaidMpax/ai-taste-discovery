import unittest

import numpy as np

from evaluate_recommendations import evaluate_recommendation_variants
from semantic_search import MODEL_NAME


class OfflineEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {
                "release_group_mbid": "seed-a",
                "title": "Seed A",
                "release_year": 2000,
                "artists": ["Artist A"],
                "tags": ["rock", "indie"],
            },
            {
                "release_group_mbid": "seed-b",
                "title": "Seed B",
                "release_year": 2001,
                "artists": ["Artist B"],
                "tags": ["rock", "electronic"],
            },
            {
                "release_group_mbid": "safe",
                "title": "Safe Album",
                "release_year": 2002,
                "artists": ["Safe Artist"],
                "tags": ["rock", "indie", "electronic"],
            },
            {
                "release_group_mbid": "explore",
                "title": "Explore Album",
                "release_year": 2003,
                "artists": ["Explore Artist"],
                "tags": ["rock", "synth pop", "art pop"],
            },
            {
                "release_group_mbid": "wildcard",
                "title": "Wildcard Album",
                "release_year": 2004,
                "artists": ["Wildcard Artist"],
                "tags": ["rock"],
            },
            {
                "release_group_mbid": "unassigned",
                "title": "Unassigned Album",
                "release_year": 2005,
                "artists": ["Unassigned Artist"],
                "tags": ["noise"],
            },
        ]
        self.vectors = np.asarray(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [0.7071, 0.7071],
                [0.6, 0.8],
                [1.0, 0.0],
                [-0.7071, 0.7071],
            ],
            dtype=np.float32,
        )

    def test_compares_three_methods_and_reports_tier_signals(self):
        report = evaluate_recommendation_variants(
            self.documents, self.vectors, ["Seed A", "Seed B"], per_tier=1
        )

        self.assertEqual(report["catalogue_size"], 6)
        self.assertEqual(report["embedding_model"], MODEL_NAME)
        self.assertEqual(
            set(report["methods"]),
            {"embedding_only", "embedding_plus_tags", "full_ranking"},
        )
        self.assertEqual(
            [
                item["tier"]
                for item in report["methods"]["full_ranking"]["items"]
            ],
            ["Safe", "Explore", "Wildcard"],
        )
        self.assertTrue(report["tier_separation"]["safe_ge_explore_ge_wildcard"])
        self.assertFalse(report["quality_labels_available"])
        for method in report["methods"].values():
            self.assertNotIn(
                "seed-a",
                {item["release_group_mbid"] for item in method["items"]},
            )

    def test_rejects_mismatched_documents_and_vectors(self):
        with self.assertRaisesRegex(ValueError, "counts must match"):
            evaluate_recommendation_variants(
                self.documents, self.vectors[:-1], ["Seed A"], per_tier=2
            )


if __name__ == "__main__":
    unittest.main()
