# V2 Beta Deployment Readiness

Audit date: 2026-10-01
Status: **V2 is not yet ready for the public Beta.** Streamlit Community Cloud
is the selected host and the earlier V1 demo was deployed there, but the V2
candidate in this branch has not yet been published to that app. The
MusicBrainz-only catalogue snapshot is published as a GitHub Release asset.
The Supabase migration is applied and verified (five tables, RLS enabled); the
hosted secrets are still pending, and no V2 behavior events have been
collected.

## Checked and improved

- Python packages are pinned in `requirements.txt`; local setup targets Python
  3.10 or newer.
- `.env` and `.streamlit/secrets.toml` are Git-ignored. `.env` is not tracked.
- Gemini now accepts an environment variable, local `.env`, or a Streamlit
  secret. Gemini is only called after an explicit explanation/profile-analysis
  action; recommendation ranking remains available without it.
- FastEmbed resources are cached for the app process. Local SQLite behavior
  writes share the catalogue file without invalidating the embedding cache;
  hosted Supabase events use a separate database.
- Behavior schema initialization is cached once per app process/revision.
- The app begins without a preselected favorite and discloses the anonymous
  events it records. Missing covers and reviews remain valid catalogue states.
- Gemini uses a 30-second request timeout, one attempt per model, and tries a
  fallback model on recognized temporary errors. A failure is caught by the UI;
  it does not change deterministic recommendation results.
- `prepare_deployment_catalog.py` builds a local snapshot from accepted manifest
  IDs without calling external APIs. It exports MusicBrainz tags only. `app.py`
  accepts `AI_TASTE_DATABASE_PATH` from the environment or Streamlit secrets and
  downloads the pinned release asset only when the configured local file is
  missing. Downloads are checked against a SHA-256 digest before installation;
  the URL and expected digest can be overridden together if a new snapshot is
  published.

## Launch blockers and decisions

### 1. Provide the catalogue database safely

