"""Tests for rosetta-suggest: similarity.py core + suggest CLI."""

from __future__ import annotations

import json

import numpy as np
import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

SOURCE_EMB = {
    "http://rosetta.interop/field/NOR/nor_radar/hoyde_m": {
        "label": "Height M",
        "lexical": [1.0, 0.0, 0.0],
    },
    "http://rosetta.interop/field/NOR/nor_radar/azimut": {
        "label": "Azimut",
        "lexical": [0.0, 1.0, 0.0],
    },
}
MASTER_EMB = {
    "http://rosetta.interop/master/attr/altitude": {
        "label": "Altitude",
        "lexical": [0.9, 0.1, 0.0],
    },
    "http://rosetta.interop/master/attr/bearing": {"label": "Bearing", "lexical": [0.1, 0.9, 0.0]},
}


@pytest.fixture
def src_file(tmp_path):
    p = tmp_path / "source.json"
    p.write_text(json.dumps(SOURCE_EMB))
    return str(p)


@pytest.fixture
def mst_file(tmp_path):
    p = tmp_path / "master.json"
    p.write_text(json.dumps(MASTER_EMB))
    return str(p)


# ---------------------------------------------------------------------------
# Unit tests — cosine_matrix
# ---------------------------------------------------------------------------


def test_cosine_matrix_shape():
    """cosine_matrix returns shape (n, m) for inputs of shape (n, d) and (m, d)."""
    from rosetta.core.similarity import cosine_matrix

    A = np.random.rand(3, 8).astype(np.float32)
    B = np.random.rand(5, 8).astype(np.float32)
    result = cosine_matrix(A, B)
    assert result.shape == (3, 5)


def test_cosine_matrix_identical():
    """Identical vectors produce score 1.0."""
    from rosetta.core.similarity import cosine_matrix

    v = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    result = cosine_matrix(v, v)
    assert pytest.approx(result[0, 0], abs=1e-6) == 1.0


def test_cosine_matrix_orthogonal():
    """Orthogonal vectors produce score 0.0."""
    from rosetta.core.similarity import cosine_matrix

    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[0.0, 1.0, 0.0]], dtype=np.float32)
    result = cosine_matrix(A, B)
    assert pytest.approx(result[0, 0], abs=1e-6) == 0.0


def test_cosine_matrix_zero_vector():
    """Zero-norm row doesn't crash (clip guard)."""
    from rosetta.core.similarity import cosine_matrix

    A = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    result = cosine_matrix(A, B)
    assert result.shape == (1, 1)
    assert np.isfinite(result[0, 0])


def test_cosine_matrix_dim_mismatch():
    """Mismatched dimensions raise ValueError with descriptive message."""
    from rosetta.core.similarity import cosine_matrix

    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[1.0, 0.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="mismatch"):
        cosine_matrix(A, B)


# ---------------------------------------------------------------------------
# Unit tests — rank_suggestions
# ---------------------------------------------------------------------------


def test_rank_suggestions_order():
    """Highest score has rank 1."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    master_uris = ["http://m/altitude", "http://m/bearing"]
    B = np.array([[0.9, 0.1, 0.0], [0.1, 0.9, 0.0]], dtype=np.float32)

    result = rank_suggestions(src_uris, A, master_uris, B)
    suggestions = result["http://src/a"]["suggestions"]
    assert suggestions[0]["rank"] == 1
    assert suggestions[0]["score"] >= suggestions[1]["score"]


def test_rank_suggestions_top_k():
    """Only top_k results returned."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    master_uris = ["http://m/a", "http://m/b", "http://m/c", "http://m/d"]
    B = np.random.rand(4, 3).astype(np.float32)

    result = rank_suggestions(src_uris, A, master_uris, B, top_k=2)
    assert len(result["http://src/a"]["suggestions"]) == 2


def test_rank_suggestions_top_k_exceeds_master():
    """top_k > len(master) returns all master entries without crashing."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    master_uris = ["http://m/a", "http://m/b"]
    B = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)

    result = rank_suggestions(src_uris, A, master_uris, B, top_k=100)
    assert len(result["http://src/a"]["suggestions"]) == 2


def test_rank_suggestions_min_score():
    """Suggestions below min_score are excluded."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    master_uris = ["http://m/altitude", "http://m/bearing"]
    # altitude ~ cos 0.98+, bearing ~ cos 0.1 (orthogonalish)
    B = np.array([[0.99, 0.01, 0.0], [0.1, 0.9, 0.0]], dtype=np.float32)

    result = rank_suggestions(src_uris, A, master_uris, B, top_k=5, min_score=0.5)
    suggestions = result["http://src/a"]["suggestions"]
    assert all(s["score"] >= 0.5 for s in suggestions)
    uris = [s["uri"] for s in suggestions]
    assert "http://m/altitude" in uris
    assert "http://m/bearing" not in uris


def test_rank_suggestions_anomaly_true():
    """Field with max score < threshold gets anomaly: true."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    # Source vector that is mostly orthogonal to master vectors
    A = np.array([[0.0, 0.0, 1.0]], dtype=np.float32)
    master_uris = ["http://m/a", "http://m/b"]
    B = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)

    result = rank_suggestions(src_uris, A, master_uris, B, anomaly_threshold=0.3)
    assert result["http://src/a"]["anomaly"] is True


def test_rank_suggestions_anomaly_false():
    """Field with max score >= threshold gets anomaly: false."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    master_uris = ["http://m/a"]
    B = np.array([[0.9, 0.1, 0.0]], dtype=np.float32)

    result = rank_suggestions(src_uris, A, master_uris, B, anomaly_threshold=0.3)
    assert result["http://src/a"]["anomaly"] is False


