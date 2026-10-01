import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from behavior import initialize_database
from prepare_deployment_catalog import build_deployment_catalog


class DeploymentCatalogTests(unittest.TestCase):
    def test_exports_only_accepted_catalog_rows_and_omits_reviews_and_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.db"
            output_path = root / "deployment" / "catalog.db"
            manifest_path = root / "manifest.json"
            initialize_database(source_path)

            source = sqlite3.connect(source_path)
            source.execute("PRAGMA foreign_keys = ON")
            source.executemany(
                "INSERT INTO albums VALUES (?, ?, ?, ?)",
                [
                    ("accepted-album", "Accepted Album", 2020, "https://cover/a"),
                    ("other-album", "Other Album", 2021, None),
                ],
            )
            source.executemany(
                "INSERT INTO artists VALUES (?, ?)",
                [("accepted-artist", "Artist A"), ("other-artist", "Artist B")],
            )
            source.executemany(
                "INSERT INTO album_artists VALUES (?, ?, ?)",
                [
                    ("accepted-album", "accepted-artist", 1),
                    ("other-album", "other-artist", 1),
                ],
            )
            source.executemany(
                "INSERT INTO album_tags VALUES (?, ?, ?, ?, ?)",
                [
                    ("accepted-album", "dream pop", "dream pop", 1, "lastfm"),
                    ("accepted-album", "art pop", "art pop", 1, "musicbrainz"),
                    ("other-album", "rock", "rock", 1, "lastfm"),
                ],
            )
            source.execute(
                "INSERT INTO reviews (review_id, release_group_mbid, language, "
                "license, review_text) VALUES (?, ?, ?, ?, ?)",
                ("review-1", "accepted-album", "en", "CC BY-SA 3.0", "Review."),
            )
            source.execute(
                "INSERT INTO sessions (session_id, created_at) VALUES (?, ?)",
                ("session-1", "2026-09-29T00:00:00+00:00"),
            )
            source.commit()
            source.close()

            manifest_path.write_text(
                json.dumps(
                    {
                        "albums": [
                            {
                                "status": "accepted",
                                "release_group_mbid": "accepted-album",
                            },
                            {
                                "status": "unmatched",
                                "release_group_mbid": None,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = build_deployment_catalog(
                source_path, manifest_path, output_path
            )

            output = sqlite3.connect(output_path)
            self.assertEqual(
                output.execute(
                    "SELECT release_group_mbid FROM albums"
                ).fetchall(),
                [("accepted-album",)],
            )
            self.assertEqual(
                output.execute("SELECT name FROM artists").fetchall(),
                [("Artist A",)],
            )
            self.assertEqual(
                output.execute("SELECT raw_tag FROM album_tags").fetchall(),
                [("art pop",)],
            )
            self.assertEqual(
                output.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 0
            )
            self.assertEqual(
                output.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0
            )
            self.assertEqual(
                output.execute("PRAGMA foreign_key_check").fetchall(), []
            )
            output.close()

            self.assertEqual(result["manifest_album_count"], 1)
            self.assertEqual(result["counts"]["albums"], 1)
            self.assertEqual(result["counts"]["album_tags"], 1)
            self.assertEqual(result["tag_source_filter"], "musicbrainz")
            self.assertEqual(result["non_musicbrainz_tag_rows_omitted"], 1)
            self.assertTrue(result["reviews_omitted_pending_attribution_and_reuse_review"])
            self.assertTrue(result["behavior_rows_omitted"])

    def test_refuses_to_overwrite_source_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.db"
            manifest_path = root / "manifest.json"
            initialize_database(source_path)
            manifest_path.write_text(
                json.dumps(
                    {"albums": [{"status": "accepted", "release_group_mbid": "a"}]}
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must not overwrite"):
                build_deployment_catalog(source_path, manifest_path, source_path)


if __name__ == "__main__":
    unittest.main()