`taste.db` and generated deployment databases are intentionally Git-ignored,
and no `.db` file is tracked. The 530-album MusicBrainz-only snapshot is
available as a [versioned GitHub Release asset](https://github.com/RaidMpax/ai-taste-discovery/releases/tag/catalogue-musicbrainz-2026-10-01).
On a fresh checkout, the app downloads this pinned file and verifies its SHA-256
when the configured `AI_TASTE_DATABASE_PATH` is missing. A local database at
that path takes precedence and causes no network download. The older
`deployment/catalog.db` is a local preview containing Last.fm-derived rows and
must not be used for public deployment.

Do not publish or upload the local `taste.db` unchanged. The generated preview
contains only accepted albums, their credited artists, and tags. It has empty
behavior tables and deliberately omits reviews until attribution and public /
Gemini reuse are reviewed. The preview therefore has no review-retrieval RAG
evidence; the app can still explain recommendations from structured tags, as
it does whenever reviews are unavailable. The local `taste.db` still contains
its full review corpus for local experiments.

The accepted manifest has 530 albums, while the local SQLite file currently has
537 albums and 127 reviews. Its review table has 96 records marked
`CC BY-NC-SA 3.0` and 31 marked `CC BY-SA 3.0`; 90 and 0 respectively have an
external source URL. Every manifest album exists in SQLite, plus 7 albums that
are outside the accepted manifest and should not enter the deployment copy. The
app schema and ingestion code now preserve reviewer display name and license
URL when the API supplies them, but the existing rows have not been refreshed
to backfill that metadata. The preview contains 530 albums, 286 associated
artists, 534 artist credits, and 5,139 MusicBrainz tag rows; 518 albums have a
cover URL, 504 have tags, and zero reviews or behavior rows are present. This
report does not determine whether the local review records can be used for every
intended purpose.

### 2. Hosted behavior data

The V2 Beta uses the separate Supabase Postgres project for opt-in behavior
events; the catalogue remains the read-only MusicBrainz-only SQLite snapshot.
The migration has been run and verified in Supabase, including row-level
security on all five tables. No events have been collected yet because the V2
code is not deployed and Streamlit secrets are not configured.

Local development defaults to `persistent`, using SQLite. The app also
supports `session` mode, which keeps interactions only for the current visit,
and `supabase` mode for opt-in remote persistence. Do not configure a
persistent hosted SQLite path for the free demo.

### 3. Set runtime secrets and resource policy

- Configure `AI_TASTE_BEHAVIOR_STORAGE = "supabase"`, `SUPABASE_URL`, and
  `SUPABASE_SECRET_KEY` in Streamlit Community Cloud Secrets. Configure
  `GEMINI_API_KEY` as well to enable the requested Taste Analysis and Why This?
  experience; deterministic recommendations remain available without Gemini.
- Never put the Supabase secret key or Gemini key in Git, the browser, or chat.
  The Supabase writer sends its secret key only in the server-side `apikey`
  request header. See `docs/SUPABASE_BEHAVIOR_SETUP.md`.
- `LASTFM_API_KEY` is optional and only collects candidate tags during
  ingestion. The app defaults to locally stored MusicBrainz tags and does not
  need the key or call Last.fm during a request.
- The app has upstream Gemini timeout/fallback handling but no application-level
  public abuse/rate limit. Set provider quotas/monitor usage or decide whether
  to add a lightweight request cap before sharing broadly.
- A cold app process needs outbound access to download the FastEmbed model. The
  first load can take longer than later interactions.

### 4. Clear public use of third-party data

The database remains Git-ignored and is not committed to the repository. Only
the verified MusicBrainz-only snapshot is published as a Release asset; the
older mixed-source preview is not intended for public distribution. The current
snapshot excludes Last.fm-derived tags and review text. See
`DATA_SOURCE_USAGE_AUDIT.md` for the remaining source-use questions:

- The new export contains MusicBrainz tag/genre rows only. The Last.fm approval
  status remains pending, but no Last.fm-derived tags are included in the
  intended deployment catalogue. Keep the older mixed-source preview out of
  public distribution.
- Continue sharing public project code, README, architecture documentation,
  and screenshots. Do not commit any SQLite catalogue; keep database files
  Git-ignored. Do not include Last.fm-derived data in a public demo unless the
  required approval and attribution are confirmed.
- 518 preview albums use remote Cover Art Archive image URLs. The owner chose
  on 2026-09-30 to retain them in the public Beta and accept the unresolved
  rights risk. This is a product decision, not confirmation of a separate image
  license; the [official CAA policy](https://musicbrainz.org/doc/Cover_Art_Archive)
  says the images are used at the user's own risk.
- CritiqueBrainz reviews are omitted from the preview. Keep them out until
  their license, attribution, and Gemini/API use are checked.

MusicBrainz lists the relevant artist/release-group identifiers and names and
release dates among core fields licensed CC0; supplementary data has a
different license. This conclusion applies only to those metadata fields, not
Last.fm tags, artwork, or reviews.

## Smoke-check results

- Local browser smoke check on 2026-09-30 used the MusicBrainz-only deployment
  snapshot, session-only behavior storage, and no Gemini key. Recommendations
  remained available and the missing-key message was clear. At a 390px mobile
  viewport, recommendation cards render one per row with no horizontal page
  overflow; at 1280px, the existing three-column layout remains. This was a
  localhost check, not a deployed-host test.
- The source-migration verification on 2026-09-30 built finite 530 x 384 album
  vectors and passed recommendation/RAG-context checks for five taste profiles.
- Full unit suite: 71 tests passed on 2026-10-01, including mocked Supabase
  request tests; no test wrote to the live Supabase project.
- Python compilation and import checks passed.
- The source migration changed only provider-specific `album_tags` rows; it did
  not change tables/schema, album/artist metadata, covers, reviews, behavior, or
  recommendation rules. `PRAGMA foreign_key_check` passed afterward.
- A single MusicBrainz-tagless seed returns no recommendations under the
  unchanged tag-bridge rules. This user-visible empty-result edge requires a
  separate product decision before claiming every possible seed combination is
  covered.
- Live Gemini generation was not verified in this smoke test because the
  external call would transmit locally stored licensed review excerpts; explicit
  approval is required before sending that payload.
- Official source-use review completed on 2026-09-29; see
  `DATA_SOURCE_USAGE_AUDIT.md`. No external provider was contacted and no legal
  clearance is claimed.
- Browser/mobile behavior has not yet been tested against a deployed host.

- The Supabase writer has only been tested with mocked HTTP responses. The
  actual hosted connection cannot be verified until the app's secret key is
  added in Streamlit Community Cloud and the V2 candidate is deployed.

Before inviting friends, publish the reviewed V2 candidate to the existing
Streamlit app, add the required hosted secrets, then verify first startup,
Gemini analysis/explanation, opt-in and opt-out behavior, a small-screen view,
and that Supabase rows persist after a fresh app session. A local mocked test
suite cannot replace that final hosted smoke test.
