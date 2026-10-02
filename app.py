"""Streamlit UI for the AI Taste Discovery V2 Beta prototype."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
import hashlib
from json import JSONDecodeError
import logging
import os
import sqlite3
import tempfile
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

import streamlit as st
from dotenv import load_dotenv

from behavior import (
    SCHEMA_REVISION,
    create_session,
    load_battle_choices,
    initialize_database,
    normalize_behavior_storage_mode,
    record_battle_choice,
    record_feedback,
    record_recommendation_impressions,
    record_taste_profile_event,
)
from rag import (
    build_context,
    build_taste_analysis_context,
    embed_chunks,
    generate_taste_analysis,
    generate_why_this,
    load_review_chunks,
)
from recommend import (
    build_battle_participants,
    candidate_features,
    choose_recommendations,
    resolve_battle_tournament,
)
from semantic_search import (
    DEFAULT_DATABASE,
    build_taste_profile,
    embed_documents,
    load_album_documents,
)
from supabase_behavior import SupabaseBehaviorError, SupabaseBehaviorStore


TIER_DETAILS = {
    "Safe": {
        "subtitle": "熟悉延伸",
        "description": "沿着熟悉的声音，再向外走一点。",
    },
    "Explore": {
        "subtitle": "相邻探索",
        "description": "留住熟悉的线索，也试试新的方向。",
    },
    "Wildcard": {
        "subtitle": "大胆跳跃",
        "description": "走远一些，但仍能找到清楚的连接。",
    },
}

BATTLE_STRATEGIES = {
    "safe_vs_explore": {
        "label": "熟悉延伸 vs 相邻探索",
        "description": "一边更熟悉，一边多走半步。",
    },
    "explore_vs_wildcard": {
        "label": "相邻探索 vs 大胆跳跃",
        "description": "比较保留熟悉线索的探索，和更远一点的选择。",
    },
    "similarity_vs_tag_overlap": {
        "label": "相似度接近，标签连接不同",
        "description": "两张专辑与品味向量相近，但和种子作品共享的桥接标签数不同。",
    },
}
logger = logging.getLogger(__name__)

PUBLIC_CATALOGUE_URL = (
    "https://github.com/RaidMpax/ai-taste-discovery/releases/download/"
    "catalogue-musicbrainz-2026-10-01/catalog_musicbrainz_only.db"
)
PUBLIC_CATALOGUE_SHA256 = (
    "9539cd5516251aeb4bc8dab183bed9f61f459def314fe709f058ba6979c05018"
)
MAX_CATALOGUE_DOWNLOAD_BYTES = 25 * 1024 * 1024
ANALYTICS_CONSENT_VERSION = "beta-2026-10-01"


@st.cache_resource
def get_taste_analysis_executor() -> ThreadPoolExecutor:
    """Keep one small worker alive across Streamlit script reruns."""
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="taste-analysis")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --moon: #f3f6ff;
            --paper: #ffffff;
            --ink: #101828;
            --muted: #667085;
            --line: #d7e2f2;
            --harbor: #3770bf;
            --fluorescent: #05a5fa;
            --ice: #8dc2ff;
            --herb: #cef26d;
            --peach: #ffb7a5;
            --butter: #ffe58a;
        }

        .stApp {
            background: var(--moon);
            color: var(--ink);
            color-scheme: light;
            font-family: "Avenir Next", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
        }

        [data-testid="stHeader"] { background: transparent; }
        #MainMenu, footer { visibility: hidden; }

        .main .block-container {
            max-width: 1180px;
            padding-top: 3rem;
            padding-bottom: 6rem;
        }

        .taste-hero {
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(280px, .65fr);
            align-items: end;
            gap: 32px;
            min-height: 250px;
            margin: 24px 0 80px;
            padding: 24px 0 32px;
            border-bottom: 1px solid rgba(55, 112, 191, .28);
        }

        .taste-hero::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 156px;
            height: 8px;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--fluorescent) 0 66%, var(--herb) 66%);
            transform-origin: left center;
            animation: shelf-line-grow .9s cubic-bezier(.22, 1, .36, 1) both;
        }

        @keyframes shelf-line-grow {
            from { opacity: .35; transform: scaleX(.35); }
            to { opacity: 1; transform: scaleX(1); }
        }

        .hero-title-wrap {
            padding-top: 34px;
        }

        .hero-title {
            max-width: 760px;
            margin: 0;
            color: #17375f;
            font-family: "Avenir Next", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
            font-size: clamp(3.45rem, 7.2vw, 6.4rem);
            font-weight: 720;
            letter-spacing: -.068em;
            line-height: .86;
        }

        .hero-note {
            max-width: 340px;
            padding: 28px 0 4px 28px;
            border-left: 6px solid var(--herb);
            color: var(--ink);
        }

        .hero-note p { margin: 0; }
        .hero-note-main {
            max-width: 310px;
            margin-bottom: 24px !important;
            color: var(--harbor);
            font-size: clamp(1.35rem, 2vw, 1.85rem);
            font-weight: 680;
            letter-spacing: -.035em;
            line-height: 1.16;
        }
        .hero-note-sub {
            max-width: 290px;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.7;
        }

        .section-heading {
            margin: 0 0 8px;
            color: var(--ink);
            font-size: clamp(1.8rem, 3vw, 2.55rem);
            font-weight: 680;
            letter-spacing: -.045em;
            line-height: 1.08;
        }

        .section-copy {
            max-width: 680px;
            margin: 0;
            color: var(--muted);
            font-size: 1.02rem;
            line-height: 1.65;
        }

        .st-key-selection_panel {
            margin-bottom: 72px;
            padding: 32px 32px 28px;
            border: 1px solid var(--line);
            border-radius: 28px;
            background: rgba(255, 255, 255, .92);
            box-shadow: 0 16px 44px rgba(55, 112, 191, .08);
        }

        .st-key-selection_panel [data-testid="stVerticalBlock"] { gap: 1rem; }

        div[data-baseweb="select"] > div {
            min-height: 54px;
            border: 1px solid #91add2 !important;
            border-radius: 16px;
            background: #ffffff !important;
            box-shadow: none;
        }
        div[data-baseweb="select"] > div:focus-within {
            border-color: var(--fluorescent);
            box-shadow: 0 0 0 4px rgba(5, 165, 250, .13);
        }
        .st-key-selection_panel [data-testid="stTextInput"] [data-baseweb="input"] > div,
        .st-key-selection_panel [data-testid="stTextInput"] [data-baseweb="base-input"] {
            border: 1px solid #91add2 !important;
            border-radius: 15px;
            background: #ffffff !important;
            box-shadow: none !important;
        }
        .st-key-selection_panel [data-testid="stTextInput"] [data-baseweb="input"]:focus-within > div,
        .st-key-selection_panel [data-testid="stTextInput"] [data-baseweb="base-input"]:focus-within {
            border: 2px solid var(--fluorescent) !important;
            box-shadow: 0 0 0 4px rgba(5, 165, 250, .13) !important;
        }

        [class*="st-key-selected_album_item_"] [data-testid="stVerticalBlockBorderWrapper"],
        [class*="st-key-album_search_result_"] [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 10px 12px;
            border-color: var(--line) !important;
            border-radius: 16px !important;
            background: #ffffff !important;
        }
        .selected-album-title,
        .search-result-title {
            color: var(--ink);
            font-size: .94rem;
            font-weight: 680;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }
        .selected-album-artist,
        .search-result-artist {
            margin-top: 3px;
            color: var(--muted);
            font-size: .8rem;
            line-height: 1.4;
            overflow-wrap: anywhere;
        }
        [class*="st-key-add_album_"] button {
            min-height: 38px;
            border-color: #9bb4d5 !important;
            border-radius: 999px;
            background: #f8fbff !important;
            color: #244e87 !important;
        }
        [class*="st-key-remove_album_"] button {
            min-height: 34px;
            min-width: 78px;
            padding: 0 10px !important;
            border-color: #c5d3e5 !important;
            border-radius: 999px;
            background: #ffffff !important;
            color: #476484 !important;
            font-size: .82rem;
        }

        [data-testid="stPills"] button,
        [data-testid="stSegmentedControl"] button {
            min-height: 42px;
            border: 1px solid #b9cae3 !important;
            border-radius: 999px !important;
            background: #ffffff !important;
            color: #244e87 !important;
            font-weight: 620;
        }
        [data-testid="stPills"] button[aria-pressed="true"],
        [data-testid="stSegmentedControl"] button[aria-pressed="true"] {
            border-color: var(--fluorescent) !important;
            background: var(--fluorescent) !important;
            color: #ffffff !important;
        }
        [data-testid="stPills"] button:hover,
        [data-testid="stSegmentedControl"] button:hover {
            border-color: var(--fluorescent) !important;
            background: #e5f4ff !important;
            color: #174f87 !important;
        }
        [data-testid="stPills"] button[aria-pressed="true"]:hover,
        [data-testid="stSegmentedControl"] button[aria-pressed="true"]:hover {
            background: #078ed4 !important;
            color: #ffffff !important;
        }

        .selected-shelf {
            margin-top: 8px;
            color: var(--muted);
            font-size: .88rem;
        }

        .album-shelf {
            display: flex;
            gap: 14px;
            overflow-x: auto;
            padding: 4px 2px 14px;
            scroll-snap-type: x mandatory;
            scrollbar-color: #9ab9df transparent;
        }
        .album-shelf-item {
            flex: 0 0 calc((100% - 42px) / 4);
            min-width: 150px;
            scroll-snap-align: start;
        }
        .album-shelf-item img,
        .album-shelf-missing {
            display: block;
            width: 100%;
            aspect-ratio: 1 / 1;
            border-radius: 16px;
            object-fit: cover;
            background: #e5edf8;
        }
        .album-shelf-missing {
            display: grid;
            place-items: center;
            color: #667085;
            font-size: .84rem;
        }
        .album-shelf-title {
            margin-top: 9px;
            color: var(--ink);
            font-size: .9rem;
            font-weight: 680;
            line-height: 1.35;
        }
        .album-shelf-artist {
            margin-top: 4px;
            color: var(--muted);
            font-size: .78rem;
            line-height: 1.35;
        }

        .st-key-profile_submit button {
            min-height: 46px;
            border-color: var(--harbor) !important;
            border-radius: 999px;
            background: var(--harbor) !important;
            color: #ffffff !important;
            font-weight: 680;
        }
        .st-key-profile_submit button:hover {
            border-color: #285b9f !important;
            background: #285b9f !important;
        }

        .st-key-profile_panel {
            margin: 24px 0 0;
            padding: 28px 30px;
            border: 1px solid rgba(55, 112, 191, .2);
            border-radius: 24px;
            background: #e5f1ff;
        }

        .st-key-battle_panel {
            margin: 28px 0;
            padding: 26px;
            border: 1px solid var(--line);
            border-radius: 26px;
            background: #ffffff;
            box-shadow: 0 12px 34px rgba(55, 112, 191, .06);
        }
        .st-key-battle_panel [data-testid="stImage"] {
            display: flex;
            justify-content: center;
        }
        .st-key-battle_panel [data-testid="stImage"] img {
            display: block;
            width: 100%;
            max-width: 240px !important;
            margin: 0 auto;
            aspect-ratio: 1 / 1;
            border-radius: 18px;
            object-fit: cover;
        }
        .st-key-battle_comparison [data-testid="stHorizontalBlock"] {
            display: grid !important;
            grid-template-columns: minmax(0, 1fr) 56px minmax(0, 1fr);
            align-items: center;
            gap: 16px !important;
        }
        .st-key-battle_comparison [data-testid="stColumn"] {
            width: auto !important;
            min-width: 0 !important;
            max-width: none !important;
            flex: none !important;
        }
        .st-key-battle_comparison .st-key-battle_album_a [data-testid="stVerticalBlockBorderWrapper"],
        .st-key-battle_comparison .st-key-battle_album_b [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 16px;
            border-color: var(--line) !important;
            border-radius: 22px !important;
            background: #ffffff !important;
        }
        .battle-album-title {
            margin-top: 10px;
            color: var(--ink);
            font-size: clamp(1.08rem, 1.6vw, 1.45rem);
            font-weight: 700;
            line-height: 1.2;
            overflow-wrap: anywhere;
        }
        .battle-album-artist {
            min-height: 2.7em;
            margin-top: 5px;
            color: var(--muted);
            font-size: .86rem;
            line-height: 1.45;
            overflow-wrap: anywhere;
        }
        .battle-vs {
            display: grid;
            width: 42px;
            height: 42px;
            place-items: center;
            border: 1px solid #d8e5c5;
            border-radius: 50%;
            background: #f5f9e9;
            color: #426a82;
            font-size: .76rem;
            font-weight: 750;
            letter-spacing: .04em;
        }
        .st-key-battle_panel [data-testid="stButton"] button {
            min-height: 44px;
            border-color: #91add2 !important;
            border-radius: 999px;
            background: #ffffff !important;
            color: #244e87 !important;
            font-weight: 650;
        }
        .st-key-battle_panel [data-testid="stButton"] button:hover {
            border-color: var(--harbor) !important;
            background: #edf5ff !important;
        }
        [data-testid="stTabs"] [role="tab"] {
            min-height: 48px;
            border-radius: 999px 999px 0 0;
            color: #52657f;
            font-weight: 650;
        }
        [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
            color: var(--harbor);
        }

        .profile-title {
            margin-bottom: 14px;
            color: var(--harbor);
            font-size: .95rem;
            font-weight: 700;
        }

        .tag-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .st-key-profile_panel .tag-row {
            margin-bottom: 16px;
        }

        .taste-tag {
            display: inline-flex;
            align-items: center;
            min-height: 30px;
            padding: 5px 11px;
            border: 1px solid rgba(55, 112, 191, .2);
            border-radius: 999px;
            background: rgba(255, 255, 255, .78);
            color: #244e87;
            font-size: .82rem;
            font-weight: 620;
        }

        .tier-intro {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 24px;
            margin: 32px 0 24px;
        }
        .tier-intro h2 {
            margin: 0 0 7px;
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -.045em;
        }
        .tier-intro p {
            max-width: 620px;
            margin: 0;
            color: var(--muted);
            line-height: 1.55;
        }

        .st-key-tier_selector {
            margin-top: 24px;
            padding: 14px;
            border: 1px solid var(--line);
            border-radius: 22px;
            background: #ffffff;
            box-shadow: 0 10px 28px rgba(55, 112, 191, .06);
        }

        [class*="st-key-recommendation_"] {
            height: 100%;
            padding: 12px;
            border: 1px solid var(--line);
            border-radius: 28px;
            background: #ffffff !important;
            box-shadow: 0 14px 38px rgba(55, 112, 191, .07);
        }
        [class*="st-key-recommendation_"] > div[data-testid="stVerticalBlockBorderWrapper"] {
            height: 100%;
            padding: 0;
            border: 0;
            border-radius: 0;
            background: transparent;
            box-shadow: none;
        }

        .tier-badge {
            display: inline-flex;
            align-items: center;
            min-height: 30px;
            margin: 4px 0 12px;
            padding: 5px 11px;
            border-radius: 999px;
            color: var(--ink);
            font-size: .78rem;
            font-weight: 720;
        }
        .tier-safe { background: var(--herb); }
        .tier-explore { background: var(--ice); }
        .tier-wildcard { background: var(--peach); }

        .recommendation-meta {
            margin: -6px 0 14px;
            color: var(--muted);
            font-size: .9rem;
        }
        .bridge-copy {
            margin: 6px 0 14px;
            color: #344054;
            line-height: 1.55;
        }
        .signal-label {
            margin: 14px 0 7px;
            color: var(--muted);
            font-size: .78rem;
            font-weight: 700;
        }
        .signal-tags {
            color: var(--ink);
            font-size: .92rem;
            line-height: 1.55;
        }

        [class*="st-key-recommendation_"] [data-testid="stImage"] img {
            aspect-ratio: 1 / 1;
            border-radius: 19px;
            object-fit: cover;
        }
        [class*="st-key-recommendation_"] h3 {
            margin-top: 6px;
            font-size: 1.55rem;
            letter-spacing: -.035em;
        }
        [class*="st-key-recommendation_"] [data-testid="stButton"] button {
            min-height: 46px;
            margin-top: 10px;
            border-color: var(--fluorescent) !important;
            border-radius: 999px;
            background: var(--fluorescent) !important;
            color: #ffffff !important;
            font-weight: 700;
        }
        [class*="st-key-collapse"] button {
            border-color: #91add2 !important;
            background: #ffffff !important;
            color: #244e87 !important;
        }
        [class*="st-key-feedback_"] [data-testid="stPills"] button {
            min-height: 30px;
            padding: 3px 12px;
            font-size: .78rem;
        }
        [class*="st-key-feedback_"] [data-testid="stCaption"] {
            margin-bottom: 3px;
        }

        .why-heading {
            margin: 24px 0 8px;
            color: var(--harbor);
            font-size: 1.2rem;
            font-weight: 720;
        }

        @media (max-width: 760px) {
            .main .block-container { padding-top: 1.4rem; }
            .taste-hero {
                grid-template-columns: 1fr;
                gap: 32px;
                min-height: 0;
                margin-bottom: 56px;
                padding-bottom: 36px;
            }
            .hero-title-wrap { padding-top: 34px; }
            .hero-title { font-size: clamp(3.2rem, 16vw, 5rem); }
            .hero-note {
                max-width: 100%;
                padding: 4px 0 4px 20px;
            }
            .hero-note-main { margin-bottom: 16px !important; }
            .st-key-selection_panel { padding: 24px 20px; }
            .st-key-per_tier_picker_v2,
            .st-key-per_tier_picker_v2 .stButtonGroup,
            .st-key-per_tier_picker_v2 [role="radiogroup"] {
                width: 100% !important;
                box-sizing: border-box;
            }
            .st-key-per_tier_picker_v2 [role="radiogroup"] {
                display: flex !important;
                justify-content: space-between;
                gap: 2px !important;
                overflow: visible;
            }
            .st-key-per_tier_picker_v2 [role="radiogroup"] > button {
                flex: 0 0 32px;
                width: 32px;
                min-width: 32px;
                height: 32px;
                min-height: 32px;
                padding: 0 !important;
            }
            [class*="st-key-recommendation_grid_"] [data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
                gap: 1rem !important;
            }
            [class*="st-key-recommendation_grid_"] [data-testid="stColumn"] {
                flex: 1 1 100% !important;
                max-width: 100% !important;
                min-width: 100% !important;
                width: 100% !important;
            }
            [class*="st-key-recommendation_grid_"] [class*="st-key-recommendation_"] h3 {
                font-size: 1.3rem;
                line-height: 1.25;
            }
            .album-shelf-item { flex-basis: calc((100% - 14px) / 2); }
            .st-key-battle_panel { padding: 20px; }
            .st-key-battle_comparison [data-testid="stHorizontalBlock"] {
                grid-template-columns: minmax(0, 1fr) 34px minmax(0, 1fr);
                gap: 6px !important;
            }
            .st-key-battle_comparison .st-key-battle_album_a [data-testid="stVerticalBlockBorderWrapper"],
            .st-key-battle_comparison .st-key-battle_album_b [data-testid="stVerticalBlockBorderWrapper"] {
                padding: 10px 8px;
            }
            .battle-album-title { font-size: 1rem; }
            .battle-album-artist { font-size: .74rem; }
            .battle-vs { width: 30px; height: 30px; font-size: .64rem; }
            .tier-intro { align-items: flex-start; flex-direction: column; }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                scroll-behavior: auto !important;
                animation-duration: .01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: .01ms !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="taste-hero">
          <div class="hero-title-wrap">
            <h1 class="hero-title">AI TASTE<br>DISCOVERY</h1>
          </div>
          <div class="hero-note">
            <p class="hero-note-main">Find the edge of your listening world.</p>
            <p class="hero-note-sub">从熟悉的声音出发，找到还没听过、却可能会喜欢的下一张专辑。</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_tags(tags: list[str]) -> None:
    if not tags:
        st.caption("暂时没有足够的标签信号。")
        return
    markup = "".join(
        f'<span class="taste-tag">{escape(tag)}</span>' for tag in tags
    )
    st.markdown(f'<div class="tag-row">{markup}</div>', unsafe_allow_html=True)


def render_album_shelf(albums: list[dict]) -> None:
    """Show confirmed seed records in a fixed-width, horizontally scrollable shelf."""
    cards = []
    for album in albums:
        title = escape(album["title"])
        artist = escape(" / ".join(album["artists"]))
        cover_url = album.get("cover_url")
        cover = (
            f'<img src="{escape(cover_url, quote=True)}" alt="{title} album cover" loading="lazy">'
            if cover_url
            else '<div class="album-shelf-missing">封面暂缺</div>'
        )
        cards.append(
            '<div class="album-shelf-item" role="listitem">'
            f"{cover}<div class=\"album-shelf-title\">{title}</div>"
            f'<div class="album-shelf-artist">{artist}</div></div>'
        )
    st.markdown(
        '<div class="selected-shelf">已选唱片 · 横向滑动查看</div>'
        f'<div class="album-shelf" role="list" aria-label="已确认的喜欢专辑">'
        f'{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def add_album_to_selection(release_group_mbid: str) -> None:
    """Add one explicit search result without coupling it to the query text."""
    selected = list(st.session_state.get("draft_favorite_mbids", []))
    if release_group_mbid not in selected and len(selected) < 10:
        selected.append(release_group_mbid)
    st.session_state["draft_favorite_mbids"] = selected
    st.session_state["album_search_query"] = ""


def remove_album_from_selection(release_group_mbid: str) -> None:
    """Remove a selected album only after its dedicated remove action."""
    selected = list(st.session_state.get("draft_favorite_mbids", []))
    st.session_state["draft_favorite_mbids"] = [
        mbid for mbid in selected if mbid != release_group_mbid
    ]


def format_gemini_error(error: Exception) -> str:
    """Turn provider/network failures into safe, actionable UI copy."""
    message = str(error).casefold()
    if isinstance(error, JSONDecodeError):
        return (
            "Gemini 返回的结构化内容无法解析，已安全跳过这次品味分析。"
            "结构化品味档案和推荐仍可使用，可以稍后重试。"
        )
    if "unknown source ids" in message:
        return (
            "Gemini 返回了检索结果中不存在的引用，来源校验已拦截这次品味分析。"
            "结构化品味档案和推荐仍可使用，可以稍后重试。"
        )
    if "unsupported consensus language" in message:
        return (
            "Gemini 使用了当前证据无法支持的概括性表述，内容校验已拦截这次品味分析。"
            "结构化品味档案和推荐仍可使用，可以稍后重试。"
        )
    if "winerror 10013" in message or "10013" in message:
        return (
            "当前运行环境的网络策略拒绝了 Gemini API 连接（WinError 10013）。"
            "这不是专辑数据或推荐逻辑错误；结构化品味档案和推荐仍可使用。"
            "请在允许 Python 访问外网的本机终端启动应用后重试。"
        )
    if "gemini_api_key is not configured" in message:
        return (
            "没有读取到 GEMINI_API_KEY。请检查本机 .env 或托管环境的 Secrets；"
            "结构化品味档案和推荐仍可使用。"
        )
    if any(marker in message for marker in ("429", "rate limit", "too_many_requests")):
        return "Gemini 免费额度或请求频率暂时受限。稍后可以重试；推荐仍可使用。"
    if "timeout" in message or "timed out" in message:
        return "连接 Gemini 超时。稍后重试即可；结构化品味档案和推荐仍可使用。"
    if isinstance(error, ValueError):
        return (
            "Gemini 返回内容未通过结构化或来源校验，已安全跳过这次品味分析。"
            "结构化品味档案和推荐仍可使用，可以稍后重试。"
        )
    return (
        f"Gemini 暂时无法生成说明（{type(error).__name__}）。"
        "结构化品味档案和推荐仍可使用，可以稍后重试。"
    )


def get_streamlit_gemini_api_key() -> str | None:
    """Read the optional hosted secret without requiring a local secrets file."""
    try:
        value = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def get_behavior_storage_mode() -> str:
    """Use local SQLite by default; deployments may select Supabase or session mode."""
    load_dotenv()
    mode = os.getenv("AI_TASTE_BEHAVIOR_STORAGE", "").strip()
    if not mode:
        try:
            mode = str(st.secrets.get("AI_TASTE_BEHAVIOR_STORAGE", "")).strip()
        except Exception:
            mode = ""
    return normalize_behavior_storage_mode(mode or None)


def get_app_setting(name: str, default: str = "") -> str:
    """Read a setting from the environment first, then Streamlit secrets."""
    load_dotenv()
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value.strip() if isinstance(value, str) and value.strip() else default


def get_supabase_behavior_store() -> SupabaseBehaviorStore:
    """Create the server-side event writer from private deployment secrets."""
    project_url = get_app_setting("SUPABASE_URL")
    secret_key = get_app_setting("SUPABASE_SECRET_KEY")
    if not project_url or not secret_key:
        raise SupabaseBehaviorError(
            "Supabase behavior storage is missing its hosted settings."
        )
    return SupabaseBehaviorStore(project_url, secret_key)


def get_application_database_path() -> Path:
    """Resolve the catalogue path from local environment or hosted secrets."""
    configured_path = get_app_setting("AI_TASTE_DATABASE_PATH")
    if not configured_path:
        return DEFAULT_DATABASE

    path = Path(configured_path).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path.resolve()


def ensure_application_database(database_path: Path) -> Path:
    """Download the pinned public catalogue only when the local file is absent."""
    if database_path.is_file():
        return database_path

    url = get_app_setting("AI_TASTE_DATABASE_URL", PUBLIC_CATALOGUE_URL)
    expected_sha256 = get_app_setting(
        "AI_TASTE_DATABASE_SHA256", PUBLIC_CATALOGUE_SHA256
    ).lower()
    if not url.startswith("https://"):
        raise ValueError("AI_TASTE_DATABASE_URL must use HTTPS")
    if len(expected_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in expected_sha256
    ):
        raise ValueError("AI_TASTE_DATABASE_SHA256 must be a 64-character hex digest")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    digest = hashlib.sha256()
    total_bytes = 0
    try:
        request = Request(url, headers={"User-Agent": "AI-Taste-Discovery"})
        with urlopen(request, timeout=30) as response:
            with tempfile.NamedTemporaryFile(
                prefix=f".{database_path.name}.",
                suffix=".download",
                dir=database_path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                while chunk := response.read(64 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > MAX_CATALOGUE_DOWNLOAD_BYTES:
                        raise ValueError("Catalogue download exceeded the size limit")
                    digest.update(chunk)
                    temporary_file.write(chunk)

        if total_bytes == 0:
            raise ValueError("Catalogue download was empty")
        if digest.hexdigest() != expected_sha256:
            raise ValueError("Catalogue download checksum did not match")
        os.replace(temporary_path, database_path)
        temporary_path = None
        return database_path
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


APP_DATABASE = get_application_database_path()


@st.cache_resource
def ensure_behavior_schema(database_path: str, schema_revision: int) -> str:
    """Apply additive behavior tables once per database and app revision."""
    del schema_revision  # Included in the cache key to rerun after schema changes.
    initialize_database(Path(database_path))
    return database_path


@st.cache_resource(show_spinner="正在加载专辑与 Embedding…")
def load_resources() -> dict:
    """Load the curated catalogue once; behavior events may use a separate store."""
    deployment_manifest = (
        Path(__file__).resolve().parent
        / "deployment"
        / "accepted_album_manifest.json"
    )
    documents = load_album_documents(APP_DATABASE, manifest_path=deployment_manifest)
    album_vectors = embed_documents(documents)
    review_chunks = load_review_chunks(APP_DATABASE)
    review_model, review_vectors = embed_chunks(review_chunks)
    return {
        "documents": documents,
        "album_vectors": album_vectors,
        "review_chunks": review_chunks,
        "review_model": review_model,
        "review_vectors": review_vectors,
    }


def show_explanation(result: dict) -> None:
    explanation = result["explanation"]
    st.markdown('<div class="why-heading">为什么推荐它？</div>', unsafe_allow_html=True)
    st.write(explanation["why_this"])
    st.markdown("**熟悉的连接**")
    st.write(explanation["familiar_connection"])
    st.markdown("**新的方向**")
    st.write(explanation["new_direction"])

    st.markdown("**还不确定的地方**")
    st.write(explanation["limitations"])

    with st.expander("查看证据与来源"):
        st.markdown("**证据片段**")
        for item in explanation["evidence"]:
            st.write(item["claim"])
            source_ids = ", ".join(item["source_ids"]) or "专辑与标签信号"
            st.caption(f"引用编号：{source_ids}")
        st.markdown("**来源**")
        if not result["sources"]:
            st.caption("没有可用评论；本次解释仅使用结构化标签。")
        for source in result["sources"]:
            st.markdown(
                f"- [{source['album_title']} / {source['source']}]"
                f"({source['source_url']})"
            )
            reviewer = source.get("reviewer_name") or "作者未提供"
            license_url = source.get("license_url")
            license_label = source["license"]
            license_credit = (
                f"[{license_label}]({license_url})"
                if license_url
                else license_label
            )
            st.caption(
                f"作者：{reviewer} · 许可：{license_credit} · "
                f"{source['source_id']}"
            )


def show_taste_analysis(result: dict) -> None:
    analysis = result["analysis"]
    st.write(analysis["overall_taste"])
    if analysis.get("limitations"):
        st.caption(f"说明：{analysis['limitations']}")
    with st.expander("查看分析依据与来源"):
        if not analysis["evidence"]:
            st.caption("本次没有单独列出的证据主张。")
        for item in analysis["evidence"]:
            st.write(item["claim"])
            st.caption(
                "来源：" + (", ".join(item["source_ids"]) or "结构化专辑与标签信号")
            )
        for source in result["sources"]:
            st.markdown(
                f"- [{source['album_title']} / {source['source']}]"
                f"({source['source_url']})"
            )
            reviewer = source.get("reviewer_name") or "作者未提供"
            license_url = source.get("license_url")
            license_label = source["license"]
            license_credit = (
                f"[{license_label}]({license_url})"
                if license_url
                else license_label
            )
            st.caption(
                f"作者：{reviewer} · 许可：{license_credit} · "
                f"{source['source_id']}"
            )


def _create_taste_analysis_result(
    profile: dict,
    review_chunks: list[dict],
    review_vectors,
    review_model,
    api_key: str | None,
) -> dict:
    """Build the optional Gemini explanation away from Streamlit's UI thread."""
    context_result = build_taste_analysis_context(
        profile,
        review_chunks,
        review_vectors,
        review_model,
    )
    return {
        "analysis": generate_taste_analysis(
            context_result,
            api_key=api_key,
        ),
        "sources": context_result["sources"],
    }


