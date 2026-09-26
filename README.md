# AI Taste Discovery

An educational V0.1 music recommendation project. The product will model a
listener's current taste, suggest Safe / Explore / Wildcard discoveries, and
explain each suggestion with retrieved source evidence.

## Day 1: data feasibility

The current code only checks whether a 10-album sample can be resolved across
MusicBrainz, Cover Art Archive, Last.fm, and CritiqueBrainz.

Requirements: Python 3.10+; no third-party Python packages are needed.

Last.fm requires a free API key. Set it only in your shell (never commit it):

```powershell
$env:LASTFM_API_KEY = "your-key"
```

Run:

```powershell
python feasibility_test.py
```

The script writes `feasibility_results.json` (raw structured observations) and
`FEASIBILITY.md` (the human-readable coverage table and limitations). If no
Last.fm key is set, that source is marked `not_tested`, not incorrectly counted
as missing data.

The sample can be changed in `test_albums.json`. Matching is intentionally
visible: inspect MusicBrainz's returned title, artist, score, MBID, and year in
the generated report before trusting the other source checks.

See [PROJECT.md](PROJECT.md) for the deliberately narrow V0.1 scope.

## Day 2: SQLite data model

The catalogue schema is defined in `schema.sql`. It models artists, MusicBrainz
release groups, artist credits, album tags, and optional reviews without adding
user, embedding, recommendation, or RAG tables early.

Day 2 includes:

- `schema.sql`: schema and integrity constraints
- `sample_data.sql`: Radiohead / *OK Computer* and Björk / *Homogenic*
- `day2_checks.sql`: read-only `JOIN`, `GROUP BY`, coverage, and integrity checks
- `DATA_MODEL.md`: decisions and known limitations
- `taste.db`: the generated local test database

## Day 3: data ingestion

`ingest.py` reads the confirmed release-group MBIDs in `test_albums.json`,
fetches the four external sources, and writes the cleaned catalogue to the
local SQLite database.

Put the Last.fm key in a local `.env` file (which Git ignores):

```text
LASTFM_API_KEY=your-key
```

Run one album first, then the full sample:

```powershell
python ingest.py --limit 1
python ingest.py
```

The import is idempotent: rerunning an album updates its current data instead
of inserting duplicates. A failed child-source request preserves previously
stored tags or cover data. Only CritiqueBrainz reviews with a non-empty license
are stored.

The current 10-album run produced 10 artists, 10 albums, 10 artist credits,
100 Last.fm tags, and 6 licensed CritiqueBrainz reviews. The pipeline first
uses the review list to discover IDs, then fetches fuller review records so
that license information is validated before a review is stored.
