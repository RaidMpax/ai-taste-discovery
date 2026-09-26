# AI Taste Discovery

## V0.1 goal

Build a small music discovery prototype from 30–50 albums. Given albums or
artists a user likes, it will create a Taste Profile and return three kinds of
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
- SQLite: curated work and user data (not created during Day 1)

## Technical approach

Python, SQLite, SQL, embeddings, vector search, an LLM API, explicit RAG
orchestration, structured output, and a later Streamlit UI. V0.1 deliberately
does not use LangChain, LlamaIndex, agents, or a large dataset.

## Current milestone: Day 3

Ingest the confirmed 10-album test catalogue into SQLite with transparent
source status reporting, idempotent writes, and safe handling of partial API
failures. Embeddings, retrieval, recommendation, RAG, and UI are not part of
this milestone.
