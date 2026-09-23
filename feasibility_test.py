"""Day 1 only: measure album-data coverage across four public services."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).parent
ALBUMS_PATH = ROOT / "test_albums.json"
JSON_OUTPUT = ROOT / "feasibility_results.json"
MARKDOWN_OUTPUT = ROOT / "FEASIBILITY.md"

# MusicBrainz asks clients to identify themselves and stay at or below 1 req/s.
USER_AGENT = "AI-Taste-Discovery/0.1 (educational Day-1 feasibility test)"
MUSICBRAINZ_DELAY_SECONDS = 1.1
MIN_USEFUL_TAGS = 5


def get_json(base_url: str, params: dict | None = None, retries: int = 2) -> dict:
    """GET JSON with a small retry for temporary API failures."""
    url = base_url
    if params:
        url += "?" + urlencode(params)

    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == retries:
                raise
        except URLError:
            if attempt == retries:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def artist_credit_text(release_group: dict) -> str:
    return "".join(
        part.get("name", "") + part.get("joinphrase", "")
        for part in release_group.get("artist-credit", [])
    )


def artist_mbids(release_group: dict) -> list[str]:
    """Keep every credited artist ID; collaborations can have more than one."""
    return [
        part["artist"]["id"]
        for part in release_group.get("artist-credit", [])
        if part.get("artist", {}).get("id")
    ]


def find_release_group(artist: str, album: str) -> dict | None:
    # Fielded search reduces collisions between albums with the same title.
    query = f'releasegroup:"{album}" AND artist:"{artist}" AND primarytype:album'
    data = get_json(
        "https://musicbrainz.org/ws/2/release-group/",
        {"query": query, "fmt": "json", "limit": 5},
    )
    time.sleep(MUSICBRAINZ_DELAY_SECONDS)
    groups = data.get("release-groups", [])
    if not groups:
        return None

    match = groups[0]
    return {
        "mbid": match["id"],
        "title": match.get("title"),
        "artist": artist_credit_text(match),
        "artist_mbids": artist_mbids(match),
        "year": (match.get("first-release-date") or "")[:4] or None,
        "score": int(match.get("score", 0)),
    }


def check_cover(release_group_mbid: str) -> dict:
    try:
        data = get_json(
            f"https://coverartarchive.org/release-group/{release_group_mbid}"
        )
        front = next((image for image in data.get("images", []) if image.get("front")), None)
        return {
            "status": "found" if front else "missing",
            "url": front.get("image") if front else None,
        }
    except HTTPError as error:
        if error.code == 404:
            return {"status": "missing", "url": None}
        return {"status": "error", "error": f"HTTP {error.code}"}
    except (URLError, TimeoutError) as error:
        return {"status": "error", "error": str(error)}


def check_lastfm(artist: str, album: str, api_key: str | None) -> dict:
    if not api_key:
        return {"status": "not_tested", "reason": "LASTFM_API_KEY is not set"}
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
            return {"status": "error", "error": data.get("message", "Last.fm error")}
        tags = data.get("toptags", {}).get("tag", [])
        names = [tag["name"] for tag in tags if tag.get("name")]
        return {
            "status": "enough" if len(names) >= MIN_USEFUL_TAGS else "sparse",
            "count": len(names),
            "tags": names,
        }
    except (HTTPError, URLError, TimeoutError) as error:
        return {"status": "error", "error": str(error)}


def check_reviews(release_group_mbid: str) -> dict:
    try:
        data = get_json(
            "https://critiquebrainz.org/ws/1/review/",
            {
                "entity_id": release_group_mbid,
                "entity_type": "release_group",
                "review_type": "review",
                "limit": 50,
            },
        )
        reviews = data.get("reviews", [])
        text_reviews = [review for review in reviews if review.get("text")]
        return {
            "status": "found" if text_reviews else "missing",
            "count": len(text_reviews),
            "reviews": [
                {
                    "id": review.get("id"),
                    "language": review.get("language"),
                    "source": review.get("source"),
                    "source_url": review.get("source_url"),
                    "license": (review.get("license") or {}).get("id"),
                    "text_length": len(review.get("text", "")),
                }
                for review in text_reviews
            ],
        }
    except (HTTPError, URLError, TimeoutError) as error:
        return {"status": "error", "error": str(error)}


def test_album(item: dict, lastfm_api_key: str | None) -> dict:
    requested_artist = item["artist"]
    requested_album = item["album"]
    result = {"requested_artist": requested_artist, "requested_album": requested_album}

    try:
        musicbrainz = find_release_group(requested_artist, requested_album)
    except (HTTPError, URLError, TimeoutError) as error:
        result["musicbrainz"] = {"status": "error", "error": str(error)}
        return result

    if not musicbrainz:
        result["musicbrainz"] = {"status": "missing"}
        return result

    result["musicbrainz"] = {"status": "found", **musicbrainz}
    result["cover_art_archive"] = check_cover(musicbrainz["mbid"])
    result["lastfm"] = check_lastfm(requested_artist, requested_album, lastfm_api_key)
    result["critiquebrainz"] = check_reviews(musicbrainz["mbid"])
    return result


def cell_status(result: dict, source: str) -> str:
    value = result.get(source, {})
    status = value.get("status", "not_tested")
    if source == "musicbrainz" and status == "found":
        return f'✓ {value.get("year") or "year?"} (score {value.get("score")})'
    if source == "cover_art_archive":
        return "✓" if status == "found" else ("✗" if status == "missing" else status)
    if source == "lastfm" and status in {"enough", "sparse"}:
        return f'{value.get("count", 0)} tags'
    if source == "critiquebrainz" and status in {"found", "missing"}:
        return str(value.get("count", 0))
    return status


def build_markdown(results: list[dict], lastfm_was_tested: bool) -> str:
    lines = [
        "# Day 1 Data Feasibility",
        "",
        "Generated by `feasibility_test.py`. Verify any MusicBrainz match with a low",
        "score or unexpected title/artist/year before using its MBID downstream.",
        "",
        "| Requested album | MusicBrainz | Cover | Last.fm tags | CritiqueBrainz reviews |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for result in results:
        label = f'{result["requested_artist"]} — {result["requested_album"]}'
        cells = [cell_status(result, source) for source in (
            "musicbrainz", "cover_art_archive", "lastfm", "critiquebrainz"
        )]
        lines.append(f'| {label} | {" | ".join(cells)} |')

    lines += [
        "",
        "## MusicBrainz identity check",
        "",
        "| Requested album | Matched artist / album | Release-group MBID | Artist MBID(s) | Year | Score |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for result in results:
        musicbrainz = result.get("musicbrainz", {})
        requested = f'{result["requested_artist"]} — {result["requested_album"]}'
        if musicbrainz.get("status") != "found":
            lines.append(f"| {requested} | not found | — | — | — | — |")
            continue
        matched = f'{musicbrainz.get("artist")} — {musicbrainz.get("title")}'
        artists = ", ".join(musicbrainz.get("artist_mbids", [])) or "—"
        lines.append(
            f'| {requested} | {matched} | {musicbrainz.get("mbid")} | {artists} | '
            f'{musicbrainz.get("year") or "—"} | {musicbrainz.get("score")} |'
        )

    mb_found = sum(r.get("musicbrainz", {}).get("status") == "found" for r in results)
    covers = sum(r.get("cover_art_archive", {}).get("status") == "found" for r in results)
    reviews = sum(r.get("critiquebrainz", {}).get("count", 0) > 0 for r in results)
    lines += [
        "",
        "## Coverage summary",
        "",
        f"- MusicBrainz matches: {mb_found}/{len(results)}",
        f"- Release-group covers: {covers}/{len(results)}",
        f"- Albums with at least one text review: {reviews}/{len(results)}",
        f'- Last.fm tags: {"tested" if lastfm_was_tested else "not tested (LASTFM_API_KEY missing)"}',
        "",
        "## Initial limitations and fallback questions",
        "",
        "- MusicBrainz search is not identity resolution. Low-score or surprising matches",
        "  need manual confirmation before their release-group MBIDs become seed data.",
        "- A release-group cover is convenient and edition-independent, but it is",
        "  community-curated and can be absent. A later pipeline may fall back to a",
        "  specific release cover, then to a placeholder.",
        "- Last.fm tags require an API key and can be noisy, duplicated in meaning, or",
        "  sparse for less popular/non-English releases. Artist-level tags are a possible",
        "  fallback, but must be labelled separately from album-level evidence.",
        "- CritiqueBrainz reviews are expected to be the sparsest field. Missing reviews",
        "  must not be silently replaced with LLM-written facts; V0.1 may need clearly",
        "  attributed fallback text sources or explanations based only on tags/metadata.",
        "- Review language and license vary. Preserve source URL, language, and license",
        "  alongside text before using reviews in RAG.",
        "",
        "## Fields that look suitable as stable identifiers",
        "",
        "- MusicBrainz release-group MBID: canonical album-level join key",
        "- MusicBrainz artist MBID (to add during the ingestion phase): artist join key",
        "- CritiqueBrainz review ID: review identity",
        "",
        "Titles, artist display names, tags, cover URLs, and review counts should be",
        "treated as mutable descriptive data, not identifiers.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    # Avoid Windows' legacy console encoding breaking names such as Björk.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    albums = json.loads(ALBUMS_PATH.read_text(encoding="utf-8"))
    lastfm_api_key = os.getenv("LASTFM_API_KEY")
    results = []

    for index, album in enumerate(albums, start=1):
        print(f'[{index}/{len(albums)}] {album["artist"]} — {album["album"]}')
        results.append(test_album(album, lastfm_api_key))

    JSON_OUTPUT.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    MARKDOWN_OUTPUT.write_text(
        build_markdown(results, lastfm_api_key is not None), encoding="utf-8"
    )
    print(f"Wrote {JSON_OUTPUT.name} and {MARKDOWN_OUTPUT.name}")


if __name__ == "__main__":
    main()
