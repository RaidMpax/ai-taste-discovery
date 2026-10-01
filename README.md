# AI Taste Discovery

An educational music-discovery project preparing for a V2 friends-and-family
Beta. It models a listener's current taste, suggests Safe / Explore / Wildcard
albums, and explains each suggestion using retrieved evidence.

The current catalogue contains 530 accepted albums. V2 also includes an
optional Gemini Taste Analysis, anonymous feedback, Taste Battle, and offline
ranking diagnostics. The earlier V1 friends-and-family demo is live at
https://ai-taste-discovery-irdp3eamhnzuofrm7tbkqr.streamlit.app/. The V2
candidate is now published on the public GitHub `v2-beta` branch, but it has
not yet been verified as running on that hosted app. The
public catalogue snapshot excludes Last.fm-derived tags and CritiqueBrainz
reviews; see `DEPLOYMENT_READINESS.md` for the current release status.

## Quick start

Requirements: Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add `GEMINI_API_KEY` to `.env` only if you want Taste Analysis or **Why This?**
generation. MusicBrainz tags are the active/default tag source and need no API
key. `LASTFM_API_KEY` is optional; if present, ingestion also retains Last.fm
tags as candidate data, but the app does not need the key or call Last.fm.
Cover Art Archive and CritiqueBrainz do not require API keys for this prototype.
Never commit `.env` or `.streamlit/secrets.toml`.

Start the app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If no local database is configured, the app downloads the pinned
MusicBrainz-only catalogue snapshot from the GitHub Release and verifies its
SHA-256 before using it. SQLite files are intentionally Git-ignored. Set
`AI_TASTE_DATABASE_PATH` as an environment variable to use an existing local or
host-mounted database instead.

The ingestion and deployment-export scripts are curator tools and require the
private working manifest `album_match_manifest.json`, which is not distributed
with the public demo. The public app uses the checked-in
`deployment/accepted_album_manifest.json` plus the pinned database snapshot; it
does not need a fresh API import to start.

In the curator workspace, a deployment preview can be rebuilt with:

```powershell
.\.venv\Scripts\python.exe prepare_deployment_catalog.py
```

This writes `deployment/catalog_musicbrainz_only.db` from the accepted manifest
without making API requests. It exports MusicBrainz tags only, omits reviews
pending attribution/reuse review, and contains no user behavior rows. The
verified snapshot is also available as a [GitHub Release asset](https://github.com/RaidMpax/ai-taste-discovery/releases/download/catalogue-musicbrainz-2026-10-01/catalog_musicbrainz_only.db).
The app uses an existing local `AI_TASTE_DATABASE_PATH` first; if that file is
missing, it downloads the pinned public snapshot and verifies its SHA-256 before
using it. The database remains Git-ignored and is not committed to the repo.

The first semantic search or app start downloads the local FastEmbed model, so
it can take longer than later runs.

## Current Beta boundaries and known limitations

- Input is by album, not artist. Artist metadata is stored, but artist-based
  selection and profiles are deferred.
- The catalogue is a curated set of 530 albums, so recommendations only
  rank albums inside that collection.
- CritiqueBrainz coverage is sparse because only reviews with a declared
  license are stored. When candidate review evidence is missing, the system
  falls back to structured metadata and tags and states that limitation.
- There is no account system. The app offers an explicit opt-in before it
  records a random session ID, selected albums, recommendation lists, feedback,
  or Taste Battle choices. The Supabase schema is ready, but the hosted app has
  not yet been verified with the V2 branch and its secrets, so remote event
  collection has not started. Set `AI_TASTE_BEHAVIOR_STORAGE = "supabase"`
  and the Supabase secrets in Streamlit Community Cloud to retain these events
  for analysis.
  The setup is documented in
  [docs/SUPABASE_BEHAVIOR_SETUP.md](docs/SUPABASE_BEHAVIOR_SETUP.md).
- Recommendations still work without Gemini. Explanation generation depends
  on the Gemini API and can be unavailable or rate-limited on the free tier.
- Offline ablation metrics describe list properties; they are not a
  recommendation quality benchmark without real preference labels.

In local persistent mode, anonymous behavior records are stored in `taste.db`.
In session mode, interaction state stays in the current Streamlit session and
is not written to a database. Supabase mode writes opt-in analytics to a
separate Postgres database; these events are not used to train a
recommendation model.

## Day 1: data feasibility

The current code only checks whether a 10-album sample can be resolved across
MusicBrainz, Cover Art Archive, Last.fm, and CritiqueBrainz.

This standalone feasibility script needs no third-party Python packages.

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

See [PROJECT.md](PROJECT.md) for the product goal and current release boundary.

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

`ingest.py` reads the accepted release-group MBIDs in
`album_match_manifest.json`, fetches MusicBrainz metadata/tags, Cover Art
Archive covers, and CritiqueBrainz reviews, and writes the cleaned catalogue to
SQLite. It can optionally fetch Last.fm tags when an API key is available. The
original 30-album V1 sample is retained in historical files; V2 has 530
accepted albums.

To retain Last.fm candidate tags, put its key in the local `.env` file (Git
ignores it). This is optional; without a key the MusicBrainz-based import still
continues:

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

The current selected catalogue has 530 albums, 286 linked artists, 5,139
MusicBrainz tag rows, 4,834 retained Last.fm candidate-tag rows, and 126
licensed reviews across 107 albums. The pipeline first uses the review list to
discover IDs, then fetches fuller review records so that a declared license is
present before a review is stored. Use `--offset` and `--limit` to import or
retry a selected batch.

## Day 4: minimal semantic retrieval

Create an isolated environment and install the project dependencies:

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
release year, and deduplicated normalized MusicBrainz tags/genres by default.
The loader has an explicit `tag_source="lastfm"` option for comparison, but does
not silently mix providers. FastEmbed runs the multilingual MiniLM model locally
and NumPy calculates cosine similarity directly. Reviews remain a separate
corpus for the later RAG stage so uneven review coverage does not distort
album-to-album comparisons.

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

Choose one to ten favorite albums and confirm them to build a Taste Profile;
the selected covers appear in a horizontal shelf. Browse Safe / Explore /
Wildcard recommendations or switch to a finite Taste Battle that produces a
winner. Generate `Why This?` only for the items you want to explain. Explanation requests use
`GEMINI_API_KEY` from the environment, local `.env`, or Streamlit secrets; album
and review retrieval remains local and sources are shown separately from model
output.

The UI caches local embedding models and vectors for the app process. This
avoids invalidating the cache when anonymous behavior rows are written to the
same SQLite file. Restart Streamlit after changing the catalogue. Recommendation
tiers remain deterministic Python rules; Gemini only turns retrieved evidence
into a structured explanation.
