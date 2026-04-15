"""Tests for rosetta-suggest: similarity.py core + suggest CLI."""

from __future__ import annotations

import json
import math

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


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_suggest_cli_basic(src_file, mst_file) -> None:
    """CLI with pre-baked JSON fixture exits 0, SSSOM TSV output."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    result = runner.invoke(cli, [src_file, mst_file])

    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail
    assert "subject_id" in result.output
    assert "\t" in result.output
    assert "{" not in result.output
    assert result.output.lstrip().startswith("#")


def test_suggest_cli_stdout(src_file, mst_file) -> None:
    """CLI without --output writes SSSOM TSV to stdout."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    result = runner.invoke(cli, [src_file, mst_file])

    assert result.exit_code == 0, result.output
    assert "subject_id" in result.output
    assert "\t" in result.output
    assert "{" not in result.output
    assert result.output.lstrip().startswith("#")


def test_suggest_cli_empty_source(tmp_path, mst_file) -> None:
    """CLI exits 1 with 'source file' in output when source has no embeddings."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    empty = tmp_path / "empty_source.json"
    empty.write_text("{}")

    result = runner.invoke(cli, [str(empty), mst_file])

    assert result.exit_code == 1
    assert "source file" in result.output


def test_suggest_cli_empty_master(tmp_path, src_file) -> None:
    """CLI exits 1 with 'master file' in output when master has no embeddings."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    empty = tmp_path / "empty_master.json"
    empty.write_text("{}")

    result = runner.invoke(cli, [src_file, str(empty)])

    assert result.exit_code == 1
    assert "master file" in result.output


def test_suggest_cli_missing_lexical_key(tmp_path, mst_file) -> None:
    """CLI exits 1 with offending URI in output when a JSON entry lacks 'lexical'."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    bad_uri = "http://example.org/field/x"
    bad_src = tmp_path / "bad_source.json"
    bad_src.write_text(json.dumps({bad_uri: {"label": "x"}}))

    result = runner.invoke(cli, [str(bad_src), mst_file])

    assert result.exit_code == 1
    assert bad_uri in result.output


def test_suggest_cli_top_k(src_file, mst_file) -> None:
    """--top-k 1 returns exactly 1 data row per source field."""
    from rosetta.cli.suggest import cli

    runner = CliRunner()
    result = runner.invoke(cli, [src_file, mst_file, "--top-k", "1"])

    assert result.exit_code == 0, result.output
    # Count data rows (non-comment, non-header lines)
    lines = result.output.splitlines()
    data_rows = [
        ln
        for ln in lines
        if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
    ]
    assert len(data_rows) == len(SOURCE_EMB)


def test_suggest_cli_config_precedence(tmp_path) -> None:
    """--top-k CLI flag overrides top_k in rosetta.toml."""
    from rosetta.cli.suggest import cli

    src = tmp_path / "source.json"
    src.write_text(json.dumps(SOURCE_EMB))
    mst = tmp_path / "master.json"
    mst.write_text(json.dumps(MASTER_EMB))

    toml_cfg = tmp_path / "rosetta.toml"
    toml_cfg.write_text("[suggest]\ntop_k = 10\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            str(src),
            str(mst),
            "--config",
            str(toml_cfg),
            "--top-k",
            "1",
        ],
    )

    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail
    lines = result.output.splitlines()
    data_rows = [
        ln
        for ln in lines
        if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
    ]
    # 1 result per source field (2 fields × 1 = 2 rows)
    assert len(data_rows) <= len(SOURCE_EMB)


def test_suggest_cli_approved_mappings(tmp_path) -> None:
    """--approved-mappings boosts a matching candidate's confidence."""
    from rosetta.cli.suggest import cli

    # Use non-collinear vectors: src=[0.9, 0, sqrt(1-0.81)], master=[1,0,0]
    # cosine ~ 0.9; after boost of 0.1 → ~1.0 (capped)
    sin_val = math.sqrt(1.0 - 0.81)
    src_uri = "http://ex.org/FieldA"
    master_uri = "http://ex.org/Master1"

    src_emb = {src_uri: {"label": "FieldA", "lexical": [0.9, 0.0, sin_val]}}
    master_emb = {master_uri: {"label": "Master1", "lexical": [1.0, 0.0, 0.0]}}

    src_file = tmp_path / "src.json"
    src_file.write_text(json.dumps(src_emb))
    mst_file = tmp_path / "master.json"
    mst_file.write_text(json.dumps(master_emb))

    approved_tsv = tmp_path / "approved.sssom.tsv"
    approved_tsv.write_text(
        "# curie_map:\n"
        "#   skos: http://www.w3.org/2004/02/skos/core#\n"
        "#   semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tconfidence\n"
        f"{src_uri}\tskos:relatedMatch\t{master_uri}\tsemapv:LexicalMatching\t0.8\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [str(src_file), str(mst_file), "--approved-mappings", str(approved_tsv)],
    )
    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail

    # Parse confidence from TSV output
    lines = result.output.splitlines()
    data_rows = [
        ln
        for ln in lines
        if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
    ]
    assert len(data_rows) >= 1
    cols = data_rows[0].split("\t")
    # confidence is 5th column (index 4)
    confidence = float(cols[4])
    # baseline cosine ~0.9, boosted by 0.1 → ~1.0 (capped)
    assert confidence == pytest.approx(1.0, abs=0.05)