def queue_taste_analysis(
    profile_signature: str,
    profile: dict,
    resources: dict,
    api_key: str | None,
) -> None:
    """Start one background analysis job for this confirmed profile."""
    analysis_key = f"taste_analysis::{profile_signature}"
    error_key = f"taste_analysis_error::{profile_signature}"
    future_key = f"taste_analysis_future::{profile_signature}"
    if analysis_key in st.session_state or error_key in st.session_state:
        return

    existing_future = st.session_state.get(future_key)
    if existing_future is not None and not existing_future.cancelled():
        return

    st.session_state[future_key] = get_taste_analysis_executor().submit(
        _create_taste_analysis_result,
        profile,
        resources["review_chunks"],
        resources["review_vectors"],
        resources["review_model"],
        api_key,
    )


@st.fragment(run_every="1s")
def render_taste_analysis_status(profile_signature: str) -> None:
    """Poll the background job without rerunning or delaying recommendations."""
    analysis_key = f"taste_analysis::{profile_signature}"
    error_key = f"taste_analysis_error::{profile_signature}"
    future_key = f"taste_analysis_future::{profile_signature}"

    if analysis_key in st.session_state:
        show_taste_analysis(st.session_state[analysis_key])
        return

    if error_key in st.session_state:
        st.warning(st.session_state[error_key])
        if st.button(
            "重试品味分析",
            key=f"retry_taste_analysis::{profile_signature}",
            width="content",
        ):
            st.session_state.pop(error_key, None)
            st.session_state.pop(future_key, None)
            st.session_state["analysis_pending_signature"] = profile_signature
            st.rerun()
        return

    future = st.session_state.get(future_key)
    if future is None:
        st.caption("品味观察还没开始；推荐已经可以先看。")
    elif not future.done():
        st.caption("我在整理你的听歌偏好；推荐已经就绪，不用等。")
    else:
        try:
            st.session_state[analysis_key] = future.result()
        except Exception as error:
            logger.info("Taste analysis unavailable: %s", type(error).__name__)
            st.session_state[error_key] = format_gemini_error(error)
        finally:
            st.session_state.pop(future_key, None)

        if analysis_key in st.session_state:
            show_taste_analysis(st.session_state[analysis_key])
        else:
            st.warning(st.session_state[error_key])
            if st.button(
                "重试品味分析",
                key=f"retry_taste_analysis::{profile_signature}",
                width="content",
            ):
                st.session_state.pop(error_key, None)
                st.session_state["analysis_pending_signature"] = profile_signature
                st.rerun()


