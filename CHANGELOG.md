# Changelog

## 2026-10-02 — V2.1 Taste Profile length refinement

- Expanded the target length of the Gemini Taste Analysis paragraph to approximately 220–320 Chinese characters so the profile reads as a fuller editorial observation while keeping the same evidence and citation constraints.

## 2026-10-02 — V2.1 product iteration

Small usability pass based on the first opted-in beta sessions and friend feedback.

- Separated album search from the selected-seed list. Search works by album or artist; selected albums are removed only with an explicit button, and the 10-album limit remains.
- Added a catalogue-scope message for searches with no matches. Raw failed queries are not collected.
- Moved the 1–8 recommendation-count control next to the recommendation experience; Safe / Explore / Wildcard rules and placement are unchanged.
- Reworked Taste Battle cards into a compact desktop A–VS–B comparison with responsive mobile sizing. Pairing and tournament logic are unchanged.
- Changed Gemini Taste Analysis to one grounded Simplified Chinese editorial paragraph while retaining structured output and citation validation.
- Polished key Chinese labels, empty states, and action text; seed resolution now prefers release-group MBIDs to avoid same-title ambiguity.
- Marked newly created anonymous sessions as `v2.1-beta` so the next cohort can be separated from earlier sessions.
- Added the read-only first-cohort analysis in [`analysis/v2_first_user_analysis.md`](analysis/v2_first_user_analysis.md).

This iteration does not expand the catalogue, alter ranking weights, regenerate catalogue embeddings, or modify/deploy the production behavior database.
