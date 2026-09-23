-- These checks are read-only. Run them after opening taste.db.
PRAGMA foreign_keys = ON;

-- Confirm that albums are connected to their credited artists.
SELECT
    ar.name AS artist,
    al.title AS album,
    al.release_year,
    aa.credit_order
FROM album_artists AS aa
JOIN artists AS ar
    ON ar.artist_mbid = aa.artist_mbid
JOIN albums AS al
    ON al.release_group_mbid = aa.release_group_mbid
ORDER BY al.title, aa.credit_order;

-- Compare source tags with their normalized form.
SELECT
    al.title AS album,
    at.tag_rank,
    at.raw_tag,
    at.normalized_tag
FROM album_tags AS at
JOIN albums AS al
    ON al.release_group_mbid = at.release_group_mbid
ORDER BY al.title, at.tag_rank;

-- Find normalized tags that combine multiple raw spellings.
SELECT
    normalized_tag,
    COUNT(DISTINCT raw_tag) AS raw_variant_count
FROM album_tags
GROUP BY normalized_tag
HAVING COUNT(DISTINCT raw_tag) > 1
ORDER BY raw_variant_count DESC, normalized_tag;

-- Review coverage per album, including albums with zero reviews.
SELECT
    al.title AS album,
    COUNT(r.review_id) AS review_count
FROM albums AS al
LEFT JOIN reviews AS r
    ON r.release_group_mbid = al.release_group_mbid
GROUP BY al.release_group_mbid, al.title
ORDER BY al.title;

-- An empty result means there are no broken foreign-key relationships.
PRAGMA foreign_key_check;
