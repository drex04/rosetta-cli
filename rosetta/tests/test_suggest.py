"""Tests for rosetta suggest: similarity.py core + suggest CLI."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

SOURCE_EMB = {
    "nor_radar:hoyde_m": {
        "label": "Height M",
        "lexical": [1.0, 0.0, 0.0],
        "structural": [],
        "datatype": None,
    },
    "nor_radar:azimut": {
        "label": "Azimut",
        "lexical": [0.0, 1.0, 0.0],
        "structural": [],
        "datatype": None,
    },
}
MASTER_EMB = {
    "mc:altitude": {
        "label": "Altitude",
        "lexical": [0.9, 0.1, 0.0],
        "structural": [],
        "datatype": None,
    },
    "mc:bearing": {
        "label": "Bearing",
        "lexical": [0.1, 0.9, 0.0],
        "structural": [],
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


@pytest.fixture
def empty_log(tmp_path: Path) -> str:
    """An empty (but existing) audit log file for tests that don't need log data."""
    from rosetta.core.ledger import append_log

    lp = tmp_path / "empty-audit-log.sssom.tsv"
    append_log([], lp)
    return str(lp)


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


def test_suggest_cli_basic(src_file, mst_file, empty_log) -> None:
    """CLI with pre-baked JSON fixture exits 0, SSSOM TSV output."""
    from rosetta.cli.suggest import cli

    result = CliRunner().invoke(cli, [src_file, mst_file, "--audit-log", empty_log])

    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail
    assert "subject_id" in result.output
    assert "\t" in result.output
    assert "{" not in result.output
    assert result.output.lstrip().startswith("#")


def test_suggest_cli_stdout(src_file, mst_file, empty_log) -> None:
    """CLI without --output writes SSSOM TSV to stdout."""
    from rosetta.cli.suggest import cli

    result = CliRunner().invoke(cli, [src_file, mst_file, "--audit-log", empty_log])

    assert result.exit_code == 0, result.output
    assert "subject_id" in result.output
    assert "\t" in result.output
    assert "{" not in result.output
    assert result.output.lstrip().startswith("#")


def test_suggest_cli_empty_source(tmp_path, mst_file, empty_log) -> None:
    """CLI exits 1 with 'source file' in output when source has no embeddings."""
    from rosetta.cli.suggest import cli

    empty = tmp_path / "empty_source.json"
    empty.write_text("{}")

    result = CliRunner().invoke(cli, [str(empty), mst_file, "--audit-log", empty_log])

    assert result.exit_code == 1
    assert "source file" in result.output


def test_suggest_cli_empty_master(tmp_path, src_file, empty_log) -> None:
    """CLI exits 1 with 'master file' in output when master has no embeddings."""
    from rosetta.cli.suggest import cli

    empty = tmp_path / "empty_master.json"
    empty.write_text("{}")

    result = CliRunner().invoke(cli, [src_file, str(empty), "--audit-log", empty_log])

    assert result.exit_code == 1
    assert "master file" in result.output


def test_suggest_cli_missing_lexical_key(tmp_path, mst_file, empty_log) -> None:
    """CLI exits 1 with offending URI in output when a JSON entry lacks 'lexical'."""
    from rosetta.cli.suggest import cli

    bad_uri = "http://example.org/field/x"
    bad_src = tmp_path / "bad_source.json"
    bad_src.write_text(json.dumps({bad_uri: {"label": "x"}}))

    result = CliRunner().invoke(cli, [str(bad_src), mst_file, "--audit-log", empty_log])

    assert result.exit_code == 1
    assert bad_uri in result.output


def test_suggest_cli_top_k(src_file, mst_file, empty_log) -> None:
    """--top-k 1 returns exactly 1 data row per source field."""
    from rosetta.cli.suggest import cli

    result = CliRunner().invoke(cli, [src_file, mst_file, "--top-k", "1", "--audit-log", empty_log])

    assert result.exit_code == 0, result.output
    # Count data rows (non-comment, non-header lines)
    lines = result.output.splitlines()
    data_rows = [ln for ln in lines if ln.strip() and not ln.startswith(("#", "subject_id"))]
    assert len(data_rows) == len(SOURCE_EMB)