def render_taste_battle(
    documents: list[dict],
    candidates: list[dict],
    session_id: str,
    profile_event_id: int | str | None,
    behavior_persistent: bool,
    profile_signature: str,
    behavior_store: SupabaseBehaviorStore | None = None,
) -> None:
    with st.container(key="battle_panel"):
        st.markdown("### Taste Battle / 品味对决")
        st.caption("两两比较，选完这一轮就进入下一场，最后会选出本轮冠军。")
        strategy = st.selectbox(
            "对决方式",
            options=list(BATTLE_STRATEGIES),
            format_func=lambda key: BATTLE_STRATEGIES[key]["label"],
            key=f"battle_strategy::{profile_signature}",
        )
        st.caption(BATTLE_STRATEGIES[strategy]["description"])
        participants = build_battle_participants(candidates, strategy)
        if len(participants) < 2:
            st.info("这组推荐还凑不齐一场对决。换一种对决方式，或调整喜欢的专辑再试。")
            return

        history_key = f"battle_choices::{profile_signature}::{strategy}"
        if behavior_persistent and profile_event_id is not None:
            if behavior_store is not None:
                try:
                    choices_by_pair = behavior_store.load_battle_choices(
                        profile_event_id, strategy
                    )
                except SupabaseBehaviorError:
                    behavior_persistent = False
                    choices_by_pair = {}
                    st.warning(
                        "数据服务暂时不可用；本轮对决选择只保留在当前访问中。"
                    )
                for choice in st.session_state.get(history_key, []):
                    pair_key = tuple(
                        sorted(
                            (
                                choice["album_a_mbid"],
                                choice["album_b_mbid"],
                            )
                        )
                    )
                    choices_by_pair[pair_key] = choice["chosen_album_mbid"]
            else:
                choices_by_pair = load_battle_choices(
                    APP_DATABASE, profile_event_id, strategy
                )
        else:
            session_choices = st.session_state.get(history_key, [])
            choices_by_pair = {}
            for choice in session_choices:
                if choice.get("generation_strategy", strategy) != strategy:
                    continue
                pair_key = tuple(
                    sorted((choice["album_a_mbid"], choice["album_b_mbid"]))
                )
                choices_by_pair[pair_key] = choice["chosen_album_mbid"]

        battle_state = resolve_battle_tournament(participants, choices_by_pair)
        completed_matches = battle_state["completed_matches"]
        total_matches = battle_state["total_matches"]
        st.progress(
            completed_matches / total_matches,
            text=f"已完成 {completed_matches} / {total_matches} 场",
        )

        documents_by_mbid = {
            album["release_group_mbid"]: album for album in documents
        }
        if battle_state["complete"]:
            winner = battle_state["winner"]
            winner_album = documents_by_mbid[winner["release_group_mbid"]]
            st.success("本轮品味冠军")
            winner_columns = st.columns([1, 2], gap="large")
            with winner_columns[0]:
                if winner_album["cover_url"]:
                    st.image(winner_album["cover_url"], width="stretch")
                else:
                    st.info("这张专辑暂时没有可用封面。")
            with winner_columns[1]:
                st.caption("本轮冠军")
                st.subheader(winner["title"])
                st.write(" / ".join(winner["artists"]))
                st.caption(
                    f"通过 {total_matches} 场逐轮选择胜出。更换路线会开启另一组比较。"
                )
            return

        max_rounds = len(participants).bit_length() - 1
        rounds_left = max_rounds - battle_state["round_number"]
        round_label = (
            "决赛" if rounds_left == 0 else
            "半决赛" if rounds_left == 1 else
            f"第 {battle_state['round_number']} 轮"
        )
        st.markdown(f"**{round_label} · 第 {completed_matches + 1} 场**")
        st.caption("哪张更合你口味？选完就进入下一场。")
        album_a = battle_state["left"]
        album_b = battle_state["right"]
        if completed_matches % 2:
            album_a, album_b = album_b, album_a
        battle_key = (
            f"{profile_signature}::{profile_event_id or 'session'}::{strategy}::"
            f"{min(album_a['release_group_mbid'], album_b['release_group_mbid'])}::"
            f"{max(album_a['release_group_mbid'], album_b['release_group_mbid'])}"
        )
        with st.container(key="battle_comparison"):
            columns = st.columns([1, 0.16, 1], gap="small", vertical_alignment="center")
            for label, recommendation, column in (
                ("A", album_a, columns[0]),
                ("B", album_b, columns[2]),
            ):
                album = documents_by_mbid[recommendation["release_group_mbid"]]
                with column:
                    with st.container(
                        border=True, key=f"battle_album_{label.casefold()}"
                    ):
                        st.caption(f"专辑 {label}")
                        if album["cover_url"]:
                            st.image(album["cover_url"], width="stretch")
                        else:
                            st.caption("封面暂缺")
                        title = escape(album["title"])
                        artists = escape(" / ".join(recommendation["artists"]))
                        st.markdown(
                            f'<div class="battle-album-title">{title}</div>'
                            f'<div class="battle-album-artist">{artists}</div>',
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "我选这张",
                            key=f"battle-choice::{battle_key}::{label}",
                            help=f"选择《{album['title']}》继续",
                            width="stretch",
                        ):
                            chosen_mbid = recommendation["release_group_mbid"]
                            if behavior_persistent and profile_event_id is not None:
                                try:
                                    if behavior_store is not None:
                                        behavior_store.record_battle_choice(
                                            session_id,
                                            profile_event_id,
                                            album_a["release_group_mbid"],
                                            album_b["release_group_mbid"],
                                            chosen_mbid,
                                            strategy,
                                        )
                                    else:
                                        record_battle_choice(
                                            APP_DATABASE,
                                            session_id,
                                            profile_event_id,
                                            album_a["release_group_mbid"],
                                            album_b["release_group_mbid"],
                                            chosen_mbid,
                                            strategy,
                                        )
                                except (
                                    ValueError,
                                    sqlite3.Error,
                                    SupabaseBehaviorError,
                                ):
                                    st.warning(
                                        "这次选择暂时没有写入数据；你仍可继续对决。"
                                    )
                                    session_choices = list(
                                        st.session_state.get(history_key, [])
                                    )
                                    session_choices.append(
                                        {
                                            "album_a_mbid": album_a["release_group_mbid"],
                                            "album_b_mbid": album_b["release_group_mbid"],
                                            "chosen_album_mbid": chosen_mbid,
                                            "generation_strategy": strategy,
                                        }
                                    )
                                    st.session_state[history_key] = session_choices
                                    st.rerun()
                            else:
                                session_choices = list(
                                    st.session_state.get(history_key, [])
                                )
                                session_choices.append(
                                    {
                                        "album_a_mbid": album_a["release_group_mbid"],
                                        "album_b_mbid": album_b["release_group_mbid"],
                                        "chosen_album_mbid": chosen_mbid,
                                        "generation_strategy": strategy,
                                    }
                                )
                                st.session_state[history_key] = session_choices
                            st.rerun()

            with columns[1]:
                st.markdown('<div class="battle-vs">VS</div>', unsafe_allow_html=True)


