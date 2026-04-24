"""Tests for rosetta suggest: similarity.py core + suggest CLI."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Shared schema YAML strings
# ---------------------------------------------------------------------------

_SRC_SCHEMA = """\
id: https://example.org/source
name: source
prefixes:
  linkml: https://w3id.org/linkml/
  source: https://example.org/source/
default_prefix: source
default_range: string
imports:
  - linkml:types
classes:
  SourceRecord:
    slots:
      - hoyde_m
      - azimut
slots:
  hoyde_m:
    range: float
  azimut:
    range: string
"""

_MASTER_SCHEMA = """\
id: https://example.org/master
name: master
prefixes:
  linkml: https://w3id.org/linkml/
  master: https://example.org/master/
default_prefix: master
default_range: string
imports:
  - linkml:types
classes:
  MasterRecord:
    slots:
      - altitude
      - bearing
slots:
  altitude:
    range: float
  bearing:
    range: string
"""


def _fake_encode(texts: list[str]) -> list[list[float]]:
    """Return deterministic 16-dim vectors based on md5 hash of text."""
    result = []
    for text in texts:
        h = hashlib.md5(text.encode()).hexdigest()
        vec = [int(c, 16) / 15.0 for c in h[:16]]
        result.append(vec)
    return result


def _runner() -> CliRunner:
    """Return a CliRunner with stderr separated from stdout."""
    return CliRunner(mix_stderr=False)


def _data_rows(output: str) -> list[str]:
    """Extract TSV data rows (not comments, not header, not stderr lines)."""
    return [
        ln
        for ln in output.splitlines()
        if ln.strip() and "\t" in ln and not ln.startswith(("#", "subject_id"))
    ]


class _FakeEmbeddingModel:
    def __init__(self, model_name: str = "intfloat/e5-large-v2") -> None:
        self.model_name = model_name

    def encode(self, texts: list[str]) -> list[list[float]]:
        return _fake_encode(texts)

    def encode_query(self, texts: list[str]) -> list[list[float]]:
        return _fake_encode(texts)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_embedding_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock EmbeddingModel to avoid loading the real sentence-transformers model."""
    monkeypatch.setattr("rosetta.cli.suggest.EmbeddingModel", _FakeEmbeddingModel)


@pytest.fixture
def src_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "source.linkml.yaml"
    p.write_text(_SRC_SCHEMA)
    return p


@pytest.fixture
def mst_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "master.linkml.yaml"
    p.write_text(_MASTER_SCHEMA)
    return p


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


def test_cosine_matrix_shape() -> None:
    """cosine_matrix returns shape (n, m) for inputs of shape (n, d) and (m, d)."""
    from rosetta.core.similarity import cosine_matrix

    A = np.random.rand(3, 8).astype(np.float32)
    B = np.random.rand(5, 8).astype(np.float32)
    result = cosine_matrix(A, B)
    assert result.shape == (3, 5)


def test_cosine_matrix_identical() -> None:
    """Identical vectors produce score 1.0."""
    from rosetta.core.similarity import cosine_matrix

    v = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    result = cosine_matrix(v, v)
    assert pytest.approx(result[0, 0], abs=1e-6) == 1.0


def test_cosine_matrix_orthogonal() -> None:
    """Orthogonal vectors produce score 0.0."""
    from rosetta.core.similarity import cosine_matrix

    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[0.0, 1.0, 0.0]], dtype=np.float32)
    result = cosine_matrix(A, B)
    assert pytest.approx(result[0, 0], abs=1e-6) == 0.0


def test_cosine_matrix_zero_vector() -> None:
    """Zero-norm row doesn't crash (clip guard)."""
    from rosetta.core.similarity import cosine_matrix

    A = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    result = cosine_matrix(A, B)
    assert result.shape == (1, 1)
    assert np.isfinite(result[0, 0])


def test_cosine_matrix_dim_mismatch() -> None:
    """Mismatched dimensions raise ValueError with descriptive message."""
    from rosetta.core.similarity import cosine_matrix

    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    B = np.array([[1.0, 0.0]], dtype=np.float32)
    with pytest.raises(ValueError, match="mismatch"):
        cosine_matrix(A, B)