def test_suggest_cli_derank_revoked(tmp_path) -> None:
    """owl:differentFrom in approved mappings decreases candidate confidence below baseline."""
    from rosetta.cli.suggest import cli

    src_uri = "http://ex.org/FieldB"
    master_uri = "http://ex.org/Master2"

    src_emb = {src_uri: {"label": "FieldB", "lexical": [1.0, 0.0, 0.0]}}
    master_emb = {master_uri: {"label": "Master2", "lexical": [0.9, 0.1, 0.0]}}

    src_file = tmp_path / "src.json"
    src_file.write_text(json.dumps(src_emb))
    mst_file = tmp_path / "master.json"
    mst_file.write_text(json.dumps(master_emb))

    runner = CliRunner()

    # Run without approved mappings to get baseline
    baseline_result = runner.invoke(cli, [str(src_file), str(mst_file)])
    assert baseline_result.exit_code == 0, baseline_result.output
    baseline_lines = baseline_result.output.splitlines()
    baseline_data = [
        ln
        for ln in baseline_lines
        if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
    ]
    baseline_confidence = float(baseline_data[0].split("\t")[4])

    # Write owl:differentFrom approved mappings
    approved_tsv = tmp_path / "approved.sssom.tsv"
    approved_tsv.write_text(
        "# curie_map:\n"
        "#   skos: http://www.w3.org/2004/02/skos/core#\n"
        "#   semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tconfidence\n"
        f"{src_uri}\towl:differentFrom\t{master_uri}\tsemapv:LexicalMatching\t0.0\n"
    )

    derank_result = runner.invoke(
        cli,
        [str(src_file), str(mst_file), "--approved-mappings", str(approved_tsv)],
    )
    assert derank_result.exit_code == 0, derank_result.output
    derank_lines = derank_result.output.splitlines()
    derank_data = [
        ln
        for ln in derank_lines
        if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
    ]
    deranked_confidence = float(derank_data[0].split("\t")[4])

    assert deranked_confidence < baseline_confidence


def test_suggest_cli_missing_approved_mappings(tmp_path, src_file, mst_file) -> None:
    """--approved-mappings pointing to a non-existent file exits 1 with path in output."""
    from rosetta.cli.suggest import cli

    non_existent = str(tmp_path / "non_existent.sssom.tsv")
    runner = CliRunner()
    result = runner.invoke(cli, [src_file, mst_file, "--approved-mappings", non_existent])

    assert result.exit_code == 1
    assert "non_existent.sssom.tsv" in result.output or "non_existent.sssom.tsv" in (
        result.stderr or ""
    )


