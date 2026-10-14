"""In-memory FAISS search over compatible protected video segments."""

from __future__ import annotations

import faiss
import numpy as np

from app.services.firestore_db import list_clip_segment_embeddings
from app.services.verdict import (
    content_score_from_cosine,
    verdict_from_score,
)


class SearchIndexError(RuntimeError):
    """Raised when the protected segment catalog cannot be searched."""


def _bounded_similarity(value: float) -> float:
    """Keep floating-point cosine scores inside their mathematical range."""

    return max(-1.0, min(1.0, float(value)))


def _normalise(matrix: np.ndarray) -> np.ndarray:
    """Normalize embedding rows so FAISS inner products equal cosine scores."""

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms <= 0) or not np.all(np.isfinite(norms)):
        raise SearchIndexError("Embedding vectors must have a non-zero finite norm")
    return matrix / norms


def build_segment_index() -> tuple[faiss.Index, list[dict]]:
    """Build an exact normalized-inner-product index from Firestore segments."""

    records = list_clip_segment_embeddings()
    if not records:
        raise SearchIndexError("No compatible protected video embeddings are available")

    dimension = int(records[0]["embedding_dimension"])
    matrix = np.asarray([record["embedding"] for record in records], dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] != dimension:
        raise SearchIndexError("Protected embedding dimensions do not match")
    matrix = _normalise(matrix)

    index = faiss.IndexFlatIP(dimension)
    index.add(matrix)
    return index, records


def search_video_segments(
    query_segments: list[dict],
    *,
    limit: int = 10,
) -> list[dict]:
    """Search query segments and aggregate their strongest matches per clip."""

    if not query_segments:
        raise SearchIndexError("At least one query video segment is required")
    if limit <= 0:
        raise SearchIndexError("Search limit must be greater than zero")

    index, records = build_segment_index()
    dimension = index.d
    grouped: dict[str, dict] = {}
    k = min(limit, index.ntotal)

    for query_number, query_segment in enumerate(query_segments):
        vector = np.asarray([query_segment.get("embedding")], dtype=np.float32)
        if vector.ndim != 2 or vector.shape[1] != dimension:
            raise SearchIndexError("Query and protected embedding dimensions do not match")
        vector = _normalise(vector)
        scores, neighbors = index.search(vector, k)

        per_clip: dict[str, tuple[float, dict]] = {}
        for score, row in zip(scores[0], neighbors[0]):
            if row < 0:
                continue
            record = records[int(row)]
            current = per_clip.get(record["clip_id"])
            if current is None or float(score) > current[0]:
                per_clip[record["clip_id"]] = (_bounded_similarity(score), record)

        for clip_id, (score, record) in per_clip.items():
            clip = grouped.setdefault(
                clip_id,
                {
                    "protected_clip_id": clip_id,
                    "protected_title": record["title"],
                    "query_scores": {},
                    "matched_segments": [],
                },
            )
            clip["query_scores"][query_number] = score
            if score >= 0.75:
                clip["matched_segments"].append(
                    {
                        "query_segment_id": query_segment.get("segment_id") or f"segment_{query_number:03d}",
                        "protected_segment_id": record["segment_id"],
                        "query_start_offset_seconds": float(
                            query_segment.get("start_offset_seconds", 0.0)
                        ),
                        "query_end_offset_seconds": float(
                            query_segment.get("end_offset_seconds", 0.0)
                        ),
                        "protected_start_offset_seconds": record["start_offset_seconds"],
                        "protected_end_offset_seconds": record["end_offset_seconds"],
                        "similarity": content_score_from_cosine(score),
                    }
                )

    results: list[dict] = []
    query_count = len(query_segments)
    for clip in grouped.values():
        # Missing query segments count as non-matches. This prevents a clip
        # with one accidental strong neighbor from looking like a full copy.
        all_scores = [
            clip["query_scores"].get(query_number, -1.0)
            for query_number in range(query_count)
        ]
        scores = sorted(all_scores, reverse=True)
        top_scores = scores[:3]
        strength = max(0.0, min(1.0, sum(top_scores) / len(top_scores)))
        matched_count = len(clip["matched_segments"])
        coverage = matched_count / query_count
        similarity = (0.5 * strength) + (0.5 * coverage)
        results.append(
            {
                "protected_clip_id": clip["protected_clip_id"],
                "protected_title": clip["protected_title"],
                "content_similarity": content_score_from_cosine(similarity),
                "verdict": verdict_from_score(similarity),
                "matched_segment_count": matched_count,
                "segment_coverage": coverage,
                "matched_segments": clip["matched_segments"],
            }
        )

    results.sort(key=lambda result: result["content_similarity"], reverse=True)
    return results
