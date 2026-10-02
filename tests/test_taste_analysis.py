import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from rag import (
    _resolve_gemini_api_key,
    build_taste_analysis_context,
    generate_taste_analysis,
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
            "evidence": [{"claim": "A review says this.", "source_ids": ["invented#1"]}],
            "limitations": "Only two seed albums.",
        }

        with self.assertRaisesRegex(ValueError, "unknown source IDs"):
            validate_generated_result(result, {"known#1"})

    def test_taste_analysis_requires_empty_evidence_when_no_reviews_exist(self):
        output = {
            "overall_taste": "这组作品呈现出清晰的声音线索，但样本有限，结论只适用于所选专辑。",
            "evidence": [],
            "limitations": "没有可用的授权评论。",
        }
        create = Mock(
            return_value=SimpleNamespace(output_text=json.dumps(output))
        )
        client = SimpleNamespace(interactions=SimpleNamespace(create=create))
        context_result = {
            "context": "[LICENSED REVIEW EVIDENCE]\nNone available.",
            "sources": [],
        }

        with patch("rag._create_gemini_client", return_value=client):
            result = generate_taste_analysis(context_result, api_key="test-key")

        self.assertEqual(result["evidence"], [])
        prompt = create.call_args.kwargs["input"]
        self.assertIn("Return an empty evidence array", prompt)
        self.assertIn("不写标题、分点、编号", prompt)
        self.assertIn("不要把这组小样本推广成普遍规律", prompt)

    def test_consensus_language_is_rejected_without_relaxing_validation(self):
        result = {
            "overall_taste": "This album is widely regarded as influential.",
            "evidence": [],
            "limitations": "No licensed reviews were available.",
        }

        with self.assertRaisesRegex(ValueError, "unsupported consensus language"):
            validate_generated_result(result, set())

    def test_taste_analysis_repairs_one_rejected_draft(self):
        rejected = {
            "overall_taste": "This album is widely regarded as influential.",
            "evidence": [],
            "limitations": "No licensed reviews were available.",
        }
        accepted = {
            "overall_taste": "这些作品把电子质感和更柔和的流行旋律并置，形成克制而有层次的听感。",
            "evidence": [],
            "limitations": "没有可用的授权评论。",
        }
        create = Mock(
            side_effect=[
                SimpleNamespace(output_text=json.dumps(rejected)),
                SimpleNamespace(output_text=json.dumps(accepted)),
            ]
        )
        client = SimpleNamespace(interactions=SimpleNamespace(create=create))
        context_result = {
            "context": "[LICENSED REVIEW EVIDENCE]\nNone available.",
            "sources": [],
        }

        with patch("rag._create_gemini_client", return_value=client):
            result = generate_taste_analysis(context_result, api_key="test-key")

        self.assertEqual(result, accepted)
        self.assertEqual(create.call_count, 2)
        self.assertIn("previous JSON draft failed validation", create.call_args_list[1].kwargs["input"])


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