def test_rank_suggestions_anomaly_pre_filter():
    """Field with good match filtered by high min_score is NOT anomalous.

    Anomaly is computed from raw scores BEFORE min_score filtering, so even
    if the best match is excluded by min_score, anomaly=False when raw max>=threshold.
    """
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    master_uris = ["http://m/a"]

    # Use a vector that scores ~0.98 but min_score=0.999 excludes it
    A2 = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B2 = np.array([[0.98, 0.2, 0.0]], dtype=np.float32)  # score will be < 1.0

    result = rank_suggestions(src_uris, A2, master_uris, B2, min_score=0.999, anomaly_threshold=0.3)
    # suggestions list will be empty (all filtered), but anomaly should be False
    # because raw max score (~0.98) >= anomaly_threshold (0.3)
    assert result["http://src/a"]["anomaly"] is False
    assert result["http://src/a"]["suggestions"] == []


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_suggest_cli_basic(src_file, mst_file):
    """CLI with pre-baked JSON fixture exits 0, valid JSON output."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--source", src_file, "--master", mst_file])

    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail
    data = json.loads(result.output)
    for uri in SOURCE_EMB:
        assert uri in data
        assert "suggestions" in data[uri]
        assert "anomaly" in data[uri]
        assert isinstance(data[uri]["anomaly"], bool)
        assert isinstance(data[uri]["suggestions"], list)


def test_suggest_cli_stdout(src_file, mst_file):
    """CLI without --output writes JSON to stdout."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--source", src_file, "--master", mst_file])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data) == len(SOURCE_EMB)


def test_suggest_cli_empty_source(tmp_path, mst_file):
    """CLI exits 1 with 'source file' in output when source has no embeddings."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    empty = tmp_path / "empty_source.json"
    empty.write_text("{}")

    result = runner.invoke(cli, ["--source", str(empty), "--master", mst_file])

    assert result.exit_code == 1
    assert "source file" in result.output


def test_suggest_cli_empty_master(tmp_path, src_file):
    """CLI exits 1 with 'master file' in output when master has no embeddings."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    empty = tmp_path / "empty_master.json"
    empty.write_text("{}")

    result = runner.invoke(cli, ["--source", src_file, "--master", str(empty)])

    assert result.exit_code == 1
    assert "master file" in result.output


def test_suggest_cli_missing_lexical_key(tmp_path, mst_file):
    """CLI exits 1 with offending URI in output when a JSON entry lacks 'lexical'."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    bad_uri = "http://example.org/field/x"
    bad_src = tmp_path / "bad_source.json"
    bad_src.write_text(json.dumps({bad_uri: {"label": "x"}}))

    result = runner.invoke(cli, ["--source", str(bad_src), "--master", mst_file])

    assert result.exit_code == 1
    assert bad_uri in result.output


def test_suggest_cli_top_k(src_file, mst_file):
    """--top-k 1 returns exactly 1 suggestion per field."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--source", src_file, "--master", mst_file, "--top-k", "1"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    for uri in SOURCE_EMB:
        assert len(data[uri]["suggestions"]) == 1


def test_suggest_cli_config_precedence(tmp_path):
    """--top-k CLI flag overrides top_k in rosetta.toml."""
    from rosetta.cli.suggest import cli

    # Write source and master files
    src = tmp_path / "source.json"
    src.write_text(json.dumps(SOURCE_EMB))
    mst = tmp_path / "master.json"
    mst.write_text(json.dumps(MASTER_EMB))

    # Write a rosetta.toml with top_k = 10
    toml_cfg = tmp_path / "rosetta.toml"
    toml_cfg.write_text("[suggest]\ntop_k = 10\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--source",
            str(src),
            "--master",
            str(mst),
            "--config",
            str(toml_cfg),
            "--top-k",
            "1",
        ],
    )

    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail
    data = json.loads(result.output)
    for uri in SOURCE_EMB:
        assert len(data[uri]["suggestions"]) <= 1


# ---------------------------------------------------------------------------
# Regression: top-k with min_score must return up to top_k qualifying entries
# ---------------------------------------------------------------------------


def test_rank_suggestions_top_k_with_min_score_returns_all_qualifying():
    """top_k=3 with min_score filtering should still return 3 results when 3+ qualify.

    Regression test: previously the loop broke on rank count including filtered
    entries, so fewer qualifying results were returned than top_k.
    """
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    A = np.array([[1.0, 0.0, 0.0, 0.0, 0.0]], dtype=np.float32)
    master_uris = [
        "http://m/a",  # score ~0.0 (orthogonal, filtered)
        "http://m/b",  # score ~0.0 (orthogonal, filtered)
        "http://m/c",  # score ~0.95
        "http://m/d",  # score ~0.90
        "http://m/e",  # score ~0.85
    ]
    B = np.array(
        [
            [0.0, 1.0, 0.0, 0.0, 0.0],  # a: orthogonal
            [0.0, 0.0, 1.0, 0.0, 0.0],  # b: orthogonal
            [0.95, 0.05, 0.0, 0.0, 0.0],  # c: high
            [0.90, 0.10, 0.0, 0.0, 0.0],  # d: high
            [0.85, 0.15, 0.0, 0.0, 0.0],  # e: high
        ],
        dtype=np.float32,
    )

    result = rank_suggestions(src_uris, A, master_uris, B, top_k=3, min_score=0.5)
    suggestions = result["http://src/a"]["suggestions"]
    assert len(suggestions) == 3, f"Expected 3 qualifying suggestions, got {len(suggestions)}"
    assert all(s["score"] >= 0.5 for s in suggestions)
    assert suggestions[0]["rank"] == 1
    assert suggestions[1]["rank"] == 2
    assert suggestions[2]["rank"] == 3