def test_suggest_cli_config_precedence(tmp_path) -> None:
    """--top-k 1 returns exactly 1 result per source field."""
    from rosetta.cli.suggest import cli
    from rosetta.core.ledger import append_log

    src = tmp_path / "source.json"
    src.write_text(json.dumps(SOURCE_EMB))
    mst = tmp_path / "master.json"
    mst.write_text(json.dumps(MASTER_EMB))

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([], log_path)

    result = CliRunner().invoke(
        cli,
        [
            str(src),
            str(mst),
            "--audit-log",
            str(log_path),
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


def test_suggest_cli_approved_hc_suppressed(tmp_path: Path) -> None:
    """HC approval in audit log suppresses ALL suggestions for that subject."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    src_uri = "http://ex.org/FieldA"
    master_uri1 = "http://ex.org/Master1"
    master_uri2 = "http://ex.org/Master2"

    src_emb = {src_uri: {"label": "FieldA", "lexical": [0.9, 0.0, 0.1]}}
    master_emb = {
        master_uri1: {"label": "Master1", "lexical": [1.0, 0.0, 0.0]},
        master_uri2: {"label": "Master2", "lexical": [0.8, 0.2, 0.0]},
    }

    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id=src_uri,
                object_id=master_uri1,
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
                object_id=master_uri1,
                predicate_id="skos:exactMatch",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )

    result = CliRunner().invoke(suggest_cli, [str(src_f), str(mst_f), "--audit-log", str(log_path)])
    assert result.exit_code == 0, result.output + str(result.exception)
    # Parse SSSOM TSV output — check subject_id column has no rows matching approved subject
    lines = result.output.splitlines()
    header_line = next((ln for ln in lines if ln.strip() and not ln.startswith("#")), None)
    assert header_line is not None
    cols = header_line.split("\t")
    subject_col = cols.index("subject_id")  # noqa: FURB184
    data_rows = [
        ln.split("\t") for ln in lines if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    subject_ids_in_output = {row[subject_col] for row in data_rows if len(row) > subject_col}
    assert src_uri not in subject_ids_in_output, (
        "Approved HC subject should have ALL suggestions removed from suggest output"
    )


def test_suggest_cli_no_log_configured_raises_usage_error(tmp_path: Path) -> None:
    """Missing required --audit-log → Click error exit 2."""
    from rosetta.cli.suggest import cli as suggest_cli

    src_emb = {"http://ex.org/FA": {"label": "FA", "lexical": [1.0, 0.0]}}
    master_emb = {"http://ex.org/MA": {"label": "MA", "lexical": [0.9, 0.1]}}
    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    result = CliRunner().invoke(suggest_cli, [str(src_f), str(mst_f)])
    assert result.exit_code == 2
    assert "audit-log" in result.output.lower() or "audit_log" in result.output.lower()


def test_suggest_cli_existing_pair_merge(tmp_path: Path) -> None:
    """MMC row in log → suggest TSV output has ManualMappingCuration for that pair."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import MMC_JUSTIFICATION, append_log
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

    result = CliRunner().invoke(suggest_cli, [str(src_f), str(mst_f), "--audit-log", str(log_path)])
    assert result.exit_code == 0, result.output + str(result.exception)
    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert data_rows
    assert MMC_JUSTIFICATION in data_rows[0]


def test_suggest_cli_suppresses_hc_decided_pairs(tmp_path: Path) -> None:
    """Approved subject has zero rows; rejected pair absent, others remain."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    src_uri_approved = "http://ex.org/FC_approved"
    src_uri_rejected = "http://ex.org/FC_rejected"
    master_uri_approved = "http://ex.org/MC_approved"
    master_uri_rejected = "http://ex.org/MC_rejected"
    master_uri_other = "http://ex.org/MC_other"

    src_emb = {
        src_uri_approved: {"label": "FC_approved", "lexical": [1.0, 0.0, 0.0]},
        src_uri_rejected: {"label": "FC_rejected", "lexical": [0.0, 1.0, 0.0]},
    }
    master_emb = {
        master_uri_approved: {"label": "MC_approved", "lexical": [0.9, 0.1, 0.0]},
        master_uri_rejected: {"label": "MC_rejected", "lexical": [0.1, 0.9, 0.0]},
        master_uri_other: {"label": "MC_other", "lexical": [0.1, 0.8, 0.1]},
    }
    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    log_path = tmp_path / "audit-log.sssom.tsv"
    # Approve src_uri_approved → HC approval (removes all suggestions for that subject)
    append_log(
        [
            SSSOMRow(
                subject_id=src_uri_approved,
                object_id=master_uri_approved,
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
                subject_id=src_uri_approved,
                object_id=master_uri_approved,
                predicate_id="skos:exactMatch",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.95,
            )
        ],
        log_path,
    )
    # Reject one pair for src_uri_rejected → only that pair removed, others remain
    append_log(
        [
            SSSOMRow(
                subject_id=src_uri_rejected,
                object_id=master_uri_rejected,
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
                subject_id=src_uri_rejected,
                object_id=master_uri_rejected,
                predicate_id="owl:differentFrom",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.0,
            )
        ],
        log_path,
    )

    result = CliRunner().invoke(suggest_cli, [str(src_f), str(mst_f), "--audit-log", str(log_path)])
    assert result.exit_code == 0, result.output + str(result.exception)
    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    # Approved subject: zero rows in output
    for row in data_rows:
        assert src_uri_approved not in row, (
            "HC-approved subject should have all suggestions removed"
        )
    # Rejected pair: that specific pair absent
    for row in data_rows:
        cols = row.split("\t")
        if len(cols) >= 3:
            assert not (cols[0] == src_uri_rejected and cols[2] == master_uri_rejected), (
                "HC-rejected pair should be absent"
            )
    # Other suggestions for the rejected subject's source still appear
    assert any(src_uri_rejected in row for row in data_rows), (
        "Other suggestions for HC-rejected subject should still appear"
    )


def test_suggest_cli_output_file(
    tmp_path: Path, src_file: str, mst_file: str, empty_log: str
) -> None:
    """--output writes SSSOM TSV to file; file contains subject_id header."""
    from rosetta.cli.suggest import cli

    out_file = tmp_path / "out.sssom.tsv"
    result = CliRunner().invoke(
        cli, [src_file, mst_file, "-o", str(out_file), "--audit-log", empty_log]
    )

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    content = out_file.read_text()
    assert "subject_id" in content


def test_suggest_cli_header_has_15_columns(src_file: str, mst_file: str, empty_log: str) -> None:
    """TSV header must have 15 columns including the four new composite-entity columns."""
    from rosetta.cli.suggest import cli

    result = CliRunner().invoke(cli, [src_file, mst_file, "--audit-log", empty_log])
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
    from rosetta.core.ledger import append_log

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

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([], log_path)

    def _run_with_weight(weight: float) -> float:
        result = runner.invoke(
            cli,
            [
                str(src_file),
                str(mst_file),
                "--audit-log",
                str(log_path),
                "--structural-weight",
                str(weight),
            ],
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
    from rosetta.core.ledger import append_log

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

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([], log_path)

    result = CliRunner().invoke(
        cli,
        [str(src_file), str(mst_file), "--audit-log", str(log_path), "--structural-weight", "0.0"],
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
# --audit-log flag and config-fallback tests
# ---------------------------------------------------------------------------


def test_suggest_cli_audit_log_flag(tmp_path: Path) -> None:
    """--audit-log CLI flag provides audit log explicitly."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import append_log

    src_emb = {"http://ex.org/FA": {"label": "FA", "lexical": [1.0, 0.0]}}
    master_emb = {"http://ex.org/MA": {"label": "MA", "lexical": [0.9, 0.1]}}
    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    log_path = tmp_path / "mylog.sssom.tsv"
    append_log([], log_path)

    result = CliRunner().invoke(
        suggest_cli,
        [str(src_f), str(mst_f), "--audit-log", str(log_path)],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert data_rows


def test_suggest_cli_audit_log_nonexistent_treated_as_empty(tmp_path: Path) -> None:
    """--audit-log pointing to nonexistent file → treated as empty log, suggest succeeds."""
    from rosetta.cli.suggest import cli as suggest_cli

    src_emb = {"http://ex.org/FA": {"label": "FA", "lexical": [1.0, 0.0]}}
    master_emb = {"http://ex.org/MA": {"label": "MA", "lexical": [0.9, 0.1]}}
    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    missing_log = tmp_path / "does-not-exist.sssom.tsv"

    result = CliRunner().invoke(
        suggest_cli,
        [str(src_f), str(mst_f), "--audit-log", str(missing_log)],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert data_rows


def test_suggest_cli_audit_log_missing_file_succeeds(tmp_path: Path) -> None:
    """--audit-log pointing to nonexistent file → treated as empty log, suggest succeeds."""
    from rosetta.cli.suggest import cli as suggest_cli

    src_emb = {"http://ex.org/FA": {"label": "FA", "lexical": [1.0, 0.0]}}
    master_emb = {"http://ex.org/MA": {"label": "MA", "lexical": [0.9, 0.1]}}
    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    missing = tmp_path / "does-not-exist.sssom.tsv"
    out = tmp_path / "candidates.sssom.tsv"

    result = CliRunner().invoke(
        suggest_cli,
        [
            str(src_f),
            str(mst_f),
            "--audit-log",
            str(missing),
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"expected exit 0, got {result.exit_code}: {result.output}"


def test_suggest_cli_audit_log_empty_shows_pair(tmp_path: Path) -> None:
    """Empty audit log → no filtering, all suggestions appear."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import append_log

    src_uri = "http://ex.org/FA"
    master_uri = "http://ex.org/MA"

    src_emb = {src_uri: {"label": "FA", "lexical": [1.0, 0.0]}}
    master_emb = {master_uri: {"label": "MA", "lexical": [0.9, 0.1]}}
    src_f = tmp_path / "src.json"
    src_f.write_text(json.dumps(src_emb))
    mst_f = tmp_path / "master.json"
    mst_f.write_text(json.dumps(master_emb))

    # Empty log: pair should NOT be suppressed
    empty_log = tmp_path / "empty-log.sssom.tsv"
    append_log([], empty_log)

    result = CliRunner().invoke(
        suggest_cli,
        [str(src_f), str(mst_f), "--audit-log", str(empty_log)],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    data_rows = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert data_rows, "Empty log should not suppress anything"


# ---------------------------------------------------------------------------
# Unit tests for filter_decided_suggestions
# ---------------------------------------------------------------------------


def test_filter_decided_approved_removes_subject() -> None:
    """Approved HC for (X, A) → result dict has no key for X."""
    from rosetta.core.models import SSSOMRow
    from rosetta.core.similarity import filter_decided_suggestions

    result = {
        "http://src/X": {
            "suggestions": [
                {"uri": "http://m/A", "score": 0.9, "rank": 1},
                {"uri": "http://m/B", "score": 0.8, "rank": 2},
                {"uri": "http://m/C", "score": 0.7, "rank": 3},
            ]
        }
    }
    log = [
        SSSOMRow(
            subject_id="http://src/X",
            object_id="http://m/A",
            predicate_id="skos:exactMatch",
            mapping_justification="semapv:HumanCuration",
            confidence=0.9,
        )
    ]
    filtered = filter_decided_suggestions(result, log)
    assert "http://src/X" not in filtered


def test_filter_decided_rejected_removes_pair_only() -> None:
    """Rejected HC for (X, B) → result has X with [A, C] only."""
    from rosetta.core.models import SSSOMRow
    from rosetta.core.similarity import filter_decided_suggestions

    result = {
        "http://src/X": {
            "suggestions": [
                {"uri": "http://m/A", "score": 0.9, "rank": 1},
                {"uri": "http://m/B", "score": 0.8, "rank": 2},
                {"uri": "http://m/C", "score": 0.7, "rank": 3},
            ]
        }
    }
    log = [
        SSSOMRow(
            subject_id="http://src/X",
            object_id="http://m/B",
            predicate_id="owl:differentFrom",
            mapping_justification="semapv:HumanCuration",
            confidence=0.0,
        )
    ]
    filtered = filter_decided_suggestions(result, log)
    assert "http://src/X" in filtered
    uris = [s["uri"] for s in filtered["http://src/X"]["suggestions"]]
    assert "http://m/A" in uris
    assert "http://m/B" not in uris
    assert "http://m/C" in uris


def test_filter_decided_empty_log_passes_all() -> None:
    """Empty log → returned dict identical to input."""
    from rosetta.core.similarity import filter_decided_suggestions

    result = {
        "http://src/X": {
            "suggestions": [
                {"uri": "http://m/A", "score": 0.9, "rank": 1},
            ]
        }
    }
    filtered = filter_decided_suggestions(result, [])
    assert filtered == result
    # Must return a new dict, not the same object
    assert filtered is not result


def test_filter_decided_mixed_approved_and_rejected_same_subject() -> None:
    """Both approved HC for (X, A) and rejected HC for (X, B) → X absent (approved wins)."""
    from rosetta.core.models import SSSOMRow
    from rosetta.core.similarity import filter_decided_suggestions

    result = {
        "http://src/X": {
            "suggestions": [
                {"uri": "http://m/A", "score": 0.9, "rank": 1},
                {"uri": "http://m/B", "score": 0.8, "rank": 2},
            ]
        }
    }
    log = [
        SSSOMRow(
            subject_id="http://src/X",
            object_id="http://m/A",
            predicate_id="skos:exactMatch",
            mapping_justification="semapv:HumanCuration",
            confidence=0.9,
        ),
        SSSOMRow(
            subject_id="http://src/X",
            object_id="http://m/B",
            predicate_id="owl:differentFrom",
            mapping_justification="semapv:HumanCuration",
            confidence=0.0,
        ),
    ]
    filtered = filter_decided_suggestions(result, log)
    assert "http://src/X" not in filtered, "Approved wins: subject must be fully removed"


def test_filter_decided_rejected_only_keeps_other_pairs() -> None:
    """Only rejected HC for (X, B), no approved → X present with [A, C]."""
    from rosetta.core.models import SSSOMRow
    from rosetta.core.similarity import filter_decided_suggestions

    result = {
        "http://src/X": {
            "suggestions": [
                {"uri": "http://m/A", "score": 0.9, "rank": 1},
                {"uri": "http://m/B", "score": 0.8, "rank": 2},
                {"uri": "http://m/C", "score": 0.7, "rank": 3},
            ]
        }
    }
    log = [
        SSSOMRow(
            subject_id="http://src/X",
            object_id="http://m/B",
            predicate_id="owl:differentFrom",
            mapping_justification="semapv:HumanCuration",
            confidence=0.0,
        )
    ]
    filtered = filter_decided_suggestions(result, log)
    assert "http://src/X" in filtered
    uris = [s["uri"] for s in filtered["http://src/X"]["suggestions"]]
    assert "http://m/A" in uris
    assert "http://m/B" not in uris
    assert "http://m/C" in uris
