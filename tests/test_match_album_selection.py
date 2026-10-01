import tempfile
import unittest
from pathlib import Path

from match_album_selection import (
    classify_album_match,
    classify_artist_match,
    parse_selection_files,
    refresh_manifest_selection,
)


ARTIST_MBID = "artist-id"


def artist(name="Radiohead", score=100, artist_mbid=ARTIST_MBID, aliases=None):
    return {
        "id": artist_mbid,
        "name": name,
        "sort-name": name,
        "score": score,
        "aliases": aliases or [],
    }


def release_group(
    title="OK Computer",
    year="1997-05-21",
    primary_type="Album",
    secondary_types=None,
    artist_mbid=ARTIST_MBID,
):
    return {
        "id": "release-group-id",
        "title": title,
        "first-release-date": year,
        "primary-type": primary_type,
        "secondary-types": secondary_types or [],
        "artist-credit": [
            {"name": "Radiohead", "artist": {"id": artist_mbid}}
        ],
    }


def album(**overrides):
    result = {
        "requested_artist": "Radiohead",
        "requested_title": "OK Computer",
        "requested_year": 1997,
        "requested_type": "album",
    }
    result.update(overrides)
    return result


class SelectionParserTests(unittest.TestCase):
    def test_reads_only_accepted_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ALBUM_SELECTION_BATCH_TEST.md"
            path.write_text(
                "\n".join(
                    [
                        "| Artist | Release | Year | Type | Eligibility | Decision | Inclusion role |",
                        "| --- | --- | ---: | --- | --- | --- | --- |",
                        "| Radiohead | OK Computer | 1997 | album | both | accept | Canon |",
                        "| Radiohead | Live | 2001 | album | none | exclude | Not eligible |",
                    ]
                ),
                encoding="utf-8",
            )
            rows = parse_selection_files(Path(directory))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["requested_title"], "OK Computer")

    def test_refresh_preserves_unchanged_results_and_resets_changed_row(self):
        unchanged = album(source_file="a.md", source_line=1, status="accepted")
        changed = album(
            source_file="a.md",
            source_line=2,
            requested_title="Old title",
            status="accepted",
        )
        for item in (unchanged, changed):
            item.setdefault("eligibility", "both")
            item.setdefault("inclusion_role", "test")
        manifest = {"albums": [unchanged, changed]}
        sources = [
            {key: value for key, value in unchanged.items() if key != "status"},
            {
                **{key: value for key, value in changed.items() if key != "status"},
                "requested_title": "New title",
            },
        ]
        for source in sources:
            source.setdefault("eligibility", "both")
            source.setdefault("inclusion_role", "test")
        refresh_manifest_selection(manifest, sources)
        self.assertEqual(manifest["albums"][0]["status"], "accepted")
        self.assertNotIn("status", manifest["albums"][1])
        self.assertEqual(manifest["albums"][1]["requested_title"], "New title")


class ArtistMatchingTests(unittest.TestCase):
    def test_unique_exact_artist_is_accepted(self):
        result = classify_artist_match("Radiohead", [artist()])
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["artist_mbid"], ARTIST_MBID)

    def test_clear_score_margin_is_accepted(self):
        result = classify_artist_match(
            "Adele", [artist("Adele", 100, "correct"), artist("Adele", 73, "other")]
        )
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["artist_mbid"], "correct")

    def test_alias_can_match(self):
        candidate = artist(name="i-dle", aliases=[{"name": "(G)I-DLE"}])
        result = classify_artist_match("(G)I-DLE", [candidate])
        self.assertEqual(result["status"], "accepted")

    def test_ambiguous_exact_artist_requires_review(self):
        result = classify_artist_match(
            "Phoenix", [artist("Phoenix", 100, "one"), artist("Phoenix", 95, "two")]
        )
        self.assertEqual(result["status"], "needs_review")


class AlbumMatchingTests(unittest.TestCase):
    def test_exact_compatible_album_is_accepted(self):
        result = classify_album_match(album(), ARTIST_MBID, [release_group()])
        self.assertEqual(result["status"], "accepted")

    def test_large_year_difference_requires_review(self):
        result = classify_album_match(
            album(), ARTIST_MBID, [release_group(year="2007-01-01")]
        )
        self.assertEqual(result["status"], "needs_review")

    def test_intentional_ep_is_accepted(self):
        result = classify_album_match(
            album(requested_title="Kindred", requested_year=2012, requested_type="EP"),
            ARTIST_MBID,
            [release_group(title="Kindred", year="2012", primary_type="EP")],
        )
        self.assertEqual(result["status"], "accepted")

    def test_intentional_mixtape_is_accepted(self):
        result = classify_album_match(
            album(requested_title="Mixtape", requested_type="mixtape"),
            ARTIST_MBID,
            [release_group(title="Mixtape", secondary_types=["Mixtape/Street"])],
        )
        self.assertEqual(result["status"], "accepted")

    def test_compilation_is_not_accepted(self):
        result = classify_album_match(
            album(), ARTIST_MBID, [release_group(secondary_types=["Compilation"])]
        )
        self.assertEqual(result["status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
