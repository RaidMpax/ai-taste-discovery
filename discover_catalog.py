"""Discover album candidates and resolve them to MusicBrainz release groups."""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from ingest import (
    MUSICBRAINZ_DELAY_SECONDS,
    get_json,
    get_lastfm_api_key,
)


ROOT = Path(__file__).parent
DEFAULT_ARTISTS = ROOT / "catalog_artists.json"
DEFAULT_OUTPUT = ROOT / "catalog_manifest.json"
MIN_AUTO_ACCEPT_SCORE = 95
BLOCKED_SECONDARY_TYPES = {
    "audio drama",
    "audiobook",
    "compilation",
    "demo",
    "dj-mix",
    "field recording",
    "interview",
    "live",
    "mixtape/street",
    "remix",
    "spokenword",
}


def normalize_title(value: str) -> str:
    """Make title comparison insensitive to case, spacing, and punctuation."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def escape_lucene_phrase(value: str) -> str:
    """Escape characters that have special meaning in a Lucene phrase."""
    special = set('+-&|!(){}[]^"~*?:\\/')
    return "".join(f"\\{character}" if character in special else character for character in value)


def artist_ids(release_group: dict) -> set[str]:
    return {
        credit["artist"]["id"]
        for credit in release_group.get("artist-credit", [])
        if credit.get("artist", {}).get("id")
    }


def artist_credit_text(release_group: dict) -> str:
    return "".join(
        credit.get("name", "") + credit.get("joinphrase", "")
        for credit in release_group.get("artist-credit", [])
    )


def classify_match(
    requested_title: str,
    artist_mbid: str,
    release_groups: list[dict],
) -> dict:
    """Classify the best MusicBrainz result without silently trusting it."""
    if not release_groups:
        return {
            "status": "unmatched",
            "match_reasons": ["MusicBrainz returned no release group"],
        }

    evaluated = []
    for release_group in release_groups:
        score = int(release_group.get("score", 0))
        title_matches = normalize_title(requested_title) == normalize_title(
            release_group.get("title", "")
        )
        artist_matches = artist_mbid in artist_ids(release_group)
        primary_type = (release_group.get("primary-type") or "").casefold()
        secondary_types = {
            item.casefold() for item in release_group.get("secondary-types", [])
        }
        blocked_types = sorted(
            secondary_types.intersection(BLOCKED_SECONDARY_TYPES)
        )

        reasons = []
        if score < MIN_AUTO_ACCEPT_SCORE:
            reasons.append(f"score below {MIN_AUTO_ACCEPT_SCORE}")
        if not title_matches:
            reasons.append("normalized title differs")
        if not artist_matches:
            reasons.append("seed artist MBID is absent from artist credit")
        if primary_type != "album":
            reasons.append("primary type is not Album")
        if blocked_types:
            reasons.append("blocked secondary type: " + ", ".join(blocked_types))

        evaluated.append(
            {
                "status": "accepted" if not reasons else "needs_review",
                "release_group_mbid": release_group.get("id"),
                "matched_title": release_group.get("title"),
                "matched_artist": artist_credit_text(release_group),
                "first_release_date": release_group.get("first-release-date") or None,
                "score": score,
                "primary_type": release_group.get("primary-type"),
                "secondary_types": release_group.get("secondary-types", []),
                "match_reasons": reasons
                or ["high-confidence exact artist/title match"],
            }
        )

    # Search ranking is useful, but an exact validated result in the top five is
    # safer than blindly trusting only the first result.
    return next(
        (result for result in evaluated if result["status"] == "accepted"),
        evaluated[0],
    )


def fetch_top_albums(artist: dict, api_key: str, limit: int) -> list[dict]:
    data = get_json(
        "https://ws.audioscrobbler.com/2.0/",
        {
            "method": "artist.getTopAlbums",
            "artist": artist["name"],
            "autocorrect": 0,
            "limit": limit,
            "api_key": api_key,
            "format": "json",
        },
    )
    if "error" in data:
        raise RuntimeError(data.get("message", "Last.fm error"))

    albums = data.get("topalbums", {}).get("album", [])
    if isinstance(albums, dict):
        albums = [albums]
    return [
        {
            "title": album.get("name", "").strip(),
            "playcount": int(album.get("playcount") or 0),
            "lastfm_url": album.get("url"),
        }
        for album in albums
        if album.get("name", "").strip()
    ]


def search_release_groups(title: str, artist_mbid: str) -> list[dict]:
    query = (
        f'releasegroup:"{escape_lucene_phrase(title)}" '
        f"AND arid:{artist_mbid} AND primarytype:album"
    )
    try:
        data = get_json(
            "https://musicbrainz.org/ws/2/release-group/",
            {"query": query, "fmt": "json", "limit": 5},
        )
        return data.get("release-groups", [])
    finally:
        # MusicBrainz allows an average of one request per second.
        time.sleep(MUSICBRAINZ_DELAY_SECONDS)


def summarize(candidates: list[dict], artists_processed: list[str]) -> dict:
    statuses = {"accepted": 0, "needs_review": 0, "unmatched": 0, "error": 0}
    for candidate in candidates:
        statuses[candidate["status"]] = statuses.get(candidate["status"], 0) + 1
    release_group_mbids = [
        candidate["release_group_mbid"]
        for candidate in candidates
        if candidate.get("release_group_mbid")
    ]
    unique_release_groups = len(set(release_group_mbids))
    return {
        "artists_processed": len(artists_processed),
        "candidate_count": len(candidates),
        "unique_release_groups": unique_release_groups,
        "duplicate_release_group_candidates": (
            len(release_group_mbids) - unique_release_groups
        ),
        **statuses,
    }


def save_manifest(path: Path, manifest: dict) -> None:
    manifest["summary"] = summarize(
        manifest["candidates"], manifest["processed_artist_mbids"]
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def new_manifest(args: argparse.Namespace) -> dict:
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "artists_file": str(args.artists),
            "albums_per_artist": args.albums_per_artist,
            "minimum_auto_accept_score": MIN_AUTO_ACCEPT_SCORE,
        },
        "processed_artist_mbids": [],
        "artist_errors": [],
        "candidates": [],
        "summary": {},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artists", type=Path, default=DEFAULT_ARTISTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--artist-limit", type=int)
    parser.add_argument("--albums-per-artist", type=int, default=20)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue an existing manifest and skip successfully processed artists.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.artist_limit is not None and args.artist_limit < 1:
        raise SystemExit("--artist-limit must be at least 1")
    if args.albums_per_artist < 1:
        raise SystemExit("--albums-per-artist must be at least 1")

    artists = json.loads(args.artists.read_text(encoding="utf-8"))
    if args.artist_limit is not None:
        artists = artists[: args.artist_limit]

    if args.resume and args.output.exists():
        manifest = json.loads(args.output.read_text(encoding="utf-8"))
    else:
        manifest = new_manifest(args)

    processed = set(manifest["processed_artist_mbids"])
    api_key = get_lastfm_api_key()

    for artist_number, artist in enumerate(artists, start=1):
        artist_mbid = artist["artist_mbid"]
        if artist_mbid in processed:
            continue

        # A resume retries failed work cleanly instead of appending duplicates.
        manifest["candidates"] = [
            candidate
            for candidate in manifest["candidates"]
            if candidate["source_artist_mbid"] != artist_mbid
        ]
        manifest["artist_errors"] = [
            error
            for error in manifest["artist_errors"]
            if error["artist_mbid"] != artist_mbid
        ]

        print(f'[{artist_number}/{len(artists)}] Discovering {artist["name"]}')
        try:
            top_albums = fetch_top_albums(
                artist, api_key, args.albums_per_artist
            )
        except Exception as error:
            manifest["artist_errors"].append(
                {
                    "artist_mbid": artist_mbid,
                    "artist": artist["name"],
                    "error": str(error),
                }
            )
            save_manifest(args.output, manifest)
            continue

        artist_had_error = False
        for rank, album in enumerate(top_albums, start=1):
            print(f'  [{rank}/{len(top_albums)}] {album["title"]}')
            base = {
                "source": "lastfm_artist_top_albums",
                "source_artist_mbid": artist_mbid,
                "source_artist": artist["name"],
                "source_rank": rank,
                "source_album": album["title"],
                "source_playcount": album["playcount"],
                "source_url": album["lastfm_url"],
            }
            try:
                groups = search_release_groups(album["title"], artist_mbid)
                candidate = {**base, **classify_match(album["title"], artist_mbid, groups)}
            except Exception as error:
                artist_had_error = True
                candidate = {
                    **base,
                    "status": "error",
                    "match_reasons": [str(error)],
                }
            manifest["candidates"].append(candidate)

        if not artist_had_error:
            manifest["processed_artist_mbids"].append(artist_mbid)
            processed.add(artist_mbid)
        save_manifest(args.output, manifest)

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    save_manifest(args.output, manifest)
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    has_errors = bool(manifest["artist_errors"]) or any(
        candidate["status"] == "error" for candidate in manifest["candidates"]
    )
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
