"""Day 7: retrieve licensed review chunks and build transparent RAG context."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from fastembed import TextEmbedding
from google import genai

from semantic_search import (
    DEFAULT_DATABASE,
    MODEL_CACHE,
    MODEL_NAME,
    cosine_scores,
    is_taste_tag,
    load_album_documents,
)


CHUNK_SIZE = 900
CHUNK_OVERLAP = 120
GEMINI_MODELS = ("gemini-3.1-flash-lite", "gemini-2.5-flash-lite")
GEMINI_TIMEOUT_MS = 30_000
UNSUPPORTED_CONSENSUS_TERMS = (
    "often",
    "widely",
    "commonly",
    "常被",
    "经常",
    "广泛",
    "普遍",
)
WHY_THIS_SCHEMA = {
    "type": "object",
    "properties": {
        "why_this": {"type": "string"},
        "familiar_connection": {"type": "string"},
        "new_direction": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "source_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["claim", "source_ids"],
                "additionalProperties": False,
            },
        },
        "limitations": {"type": "string"},
    },
    "required": [
        "why_this",
        "familiar_connection",
        "new_direction",
        "evidence",
        "limitations",
    ],
    "additionalProperties": False,
}


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split at sentence boundaries and preserve whole-sentence overlap."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")

    normalized = " ".join(text.split())
    if not normalized:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    segments = []
    for sentence in sentences:
        remaining = sentence.strip()
        while len(remaining) > chunk_size:
            boundary = remaining.rfind(" ", 0, chunk_size)
            if boundary <= 0:
                boundary = chunk_size
            segments.append(remaining[:boundary].strip())
            remaining = remaining[boundary:].strip()
        if remaining:
            segments.append(remaining)

    chunks = []
    current: list[str] = []
    for segment in segments:
        proposed = " ".join([*current, segment])
        if current and len(proposed) > chunk_size:
            chunks.append(" ".join(current))

            overlap_segments = []
            overlap_length = 0
            for previous in reversed(current):
                overlap_segments.insert(0, previous)
                overlap_length += len(previous) + 1
                if overlap_length >= overlap:
                    break
            while overlap_segments and len(" ".join([*overlap_segments, segment])) > chunk_size:
                overlap_segments.pop(0)
            current = overlap_segments
        current.append(segment)

    if current:
        chunks.append(" ".join(current))

    return chunks


def load_review_chunks(database_path: Path) -> list[dict]:
    """Read only licensed reviews and attach source metadata to every chunk."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT
            r.review_id,
            r.release_group_mbid,
            a.title AS album_title,
            r.language,
            r.source,
            r.source_url,
            r.license,
            r.review_text
        FROM reviews AS r
        JOIN albums AS a
          ON a.release_group_mbid = r.release_group_mbid
        WHERE trim(r.review_text) <> '' AND trim(r.license) <> ''
        ORDER BY a.title, r.review_id
        """
    ).fetchall()
    connection.close()

    chunks = []
    for row in rows:
        review_chunks = chunk_text(row["review_text"])
        for chunk_index, text in enumerate(review_chunks, start=1):
            chunks.append(
                {
                    "review_id": row["review_id"],
                    "release_group_mbid": row["release_group_mbid"],
                    "album_title": row["album_title"],
                    "language": row["language"],
                    "source": row["source"] or "CritiqueBrainz",
                    "source_url": row["source_url"]
                    or f'https://critiquebrainz.org/ws/1/review/{row["review_id"]}',
                    "license": row["license"],
                    "chunk_index": chunk_index,
                    "chunk_count": len(review_chunks),
                    "text": text,
                }
            )
    return chunks


def embed_chunks(chunks: list[dict]) -> tuple[TextEmbedding, np.ndarray]:
    model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(MODEL_CACHE))
    vectors = model.embed([chunk["text"] for chunk in chunks])
    return model, np.asarray(list(vectors), dtype=np.float32)


def retrieve_chunks(
    chunks: list[dict],
    vectors: np.ndarray,
    model: TextEmbedding,
    query: str,
    album_title: str,
    top_k: int,
) -> list[dict]:
    """Retrieve only within one album so evidence cannot drift to another work."""
    eligible_indices = [
        index
        for index, chunk in enumerate(chunks)
        if chunk["album_title"].casefold() == album_title.casefold()
    ]
    if not eligible_indices:
        return []

    query_vector = np.asarray(list(model.embed([query]))[0], dtype=np.float32)
    eligible_vectors = vectors[eligible_indices]
    scores = cosine_scores(eligible_vectors, query_vector)
    ranked_positions = np.argsort(scores)[::-1][:top_k]

    results = []
    for position in ranked_positions:
        chunk = dict(chunks[eligible_indices[int(position)]])
        chunk["score"] = float(scores[int(position)])
        results.append(chunk)
    return results


def find_album(documents: list[dict], title: str) -> dict:
    matches = [
        album for album in documents if album["title"].casefold() == title.casefold()
    ]
    if not matches:
        raise ValueError(f"Unknown album: {title}")
    if len(matches) > 1:
        raise ValueError(f"Ambiguous album title: {title}")
    return matches[0]


def build_context(
    documents: list[dict],
    chunks: list[dict],
    vectors: np.ndarray,
    model: TextEmbedding,
    favorite_title: str,
    candidate_title: str,
    top_k: int,
) -> dict:
    """Combine structured facts with separately retrieved review evidence."""
    favorite = find_album(documents, favorite_title)
    candidate = find_album(documents, candidate_title)

    favorite_tags = {tag for tag in favorite["tags"] if is_taste_tag(tag)}
    candidate_tags = {tag for tag in candidate["tags"] if is_taste_tag(tag)}
    shared_tags = sorted(favorite_tags.intersection(candidate_tags))
    new_tags = sorted(candidate_tags - favorite_tags)
    query = (
        f"Musical qualities of {candidate['title']} by "
        f"{', '.join(candidate['artists'])}. "
        f"Connection to {favorite['title']}. "
        f"Shared descriptors: {', '.join(shared_tags) or 'none'}."
    )

    candidate_evidence = retrieve_chunks(
        chunks, vectors, model, query, candidate["title"], top_k
    )
    favorite_evidence = retrieve_chunks(
        chunks, vectors, model, query, favorite["title"], 1
    )

    context_lines = [
        "[STRUCTURED FACTS]",
        f"Favorite: {', '.join(favorite['artists'])} — {favorite['title']}",
        f"Candidate: {', '.join(candidate['artists'])} — {candidate['title']}",
        f"Shared tags: {', '.join(shared_tags) or 'none'}",
        f"Candidate new tags: {', '.join(new_tags) or 'none'}",
    ]

    evidence = candidate_evidence + favorite_evidence
    if evidence:
        context_lines.append("\n[RETRIEVED REVIEW EVIDENCE]")
        for item in evidence:
            context_lines.extend(
                [
                    (
                        f"Source {item['review_id']}#{item['chunk_index']} "
                        f"({item['album_title']}, score={item['score']:.4f}, "
                        f"license={item['license']})"
                    ),
                    item["text"],
                ]
            )
    else:
        context_lines.append("\n[RETRIEVED REVIEW EVIDENCE]\nNone available.")

    sources = [
        {
            "source_id": f'{item["review_id"]}#{item["chunk_index"]}',
            "review_id": item["review_id"],
            "album_title": item["album_title"],
            "source": item["source"],
            "source_url": item["source_url"],
            "license": item["license"],
        }
        for item in evidence
    ]
    return {
        "query": query,
        "shared_tags": shared_tags,
        "new_tags": new_tags,
        "candidate_evidence": candidate_evidence,
        "favorite_evidence": favorite_evidence,
        "context": "\n".join(context_lines),
        "sources": sources,
    }


def validate_generated_result(
    result: dict, allowed_source_ids: set[str]
) -> dict:
    """Reject unsupported consensus wording and invented citations."""
    generated_text = json.dumps(result, ensure_ascii=False).casefold()
    unsupported_terms = [
        term
        for term in UNSUPPORTED_CONSENSUS_TERMS
        if term.casefold() in generated_text
    ]
    if unsupported_terms:
        raise ValueError(
            "Gemini used unsupported consensus language: "
            + ", ".join(unsupported_terms)
        )

    cited_source_ids = {
        source_id
        for item in result["evidence"]
        for source_id in item["source_ids"]
    }
    invented_source_ids = cited_source_ids - allowed_source_ids
    if invented_source_ids:
        raise ValueError(
            "Gemini returned unknown source IDs: "
            + ", ".join(sorted(invented_source_ids))
        )
    return result


def generate_why_this(
    rag_result: dict,
    tier: str | None = None,
    recommendation: dict | None = None,
) -> dict:
    """Generate a grounded explanation and reject invented source IDs."""
    load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is missing from .env")

    allowed_source_ids = {
        source["source_id"] for source in rag_result["sources"]
    }
    source_instruction = (
        ", ".join(sorted(allowed_source_ids))
        if allowed_source_ids
        else "none"
    )
    tier_context = ""
    if tier and recommendation:
        tier_context = f"""
