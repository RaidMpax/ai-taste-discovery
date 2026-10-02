import os
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import (
    ensure_application_database,
    format_gemini_error,
    get_application_database_path,
    queue_taste_analysis,
)


class ApplicationDatabaseConfigTests(unittest.TestCase):
    def test_relative_environment_path_resolves_from_project_root(self):
        expected = Path(__file__).resolve().parents[1] / "deployment" / "catalog.db"
        with (
            patch.dict(
                os.environ,
                {"AI_TASTE_DATABASE_PATH": "deployment/catalog.db"},
                clear=False,
            ),
            patch("app.load_dotenv"),
        ):
            self.assertEqual(get_application_database_path(), expected)

    def test_missing_catalogue_downloads_to_temp_file_and_checks_sha256(self):
        contents = b"verified catalogue fixture"
        expected_hash = hashlib.sha256(contents).hexdigest()
        settings = {
            "AI_TASTE_DATABASE_URL": "https://example.test/catalogue.db",
            "AI_TASTE_DATABASE_SHA256": expected_hash,
        }
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "catalogue.db"
            with (
                patch(
                    "app.get_app_setting",
                    side_effect=lambda key, default="": settings.get(key, default),
                ),
                patch("app.urlopen", return_value=io.BytesIO(contents)) as open_url,
            ):
                self.assertEqual(ensure_application_database(target), target)

            self.assertEqual(target.read_bytes(), contents)
            open_url.assert_called_once()
            self.assertEqual(list(Path(directory).glob("*.download")), [])

    def test_catalogue_with_wrong_checksum_is_not_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "catalogue.db"
            settings = {
                "AI_TASTE_DATABASE_URL": "https://example.test/catalogue.db",
                "AI_TASTE_DATABASE_SHA256": "0" * 64,
            }
            with (
                patch(
                    "app.get_app_setting",
                    side_effect=lambda key, default="": settings.get(key, default),
                ),
                patch("app.urlopen", return_value=io.BytesIO(b"not the catalogue")),
            ):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    ensure_application_database(target)

            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).glob("*.download")), [])

    def test_existing_local_catalogue_skips_download(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "catalogue.db"
            target.write_bytes(b"local catalogue")
            with patch("app.urlopen") as open_url:
                self.assertEqual(ensure_application_database(target), target)
            open_url.assert_not_called()

    def test_gemini_socket_permission_error_is_explained_without_blocking_profile(self):
        message = format_gemini_error(
            PermissionError("[WinError 10013] socket access was denied")
        )
        self.assertIn("WinError 10013", message)
        self.assertIn("结构化品味档案和推荐仍可使用", message)

    def test_missing_gemini_key_has_a_distinct_actionable_message(self):
        message = format_gemini_error(
            RuntimeError("GEMINI_API_KEY is not configured")
        )
        self.assertIn("GEMINI_API_KEY", message)
        self.assertIn("结构化品味档案和推荐仍可使用", message)

    def test_invalid_json_from_gemini_has_a_specific_safe_message(self):
        message = format_gemini_error(json.JSONDecodeError("invalid", "{", 1))
        self.assertIn("结构化内容无法解析", message)
        self.assertIn("结构化品味档案和推荐仍可使用", message)

    def test_unknown_citation_from_gemini_has_a_specific_safe_message(self):
        message = format_gemini_error(
            ValueError("Gemini returned unknown source IDs: invented#1")
        )
        self.assertIn("来源校验已拦截", message)

    def test_unsupported_consensus_language_has_a_specific_safe_message(self):
        message = format_gemini_error(
            ValueError("Gemini used unsupported consensus language: widely")
        )
        self.assertIn("概括性表述", message)

    def test_value_error_has_a_safe_validation_fallback(self):
        message = format_gemini_error(ValueError("unexpected analysis shape"))
        self.assertIn("未通过结构化或来源校验", message)

    def test_taste_analysis_is_queued_once_without_running_in_the_ui_thread(self):
        state = {}
        future = Mock()
        future.cancelled.return_value = False
        resources = {
            "review_chunks": [],
            "review_vectors": [],
            "review_model": object(),
        }

        with (
            patch("app.st.session_state", state),
            patch("app.get_taste_analysis_executor") as get_executor,
        ):
            executor = get_executor.return_value
            executor.submit.return_value = future
            queue_taste_analysis("seed-a", {}, resources, "test-key")
            queue_taste_analysis("seed-a", {}, resources, "test-key")

        self.assertIs(state["taste_analysis_future::seed-a"], future)
        executor.submit.assert_called_once()

    def test_relative_streamlit_secret_path_resolves_from_project_root(self):
        expected = Path(__file__).resolve().parents[1] / "deployment" / "catalog.db"
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("app.load_dotenv"),
            patch(
                "app.st.secrets",
                {"AI_TASTE_DATABASE_PATH": "deployment/catalog.db"},
            ),
        ):
            self.assertEqual(get_application_database_path(), expected)


if __name__ == "__main__":
    unittest.main()
