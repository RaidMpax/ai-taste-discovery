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

The current 30-album catalogue produced 30 artists, 30 albums, 30 artist
credits, 292 Last.fm tags, and 18 licensed CritiqueBrainz reviews. The pipeline
first uses the review list to discover IDs, then fetches fuller review records
so that license information is validated before a review is stored. Use
`--offset` and `--limit` to import or retry a selected batch.

## Day 4: minimal semantic retrieval

Create an isolated environment and install the one direct dependency:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Inspect the deterministic text representation before embedding it:

```powershell
.\.venv\Scripts\python.exe semantic_search.py
```

Run a top-k search using an album already in the catalogue:

```powershell
.\.venv\Scripts\python.exe semantic_search.py --album "OK Computer" --top-k 3
```

Each album is represented by one document containing its title, artists,
release year, and deduplicated normalized tags. FastEmbed runs the multilingual
MiniLM model locally and NumPy calculates cosine similarity directly. Reviews
remain a separate corpus for the later RAG stage so uneven review coverage does
not distort album-to-album comparisons.

Top-k always returns the least-distant candidates even when none is genuinely
close. Catalogue coverage and supporting evidence must therefore be checked
before similarity scores are used for recommendation tiers.

## Day 5: minimal Taste Profile

Repeat `--favorite` to average several normalized album vectors into a profile:

```powershell
.\.venv\Scripts\python.exe semantic_search.py `
  --favorite "OK Computer" `
  --favorite "Homogenic" `
  --favorite "Untrue" `
  --top-k 5
```

The output also shows frequent profile tags and each candidate's nearest
individual favorite. These diagnostics expose cases where an average vector
creates a mathematical midpoint that is not a genuine user preference.

## Day 6: transparent recommendation tiers

Run the rule-based baseline with repeated favorites:

```powershell
.\.venv\Scripts\python.exe recommend.py `
  --favorite "OK Computer" `
  --favorite "Homogenic" `
  --favorite "Untrue" `
  --per-tier 3
```

The rules combine profile similarity, similarity to one concrete bridge
favorite, shared bridge tags, and new tags. Safe requires strong similarity
and at least two tags shared with the same favorite. Explore keeps at least one
bridge tag while adding new tags. Wildcard must be farther from the centroid
but still retain an explicit bridge; the program returns fewer results instead
of filling a tier without evidence.

## Day 7: review retrieval and RAG context

Inspect the evidence prepared for one recommendation before calling an LLM:

```powershell
.\.venv\Scripts\python.exe rag.py `
  --favorite "Homogenic" `
  --candidate "Dummy" `
  --top-k 2
```

Licensed reviews are split into roughly 900-character chunks with whole-sentence
overlap, embedded locally, and retrieved only within the named candidate and
favorite albums. The Context Builder combines structured tags with review
evidence and keeps review ID, source URL, and license. If no review exists, it
uses structured facts instead of borrowing evidence from an unrelated album.

## Day 8: minimal Streamlit UI

Start the local app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Choose one to five favorite albums, inspect the Safe / Explore / Wildcard
recommendations, and generate `Why This?` only for the items you want to
explain. Explanation requests use the local `.env` Gemini key; album and review
retrieval remains local and sources are shown separately from model output.
