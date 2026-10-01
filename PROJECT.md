# AI Taste Discovery

## Current target: V2 friends-and-family Beta

The V1 prototype is complete. V2 is preparing a shareable music-discovery Beta
using the curated 530-album catalogue. The local app now builds a Taste Profile,
returns Safe / Explore / Wildcard recommendations, and supports Taste Analysis,
Why This?, anonymous feedback, and pairwise Taste Battle.

Recommendations, ranking, tiers, and citations remain determined and checked by
transparent Python code. Gemini only produces evidence-grounded explanations;
recommendations remain usable when Gemini is unavailable.

## Product goal

Given albums a listener likes, create a current-session Taste Profile and
recommend music at three exploration distances:

- **Safe**: close to the user's current taste.
- **Explore**: keeps familiar traits while introducing an adjacent area.
- **Wildcard**: farther away, but connected by clear evidence.

Each recommendation should answer **Why This?** using retrieved metadata,
community tags, and review evidence rather than unsupported LLM claims. Sources
must be visible. Offline ranking metrics are diagnostics only; the project does
not yet claim recommendation accuracy or train from the collected behavior.

## Data sources

- MusicBrainz: artist, release group, year, MBIDs, basic metadata, and the
  active/default album tags and genres
- Cover Art Archive: album covers
- Last.fm: retained candidate community tags; optional for ingestion and not
  used by the app's default profile/recommendation path
- CritiqueBrainz: review text and review metadata
- SQLite: curated catalogue and local behavior data
- Supabase: opt-in hosted behavior analytics for the public Beta

## Technical approach

Python, SQLite, SQL, local embeddings, NumPy cosine similarity, explicit RAG
orchestration, structured output, Gemini API, and Streamlit. The project does
not use LangChain, LlamaIndex, agents, or a trained recommendation model.

## Current status and boundary

The V2 candidate is implemented locally; the previously deployed Streamlit app
is still the earlier version until this branch is published and redeployed. The
530-album MusicBrainz-only catalogue is available as a separate GitHub Release
asset, and the Supabase behavior schema has been applied and verified. Hosted
Streamlit secrets are not configured yet, so V2 behavior collection has not
started. See `DEPLOYMENT_READINESS.md` for the remaining release checks. Review
attribution and intended-use compatibility still need a deployment-focused
review.
