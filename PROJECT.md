# AI Taste Discovery

## V0.1 goal

Build a small music discovery prototype from 30–50 albums. Given albums a user
likes, it creates a session-only Taste Profile and returns three kinds of
recommendations:

- **Safe**: close to the user's current taste.
- **Explore**: keeps familiar traits while introducing an adjacent area.
- **Wildcard**: farther away, but connected by clear evidence.

Each recommendation should answer **Why This?** using retrieved metadata,
community tags, and review text rather than unsupported LLM claims. Sources
must be visible.

## V0.1 data sources

- MusicBrainz: artist, release group, year, MBIDs, basic metadata
- Cover Art Archive: album covers
- Last.fm: community tags
- CritiqueBrainz: review text and review metadata
- SQLite: curated catalogue data; V0.1 user choices remain in the UI session

## Technical approach

Python, SQLite, SQL, embeddings, vector search, an LLM API, explicit RAG
orchestration, structured output, and a Streamlit UI. V0.1 deliberately
does not use LangChain, LlamaIndex, agents, or a large dataset.

## Current milestone: V0.1 finalization

The 30-album prototype now covers ingestion, SQLite storage, local embeddings,
Taste Profile construction, deterministic recommendation tiers, licensed review
retrieval, Gemini structured explanations, source validation, evaluation, and a
minimal Streamlit UI. Remaining work is final documentation, regression review,
and presentation cleanup rather than new product scope.
