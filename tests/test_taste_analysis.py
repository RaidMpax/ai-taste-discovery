import unittest
from unittest.mock import patch

import numpy as np

from rag import (
    _resolve_gemini_api_key,
    build_taste_analysis_context,
    validate_generated_result,
)


class FixedEmbeddingModel:
    def embed(self, texts):
        return iter([np.asarray([1.0, 0.0], dtype=np.float32) for _ in texts])


def make_profile():
    return {
        "seed_albums": [
            {
                "release_group_mbid": "seed-a",
                "title": "Shared Title",
                "artists": ["Artist A"],
                "release_year": 2000,
                "tags": ["dream pop", "indie"],
            },
            {
                "release_group_mbid": "seed-b",
                "title": "Other Album",
                "artists": ["Artist B"],
                "release_year": 2020,
                "tags": ["dream pop", "electronic"],
            },
        ],
        "top_tags": [("dream pop", 2), ("electronic", 1)],
        "shared_tags": ["dream pop"],
        "distinctive_tags": ["electronic", "indie"],
        "release_year_range": [2000, 2020],
        "aggregation_method": "mean_of_l2_normalized_seed_vectors_then_l2_normalize",
    }


class TasteAnalysisContextTests(unittest.TestCase):
    def test_review_retrieval_is_scoped_by_mbid_not_ambiguous_title(self):
        chunks = [
            {
                "review_id": "review-correct",
                "release_group_mbid": "seed-a",
                "album_title": "Shared Title",
                "source": "CritiqueBrainz",
                "source_url": "https://example.test/correct",
                "license": "CC BY-SA",
                "chunk_index": 1,
                "text": "Dream pop textures and layered vocals.",
            },
            {
                "review_id": "review-wrong-album",
                "release_group_mbid": "different-mbid",
                "album_title": "Shared Title",
                "source": "CritiqueBrainz",
                "source_url": "https://example.test/wrong",
                "license": "CC BY-SA",
                "chunk_index": 1,
                "text": "Unrelated review with a duplicate album title.",
            },
        ]
        vectors = np.asarray([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)

        result = build_taste_analysis_context(
            make_profile(), chunks, vectors, FixedEmbeddingModel()
        )

        self.assertEqual([source["review_id"] for source in result["sources"]], ["review-correct"])
        self.assertIn("review-correct#1", result["context"])
        self.assertNotIn("review-wrong-album", result["context"])

    def test_profile_context_still_builds_when_no_reviews_exist(self):
        result = build_taste_analysis_context(
            make_profile(), [], np.asarray([], dtype=np.float32), FixedEmbeddingModel()
        )

        self.assertEqual(result["sources"], [])
        self.assertIn("Dominant tags", result["context"])
        self.assertIn("None available.", result["context"])

    def test_citation_validation_rejects_unknown_source_ids(self):
        result = {
            "overall_taste": "A grounded summary.",
            "core_tendencies": [],
            "interesting_contrasts": [],
            "exploration_directions": [],
            "evidence": [{"claim": "A review says this.", "source_ids": ["invented#1"]}],
            "limitations": "Only two seed albums.",
        }

        with self.assertRaisesRegex(ValueError, "unknown source IDs"):
            validate_generated_result(result, {"known#1"})


class GeminiKeyConfigurationTests(unittest.TestCase):
    def test_explicit_streamlit_secret_takes_precedence(self):
        with patch("rag.load_dotenv"):
            self.assertEqual(_resolve_gemini_api_key("  hosted-key  "), "hosted-key")

    def test_environment_key_is_supported(self):
        with patch("rag.load_dotenv"), patch.dict(
            "os.environ", {"GEMINI_API_KEY": "environment-key"}
        ):
            self.assertEqual(_resolve_gemini_api_key(), "environment-key")

    def test_missing_key_explains_supported_locations(self):
        with patch("rag.load_dotenv"), patch.dict(
            "os.environ", {"GEMINI_API_KEY": ""}
        ):
            with self.assertRaisesRegex(RuntimeError, "Streamlit secrets"):
                _resolve_gemini_api_key()


if __name__ == "__main__":
    unittest.main()
