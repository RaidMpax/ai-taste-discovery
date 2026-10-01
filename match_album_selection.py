"""Resolve the editorial album selection to canonical MusicBrainz IDs.

This script only writes a JSON manifest and a Markdown report. It never opens
or changes the SQLite database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from ingest import MUSICBRAINZ_DELAY_SECONDS, get_json


ROOT = Path(__file__).parent
DEFAULT_OUTPUT = ROOT / "album_match_manifest.json"
DEFAULT_REPORT = ROOT / "ALBUM_MATCHING_REPORT.md"
KNOWN_ARTISTS = ROOT / "catalog_artists.json"
ARTIST_OVERRIDES = ROOT / "artist_mbid_overrides.json"
ALBUM_OVERRIDES = ROOT / "album_mbid_overrides.json"
ALLOWED_ELIGIBILITY = {"both", "seed-only", "recommendation-only"}
ALBUM_SOURCE_KEYS = {
    "source_file",
    "source_line",
    "requested_artist",
    "requested_title",
    "requested_year",
    "requested_type",
    "eligibility",
    "inclusion_role",
}
BLOCKED_SECONDARY_TYPES = {
    "audio drama",
    "audiobook",
    "compilation",
    "demo",
    "dj-mix",
    "field recording",
    "interview",
    "live",
    "remix",
    "spokenword",
}


def normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def parse_selection_files(root: Path) -> list[dict]:
    """Read accepted rows from the human-reviewed Markdown batch files."""
    albums = []
    seen = set()
    for path in sorted(root.glob("ALBUM_SELECTION_BATCH_*.md")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            if len(cells) != 7 or not cells[2].isdigit():
                continue
            artist, title, year, release_type, eligibility, decision, role = cells
            if decision != "accept" or eligibility not in ALLOWED_ELIGIBILITY:
                continue
            key = (normalize(artist), normalize(title))
            if key in seen:
                raise ValueError(f"duplicate artist/title selection: {artist} - {title}")
            seen.add(key)
            albums.append(
                {
                    "source_file": path.name,
                    "source_line": line_number,
                    "requested_artist": artist,
                    "requested_title": title,
                    "requested_year": int(year),
                    "requested_type": release_type,
                    "eligibility": eligibility,
                    "inclusion_role": role,
                }
            )
    if not albums:
        raise ValueError("no accepted album rows found")
    return albums


def selection_fingerprint(albums: list[dict]) -> str:
    stable_rows = [
        {
            key: album[key]
            for key in (
                "requested_artist",
                "requested_title",
                "requested_year",
                "requested_type",
                "eligibility",
            )
        }
        for album in albums
    ]
    payload = json.dumps(stable_rows, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def musicbrainz_json(url: str, params: dict) -> dict:
    try:
        return get_json(url, params)
    finally:
        # MusicBrainz permits an average of one request per second.
        time.sleep(MUSICBRAINZ_DELAY_SECONDS)


def artist_names(candidate: dict) -> set[str]:
    names = {candidate.get("name", ""), candidate.get("sort-name", "")}
    names.update(alias.get("name", "") for alias in candidate.get("aliases", []))
    return {normalize(name) for name in names if name}


def artist_candidate_summary(candidate: dict) -> dict:
    return {
        "artist_mbid": candidate.get("id"),
        "name": candidate.get("name"),
        "sort_name": candidate.get("sort-name"),
        "score": int(candidate.get("score") or 0),
        "type": candidate.get("type"),
        "country": candidate.get("country"),
        "disambiguation": candidate.get("disambiguation") or None,
    }


def classify_artist_match(requested_artist: str, candidates: list[dict]) -> dict:
    requested = normalize(requested_artist)
    exact = [candidate for candidate in candidates if requested in artist_names(candidate)]
    exact.sort(key=lambda candidate: int(candidate.get("score") or 0), reverse=True)

    summaries = [artist_candidate_summary(candidate) for candidate in exact[:5]]
    if not exact:
        return {
            "status": "unmatched",
            "match_reasons": ["no exact normalized artist name or alias"],
            "alternatives": [artist_candidate_summary(item) for item in candidates[:5]],
        }

    top_score = int(exact[0].get("score") or 0)
    second_score = int(exact[1].get("score") or 0) if len(exact) > 1 else 0
    if top_score >= 95 and (len(exact) == 1 or top_score - second_score >= 10):
        return {
            "status": "accepted",
            **artist_candidate_summary(exact[0]),
            "match_method": "musicbrainz_artist_search_exact_name_or_alias",
            "match_reasons": [
                "exact normalized name or alias with score >= 95 and a clear score margin"
            ],
        }

    return {
        "status": "needs_review",
        "match_reasons": ["artist identity is not uniquely high-confidence"],
        "alternatives": summaries,
    }


def search_artist(name: str) -> list[dict]:
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    data = musicbrainz_json(
        "https://musicbrainz.org/ws/2/artist/",
        {"query": f'artist:"{escaped}"', "fmt": "json", "limit": 10},
    )
    return data.get("artists", [])


def broad_search_artist(name: str) -> list[dict]:
    data = musicbrainz_json(
        "https://musicbrainz.org/ws/2/artist/",
        {"query": name, "fmt": "json", "limit": 10},
    )
    return data.get("artists", [])


def fetch_artist_discography(artist_mbid: str) -> list[dict]:
    """Fetch every release-group type so intentional EPs/mixtapes are visible."""
    release_groups = []
    offset = 0
    while True:
        data = musicbrainz_json(
            "https://musicbrainz.org/ws/2/release-group/",
            {
                "artist": artist_mbid,
                "inc": "artist-credits",
                "fmt": "json",
                "limit": 100,
                "offset": offset,
            },
        )
        batch = data.get("release-groups", [])
        release_groups.extend(batch)
        offset += len(batch)
        total = int(data.get("release-group-count", len(release_groups)))
        if not batch or offset >= total:
            return release_groups


def fetch_release_group(release_group_mbid: str) -> dict:
    return musicbrainz_json(
        f"https://musicbrainz.org/ws/2/release-group/{release_group_mbid}",
        {"inc": "artist-credits", "fmt": "json"},
    )


def resolve_artist_by_album_evidence(
    requested_artist: str,
    selected_albums: list[dict],
    candidates: list[dict],
) -> dict | None:
    """Resolve a name collision only when one candidate owns selected titles."""
    unique_candidates = []
    seen_mbids = set()
    for candidate in sorted(
        candidates, key=lambda item: int(item.get("score") or 0), reverse=True
    ):
        artist_mbid = candidate.get("id")
        if not artist_mbid or artist_mbid in seen_mbids:
            continue
        if int(candidate.get("score") or 0) < 60:
            continue
        seen_mbids.add(artist_mbid)
        unique_candidates.append(candidate)
        if len(unique_candidates) == 5:
            break

    requested_titles = {
        normalize(album["requested_title"]): album["requested_title"]
        for album in selected_albums
    }
    evidence = []
    for candidate in unique_candidates:
        discography = fetch_artist_discography(candidate["id"])
        matched_titles = sorted(
            {
                requested_titles[normalize(release_group.get("title", ""))]
                for release_group in discography
                if normalize(release_group.get("title", "")) in requested_titles
            }
        )
        evidence.append((candidate, matched_titles))

    evidence.sort(key=lambda item: len(item[1]), reverse=True)
    if not evidence or not evidence[0][1]:
        return None
    top_count = len(evidence[0][1])
    second_count = len(evidence[1][1]) if len(evidence) > 1 else 0
    if top_count == second_count:
        return None

    candidate, matched_titles = evidence[0]
    return {
        "requested_artist": requested_artist,
        "status": "accepted",
        **artist_candidate_summary(candidate),
        "match_method": "selected_album_titles_in_candidate_discography",
        "match_reasons": [
            "only one candidate discography contains the selected album titles"
        ],
        "evidence_titles": matched_titles,
    }


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


def release_type_reasons(requested_type: str, release_group: dict) -> list[str]:
    primary = (release_group.get("primary-type") or "").casefold()
    secondary = {
        item.casefold() for item in release_group.get("secondary-types", [])
    }
    reasons = []
    blocked = sorted(secondary.intersection(BLOCKED_SECONDARY_TYPES))
    if blocked:
        reasons.append("blocked secondary type: " + ", ".join(blocked))

    if requested_type in {"album", "repackage"} and primary != "album":
        reasons.append(f"requested {requested_type}, MusicBrainz primary type is {primary or 'unset'}")
    elif requested_type == "EP" and primary != "ep":
        reasons.append(f"requested EP, MusicBrainz primary type is {primary or 'unset'}")
    elif requested_type == "mixtape" and "mixtape/street" not in secondary:
        reasons.append("requested mixtape, MusicBrainz does not mark Mixtape/Street")
    elif requested_type == "project":
        reasons.append("editorial type 'project' requires manual type confirmation")
    return reasons


def release_candidate_summary(
    release_group: dict, requested_year: int, requested_type: str
) -> dict:
    first_release_date = release_group.get("first-release-date") or None
    year_text = (first_release_date or "")[:4]
    matched_year = int(year_text) if year_text.isdigit() else None
    reasons = release_type_reasons(requested_type, release_group)
    if matched_year is None:
        reasons.append("MusicBrainz has no first release year")
    elif abs(matched_year - requested_year) > 1:
        reasons.append(
            f"requested year {requested_year}, MusicBrainz first release year {matched_year}"
        )
    return {
        "release_group_mbid": release_group.get("id"),
        "matched_title": release_group.get("title"),
        "matched_artist": artist_credit_text(release_group),
        "matched_artist_mbids": sorted(artist_ids(release_group)),
        "first_release_date": first_release_date,
        "primary_type": release_group.get("primary-type"),
        "secondary_types": release_group.get("secondary-types", []),
        "validation_reasons": reasons,
    }


def classify_album_match(album: dict, artist_mbid: str, release_groups: list[dict]) -> dict:
    exact = [
        release_group
        for release_group in release_groups
        if normalize(album["requested_title"]) == normalize(release_group.get("title", ""))
    ]
    if not exact:
        return {
            "status": "unmatched",
            "match_method": "confirmed_artist_discography_exact_title",
            "match_reasons": ["no exact normalized title in confirmed artist discography"],
        }

    evaluated = []
    for release_group in exact:
        item = release_candidate_summary(
            release_group, album["requested_year"], album["requested_type"]
        )
        reasons = list(item.pop("validation_reasons"))
        if artist_mbid not in artist_ids(release_group):
            reasons.append("confirmed artist MBID is absent from release-group credit")
        evaluated.append({**item, "reasons": reasons})

    valid = [item for item in evaluated if not item["reasons"]]
    if len(valid) > 1:
        exact_year = [
            item
            for item in valid
            if (item.get("first_release_date") or "")[:4]
            == str(album["requested_year"])
        ]
        if len(exact_year) == 1:
            valid = exact_year

    if len(valid) == 1:
        result = dict(valid[0])
        result.pop("reasons")
        return {
            "status": "accepted",
            **result,
            "match_method": "confirmed_artist_discography_exact_title",
            "match_reasons": ["unique exact title with compatible artist, type, and year"],
        }

    alternatives = [
        {key: value for key, value in item.items() if key != "reasons"}
        | {"review_reasons": item["reasons"]}
        for item in evaluated
    ]
    reason = (
        "multiple valid exact release groups"
        if len(valid) > 1
        else "exact title found but artist, type, or year requires review"
    )
    return {
        "status": "needs_review",
        "match_method": "confirmed_artist_discography_exact_title",
        "match_reasons": [reason],
        "alternatives": alternatives,
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_manifest(albums: list[dict]) -> dict:
    return {
        "version": 1,
        "generated_at": now_iso(),
        "selection_fingerprint": selection_fingerprint(albums),
        "settings": {
            "selection_glob": "ALBUM_SELECTION_BATCH_*.md",
            "artist_matching": "unique exact normalized MusicBrainz name or alias, score >= 90",
            "album_matching": "exact normalized title inside confirmed artist discography, plus explicitly reviewed and revalidated MBID overrides",
        },
        "artists": [],
        "albums": albums,
        "artist_errors": [],
        "album_errors": [],
        "summary": {},
    }


def summarize(manifest: dict) -> dict:
    def statuses(items: list[dict]) -> dict:
        counts = {"accepted": 0, "needs_review": 0, "unmatched": 0, "error": 0, "pending": 0}
        for item in items:
            status = item.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
        return counts

    accepted_albums = [item for item in manifest["albums"] if item.get("status") == "accepted"]
    mbids = [item["release_group_mbid"] for item in accepted_albums]
    return {
        "artist_count": len(manifest["artists"]),
        "artist_statuses": statuses(manifest["artists"]),
        "album_count": len(manifest["albums"]),
        "album_statuses": statuses(manifest["albums"]),
        "accepted_unique_release_groups": len(set(mbids)),
        "accepted_duplicate_release_groups": len(mbids) - len(set(mbids)),
        "artist_error_count": len(manifest["artist_errors"]),
        "album_error_count": len(manifest["album_errors"]),
    }


def save_manifest(path: Path, manifest: dict) -> None:
    manifest["updated_at"] = now_iso()
    manifest["summary"] = summarize(manifest)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_known_artists() -> dict[str, dict]:
    if not KNOWN_ARTISTS.exists():
        return {}
    artists = json.loads(KNOWN_ARTISTS.read_text(encoding="utf-8"))
    return {normalize(artist["name"]): artist for artist in artists}


def load_artist_overrides() -> dict[str, dict]:
    if not ARTIST_OVERRIDES.exists():
        return {}
    overrides = json.loads(ARTIST_OVERRIDES.read_text(encoding="utf-8"))
    return {normalize(name): value for name, value in overrides.items()}


def load_album_overrides() -> dict[tuple[str, str], dict]:
    if not ALBUM_OVERRIDES.exists():
        return {}
    data = json.loads(ALBUM_OVERRIDES.read_text(encoding="utf-8"))
    return {
        (normalize(item["requested_artist"]), normalize(item["requested_title"])): item
        for item in data.get("overrides", [])
    }


def reset_album_match(album: dict) -> None:
    for key in list(album):
        if key not in ALBUM_SOURCE_KEYS:
            album.pop(key)


def refresh_manifest_selection(manifest: dict, albums: list[dict]) -> None:
    """Refresh edited source rows without discarding unchanged API results."""
    old_by_location = {
        (item["source_file"], item["source_line"]): item
        for item in manifest["albums"]
    }
    new_by_location = {
        (item["source_file"], item["source_line"]): item for item in albums
    }
    if old_by_location.keys() != new_by_location.keys():
        raise SystemExit(
            "Selection row locations changed; start a fresh manifest without --resume"
        )

    refreshed = []
    for source in albums:
        location = (source["source_file"], source["source_line"])
        existing = old_by_location[location]
        changed = any(existing.get(key) != source.get(key) for key in ALBUM_SOURCE_KEYS)
        if changed:
            existing = dict(source)
        else:
            existing.update(source)
        refreshed.append(existing)

    manifest["albums"] = refreshed
    manifest["selection_fingerprint"] = selection_fingerprint(albums)


def apply_album_overrides(manifest: dict) -> None:
    """Apply reviewed release-group IDs after revalidating their artist credit."""
    overrides = load_album_overrides()
    artists = {
        normalize(item["requested_artist"]): item
        for item in manifest["artists"]
        if item.get("status") == "accepted"
    }
    for album in manifest["albums"]:
        key = (normalize(album["requested_artist"]), normalize(album["requested_title"]))
        override = overrides.get(key)
        if not override:
            continue
        if (
            album.get("status") == "accepted"
            and album.get("release_group_mbid") == override["release_group_mbid"]
        ):
            continue

        artist = artists.get(key[0])
        if not artist:
            continue
        try:
            release_group = fetch_release_group(override["release_group_mbid"])
            credited_mbids = artist_ids(release_group)
            expected_mbids = set(
                override.get("artist_credit_mbids", [artist["artist_mbid"]])
            )
            if not expected_mbids.issubset(credited_mbids):
                raise ValueError(
                    "override release group does not contain every expected artist-credit MBID"
                )
            if release_group.get("id") != override["release_group_mbid"]:
                raise ValueError("MusicBrainz returned a different release-group MBID")

            summary = release_candidate_summary(
                release_group, album["requested_year"], album["requested_type"]
            )
            summary.pop("validation_reasons", None)
            reset_album_match(album)
            album.update(
                {
                    **summary,
                    "status": "accepted",
                    "match_method": "reviewed_release_group_mbid_override",
                    "match_reasons": [override["reason"]],
                }
            )
        except Exception as error:
            reset_album_match(album)
            album.update(
                {
                    "status": "error",
                    "match_method": "reviewed_release_group_mbid_override",
                    "match_reasons": [str(error)],
                }
            )
            manifest["album_errors"].append(
                {
                    "requested_artist": album["requested_artist"],
                    "requested_title": album["requested_title"],
                    "error": str(error),
                }
            )


def apply_artist_overrides(manifest: dict) -> set[str]:
    """Replace previously selected identities when a reviewed override exists."""
    overrides = load_artist_overrides()
    changed_names = set()
    for artist in manifest["artists"]:
        override = overrides.get(normalize(artist["requested_artist"]))
        if not override or artist.get("artist_mbid") == override["artist_mbid"]:
            continue
        requested_artist = artist["requested_artist"]
        artist.clear()
        artist.update(
            {
                "requested_artist": requested_artist,
                "status": "accepted",
                "artist_mbid": override["artist_mbid"],
                "name": override["name"],
                "score": None,
                "match_method": "reviewed_artist_mbid_override",
                "match_reasons": [override["reason"]],
            }
        )
        changed_names.add(requested_artist)

    if changed_names:
        for album in manifest["albums"]:
            if album["requested_artist"] in changed_names:
                reset_album_match(album)
        manifest["album_errors"] = [
            item
            for item in manifest["album_errors"]
            if item.get("requested_artist") not in changed_names
        ]
    return changed_names


def resolve_artists(manifest: dict, output: Path) -> None:
    requested_names = sorted(
        {album["requested_artist"] for album in manifest["albums"]},
        key=lambda value: value.casefold(),
    )
    existing = {item["requested_artist"]: item for item in manifest["artists"]}
    known = load_known_artists()
    overrides = load_artist_overrides()

    for number, name in enumerate(requested_names, start=1):
        if name in existing:
            continue
        print(f"[artist {number}/{len(requested_names)}] {name}", flush=True)
        override = overrides.get(normalize(name))
        cached = known.get(normalize(name))
        if override:
            result = {
                "requested_artist": name,
                "status": "accepted",
                "artist_mbid": override["artist_mbid"],
                "name": override["name"],
                "score": None,
                "match_method": "reviewed_artist_mbid_override",
                "match_reasons": [override["reason"]],
            }
        elif cached:
            result = {
                "requested_artist": name,
                "status": "accepted",
                "artist_mbid": cached["artist_mbid"],
                "name": cached["name"],
                "score": None,
                "match_method": "existing_confirmed_catalog_artist",
                "match_reasons": ["reused previously confirmed artist MBID"],
            }
        else:
            try:
                search_results = search_artist(name)
                result = {
                    "requested_artist": name,
                    **classify_artist_match(name, search_results),
                }
                if result["status"] != "accepted":
                    broad_results = broad_search_artist(name)
                    evidence_result = resolve_artist_by_album_evidence(
                        name,
                        [
                            album
                            for album in manifest["albums"]
                            if album["requested_artist"] == name
                        ],
                        search_results + broad_results,
                    )
                    if evidence_result:
                        result = evidence_result
            except Exception as error:
                result = {
                    "requested_artist": name,
                    "status": "error",
                    "match_reasons": [str(error)],
                }
                manifest["artist_errors"].append(
                    {"requested_artist": name, "error": str(error)}
                )
        manifest["artists"].append(result)
        save_manifest(output, manifest)


def resolve_albums(manifest: dict, output: Path) -> None:
    artist_matches = {
        item["requested_artist"]: item
        for item in manifest["artists"]
        if item.get("status") == "accepted"
    }
    albums_by_artist: dict[str, list[dict]] = {}
    for album in manifest["albums"]:
        if album.get("status"):
            continue
        albums_by_artist.setdefault(album["requested_artist"], []).append(album)

    names = sorted(albums_by_artist, key=str.casefold)
    for number, name in enumerate(names, start=1):
        albums = albums_by_artist[name]
        artist = artist_matches.get(name)
        if not artist:
            for album in albums:
                album["status"] = "needs_review"
                album["match_reasons"] = ["artist identity is not accepted"]
            save_manifest(output, manifest)
            continue

        print(f"[discography {number}/{len(names)}] {name}", flush=True)
        try:
            discography = fetch_artist_discography(artist["artist_mbid"])
            for album in albums:
                album.update(
                    classify_album_match(album, artist["artist_mbid"], discography)
                )
        except Exception as error:
            manifest["album_errors"].append(
                {"requested_artist": name, "error": str(error)}
            )
            for album in albums:
                album["status"] = "error"
                album["match_reasons"] = [str(error)]
        save_manifest(output, manifest)


def markdown_escape(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def write_report(path: Path, manifest: dict) -> None:
    summary = summarize(manifest)
    artist_counts = summary["artist_statuses"]
    album_counts = summary["album_statuses"]
    lines = [
        "# Album Matching Report",
        "",
        "Generated by `match_album_selection.py`. No SQLite writes are performed.",
        "",
        "## Coverage",
        "",
        f"- Artists: {summary['artist_count']}",
        f"- Artist accepted: {artist_counts['accepted']}",
        f"- Artist needs review: {artist_counts['needs_review']}",
        f"- Artist unmatched: {artist_counts['unmatched']}",
        f"- Artist errors: {artist_counts['error']}",
        f"- Albums: {summary['album_count']}",
        f"- Album accepted: {album_counts['accepted']}",
        f"- Album needs review: {album_counts['needs_review']}",
        f"- Album unmatched: {album_counts['unmatched']}",
        f"- Album errors: {album_counts['error']}",
        f"- Unique accepted release groups: {summary['accepted_unique_release_groups']}",
        f"- Duplicate accepted release groups: {summary['accepted_duplicate_release_groups']}",
        "",
        "## Artist exceptions",
        "",
        "| Requested artist | Status | Reason |",
        "| --- | --- | --- |",
    ]
    artist_exceptions = [
        item for item in manifest["artists"] if item.get("status") != "accepted"
    ]
    for item in artist_exceptions:
        lines.append(
            "| {} | {} | {} |".format(
                markdown_escape(item["requested_artist"]),
                markdown_escape(item.get("status", "pending")),
                markdown_escape("; ".join(item.get("match_reasons", []))),
            )
        )
    if not artist_exceptions:
        lines.append("| — | — | No artist exceptions |")

    lines.extend(
        [
            "",
            "## Album exceptions",
            "",
            "| Artist | Requested release | Year | Type | Status | Reason |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    album_exceptions = [
        item for item in manifest["albums"] if item.get("status") != "accepted"
    ]
    for item in album_exceptions:
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                markdown_escape(item["requested_artist"]),
                markdown_escape(item["requested_title"]),
                item["requested_year"],
                markdown_escape(item["requested_type"]),
                markdown_escape(item.get("status", "pending")),
                markdown_escape("; ".join(item.get("match_reasons", []))),
            )
        )
    if not album_exceptions:
        lines.append("| — | — | — | — | — | No album exceptions |")

    lines.extend(
        [
            "",
            "## Acceptance rule",
            "",
            "An album is accepted either when its title matches inside an accepted",
            "artist MBID's MusicBrainz discography and its artist credit, release",
            "type, and first-release year are compatible, or through an explicitly",
            "reviewed MBID override whose artist credit is revalidated against",
            "MusicBrainz. The script never guesses an MBID from title similarity alone.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--phase", choices=("artists", "albums", "all"), default="all")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--retry-unresolved",
        action="store_true",
        help="With --resume, rerun only non-accepted artist identities.",
    )
    parser.add_argument(
        "--retry-album-exceptions",
        action="store_true",
        help="With --resume, rerun non-accepted album matches.",
    )
    parser.add_argument(
        "--refresh-selection",
        action="store_true",
        help="With --resume, merge edited source rows while preserving unchanged matches.",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    albums = parse_selection_files(ROOT)
    fingerprint = selection_fingerprint(albums)

    if args.resume and args.output.exists():
        manifest = json.loads(args.output.read_text(encoding="utf-8"))
        if manifest.get("selection_fingerprint") != fingerprint:
            if not args.refresh_selection:
                raise SystemExit(
                    "Selection files changed; use --refresh-selection or start a fresh manifest"
                )
            refresh_manifest_selection(manifest, albums)
    else:
        manifest = new_manifest(albums)
        save_manifest(args.output, manifest)

    apply_artist_overrides(manifest)
    apply_album_overrides(manifest)
    save_manifest(args.output, manifest)

    if args.retry_unresolved:
        if not args.resume:
            raise SystemExit("--retry-unresolved requires --resume")
        unresolved_names = {
            item["requested_artist"]
            for item in manifest["artists"]
            if item.get("status") != "accepted"
        }
        manifest["artists"] = [
            item
            for item in manifest["artists"]
            if item.get("status") == "accepted"
        ]
        manifest["artist_errors"] = [
            item
            for item in manifest["artist_errors"]
            if item.get("requested_artist") not in unresolved_names
        ]
        for album in manifest["albums"]:
            if album["requested_artist"] in unresolved_names:
                reset_album_match(album)
        save_manifest(args.output, manifest)

    if args.retry_album_exceptions:
        if not args.resume:
            raise SystemExit("--retry-album-exceptions requires --resume")
        for album in manifest["albums"]:
            if album.get("status") != "accepted":
                reset_album_match(album)
        manifest["album_errors"] = []
        save_manifest(args.output, manifest)

    if args.phase in {"artists", "all"}:
        resolve_artists(manifest, args.output)
    if args.phase in {"albums", "all"}:
        resolve_albums(manifest, args.output)

    manifest["finished_at"] = now_iso()
    save_manifest(args.output, manifest)
    write_report(args.report, manifest)
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
