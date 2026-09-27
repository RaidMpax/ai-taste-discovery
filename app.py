"""Minimal Streamlit UI for AI Taste Discovery V0.1."""

from __future__ import annotations

import streamlit as st

from rag import build_context, embed_chunks, generate_why_this, load_review_chunks
from recommend import candidate_features, choose_recommendations
from semantic_search import (
    DEFAULT_DATABASE,
    build_taste_profile,
    embed_documents,
    load_album_documents,
)


TIER_DESCRIPTIONS = {
    "Safe": "与你当前的审美高度接近，适合作为低风险延伸。",
    "Explore": "保留熟悉的连接，同时引入新的审美方向。",
    "Wildcard": "距离更远，但仍有可以解释的桥梁。",
}


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
    st.markdown("#### Why This?")
    st.write(explanation["why_this"])
    st.markdown("**熟悉的连接**")
    st.write(explanation["familiar_connection"])
    st.markdown("**新的方向**")
    st.write(explanation["new_direction"])

    with st.expander("Evidence"):
        for item in explanation["evidence"]:
            st.write(item["claim"])
            source_ids = ", ".join(item["source_ids"]) or "Structured tags"
            st.caption(f"Source IDs: {source_ids}")

    st.markdown("**证据限制**")
    st.write(explanation["limitations"])
    st.markdown("**Sources**")
    if not result["sources"]:
        st.caption("没有可用的 review；本次解释仅使用结构化标签。")
    for source in result["sources"]:
        st.markdown(
            f"- [{source['album_title']} — {source['source']}]"
            f"({source['source_url']}) · {source['license']} · "
            f"{source['source_id']}"
        )


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

    with st.container(border=True):
        cover_column, details_column = st.columns([1, 3])
        with cover_column:
            if album["cover_url"]:
                st.image(album["cover_url"], width="stretch")
            else:
                st.caption("No cover available")

        with details_column:
            artists = ", ".join(recommendation["artists"])
            st.subheader(recommendation["title"])
            st.caption(f"{artists} · {album['release_year'] or 'Year unknown'}")
            st.write(
                f"Bridge: **{recommendation['bridge_favorite']}** "
                f"({recommendation['bridge_similarity']:.3f})"
            )
            bridge_tags = ", ".join(recommendation["bridge_tags"]) or "none"
            new_tags = ", ".join(recommendation["new_tags"][:6]) or "none"
            st.write(f"熟悉标签：{bridge_tags}")
            st.write(f"新标签：{new_tags}")

            if st.button("Generate Why This?", key=f"generate::{state_key}"):
                with st.spinner("正在检索评论并生成解释…"):
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
                        st.error(f"Why This? 暂时无法生成：{error}")

        if state_key in st.session_state:
            show_explanation(st.session_state[state_key])


def main() -> None:
    st.set_page_config(
        page_title="AI Taste Discovery",
        page_icon="🎧",
        layout="wide",
    )
    st.title("AI Taste Discovery")
    st.write("从你喜欢的专辑出发，发现安全延伸、相邻探索与大胆跳跃。")

    if not DEFAULT_DATABASE.exists():
        st.error("taste.db 不存在，请先运行数据获取 Pipeline。")
        st.stop()

    resources = load_resources(DEFAULT_DATABASE.stat().st_mtime_ns)
    album_titles = [album["title"] for album in resources["documents"]]
    default_favorites = ["OK Computer"] if "OK Computer" in album_titles else []

    favorite_titles = st.multiselect(
        "选择你喜欢的专辑",
        album_titles,
        default=default_favorites,
        max_selections=5,
    )
    per_tier = st.slider("每档显示数量", min_value=1, max_value=3, value=2)

    if not favorite_titles:
        st.info("请至少选择一张喜欢的专辑。")
        st.stop()

    try:
        profile = build_taste_profile(
            resources["documents"],
            resources["album_vectors"],
            favorite_titles,
        )
    except ValueError as error:
        st.error(str(error))
        st.stop()

    candidates = candidate_features(
        resources["documents"],
        resources["album_vectors"],
        profile,
    )
    recommendations = choose_recommendations(candidates, per_tier)

    profile_tags = ", ".join(
        f"{tag} ({count})" for tag, count in profile["top_tags"][:8]
    )
    st.caption(f"Taste Profile tags: {profile_tags or 'none'}")

    tabs = st.tabs(list(TIER_DESCRIPTIONS))
    for tab, (tier, description) in zip(tabs, TIER_DESCRIPTIONS.items()):
        with tab:
            st.write(description)
            items = recommendations[tier]
            if not items:
                st.info("当前没有候选满足这一档的证据规则。")
            for rank, recommendation in enumerate(items, start=1):
                show_recommendation(
                    tier,
                    rank,
                    recommendation,
                    resources,
                    favorite_titles,
                )


if __name__ == "__main__":
    main()
