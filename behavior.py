"""Small SQLite helpers for anonymous recommendation behavior data."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).parent
SCHEMA_PATH = ROOT / "schema.sql"
VALID_TIERS = {"Safe", "Explore", "Wildcard"}
VALID_BATTLE_STRATEGIES = {
    "safe_vs_explore",
    "explore_vs_wildcard",
    "similarity_vs_tag_overlap",
}
SCHEMA_REVISION = 3


def normalize_behavior_storage_mode(value: str | None) -> str:
    """Validate whether behavior events should persist or stay in one session."""
    mode = (value or "persistent").strip().lower()
    if mode not in {"persistent", "session", "supabase"}:
        raise ValueError(
            "AI_TASTE_BEHAVIOR_STORAGE must be 'persistent', 'session', or 'supabase'"
        )
    return mode


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path) -> None:
    """Apply idempotent schema.sql to both new and existing databases."""
    connection = connect(database_path)
    try:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        review_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(reviews)")
        }
        if "reviewer_name" not in review_columns:
            connection.execute("ALTER TABLE reviews ADD COLUMN reviewer_name TEXT")
        if "license_url" not in review_columns:
            connection.execute("ALTER TABLE reviews ADD COLUMN license_url TEXT")
    finally:
        connection.close()


def create_session(database_path: Path, session_id: str) -> None:
    connection = connect(database_path)
    try:
        with connection:
            connection.execute(
                "INSERT OR IGNORE INTO sessions (session_id, created_at) VALUES (?, ?)",
                (session_id, utc_now()),
            )
    finally:
        connection.close()


def record_taste_profile_event(
    database_path: Path, session_id: str, seed_album_mbids: list[str]
) -> int:
    if not 1 <= len(seed_album_mbids) <= 10:
        raise ValueError("A taste profile event must have 1 to 10 seed albums")
    if len(seed_album_mbids) != len(set(seed_album_mbids)):
        raise ValueError("Seed album MBIDs must be unique")

    connection = connect(database_path)
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO taste_profile_events
                    (session_id, generated_at)
                VALUES (?, ?)
                """,
                (session_id, utc_now()),
            )
            profile_event_id = int(cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO taste_profile_event_albums
                    (profile_event_id, release_group_mbid, seed_order)
                VALUES (?, ?, ?)
                """,
                [
                    (profile_event_id, mbid, order)
                    for order, mbid in enumerate(seed_album_mbids, start=1)
                ],
            )
            return profile_event_id
    finally:
        connection.close()


def record_recommendation_impressions(
    database_path: Path,
    session_id: str,
    profile_event_id: int,
    tier: str,
    recommendations: list[dict],
) -> None:
    if tier not in VALID_TIERS:
        raise ValueError(f"Unknown recommendation tier: {tier}")
    timestamp = utc_now()
    rows = []
    for rank, recommendation in enumerate(recommendations, start=1):
        rows.append(
            (
                session_id,
                profile_event_id,
                recommendation["release_group_mbid"],
                tier,
                rank,
                recommendation.get("profile_similarity"),
                recommendation.get("bridge_similarity"),
                recommendation.get("safe_score"),
                recommendation.get("explore_score"),
                recommendation.get("wildcard_score"),
                recommendation.get("novelty_ratio"),
                timestamp,
            )
        )

    connection = connect(database_path)
    try:
        with connection:
            connection.executemany(
                """
                INSERT INTO recommendation_impressions
                    (session_id, profile_event_id, release_group_mbid, tier,
                     rank, profile_similarity, bridge_similarity, safe_score,
                     explore_score, wildcard_score, novelty_ratio, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
    finally:
        connection.close()


def record_feedback(
    database_path: Path,
    session_id: str,
    release_group_mbid: str,
    tier: str,
    feedback: str,
) -> None:
    if tier not in VALID_TIERS:
        raise ValueError(f"Unknown recommendation tier: {tier}")
    if feedback not in {"like", "dislike"}:
        raise ValueError("Feedback must be 'like' or 'dislike'")

    connection = connect(database_path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO recommendation_feedback
                    (session_id, release_group_mbid, tier, feedback, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (session_id, release_group_mbid) DO UPDATE SET
                    tier = excluded.tier,
                    feedback = excluded.feedback,
                    created_at = excluded.created_at
                """,
                (session_id, release_group_mbid, tier, feedback, utc_now()),
            )
    finally:
        connection.close()


def load_seen_battle_pairs(
    database_path: Path, profile_event_id: int
) -> tuple[set[tuple[str, str]], int]:
    connection = connect(database_path)
    try:
        rows = connection.execute(
            """
            SELECT album_a_mbid, album_b_mbid
            FROM taste_battles
            WHERE profile_event_id = ?
            """,
            (profile_event_id,),
        ).fetchall()
        seen = {tuple(sorted((album_a, album_b))) for album_a, album_b in rows}
        return seen, len(rows)
    finally:
        connection.close()


def load_battle_choices(
    database_path: Path, profile_event_id: int, generation_strategy: str
) -> dict[tuple[str, str], str]:
    """Load the latest choice for each unordered pair in one battle strategy."""
    connection = connect(database_path)
    try:
        rows = connection.execute(
            """
            SELECT album_a_mbid, album_b_mbid, chosen_album_mbid
            FROM taste_battles
            WHERE profile_event_id = ? AND generation_strategy = ?
            ORDER BY created_at, battle_id
            """,
            (profile_event_id, generation_strategy),
        ).fetchall()
        return {
            tuple(sorted((album_a, album_b))): chosen
            for album_a, album_b, chosen in rows
        }
    finally:
        connection.close()


def load_session_battle_pairs(
    choices: list[dict],
) -> tuple[set[tuple[str, str]], int]:
    """Summarize Taste Battle choices held only in the current app session."""
    seen = {
        tuple(sorted((choice["album_a_mbid"], choice["album_b_mbid"])))
        for choice in choices
    }
    return seen, len(choices)


def record_battle_choice(
    database_path: Path,
    session_id: str,
    profile_event_id: int,
    album_a_mbid: str,
    album_b_mbid: str,
    chosen_album_mbid: str,
    generation_strategy: str,
) -> None:
    if album_a_mbid == album_b_mbid:
        raise ValueError("A Taste Battle must compare two different albums")
    if chosen_album_mbid not in {album_a_mbid, album_b_mbid}:
        raise ValueError("The selected album must be A or B")
    if generation_strategy not in VALID_BATTLE_STRATEGIES:
        raise ValueError(f"Unknown Taste Battle strategy: {generation_strategy}")

    connection = connect(database_path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO taste_battles
                    (session_id, profile_event_id, album_a_mbid, album_b_mbid,
                     chosen_album_mbid, generation_strategy, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    profile_event_id,
                    album_a_mbid,
                    album_b_mbid,
                    chosen_album_mbid,
                    generation_strategy,
                    utc_now(),
                ),
            )
    finally:
        connection.close()
