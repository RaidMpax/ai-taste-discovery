"""Minimal Streamlit UI for AI Taste Discovery V0.1."""

from __future__ import annotations

from html import escape

import streamlit as st

from rag import build_context, embed_chunks, generate_why_this, load_review_chunks
from recommend import candidate_features, choose_recommendations
from semantic_search import (
    DEFAULT_DATABASE,
    build_taste_profile,
    embed_documents,
    load_album_documents,
)


TIER_DETAILS = {
    "Safe": {
        "subtitle": "熟悉延伸",
        "description": "从已经喜欢的声音继续向外走，连接清晰，变化克制。",
    },
    "Explore": {
        "subtitle": "相邻探索",
        "description": "保留一部分熟悉感，同时打开一个新的审美方向。",
    },
    "Wildcard": {
        "subtitle": "大胆跳跃",
        "description": "距离更远，但仍然保留一条可以说清楚的连接。",
    },
}


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
        [data-testid="stMultiSelect"] [data-baseweb="select"] {
            position: relative;
            border-radius: 16px;
            background: #ffffff !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="select"]::after {
            content: "";
            position: absolute;
            z-index: 3;
            inset: 0;
            pointer-events: none;
            border: 1.5px solid #7f9fc9;
            border-radius: 16px;
        }
        [data-testid="stMultiSelect"] [data-baseweb="select"]:hover::after {
            border-color: #557fb7;
        }
        [data-testid="stMultiSelect"] [data-baseweb="select"]:focus-within::after {
            border: 2px solid var(--fluorescent);
        }
        div[data-baseweb="tag"] {
            background: #ddecff !important;
            color: #204f8d !important;
        }
        div[data-baseweb="tag"] span,
        div[data-baseweb="tag"] svg {
            color: #204f8d !important;
            fill: #204f8d !important;
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

        .st-key-profile_panel {
            margin: 24px 0 0;
            padding: 28px 30px;
            border: 1px solid rgba(55, 112, 191, .2);
            border-radius: 24px;
            background: #e5f1ff;
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
            <p class="hero-note-sub">从熟悉的声音出发，找到你还没有遇见的下一张专辑。</p>
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


@st.cache_resource(show_spinner="正在加载专辑与 Embedding…")
def load_resources(database_version: int) -> dict:
    """Load expensive local models and vectors once per database version."""
    del database_version  # Used only to invalidate the cache after DB changes.
    documents = load_album_documents(DEFAULT_DATABASE)
    album_vectors = embed_documents(documents)
    review_chunks = load_review_chunks(DEFAULT_DATABASE)
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

    st.markdown("**我们还不能确定的部分**")
    st.write(explanation["limitations"])

    with st.expander("查看证据与来源"):
        st.markdown("**证据片段**")
        for item in explanation["evidence"]:
            st.write(item["claim"])
            source_ids = ", ".join(item["source_ids"]) or "Structured tags"
            st.caption(f"Source IDs: {source_ids}")
        st.markdown("**来源**")
        if not result["sources"]:
            st.caption("没有可用评论；本次解释仅使用结构化标签。")
        for source in result["sources"]:
            st.markdown(
                f"- [{source['album_title']} / {source['source']}]"
                f"({source['source_url']})"
            )
            st.caption(f"{source['license']} / {source['source_id']}")


def show_recommendation(
    tier: str,
    rank: int,
    recommendation: dict,
    resources: dict,
    favorite_titles: list[str],
) -> None:
    documents_by_title = {
        document["title"]: document for document in resources["documents"]
    }
    album = documents_by_title[recommendation["title"]]
    state_key = "::".join(
        [*favorite_titles, tier, str(rank), recommendation["title"]]
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
            f'<div class="bridge-copy">连接自你喜欢的 '
            f"<strong>{escape(recommendation['bridge_favorite'])}</strong></div>",
            unsafe_allow_html=True,
        )

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
                        )
                        st.session_state[state_key] = {
                            "explanation": explanation,
                            "sources": rag_result["sources"],
                        }
                    except Exception as error:
                        st.error(f"暂时无法生成解释：{error}")

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

    if not DEFAULT_DATABASE.exists():
        st.error("taste.db 不存在，请先运行数据获取 Pipeline。")
        st.stop()

    resources = load_resources(DEFAULT_DATABASE.stat().st_mtime_ns)
    album_titles = [album["title"] for album in resources["documents"]]
    documents_by_title = {
        document["title"]: document for document in resources["documents"]
    }
    default_favorites = ["OK Computer"] if "OK Computer" in album_titles else []

    with st.container(key="selection_panel"):
        st.markdown(
            '<h2 class="section-heading">从你真正喜欢的专辑开始。</h2>'
            '<p class="section-copy">搜索并选择一至四张专辑。我们会从这些作品中提取你的当前审美线索。</p>',
            unsafe_allow_html=True,
        )
        selection_column, count_column = st.columns([2.2, 1], gap="large")
        with selection_column:
            favorite_titles = st.multiselect(
                "喜欢的专辑",
                album_titles,
                default=default_favorites,
                max_selections=4,
                placeholder="搜索一张你喜欢的专辑",
            )
        with count_column:
            per_tier = st.pills(
                "每档最多显示",
                options=list(range(1, 9)),
                default=2,
                selection_mode="single",
            )
            per_tier = per_tier or 2

        if favorite_titles:
            st.markdown(
                '<div class="selected-shelf">你带到柜台的唱片</div>',
                unsafe_allow_html=True,
            )
            cover_columns = st.columns(4, gap="small")
            for column, title in zip(cover_columns, favorite_titles):
                album = documents_by_title[title]
                with column:
                    if album["cover_url"]:
                        st.image(album["cover_url"], caption=title, width="stretch")
                    else:
                        st.info(title)

            try:
                profile = build_taste_profile(
                    resources["documents"],
                    resources["album_vectors"],
                    favorite_titles,
                )
            except ValueError as error:
                st.error(str(error))
                st.stop()

            profile_tags = [tag for tag, _count in profile["top_tags"][:8]]
            with st.container(key="profile_panel"):
                st.markdown(
                    '<div class="profile-title">你的 Taste Profile</div>',
                    unsafe_allow_html=True,
                )
                render_tags(profile_tags)

    if not favorite_titles:
        st.info("先选择一张你喜欢的专辑，我们再开始寻找下一张。")
        st.stop()

    candidates = candidate_features(
        resources["documents"],
        resources["album_vectors"],
        profile,
    )
    recommendations = choose_recommendations(candidates, per_tier)

    st.markdown(
        '<h2 class="section-heading">今天想走多远？</h2>'
        '<p class="section-copy">选择一种探索距离。档位来自透明的相似度与标签规则，不由语言模型决定。</p>',
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
    selected_detail = TIER_DETAILS[selected_tier]
    items = recommendations[selected_tier]

    st.markdown(
        f'<div class="tier-intro"><div><h2>{escape(selected_tier)} / '
        f"{escape(selected_detail['subtitle'])}</h2>"
        f"<p>{escape(selected_detail['description'])}</p></div>"
        f"<p>找到 {len(items)} 张</p></div>",
        unsafe_allow_html=True,
    )

    if not items:
        st.info("当前没有候选满足这一档的证据规则。换一张喜欢的专辑，或选择另一种探索距离。")
    else:
        card_columns = st.columns(3, gap="large")
        for rank, recommendation in enumerate(items, start=1):
            with card_columns[(rank - 1) % 3]:
                show_recommendation(
                    selected_tier,
                    rank,
                    recommendation,
                    resources,
                    favorite_titles,
                )


if __name__ == "__main__":
    main()
