-- SQLite checks foreign-key relationships only when enabled per connection.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS artists (
    artist_mbid TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS albums (
    release_group_mbid TEXT PRIMARY KEY NOT NULL,
    title TEXT NOT NULL,
    release_year INTEGER,
    cover_url TEXT
);

CREATE TABLE IF NOT EXISTS album_artists (
    release_group_mbid TEXT NOT NULL,
    artist_mbid TEXT NOT NULL,
    credit_order INTEGER NOT NULL CHECK (credit_order >= 1),

    PRIMARY KEY (release_group_mbid, artist_mbid),

    FOREIGN KEY (release_group_mbid)
        REFERENCES albums (release_group_mbid),

    FOREIGN KEY (artist_mbid)
        REFERENCES artists (artist_mbid)
);

CREATE TABLE IF NOT EXISTS album_tags (
    release_group_mbid TEXT NOT NULL,
    raw_tag TEXT NOT NULL,
    normalized_tag TEXT NOT NULL,
    tag_rank INTEGER NOT NULL CHECK (tag_rank >= 1),
    source TEXT NOT NULL,

    PRIMARY KEY (release_group_mbid, source, raw_tag),

    FOREIGN KEY (release_group_mbid)
        REFERENCES albums (release_group_mbid)
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY NOT NULL,
    release_group_mbid TEXT NOT NULL,
    language TEXT NOT NULL,
    source TEXT,
    source_url TEXT,
    reviewer_name TEXT,
    license TEXT NOT NULL,
    license_url TEXT,
    review_text TEXT NOT NULL
        CHECK (length(trim(review_text)) > 0),

    FOREIGN KEY (release_group_mbid)
        REFERENCES albums (release_group_mbid)
);

-- Anonymous product behavior for V2. No account or personal profile is stored.
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS taste_profile_events (
    profile_event_id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    generated_at TEXT NOT NULL,

    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
);

CREATE TABLE IF NOT EXISTS taste_profile_event_albums (
    profile_event_id INTEGER NOT NULL,
    release_group_mbid TEXT NOT NULL,
    seed_order INTEGER NOT NULL CHECK (seed_order >= 1),

    PRIMARY KEY (profile_event_id, release_group_mbid),
    UNIQUE (profile_event_id, seed_order),
    FOREIGN KEY (profile_event_id)
        REFERENCES taste_profile_events (profile_event_id),
    FOREIGN KEY (release_group_mbid)
        REFERENCES albums (release_group_mbid)
);

CREATE TABLE IF NOT EXISTS recommendation_impressions (
    impression_id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    profile_event_id INTEGER NOT NULL,
    release_group_mbid TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('Safe', 'Explore', 'Wildcard')),
    rank INTEGER NOT NULL CHECK (rank >= 1),
    profile_similarity REAL,
    bridge_similarity REAL,
    safe_score REAL,
    explore_score REAL,
    wildcard_score REAL,
    novelty_ratio REAL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
    FOREIGN KEY (profile_event_id) REFERENCES taste_profile_events (profile_event_id),
    FOREIGN KEY (release_group_mbid) REFERENCES albums (release_group_mbid)
);

CREATE TABLE IF NOT EXISTS recommendation_feedback (
    feedback_id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    release_group_mbid TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('Safe', 'Explore', 'Wildcard')),
    feedback TEXT NOT NULL CHECK (feedback IN ('like', 'dislike')),
    created_at TEXT NOT NULL,

    UNIQUE (session_id, release_group_mbid),
    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
    FOREIGN KEY (release_group_mbid) REFERENCES albums (release_group_mbid)
);

CREATE TABLE IF NOT EXISTS taste_battles (
    battle_id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    profile_event_id INTEGER NOT NULL,
    album_a_mbid TEXT NOT NULL,
    album_b_mbid TEXT NOT NULL,
    chosen_album_mbid TEXT NOT NULL,
    generation_strategy TEXT NOT NULL CHECK (
        generation_strategy IN (
            'safe_vs_explore',
            'explore_vs_wildcard',
            'similarity_vs_tag_overlap'
        )
    ),
    created_at TEXT NOT NULL,

    CHECK (album_a_mbid <> album_b_mbid),
    CHECK (chosen_album_mbid = album_a_mbid OR chosen_album_mbid = album_b_mbid),
    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
    FOREIGN KEY (profile_event_id) REFERENCES taste_profile_events (profile_event_id),
    FOREIGN KEY (album_a_mbid) REFERENCES albums (release_group_mbid),
    FOREIGN KEY (album_b_mbid) REFERENCES albums (release_group_mbid),
    FOREIGN KEY (chosen_album_mbid) REFERENCES albums (release_group_mbid)
);

CREATE INDEX IF NOT EXISTS idx_profile_events_session_time
    ON taste_profile_events (session_id, generated_at);
CREATE INDEX IF NOT EXISTS idx_profile_event_albums_album
    ON taste_profile_event_albums (release_group_mbid);
CREATE INDEX IF NOT EXISTS idx_impressions_session_time
    ON recommendation_impressions (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_impressions_album
    ON recommendation_impressions (release_group_mbid);
CREATE INDEX IF NOT EXISTS idx_feedback_album
    ON recommendation_feedback (release_group_mbid);
CREATE INDEX IF NOT EXISTS idx_taste_battles_profile_event
    ON taste_battles (profile_event_id, created_at);
