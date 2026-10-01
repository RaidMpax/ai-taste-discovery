"""Build a clean, local catalogue-only SQLite copy for deployment review."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from behavior import initialize_database


ROOT = Path(__file__).parent
DEFAULT_SOURCE = ROOT / "taste.db"
DEFAULT_MANIFEST = ROOT / "album_match_manifest.json"
DEFAULT_OUTPUT = ROOT / "deployment" / "catalog_musicbrainz_only.db"


def load_accepted_ids(manifest_path: Path) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    albums = manifest.get("albums") if isinstance(manifest, dict) else None
    if not isinstance(albums, list):
        raise ValueError("Manifest must contain an albums list")

    accepted_ids = [
        album.get("release_group_mbid")
        for album in albums
        if album.get("status") == "accepted"
    ]
    if not accepted_ids or any(not mbid for mbid in accepted_ids):
        raise ValueError("Manifest must contain accepted albums with MBIDs")
    if len(accepted_ids) != len(set(accepted_ids)):
        raise ValueError("Accepted manifest albums contain duplicate MBIDs")
    return accepted_ids


def open_read_only(database_path: Path) -> sqlite3.Connection:
    path = database_path.resolve()
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def build_deployment_catalog(
    source_path: Path, manifest_path: Path, output_path: Path
) -> dict:
    """Copy accepted catalogue rows, deliberately omitting reviews and behavior."""
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise ValueError("Output database must not overwrite the source database")

    accepted_ids = load_accepted_ids(manifest_path)
    placeholders = ", ".join("?" for _ in accepted_ids)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        prefix="catalog-", suffix=".db", dir=output_path.parent, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        initialize_database(temporary_path)
        source = open_read_only(source_path)
        target = sqlite3.connect(temporary_path)
        target.execute("PRAGMA foreign_keys = ON")
        try:
            albums = source.execute(
                f"""
                SELECT release_group_mbid, title, release_year, cover_url
                FROM albums
                WHERE release_group_mbid IN ({placeholders})
                ORDER BY release_group_mbid
                """,
                accepted_ids,
            ).fetchall()
            found_ids = {row[0] for row in albums}
            missing_ids = sorted(set(accepted_ids) - found_ids)
            if missing_ids:
                raise ValueError(
                    f"{len(missing_ids)} accepted albums are missing from the source DB"
                )
            source_album_count = source.execute(
                "SELECT COUNT(*) FROM albums"
            ).fetchone()[0]

            credits = source.execute(
                f"""
                SELECT release_group_mbid, artist_mbid, credit_order
                FROM album_artists
                WHERE release_group_mbid IN ({placeholders})
                ORDER BY release_group_mbid, credit_order
                """,
                accepted_ids,
            ).fetchall()
            artist_ids = sorted({row[1] for row in credits})
            if artist_ids:
                artist_placeholders = ", ".join("?" for _ in artist_ids)
                artists = source.execute(
                    f"""
                    SELECT artist_mbid, name FROM artists
                    WHERE artist_mbid IN ({artist_placeholders})
                    ORDER BY artist_mbid
                    """,
                    artist_ids,
                ).fetchall()
            else:
                artists = []

            tags = source.execute(
                f"""
                SELECT release_group_mbid, raw_tag, normalized_tag, tag_rank, source
                FROM album_tags
                WHERE release_group_mbid IN ({placeholders})
                  AND source = 'musicbrainz'
                ORDER BY release_group_mbid, source, tag_rank
                """,
                accepted_ids,
            ).fetchall()
            accepted_tag_rows = source.execute(
                f"""
                SELECT COUNT(*) FROM album_tags
                WHERE release_group_mbid IN ({placeholders})
                """,
                accepted_ids,
            ).fetchone()[0]

            with target:
                target.executemany(
                    "INSERT INTO albums VALUES (?, ?, ?, ?)", albums
                )
                target.executemany("INSERT INTO artists VALUES (?, ?)", artists)
                target.executemany(
                    "INSERT INTO album_artists VALUES (?, ?, ?)", credits
                )
                target.executemany(
                    "INSERT INTO album_tags VALUES (?, ?, ?, ?, ?)", tags
                )

            integrity_errors = target.execute("PRAGMA foreign_key_check").fetchall()
            if integrity_errors:
                raise ValueError("Exported database has foreign-key violations")

            counts = {
                table: target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "albums",
                    "artists",
                    "album_artists",
                    "album_tags",
                    "reviews",
                    "sessions",
                    "taste_profile_events",
                    "taste_profile_event_albums",
                    "recommendation_impressions",
                    "recommendation_feedback",
                    "taste_battles",
                )
            }
        finally:
            source.close()
            target.close()

        os.replace(temporary_path, output_path)
        return {
            "output": str(output_path),
            "manifest_album_count": len(accepted_ids),
            "excluded_source_albums": source_album_count - len(accepted_ids),
            "counts": counts,
            "tag_source_filter": "musicbrainz",
            "non_musicbrainz_tag_rows_omitted": accepted_tag_rows - len(tags),
            "reviews_omitted_pending_attribution_and_reuse_review": True,
            "behavior_rows_omitted": True,
        }
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = build_deployment_catalog(args.source, args.manifest, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