def show_recommendation(
    tier: str,
    rank: int,
    recommendation: dict,
    resources: dict,
    favorite_seed_mbids: list[str],
    session_id: str,
    profile_event_id: int | str | None,
    behavior_persistent: bool,
    behavior_store: SupabaseBehaviorStore | None = None,
) -> None:
    documents_by_mbid = {
        document["release_group_mbid"]: document for document in resources["documents"]
    }
    album = documents_by_mbid[recommendation["release_group_mbid"]]
    state_key = "::".join(
        [*favorite_seed_mbids, tier, str(rank), recommendation["title"]]
    )

    container_key = f"recommendation_{tier.lower()}_{rank}"
    with st.container(border=True, key=container_key):
        tier_detail = TIER_DETAILS[tier]
        st.markdown(
            f'<span class="tier-badge tier-{tier.lower()}">'
            f"{escape(tier)} / {escape(tier_detail['subtitle'])}</span>",
            unsafe_allow_html=True,
        )
        if album["cover_url"]:
            st.image(album["cover_url"], width="stretch")
        else:
            st.info("这张专辑暂时没有可用封面。")

        artists = ", ".join(recommendation["artists"])
        year = album["release_year"] or "年份未知"
        st.subheader(recommendation["title"])
        st.markdown(
            f'<div class="recommendation-meta">{escape(artists)} / {escape(str(year))}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="bridge-copy">和你喜欢的 '
            f"<strong>{escape(recommendation['bridge_favorite'])}</strong> 有一条连接</div>",
            unsafe_allow_html=True,
        )

        feedback_key = (
            f"feedback::{session_id}::{recommendation['release_group_mbid']}"
        )
        feedback_labels = {"适合我": "like", "不太适合": "dislike"}
        feedback_value = st.session_state.get(feedback_key)
        default_feedback = next(
            (label for label, value in feedback_labels.items() if value == feedback_value),
            None,
        )
        with st.container(key=f"feedback_{tier.lower()}_{rank}"):
            selected_label = st.pills(
                "推荐反馈",
                options=list(feedback_labels),
                default=default_feedback,
                selection_mode="single",
                label_visibility="collapsed",
                key=f"feedback_control::{session_id}::{recommendation['release_group_mbid']}",
            )
        selected_feedback = feedback_labels.get(selected_label)
        if selected_feedback and selected_feedback != feedback_value:
            if behavior_persistent and profile_event_id is not None:
                try:
                    if behavior_store is not None:
                        behavior_store.record_feedback(
                            session_id,
                            profile_event_id,
                            recommendation["release_group_mbid"],
                            tier,
                            selected_feedback,
                        )
                    else:
                        record_feedback(
                            APP_DATABASE,
                            session_id,
                            recommendation["release_group_mbid"],
                            tier,
                            selected_feedback,
                        )
                except (sqlite3.Error, SupabaseBehaviorError) as error:
                    st.warning(f"暂时无法保存反馈；本次访问仍保留当前选择：{error}")
            st.session_state[feedback_key] = selected_feedback

        bridge_tags = recommendation["bridge_tags"][:5]
        new_tags = recommendation["new_tags"][:5]
        st.markdown('<div class="signal-label">熟悉之处</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="signal-tags">{escape(" / ".join(bridge_tags) or "暂无明确标签")}</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="signal-label">新的方向</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="signal-tags">{escape(" / ".join(new_tags) or "变化较小")}</div>',
            unsafe_allow_html=True,
        )

        if state_key not in st.session_state:
            if st.button(
                "为什么推荐它？",
                key=f"generate::{state_key}",
                type="primary",
                width="stretch",
            ):
                with st.spinner("正在检索评论并整理解释…"):
                    try:
                        rag_result = build_context(
                            resources["documents"],
                            resources["review_chunks"],
                            resources["review_vectors"],
                            resources["review_model"],
                            recommendation["bridge_favorite"],
                            recommendation["title"],
                            top_k=2,
                        )
                        explanation = generate_why_this(
                            rag_result,
                            tier=tier,
                            recommendation=recommendation,
                            api_key=get_streamlit_gemini_api_key(),
                        )
                        st.session_state[state_key] = {
                            "explanation": explanation,
                            "sources": rag_result["sources"],
                        }
                    except Exception as error:
                        logger.info("Why This explanation unavailable: %s", type(error).__name__)
                        st.error(format_gemini_error(error))

        if state_key in st.session_state:
            show_explanation(st.session_state[state_key])
            if st.button(
                "收起解释",
                key=f"collapse::{state_key}",
                width="stretch",
            ):
                del st.session_state[state_key]
                st.rerun()

