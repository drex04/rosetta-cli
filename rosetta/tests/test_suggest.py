"""Tests for rosetta-suggest: similarity.py core + suggest CLI."""

from __future__ import annotations

import json
import math
from pathlib import Path

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
        "datatype": None,
    },
    "http://rosetta.interop/field/NOR/nor_radar/azimut": {
        "label": "Azimut",
        "lexical": [0.0, 1.0, 0.0],
        "datatype": None,
    },
}
MASTER_EMB = {
    "http://rosetta.interop/master/attr/altitude": {
        "label": "Altitude",
        "lexical": [0.9, 0.1, 0.0],
        "datatype": None,
    },
    "http://rosetta.interop/master/attr/bearing": {
        "label": "Bearing",
        "lexical": [0.1, 0.9, 0.0],
        "datatype": None,
    },
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

    result = CliRunner().invoke(cli, [src_file, mst_file])

    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail
    assert "subject_id" in result.output
    assert "\t" in result.output
    assert "{" not in result.output
    assert result.output.lstrip().startswith("#")


def test_suggest_cli_stdout(src_file, mst_file) -> None:
    """CLI without --output writes SSSOM TSV to stdout."""
    from rosetta.cli.suggest import cli

    result = CliRunner().invoke(cli, [src_file, mst_file])

    assert result.exit_code == 0, result.output
    assert "subject_id" in result.output
    assert "\t" in result.output
    assert "{" not in result.output
    assert result.output.lstrip().startswith("#")


def test_suggest_cli_empty_source(tmp_path, mst_file) -> None:
    """CLI exits 1 with 'source file' in output when source has no embeddings."""
    from rosetta.cli.suggest import cli

    empty = tmp_path / "empty_source.json"
    empty.write_text("{}")

    result = CliRunner().invoke(cli, [str(empty), mst_file])

    assert result.exit_code == 1
    assert "source file" in result.output


def test_suggest_cli_empty_master(tmp_path, src_file) -> None:
    """CLI exits 1 with 'master file' in output when master has no embeddings."""
    from rosetta.cli.suggest import cli

    empty = tmp_path / "empty_master.json"
    empty.write_text("{}")

    result = CliRunner().invoke(cli, [src_file, str(empty)])

    assert result.exit_code == 1
    assert "master file" in result.output


def test_suggest_cli_missing_lexical_key(tmp_path, mst_file) -> None:
    """CLI exits 1 with offending URI in output when a JSON entry lacks 'lexical'."""
    from rosetta.cli.suggest import cli

    bad_uri = "http://example.org/field/x"
    bad_src = tmp_path / "bad_source.json"
    bad_src.write_text(json.dumps({bad_uri: {"label": "x"}}))

    result = CliRunner().invoke(cli, [str(bad_src), mst_file])

    assert result.exit_code == 1
    assert bad_uri in result.output


def test_suggest_cli_top_k(src_file, mst_file) -> None:
    """--top-k 1 returns exactly 1 data row per source field."""
    from rosetta.cli.suggest import cli

    result = CliRunner().invoke(cli, [src_file, mst_file, "--top-k", "1"])

    assert result.exit_code == 0, result.output
    # Count data rows (non-comment, non-header lines)
    lines = result.output.splitlines()
    data_rows = [ln for ln in lines if ln.strip() and not ln.startswith(("#", "subject_id"))]
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

    result = CliRunner().invoke(
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
    data_rows = [ln for ln in lines if ln.strip() and not ln.startswith(("#", "subject_id"))]
    # 1 result per source field (2 fields × 1 = 2 rows)
    assert len(data_rows) <= len(SOURCE_EMB)


def test_suggest_cli_log_based_boost(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """HC approval in audit log boosts candidate confidence."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    sin_val = math.sqrt(1.0 - 0.81)
    src_uri = "http://ex.org/FieldA"
    master_uri = "http://ex.org/Master1"

    src_emb = {src_uri: {"label": "FieldA", "lexical": [0.9, 0.0, sin_val]}}
    master_emb = {master_uri: {"label": "Master1", "lexical": [1.0, 0.0, 0.0]}}

    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    runner = CliRunner()
    baseline = runner.invoke(suggest_cli, [str(src_f), str(mst_f)])
    assert baseline.exit_code == 0, baseline.output
    baseline_data = [
        ln
        for ln in baseline.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    baseline_score = float(baseline_data[0].split("\t")[4])

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id=src_uri,
                object_id=master_uri,
                predicate_id="skos:exactMatch",
                mapping_justification=MMC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )
    append_log(
        [
            SSSOMRow(
                subject_id=src_uri,
                object_id=master_uri,
                predicate_id="skos:exactMatch",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )

    result = runner.invoke(suggest_cli, [str(src_f), str(mst_f), "--config", str(tmp_rosetta_toml)])
    assert result.exit_code == 0, result.output + str(result.exception)
    boosted_data = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    boosted_score = float(boosted_data[0].split("\t")[4])
    assert boosted_score > baseline_score


def test_suggest_cli_log_based_derank(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """HC owl:differentFrom in audit log deranks candidate confidence."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    src_uri = "http://ex.org/FieldB"
    master_uri = "http://ex.org/Master2"

    src_emb = {src_uri: {"label": "FieldB", "lexical": [1.0, 0.0, 0.0]}}
    master_emb = {master_uri: {"label": "Master2", "lexical": [0.9, 0.1, 0.0]}}

    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    runner = CliRunner()
    baseline = runner.invoke(suggest_cli, [str(src_f), str(mst_f)])
    assert baseline.exit_code == 0, baseline.output
    baseline_data = [
        ln
        for ln in baseline.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    baseline_score = float(baseline_data[0].split("\t")[4])

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id=src_uri,
                object_id=master_uri,
                predicate_id="skos:exactMatch",
                mapping_justification=MMC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )
    append_log(
        [
            SSSOMRow(
                subject_id=src_uri,
                object_id=master_uri,
                predicate_id="owl:differentFrom",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.0,
            )
        ],
        log_path,
    )

    result = runner.invoke(suggest_cli, [str(src_f), str(mst_f), "--config", str(tmp_rosetta_toml)])
    assert result.exit_code == 0, result.output + str(result.exception)
    deranked_data = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    deranked_score = float(deranked_data[0].split("\t")[4])
    assert deranked_score < baseline_score


def test_suggest_cli_no_log_configured_passthrough(tmp_path: Path) -> None:
    """Config without [accredit] section → suggest runs normally."""
    from rosetta.cli.suggest import cli as suggest_cli

    config = tmp_path / "rosetta.toml"
    config.write_text("[suggest]\ntop_k = 5\n")

    src_emb = {"http://ex.org/FA": {"label": "FA", "lexical": [1.0, 0.0]}}
    master_emb = {"http://ex.org/MA": {"label": "MA", "lexical": [0.9, 0.1]}}
    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    result = CliRunner().invoke(suggest_cli, [str(src_f), str(mst_f), "--config", str(config)])
    assert result.exit_code == 0, result.output + str(result.exception)
    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert data_rows
    # No log-based justification override — row has LexicalMatching
    assert "LexicalMatching" in data_rows[0]


def test_suggest_cli_existing_pair_merge(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """MMC row in log → suggest TSV output has ManualMappingCuration for that pair."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.accredit import MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    src_uri = "http://ex.org/FC"
    master_uri = "http://ex.org/MC"

    src_emb = {src_uri: {"label": "FC", "lexical": [1.0, 0.0]}}
    master_emb = {master_uri: {"label": "MC", "lexical": [0.9, 0.1]}}
    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id=src_uri,
                object_id=master_uri,
                predicate_id="skos:exactMatch",
                mapping_justification=MMC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )

    result = CliRunner().invoke(
        suggest_cli, [str(src_f), str(mst_f), "--config", str(tmp_rosetta_toml)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert data_rows
    assert MMC_JUSTIFICATION in data_rows[0]


def test_suggest_cli_output_file(tmp_path: Path, src_file: str, mst_file: str) -> None:
    """--output writes SSSOM TSV to file; file contains subject_id header."""
    from rosetta.cli.suggest import cli

    out_file = tmp_path / "out.sssom.tsv"
    result = CliRunner().invoke(cli, [src_file, mst_file, "--output", str(out_file)])

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    content = out_file.read_text()
    assert "subject_id" in content


def test_suggest_cli_header_has_15_columns(src_file: str, mst_file: str) -> None:
    """TSV header must have 15 columns including the four new composite-entity columns."""
    from rosetta.cli.suggest import cli

    result = CliRunner().invoke(cli, [src_file, mst_file])
    assert result.exit_code == 0, result.output

    # Find the header line (not a comment line)
    columns = next(
        ln for ln in result.output.splitlines() if ln.strip() and not ln.startswith("#")
    ).split("\t")
    assert len(columns) == 15, f"Expected 15 columns, got {len(columns)}: {columns}"
    assert "subject_datatype" in columns
    assert "object_datatype" in columns
    assert "subject_type" in columns
    assert "object_type" in columns
    assert "mapping_group_id" in columns
    assert "composition_expr" in columns
    assert columns[11:] == ["subject_type", "object_type", "mapping_group_id", "composition_expr"]


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
        data_rows = [ln for ln in lines if ln.strip() and not ln.startswith(("#", "subject_id"))]
        assert data_rows, "Expected at least one data row"
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

    result = CliRunner().invoke(
        cli,
        [str(src_file), str(mst_file), "--config", str(toml_file)],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert data_rows, "Expected at least one data row"
    fields = data_rows[0].split("\t")
    mapping_justification = fields[3]

    assert mapping_justification == "semapv:LexicalMatching", (
        f"structural_weight=0.0 must emit LexicalMatching, got: {mapping_justification}"
    )


# ---------------------------------------------------------------------------
# Direct unit tests for _adjusted_score — covers all 4 branches
# (review-2: previously only tested transitively via apply_sssom_feedback;
# soft-derank 0.25 coefficient had no regression guard.)
# ---------------------------------------------------------------------------


def _hc_row(subject: str, obj: str, predicate: str = "skos:exactMatch"):
    from rosetta.core.models import SSSOMRow

    return SSSOMRow(
        subject_id=subject,
        predicate_id=predicate,
        object_id=obj,
        mapping_justification="semapv:HumanCuration",
        confidence=1.0,
    )


class TestAdjustedScore:
    """Exercise every branch of _adjusted_score with boundary values."""

    def test_exact_differentfrom_match_subtracts_full_penalty(self) -> None:
        from rosetta.core.similarity import _adjusted_score

        score = _adjusted_score(
            cand_score=0.9,
            obj_id="obj:X",
            subject_id="subj:A",
            diff_from_object_ids={"obj:X"},
            has_diff_from=True,
            approved_rows=[],
            boost=0.1,
            penalty=0.2,
        )
        assert score == pytest.approx(0.7)

    def test_exact_differentfrom_match_floors_at_zero(self) -> None:
        from rosetta.core.similarity import _adjusted_score

        score = _adjusted_score(
            cand_score=0.1,
            obj_id="obj:X",
            subject_id="subj:A",
            diff_from_object_ids={"obj:X"},
            has_diff_from=True,
            approved_rows=[],
            boost=0.1,
            penalty=0.5,
        )
        assert score == 0.0

    def test_soft_derank_uses_quarter_penalty_coefficient(self) -> None:
        """Regression guard for the 0.25 soft subject-breadth penalty coefficient.

        If anyone changes 0.25, this test will fail — the value is a correctness
        invariant of apply_sssom_feedback's derank design.
        """
        from rosetta.core.similarity import _adjusted_score

        score = _adjusted_score(
            cand_score=0.8,
            obj_id="obj:OTHER",
            subject_id="subj:A",
            diff_from_object_ids={"obj:X"},  # subject has diffFrom, but not for obj:OTHER
            has_diff_from=True,
            approved_rows=[],
            boost=0.1,
            penalty=0.2,
        )
        # 0.8 - (0.2 * 0.25) = 0.8 - 0.05 = 0.75
        assert score == pytest.approx(0.75)

    def test_soft_derank_floors_at_zero(self) -> None:
        from rosetta.core.similarity import _adjusted_score

        score = _adjusted_score(
            cand_score=0.01,
            obj_id="obj:OTHER",
            subject_id="subj:A",
            diff_from_object_ids={"obj:X"},
            has_diff_from=True,
            approved_rows=[],
            boost=0.1,
            penalty=1.0,  # 1.0 * 0.25 = 0.25; 0.01 - 0.25 → floor 0.0
        )
        assert score == 0.0

    def test_boost_match_adds_boost_when_approved_row_matches(self) -> None:
        from rosetta.core.similarity import _adjusted_score

        approved = [_hc_row("subj:A", "obj:X", "skos:exactMatch")]
        score = _adjusted_score(
            cand_score=0.7,
            obj_id="obj:X",
            subject_id="subj:A",
            diff_from_object_ids=set(),
            has_diff_from=False,
            approved_rows=approved,
            boost=0.1,
            penalty=0.2,
        )
        assert score == pytest.approx(0.8)

    def test_boost_match_caps_at_one(self) -> None:
        from rosetta.core.similarity import _adjusted_score

        approved = [_hc_row("subj:A", "obj:X", "skos:closeMatch")]
        score = _adjusted_score(
            cand_score=0.95,
            obj_id="obj:X",
            subject_id="subj:A",
            diff_from_object_ids=set(),
            has_diff_from=False,
            approved_rows=approved,
            boost=0.3,
            penalty=0.2,
        )
        assert score == 1.0

    def test_boost_ignores_differentfrom_rows(self) -> None:
        """owl:differentFrom rows in approved_rows must NOT trigger a boost."""
        from rosetta.core.similarity import _adjusted_score

        approved = [_hc_row("subj:A", "obj:X", "owl:differentFrom")]
        score = _adjusted_score(
            cand_score=0.5,
            obj_id="obj:X",
            subject_id="subj:A",
            diff_from_object_ids=set(),  # caller didn't flag; check boost path only
            has_diff_from=False,
            approved_rows=approved,
            boost=0.1,
            penalty=0.2,
        )
        assert score == pytest.approx(0.5)  # passthrough, no boost

    def test_passthrough_when_no_feedback_applies(self) -> None:
        from rosetta.core.similarity import _adjusted_score

        score = _adjusted_score(
            cand_score=0.42,
            obj_id="obj:UNSEEN",
            subject_id="subj:A",
            diff_from_object_ids=set(),
            has_diff_from=False,
            approved_rows=[],
            boost=0.1,
            penalty=0.2,
        )
        assert score == pytest.approx(0.42)
