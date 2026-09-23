-- Minimal Day 2 data for relationship and constraint checks.

INSERT INTO artists (artist_mbid, name)
VALUES
    ('a74b1b7f-71a5-4011-9441-d0b5e4122711', 'Radiohead'),
    ('87c5dedd-371d-4a53-9f7f-80522fb7f3cb', 'Björk');

INSERT INTO albums (release_group_mbid, title, release_year, cover_url)
VALUES
    (
        'b1392450-e666-3926-a536-22c65f834433',
        'OK Computer',
        1997,
        'https://coverartarchive.org/release/30702389-5c67-4438-9ea0-2351c8de0f1d/43287476628.png'
    ),
    (
        '810272e0-aef1-3d85-b2d3-e512e87fc38c',
        'Homogenic',
        1997,
        'https://coverartarchive.org/release/9eb06b8b-73af-4e4f-815c-1a0e459af1c4/42643046619.png'
    );

INSERT INTO album_artists (release_group_mbid, artist_mbid, credit_order)
VALUES
    ('b1392450-e666-3926-a536-22c65f834433', 'a74b1b7f-71a5-4011-9441-d0b5e4122711', 1),
    ('810272e0-aef1-3d85-b2d3-e512e87fc38c', '87c5dedd-371d-4a53-9f7f-80522fb7f3cb', 1);

INSERT INTO album_tags (
    release_group_mbid,
    raw_tag,
    normalized_tag,
    tag_rank,
    source
)
VALUES
    ('b1392450-e666-3926-a536-22c65f834433', 'alternative rock', 'alternative rock', 1, 'lastfm'),
    ('b1392450-e666-3926-a536-22c65f834433', 'art rock', 'art rock', 6, 'lastfm'),
    ('b1392450-e666-3926-a536-22c65f834433', 'electronic', 'electronic', 10, 'lastfm'),
    ('810272e0-aef1-3d85-b2d3-e512e87fc38c', 'electronic', 'electronic', 1, 'lastfm'),
    ('810272e0-aef1-3d85-b2d3-e512e87fc38c', 'trip-hop', 'trip-hop', 9, 'lastfm'),
    ('810272e0-aef1-3d85-b2d3-e512e87fc38c', 'trip hop', 'trip-hop', 10, 'lastfm');

