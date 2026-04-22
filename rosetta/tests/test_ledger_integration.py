"""End-to-end integration tests for the audit-log accreditation pipeline."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.suggest import cli as suggest_cli
from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
from rosetta.core.models import SSSOMRow

pytestmark = [pytest.mark.integration]

# ---------------------------------------------------------------------------
# Constants for integration tests
# ---------------------------------------------------------------------------

SRC_URI = "http://example.org/NOR#altitude"
TGT_URI = "http://nato.int/master#Altitude"
OTHER_TGT = "http://nato.int/master#Elevation"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embed_json(tmp_path: Path, filename: str, entries: dict[str, dict[str, object]]) -> Path:
    """Write an embed JSON file. Each entry has 'lexical' (list[float]) and optionally 'label'."""
    path = tmp_path / filename
    path.write_text(json.dumps(entries))
    return path


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


def _make_embed_fixtures(
    tmp_path: Path,
) -> tuple[Path, Path]:
    """Build non-collinear embed fixtures: src altitude ~= master Altitude."""
    sin_val = math.sqrt(1.0 - 0.81)
    src_emb = {
        SRC_URI: {"label": "Altitude", "lexical": [0.9, 0.0, sin_val]},
        "http://example.org/NOR#speed": {"label": "Speed", "lexical": [0.0, 1.0, 0.0]},
    }
    master_emb = {
        TGT_URI: {"label": "Altitude", "lexical": [1.0, 0.0, 0.0]},
        OTHER_TGT: {"label": "Elevation", "lexical": [0.0, 1.0, 0.0]},
    }
    src_file = _make_embed_json(tmp_path, "src.json", src_emb)  # pyright: ignore[reportArgumentType]
    master_file = _make_embed_json(tmp_path, "master.json", master_emb)  # pyright: ignore[reportArgumentType]
    return src_file, master_file


def test_full_flow_approve_suppresses_future_suggestion(tmp_path: Path) -> None:
    """MMC → HC approve → suggest omits ALL rows for that subject from output."""
    src_file, master_file = _make_embed_fixtures(tmp_path)
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


def test_full_flow_reject_filters_pair(tmp_path: Path) -> None:
    """Rejected pair is completely absent from suggest output."""
    src_file, master_file = _make_embed_fixtures(tmp_path)
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


def test_full_flow_correction_overrides_previous_decision(tmp_path: Path) -> None:
    """MMC → HC approve → HC correction (reject) → subject fully absent (approved wins)."""
    src_file, master_file = _make_embed_fixtures(tmp_path)
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


def test_suggest_existing_pair_merge_preserves_justification(tmp_path: Path) -> None:
    """MMC row in log → suggest output has ManualMappingCuration for that pair."""
    src_file, master_file = _make_embed_fixtures(tmp_path)
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
