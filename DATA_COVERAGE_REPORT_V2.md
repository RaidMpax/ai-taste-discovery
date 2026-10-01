# V2 Dataset Coverage

Snapshot: 2026-09-30
Scope: the 530 accepted release-group MBIDs in `album_match_manifest.json`.

## Source coverage

| Data source | Stored coverage in the 530-album catalogue | Notes |
| --- | ---: | --- |
| MusicBrainz album metadata | 530 / 530 | Existing accepted MBIDs were queried directly; no album matching was repeated. |
| MusicBrainz tags + genres | 504 / 530 (95.1%) | 530 / 530 API responses succeeded. 26 valid release groups returned no tags. |
| Cover Art Archive covers | 518 / 530 (97.7%) | 12 selected albums have no stored cover URL. |
| Last.fm tags (retained candidate source) | 515 / 530 (97.2%) | 4,834 rows in the accepted catalogue; not used by the default app loader. |
| CritiqueBrainz reviews | 107 / 530 (20.2%) | 126 licensed review records. No review is a normal data state. |

MusicBrainz returned 5,139 distinct normalized album-tag rows across the
accepted catalogue, averaging 9.70 tags per album (median 8; counting empty
responses as zero). The per-album distribution is 26 with zero tags, 92 with
1–3, 135 with 4–7, 239 with 8–20, and 38 with more than 20. The largest result
had 69 tags. Of the 5,139 tag values, 5,139 had a provider count; the median
provider count was 1, with 3,406 values having count 1. Those provider counts
remain in the Git-ignored migration cache and are not persisted as a new SQLite
column; SQLite keeps tag rank and source provenance.

Full per-album statuses and the 26 no-tag albums are recorded in the local,
Git-ignored `experiments/tag_source_ab_test/musicbrainz_tag_migration_report.json`.
There were no API failures, MBID mismatches, empty tag strings, control
characters, or duplicate normalized album/tag pairs.

## Tag quality and decision

The full catalogue has slightly lower MusicBrainz tag coverage than the stored
Last.fm data (95.1% vs. 97.2%), despite the 50-album stratified A/B sample
showing 96% vs. 92%. The A/B sample was intentionally stratified rather than a
random full-catalogue estimate; the full backfill is the stronger coverage
measurement for these 530 accepted albums. MusicBrainz therefore provides
adequate, but not complete or higher, tag coverage for the Beta.

The returned vocabulary includes specific descriptors such as `dream pop`,
`future bass`, `ethereal`, and `melancholic`, alongside broad genres. A spot
check also found metadata/list-like tags such as `offizielle charts`,
`plattentests.de`, `5+ wochen`, and a few long Discogs-generated strings. Four
tag values exceed 60 characters. These were retained rather than heuristically
removed: no tag-cleaning or recommendation-rule change was part of this source
migration. The smoke test shows that some metadata-like tags can still appear
in bridge signals, so that remains a visible evaluation/bad-case item.

The formal source is MusicBrainz. Last.fm rows remain in SQLite as separately
attributed candidate data; the loader does not fall back to or silently merge
them when a MusicBrainz album has no tags. This keeps each album document's
source consistent and avoids changing the recommendation logic mid-migration.
The 50-album A/B `RESULTS.md` remains the historical comparison; it established
technical feasibility, not recommendation quality.

**Beta edge case requiring a product decision:** 25 of the 26 MusicBrainz
tagless albums have stored Last.fm tags; one has no tags from either source. A
smoke test selecting a tagless MusicBrainz album as the only seed produced zero
recommendations in all three tiers, because the current unchanged recommender
requires a tag bridge. The five representative multi-album smoke profiles all
produced recommendations. No fallback or algorithm change was made; decide
separately whether the Beta should use an explicit per-album fallback or retain
this known empty-result case.

## Catalogue and integrity

The database has 537 album rows; all 530 accepted albums remain present and the
seven older rows outside the accepted manifest were not removed. For the
accepted catalogue, SQLite contains 286 linked artists, 534 album-artist links,
5,139 MusicBrainz tag rows, 4,834 Last.fm candidate-tag rows, and 126 reviews
across 107 albums. No database schema change was made. The migration backed up
the pre-migration database and changed only `album_tags` rows whose source is
`musicbrainz`; all existing Last.fm tag rows were preserved. Foreign-key checks
passed.

## Embedding and smoke verification

`semantic_search.py:load_album_documents()` now defaults to the 530 accepted
MBIDs and the `musicbrainz` tag source. The optional `tag_source="lastfm"`
argument remains available for explicit comparison. Streamlit, recommendation,
and RAG continue to use the same generic album-document fields. The embedding
model remains `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`;
album vectors are rebuilt in memory, not stored in SQLite.

The migration smoke test produced finite `(530, 384)` album vectors and finite
`(466, 384)` review-chunk vectors. Mainstream pop, alternative/indie,
electronic, experimental, and mixed-taste profiles all built successfully; each
produced Safe / Explore / Wildcard recommendations and RAG contexts. The
tagless single-seed edge case above returned empty tiers. Live Gemini
generation calls were not run: security review blocked transmission of locally
stored licensed review excerpts to the external API pending explicit user
approval. Offline citation-validation unit tests remain available.

When Streamlit is already running, restart that process before testing so its
cached album vectors are rebuilt from the MusicBrainz-based documents.
