"""End-to-end integration tests for the audit-log accreditation pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import sentence_transformers
from click.testing import CliRunner

from rosetta.cli.suggest import cli as suggest_cli
from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
from rosetta.core.models import SSSOMRow

pytestmark = [pytest.mark.integration]

# ---------------------------------------------------------------------------
# Constants for integration tests
# URIs now use the CURIE format that suggest emits: {schema_name}:{slot_name}
# ---------------------------------------------------------------------------

SRC_URI = "NOR:altitude"
TGT_URI = "master_cop:Altitude"
OTHER_TGT = "master_cop:Elevation"


# ---------------------------------------------------------------------------
# Fake embedding model
# ---------------------------------------------------------------------------


class _FakeLaBSE:
    """Deterministic fake sentence-transformer that returns non-collinear vectors.

    Vectors are keyed off the slot label so that 'altitude' is close to
    'Altitude' and 'speed' is close to 'Elevation' (orthogonal bucket).
    """

    _VECTORS: dict[str, list[float]] = {
        # src slots
        "altitude": [0.9, 0.0, 0.436],
        "speed": [0.0, 1.0, 0.0],
        # master slots
        "Altitude": [1.0, 0.0, 0.0],
        "Elevation": [0.0, 1.0, 0.0],
    }

    def encode(self, texts: list[str]) -> np.ndarray:
        rows: list[list[float]] = []
        for text in texts:
            # Match on the last word (slot label portion of text)
            label = text.split()[-1] if text else text
            vec = self._VECTORS.get(label, [0.5, 0.5, 0.0])
            rows.append(vec)
        return np.array(rows, dtype=np.float32)


def _row(
    subject_id: str,
    object_id: str,
    justification: str,
    predicate: str = "skos:exactMatch",
    confidence: float = 0.9,
) -> SSSOMRow:
    return SSSOMRow(
        subject_id=subject_id,
        object_id=object_id,
        predicate_id=predicate,
        mapping_justification=justification,
        confidence=confidence,
    )


def _parse_suggest_output(output: str) -> list[dict[str, str]]:
    """Parse SSSOM TSV output from suggest CLI into list of dicts."""
    rows: list[dict[str, str]] = []
    cols: list[str] = []
    for line in output.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if parts[0] == "subject_id":
            cols = parts
            continue
        if cols:
            rows.append(dict(zip(cols, parts)))
    return rows


# ---------------------------------------------------------------------------
# Full E2E: accredit ingest → suggest
# ---------------------------------------------------------------------------

_SRC_SCHEMA_YAML = """\
id: https://example.org/NOR
name: NOR
prefixes:
  NOR: https://example.org/NOR/
default_prefix: NOR
slots:
  altitude:
    description: altitude
    range: float
  speed:
    description: speed
    range: float
"""

_MASTER_SCHEMA_YAML = """\
id: https://nato.int/master_cop
name: master_cop
prefixes:
  master_cop: https://nato.int/master_cop/
default_prefix: master_cop
slots:
  Altitude:
    description: Altitude
    range: float
  Elevation:
    description: Elevation
    range: float
"""


def _make_schema_fixtures(tmp_path: Path) -> tuple[Path, Path]:
    """Write minimal LinkML YAML fixtures for suggest."""
    src_path = tmp_path / "src_schema.yaml"
    master_path = tmp_path / "master_schema.yaml"
    src_path.write_text(_SRC_SCHEMA_YAML)
    master_path.write_text(_MASTER_SCHEMA_YAML)
    return src_path, master_path


def test_full_flow_approve_suppresses_future_suggestion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MMC → HC approve → suggest omits ALL rows for that subject from output."""
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda _: _FakeLaBSE())
    src_file, master_file = _make_schema_fixtures(tmp_path)
    log_path = tmp_path / "audit-log.sssom.tsv"

    # Ingest MMC then HC approval
    append_log([_row(SRC_URI, TGT_URI, MMC_JUSTIFICATION)], log_path)
    append_log([_row(SRC_URI, TGT_URI, HC_JUSTIFICATION, predicate="skos:exactMatch")], log_path)

    # Suggest with explicit audit-log path
    result = CliRunner().invoke(
        suggest_cli, [str(src_file), str(master_file), "--audit-log", str(log_path)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = _parse_suggest_output(result.output)
    # Subject-level suppression: no rows at all for the approved subject
    src_rows = [r for r in rows if r.get("subject_id") == SRC_URI]
    assert not src_rows, (
        "Approved HC subject should have all suggestions removed from suggest output"
    )


def test_full_flow_reject_filters_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rejected pair is completely absent from suggest output."""
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda _: _FakeLaBSE())
    src_file, master_file = _make_schema_fixtures(tmp_path)
    log_path = tmp_path / "audit-log.sssom.tsv"

    # Ingest MMC then HC rejection
    append_log([_row(SRC_URI, TGT_URI, MMC_JUSTIFICATION)], log_path)
    append_log([_row(SRC_URI, TGT_URI, HC_JUSTIFICATION, predicate="owl:differentFrom")], log_path)

    result = CliRunner().invoke(
        suggest_cli, [str(src_file), str(master_file), "--audit-log", str(log_path)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = _parse_suggest_output(result.output)
    rejected_pair = next(
        (r for r in rows if r.get("subject_id") == SRC_URI and TGT_URI in r.get("object_id", "")),
        None,
    )
    assert rejected_pair is None, "HC-rejected pair should be completely absent from suggest output"
    # Other suggestions for the subject should still appear
    other_rows = [r for r in rows if r.get("subject_id") == SRC_URI]
    assert other_rows, "Other suggestions for the rejected subject should still appear"


def test_full_flow_correction_overrides_previous_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MMC → HC approve → HC correction (reject) → subject fully absent (approved wins)."""
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda _: _FakeLaBSE())
    src_file, master_file = _make_schema_fixtures(tmp_path)
    log_path = tmp_path / "audit-log.sssom.tsv"

    # MMC → approve → reject correction
    # filter_decided_suggestions sees both HC rows; approved wins over rejected
    append_log([_row(SRC_URI, TGT_URI, MMC_JUSTIFICATION)], log_path)
    append_log([_row(SRC_URI, TGT_URI, HC_JUSTIFICATION, predicate="skos:exactMatch")], log_path)
    append_log([_row(SRC_URI, TGT_URI, HC_JUSTIFICATION, predicate="owl:differentFrom")], log_path)

    result = CliRunner().invoke(
        suggest_cli, [str(src_file), str(master_file), "--audit-log", str(log_path)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    corrected_rows = _parse_suggest_output(result.output)
    # Approved (non-differentFrom) HC exists in log → subject fully removed
    src_rows = [r for r in corrected_rows if r.get("subject_id") == SRC_URI]
    assert not src_rows, (
        "When both approved and rejected HC exist for same subject, approved wins: subject absent"
    )


def test_suggest_existing_pair_merge_preserves_justification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MMC row in log → suggest output has ManualMappingCuration for that pair."""
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda _: _FakeLaBSE())
    src_file, master_file = _make_schema_fixtures(tmp_path)
    log_path = tmp_path / "audit-log.sssom.tsv"

    # Ingest MMC only (no HC)
    append_log([_row(SRC_URI, TGT_URI, MMC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(
        suggest_cli, [str(src_file), str(master_file), "--audit-log", str(log_path)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = _parse_suggest_output(result.output)
    pair_row = next((r for r in rows if TGT_URI in r.get("object_id", "")), None)
    assert pair_row is not None
    assert pair_row.get("mapping_justification") == MMC_JUSTIFICATION
