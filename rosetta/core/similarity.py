import numpy as np


def cosine_matrix(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Return pairwise cosine similarity matrix, shape (len(A), len(B)).

    Uses (A @ B.T) / (||A|| * ||B||.T) — pure numpy, no scipy.
    Zero-norm rows are handled by clipping denominator to avoid division by zero.
    Raises ValueError if A and B have different vector dimensions.
    """
    if A.shape[1] != B.shape[1]:
        raise ValueError(
            f"Embedding dimension mismatch: source={A.shape[1]}, master={B.shape[1]}"
        )

    norms_a = np.linalg.norm(A, axis=1, keepdims=True)
    A_norm = A / np.clip(norms_a, 1e-10, None)

    norms_b = np.linalg.norm(B, axis=1, keepdims=True)
    B_norm = B / np.clip(norms_b, 1e-10, None)

    sim = A_norm @ B_norm.T
    return sim


def rank_suggestions(
    src_uris: list[str],
    A: np.ndarray,            # shape (n_src, dim)
    master_uris: list[str],
    B: np.ndarray,            # shape (n_master, dim)
    top_k: int = 5,
    min_score: float = 0.0,
    anomaly_threshold: float = 0.3,
) -> dict:
    """Compute ranked suggestions for each source URI against all master URIs.

    Returns:
        {
            "<source_uri>": {
                "suggestions": [{"uri": str, "score": float, "rank": int}, ...],
                "anomaly": bool
            }
        }
    Scores rounded to 6 decimal places. Rank is 1-based.
    Anomaly computed from raw scores BEFORE min_score filtering.
    If top_k > len(master), returns all master entries sorted by score.
    """
    sim = cosine_matrix(A, B)
    n_take = min(top_k, len(master_uris))
    result = {}

    for i, src_uri in enumerate(src_uris):
        sim_row = sim[i]

        max_sim = float(sim_row.max())
        anomaly = max_sim < anomaly_threshold

        sorted_indices = np.argsort(sim_row)[::-1]

        suggestions = []
        rank = 1
        for idx in sorted_indices:
            score = round(float(sim_row[idx]), 6)
            if score < min_score:
                continue
            suggestions.append({"uri": master_uris[idx], "score": score, "rank": rank})
            rank += 1
            if rank > n_take:
                break

        result[src_uri] = {
            "suggestions": suggestions,
            "anomaly": anomaly,
        }

    return result
