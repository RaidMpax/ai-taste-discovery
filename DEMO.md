# Historical V1 Demo Guide

The example rankings below were checked against the original 30-album V1
sample. V2 now uses 530 selected albums, so titles and ranks can differ; inspect
the live results rather than promising these exact outputs.

Target length: 3–5 minutes. Use `OK Computer` and `Homogenic` as the favorite
albums and display three recommendations per tier.

## Before the demo

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Confirm that album covers load and that `GEMINI_API_KEY` is configured in the
environment, local `.env`, or Streamlit secrets if live generation will be
shown. Never display a secrets file on screen.

## Demo route

1. **Problem — 20 seconds**
   Explain that ordinary recommendation lists say what to play, but rarely show
   where the connection comes from. This prototype exposes both the familiar
   bridge and the new direction.

2. **Taste Profile — 45 seconds**
   Select `OK Computer` and `Homogenic`. Point out that the profile is built by
   averaging their normalized album embeddings and separately displaying their
   recurring community tags. The profile is a current-session summary, not a
   permanent verdict about the listener.

3. **Three distances — 90 seconds**
   Set the result count to 3 and compare the tiers:

   - Safe: `Dummy` retains 90s, electronic, and trip-hop signals.
   - Explore: `Discovery` keeps electronic/electronica while adding dance,
     French, and French house.
   - Wildcard: `Untrue` keeps an alternative/electronic bridge while adding
     2-step, ambient, atmospheric, and dubstep.

   State clearly that Python rules assign these tiers. Gemini does not choose
   or rank the albums.

4. **Why This? — 60 seconds**
   Return to Safe and open `Dummy`. Explain the visible pipeline:

   `candidate + favorites → retrieve licensed review chunks → build context → Gemini → validate citations`

   Show the explanation, limitations, and source section. Point out that source
   URLs and IDs come from the application, not from the model.

5. **Limitations — 30 seconds**
   The 530-album catalogue has incomplete licensed-review coverage. Evaluation
   metrics describe list properties rather than user preference, and this guide
   is still a V1 walkthrough. The V2 candidate and Supabase integration have
   not yet been published to the hosted app; see `DEPLOYMENT_READINESS.md`.

## If Gemini is unavailable

The recommendation system still works. Show the bridge and new tags in the UI,
then run this local retrieval command if evidence retrieval needs to be
demonstrated without an LLM call:

```powershell
.\.venv\Scripts\python.exe rag.py `
  --favorite "Homogenic" `
  --candidate "Dummy" `
  --top-k 2
```

This prints the exact RAG context and sources without using Gemini.

## One-sentence architecture

MusicBrainz, Cover Art Archive, Last.fm, and licensed CritiqueBrainz data are
cleaned into SQLite; local embeddings and transparent rules retrieve and rank
candidates; Gemini only explains retrieved evidence through validated
structured output.
