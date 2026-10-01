import sqlite3
import tempfile
import unittest
from pathlib import Path

from behavior import (
    create_session,
    initialize_database,
    load_battle_choices,
    load_seen_battle_pairs,
    load_session_battle_pairs,
    normalize_behavior_storage_mode,
    record_feedback,
    record_battle_choice,
    record_recommendation_impressions,
    record_taste_profile_event,
)


class BehaviorDataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "taste.db"
        initialize_database(self.database_path)
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "INSERT INTO albums (release_group_mbid, title) VALUES (?, ?)",
            ("album-a", "Album A"),
        )
        connection.execute(
            "INSERT INTO albums (release_group_mbid, title) VALUES (?, ?)",
            ("album-b", "Album B"),
        )
        connection.execute(
            "INSERT INTO albums (release_group_mbid, title) VALUES (?, ?)",
            ("album-c", "Album C"),
        )
        connection.commit()
        connection.close()
        create_session(self.database_path, "anonymous-session")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schema_initialization_is_repeatable(self):
        initialize_database(self.database_path)
        connection = sqlite3.connect(self.database_path)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        connection.close()
        self.assertTrue(
            {
                "sessions",
                "taste_profile_events",
                "recommendation_impressions",
                "recommendation_feedback",
                "taste_profile_event_albums",
                "taste_battles",
            }.issubset(tables)
        )

    def test_behavior_storage_mode_accepts_supported_modes(self):
        self.assertEqual(normalize_behavior_storage_mode(None), "persistent")
        self.assertEqual(normalize_behavior_storage_mode(" PERSISTENT "), "persistent")
        self.assertEqual(normalize_behavior_storage_mode("session"), "session")
        self.assertEqual(normalize_behavior_storage_mode(" Supabase "), "supabase")
        with self.assertRaisesRegex(
            ValueError, "must be 'persistent', 'session', or 'supabase'"
        ):
            normalize_behavior_storage_mode("cloud")

    def test_session_battle_history_tracks_pairs_without_a_database(self):
        choices = [
            {
                "album_a_mbid": "album-a",
                "album_b_mbid": "album-b",
                "chosen_album_mbid": "album-a",
            },
            {
                "album_a_mbid": "album-c",
                "album_b_mbid": "album-b",
                "chosen_album_mbid": "album-b",
            },
        ]
        seen_pairs, battle_count = load_session_battle_pairs(choices)
        self.assertEqual(
            seen_pairs, {("album-a", "album-b"), ("album-b", "album-c")}
        )
        self.assertEqual(battle_count, 2)

    def test_battle_choice_is_saved_and_seen_pair_is_order_independent(self):
        profile_event_id = record_taste_profile_event(
            self.database_path, "anonymous-session", ["album-a"]
        )
        record_battle_choice(
            self.database_path,
            "anonymous-session",
            profile_event_id,
            "album-b",
            "album-c",
            "album-c",
            "safe_vs_explore",
        )

        seen_pairs, battle_count = load_seen_battle_pairs(
            self.database_path, profile_event_id
        )
        choices = load_battle_choices(
            self.database_path, profile_event_id, "safe_vs_explore"
        )

        self.assertEqual(seen_pairs, {("album-b", "album-c")})
        self.assertEqual(battle_count, 1)
        self.assertEqual(choices, {("album-b", "album-c"): "album-c"})

    def test_battle_rejects_invalid_choice_and_strategy(self):
        profile_event_id = record_taste_profile_event(
            self.database_path, "anonymous-session", ["album-a"]
        )
        with self.assertRaisesRegex(ValueError, "must be A or B"):
            record_battle_choice(
                self.database_path,
                "anonymous-session",
                profile_event_id,
                "album-b",
                "album-c",
                "album-a",
                "safe_vs_explore",
            )
        with self.assertRaisesRegex(ValueError, "Unknown Taste Battle strategy"):
            record_battle_choice(
                self.database_path,
                "anonymous-session",
                profile_event_id,
                "album-b",
                "album-c",
                "album-b",
                "random",
            )

    def test_profile_and_impressions_preserve_seed_and_score_data(self):
        profile_event_id = record_taste_profile_event(
            self.database_path, "anonymous-session", ["album-a"]
        )
        record_recommendation_impressions(
            self.database_path,
            "anonymous-session",
            profile_event_id,
            "Explore",
            [
                {
                    "release_group_mbid": "album-b",
                    "profile_similarity": 0.72,
                    "bridge_similarity": 0.81,
                    "explore_score": 0.77,
                    "novelty_ratio": 0.5,
                }
            ],
        )

        connection = sqlite3.connect(self.database_path)
        seeds = connection.execute(
            "SELECT release_group_mbid FROM taste_profile_event_albums "
            "WHERE profile_event_id = ? ORDER BY seed_order",
            (profile_event_id,),
        ).fetchall()
        impression = connection.execute(
            "SELECT session_id, release_group_mbid, tier, rank, explore_score "
            "FROM recommendation_impressions"
        ).fetchone()
        connection.close()
        self.assertEqual(seeds, [("album-a",)])
        self.assertEqual(impression[:4], ("anonymous-session", "album-b", "Explore", 1))
        self.assertEqual(impression[4], 0.77)

    def test_feedback_can_be_changed_without_creating_duplicate_rows(self):
        record_feedback(
            self.database_path, "anonymous-session", "album-b", "Explore", "like"
        )
        record_feedback(
            self.database_path, "anonymous-session", "album-b", "Explore", "dislike"
        )

        connection = sqlite3.connect(self.database_path)
        rows = connection.execute(
            "SELECT feedback FROM recommendation_feedback WHERE session_id = ?",
            ("anonymous-session",),
        ).fetchall()
        connection.close()
        self.assertEqual(rows, [("dislike",)])

    def test_invalid_feedback_and_seed_count_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "1 to 10"):
            record_taste_profile_event(self.database_path, "anonymous-session", [])
        with self.assertRaisesRegex(ValueError, "1 to 10"):
            record_taste_profile_event(
                self.database_path,
                "anonymous-session",
                [f"missing-{index}" for index in range(11)],
            )
        with self.assertRaisesRegex(ValueError, "like' or 'dislike"):
            record_feedback(
                self.database_path, "anonymous-session", "album-b", "Explore", "maybe"
            )

    def test_profile_event_accepts_ten_seed_albums(self):
        extra_mbids = [f"album-{index}" for index in range(7)]
        connection = sqlite3.connect(self.database_path)
        connection.executemany(
            "INSERT INTO albums (release_group_mbid, title) VALUES (?, ?)",
            [(mbid, mbid) for mbid in extra_mbids],
        )
        connection.commit()
        connection.close()

        profile_event_id = record_taste_profile_event(
            self.database_path,
            "anonymous-session",
            ["album-a", "album-b", "album-c", *extra_mbids],
        )

        connection = sqlite3.connect(self.database_path)
        seed_count = connection.execute(
            "SELECT COUNT(*) FROM taste_profile_event_albums WHERE profile_event_id = ?",
            (profile_event_id,),
        ).fetchone()[0]
        connection.close()
        self.assertEqual(seed_count, 10)