def main() -> None:
    st.set_page_config(
        page_title="AI Taste Discovery",
        page_icon="🎧",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_styles()
    render_hero()
    try:
        behavior_mode = get_behavior_storage_mode()
    except ValueError as error:
        behavior_mode = "session"
        st.warning(f"行为记录设置无效，已切换为仅本次访问暂存：{error}")
    try:
        ensure_application_database(APP_DATABASE)
    except Exception as error:
        logger.exception("Failed to obtain the album catalogue")
        st.error(
            "专辑目录暂时无法获取。请检查网络连接，或确认目录下载地址和校验值设置正确。"
        )
        st.caption(f"诊断类型：{type(error).__name__}")
        st.stop()
    if not APP_DATABASE.exists():
        st.error(
            "找不到专辑数据库，请检查 AI_TASTE_DATABASE_PATH，或先运行数据 Pipeline。"
        )
        st.stop()

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    session_id = st.session_state["session_id"]
    consent_given = st.checkbox(
        "我同意匿名记录本次选择、推荐展示和反馈，用于评估与改进推荐。",
        key="analytics_consent",
        help=(
            "行为数据表只记录随机会话 ID 和你在应用内的选择，不写入姓名、邮箱或 IP。"
            "你可以不勾选，仍可体验推荐；取消勾选会停止后续记录，但不会自动删除此前提交的事件。"
        ),
    )
    behavior_store = None
    behavior_persistent = False
    if consent_given and behavior_mode == "persistent":
        try:
            ensure_behavior_schema(str(APP_DATABASE), SCHEMA_REVISION)
            create_session(APP_DATABASE, session_id)
            behavior_persistent = True
        except (sqlite3.Error, OSError) as error:
            st.warning(
                f"本地行为数据暂时无法保存；推荐仍可使用：{type(error).__name__}"
            )
    elif consent_given and behavior_mode == "supabase":
        try:
            behavior_store = get_supabase_behavior_store()
            registered_session_id = st.session_state.get(
                "registered_analytics_session_id"
            )
            if registered_session_id != session_id:
                behavior_store.create_session(
                    session_id, ANALYTICS_CONSENT_VERSION
                )
                st.session_state["registered_analytics_session_id"] = session_id
            behavior_persistent = True
        except (SupabaseBehaviorError, ValueError) as error:
            behavior_store = None
            detail = str(error).strip() or type(error).__name__
            st.warning(
                "匿名数据存储暂不可用；推荐仍可使用，本次反馈不会保存。"
                f"（{detail}）"
            )
    elif consent_given and behavior_mode == "session":
        st.info(
            "当前运行模式只暂存本次访问的行为，数据不会写入持久化数据库。"
        )
    elif not consent_given:
        st.caption(
            "未同意数据记录：推荐和 AI 功能仍可使用；选择与反馈只用于当前页面交互，不会写入行为数据库。"
        )

    if consent_given and behavior_persistent:
        if behavior_store is not None:
            st.caption(
                "匿名 Beta 数据已启用：随机会话 ID、专辑选择、推荐展示、反馈与对决选择会保存，用于评估。"
            )
        else:
            st.caption(
                "匿名 Beta 数据已启用：本机使用 SQLite 记录专辑选择、推荐展示、反馈与对决选择。"
            )

    try:
        resources = load_resources()
    except Exception as error:
        logger.exception("Failed to load the album catalogue and local embeddings")
        st.error(
            "专辑目录或本地语义模型暂时无法加载。请确认部署中包含目录数据库，"
            "且首次启动时可以下载 FastEmbed 模型，然后刷新页面。"
        )
        st.caption(f"诊断类型：{type(error).__name__}")
        st.stop()
    documents_by_mbid = {
        document["release_group_mbid"]: document
        for document in resources["documents"]
    }
    if "confirmed_favorite_titles" not in st.session_state:
        st.session_state["confirmed_favorite_titles"] = []
    if "confirmed_favorite_mbids" not in st.session_state:
        legacy_titles = st.session_state["confirmed_favorite_titles"]
        documents_by_title = {}
        for document in resources["documents"]:
            documents_by_title.setdefault(document["title"], document)
        st.session_state["confirmed_favorite_mbids"] = [
            documents_by_title[title]["release_group_mbid"]
            for title in legacy_titles
            if title in documents_by_title
        ]
    if "draft_favorite_mbids" not in st.session_state:
        st.session_state["draft_favorite_mbids"] = list(
            st.session_state["confirmed_favorite_mbids"]
        )

    with st.container(key="selection_panel"):
        st.markdown(
            '<h2 class="section-heading">先选几张你真心喜欢的专辑。</h2>'
            '<p class="section-copy">最多选 10 张。确认后先看推荐，品味分析会在后台继续生成。</p>',
            unsafe_allow_html=True,
        )
        st.markdown("**搜索曲库**")
        st.text_input(
            "搜索专辑名或艺人名",
            key="album_search_query",
            placeholder="例如：BRAT、Charli xcx",
            help="删除或修改搜索文字不会影响已选专辑。",
        )
        st.caption("搜索结果里的“加入”会把专辑放到下方；只有点 × 才会移除。")

        draft_favorite_mbids = list(
            st.session_state.get("draft_favorite_mbids", [])
        )
        st.markdown(f"**已选专辑 · {len(draft_favorite_mbids)} / 10**")
        if draft_favorite_mbids:
            selected_columns = st.columns(2, gap="small")
            for index, release_group_mbid in enumerate(draft_favorite_mbids):
                album = documents_by_mbid[release_group_mbid]
                with selected_columns[index % 2]:
                    with st.container(
                        border=True,
                        key=f"selected_album_item_{release_group_mbid}",
                    ):
                        title = escape(album["title"])
                        artists = escape(" / ".join(album["artists"]))
                        st.markdown(
                            f'<div class="selected-album-title">{title}</div>'
                            f'<div class="selected-album-artist">{artists}</div>',
                            unsafe_allow_html=True,
                        )
                        st.button(
                            "× 移除",
                            key=f"remove_album_{release_group_mbid}",
                            help=f"移除《{album['title']}》",
                            on_click=remove_album_from_selection,
                            args=(release_group_mbid,),
                            width="content",
                        )
        else:
            st.caption("还没有选专辑。搜索后点“加入”，选错了可以在这里移除。")
        if len(draft_favorite_mbids) >= 10:
            st.caption("已经选满 10 张；移除一张后可以继续添加。")

        search_query = str(st.session_state.get("album_search_query", "")).strip()
        if search_query:
            query = search_query.casefold()
            matches = [
                album
                for album in resources["documents"]
                if query in album["title"].casefold()
                or any(query in artist.casefold() for artist in album["artists"])
            ]
            if matches:
                for album in matches[:8]:
                    release_group_mbid = album["release_group_mbid"]
                    already_selected = release_group_mbid in draft_favorite_mbids
                    selection_full = len(draft_favorite_mbids) >= 10
                    with st.container(
                        border=True,
                        key=f"album_search_result_{release_group_mbid}",
                    ):
                        result_column, action_column = st.columns(
                            [5, 1.1], vertical_alignment="center"
                        )
                        with result_column:
                            title = escape(album["title"])
                            artists = escape(" / ".join(album["artists"]))
                            year = album.get("release_year")
                            year_text = f" · {year}" if year else ""
                            st.markdown(
                                f'<div class="search-result-title">{title}</div>'
                                f'<div class="search-result-artist">{artists}{year_text}</div>',
                                unsafe_allow_html=True,
                            )
                        with action_column:
                            st.button(
                                "已加入" if already_selected else "加入",
                                key=f"add_album_{release_group_mbid}",
                                disabled=already_selected or selection_full,
                                on_click=add_album_to_selection,
                                args=(release_group_mbid,),
                                width="stretch",
                            )
                if len(matches) > 8:
                    st.caption("先显示前 8 项；再多输入几个字可以缩小范围。")
            else:
                st.info(
                    f"曲库目前收录约 {len(resources['documents'])} 张专辑，"
                    "以欧美流行音乐和部分 K-pop 为主，更多作品会逐步补充。"
                    "暂时没找到匹配项；可以换个专辑名或艺人名再试。"
                )
        favorite_draft_signature = "|".join(draft_favorite_mbids)
        old_signature = st.session_state.get("confirmed_profile_signature", "")
        if favorite_draft_signature != old_signature:
            st.caption("选择有改动；点击下方按钮后，品味档案和推荐会一起更新。")
        confirmed_mbids = list(
            st.session_state.get("confirmed_favorite_mbids", [])
        )
        submit_label = (
            "完成选择，开始推荐"
            if draft_favorite_mbids
            else "清空已确认的选择"
        )
        submitted = st.button(
            submit_label,
            key="profile_submit",
            type="primary",
            width="stretch",
            disabled=not draft_favorite_mbids and not confirmed_mbids,
        )

        if submitted:
            favorite_draft = list(draft_favorite_mbids)
            new_signature = "|".join(favorite_draft)
            old_signature = st.session_state.get("confirmed_profile_signature")
            st.session_state["confirmed_favorite_mbids"] = favorite_draft
            st.session_state["confirmed_favorite_titles"] = [
                documents_by_mbid[mbid]["title"] for mbid in favorite_draft
            ]
            st.session_state["confirmed_profile_signature"] = new_signature
            if new_signature and (
                new_signature != old_signature
                or f"taste_analysis::{new_signature}" not in st.session_state
            ):
                st.session_state["analysis_pending_signature"] = new_signature
                st.session_state.pop(
                    f"taste_analysis_error::{new_signature}", None
                )
            elif not new_signature:
                st.session_state["analysis_pending_signature"] = None
                st.session_state["active_profile_mbids"] = None
                st.session_state["profile_event_id"] = None

        favorite_mbids = list(
            st.session_state.get("confirmed_favorite_mbids", [])
        )
        favorite_titles = [
            documents_by_mbid[mbid]["title"] for mbid in favorite_mbids
        ]
        if favorite_titles:
            selected_albums = [documents_by_mbid[mbid] for mbid in favorite_mbids]
            render_album_shelf(selected_albums)
            try:
                profile = build_taste_profile(
                    resources["documents"],
                    resources["album_vectors"],
                    favorite_mbids,
                )
            except ValueError as error:
                st.error(str(error))
                st.stop()

            profile_event_id = st.session_state.get("profile_event_id")
            seed_album_mbids = [
                album["release_group_mbid"] for album in profile["seed_albums"]
            ]
            profile_signature = "|".join(seed_album_mbids)
            if behavior_persistent:
                if st.session_state.get("active_profile_mbids") != seed_album_mbids:
                    try:
                        if behavior_store is not None:
                            profile_event_id = (
                                behavior_store.record_taste_profile_event(
                                    session_id, seed_album_mbids
                                )
                            )
                        else:
                            profile_event_id = record_taste_profile_event(
                                APP_DATABASE, session_id, seed_album_mbids
                            )
                        st.session_state["active_profile_mbids"] = seed_album_mbids
                        st.session_state["profile_event_id"] = profile_event_id
                    except (sqlite3.Error, SupabaseBehaviorError) as error:
                        behavior_persistent = False
                        profile_event_id = None
                        detail = str(error).strip() or type(error).__name__
                        st.warning(
                            "无法保存本次专辑选择；推荐仍可使用，后续交互只暂存在本次访问。"
                            f"（{detail}）"
                        )
            else:
                profile_event_id = None

            profile_tags = [tag for tag, _count in profile["top_tags"][:8]]
            with st.container(key="profile_panel"):
                st.markdown(
                    '<div class="profile-title">你的听歌品味</div>',
                    unsafe_allow_html=True,
                )
                render_tags(profile_tags)
                if st.session_state.get("analysis_pending_signature") == profile_signature:
                    st.session_state["analysis_pending_signature"] = None
                    queue_taste_analysis(
                        profile_signature,
                        profile,
                        resources,
                        get_streamlit_gemini_api_key(),
                    )
                render_taste_analysis_status(profile_signature)
        else:
            st.session_state["active_profile_mbids"] = None
            st.session_state["profile_event_id"] = None

    if not favorite_titles:
        if st.session_state.get("draft_favorite_mbids"):
            st.info("已选好专辑；点上方“完成选择，开始推荐”后继续。")
        else:
            st.info("先搜索并加入至少一张喜欢的专辑，再点上方按钮。")
        st.stop()

    candidates = candidate_features(
        resources["documents"],
        resources["album_vectors"],
        profile,
    )

    recommendation_tab, battle_tab = st.tabs(
        ["推荐探索", "Taste Battle / 品味对决"]
    )
    with recommendation_tab:
        st.markdown(
            '<h2 class="section-heading">今天想走多远？</h2>'
            '<p class="section-copy">先选一个探索距离。推荐由专辑相似度和标签线索决定，AI 不会替你挑选。</p>',
            unsafe_allow_html=True,
        )
        tier_options = list(TIER_DETAILS)
        with st.container(key="tier_selector"):
            selected_tier = st.segmented_control(
                "探索距离",
                options=tier_options,
                default="Explore",
                format_func=lambda tier: f"{tier} / {TIER_DETAILS[tier]['subtitle']}",
                selection_mode="single",
                label_visibility="collapsed",
                width="stretch",
            )
        selected_tier = selected_tier or "Explore"
        per_tier = st.pills(
            "每档想看几张？",
            options=list(range(1, 9)),
            default=st.session_state.get("confirmed_per_tier", 2),
            selection_mode="single",
            key="per_tier_picker_v2",
        )
        per_tier = int(per_tier or 2)
        st.session_state["confirmed_per_tier"] = per_tier
        recommendations = choose_recommendations(candidates, per_tier)
        selected_detail = TIER_DETAILS[selected_tier]
        items = recommendations[selected_tier]

        if not items:
            st.session_state["last_impression_signature"] = None
        elif behavior_persistent and profile_event_id is not None:
            impression_signature = (
                profile_event_id,
                selected_tier,
                tuple(item["release_group_mbid"] for item in items),
            )
            if st.session_state.get("last_impression_signature") != impression_signature:
                try:
                    if behavior_store is not None:
                        behavior_store.record_recommendation_impressions(
                            session_id,
                            profile_event_id,
                            selected_tier,
                            items,
                        )
                    else:
                        record_recommendation_impressions(
                            APP_DATABASE,
                            session_id,
                            profile_event_id,
                            selected_tier,
                            items,
                        )
                    st.session_state["last_impression_signature"] = impression_signature
                except (sqlite3.Error, SupabaseBehaviorError) as error:
                    st.warning(
                        f"暂时无法记录推荐展示；稍后操作时会重试。"
                        f"（{type(error).__name__}）"
                    )

        st.markdown(
            f'<div class="tier-intro"><div><h2>{escape(selected_tier)} / '
            f"{escape(selected_detail['subtitle'])}</h2>"
            f"<p>{escape(selected_detail['description'])}</p></div>"
            f"<p>找到 {len(items)} 张</p></div>",
            unsafe_allow_html=True,
        )

        if not items:
            st.info("这一档暂时没有合适的专辑。换个探索距离，或调整喜欢的专辑再试。")
        else:
            with st.container(key=f"recommendation_grid_{selected_tier.lower()}"):
                card_columns = st.columns(3, gap="large")
                for rank, recommendation in enumerate(items, start=1):
                    with card_columns[(rank - 1) % 3]:
                        show_recommendation(
                            selected_tier,
                            rank,
                            recommendation,
                            resources,
                            favorite_mbids,
                            session_id,
                            profile_event_id,
                            behavior_persistent,
                            behavior_store,
                        )

    with battle_tab:
        render_taste_battle(
            resources["documents"],
            candidates,
            session_id,
            profile_event_id,
            behavior_persistent,
            profile_signature,
            behavior_store,
        )

    with st.expander("排序调试：查看完整候选评分", expanded=False):
        st.caption(
            "分数是可检查的启发式信号，不是概率。Embedding distance = 1 − cosine similarity；"
            "新颖比例 = 候选标签中不在种子专辑标签集合里的比例。"
        )
        st.markdown(
            "Safe = 0.70×embedding + 0.20×bridge + 0.10×tag familiarity\n\n"
            "Explore = 0.55×embedding + 0.20×bridge + 0.10×tag familiarity + 0.15×novelty balance\n\n"
            "Wildcard = 0.45×bridge + 0.25×tag familiarity + 0.30×embedding distance"
        )
        tier_order = {"Safe": 0, "Explore": 1, "Wildcard": 2, None: 3}
        ranked_candidates = sorted(
            candidates,
            key=lambda item: (
                tier_order[item["assigned_tier"]],
                item["tier_rank"] if item["tier_rank"] is not None else 10**9,
                item["title"].casefold(),
            ),
        )
        debug_rows = []
        for candidate in ranked_candidates:
            tier = candidate["assigned_tier"]
            components = candidate["score_components"].get(tier, {})
            debug_rows.append(
                {
                    "Album": candidate["title"],
                    "Artist": ", ".join(candidate["artists"]),
                    "Release group MBID": candidate["release_group_mbid"],
                    "Tier": tier or "Unassigned",
                    "Tier rank": candidate["tier_rank"],
                    "Displayed": candidate["shown_in_ui"],
                    "Median similarity threshold": candidate["median_profile_similarity"],
                    "Embedding similarity": candidate["embedding_similarity"],
                    "Embedding distance": candidate["embedding_distance"],
                    "Bridge similarity": candidate["bridge_similarity"],
                    "Bridge tag overlap": candidate["bridge_tag_overlap_count"],
                    "Tag familiarity": candidate["tag_familiarity"],
                    "Novelty ratio": candidate["novelty_ratio"],
                    "Novelty balance": candidate["novelty_balance"],
                    "Safe score": candidate["safe_score"],
                    "Explore score": candidate["explore_score"],
                    "Wildcard score": candidate["wildcard_score"],
                    "Final score": candidate["final_score"],
                    "Weighted components": ", ".join(
                        f"{name}={value:.4f}"
                        for name, value in components.items()
                    ),
                    "Assignment rule": candidate["assignment_reason"],
                }
            )
        st.dataframe(debug_rows, hide_index=True, width="stretch")


if __name__ == "__main__":
    main()
