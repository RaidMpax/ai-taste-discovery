"""Backfill MusicBrainz tags for accepted albums, preserving Last.fm rows."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ingest import (
    DEFAULT_DATABASE,
    DEFAULT_INPUT,
    error_message,
    extract_musicbrainz_tags,
    fetch_musicbrainz,
    load_seeds,
)


EXPERIMENT_DIR = Path(__file__).parent
AB_CACHE_PATH = EXPERIMENT_DIR / "api_cache.json"
CACHE_PATH = EXPERIMENT_DIR / "musicbrainz_tag_migration_cache.json"
REPORT_PATH = EXPERIMENT_DIR / "musicbrainz_tag_migration_report.json"
BACKUP_PATH = EXPERIMENT_DIR / "taste_before_musicbrainz.db"


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    """Replace a cache/report atomically so an interrupted run stays resumable."""
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(data, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def cached_tags(entries: list[dict]) -> list[dict]:
    """Apply the same normalizer to the successful 50-album A/B cache."""
    raw_entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_entries.append(
            {"name": entry.get("name") or entry.get("raw_tag"), "count": entry.get("count")}
        )
    return extract_musicbrainz_tags(raw_entries, [])


def load_cache(seeds: list[dict]) -> dict:
    cache = read_json(CACHE_PATH, {"musicbrainz": {}})
    results = cache.setdefault("musicbrainz", {})
    old_cache = read_json(AB_CACHE_PATH, {}).get("musicbrainz", {})
    for seed in seeds:
        mbid = seed["release_group_mbid"]
        if mbid in results:
            continue
        old_result = old_cache.get(mbid, {})
        if old_result.get("status") == "ok":
            results[mbid] = {
                "status": "success",
                "tags": cached_tags(old_result.get("tags", [])),
                "cache_source": "tag_source_ab_test/api_cache.json",
            }
    return cache


def validate_database(database_path: Path, seeds: list[dict]) -> None:
    if not database_path.is_file():
        raise FileNotFoundError(f"Database not found: {database_path}")
    connection = sqlite3.connect(
        f"file:{database_path.resolve().as_posix()}?mode=ro", uri=True
    )
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if not {"albums", "album_tags"}.issubset(tables):
            raise RuntimeError("Database is missing albums or album_tags")
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(album_tags)")
        }
        if not {"release_group_mbid", "raw_tag", "normalized_tag", "tag_rank", "source"}.issubset(columns):
            raise RuntimeError("album_tags does not have the expected source-aware schema")

        accepted_ids = [seed["release_group_mbid"] for seed in seeds]
        placeholders = ", ".join("?" for _ in accepted_ids)
        present_ids = {
            row[0]
            for row in connection.execute(
                f"SELECT release_group_mbid FROM albums WHERE release_group_mbid IN ({placeholders})",
                accepted_ids,
            )
        }
        missing = set(accepted_ids) - present_ids
        if missing:
            raise RuntimeError(f"{len(missing)} accepted albums are missing from SQLite")
    finally:
        connection.close()


def make_backup(database_path: Path) -> None:
    if BACKUP_PATH.exists():
        return
    source = sqlite3.connect(database_path)
    backup = sqlite3.connect(BACKUP_PATH)
    try:
        source.backup(backup)
    finally:
        backup.close()
        source.close()


def apply_tags(database_path: Path, seeds: list[dict], results: dict) -> int:
    successful = {
        seed["release_group_mbid"]: results[seed["release_group_mbid"]]
        for seed in seeds
        if results.get(seed["release_group_mbid"], {}).get("status") == "success"
    }
    if not successful:
        return 0

    make_backup(database_path)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            for mbid, result in successful.items():
                # Replace only this provider's rows after a successful MB response.
                connection.execute(
                    "DELETE FROM album_tags WHERE release_group_mbid = ? AND source = 'musicbrainz'",
                    (mbid,),
                )
                connection.executemany(
                    """
                    INSERT INTO album_tags (
                        release_group_mbid, raw_tag, normalized_tag, tag_rank, source
                    )
                    VALUES (?, ?, ?, ?, 'musicbrainz')
                    """,
                    [
                        (
                            mbid,
                            tag["raw_tag"],
                            tag["normalized_tag"],
                            tag["tag_rank"],
                        )
                        for tag in result.get("tags", [])
                    ],
                )
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError(f"Foreign-key check failed: {foreign_key_errors[:3]}")
        return len(successful)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def build_report(
    database_path: Path, seeds: list[dict], results: dict, applied_albums: int
) -> dict:
    connection = sqlite3.connect(database_path)
    try:
        albums = {
            row[0]: {"title": row[1], "artist": row[2]}
            for row in connection.execute(
                """
                SELECT al.release_group_mbid, al.title,
                       GROUP_CONCAT(ar.name, ', ')
                FROM albums AS al
                LEFT JOIN album_artists AS aa
                  ON aa.release_group_mbid = al.release_group_mbid
                LEFT JOIN artists AS ar ON ar.artist_mbid = aa.artist_mbid
                GROUP BY al.release_group_mbid
                """
            )
        }
        tag_counts = {
            mbid: len(result.get("tags", []))
            for mbid, result in results.items()
            if result.get("status") == "success"
        }
        statuses = Counter(
            results.get(seed["release_group_mbid"], {}).get("status", "missing")
            for seed in seeds
        )
        no_tag_albums = [
            {
                "release_group_mbid": seed["release_group_mbid"],
                **albums.get(seed["release_group_mbid"], {}),
            }
            for seed in seeds
            if tag_counts.get(seed["release_group_mbid"]) == 0
        ]
        failures = [
            {
                "release_group_mbid": seed["release_group_mbid"],
                **albums.get(seed["release_group_mbid"], {}),
                "status": results.get(seed["release_group_mbid"], {}).get(
                    "status", "missing"
                ),
                "error": results.get(seed["release_group_mbid"], {}).get("error"),
            }
            for seed in seeds
            if results.get(seed["release_group_mbid"], {}).get("status") != "success"
        ]
        values = [tag_counts[seed["release_group_mbid"]] for seed in seeds if seed["release_group_mbid"] in tag_counts]
        tag_vote_counts = [
            tag["count"]
            for seed in seeds
            for tag in results.get(seed["release_group_mbid"], {}).get("tags", [])
            if isinstance(tag.get("count"), (int, float))
        ]
        tag_row_counts = dict(
            connection.execute(
                "SELECT source, COUNT(*) FROM album_tags GROUP BY source"
            ).fetchall()
        )
        known_count = len(values)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": str(database_path.resolve()),
            "source": "MusicBrainz release-group tags + genres",
            "requested_albums": len(seeds),
            "successful_responses": statuses.get("success", 0),
            "albums_written": applied_albums,
            "albums_with_tags": sum(value > 0 for value in values),
            "coverage_percent": round(
                sum(value > 0 for value in values) / len(seeds) * 100, 1
            ),
            "coverage_among_successful_responses_percent": round(
                sum(value > 0 for value in values) / known_count * 100, 1
            )
            if known_count
            else None,
            "albums_with_no_tags": no_tag_albums,
            "api_failures_or_unavailable": failures,
            "request_statuses": dict(statuses),
            "tag_count_per_album": {
                "average_among_successful_responses": round(
                    sum(values) / known_count, 2
                )
                if known_count
                else None,
                "median_among_successful_responses": median(values) if values else None,
                "successful_response_count": known_count,
                "distribution": dict(sorted(Counter(values).items())),
                "buckets": {
                    "0": sum(value == 0 for value in values),
                    "1-3": sum(1 <= value <= 3 for value in values),
                    "4-7": sum(4 <= value <= 7 for value in values),
                    "8-20": sum(8 <= value <= 20 for value in values),
                    ">20": sum(value > 20 for value in values),
                },
            },
            "tag_vote_count_distribution": {
                "tag_values_with_count": len(tag_vote_counts),
                "median_count": sorted(tag_vote_counts)[len(tag_vote_counts) // 2]
                if tag_vote_counts
                else None,
                "1": sum(value == 1 for value in tag_vote_counts),
                "2-4": sum(2 <= value <= 4 for value in tag_vote_counts),
                "5-9": sum(5 <= value <= 9 for value in tag_vote_counts),
                "10+": sum(value >= 10 for value in tag_vote_counts),
            },
            "tag_vote_counts_are_retained_in_local_cache_not_sqlite": True,
            "database_tag_rows_by_source": tag_row_counts,
            "lastfm_rows_deleted": False,
            "schema_changed": False,
        }
        return report
    finally:
        connection.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    seeds = load_seeds(args.manifest)
    validate_database(args.database, seeds)
    cache = load_cache(seeds)
    results = cache["musicbrainz"]
    pending = [
        seed
        for seed in seeds
        if results.get(seed["release_group_mbid"], {}).get("status") != "success"
    ]
    print(
        f"Accepted albums: {len(seeds)}; cached successes: {len(seeds) - len(pending)}; "
        f"MusicBrainz requests remaining: {len(pending)} (one at a time, rate-limited).",
        flush=True,
    )

    for index, seed in enumerate(pending, start=1):
        mbid = seed["release_group_mbid"]
        try:
            response = fetch_musicbrainz(mbid)
            results[mbid] = {
                "status": "success",
                "tags": response["tags"],
                "album_title": response["title"],
            }
        except Exception as error:
            results[mbid] = {"status": "error", "error": error_message(error)}
        write_json(CACHE_PATH, cache)
        if index % 10 == 0 or index == len(pending):
            tag_count = len(results.get(mbid, {}).get("tags", []))
            print(
                f"Fetched {index}/{len(pending)}; latest {seed['album']} — "
                f"{tag_count} tags; status={results[mbid]['status']}",
                flush=True,
            )

    applied_albums = apply_tags(args.database, seeds, results)
    report = build_report(args.database, seeds, results, applied_albums)
    write_json(REPORT_PATH, report)
    print(f"Wrote migration report: {REPORT_PATH}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["api_failures_or_unavailable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