def test_suggest_cli_output_file(tmp_path, src_file, mst_file) -> None:
    """--output writes SSSOM TSV to file; file contains subject_id header."""
    from rosetta.cli.suggest import cli

    out_file = tmp_path / "out.sssom.tsv"
    runner = CliRunner()
    result = runner.invoke(cli, [src_file, mst_file, "--output", str(out_file)])

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    content = out_file.read_text()
    assert "subject_id" in content


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


# ---------------------------------------------------------------------------
# Structural blending tests
# ---------------------------------------------------------------------------


def test_rank_suggestions_structural_blend() -> None:
    """Non-collinear structural vectors → blended score differs from lexical-only."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    master_uris = ["http://master/b"]

    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[0.9, 0.1, 0.0]], dtype=np.float32)

    # Non-collinear structural vectors
    A_struct = np.array([[1.0, 0.0, 0.0, 0.0, 0.0]], dtype=np.float32)
    B_struct = np.array([[0.0, 1.0, 0.0, 0.0, 0.0]], dtype=np.float32)

    lex_result = rank_suggestions(src_uris, A, master_uris, B)
    blend_result = rank_suggestions(
        src_uris,
        A,
        master_uris,
        B,
        A_struct=A_struct,
        B_struct=B_struct,
        structural_weight=0.5,
    )

    lex_score = lex_result["http://src/a"]["suggestions"][0]["score"]
    blend_score = blend_result["http://src/a"]["suggestions"][0]["score"]

    assert lex_score != blend_score, (
        f"Expected blended score ({blend_score}) to differ from lexical-only ({lex_score})"
    )


def test_rank_suggestions_structural_fallback() -> None:
    """A_struct/B_struct=None → identical to lexical-only result."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    master_uris = ["http://master/b"]

    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[0.9, 0.1, 0.0]], dtype=np.float32)

    lex_result = rank_suggestions(src_uris, A, master_uris, B)
    fallback_result = rank_suggestions(src_uris, A, master_uris, B, A_struct=None, B_struct=None)

    lex_score = lex_result["http://src/a"]["suggestions"][0]["score"]
    fallback_score = fallback_result["http://src/a"]["suggestions"][0]["score"]

    assert lex_score == fallback_score, (
        f"Fallback (no struct) should match lexical-only: {lex_score} vs {fallback_score}"
    )


def test_rank_suggestions_structural_weight_zero() -> None:
    """structural_weight=0.0 → pure lexical scores."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    master_uris = ["http://master/b"]

    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[0.9, 0.1, 0.0]], dtype=np.float32)

    A_struct = np.array([[1.0, 0.0, 0.0, 0.0, 0.0]], dtype=np.float32)
    B_struct = np.array([[0.0, 1.0, 0.0, 0.0, 0.0]], dtype=np.float32)

    lex_result = rank_suggestions(src_uris, A, master_uris, B)
    zero_w_result = rank_suggestions(
        src_uris,
        A,
        master_uris,
        B,
        A_struct=A_struct,
        B_struct=B_struct,
        structural_weight=0.0,
    )

    lex_score = lex_result["http://src/a"]["suggestions"][0]["score"]
    zero_w_score = zero_w_result["http://src/a"]["suggestions"][0]["score"]

    assert lex_score == zero_w_score, (
        f"structural_weight=0 should equal lexical-only: {lex_score} vs {zero_w_score}"
    )


def test_rank_suggestions_structural_partial_zeros() -> None:
    """src has non-zero structural, master has all-zero rows → fallback to lexical-only."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    master_uris = ["http://master/b"]

    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[0.9, 0.1, 0.0]], dtype=np.float32)

    A_struct = np.array([[1.0, 0.0, 0.0, 0.0, 0.0]], dtype=np.float32)
    B_struct = np.array([[0.0, 0.0, 0.0, 0.0, 0.0]], dtype=np.float32)  # all-zero

    lex_result = rank_suggestions(src_uris, A, master_uris, B)
    partial_result = rank_suggestions(
        src_uris,
        A,
        master_uris,
        B,
        A_struct=A_struct,
        B_struct=B_struct,
        structural_weight=0.5,
    )

    lex_score = lex_result["http://src/a"]["suggestions"][0]["score"]
    partial_score = partial_result["http://src/a"]["suggestions"][0]["score"]

    assert lex_score == partial_score, (
        f"All-zero master struct should fall back to lexical: {lex_score} vs {partial_score}"
    )


