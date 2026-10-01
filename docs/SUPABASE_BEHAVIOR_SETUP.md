# User Behavior Data Setup

This adds a durable store for anonymous product events. The album catalogue
stays in the existing MusicBrainz-only SQLite snapshot. The event schema does
not store names, emails, IP addresses, prompts, or generated explanation text.

## Data model

- **sessions**: random session ID and the consent notice version.
- **taste_profile_events**: selected album MBIDs and recommendation algorithm version.
- **recommendation_impressions**: albums shown, tier, rank, and ranking signals.
- **recommendation_feedback_events**: append-only like/dislike changes.
- **taste_battle_events**: each pairwise choice and how the pair was generated.

The SQL dashboard can run the example queries in
supabase/analysis_queries.sql.
You can inspect raw rows in **Table Editor** and run the analysis queries in
**SQL Editor**.

## Create the Supabase database

1. Create a Supabase project on the account you want to own the project.
2. Open **SQL Editor** in its dashboard.
3. Run supabase/migrations/202610010001_behavior_analytics.sql.
4. In **Project Settings → API Keys**, create or copy a **secret key**. Keep
   this key private; it bypasses RLS. Use a dedicated Supabase project for
   these behavior tables.
5. Add these values to Streamlit Community Cloud's **App settings → Secrets**:

       AI_TASTE_BEHAVIOR_STORAGE = "supabase"
       SUPABASE_URL = "https://ogypwrsqoccdzvapways.supabase.co"
       SUPABASE_SECRET_KEY = "YOUR-SUPABASE-SECRET-KEY"

   Do not send the key in chat, put it in a GitHub file, or use it in
   browser-side JavaScript. The Streamlit Python process is the only component
   that should receive it. Use the new secret-key format from Supabase's API
   Keys page rather than the legacy service_role JWT key.

## Current implementation status

The migration, analysis queries, and server-side event writer are prepared.
On 2026-10-01 the migration was applied in the project dashboard and verified:
all five tables exist with row-level security enabled. No behavior rows have
been collected yet. The V2 code is published on the public GitHub `v2-beta`
branch and the hosted app now loads from that branch. It needs the following
secrets before Gemini features and opted-in events can work:

       AI_TASTE_BEHAVIOR_STORAGE = "supabase"
       SUPABASE_URL = "https://ogypwrsqoccdzvapways.supabase.co"
       SUPABASE_SECRET_KEY = "YOUR-SUPABASE-SECRET-KEY"
       GEMINI_API_KEY = "YOUR-GEMINI-API-KEY"

Add them only in Streamlit Community Cloud's App settings → Secrets, never in
Git or chat. The secret Supabase API key is sent in the `apikey` header by the
server-side writer.

