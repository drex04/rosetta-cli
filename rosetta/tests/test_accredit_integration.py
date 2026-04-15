"""End-to-end integration tests for the audit-log accreditation pipeline."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.suggest import cli as suggest_cli
from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
from rosetta.core.models import SSSOMRow

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
# Unit-level integration: apply_sssom_feedback
# ---------------------------------------------------------------------------


def make_candidates() -> list[dict[str, object]]:
    return [
        {"uri": TGT_URI, "score": 0.75, "label": "Altitude"},
        {"uri": OTHER_TGT, "score": 0.60, "label": "Elevation"},
    ]


def make_approved_rows(predicate: str = "skos:relatedMatch") -> list[SSSOMRow]:
    return [
        SSSOMRow(
            subject_id=SRC_URI,
            predicate_id=predicate,
            object_id=TGT_URI,
            mapping_justification="semapv:LexicalMatching",
            confidence=0.8,
        )
    ]


def test_approve_boost() -> None:
    """Accredited mapping raises score of matching candidate."""
    from rosetta.core.similarity import apply_sssom_feedback

    approved_rows = make_approved_rows("skos:relatedMatch")
    candidates = make_candidates()
    result = apply_sssom_feedback(SRC_URI, candidates, approved_rows, boost=0.1)

    tgt = next(c for c in result if c["uri"] == TGT_URI)
    old_score = 0.75
    assert tgt["score"] == pytest.approx(old_score + 0.1, abs=0.001)
    assert tgt["score"] <= 1.0


def test_derank_revoked() -> None:
    """owl:differentFrom row decreases score but candidate is NOT removed."""
    from rosetta.core.similarity import apply_sssom_feedback

    approved_rows = make_approved_rows("owl:differentFrom")
    candidates = make_candidates()
    result = apply_sssom_feedback(SRC_URI, candidates, approved_rows, penalty=0.2)

    uris = [c["uri"] for c in result]
    assert TGT_URI in uris
    assert OTHER_TGT in uris

    tgt = next(c for c in result if c["uri"] == TGT_URI)
    assert tgt["score"] < 0.75


def test_no_approved_rows_match_passthrough() -> None:
    """Candidates with no matching approved rows are unchanged."""
    from rosetta.core.similarity import apply_sssom_feedback

    approved_rows: list[SSSOMRow] = []
    result = apply_sssom_feedback(SRC_URI, make_candidates(), approved_rows)
    original = make_candidates()
    assert len(result) == len(original)
    for res, orig in zip(result, original):
        assert res["uri"] == orig["uri"]
        assert res["score"] == pytest.approx(float(orig["score"]))  # pyright: ignore[reportArgumentType]


def test_boost_cap_at_1() -> None:
    """Score boosted beyond 1.0 is capped at 1.0."""
    from rosetta.core.similarity import apply_sssom_feedback

    approved_rows = make_approved_rows("skos:relatedMatch")
    high_score_candidates: list[dict[str, object]] = [
        {"uri": TGT_URI, "score": 0.95, "label": "Altitude"}
    ]
    result = apply_sssom_feedback(SRC_URI, high_score_candidates, approved_rows, boost=0.1)
    assert result[0]["score"] == pytest.approx(1.0)


def test_empty_candidates() -> None:
    """Empty candidate list returns empty list regardless of approved rows."""
    from rosetta.core.similarity import apply_sssom_feedback

    approved_rows = make_approved_rows("skos:relatedMatch")
    result = apply_sssom_feedback(SRC_URI, [], approved_rows)
    assert result == []


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


def test_full_flow_approve_boosts_future_suggestion(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """MMC → HC approve → suggest shows boosted confidence for that pair."""
    src_file, master_file = _make_embed_fixtures(tmp_path)
    log_path = tmp_path / "audit-log.sssom.tsv"

    # Baseline suggest (no log)
    runner = CliRunner()
    baseline = runner.invoke(suggest_cli, [str(src_file), str(master_file)])
    assert baseline.exit_code == 0, baseline.output
    baseline_rows = _parse_suggest_output(baseline.output)
    baseline_tgt = next((r for r in baseline_rows if TGT_URI in r.get("object_id", "")), None)
    assert baseline_tgt is not None
    baseline_score = float(baseline_tgt["confidence"])

    # Ingest MMC then HC approval
    append_log([_row(SRC_URI, TGT_URI, MMC_JUSTIFICATION)], log_path)
    append_log([_row(SRC_URI, TGT_URI, HC_JUSTIFICATION, predicate="skos:exactMatch")], log_path)

    # Suggest with config pointing to audit log
    result = runner.invoke(
        suggest_cli, [str(src_file), str(master_file), "--config", str(tmp_rosetta_toml)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    boosted_rows = _parse_suggest_output(result.output)
    boosted_tgt = next((r for r in boosted_rows if TGT_URI in r.get("object_id", "")), None)
    assert boosted_tgt is not None
    boosted_score = float(boosted_tgt["confidence"])
    assert boosted_score > baseline_score, (
        f"Expected boosted ({boosted_score}) > baseline ({baseline_score})"
    )


def test_full_flow_reject_deranks_future_suggestion(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """MMC → HC reject (owl:differentFrom) → suggest shows deranked confidence."""
    src_file, master_file = _make_embed_fixtures(tmp_path)
    log_path = tmp_path / "audit-log.sssom.tsv"

    # Baseline
    runner = CliRunner()
    baseline = runner.invoke(suggest_cli, [str(src_file), str(master_file)])
    assert baseline.exit_code == 0, baseline.output
    baseline_rows = _parse_suggest_output(baseline.output)
    baseline_tgt = next((r for r in baseline_rows if TGT_URI in r.get("object_id", "")), None)
    assert baseline_tgt is not None
    baseline_score = float(baseline_tgt["confidence"])

    # Ingest MMC then HC rejection
    append_log([_row(SRC_URI, TGT_URI, MMC_JUSTIFICATION)], log_path)
    append_log([_row(SRC_URI, TGT_URI, HC_JUSTIFICATION, predicate="owl:differentFrom")], log_path)

    result = runner.invoke(
        suggest_cli, [str(src_file), str(master_file), "--config", str(tmp_rosetta_toml)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    deranked_rows = _parse_suggest_output(result.output)
    deranked_tgt = next((r for r in deranked_rows if TGT_URI in r.get("object_id", "")), None)
    assert deranked_tgt is not None
    deranked_score = float(deranked_tgt["confidence"])
    assert deranked_score < baseline_score, (
        f"Expected deranked ({deranked_score}) < baseline ({baseline_score})"
    )


def test_full_flow_correction_overrides_previous_decision(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    """MMC → HC approve → HC correction (reject) → suggest shows deranked."""
    src_file, master_file = _make_embed_fixtures(tmp_path)
    log_path = tmp_path / "audit-log.sssom.tsv"

    # Baseline
    runner = CliRunner()
    baseline = runner.invoke(suggest_cli, [str(src_file), str(master_file)])
    assert baseline.exit_code == 0
    baseline_rows = _parse_suggest_output(baseline.output)
    baseline_tgt = next((r for r in baseline_rows if TGT_URI in r.get("object_id", "")), None)
    assert baseline_tgt is not None
    baseline_score = float(baseline_tgt["confidence"])

    # MMC → approve → reject correction
    append_log([_row(SRC_URI, TGT_URI, MMC_JUSTIFICATION)], log_path)
    append_log([_row(SRC_URI, TGT_URI, HC_JUSTIFICATION, predicate="skos:exactMatch")], log_path)
    append_log([_row(SRC_URI, TGT_URI, HC_JUSTIFICATION, predicate="owl:differentFrom")], log_path)

    result = runner.invoke(
        suggest_cli, [str(src_file), str(master_file), "--config", str(tmp_rosetta_toml)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    corrected_rows = _parse_suggest_output(result.output)
    corrected_tgt = next((r for r in corrected_rows if TGT_URI in r.get("object_id", "")), None)
    assert corrected_tgt is not None
    corrected_score = float(corrected_tgt["confidence"])
    assert corrected_score < baseline_score, (
        f"Expected corrected ({corrected_score}) < baseline ({baseline_score})"
    )


def test_suggest_existing_pair_merge_preserves_justification(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    """MMC row in log → suggest output has ManualMappingCuration for that pair."""
    src_file, master_file = _make_embed_fixtures(tmp_path)
    log_path = tmp_path / "audit-log.sssom.tsv"

    # Ingest MMC only (no HC)
    append_log([_row(SRC_URI, TGT_URI, MMC_JUSTIFICATION)], log_path)

    runner = CliRunner()
    result = runner.invoke(
        suggest_cli, [str(src_file), str(master_file), "--config", str(tmp_rosetta_toml)]
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = _parse_suggest_output(result.output)
    pair_row = next((r for r in rows if TGT_URI in r.get("object_id", "")), None)
    assert pair_row is not None
    assert pair_row.get("mapping_justification") == MMC_JUSTIFICATION
