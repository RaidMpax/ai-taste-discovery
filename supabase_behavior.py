"""Small server-side PostgREST writer for anonymous behavior events."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID, uuid4


VALID_TIERS = {"Safe", "Explore", "Wildcard"}
VALID_BATTLE_STRATEGIES = {
    "safe_vs_explore",
    "explore_vs_wildcard",
    "similarity_vs_tag_overlap",
}
DEFAULT_TIMEOUT_SECONDS = 8


class SupabaseBehaviorError(RuntimeError):
    """Safe-to-display error without request bodies or credentials."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _require_uuid(value: str, field_name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"{field_name} must be a UUID") from error


def _number_or_none(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


class SupabaseBehaviorStore:
    """Write behavior rows through Supabase REST from the Streamlit server."""

    def __init__(
        self,
        project_url: str,
        secret_key: str,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        project_url = project_url.strip().rstrip("/")
        if not project_url.startswith("https://"):
            raise ValueError("SUPABASE_URL must use HTTPS")
        if not secret_key.strip():
            raise ValueError("SUPABASE_SECRET_KEY is missing")
        self._rest_url = f"{project_url}/rest/v1"
        self._secret_key = secret_key.strip()
        self._timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        table: str,
        payload: dict | list[dict] | None = None,
        query: dict[str, str] | None = None,
        prefer: str | None = None,
    ) -> list[dict] | None:
        url = f"{self._rest_url}/{table}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {
            "apikey": self._secret_key,
            "Accept": "application/json",
        }
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(
                "utf-8"
            )
        if prefer:
            headers["Prefer"] = prefer

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                response_body = response.read()
        except HTTPError as error:
            raise SupabaseBehaviorError(
                f"Supabase returned HTTP {error.code} for behavior storage.",
                status_code=error.code,
            ) from None
        except (URLError, TimeoutError, OSError):
            raise SupabaseBehaviorError(
                "Could not reach Supabase behavior storage."
            ) from None

        if not response_body:
            return None
        try:
            result = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SupabaseBehaviorError(
                "Supabase returned an unreadable response."
            ) from None
        return result if isinstance(result, list) else None

    def create_session(
        self,
        session_id: str,
        consent_version: str = "beta-2026-10-01",
    ) -> None:
        session_id = _require_uuid(session_id, "session_id")
        try:
            # Keep this as a plain insert.  ON CONFLICT DO NOTHING also needs
            # SELECT privilege on the conflict key, which is unnecessary for
            # this write-only analytics role.
            self._request(
                "POST",
                "sessions",
                {
                    "session_id": session_id,
                    "consent_version": consent_version,
                    "app_version": "v2-beta",
                },
                prefer="return=minimal",
            )
        except SupabaseBehaviorError as error:
            # A Streamlit rerun can submit the same session twice.  The
            # primary-key conflict means the session already exists, so it is
            # safe to treat that specific response as success.
            if error.status_code != 409:
                raise

    def record_taste_profile_event(
        self,
        session_id: str,
        seed_album_mbids: list[str],
        algorithm_version: str = "v2-beta",
    ) -> str:
        session_id = _require_uuid(session_id, "session_id")
        if not 1 <= len(seed_album_mbids) <= 10:
            raise ValueError("A taste profile event must have 1 to 10 seed albums")
        if len(seed_album_mbids) != len(set(seed_album_mbids)):
            raise ValueError("Seed album MBIDs must be unique")

        profile_event_id = str(uuid4())
        self._request(
            "POST",
            "taste_profile_events",
            {
                "profile_event_id": profile_event_id,
                "session_id": session_id,
                "seed_album_mbids": seed_album_mbids,
                "algorithm_version": algorithm_version,
            },
            prefer="return=minimal",
        )
        return profile_event_id

    def record_recommendation_impressions(
        self,
        session_id: str,
        profile_event_id: str,
        tier: str,
        recommendations: list[dict],
    ) -> None:
        session_id = _require_uuid(session_id, "session_id")
        profile_event_id = _require_uuid(profile_event_id, "profile_event_id")
        if tier not in VALID_TIERS:
            raise ValueError(f"Unknown recommendation tier: {tier}")
        if not recommendations:
            return

        rows = []
        for rank, recommendation in enumerate(recommendations, start=1):
            rows.append(
                {
                    "impression_id": str(uuid4()),
                    "session_id": session_id,
                    "profile_event_id": profile_event_id,
                    "release_group_mbid": recommendation["release_group_mbid"],
                    "tier": tier,
                    "rank": rank,
                    "profile_similarity": _number_or_none(
                        recommendation.get("profile_similarity")
                    ),
                    "bridge_similarity": _number_or_none(
                        recommendation.get("bridge_similarity")
                    ),
                    "safe_score": _number_or_none(recommendation.get("safe_score")),
                    "explore_score": _number_or_none(
                        recommendation.get("explore_score")
                    ),
                    "wildcard_score": _number_or_none(
                        recommendation.get("wildcard_score")
                    ),
                    "novelty_ratio": _number_or_none(
                        recommendation.get("novelty_ratio")
                    ),
                }
            )
        self._request(
            "POST",
            "recommendation_impressions",
            rows,
            prefer="return=minimal",
        )

    def record_feedback(
        self,
        session_id: str,
        profile_event_id: str,
        release_group_mbid: str,
        tier: str,
        feedback: str,
    ) -> None:
        session_id = _require_uuid(session_id, "session_id")
        profile_event_id = _require_uuid(profile_event_id, "profile_event_id")
        if tier not in VALID_TIERS:
            raise ValueError(f"Unknown recommendation tier: {tier}")
        if feedback not in {"like", "dislike"}:
            raise ValueError("Feedback must be 'like' or 'dislike'")
        self._request(
            "POST",
            "recommendation_feedback_events",
            {
                "feedback_event_id": str(uuid4()),
                "session_id": session_id,
                "profile_event_id": profile_event_id,
                "release_group_mbid": release_group_mbid,
                "tier": tier,
                "feedback": feedback,
            },
            prefer="return=minimal",
        )

    def load_battle_choices(
        self, profile_event_id: str, generation_strategy: str
    ) -> dict[tuple[str, str], str]:
        profile_event_id = _require_uuid(profile_event_id, "profile_event_id")
        if generation_strategy not in VALID_BATTLE_STRATEGIES:
            raise ValueError(f"Unknown Taste Battle strategy: {generation_strategy}")
        rows = self._request(
            "GET",
            "taste_battle_events",
            query={
                "select": "album_a_mbid,album_b_mbid,chosen_album_mbid",
                "profile_event_id": f"eq.{profile_event_id}",
                "generation_strategy": f"eq.{generation_strategy}",
                "order": "created_at.asc",
            },
        ) or []
        return {
            tuple(sorted((row["album_a_mbid"], row["album_b_mbid"]))):
            row["chosen_album_mbid"]
            for row in rows
        }

    def record_battle_choice(
        self,
        session_id: str,
        profile_event_id: str,
        album_a_mbid: str,
        album_b_mbid: str,
        chosen_album_mbid: str,
        generation_strategy: str,
    ) -> None:
        session_id = _require_uuid(session_id, "session_id")
        profile_event_id = _require_uuid(profile_event_id, "profile_event_id")
        if album_a_mbid == album_b_mbid:
            raise ValueError("A Taste Battle must compare two different albums")
        if chosen_album_mbid not in {album_a_mbid, album_b_mbid}:
            raise ValueError("The selected album must be A or B")
        if generation_strategy not in VALID_BATTLE_STRATEGIES:
            raise ValueError(f"Unknown Taste Battle strategy: {generation_strategy}")
        self._request(
            "POST",
            "taste_battle_events",
            {
                "battle_event_id": str(uuid4()),
                "session_id": session_id,
                "profile_event_id": profile_event_id,
                "album_a_mbid": album_a_mbid,
                "album_b_mbid": album_b_mbid,
                "chosen_album_mbid": chosen_album_mbid,
                "generation_strategy": generation_strategy,
            },
            prefer="return=minimal",
        )
