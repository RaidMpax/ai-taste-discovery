import unittest

from discover_catalog import (
    classify_match,
    escape_lucene_phrase,
    normalize_title,
    summarize,
)


ARTIST_MBID = "a74b1b7f-71a5-4011-9441-d0b5e4122711"


def release_group(
    *,
    title="OK Computer",
    score=100,
    artist_mbid=ARTIST_MBID,
    primary_type="Album",
    secondary_types=None,
):
    return {
        "id": "b1392450-e666-3926-a536-22c65f834433",
        "title": title,
        "score": score,
        "primary-type": primary_type,
        "secondary-types": secondary_types or [],
        "first-release-date": "1997-05-21",
        "artist-credit": [
            {"name": "Radiohead", "artist": {"id": artist_mbid}}
        ],
    }


class CatalogDiscoveryTests(unittest.TestCase):
    def test_title_normalization_ignores_case_spacing_and_punctuation(self):
        self.assertEqual(normalize_title("LONG SEASON"), normalize_title("Long-Season"))

    def test_lucene_special_characters_are_escaped(self):
        self.assertEqual(escape_lucene_phrase("AC/DC: Live"), "AC\\/DC\\: Live")

    def test_high_confidence_album_is_accepted(self):
        result = classify_match("OK Computer", ARTIST_MBID, [release_group()])
        self.assertEqual(result["status"], "accepted")

    def test_wrong_artist_requires_review_even_with_score_100(self):
        result = classify_match(
            "OK Computer",
            ARTIST_MBID,
            [release_group(artist_mbid="different-artist")],
        )
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("seed artist MBID is absent from artist credit", result["match_reasons"])

    def test_later_exact_result_can_beat_an_ambiguous_first_result(self):
        ambiguous = release_group(title="OK Computer Deluxe")
        exact = release_group(score=98)
        result = classify_match(
            "OK Computer", ARTIST_MBID, [ambiguous, exact]
        )
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["score"], 98)

    def test_live_album_is_not_auto_accepted(self):
        result = classify_match(
            "OK Computer",
            ARTIST_MBID,
            [release_group(secondary_types=["Live"])],
        )
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("blocked secondary type: live", result["match_reasons"])

    def test_no_result_is_unmatched(self):
        result = classify_match("Unknown", ARTIST_MBID, [])
        self.assertEqual(result["status"], "unmatched")

    def test_summary_counts_unique_release_groups(self):
        candidates = [
            {"status": "accepted", "release_group_mbid": "same-id"},
            {"status": "accepted", "release_group_mbid": "same-id"},
            {"status": "unmatched"},
        ]
        result = summarize(candidates, [ARTIST_MBID])
        self.assertEqual(result["candidate_count"], 3)
        self.assertEqual(result["unique_release_groups"], 1)
        self.assertEqual(result["duplicate_release_group_candidates"], 1)


if __name__ == "__main__":
    unittest.main()
