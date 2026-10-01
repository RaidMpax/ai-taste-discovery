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
- `discover_catalog.py` gets popular album candidates from Last.fm, then browses
  the confirmed artist's MusicBrainz album discography once.
- `classify_discography_match()` applies deterministic acceptance rules locally.
- The output manifest preserves source rank, playcount, match metadata, and rejection reasons.
- `tests/test_discover_catalog.py` checks the matching rules without making network requests.

### Interview Questions

1. Why is an artist-MBID-constrained discography safer than a global title search?
2. What false positives can appear when album titles are used without artist MBIDs?
3. How would you measure precision before importing hundreds of auto-accepted matches?
4. What should happen if discovery succeeds but a later metadata API fails?
5. How would you resume a long-running ingestion job without creating duplicates?

## Topic: Dataset Ingestion and Coverage

### Current Implementation

- `ingest.py`: request retries, source-specific fetch functions, SQLite upserts, and per-run coverage summary.
- `album_match_manifest.json`: approved canonical V2 album set and MusicBrainz IDs.
- `ingestion_report_v2.json` and `ingestion_retry_report_v2.json`: source outcomes for the initial run and targeted retry.
- `DATA_COVERAGE_REPORT_V2.md`: reconciled coverage for the selected 530 albums.

### Questions I Should Be Able to Answer

- Why does the pipeline use a confirmed release-group MBID after selection?
- What is the difference between a source request failing, a source returning no data, and data already existing in SQLite?
- How does the SQLite upsert make a repeated ingestion run safe?
- When a source request fails, which existing fields does the importer preserve?
- Why do request success rates and stored database coverage sometimes differ?
- What denominator should a coverage percentage use, and why should it be explicit?
- Why is an album with no CritiqueBrainz review still valid for the catalogue?
- How do the review license and source metadata support later RAG citations?

### Interview Questions

1. How would you distinguish a timeout from a valid empty response in a data pipeline?
2. How do primary keys and unique constraints help make ingestion idempotent?
3. How would you retry only failed records without reprocessing the whole catalogue?
4. How would you report partial success across several independent data sources?
5. What data provenance would you retain so a recommendation explanation can be audited?

## Topic: Album Documents and Embedding Scope

### Current Implementation

- `semantic_search.py:load_album_documents()` reads only accepted release-group MBIDs from `album_match_manifest.json` and checks that each one exists in SQLite.
- Each album document contains title, artist credits, release year, and
  normalized MusicBrainz tags/genres by default. The loader accepts an explicit
  `tag_source="lastfm"` for comparison; providers are not silently combined.
