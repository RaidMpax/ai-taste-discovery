# V2 Data-Source Usage Audit

Audit date: 2026-10-01  
Purpose: record source-use boundaries for the public-Beta catalogue.  
This is a technical risk review, not legal advice. Contact/approval status is
tracked separately and is not changed by the source migration.

## Executive result

Last.fm status: **Pending written approval before public use of Last.fm-derived
data; does not block local development or the MusicBrainz-only snapshot.**
MusicBrainz tags/genres are now the active/default
production tag source. Existing Last.fm tag rows are retained as candidate data
and are not used by the default app loader. Public GitHub code, README,
architecture documents, and screenshots are not blocked. SQLite files remain
Git-ignored and are not committed to Git. The separately published
[MusicBrainz-only Release asset](https://github.com/RaidMpax/ai-taste-discovery/releases/tag/catalogue-musicbrainz-2026-10-01)
contains no Last.fm-derived tags, review text, or user behavior records. This
does not resolve or change the Last.fm approval status.

Cover Art Archive images are separate from MusicBrainz metadata licensing. The
official [CAA policy](https://musicbrainz.org/doc/Cover_Art_Archive) says the
images are collected for archival purposes and are used at the user's own risk.
The app displays remote CAA image URLs. Owner decision on 2026-09-30: retain
those URLs in the public Beta and accept the unresolved rights risk. This records
the product decision; it does not claim that a separate license was confirmed.

Decision recorded on 2026-09-29: written approval is tracked separately from
development. A short copy-ready request is saved in
`docs/LASTFM_APPROVAL_REQUEST.md`. This technical migration neither sends nor
updates an approval request. The pending approval status is a deployment issue
only, not a development or testing blocker.

## Local implementation checked

- `deployment/catalog.db` is an older local, Git-ignored mixed-source preview;
  it has not been committed or published and must not be used for deployment.
  The deployment exporter now creates
  `deployment/catalog_musicbrainz_only.db`, containing accepted catalogue rows
  and MusicBrainz tags only; it excludes Last.fm tags, reviews, and behavior.
  The verified snapshot is distributed separately as a GitHub Release asset;
  its database file remains untracked and Git-ignored.
- The app's default path displays and uses MusicBrainz tags, not Last.fm tags.
  The UI has no Last.fm attribution links; there is no Last.fm runtime API call.
- `semantic_search.py:load_album_documents()` builds each album document from
  title, credited artists, release year, and MusicBrainz tags/genres by default.
  The loader can explicitly select Last.fm for comparison. The app computes
  embeddings from the chosen documents at runtime; changing providers requires
  rebuilding vectors and reviewing recommendation results.
- `ingest.py:fetch_cover()` requests the Cover Art Archive and stores a remote
  `coverartarchive.org` image URL. The SQLite catalogue stores URLs, not image
  binaries. The preview has 518 such URLs.
- The preview deliberately contains no CritiqueBrainz review text. The separate
  local `taste.db` has 127 review rows (96 marked CC BY-NC-SA 3.0 and 31 marked
  CC BY-SA 3.0); attribution metadata is incomplete for older rows. This review
  corpus is not part of the deployment preview.

## Source-by-source findings

### MusicBrainz

MusicBrainz says its core database data is CC0 and distinguishes it from
supplementary data, which is CC BY-NC-SA 3.0. Its data breakdown places artist
names/MBIDs and release-group titles/MBIDs in core data, and release dates in
the core release fields. Our basic artist, release-group, and year metadata
matches those core categories. This does **not** apply to artwork or data from
other providers. See [MusicBrainz data licensing](https://musicbrainz.org/doc/About/Data_License)
and the [core/supplementary field breakdown](https://musicbrainz.org/doc/MusicBrainz_Database).

### Last.fm

The project retains album and artist tags retrieved through the Last.fm API as
candidate data. Ingestion can skip Last.fm when its optional API key is absent;
the default app path reads MusicBrainz tag rows and makes no Last.fm request.
Status: **Pending written approval before public use of Last.fm-derived tags.**
The MusicBrainz-only snapshot excludes them; this does not block local
development. See
the [Last.fm API Terms of Service](https://www.last.fm/api/tos), including
Section 2.7.

### Cover Art Archive

MusicBrainz explicitly notes that cover art has separate licensing and
copyright issues. The Cover Art Archive describes the images as an archival
collection, says to use them at one's own risk, and asks users to respect
artists' and labels' rights. Our preview displays remote image URLs. The owner
has chosen to retain the images in the public Beta while accepting the
unresolved rights risk; this is a product decision, not a license confirmation.
See
[MusicBrainz cover-art guidance](https://musicbrainz.org/doc/Cover_Art) and the
[Cover Art Archive policy](https://musicbrainz.org/doc/Cover_Art_Archive).

### CritiqueBrainz

The CritiqueBrainz API response exposes review text together with a license,
source URL, and reviewer metadata. The current preview excludes all reviews,
which avoids publishing this corpus before its license, attribution, and
intended Gemini/API reuse have been checked. See the
[CritiqueBrainz API response documentation](https://critiquebrainz.readthedocs.io/api/endpoints.html).

## Deployment status and follow-up

1. Written Last.fm approval for public use of Last.fm-derived data is pending.
   Continue local development, tests, tag signals, embeddings, recommendation,
   and Gemini work. Before a public deployment uses Last.fm-derived data,
   confirm approval and apply the required attribution/link placement.
2. Keep Last.fm-derived SQLite catalogue files Git-ignored and out of GitHub.
   Public code, README, architecture documentation, and screenshots may
   continue to be shared.
3. The owner has accepted the unresolved Cover Art Archive image-rights risk
   for the public Beta. CritiqueBrainz review reuse remains a separate
   public-deployment check; reviews stay out of the deployment catalogue.

The 2026-09-30 source migration changed only provider-specific tag rows in the
local databases and updated the default tag source. On 2026-10-01, the owner
authorized publication of the verified MusicBrainz-only SQLite snapshot as a
Release asset; no database was committed to Git. Last.fm approval remains
pending; Cover Art Archive display is recorded as an owner-accepted risk, not
license clearance. CritiqueBrainz public reuse remains unresolved.
