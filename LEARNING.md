# V2 Learning Notes

This file is a study guide, not a set of prepared interview answers.

## Topic: Canonical Album Discovery and Matching

### Questions I Should Be Able to Answer

- Why does V1 ingest confirmed release-group MBIDs instead of trusting album titles?
- What is the difference between discovering a candidate and accepting a canonical match?
- Why does V2 constrain MusicBrainz search with an artist MBID?
- Why are score, normalized title, artist credit, primary type, and secondary type checked separately?
- Why should ambiguous results enter `needs_review` instead of being discarded or auto-inserted?
- How do checkpointing and idempotent ingestion solve different problems?

### Current Implementation

- `catalog_artists.json` contains the small, confirmed artist seed set.
- `discover_catalog.py` gets popular album candidates from Last.fm.
- `classify_match()` applies deterministic acceptance rules to MusicBrainz results.
- The output manifest preserves source rank, playcount, match metadata, and rejection reasons.
- `tests/test_discover_catalog.py` checks the matching rules without making network requests.

### Interview Questions

1. Why is a MusicBrainz search score of 100 insufficient by itself?
2. What false positives can appear when album titles are used without artist MBIDs?
3. How would you measure precision before importing hundreds of auto-accepted matches?
4. What should happen if discovery succeeds but a later metadata API fails?
5. How would you resume a long-running ingestion job without creating duplicates?