def test_suggest_cli_structural_weight_config(tmp_path) -> None:
    """CLI with non-default structural_weight produces different confidence than default."""
    import json as _json

    from rosetta.cli.suggest import cli

    runner = CliRunner()

    src_emb = {
        "schema/A": {
            "label": "A",
            "lexical": [1.0, 0.0, 0.0],
            "structural": [1.0, 0.0, 0.0, 0.0, 0.0],
        }
    }
    master_emb = {
        "schema/B": {
            "label": "B",
            "lexical": [0.9, 0.1, 0.0],
            "structural": [0.0, 1.0, 0.0, 0.0, 0.0],  # non-collinear
        }
    }

    src_file = tmp_path / "src.json"
    mst_file = tmp_path / "mst.json"
    src_file.write_text(_json.dumps(src_emb))
    mst_file.write_text(_json.dumps(master_emb))

    def _run_with_weight(weight: float) -> float:
        toml_file = tmp_path / f"rosetta_{weight}.toml"
        toml_file.write_text(f"[suggest]\nstructural_weight = {weight}\n")
        result = runner.invoke(
            cli,
            [str(src_file), str(mst_file), "--config", str(toml_file)],
        )
        assert result.exit_code == 0, f"CLI failed (weight={weight}): {result.output}"
        lines = result.output.splitlines()
        data_rows = [
            ln
            for ln in lines
            if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
        ]
        assert len(data_rows) >= 1, "Expected at least one data row"
        fields = data_rows[0].split("\t")
        return float(fields[4])  # confidence column index 4

    score_a = _run_with_weight(0.5)
    score_b = _run_with_weight(0.1)

    assert score_a != score_b, (
        f"Different structural_weight values should produce different confidence: "
        f"0.5→{score_a}, 0.1→{score_b}"
    )


def test_suggest_cli_structural_weight_zero_disables_blending(tmp_path) -> None:
    """structural_weight=0.0 in rosetta.toml → LexicalMatching, not CompositeMatching.

    Regression guard for the falsy-zero bug: `get_config_value(...) or 0.2` would
    override an explicit 0.0 with 0.2, activating blending against the user's intent.
    """
    import json as _json

    from rosetta.cli.suggest import cli

    runner = CliRunner()

    src_emb = {
        "schema/A": {
            "label": "A",
            "lexical": [1.0, 0.0, 0.0],
            "structural": [1.0, 0.0, 0.0, 0.0, 0.0],
        }
    }
    master_emb = {
        "schema/B": {
            "label": "B",
            "lexical": [0.9, 0.1, 0.0],
            "structural": [0.0, 1.0, 0.0, 0.0, 0.0],  # non-collinear → blending changes score
        }
    }

    src_file = tmp_path / "src.json"
    mst_file = tmp_path / "mst.json"
    src_file.write_text(_json.dumps(src_emb))
    mst_file.write_text(_json.dumps(master_emb))

    toml_file = tmp_path / "rosetta_zero.toml"
    toml_file.write_text("[suggest]\nstructural_weight = 0.0\n")

    result = runner.invoke(
        cli,
        [str(src_file), str(mst_file), "--config", str(toml_file)],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
    ]
    assert len(data_rows) >= 1, "Expected at least one data row"
    fields = data_rows[0].split("\t")
    mapping_justification = fields[3]

    assert mapping_justification == "semapv:LexicalMatching", (
        f"structural_weight=0.0 must emit LexicalMatching, got: {mapping_justification}"
    )
