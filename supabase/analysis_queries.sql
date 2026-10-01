-- 1. Overall volume
select
    (select count(*) from public.sessions) as sessions,
    (select count(*) from public.taste_profile_events) as taste_profiles,
    (select count(*) from public.recommendation_impressions) as impressions,
    (select count(*) from public.recommendation_feedback_events) as feedback_events,
    (select count(*) from public.taste_battle_events) as battle_choices;

-- 2. Profile completion among sessions that agreed to anonymous analytics
select
    count(distinct s.session_id) as opted_in_sessions,
    count(distinct p.session_id) as sessions_with_a_profile,
    round(
        100.0 * count(distinct p.session_id)
        / nullif(count(distinct s.session_id), 0),
        1
    ) as profile_completion_percent
from public.sessions s
left join public.taste_profile_events p using (session_id);

-- 3. Latest explicit response per rendered candidate, summarized by tier.
-- A row means the list was rendered; it does not prove the card entered view.
with shown as (
    select distinct session_id, profile_event_id, release_group_mbid, tier
    from public.recommendation_impressions
), latest_feedback as (
    select *, row_number() over (
        partition by session_id, profile_event_id, release_group_mbid, tier
        order by created_at desc, feedback_event_id desc
    ) as response_order
    from public.recommendation_feedback_events
)
select
    shown.tier,
    count(*) as unique_rendered_candidates,
    count(latest_feedback.feedback_event_id) as candidates_with_feedback,
    count(*) filter (where latest_feedback.feedback = 'like') as likes,
    count(*) filter (where latest_feedback.feedback = 'dislike') as dislikes,
    round(
        100.0 * count(*) filter (where latest_feedback.feedback = 'like')
        / nullif(count(latest_feedback.feedback_event_id), 0),
        1
    ) as like_rate_percent
from shown
left join latest_feedback
    on latest_feedback.session_id = shown.session_id
   and latest_feedback.profile_event_id = shown.profile_event_id
   and latest_feedback.release_group_mbid = shown.release_group_mbid
   and latest_feedback.tier = shown.tier
   and latest_feedback.response_order = 1
group by shown.tier
order by shown.tier;

-- 4. Most frequently selected seed albums
select
    seed.release_group_mbid,
    count(*) as seed_selections
from public.taste_profile_events p
cross join lateral unnest(p.seed_album_mbids) as seed(release_group_mbid)
group by seed.release_group_mbid
order by seed_selections desc
limit 30;

-- 5. Pairwise wins by generation strategy
select
    generation_strategy,
    count(*) as comparisons,
    count(*) filter (where chosen_album_mbid = album_a_mbid) as album_a_wins,
    count(*) filter (where chosen_album_mbid = album_b_mbid) as album_b_wins
from public.taste_battle_events
group by generation_strategy
order by generation_strategy;

-- 6. Recommendation candidates with the most likes/dislikes after display.
-- Deduplicate repeated reruns for the same session/profile/album/tier.
with shown as (
    select distinct session_id, profile_event_id, release_group_mbid, tier
    from public.recommendation_impressions
), latest_feedback as (
    select *, row_number() over (
        partition by session_id, profile_event_id, release_group_mbid, tier
        order by created_at desc, feedback_event_id desc
    ) as response_order
    from public.recommendation_feedback_events
)
select
    i.release_group_mbid,
    i.tier,
    count(*) as unique_session_profile_exposures,
    count(*) filter (where f.feedback = 'like') as likes,
    count(*) filter (where f.feedback = 'dislike') as dislikes
from shown i
left join latest_feedback f
    on f.session_id = i.session_id
   and f.profile_event_id = i.profile_event_id
   and f.release_group_mbid = i.release_group_mbid
   and f.tier = i.tier
   and f.response_order = 1
group by i.release_group_mbid, i.tier
order by likes desc, unique_session_profile_exposures desc
limit 50;
