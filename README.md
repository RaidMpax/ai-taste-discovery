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