[RULE-BASED RECOMMENDATION DECISION]
Tier: {tier}
Profile similarity: {recommendation["profile_similarity"]:.4f}
Bridge favorite: {recommendation["bridge_favorite"]}
Bridge similarity: {recommendation["bridge_similarity"]:.4f}
Bridge tags: {", ".join(recommendation["bridge_tags"]) or "none"}
New tags: {", ".join(recommendation["new_tags"]) or "none"}
""".strip()

    tier_instruction = {
        "Safe": (
            "Explain why this is a close, low-risk extension of the current "
            "taste profile. Do not exaggerate novelty."
        ),
        "Explore": (
            "Balance the familiar bridge with the genuinely new direction. "
            "Do not describe it as either nearly identical or completely distant."
        ),
        "Wildcard": (
            "Be explicit that this is a more distant choice, then explain the "
            "specific bridge that makes the leap defensible."
        ),
    }.get(tier, "Do not assign a recommendation tier yourself.")
    prompt = f"""
You explain music recommendations using only the supplied context.
Write in clear Simplified Chinese, while keeping album and tag names unchanged.
Do not add musical facts, review claims, or sources that are absent from the context.
Treat each review as one source, not as general consensus. Do not use words such
as "often", "widely", "commonly", or their Chinese equivalents unless the
retrieved text explicitly supports that frequency. Prefer "the review says".
The recommendation tier was assigned by deterministic Python rules, not by you.
{tier_instruction}
Valid review source IDs: {source_instruction}
For review-based claims, source_ids must contain only IDs from that list.
For claims based only on structured tags, use an empty source_ids list.
If review evidence is missing or weak, say so honestly in limitations.

