-- AI Taste Discovery: anonymous product-behavior analytics.
-- The music catalogue stays in the existing read-only SQLite database.
-- The Streamlit server writes to these tables using a server-side secret.

create table if not exists public.sessions (
    session_id uuid primary key,
    consent_version text not null,
    app_version text not null default 'v2-beta',
    created_at timestamptz not null default now()
);

create table if not exists public.taste_profile_events (
    profile_event_id uuid primary key,
    session_id uuid not null references public.sessions(session_id),
    seed_album_mbids text[] not null,
    algorithm_version text not null default 'v2-beta',
    created_at timestamptz not null default now(),
    constraint taste_profile_seed_count
        check (cardinality(seed_album_mbids) between 1 and 10)
);

create table if not exists public.recommendation_impressions (
    impression_id uuid primary key,
    session_id uuid not null references public.sessions(session_id),
    profile_event_id uuid not null
        references public.taste_profile_events(profile_event_id),
    release_group_mbid text not null,
    tier text not null check (tier in ('Safe', 'Explore', 'Wildcard')),
    rank integer not null check (rank > 0),
    profile_similarity double precision,
    bridge_similarity double precision,
    safe_score double precision,
    explore_score double precision,
    wildcard_score double precision,
    novelty_ratio double precision,
    created_at timestamptz not null default now()
);

-- Feedback is append-only so a changed like/dislike remains visible as an event.
create table if not exists public.recommendation_feedback_events (
    feedback_event_id uuid primary key,
    session_id uuid not null references public.sessions(session_id),
    profile_event_id uuid not null
        references public.taste_profile_events(profile_event_id),
    release_group_mbid text not null,
    tier text not null check (tier in ('Safe', 'Explore', 'Wildcard')),
    feedback text not null check (feedback in ('like', 'dislike')),
    created_at timestamptz not null default now()
);

create table if not exists public.taste_battle_events (
    battle_event_id uuid primary key,
    session_id uuid not null references public.sessions(session_id),
    profile_event_id uuid not null
        references public.taste_profile_events(profile_event_id),
    album_a_mbid text not null,
    album_b_mbid text not null,
    chosen_album_mbid text not null,
    generation_strategy text not null check (
        generation_strategy in (
            'safe_vs_explore',
            'explore_vs_wildcard',
            'similarity_vs_tag_overlap'
        )
    ),
    created_at timestamptz not null default now(),
    constraint taste_battle_distinct_albums check (album_a_mbid <> album_b_mbid),
    constraint taste_battle_winner_is_a_participant
        check (chosen_album_mbid in (album_a_mbid, album_b_mbid))
);

create index if not exists idx_taste_profiles_session_created
    on public.taste_profile_events (session_id, created_at);
create index if not exists idx_taste_profiles_created
    on public.taste_profile_events (created_at);
create index if not exists idx_impressions_profile_tier_created
    on public.recommendation_impressions (profile_event_id, tier, created_at);
create index if not exists idx_impressions_album_tier
    on public.recommendation_impressions (release_group_mbid, tier);
create index if not exists idx_feedback_profile_album_created
    on public.recommendation_feedback_events
        (profile_event_id, release_group_mbid, created_at);
create index if not exists idx_battles_profile_strategy_created
    on public.taste_battle_events
        (profile_event_id, generation_strategy, created_at);

-- Visitors cannot read or write these tables directly. The Streamlit Python
-- server uses SUPABASE_SECRET_KEY from Secrets; never put that key in
-- browser code, repository files, logs, or user-facing output.
alter table public.sessions enable row level security;
alter table public.taste_profile_events enable row level security;
alter table public.recommendation_impressions enable row level security;
alter table public.recommendation_feedback_events enable row level security;
alter table public.taste_battle_events enable row level security;

revoke all on table public.sessions from public, anon, authenticated;
revoke all on table public.taste_profile_events from public, anon, authenticated;
revoke all on table public.recommendation_impressions from public, anon, authenticated;
revoke all on table public.recommendation_feedback_events from public, anon, authenticated;
revoke all on table public.taste_battle_events from public, anon, authenticated;

-- Restrict the app's backend role to the operations it actually needs.
revoke all on table public.sessions from service_role;
revoke all on table public.taste_profile_events from service_role;
revoke all on table public.recommendation_impressions from service_role;
revoke all on table public.recommendation_feedback_events from service_role;
revoke all on table public.taste_battle_events from service_role;

grant insert on table public.sessions to service_role;
grant insert on table public.taste_profile_events to service_role;
grant insert on table public.recommendation_impressions to service_role;
grant insert on table public.recommendation_feedback_events to service_role;
grant select, insert on table public.taste_battle_events to service_role;
