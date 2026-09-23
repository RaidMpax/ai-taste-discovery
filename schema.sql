-- SQLite checks foreign-key relationships only when enabled per connection.
PRAGMA foreign_keys = ON;

CREATE TABLE artists (
    artist_mbid TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE albums (
    release_group_mbid TEXT PRIMARY KEY NOT NULL,
    title TEXT NOT NULL,
    release_year INTEGER,
    cover_url TEXT
);

CREATE TABLE album_artists (
    release_group_mbid TEXT NOT NULL,
    artist_mbid TEXT NOT NULL,
    credit_order INTEGER NOT NULL CHECK (credit_order >= 1),

    PRIMARY KEY (release_group_mbid, artist_mbid),

    FOREIGN KEY (release_group_mbid)
        REFERENCES albums (release_group_mbid),

    FOREIGN KEY (artist_mbid)
        REFERENCES artists (artist_mbid)
);

CREATE TABLE album_tags (
    release_group_mbid TEXT NOT NULL,
    raw_tag TEXT NOT NULL,
    normalized_tag TEXT NOT NULL,
    tag_rank INTEGER NOT NULL CHECK (tag_rank >= 1),
    source TEXT NOT NULL,

    PRIMARY KEY (release_group_mbid, source, raw_tag),

    FOREIGN KEY (release_group_mbid)
        REFERENCES albums (release_group_mbid)
);

CREATE TABLE reviews (
    review_id TEXT PRIMARY KEY NOT NULL,
    release_group_mbid TEXT NOT NULL,
    language TEXT NOT NULL,
    source TEXT,
    source_url TEXT,
    license TEXT NOT NULL,
    review_text TEXT NOT NULL
        CHECK (length(trim(review_text)) > 0),

    FOREIGN KEY (release_group_mbid)
        REFERENCES albums (release_group_mbid)
);