- `semantic_search.py:embed_documents()` uses `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; the current output is a 530 x 384 `float32` matrix.
- Streamlit, the recommendation CLI, and the RAG CLI share the same album-document loader. The app keeps the vectors in memory through Streamlit's resource cache.

### Questions I Should Be Able to Answer

- Why is an approved MBID manifest a better catalogue boundary than selecting every row from `albums`?
- Which fields are included in an album's embedding text, and which are left out?
- Why are CritiqueBrainz reviews not mixed into the album document when review coverage is uneven?
- What does the embedding model's 384-dimensional output represent?
- Where do the document rows and vector rows get their shared ordering from?
- How does the cosine-similarity function use the vectors?
- What would change if the vectors were persisted instead of rebuilt and cached in memory?

### Interview Questions

1. How do you ensure a filtered vector matrix remains aligned with its album metadata?
2. Why should a missing manifest MBID raise an error instead of silently shrinking the catalogue?
3. What trade-offs come from keeping vectors in memory for a catalogue of this size?
4. How would you verify that a candidate was ranked from the approved catalogue only?

## Topic: Structured Taste Profile from Multiple Seeds

### Current Implementation

- `semantic_search.py:build_taste_profile()` L2-normalizes each selected album vector, averages them, then L2-normalizes the result. This preserves the existing mean-pooling method.
- The profile also exposes seed album facts, tag counts, tags found in at least two seeds, tags found in only one seed, and the known release-year range.
- These are deterministic descriptive signals, not a model's interpretation of the user's personality. `tests/test_semantic_search.py` checks a two-seed example and missing-year behavior.

### Questions I Should Be Able to Answer

- Why normalize each seed vector before averaging, then normalize the average again?
- What information does the centroid lose when the selected albums have very different styles?
- Why does a tag count represent the number of seed albums carrying that tag, rather than its raw number of occurrences?
- Why can a shared tag be suggestive without proving that the user likes every album with that tag?
- Why is a release-year range a descriptive fact rather than a recommendation score?

### Interview Questions

1. How would you explain mean pooling to someone who knows vectors but not recommender systems?
2. What happens if two seed embeddings point in nearly opposite directions?
3. How would you distinguish a shared trait from a contrast across selected albums?
4. What could go wrong if metadata or tags are missing for one seed?

## Topic: Taste Analysis with Grounded Review Evidence

### Current Implementation

- `rag.py:build_taste_analysis_context()` starts with the deterministic Taste Profile signals and retrieves licensed review chunks for each selected seed album.
- Review retrieval is constrained by the album's release-group MBID, so albums with the same title cannot leak evidence into each other.
- `rag.py:generate_taste_analysis()` asks Gemini for structured Chinese analysis. It may summarize the profile, tendencies, contrasts, and exploration directions; it cannot choose recommendations or infer personal identity.
- The returned source IDs pass through the existing citation and unsupported-consensus checks. The Streamlit button calls Gemini only when clicked; a failure leaves recommendations usable.
- `tests/test_taste_analysis.py` covers MBID-scoped retrieval, missing-review context, and rejection of invented source IDs. The API itself is not called by these offline tests.

### Questions I Should Be Able to Answer

- Which fields enter Taste Analysis before Gemini is called?
- How is a review chunk tied to the exact seed album, and why is an MBID safer than a title?
- What can the citation validator confirm, and what does it still not prove about a claim's truth?
- How does Taste Analysis differ from the per-recommendation Why This explanation?
- What should the app do when there are no licensed reviews or Gemini is unavailable?

### Interview Questions

1. How would you trace a Taste Analysis sentence back to its supplied evidence?
2. Why use structured output for this response?
3. How can a prompt reduce unsupported claims without guaranteeing factual correctness?
4. Why should recommendation ranking remain outside the LLM call?

## Topic: Anonymous Recommendation Behavior Data

### Current Implementation

- In local SQLite mode, `behavior.py` creates a random session row, records selected seed MBIDs through a join table, logs recommendations shown in the selected tier, and upserts like/dislike feedback.
- `schema.sql` defines the local behavior tables and foreign keys. The schema uses `CREATE TABLE IF NOT EXISTS`, so startup can add these tables to an existing catalogue database.
- `recommend.py:candidate_features()` includes the release-group MBID and keeps recommendation scores in Python. Impression scores are stored in separate numeric SQLite columns for direct SQL analysis.
- `app.py` writes a profile event when the selected seed set changes and records impressions only for the visible recommendation set. A session-state signature avoids counting Streamlit reruns as new views.
- In local SQLite mode, feedback is the latest choice per album and session. The hosted Supabase schema instead appends each feedback change as a separate event. Neither store trains a model.

### Questions I Should Be Able to Answer

- What makes the session ID anonymous, and what limitations does that have?
- Why store selected seed MBIDs instead of only their display titles?
- What event counts as an impression, and how does the app avoid duplicate rows on rerun?
- Which recommendation scores are stored, and who computed them?
- Why does changing like to dislike update the row instead of keeping both events?
- Which foreign keys connect behavior records to sessions, profile events, and albums?

### Interview Questions

1. How would you calculate feedback rate by recommendation tier from these tables?
2. What bias can arise because only visible cards are logged as impressions?
3. What would need to change to preserve a full history of feedback changes?
4. Why is a random session ID not the same as an authenticated user account?

## Topic: Recommendation Score Breakdown and Tier Assignment

### Current Implementation

- `recommend.py:candidate_features()` exposes embedding similarity/distance, bridge similarity, bridge-tag overlap, tag familiarity, novelty ratio, and the existing Safe / Explore / Wildcard score formulas.
- Each final score is also broken into weighted signal contributions. The formulas remain deterministic Python heuristics; they are not learned probabilities.
- `recommend.py:choose_recommendations()` applies the existing median and tag rules, records the assigned tier, full-pool rank, final score, assignment reason, and whether the item fits the display limit.
- Candidate identity for tier assignment uses release-group MBID, so duplicate album titles do not collide.
- The Streamlit expander displays the full candidate breakdown, including items that were assigned but fell outside the visible top-N.
- `tests/test_recommend.py` checks score components, tier rules, full-pool ranks, display limits, and candidates left unassigned.

### Questions I Should Be Able to Answer

- What is the difference between embedding similarity, embedding distance, and tag novelty ratio?
- Which seed album determines bridge similarity and bridge-tag overlap when several seed albums are selected?
- How does tag familiarity map the number of bridge tags into a 0–1 score?
- What are the weights in each tier's final score, and what does each contribution mean?
- Why can a candidate have an assigned tier but not appear in the UI?
- Why is a final score a heuristic rather than a probability that the user will like an album?

### Interview Questions

1. How would you diagnose a candidate with high embedding similarity but low tag familiarity?
2. How would changing the median threshold affect Safe and Wildcard assignments?
3. How would you run an ablation to test whether tag signals improve recommendations?
4. What evidence would justify changing one of the score weights?

## Topic: Taste Battle and Pairwise Preference Data

### Current Implementation

- `recommend.py:build_battle_participants()` creates a balanced field of up to eight albums, and `resolve_battle_tournament()` advances winners through a deterministic knockout bracket.
- `app.py:render_taste_battle()` displays one unfinished match at a time and shows the final winner after at most seven choices. The comparison route still comes from the selected Safe/Explore or similarity/tag strategy.
- `behavior.py:record_battle_choice()` stores the session, profile event, both album MBIDs, the chosen MBID, pair-generation strategy, and timestamp in `taste_battles`.
- `behavior.py:load_battle_choices()` reconstructs prior match winners from unordered album pairs, so the bracket can resume after an app rerun without adding a tournament framework or changing the database schema.
- The pairwise records are evaluation data only. No preference model is trained and no choice changes recommendation scores.

### Questions I Should Be Able to Answer

- What does a pairwise preference record tell us that a like/dislike on one album does not?
- Why attach a battle to a `profile_event_id` as well as a `session_id`?
- Why do the pairing strategies compare recommendation tiers or isolate a similarity/tag-signal contrast?
- How does the app infer each round's winner from the saved pairwise records?
- What biases can remain even when A/B display order alternates?
- Why are the seven tournament choices still evaluation data rather than a trained ranking model?

### Interview Questions

1. How would you calculate the share of battles won by Explore against Safe?
2. What selection bias is introduced by offering only a bounded top-ranked pool?
3. How would you change the schema if you wanted to preserve repeated judgments of the same pair?
4. Why are pairwise votes not automatically training data for a ranking model?

## Topic: Confirming Seeds and Completing a Taste Battle

### Current Implementation

- `app.py:main()` keeps draft favorites inside a form. Taste Profile, AI Taste Analysis, and recommendations use only the confirmed selection; confirmation can include up to ten albums.
- `app.py:render_album_shelf()` shows the confirmed covers in a fixed-height horizontal scroller. This is a display of the selected records, not a second source of profile data.
- `semantic_search.py:build_taste_profile()` still aggregates L2-normalized seed embeddings by mean pooling, regardless of whether one or ten seeds are selected.
- A newly confirmed profile triggers Taste Analysis once. A provider error is shown separately with a retry action; structured profile and recommendation generation remain available.
- `app.py:render_taste_battle()` presents recommendation discovery and the knockout comparison as neighboring tabs. The bracket uses existing pair-choice rows; it does not alter recommendation scores or require a schema migration.

### Questions I Should Be Able to Answer

- Why does a Streamlit form separate draft selections from the confirmed profile used for recommendations?
- What changes mathematically when mean-pooling one seed embedding versus ten?
- Why can the horizontal cover shelf be presentation-only while the multiselect remains the source of truth?
- How do pairwise choice rows reconstruct a deterministic bracket after a rerun?
- What does `WinError 10013` tell us about the process environment, and what does it not tell us about the Gemini key?

### Interview Questions

1. How would you prevent an expensive API call from repeating on every Streamlit rerun?
2. What is the difference between an API-key configuration error and a network permission error?
3. Why does a single-elimination tournament need seven comparisons to choose one winner from eight albums?
4. What limitations arise from constructing a pairwise bracket from recommendation candidates?

## Topic: Offline Evaluation and Ablation

### Current Implementation

- `evaluate_recommendations.py:evaluate_recommendation_variants()` compares three deterministic lists over the accepted catalogue: embedding-only, embedding plus the existing tag/bridge signals, and the complete tiered ranking rules.
- Every method uses the same seed profile and a comparable result limit (up to three tiers × the requested per-tier count). The full method may return fewer results when a tier has no eligible albums.
- The report calculates mean profile similarity, mean pairwise cosine distance (a simple diversity proxy), unique lead-artist count, top-artist share, list overlap, and displayed-tier similarity means.
- `EVALUATION_REPORT_V2.md` lists the actual candidates for manual bad-case review; `.json` preserves their IDs and numeric signals for later inspection.
- There is no ground-truth preference label in this offline test. Metrics describe list properties, not recommendation accuracy or what users will like. The script does not call Gemini.

### Questions I Should Be Able to Answer

- What question does an ablation answer, and which signals differ between these three variants?
- Why does the embedding-plus-tags baseline use the existing Safe score?
- What does mean pairwise cosine distance say about diversity, and what does it not say?
- How can artist concentration expose a catalog or ranking issue?
- Why can this report not tell us which ranking is best for real users?

### Interview Questions

1. How would you use explicit like/dislike or Taste Battle labels to evaluate ranking quality?
2. What bias would arise if you only evaluated albums already selected by the current recommender?
3. How would you change the report to compare several seed profiles reproducibly?
4. Why should you not interpret higher diversity as automatically better recommendations?

## Topic: Deployment Readiness and Runtime Boundaries

### Current Implementation

- `app.py` reads a hosted Gemini key from Streamlit secrets and otherwise lets `rag.py` resolve the environment or local `.env` value. Recommendations do not require a Gemini key.
- `load_resources()` caches the catalogue documents and local vectors once per app process. This is deliberate because behavior events update the same SQLite file; restart Streamlit after changing catalogue data.
- `ensure_behavior_schema()` applies the idempotent schema once per database path and `SCHEMA_REVISION` per process. Increment the revision when the SQL schema changes.
- `AI_TASTE_DATABASE_PATH` lets the app and ingestion pipeline use a host-provided persistent file path. The database itself is excluded from Git and must be provisioned separately.
- `get_behavior_storage_mode()` reads `AI_TASTE_BEHAVIOR_STORAGE` from the environment or Streamlit secrets. Local development defaults to `persistent`; the V2 hosted Beta is intended to use `supabase`.
- `fetch_reviews()` stores CritiqueBrainz reviewer display names and license-info URLs when provided; `initialize_database()` adds those nullable columns to older SQLite files without rewriting review text.
- RAG source metadata carries the reviewer and license link through to the evidence/source expander. Existing stored rows remain unattributed until refreshed from the API.
- In `session` mode, selected seeds and recommendation impressions do not enter SQLite. Like/dislike feedback and Taste Battle choices live in `st.session_state` only and disappear when the app session ends or the app restarts. In `supabase` mode, opted-in events are sent to the separate hosted Postgres store.
- Taste Battle reads the latest choice per unordered pair for the selected route so a deterministic knockout bracket can resume in either storage mode.
- The earlier V1 Streamlit demo was deployed. The current V2 candidate is not yet on the hosted app; its Supabase schema is applied, but Streamlit secrets still need to be configured before event collection can start.

### Questions I Should Be Able to Answer

- Why should a browser-facing app read API secrets from the host rather than expose them in source code?
- Why did writing one anonymous event previously cause expensive embedding work to repeat?
- What is the difference between a per-process cache and durable database storage?
- What will happen to SQLite behavior rows if the hosting filesystem is ephemeral?
- What changes between `persistent` and `session` behavior-storage modes?
- Which user events are omitted in session mode, and which can still be used during the current visit?
- Why is Streamlit session state suitable for temporary interaction state but not a behavior dataset?
- Why is a non-empty review license field not, by itself, enough to confirm deployment readiness?
- Which attribution fields does the app retain for each CritiqueBrainz review, and why can older rows still be missing them?

### Interview Questions

1. How would you safely provision a read-mostly catalogue and writable user-event store?
2. What operational trade-offs does SQLite make for a low-traffic Beta?
3. What should be monitored when model/API calls are triggered by public users?
4. How would you test that an app restart preserves the data you intend to keep?
5. What evaluation questions can no longer be answered if public behavior events are not persisted?

## Topic: Review Attribution and Provenance

### Current Implementation

- `ingest.fetch_reviews()` reads the CritiqueBrainz reviewer display name and license-info URL when available, alongside the review ID, license ID, and source URL.
- `schema.sql` stores `reviewer_name` and `license_url` as nullable review metadata. `behavior.initialize_database()` adds these columns to an older database without replacing its review text.
- `rag.load_review_chunks()` carries attribution metadata with each retrieved chunk; `app.py` shows the reviewer and license link in the evidence/source expanders.
- Existing rows are not backfilled automatically. Re-ingestion or a dedicated metadata refresh is still needed before their attribution fields are populated.

### Questions I Should Be Able to Answer

- What is the difference between the review's original `source_url` and its CritiqueBrainz review ID?
- Why store both a short license identifier and its official information URL?
- Why are reviewer and license-link columns nullable, and what happens to older rows after the migration?
- How does review provenance travel from the API response to the RAG evidence panel?
- Why does having attribution fields still not settle whether review text can be reused in a public app or sent to an LLM API?

### Interview Questions

1. How would you preserve provenance when transforming review text into chunks and embeddings?
2. How would you backfill missing attribution fields without refetching album metadata or deleting existing reviews?
3. What checks would you require before publishing a dataset containing third-party review text?

## Topic: Building a Deployment Catalogue Snapshot

### Current Implementation

- `prepare_deployment_catalog.py` reads only accepted release-group MBIDs from `album_match_manifest.json` and copies their album metadata, artist credits, and tags from the existing SQLite database.
- The source database is opened read-only. A temporary target is built, foreign keys are checked, then the finished file replaces `deployment/catalog.db`.
- Review text and behavior rows are omitted from this preview. `app.get_application_database_path()` reads a local environment value or Streamlit secret to select the database.

### Questions I Should Be Able to Answer

- Why is the accepted manifest the export boundary instead of copying every album row in `taste.db`?
- Why should a packaging script not make hundreds of upstream requests at app startup?
- How does a temporary output file protect the finished catalogue from a partial export?
- Why are behavior rows and review text omitted from this preview, and what product capability does that affect?
- What does `PRAGMA foreign_key_check` verify in the exported file?

### Interview Questions

1. How would you make a dataset export reproducible and safe to rerun?
2. How would you verify the export has no missing accepted records or orphan foreign keys?
3. What trade-offs arise when the public deployment uses a review-free catalogue while local development retains reviews?

## Topic: Data Provenance, Licensing, and Public Release

### Current Implementation

- The current accepted catalogue has 530 albums, 5,139 MusicBrainz tag rows,
  and 4,834 retained Last.fm candidate-tag rows. The local preview database is
  Git-ignored and has not been shared.
- `semantic_search.py:load_album_documents()` defaults to MusicBrainz tags and
  genres. The app creates album vectors at runtime, so changing the selected
  source changes both embedding inputs and tag-based recommendation signals;
  the app process must be restarted to clear its cached vectors.
- `ingest.fetch_cover()` stores remote Cover Art Archive URLs; it does not
  download artwork into SQLite. The default app path displays MusicBrainz tags;
  a future UI that explicitly displays Last.fm tags would need its attribution
  and catalogue links.
- The public preview excludes CritiqueBrainz reviews. The full local review
  corpus still needs a per-license/provenance review before public or Gemini
  reuse.
- `DATA_SOURCE_USAGE_AUDIT.md` summarizes the official provider terms reviewed
  and unresolved public-release decisions. It is a technical audit, not legal
  advice, and no provider has been contacted.

### Questions I Should Be Able to Answer

- Which exact fields in our catalogue come from each upstream provider?
- Why does the MusicBrainz core-data license not automatically cover tags,
  reviews, or cover images?
- What public-use conditions does the current Last.fm API agreement state?
- Why is storing a remote artwork URL different from storing the image itself,
  but still not a complete permission check for displaying it?
- If an upstream tag source or its values change, which downstream documents,
  embeddings, scores, explanations, and evaluation results need to be reviewed?
- What provenance needs to travel with review text and retrieved RAG chunks?

### Interview Questions

1. How would you represent data provenance at the field or record level in a
   multi-source catalogue?
2. Why can a technically successful API response still be unsuitable for
   redistribution in a public application?
3. How would you design a recommendation system so an uncertain data source can
   be disabled without losing the entire product?
4. Why should derived artifacts such as embeddings be included in a data-source
   removal plan?

## Topic: Offline Evaluation Across Taste Profiles

### Current Implementation

- `evaluate_recommendations.py` compares embedding-only, embedding-plus-tags,
  and the full tiered ranking over the same accepted 530-album catalogue.
- This smoke evaluation ran the script separately for four three-seed profiles:
  alt/electronic, contemporary pop, girl-group K-pop, and rap/Latin pop.
- Each report includes similarity by tier, diversity and artist-concentration
  diagnostics, and inspectable candidate lists. Reports are in
  `evaluation_profiles/` and are linked from `EVALUATION.md`.
- The runs are deterministic and make no Gemini or Last.fm API calls. They
  reveal candidate lists to review; they do not measure whether a person likes
  the recommendations because the catalogue has no ground-truth labels.

### Questions I Should Be Able to Answer

- Why run the same evaluation on different seed profiles instead of only one?
- What does `Safe ≥ Explore ≥ Wildcard` mean in this report, and what does it
  fail to prove?
- How do mean pairwise cosine distance and top-artist share describe different
  properties of a recommendation list?
- Why can two albums by the same artist be either useful discovery or unwanted
  repetition, depending on the listener and tier?
- Why do noisy tags matter even when the tier-similarity ordering looks right?

### Interview Questions

1. Why is this multi-profile report a smoke test rather than a benchmark?
2. How would you collect labels to tell whether users find Safe, Explore, and
   Wildcard recommendations satisfying?
3. What experiment could test an artist-diversity rule without assuming it is
   always better?
4. How could you evaluate tag filtering separately from embedding similarity
   while keeping seed profiles and candidate catalogues constant?

## Topic: Anonymous Product Analytics

### Current Implementation

- supabase/migrations/202610010001_behavior_analytics.sql defines separate
  Postgres tables for sessions, selected seed albums, recommendation lists and
  scores, explicit feedback, and Taste Battle choices.
- supabase_behavior.py writes events through Supabase REST from the Streamlit
  server. The secret key comes from Streamlit Secrets and is never sent to
  browser-side code.
- app.py asks for consent before writing behavior data. With
  AI_TASTE_BEHAVIOR_STORAGE=supabase, album selection, recommendation display,
  feedback, and pairwise choices are saved remotely. The catalogue stays in
  SQLite.
- The Supabase migration was applied and verified on 2026-10-01: all five
  tables exist and have row-level security enabled. The hosted Streamlit
  secrets and V2 deployment are still pending, so the project has collected no
  remote events yet.
- supabase/analysis_queries.sql contains starter queries for profile
  completion, feedback by tier, popular seed albums, and pairwise outcomes.

### Questions I Should Be Able to Answer

- Why is the catalogue separate from the behavior database?
- What events does one opted-in visitor create, and which user details are not collected?
- Why are feedback changes appended instead of overwriting the previous value?
- What does the secret API key allow, and why must the Streamlit server keep it private?
- What does row-level security protect here, and which database role does the server use?
- Why does a rendered recommendation list not prove that every card entered the user's viewport?
- How can feedback rate by tier be computed from impressions and feedback events?
- Why are these events for evaluation rather than model training?

### Interview Questions

1. How would you calculate recommendation feedback rate without counting a like as a view?
2. How would you detect that Explore performs better for one taste segment but worse for another?
3. What changes would be needed to add a data deletion request without collecting identity?
4. How would you validate that public visitors can neither write to nor read analytics tables directly?
5. Why might a small number of pairwise choices be useful evidence but not a reliable quality claim?
