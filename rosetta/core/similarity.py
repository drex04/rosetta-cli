from __future__ import annotations

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


def filter_decided_suggestions(result: dict[str, Any], log: list[SSSOMRow]) -> dict[str, Any]:
    """Filter suggestions based on HumanCuration decisions in the audit log.

    - Approved (HC + predicate != owl:differentFrom): subject removed entirely.
    - Rejected (HC + predicate == owl:differentFrom): only that (subject, object) pair removed.
    - If subject has both approved and rejected HC rows, approved wins (subject fully removed).
    - Empty log → return full result unchanged (as a new dict).

    Returns a new dict; does not mutate input.
    """
    hc_approved_subjects: set[str] = set()
    hc_rejected_pairs: set[tuple[str, str]] = set()

    for row in log:
        if row.mapping_justification != "semapv:HumanCuration":
            continue
        if row.predicate_id == "owl:differentFrom":
            hc_rejected_pairs.add((row.subject_id, row.object_id))
        else:
            hc_approved_subjects.add(row.subject_id)

    filtered: dict[str, Any] = {}
    for src_uri, entry in result.items():
        if src_uri in hc_approved_subjects:
            continue
        kept = [
            sug for sug in entry["suggestions"] if (src_uri, sug["uri"]) not in hc_rejected_pairs
        ]
        filtered[src_uri] = {"suggestions": kept}

    return filtered
