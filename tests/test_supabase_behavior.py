import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from supabase_behavior import SupabaseBehaviorError, SupabaseBehaviorStore


class FakeResponse:
    def __init__(self, body=b""):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, _exception_type, _exception, _traceback):
        return False

    def read(self):
        return self.body


class SupabaseBehaviorStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = SupabaseBehaviorStore(
            "https://example.supabase.co", "sb_secret_test_value"
        )

    def test_requires_https_and_a_secret_key(self):
        with self.assertRaisesRegex(ValueError, "must use HTTPS"):
            SupabaseBehaviorStore("http://example.supabase.co", "key")
        with self.assertRaisesRegex(ValueError, "SUPABASE_SECRET_KEY is missing"):
            SupabaseBehaviorStore("https://example.supabase.co", " ")

    @patch("supabase_behavior.urlopen", return_value=FakeResponse())
    def test_session_write_uses_upsert_and_server_side_key(self, mock_urlopen):
        session_id = str(uuid4())

        self.store.create_session(session_id, "consent-test")

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            "https://example.supabase.co/rest/v1/sessions?on_conflict=session_id",
        )
        self.assertEqual(request.get_header("Apikey"), "sb_secret_test_value")
        self.assertEqual(
            request.get_header("Prefer"),
            "resolution=ignore-duplicates,return=minimal",
        )
        self.assertEqual(
            json.loads(request.data),
            {
                "session_id": session_id,
                "consent_version": "consent-test",
                "app_version": "v2-beta",
            },
        )

    @patch("supabase_behavior.urlopen")
    def test_http_error_does_not_expose_response_or_secret(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://example.supabase.co/rest/v1/sessions",
            401,
            "invalid key sb_secret_test_value",
            None,
            BytesIO(b"private database response"),
        )

        with self.assertRaises(SupabaseBehaviorError) as raised:
            self.store.create_session(str(uuid4()))

        message = str(raised.exception)
        self.assertIn("HTTP 401", message)
        self.assertNotIn("sb_secret_test_value", message)
        self.assertNotIn("private database response", message)

    @patch("supabase_behavior.urlopen", return_value=FakeResponse(
        json.dumps(
            [
                {
                    "album_a_mbid": "album-b",
                    "album_b_mbid": "album-a",
                    "chosen_album_mbid": "album-a",
                }
            ]
        ).encode("utf-8")
    ))
    def test_battle_choices_are_normalized_as_unordered_pairs(self, mock_urlopen):
        profile_event_id = str(uuid4())

        choices = self.store.load_battle_choices(
            profile_event_id, "safe_vs_explore"
        )

        self.assertEqual(choices, {("album-a", "album-b"): "album-a"})
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("/taste_battle_events?", request.full_url)
        self.assertNotIn("Authorization", request.headers)


if __name__ == "__main__":
    unittest.main()
