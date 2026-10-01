import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from semantic_search import build_taste_profile, load_album_documents


class AlbumDocumentScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database_path = self.root / "taste.db"
        self.manifest_path = self.root / "manifest.json"

        connection = sqlite3.connect(self.database_path)
        connection.executescript(
            """
            CREATE TABLE albums (
                release_group_mbid TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                release_year INTEGER,
                cover_url TEXT
            );
            CREATE TABLE artists (
                artist_mbid TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE album_artists (
                release_group_mbid TEXT NOT NULL,
                artist_mbid TEXT NOT NULL,
                credit_order INTEGER NOT NULL
            );
            CREATE TABLE album_tags (
                release_group_mbid TEXT NOT NULL,
                normalized_tag TEXT NOT NULL,
                tag_rank INTEGER NOT NULL,
                source TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO albums VALUES (?, ?, ?, ?)",
            [
                ("selected-mbid", "Selected Album", 2020, "cover.jpg"),
                ("legacy-mbid", "Legacy Album", 1990, None),
            ],
        )
        connection.executemany(
            "INSERT INTO artists VALUES (?, ?)",
            [("selected-artist", "Selected Artist"), ("legacy-artist", "Legacy Artist")],
        )
        connection.executemany(
            "INSERT INTO album_artists VALUES (?, ?, ?)",
            [
                ("selected-mbid", "selected-artist", 1),
                ("legacy-mbid", "legacy-artist", 1),
            ],
        )
        connection.executemany(
            "INSERT INTO album_tags VALUES (?, ?, ?, ?)",
            [
                ("selected-mbid", "dream pop", 1, "lastfm"),
                ("legacy-mbid", "jazz", 1, "lastfm"),
                ("selected-mbid", "synthpop", 1, "musicbrainz"),
                ("legacy-mbid", "noise", 1, "musicbrainz"),
            ],
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_only_accepted_manifest_albums_become_documents(self):
        self.manifest_path.write_text(
            json.dumps(
                {
                    "albums": [
                        {"release_group_mbid": "selected-mbid", "status": "accepted"},
                        {"release_group_mbid": "legacy-mbid", "status": "rejected"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        documents = load_album_documents(self.database_path, self.manifest_path)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["release_group_mbid"], "selected-mbid")
        self.assertEqual(documents[0]["artists"], ["Selected Artist"])
        self.assertEqual(documents[0]["tags"], ["synthpop"])

    def test_lastfm_remains_available_as_an_explicit_non_default_source(self):
        self.manifest_path.write_text(
            json.dumps(
                {"albums": [{"release_group_mbid": "selected-mbid", "status": "accepted"}]}
            ),
            encoding="utf-8",
        )

        documents = load_album_documents(
            self.database_path, self.manifest_path, tag_source="lastfm"
        )

        self.assertEqual(documents[0]["tags"], ["dream pop"])

    def test_missing_accepted_album_fails_instead_of_silently_shrinking_catalogue(self):
        self.manifest_path.write_text(
            json.dumps(
                {
                    "albums": [
                        {"release_group_mbid": "selected-mbid", "status": "accepted"},
                        {"release_group_mbid": "missing-mbid", "status": "accepted"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "missing from the database"):
            load_album_documents(self.database_path, self.manifest_path)


class TasteProfileTests(unittest.TestCase):
    def test_structured_signals_and_normalized_mean(self):
        documents = [
            {
                "release_group_mbid": "a",
                "title": "A",
                "artists": ["Artist A"],
                "release_year": 2000,
                "tags": ["dream pop", "indie", "indie"],
            },
            {
                "release_group_mbid": "b",
                "title": "B",
                "artists": ["Artist B"],
                "release_year": 2020,
                "tags": ["dream pop", "electronic"],
            },
        ]
        vectors = np.asarray([[3.0, 0.0], [0.0, 2.0]], dtype=np.float32)

        profile = build_taste_profile(documents, vectors, ["A", "B"])

        np.testing.assert_allclose(profile["vector"], [2**-0.5, 2**-0.5])
        self.assertEqual(profile["top_tags"], [("dream pop", 2), ("electronic", 1), ("indie", 1)])
        self.assertEqual(profile["shared_tags"], ["dream pop"])
        self.assertEqual(profile["distinctive_tags"], ["electronic", "indie"])
        self.assertEqual(profile["release_year_range"], [2000, 2020])
        self.assertEqual([album["release_group_mbid"] for album in profile["seed_albums"]], ["a", "b"])

    def test_one_seed_with_missing_year_has_no_shared_tags_or_year_range(self):
        documents = [{
            "release_group_mbid": "a",
            "title": "A",
            "artists": ["Artist A"],
            "release_year": None,
            "tags": ["indie"],
        }]
        vectors = np.asarray([[1.0, 0.0]], dtype=np.float32)

        profile = build_taste_profile(documents, vectors, ["A"])

        self.assertEqual(profile["shared_tags"], [])
        self.assertEqual(profile["distinctive_tags"], ["indie"])
        self.assertIsNone(profile["release_year_range"])


if __name__ == "__main__":
    unittest.main()