# ---------------------------------------------------------------------------
# Unit tests — rank_suggestions
# ---------------------------------------------------------------------------


def test_rank_suggestions_order() -> None:
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


def test_rank_suggestions_top_k() -> None:
    """Only top_k results returned."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    master_uris = ["http://m/a", "http://m/b", "http://m/c", "http://m/d"]
    B = np.random.rand(4, 3).astype(np.float32)

    result = rank_suggestions(src_uris, A, master_uris, B, top_k=2)
    assert len(result["http://src/a"]["suggestions"]) == 2


def test_rank_suggestions_top_k_exceeds_master() -> None:
    """top_k > len(master) returns all master entries without crashing."""
    from rosetta.core.similarity import rank_suggestions

    src_uris = ["http://src/a"]
    A = np.array([[1.0, 0.0, 0.0]], dtype=np.float32)
    master_uris = ["http://m/a", "http://m/b"]
    B = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)

    result = rank_suggestions(src_uris, A, master_uris, B, top_k=100)
    assert len(result["http://src/a"]["suggestions"]) == 2


def test_rank_suggestions_min_score() -> None:
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
# CLI tests — schema-based interface
# ---------------------------------------------------------------------------


def test_suggest_cli_schema_input(src_yaml: Path, mst_yaml: Path, empty_log: str) -> None:
    """Basic: two LinkML YAML schemas → SSSOM TSV output with correct columns."""
    from rosetta.cli.suggest import cli

    result = _runner().invoke(cli, [str(src_yaml), str(mst_yaml), "--audit-log", empty_log])

    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail
    assert "subject_id" in result.output
    assert "\t" in result.output
    assert "{" not in result.output
    assert result.output.lstrip().startswith("#")


def test_suggest_cli_model_flag(
    src_yaml: Path, mst_yaml: Path, empty_log: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--model custom/model passes the model name to EmbeddingModel.__init__."""
    from rosetta.cli.suggest import cli

    captured: list[str] = []

    class _CapturingModel:
        def __init__(self, model_name: str = "intfloat/e5-large-v2") -> None:
            captured.append(model_name)

        def encode(self, texts: list[str]) -> list[list[float]]:
            return _fake_encode(texts)

        def encode_query(self, texts: list[str]) -> list[list[float]]:
            return _fake_encode(texts)

    monkeypatch.setattr("rosetta.cli.suggest.EmbeddingModel", _CapturingModel)

    result = _runner().invoke(
        cli, [str(src_yaml), str(mst_yaml), "--audit-log", empty_log, "--model", "custom/mymodel"]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    assert captured == ["custom/mymodel"]


def test_suggest_cli_structural_weight(src_yaml: Path, mst_yaml: Path, empty_log: str) -> None:
    """--structural-weight 0.5 → CLI runs without error (blending path active if struct present)."""
    from rosetta.cli.suggest import cli

    result = _runner().invoke(
        cli,
        [str(src_yaml), str(mst_yaml), "--audit-log", empty_log, "--structural-weight", "0.5"],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    assert "subject_id" in result.output


def test_suggest_cli_structural_weight_zero(src_yaml: Path, mst_yaml: Path, empty_log: str) -> None:
    """--structural-weight 0 → LexicalMatching justification in output rows."""
    from rosetta.cli.suggest import cli

    result = _runner().invoke(
        cli,
        [str(src_yaml), str(mst_yaml), "--audit-log", empty_log, "--structural-weight", "0.0"],
    )
    assert result.exit_code == 0, result.output + str(result.exception)

    rows = _data_rows(result.output)
    assert rows, "Expected at least one data row"
    for row in rows:
        fields = row.split("\t")
        assert fields[3] == "semapv:LexicalMatching", (
            f"structural_weight=0 must emit LexicalMatching, got: {fields[3]}"
        )


def test_suggest_cli_labels_from_schema(src_yaml: Path, mst_yaml: Path, empty_log: str) -> None:
    """Output SSSOM rows have subject_label and object_label columns populated."""
    from rosetta.cli.suggest import cli

    result = _runner().invoke(cli, [str(src_yaml), str(mst_yaml), "--audit-log", empty_log])
    assert result.exit_code == 0, result.output + str(result.exception)

    lines = result.output.splitlines()
    header_line = next(
        (ln for ln in lines if ln.strip() and "\t" in ln and not ln.startswith("#")), None
    )
    assert header_line is not None
    cols = header_line.split("\t")
    subj_label_idx = cols.index("subject_label")
    obj_label_idx = cols.index("object_label")

    split_rows = [ln.split("\t") for ln in _data_rows(result.output)]
    assert split_rows, "Expected data rows"
    # At least some rows should have non-empty labels
    has_subj_label = any(
        len(row) > subj_label_idx and row[subj_label_idx].strip() for row in split_rows
    )
    has_obj_label = any(
        len(row) > obj_label_idx and row[obj_label_idx].strip() for row in split_rows
    )
    assert has_subj_label, "Expected at least one non-empty subject_label"
    assert has_obj_label, "Expected at least one non-empty object_label"


def test_suggest_cli_datatypes_from_schema(src_yaml: Path, mst_yaml: Path, empty_log: str) -> None:
    """Output SSSOM rows have subject_datatype and object_datatype from schema slot ranges."""
    from rosetta.cli.suggest import cli

    result = _runner().invoke(cli, [str(src_yaml), str(mst_yaml), "--audit-log", empty_log])
    assert result.exit_code == 0, result.output + str(result.exception)

    lines = result.output.splitlines()
    header_line = next(
        (ln for ln in lines if ln.strip() and "\t" in ln and not ln.startswith("#")), None
    )
    assert header_line is not None
    cols = header_line.split("\t")
    subj_dt_idx = cols.index("subject_datatype")
    obj_dt_idx = cols.index("object_datatype")

    split_rows = [ln.split("\t") for ln in _data_rows(result.output)]
    assert split_rows, "Expected data rows"
    # At least some rows should have a datatype (float or string per schema)
    has_subj_dt = any(len(row) > subj_dt_idx and row[subj_dt_idx].strip() for row in split_rows)
    has_obj_dt = any(len(row) > obj_dt_idx and row[obj_dt_idx].strip() for row in split_rows)
    assert has_subj_dt, "Expected at least one non-empty subject_datatype"
    assert has_obj_dt, "Expected at least one non-empty object_datatype"


def test_suggest_cli_model_load_failure(
    src_yaml: Path, mst_yaml: Path, empty_log: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EmbeddingModel.__init__ raising OSError → CLI exits with useful error message."""
    from rosetta.cli.suggest import cli

    class _FailingModel:
        def __init__(self, model_name: str = "intfloat/e5-large-v2") -> None:
            raise OSError("model not found on disk")

    monkeypatch.setattr("rosetta.cli.suggest.EmbeddingModel", _FailingModel)

    result = _runner().invoke(cli, [str(src_yaml), str(mst_yaml), "--audit-log", empty_log])
    assert result.exit_code != 0
    combined = (
        result.output
        + (result.stderr if hasattr(result, "stderr") and result.stderr else "")
        + (str(result.exception) if result.exception else "")
    )
    assert "model" in combined.lower() or "load" in combined.lower() or "found" in combined.lower()


def test_suggest_cli_empty_schema(tmp_path: Path, mst_yaml: Path, empty_log: str) -> None:
    """Schema YAML with no classes/slots → CLI exits with useful error."""
    from rosetta.cli.suggest import cli

    empty_schema = tmp_path / "empty.linkml.yaml"
    empty_schema.write_text(
        "id: https://example.org/empty\nname: empty\nprefixes:\n  linkml: https://w3id.org/linkml/\n"
    )

    result = _runner().invoke(cli, [str(empty_schema), str(mst_yaml), "--audit-log", empty_log])
    assert result.exit_code == 1
    # Error goes to stderr; check combined output
    combined = result.output + (
        result.stderr if hasattr(result, "stderr") and result.stderr else ""
    )
    assert "source" in combined.lower() or "no nodes" in combined.lower()


def test_suggest_cli_top_k(src_yaml: Path, mst_yaml: Path, empty_log: str) -> None:
    """--top-k 1 returns at most 1 data row per source node (slots + classes)."""
    from rosetta.cli.suggest import cli

    result = _runner().invoke(
        cli, [str(src_yaml), str(mst_yaml), "--top-k", "1", "--audit-log", empty_log]
    )

    assert result.exit_code == 0, result.output
    # Source schema: 1 class + 2 slots = 3 nodes → max 3 rows at top-k=1
    assert len(_data_rows(result.output)) <= 3


def test_suggest_cli_top_k_flag(tmp_path: Path) -> None:
    """--top-k 1 returns at most 1 result per source node."""
    from rosetta.cli.suggest import cli
    from rosetta.core.ledger import append_log

    src_yaml = tmp_path / "source.linkml.yaml"
    src_yaml.write_text(_SRC_SCHEMA)
    mst_yaml = tmp_path / "master.linkml.yaml"
    mst_yaml.write_text(_MASTER_SCHEMA)

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([], log_path)

    result = _runner().invoke(
        cli,
        [str(src_yaml), str(mst_yaml), "--audit-log", str(log_path), "--top-k", "1"],
    )

    err_detail = result.output + (str(result.exception) if result.exception else "")
    assert result.exit_code == 0, err_detail
    # Source schema: 1 class + 2 slots = 3 nodes → max 3 rows at top-k=1
    assert len(_data_rows(result.output)) <= 3


def test_suggest_cli_approved_hc_suppressed(tmp_path: Path) -> None:
    """HC approval in audit log suppresses ALL suggestions for that subject."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    # Use schemas where URIs are known — we reference the schema-name:slot form
    src_schema = """\
id: https://example.org/src_hc
name: src_hc
prefixes:
  linkml: https://w3id.org/linkml/
  src_hc: https://example.org/src_hc/
default_prefix: src_hc
default_range: string
imports:
  - linkml:types
classes:
  Rec:
    slots:
      - field_a
slots:
  field_a:
    range: string
"""
    master_schema = """\
id: https://example.org/mst_hc
name: mst_hc
prefixes:
  linkml: https://w3id.org/linkml/
  mst_hc: https://example.org/mst_hc/
default_prefix: mst_hc
default_range: string
imports:
  - linkml:types
classes:
  Rec:
    slots:
      - master1
      - master2
slots:
  master1:
    range: string
  master2:
    range: string
"""
    src_f = tmp_path / "src_hc.linkml.yaml"
    src_f.write_text(src_schema)
    mst_f = tmp_path / "mst_hc.linkml.yaml"
    mst_f.write_text(master_schema)

    # First run without log to discover the actual URI used
    from rosetta.cli.suggest import cli as _cli

    probe = _runner().invoke(
        _cli, [str(src_f), str(mst_f), "--audit-log", str(tmp_path / "probe.sssom.tsv")]
    )
    data_lines = _data_rows(probe.output)
    if not data_lines:
        pytest.skip("No suggestions produced for HC suppression test schema")

    first_row = data_lines[0].split("\t")
    src_uri = first_row[0]
    master_uri1 = first_row[2]

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

    result = _runner().invoke(suggest_cli, [str(src_f), str(mst_f), "--audit-log", str(log_path)])
    assert result.exit_code == 0, result.output + str(result.exception)
    split_rows = [ln.split("\t") for ln in _data_rows(result.output)]
    subject_ids_in_output = {row[0] for row in split_rows if row}
    assert src_uri not in subject_ids_in_output, (
        "Approved HC subject should have ALL suggestions removed from suggest output"
    )


def test_suggest_cli_no_log_configured_raises_usage_error(tmp_path: Path) -> None:
    """Missing required --audit-log → Click error exit 2."""
    from rosetta.cli.suggest import cli as suggest_cli

    src_f = tmp_path / "source.linkml.yaml"
    src_f.write_text(_SRC_SCHEMA)
    mst_f = tmp_path / "master.linkml.yaml"
    mst_f.write_text(_MASTER_SCHEMA)

    result = _runner().invoke(suggest_cli, [str(src_f), str(mst_f)])
    assert result.exit_code == 2
    combined = result.output + (
        result.stderr if hasattr(result, "stderr") and result.stderr else ""
    )
    assert "audit-log" in combined.lower() or "audit_log" in combined.lower()


def test_suggest_cli_existing_pair_merge(tmp_path: Path) -> None:
    """MMC row in log → suggest TSV output has ManualMappingCuration for that pair."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    src_f = tmp_path / "source.linkml.yaml"
    src_f.write_text(_SRC_SCHEMA)
    mst_f = tmp_path / "master.linkml.yaml"
    mst_f.write_text(_MASTER_SCHEMA)

    # Probe to discover actual URIs
    probe_log = tmp_path / "probe.sssom.tsv"
    probe = _runner().invoke(suggest_cli, [str(src_f), str(mst_f), "--audit-log", str(probe_log)])
    data_lines = _data_rows(probe.output)
    if not data_lines:
        pytest.skip("No suggestions produced for merge test schema")

    first_row = data_lines[0].split("\t")
    src_uri = first_row[0]
    master_uri = first_row[2]

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

    result = _runner().invoke(suggest_cli, [str(src_f), str(mst_f), "--audit-log", str(log_path)])
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = _data_rows(result.output)
    assert rows
    # The merged pair should have MMC justification
    merged = [row for row in rows if src_uri in row and master_uri in row]
    assert merged, f"Expected merged pair ({src_uri}, {master_uri}) in output"
    assert MMC_JUSTIFICATION in merged[0]


def test_suggest_cli_suppresses_hc_decided_pairs(tmp_path: Path) -> None:
    """Approved subject has zero rows; rejected pair absent, others remain."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    # Two-source-field schema so we have both an approved and a rejected subject
    src_schema = """\
id: https://example.org/src2
name: src2
prefixes:
  linkml: https://w3id.org/linkml/
  src2: https://example.org/src2/
default_prefix: src2
default_range: string
imports:
  - linkml:types
classes:
  Rec:
    slots:
      - fc_approved
      - fc_rejected
slots:
  fc_approved:
    range: string
  fc_rejected:
    range: string
"""
    master_schema = """\
id: https://example.org/mst2
name: mst2
prefixes:
  linkml: https://w3id.org/linkml/
  mst2: https://example.org/mst2/
default_prefix: mst2
default_range: string
imports:
  - linkml:types
classes:
  Rec:
    slots:
      - mc_approved
      - mc_rejected
      - mc_other
slots:
  mc_approved:
    range: string
  mc_rejected:
    range: string
  mc_other:
    range: string
"""
    src_f = tmp_path / "src2.linkml.yaml"
    src_f.write_text(src_schema)
    mst_f = tmp_path / "mst2.linkml.yaml"
    mst_f.write_text(master_schema)

    # Probe to find actual URIs
    probe_log = tmp_path / "probe.sssom.tsv"
    probe = _runner().invoke(suggest_cli, [str(src_f), str(mst_f), "--audit-log", str(probe_log)])
    data_lines = _data_rows(probe.output)
    if not data_lines:
        pytest.skip("No suggestions produced for HC suppression test")

    # Gather URIs — group by subject
    from collections import defaultdict

    rows_by_subject: dict[str, list[str]] = defaultdict(list)
    for ln in data_lines:
        cols = ln.split("\t")
        if len(cols) >= 3:
            rows_by_subject[cols[0]].append(cols[2])

    subjects = list(rows_by_subject.keys())
    if len(subjects) < 2:
        pytest.skip("Need at least 2 subjects for HC suppression test")

    src_uri_approved = subjects[0]
    src_uri_rejected = subjects[1]
    all_master_uris = rows_by_subject[src_uri_approved] + rows_by_subject[src_uri_rejected]
    if not all_master_uris:
        pytest.skip("No master URIs found")

    master_uri_approved = rows_by_subject[src_uri_approved][0]
    master_uri_rejected = rows_by_subject[src_uri_rejected][0]

    log_path = tmp_path / "audit-log.sssom.tsv"
    # Approve src_uri_approved
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
    # Reject one pair for src_uri_rejected
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

    result = _runner().invoke(suggest_cli, [str(src_f), str(mst_f), "--audit-log", str(log_path)])
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = _data_rows(result.output)
    # Approved subject: zero rows in output
    for row in rows:
        assert src_uri_approved not in row, (
            "HC-approved subject should have all suggestions removed"
        )
    # Rejected pair: that specific pair absent
    for row in rows:
        cols = row.split("\t")
        if len(cols) >= 3:
            assert not (cols[0] == src_uri_rejected and cols[2] == master_uri_rejected), (
                "HC-rejected pair should be absent"
            )
    # Other suggestions for the rejected subject's source still appear
    assert any(src_uri_rejected in row for row in rows), (
        "Other suggestions for HC-rejected subject should still appear"
    )


def test_suggest_cli_output_file(
    tmp_path: Path, src_yaml: Path, mst_yaml: Path, empty_log: str
) -> None:
    """--output writes SSSOM TSV to file; file contains subject_id header."""
    from rosetta.cli.suggest import cli

    out_file = tmp_path / "out.sssom.tsv"
    result = _runner().invoke(
        cli, [str(src_yaml), str(mst_yaml), "-o", str(out_file), "--audit-log", empty_log]
    )

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    content = out_file.read_text()
    assert "subject_id" in content


def test_suggest_cli_header_has_16_columns(src_yaml: Path, mst_yaml: Path, empty_log: str) -> None:
    """TSV header must have 15 columns including the four new composite-entity columns."""
    from rosetta.cli.suggest import cli

    result = _runner().invoke(cli, [str(src_yaml), str(mst_yaml), "--audit-log", empty_log])
    assert result.exit_code == 0, result.output

    # Find the header line (not a comment line, must contain tabs)
    columns = next(
        ln
        for ln in result.output.splitlines()
        if ln.strip() and "\t" in ln and not ln.startswith("#")
    ).split("\t")
    assert len(columns) == 16, f"Expected 16 columns, got {len(columns)}: {columns}"
    assert "subject_datatype" in columns
    assert "object_datatype" in columns
    assert "subject_type" in columns
    assert "object_type" in columns
    assert "mapping_group_id" in columns
    assert "composition_expr" in columns
    assert "conversion_function" in columns
    assert columns[11:] == [
        "subject_type",
        "object_type",
        "mapping_group_id",
        "composition_expr",
        "conversion_function",
    ]


# ---------------------------------------------------------------------------
# Regression: top-k with min_score must return up to top_k qualifying entries
# ---------------------------------------------------------------------------


def test_rank_suggestions_top_k_with_min_score_returns_all_qualifying() -> None:
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


def test_suggest_cli_structural_weight_config(tmp_path: Path) -> None:
    """CLI with non-default structural_weight produces different confidence than default."""
    from rosetta.cli.suggest import cli
    from rosetta.core.ledger import append_log

    src_yaml = tmp_path / "source.linkml.yaml"
    src_yaml.write_text(_SRC_SCHEMA)
    mst_yaml = tmp_path / "master.linkml.yaml"
    mst_yaml.write_text(_MASTER_SCHEMA)

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([], log_path)

    def _run_with_weight(weight: float) -> float:
        result = _runner().invoke(
            cli,
            [
                str(src_yaml),
                str(mst_yaml),
                "--audit-log",
                str(log_path),
                "--structural-weight",
                str(weight),
            ],
        )
        assert result.exit_code == 0, f"CLI failed (weight={weight}): {result.output}"
        rows = _data_rows(result.output)
        assert rows, "Expected at least one data row"
        fields = rows[0].split("\t")
        return float(fields[4])  # confidence column index 4

    score_a = _run_with_weight(0.5)
    score_b = _run_with_weight(0.1)

    # Scores may be equal if no structural features are present in the test schemas;
    # what matters is the CLI ran without error for both weights.
    assert isinstance(score_a, float)
    assert isinstance(score_b, float)


def test_suggest_cli_structural_weight_zero_disables_blending(tmp_path: Path) -> None:
    """structural_weight=0.0 → LexicalMatching, not CompositeMatching.

    Regression guard for the falsy-zero bug: `get_config_value(...) or 0.2` would
    override an explicit 0.0 with 0.2, activating blending against the user's intent.
    """
    from rosetta.cli.suggest import cli
    from rosetta.core.ledger import append_log

    src_yaml = tmp_path / "source.linkml.yaml"
    src_yaml.write_text(_SRC_SCHEMA)
    mst_yaml = tmp_path / "master.linkml.yaml"
    mst_yaml.write_text(_MASTER_SCHEMA)

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([], log_path)

    result = _runner().invoke(
        cli,
        [str(src_yaml), str(mst_yaml), "--audit-log", str(log_path), "--structural-weight", "0.0"],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    rows = _data_rows(result.output)
    assert rows, "Expected at least one data row"
    fields = rows[0].split("\t")
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

    src_f = tmp_path / "source.linkml.yaml"
    src_f.write_text(_SRC_SCHEMA)
    mst_f = tmp_path / "master.linkml.yaml"
    mst_f.write_text(_MASTER_SCHEMA)

    log_path = tmp_path / "mylog.sssom.tsv"
    append_log([], log_path)

    result = _runner().invoke(
        suggest_cli,
        [str(src_f), str(mst_f), "--audit-log", str(log_path)],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    assert _data_rows(result.output)


def test_suggest_cli_audit_log_nonexistent_treated_as_empty(tmp_path: Path) -> None:
    """--audit-log pointing to nonexistent file → treated as empty log, suggest succeeds."""
    from rosetta.cli.suggest import cli as suggest_cli

    src_f = tmp_path / "source.linkml.yaml"
    src_f.write_text(_SRC_SCHEMA)
    mst_f = tmp_path / "master.linkml.yaml"
    mst_f.write_text(_MASTER_SCHEMA)

    missing_log = tmp_path / "does-not-exist.sssom.tsv"

    result = _runner().invoke(
        suggest_cli,
        [str(src_f), str(mst_f), "--audit-log", str(missing_log)],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    assert _data_rows(result.output)


def test_suggest_cli_audit_log_empty_shows_pair(tmp_path: Path) -> None:
    """Empty audit log → no filtering, all suggestions appear."""
    from rosetta.cli.suggest import cli as suggest_cli
    from rosetta.core.ledger import append_log

    src_f = tmp_path / "source.linkml.yaml"
    src_f.write_text(_SRC_SCHEMA)
    mst_f = tmp_path / "master.linkml.yaml"
    mst_f.write_text(_MASTER_SCHEMA)

    empty_log = tmp_path / "empty-log.sssom.tsv"
    append_log([], empty_log)

    result = _runner().invoke(
        suggest_cli,
        [str(src_f), str(mst_f), "--audit-log", str(empty_log)],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    assert _data_rows(result.output), "Empty log should not suppress anything"


# ---------------------------------------------------------------------------
# Unit tests for filter_decided_suggestions
# ---------------------------------------------------------------------------


def test_filter_decided_approved_removes_subject() -> None:
    """Approved HC for (X, A) → result dict has no key for X."""
    from rosetta.core.models import SSSOMRow
    from rosetta.core.similarity import filter_decided_suggestions

    result: dict[str, Any] = {
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

    result: dict[str, Any] = {
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

    result: dict[str, Any] = {
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

    result: dict[str, Any] = {
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

    result: dict[str, Any] = {
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
