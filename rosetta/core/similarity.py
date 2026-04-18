from __future__ import annotations

import copy
from typing import Any

import numpy as np

from rosetta.core.models import SSSOMRow


def cosine_matrix(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Return pairwise cosine similarity matrix, shape (len(A), len(B)).

    Uses (A @ B.T) / (||A|| * ||B||.T) — pure numpy, no scipy.
    Zero-norm rows are handled by clipping denominator to avoid division by zero.
    Raises ValueError if A and B have different vector dimensions.
    """
    if A.shape[1] != B.shape[1]:
        raise ValueError(f"Embedding dimension mismatch: source={A.shape[1]}, master={B.shape[1]}")

    norms_a = np.linalg.norm(A, axis=1, keepdims=True)
    A_norm = A / np.clip(norms_a, 1e-10, None)

    norms_b = np.linalg.norm(B, axis=1, keepdims=True)
    B_norm = B / np.clip(norms_b, 1e-10, None)

    sim = A_norm @ B_norm.T
    return sim


def rank_suggestions(
    src_uris: list[str],
    A: np.ndarray,  # shape (n_src, dim)
    master_uris: list[str],
    B: np.ndarray,  # shape (n_master, dim)
    top_k: int = 5,
    min_score: float = 0.0,
    *,
    A_struct: np.ndarray | None = None,
    B_struct: np.ndarray | None = None,
    structural_weight: float = 0.2,
) -> dict[str, Any]:
    """Compute ranked suggestions for each source URI against all master URIs.

    Returns:
        {
            "<source_uri>": {
                "suggestions": [{"uri": str, "score": float, "rank": int}, ...]
            }
        }
    Scores rounded to 6 decimal places. Rank is 1-based.
    If top_k > len(master), returns all master entries sorted by score.

    Optional structural blending:
        If A_struct and B_struct are both provided and neither is all-zero,
        the final score is a weighted blend:
            final = (1 - structural_weight) * lex_sim + structural_weight * struct_sim
        Otherwise falls back to lexical-only (silent, no warning here).
    """
    lex_sim = cosine_matrix(A, B)

    final: np.ndarray
    if (
        A_struct is not None
        and B_struct is not None
        and np.any(A_struct != 0)
        and np.any(B_struct != 0)
    ):
        struct_sim = cosine_matrix(A_struct, B_struct)
        final = (1.0 - structural_weight) * lex_sim + structural_weight * struct_sim
    else:
        final = lex_sim

    n_take = min(top_k, len(master_uris))
    result = {}

    for i, src_uri in enumerate(src_uris):
        final_row = final[i]

        sorted_indices = np.argsort(final_row)[::-1]

        suggestions = []
        for idx in sorted_indices:
            score = round(float(final_row[idx]), 6)
            if score < min_score:
                continue
            suggestions.append({"uri": master_uris[idx], "score": score, "rank": len(suggestions)})
            if len(suggestions) >= n_take:
                break

        # Assign 1-based ranks after collection
        for rank_idx, sug in enumerate(suggestions, 1):
            sug["rank"] = rank_idx

        result[src_uri] = {
            "suggestions": suggestions,
        }

    return result


def _adjusted_score(
    cand_score: float,
    obj_id: str,
    subject_id: str,
    diff_from_object_ids: set[str],
    has_diff_from: bool,
    approved_rows: list[SSSOMRow],
    boost: float,
    penalty: float,
) -> float:
    """Compute the feedback-adjusted score for a single candidate."""
    if obj_id in diff_from_object_ids:
        return max(cand_score - penalty, 0.0)
    if has_diff_from:
        return max(cand_score - penalty * 0.25, 0.0)
    boost_match = any(
        r.subject_id == subject_id
        and r.object_id == obj_id
        and r.predicate_id != "owl:differentFrom"
        for r in approved_rows
    )
    return min(cand_score + boost, 1.0) if boost_match else cand_score


def apply_sssom_feedback(
    subject_id: str,
    candidates: list[dict[str, Any]],
    approved_rows: list[SSSOMRow],
    boost: float = 0.1,
    penalty: float = 0.2,
) -> list[dict[str, Any]]:
    """Boost or derank candidates based on approved SSSOM rows.

    - Row predicate_id == owl:differentFrom → subtract penalty (floor 0.0), row NOT removed.
    - Any other predicate match on (subject_id, object_id) → add boost (cap 1.0).
    - If ANY differentFrom row exists for subject_id → apply penalty * 0.25 to all
      OTHER candidates for that field (soft subject-breadth deranking).
    Returns a new list (does not mutate input).
    """
    result = copy.deepcopy(candidates)

    diff_from_object_ids = {
        r.object_id
        for r in approved_rows
        if r.subject_id == subject_id and r.predicate_id == "owl:differentFrom"
    }
    has_diff_from = bool(diff_from_object_ids)

    for cand in result:
        obj_id = str(cand.get("uri", ""))
        cand["score"] = _adjusted_score(
            float(cand["score"]),
            obj_id,
            subject_id,
            diff_from_object_ids,
            has_diff_from,
            approved_rows,
            boost,
            penalty,
        )

    return result
