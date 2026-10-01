import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingest import (
    extract_musicbrainz_tags,
    fetch_album,
    fetch_reviews,
    load_seeds,
    open_database,
    summarize_report,
    write_album,
)


class ManifestInputTests(unittest.TestCase):
    def test_loads_only_accepted_manifest_albums(self):
        manifest = {
            "summary": {"album_statuses": {"accepted": 1}},
            "albums": [
                {
                    "requested_artist": "Björk",
                    "requested_title": "Homogenic",
                    "release_group_mbid": "accepted-id",
                    "status": "accepted",
                },
                {
                    "requested_artist": "Unknown",
                    "requested_title": "Missing",
                    "status": "unmatched",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(
                load_seeds(path),
                [
                    {
                        "artist": "Björk",
                        "album": "Homogenic",
                        "release_group_mbid": "accepted-id",
                    }
                ],
            )

    def test_duplicate_mbids_are_rejected(self):
        rows = [
            {"artist": "A", "album": "One", "release_group_mbid": "same"},
            {"artist": "B", "album": "Two", "release_group_mbid": "same"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seeds.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_seeds(path)


class CoverageSummaryTests(unittest.TestCase):
    def test_counts_coverage_and_errors(self):
        report = {
            "albums": [
                {
                    "musicbrainz": {"status": "success"},
                    "cover_art_archive": {"status": "found"},
                    "lastfm": {"status": "success", "count": 4},
                    "critiquebrainz": {"status": "success", "count": 0},
                    "database_write": {"status": "written"},
                },
                {
                    "musicbrainz": {"status": "success"},
                    "cover_art_archive": {"status": "missing"},
                    "lastfm": {"status": "error"},
                    "critiquebrainz": {"status": "success", "count": 2},
                    "database_write": {"status": "written"},
                },
            ]
        }
        summary = summarize_report(report)
        self.assertEqual(summary["total_requested"], 2)
        self.assertEqual(summary["cover_art_found"], 1)
        self.assertEqual(summary["lastfm_with_tags"], 1)
        self.assertEqual(summary["critiquebrainz_with_reviews"], 1)
        self.assertEqual(summary["albums_with_any_error"], 1)


class MusicBrainzTagTests(unittest.TestCase):
    def test_tags_and_genres_are_normalized_deduplicated_and_ranked(self):
        tags = extract_musicbrainz_tags(
            [
                {"name": "trip hop", "count": 2},
                {"name": "Dream Pop", "count": 7},
                {"name": "   ", "count": 9},
            ],
            [
                {"name": "trip-hop", "count": 5},
                {"name": "ethereal"},
            ],
        )

        self.assertEqual(
            [(tag["normalized_tag"], tag["count"], tag["tag_rank"]) for tag in tags],
            [("dream pop", 7, 1), ("trip-hop", 5, 2), ("ethereal", None, 3)],
        )

    def test_missing_lastfm_key_skips_only_lastfm(self):
        seed = {
            "artist": "Example Artist",
            "album": "Example Album",
            "release_group_mbid": "example-mbid",
        }
        with (
            patch("ingest.fetch_musicbrainz", return_value={"status": "success"}),
            patch("ingest.fetch_cover", return_value={"status": "missing"}),
            patch("ingest.fetch_reviews", return_value={"status": "success"}),
            patch("ingest.fetch_lastfm") as lastfm_fetch,
        ):
            result = fetch_album(seed, None)

        self.assertEqual(result["lastfm"]["status"], "skipped")
        lastfm_fetch.assert_not_called()

    def test_writes_musicbrainz_tags_without_removing_lastfm_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "taste.db"
            connection = open_database(database_path)
            with connection:
                connection.execute(
                    "INSERT INTO albums VALUES (?, ?, ?, ?)",
                    ("album-1", "Example", 2020, None),
                )
                connection.execute(
                    "INSERT INTO album_tags VALUES (?, ?, ?, ?, ?)",
                    ("album-1", "lastfm-only", "lastfm-only", 1, "lastfm"),
                )
            result = {
                "release_group_mbid": "album-1",
                "musicbrainz": {
                    "status": "success",
                    "title": "Example",
                    "release_year": 2020,
                    "artists": [{
                        "artist_mbid": "artist-1",
                        "name": "Example Artist",
                        "credit_order": 1,
                    }],
                    "tags": [{
                        "raw_tag": "dream pop",
                        "normalized_tag": "dream pop",
                        "tag_rank": 1,
                    }],
                },
                "cover_art_archive": {"status": "missing", "url": None},
                "lastfm": {"status": "skipped"},
                "critiquebrainz": {"status": "success", "reviews": []},
            }

            write_album(connection, result)

            rows = connection.execute(
                "SELECT source, normalized_tag FROM album_tags ORDER BY source"
            ).fetchall()
            self.assertEqual(
                rows,
                [("lastfm", "lastfm-only"), ("musicbrainz", "dream pop")],
            )
            connection.close()


class ReviewProvenanceTests(unittest.TestCase):
    def test_fetch_reviews_keeps_author_and_license_link(self):
        listing = {
            "reviews": [
                {
                    "id": "review-1",
                    "language": "en",
                    "text": "A review with enough text for this fixture.",
                    "user": {"display_name": "Review Author"},
                    "license": {
                        "id": "CC BY-SA 3.0",
                        "info_url": "https://creativecommons.org/licenses/by-sa/3.0/",
                    },
                }
            ]
        }
        details = {
            "reviews": {
                "review-1": {
                    "id": "review-1",
                    "language": "en",
                    "text": "A review with enough text for this fixture.",
                    "user": {"display_name": "Review Author"},
                    "license": {
                        "id": "CC BY-SA 3.0",
                        "info_url": "https://creativecommons.org/licenses/by-sa/3.0/",
                    },
                }
            }
        }
        with patch("ingest.get_json", side_effect=[listing, details]):
            result = fetch_reviews("album-mbid")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["reviews"][0]["reviewer_name"], "Review Author")
        self.assertEqual(
            result["reviews"][0]["license_url"],
            "https://creativecommons.org/licenses/by-sa/3.0/",
        )


if __name__ == "__main__":
    unittest.main()
