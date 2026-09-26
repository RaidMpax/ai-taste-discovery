"""Day 3: fetch the confirmed album catalogue and write it to SQLite."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).parent
DEFAULT_INPUT = ROOT / "test_albums.json"
DEFAULT_DATABASE = ROOT / "taste.db"
DEFAULT_REPORT = ROOT / "ingestion_report.json"
SCHEMA_PATH = ROOT / "schema.sql"

USER_AGENT = os.getenv(
    "MUSICBRAINZ_USER_AGENT",
    "AI-Taste-Discovery/0.1 (https://github.com/RaidMpax/ai-taste-discovery)",
)
MUSICBRAINZ_DELAY_SECONDS = 1.1
TAG_ALIASES = {
    "jpop": "j-pop",
    "trip hop": "trip-hop",
}


def read_local_api_key(env_path: Path) -> str | None:
    """Read LASTFM_API_KEY from a small local .env file without dependencies."""
    if not env_path.exists():
        return None

    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "LASTFM_API_KEY":
            return value.strip().strip('"').strip("'") or None
    return None


def get_lastfm_api_key() -> str:
    """Resolve the key from the process, local .env, or an interactive prompt."""
    key = os.getenv("LASTFM_API_KEY") or read_local_api_key(ROOT / ".env")
    if key:
        return key

    if not sys.stdin.isatty():
        raise SystemExit(
            "LASTFM_API_KEY is not set. Run ingest.py in a terminal once to configure it."
        )

    key = getpass.getpass("Last.fm API key (input hidden): ").strip()
    if not key:
        raise SystemExit("No Last.fm API key was provided")

    save = input("Save it to the local, Git-ignored .env file? [Y/n]: ").strip().lower()
    if save in {"", "y", "yes"}:
        (ROOT / ".env").write_text(
            f"LASTFM_API_KEY={key}\n",
            encoding="utf-8",
        )
        print("Saved LASTFM_API_KEY to local .env (ignored by Git).")
    return key


def get_json(base_url: str, params: dict | None = None, retries: int = 2) -> dict:
    """Request JSON and retry temporary network or server failures."""
    url = base_url
    if params:
        url += "?" + urlencode(params)

    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == retries:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == retries:
                raise
        time.sleep(2**attempt)

    raise RuntimeError("unreachable")


def error_message(error: Exception) -> str:
    if isinstance(error, HTTPError):
        return f"HTTP {error.code}"
    return str(error)


def fetch_musicbrainz(release_group_mbid: str) -> dict:
    """Fetch canonical album metadata by confirmed release-group MBID."""
    try:
        data = get_json(
            f"https://musicbrainz.org/ws/2/release-group/{release_group_mbid}",
            {"inc": "artist-credits", "fmt": "json"},
        )
    finally:
        # MusicBrainz requires clients to remain at or below one request/second.
        time.sleep(MUSICBRAINZ_DELAY_SECONDS)

    if data.get("id") != release_group_mbid:
        raise ValueError("MusicBrainz returned an unexpected release-group MBID")

    credits = []
    for order, credit in enumerate(data.get("artist-credit", []), start=1):
        artist = credit.get("artist") or {}
        if not artist.get("id"):
            continue
        credits.append(
            {
                "artist_mbid": artist["id"],
                "name": credit.get("name") or artist.get("name"),
                "credit_order": order,
            }
        )

    if not credits:
        raise ValueError("MusicBrainz returned no usable artist credits")

    first_release_date = data.get("first-release-date") or ""
    year_text = first_release_date[:4]
    return {
        "status": "success",
        "release_group_mbid": release_group_mbid,
        "title": data.get("title"),
        "release_year": int(year_text) if year_text.isdigit() else None,
        "artists": credits,
    }


def fetch_cover(release_group_mbid: str) -> dict:
    try:
        data = get_json(
            f"https://coverartarchive.org/release-group/{release_group_mbid}"
        )
    except HTTPError as error:
        if error.code == 404:
            return {"status": "missing", "url": None}
        return {"status": "error", "error": error_message(error)}
    except (URLError, TimeoutError, ConnectionError) as error:
        return {"status": "error", "error": error_message(error)}

    front = next(
        (image for image in data.get("images", []) if image.get("front")),
        None,
    )
    if not front:
        return {"status": "missing", "url": None}
    return {"status": "found", "url": front.get("image")}


def normalize_tag(raw_tag: str) -> str:
    normalized = " ".join(raw_tag.strip().lower().split())
    return TAG_ALIASES.get(normalized, normalized)


def fetch_lastfm(artist: str, album: str, api_key: str) -> dict:
    try:
        data = get_json(
            "https://ws.audioscrobbler.com/2.0/",
            {
                "method": "album.getTopTags",
                "artist": artist,
                "album": album,
                "autocorrect": 1,
                "api_key": api_key,
                "format": "json",
            },
        )
        if "error" in data:
            raise RuntimeError(data.get("message", "Last.fm error"))

        source_tags = data.get("toptags", {}).get("tag", [])
        if isinstance(source_tags, dict):
            source_tags = [source_tags]

        tags = []
        seen_raw_tags = set()
        for rank, tag in enumerate(source_tags, start=1):
            raw_tag = tag.get("name", "")
            normalized_tag = normalize_tag(raw_tag)
            if not normalized_tag or raw_tag in seen_raw_tags:
                continue
            seen_raw_tags.add(raw_tag)
            tags.append(
                {
                    "raw_tag": raw_tag,
                    "normalized_tag": normalized_tag,
                    "tag_rank": rank,
                }
            )
        return {"status": "success", "count": len(tags), "tags": tags}
    except (HTTPError, URLError, TimeoutError, ConnectionError, RuntimeError) as error:
        return {"status": "error", "error": error_message(error)}


def fetch_reviews(release_group_mbid: str) -> dict:
    try:
        list_data = get_json(
            "https://critiquebrainz.org/ws/1/review/",
            {
                "entity_id": release_group_mbid,
                "entity_type": "release_group",
                "review_type": "review",
                "limit": 50,
            },
        )
    except (HTTPError, URLError, TimeoutError, ConnectionError) as error:
        return {"status": "error", "error": error_message(error)}

    summaries = [
        review
        for review in list_data.get("reviews", [])
        if review.get("id")
    ]
    review_ids = [review["id"] for review in summaries]
    if not review_ids:
        return {
            "status": "success",
            "listed_count": 0,
            "count": 0,
            "invalid_count": 0,
            "reviews": [],
        }

    # The list endpoint can omit license details. Fetch the fuller records in
    # one request, then use the single-review endpoint only as a fallback.
    try:
        detail_data = get_json(
            "https://critiquebrainz.org/ws/1/reviews",
            {"review_ids": ",".join(review_ids)},
        )
        details = detail_data.get("reviews", {})
    except (HTTPError, URLError, TimeoutError, ConnectionError):
        details = {}

    reviews = []
    invalid_count = 0
    for summary in summaries:
        review_id = summary["id"]
        detail = details.get(review_id) or {}

        text = detail.get("text") or summary.get("text") or ""
        language = detail.get("language") or summary.get("language")
        license_data = detail.get("license") or summary.get("license") or {}
        license_id = license_data.get("id") if isinstance(license_data, dict) else None

        if not language or not license_id or not text.strip():
            try:
                single_data = get_json(
                    f"https://critiquebrainz.org/ws/1/review/{review_id}"
                )
                single = single_data.get("review", {})
            except (HTTPError, URLError, TimeoutError, ConnectionError):
                single = {}

            text = single.get("text") or text
            language = single.get("language") or language
            single_license = single.get("license") or {}
            if isinstance(single_license, dict):
                license_id = single_license.get("id") or license_id
            if single:
                detail = single

        if not language or not license_id or not text.strip():
            invalid_count += 1
            continue

        reviews.append(
            {
                "review_id": review_id,
                "language": language,
                "source": detail.get("source") or summary.get("source"),
                "source_url": detail.get("source_url") or summary.get("source_url"),
                "license": license_id,
                "review_text": text,
            }
        )

    return {
        "status": "success",
        "listed_count": len(summaries),
        "count": len(reviews),
        "invalid_count": invalid_count,
        "reviews": reviews,
    }


def fetch_album(seed: dict, lastfm_api_key: str) -> dict:
    result = {
        "requested_artist": seed["artist"],
        "requested_album": seed["album"],
        "release_group_mbid": seed["release_group_mbid"],
    }

    try:
        result["musicbrainz"] = fetch_musicbrainz(seed["release_group_mbid"])
    except (
        HTTPError,
        URLError,
        TimeoutError,
        ConnectionError,
        RuntimeError,
        ValueError,
    ) as error:
        result["musicbrainz"] = {
            "status": "error",
            "error": error_message(error),
        }
        return result

    result["cover_art_archive"] = fetch_cover(seed["release_group_mbid"])
    result["lastfm"] = fetch_lastfm(seed["artist"], seed["album"], lastfm_api_key)
    result["critiquebrainz"] = fetch_reviews(seed["release_group_mbid"])
    return result


def open_database(database_path: Path) -> sqlite3.Connection:
    is_new = not database_path.exists()
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")

    if is_new:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    required_tables = {
        "artists",
        "albums",
        "album_artists",
        "album_tags",
        "reviews",
    }
    existing_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    missing_tables = required_tables - existing_tables
    if missing_tables:
        connection.close()
        raise RuntimeError(f"Database is missing tables: {sorted(missing_tables)}")

    return connection


def write_album(connection: sqlite3.Connection, result: dict) -> dict:
    musicbrainz = result["musicbrainz"]
    release_group_mbid = result["release_group_mbid"]
    cover = result["cover_art_archive"]

    existing = connection.execute(
        "SELECT cover_url FROM albums WHERE release_group_mbid = ?",
        (release_group_mbid,),
    ).fetchone()
    existing_cover_url = existing[0] if existing else None
    cover_url = (
        existing_cover_url if cover["status"] == "error" else cover.get("url")
    )

    with connection:
        connection.execute(
            """
            INSERT INTO albums (
                release_group_mbid,
                title,
                release_year,
                cover_url
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT (release_group_mbid)
            DO UPDATE SET
                title = excluded.title,
                release_year = excluded.release_year,
                cover_url = excluded.cover_url
            """,
            (
                release_group_mbid,
                musicbrainz["title"],
                musicbrainz["release_year"],
                cover_url,
            ),
        )

        for artist in musicbrainz["artists"]:
            connection.execute(
                """
                INSERT INTO artists (artist_mbid, name)
                VALUES (?, ?)
                ON CONFLICT (artist_mbid)
                DO UPDATE SET name = excluded.name
                """,
                (artist["artist_mbid"], artist["name"]),
            )

        connection.execute(
            "DELETE FROM album_artists WHERE release_group_mbid = ?",
            (release_group_mbid,),
        )
        connection.executemany(
            """
            INSERT INTO album_artists (
                release_group_mbid,
                artist_mbid,
                credit_order
            )
            VALUES (?, ?, ?)
            """,
            [
                (
                    release_group_mbid,
                    artist["artist_mbid"],
                    artist["credit_order"],
                )
                for artist in musicbrainz["artists"]
            ],
        )

        lastfm = result["lastfm"]
        if lastfm["status"] == "success":
            connection.execute(
                """
                DELETE FROM album_tags
                WHERE release_group_mbid = ? AND source = 'lastfm'
                """,
                (release_group_mbid,),
            )
            connection.executemany(
                """
                INSERT INTO album_tags (
                    release_group_mbid,
                    raw_tag,
                    normalized_tag,
                    tag_rank,
                    source
                )
                VALUES (?, ?, ?, ?, 'lastfm')
                """,
                [
                    (
                        release_group_mbid,
                        tag["raw_tag"],
                        tag["normalized_tag"],
                        tag["tag_rank"],
                    )
                    for tag in lastfm["tags"]
                ],
            )

        reviews = result["critiquebrainz"]
        if reviews["status"] == "success":
            # V0.1 stores only CritiqueBrainz reviews in this table.
            connection.execute(
                "DELETE FROM reviews WHERE release_group_mbid = ?",
                (release_group_mbid,),
            )
            connection.executemany(
                """
                INSERT INTO reviews (
                    review_id,
                    release_group_mbid,
                    language,
                    source,
                    source_url,
                    license,
                    review_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        review["review_id"],
                        release_group_mbid,
                        review["language"],
                        review["source"],
                        review["source_url"],
                        review["license"],
                        review["review_text"],
                    )
                    for review in reviews["reviews"]
                ],
            )

    return {
        "status": "written",
        "artist_count": len(musicbrainz["artists"]),
        "tag_count": connection.execute(
            "SELECT COUNT(*) FROM album_tags WHERE release_group_mbid = ?",
            (release_group_mbid,),
        ).fetchone()[0],
        "review_count": connection.execute(
            "SELECT COUNT(*) FROM reviews WHERE release_group_mbid = ?",
            (release_group_mbid,),
        ).fetchone()[0],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only the first N albums for staged validation.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")

    lastfm_api_key = get_lastfm_api_key()

    seeds = json.loads(args.input.read_text(encoding="utf-8"))
    if args.limit is not None:
        seeds = seeds[: args.limit]

    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "database": str(args.database),
        "albums": [],
    }

    connection = open_database(args.database)
    try:
        for index, seed in enumerate(seeds, start=1):
            print(f'[{index}/{len(seeds)}] {seed["artist"]} — {seed["album"]}')
            result = fetch_album(seed, lastfm_api_key)
            if result["musicbrainz"]["status"] == "success":
                try:
                    result["database_write"] = write_album(connection, result)
                except sqlite3.Error as error:
                    result["database_write"] = {
                        "status": "error",
                        "error": str(error),
                    }
            else:
                result["database_write"] = {"status": "skipped"}
            report["albums"].append(result)
    finally:
        connection.close()

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.report}")

    has_errors = any(
        album["musicbrainz"]["status"] == "error"
        or album.get("cover_art_archive", {}).get("status") == "error"
        or album.get("lastfm", {}).get("status") == "error"
        or album.get("critiquebrainz", {}).get("status") == "error"
        or album["database_write"]["status"] == "error"
        for album in report["albums"]
    )
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
