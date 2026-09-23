# V0.1 Data Model

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
- `album_tags` preserves both the source text and its normalized form.
- `reviews` stores optional CritiqueBrainz text and its attribution metadata.
- One release-group cover URL is stored directly on `albums` for V0.1.

## Important decisions

- Missing release years and covers do not prevent an album from being stored.
- Artist and album names are descriptive data; MBIDs are identifiers.
- Tag rank and artist-credit order start at 1.
- Review source name and source URL may be absent, but language, license, and
  non-blank text are required.
- SQLite foreign-key enforcement must be enabled for every connection with
  `PRAGMA foreign_keys = ON`.

## Known limitations

- Tag normalization currently has no finalized rule set. The sample only shows
  that raw variants such as `trip-hop` and `trip hop` can map to one value.
- The schema stores one representative cover rather than edition-level covers.
- CritiqueBrainz review coverage is incomplete, so albums may have no reviews.
- There are no user, embedding, vector, or recommendation tables yet.
- Formal migrations and performance indexes are unnecessary at the current
  30–50 album scale and are not part of Day 2.

## Day 2 files

- `schema.sql`: table definitions and constraints
- `sample_data.sql`: two reproducible test albums
- `day2_checks.sql`: read-only relationship and integrity queries
- `taste.db`: generated local test database

