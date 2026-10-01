# Data Model

## Scope

This schema stores the small music catalogue needed by V0.1. An album means a
MusicBrainz **release group**, not a specific regional, physical, or digital
release.

## Relationships

```text
artists
   |
   | many-to-many through album_artists
   |
albums ----< album_tags
   |
   +--------< reviews
```

- `artists` and `albums` use MusicBrainz IDs as their primary keys.
- `album_artists` supports collaborations and preserves artist-credit order.
- `album_tags` preserves source text, normalized text, rank, and provider
  provenance. MusicBrainz is the active/default tag source; Last.fm rows remain
  separately stored as candidate data.
- `reviews` stores optional CritiqueBrainz text and its attribution metadata.
- One release-group cover URL is stored directly on `albums` for V0.1.
- V2 behavior tables store anonymous sessions, selected seed IDs, visible recommendation impressions, and like/dislike feedback.

## Important decisions

- Missing release years and covers do not prevent an album from being stored.
- Artist and album names are descriptive data; MBIDs are identifiers.
- Tag rank and artist-credit order start at 1.
- MusicBrainz tag/genre names are deduplicated by normalized value and ranked by
  the provider's available count. The current schema stores that rank, not the
  provider count itself; migration counts are kept in the local ignored cache.
- Review source name and source URL may be absent, but language, license, and
  non-blank text are required. Reviewer display name and license URL are stored
  when CritiqueBrainz provides them; both may be absent in older rows.
- SQLite foreign-key enforcement must be enabled for every connection with
  `PRAGMA foreign_keys = ON`.

## Known limitations

- Tag normalization currently has no finalized rule set. The sample only shows
  that raw variants such as `trip-hop` and `trip hop` can map to one value.
- The schema stores one representative cover rather than edition-level covers.
- CritiqueBrainz review coverage is incomplete, so albums may have no reviews.
- There are no accounts or personal identifying fields. A random session ID
  connects behavior events during a Streamlit session.
- Embeddings remain in memory; they are not stored in SQLite.
- Schema creation uses `CREATE TABLE IF NOT EXISTS`. A small additive migration
  adds reviewer and license-link columns to existing review tables; this is not
  a general versioned migration framework.

## V2 anonymous behavior tables

- `sessions`: one random `session_id` and its first-seen UTC timestamp.
- `taste_profile_events`: the profile generation time.
- `taste_profile_event_albums`: a join table connecting each event to its seed
  album MBIDs and preserving the user's selection order. A new event is recorded
  when the selected seed set changes.
- `recommendation_impressions`: each album actually shown in the selected tier,
  its rank, Python-computed scores in separate numeric columns, and timestamp.
  Streamlit reruns do not create another impression for the same visible set.
- `recommendation_feedback`: `like` or `dislike` for an album in a session.
  Selecting the other value updates the existing row, so the table keeps the
  latest opinion per session and album.
- `taste_battles`: a pairwise preference between two different album MBIDs,
  linked to the anonymous session and the taste-profile event that produced the
  comparison. It stores the chosen album, deterministic pair-generation
  strategy, and timestamp. Previously compared pairs are not repeated within
  the same profile event.

All behavior rows reference canonical album MBIDs where applicable. They are
exploratory evaluation data; they are not used to train a model.

## Day 2 files

- `schema.sql`: table definitions and constraints
- `sample_data.sql`: two reproducible test albums
- `day2_checks.sql`: read-only relationship and integrity queries
- `taste.db`: generated local test database
