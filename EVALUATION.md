# V0.1 Evaluation

Evaluation date: 2026-09-27

Final regression: 2026-09-28

This is a small qualitative check, not a recommendation benchmark. The test
profile contains one favorite album, Radiohead's *OK Computer*, and uses the
current 30-album catalogue.

## Cases

| Case | Candidate | Review evidence | Result |
| --- | --- | --- | --- |
| Safe | *Loveless* | Candidate and favorite reviews | Partial pass |
| Explore | *Dummy* | Candidate and favorite reviews | Pass |
| Wildcard | *Untrue* | Candidate and favorite reviews | Pass |
| Missing candidate review | *万能青年旅店* | Favorite review plus tags | Pass |
| Streamlit end-to-end | *Dummy* | Three retrieved review chunks | Pass |

### Safe — Loveless

The explanation correctly used the shared 90s, alternative,
alternative rock, and rock tags and treated the recommendation as a
low-risk extension. The retrieved review directly compared *Loveless* with
*OK Computer* in a greatest-album discussion.

Bad case: the first generation changed one review's comparison into the
broader phrase "often mentioned together." A later retest still used the
equivalent phrase "常被". The prompt remains explicit, and a deterministic
validator now rejects unsupported consensus language instead of displaying it.

### Explore — Dummy

The explanation balanced the familiar 90s and electronic bridge with new
trip-hop, downtempo, and female vocalists directions. Every review claim used
an allowed retrieved chunk ID, and the limitations field acknowledged that
the reviews did not directly compare both albums.

### Wildcard — Untrue

The explanation explicitly described the recommendation as more distant. It
used alternative and electronic as the bridge and identified 2-step, ambient,
and UK garage-related tags as the exploratory leap. The limitations field did
not pretend that the albums were closely similar.

### Missing candidate review — 万能青年旅店

No candidate review was available. The generated explanation relied on shared
and new tags, cited only the favorite album's review, and explicitly stated
that evidence about the candidate was missing. This is the intended fallback.

### Streamlit end-to-end — Dummy

Starting from the default *OK Computer* favorite, the Explore recommendation
button completed review retrieval, context building, Gemini structured output,
validation, and source binding without a UI error. The displayed result kept
three retrieved source IDs; source URLs remained application-owned data.

## Deterministic checks

- Recommendation tier is assigned by Python rules, not by the LLM.
- Changing per_tier changes display count but no longer changes assignment.
- Review source IDs returned by Gemini must exist in the retrieved context.
- URLs are resolved by the application; Gemini does not generate source URLs.
- Omitting --generate makes no Gemini API request.

## Final regression

- Python dependency and syntax checks passed.
- SQLite foreign-key check returned no errors.
- Catalogue counts remained 30 artists, 30 albums, 292 tags, and 18 reviews.
- A two-favorite profile produced 5 Safe, 6 Explore, and 7 Wildcard candidates
  with no cross-tier duplicates and no favorite album returned as a candidate.
- Candidate-scoped RAG retrieved two licensed *Dummy* review chunks for the
  *Homogenic* to *Dummy* case without borrowing evidence from another album.
- The UI passed default-state and four-favorite / eight-result tests with no
  Streamlit exceptions. The generated explanation state can be collapsed and
  cleared without another Gemini request.
- Windows CLI output is forced to UTF-8; Chinese artist names and names such as
  Björk now render without mojibake or `UnicodeEncodeError`.

## Bad cases and follow-ups

| Bad case | Status |
| --- | --- |
| Tier changed when per_tier changed | Fixed by assigning all candidates before slicing results |
| One review was phrased as general consensus | Prompt tightened; deterministic output validator now rejects consensus wording |
| Gemini 503 high-demand and 429 rate-limit errors | Flash-Lite primary/fallback, one attempt per model, 30-second timeout |
| No candidate review | Tags-only fallback works and reports the limitation |
| Last.fm tag inide | Fixed: normalize to indie while retaining the raw tag |
| Opaque Last.fm tag dabeat | Fixed: retain it in SQLite but exclude it from taste signals |
| Embeddings recomputed for every CLI run | Fixed for the UI with `st.cache_resource`; the database modification time invalidates stale vectors |
| Windows CLI crashed on non-GBK artist names | Fixed by configuring the recommendation, semantic-search, and RAG entry points for UTF-8 output |
