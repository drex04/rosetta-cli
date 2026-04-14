from __future__ import annotations

from typing import Any

import numpy as np

from rosetta.core.models import Ledger, SSSOMRow


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
    """
    sim = cosine_matrix(A, B)
    n_take = min(top_k, len(master_uris))
    result = {}

    for i, src_uri in enumerate(src_uris):
        sim_row = sim[i]

        sorted_indices = np.argsort(sim_row)[::-1]

        suggestions = []
        for idx in sorted_indices:
            score = round(float(sim_row[idx]), 6)
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


def apply_ledger_feedback(
    source_uri: str,
    candidates: list[dict[str, Any]],
    ledger: Ledger,
    boost: float = 0.1,
) -> list[dict[str, Any]]:
    """Adjust candidates based on accreditation ledger entries.

    - status == "accredited" → add boost, cap at 1.0
    - status == "revoked"    → remove candidate from list entirely
    - status == "pending"    → no change (pass through)
    Returns a new list (does not mutate input).
    """
    import copy

    result = []
    for cand in candidates:
        obj_id = str(cand.get("uri", ""))
        entry = next(
            (e for e in ledger.mappings if e.source_uri == source_uri and e.target_uri == obj_id),
            None,
        )
        if entry is None or entry.status == "pending":
            result.append(copy.deepcopy(cand))
        elif entry.status == "accredited":
            c = copy.deepcopy(cand)
            c["score"] = min(float(c["score"]) + boost, 1.0)
            result.append(c)
        # revoked → omit entirely

    return result


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
    import copy

    result = copy.deepcopy(candidates)

    # Find differentFrom rows for this subject
    diff_from_rows = [
        r
        for r in approved_rows
        if r.subject_id == subject_id and r.predicate_id == "owl:differentFrom"
    ]
    diff_from_object_ids = {r.object_id for r in diff_from_rows}
    has_diff_from = len(diff_from_rows) > 0

    for cand in result:
        obj_id = str(cand.get("uri", ""))
        if obj_id in diff_from_object_ids:
            # Hard derank: subtract penalty, floor at 0.0
            cand["score"] = max(float(cand["score"]) - penalty, 0.0)
        elif has_diff_from:
            # Soft breadth penalty: other candidates get penalty * 0.25
            cand["score"] = max(float(cand["score"]) - penalty * 0.25, 0.0)
        else:
            # Check for boost: any non-differentFrom row matching this pair
            boost_rows = [
                r
                for r in approved_rows
                if r.subject_id == subject_id
                and r.object_id == obj_id
                and r.predicate_id != "owl:differentFrom"
            ]
            if boost_rows:
                cand["score"] = min(float(cand["score"]) + boost, 1.0)

    return result