{tier_context}

{rag_result["context"]}
""".strip()

    client = genai.Client(
        http_options={
            "timeout": GEMINI_TIMEOUT_MS,
            "retry_options": {"attempts": 1},
        }
    )
    interaction = None
    last_transient_error = None
    for model_name in GEMINI_MODELS:
        try:
            interaction = client.interactions.create(
                model=model_name,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": WHY_THIS_SCHEMA,
                },
            )
            break
        except Exception as error:
            error_text = str(error).casefold()
            is_temporary = (
                "service_unavailable" in error_text
                or "high demand" in error_text
                or "error code: 503" in error_text
                or "too_many_requests" in error_text
                or "rate limit exceeded" in error_text
                or "error code: 429" in error_text
                or "timeout" in error_text
                or "timed out" in error_text
            )
            if not is_temporary:
                raise
            last_transient_error = error

    if interaction is None:
        raise RuntimeError(
            "Gemini free models are temporarily unavailable or rate-limited. "
            "Please try again later."
        ) from last_transient_error

    result = json.loads(interaction.output_text)
    return validate_generated_result(result, allowed_source_ids)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--favorite", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Call Gemini to generate a structured Why This? explanation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.top_k < 1:
        raise SystemExit("--top-k must be at least 1")

    documents = load_album_documents(args.database)
    chunks = load_review_chunks(args.database)
    if not chunks:
        raise SystemExit("No licensed review chunks are available")
    model, vectors = embed_chunks(chunks)
    try:
        result = build_context(
            documents,
            chunks,
            vectors,
            model,
            args.favorite,
            args.candidate,
            args.top_k,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    print(
        f"Review corpus: {len(chunks)} chunks x {vectors.shape[1]} dimensions"
    )
    print(f"Retrieval query: {result['query']}")
    print("\n--- RAG CONTEXT ---")
    print(result["context"])
    print("\n--- SOURCES ---")
    if not result["sources"]:
        print("No review sources; context uses structured facts only.")
    for source in result["sources"]:
        print(
            f"{source['source_id']} | {source['album_title']} | "
            f"{source['source']} | "
            f"{source['license']} | {source['source_url']}"
        )

    if args.generate:
        try:
            explanation = generate_why_this(result)
        except (RuntimeError, ValueError) as error:
            raise SystemExit(str(error)) from error
        print("\n--- WHY THIS? ---")
        print(json.dumps(explanation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