class ReviewSchemaUpgradeTests(unittest.TestCase):
    def test_adds_attribution_columns_without_replacing_existing_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(database_path)
            connection.executescript(
                """
                CREATE TABLE albums (
                    release_group_mbid TEXT PRIMARY KEY NOT NULL,
                    title TEXT NOT NULL,
                    release_year INTEGER,
                    cover_url TEXT
                );
                CREATE TABLE reviews (
                    review_id TEXT PRIMARY KEY NOT NULL,
                    release_group_mbid TEXT NOT NULL,
                    language TEXT NOT NULL,
                    source TEXT,
                    source_url TEXT,
                    license TEXT NOT NULL,
                    review_text TEXT NOT NULL
                );
                INSERT INTO albums VALUES ('album-1', 'Album', 2020, NULL);
                INSERT INTO reviews VALUES (
                    'review-1', 'album-1', 'en', 'CritiqueBrainz', NULL,
                    'CC BY-SA 3.0', 'Existing review text.'
                );
                """
            )
            connection.close()

            initialize_database(database_path)

            connection = sqlite3.connect(database_path)
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(reviews)")
            }
            saved_review = connection.execute(
                "SELECT review_text, reviewer_name, license_url FROM reviews"
            ).fetchone()
            connection.close()

        self.assertIn("reviewer_name", columns)
        self.assertIn("license_url", columns)
        self.assertEqual(saved_review, ("Existing review text.", None, None))


if __name__ == "__main__":
    unittest.main()
