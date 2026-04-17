"""Tests for rosetta/core/units.py and rosetta/cli/lint.py."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.lint import cli
from rosetta.core.units import (
    dimension_vector,
    load_qudt_graph,
    suggest_fnml,
    units_compatible,
)

# ---------------------------------------------------------------------------
# Module-level fixture — load QUDT graph once for all unit tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qudt_graph():
    return load_qudt_graph()


# ---------------------------------------------------------------------------
# Section 1 — units.py unit tests
# ---------------------------------------------------------------------------


def test_load_qudt_graph_parses(qudt_graph):
    assert len(list(qudt_graph)) > 10


def test_dimension_vector_metre(qudt_graph):
    assert dimension_vector("unit:M", qudt_graph) == "A0E0L1I0M0H0T0D0"


def test_dimension_vector_kilogram(qudt_graph):
    assert dimension_vector("unit:KiloGM", qudt_graph) == "A0E0L0I0M1H0T0D0"


def test_dimension_vector_unknown(qudt_graph):
    assert dimension_vector("unit:FOOBAR", qudt_graph) is None


def test_units_compatible_same_unit(qudt_graph):
    assert units_compatible("unit:M", "unit:M", qudt_graph) is True


def test_units_compatible_same_dimension(qudt_graph):
    assert units_compatible("unit:FT", "unit:M", qudt_graph) is True


def test_units_compatible_different_dimension(qudt_graph):
    assert units_compatible("unit:FT", "unit:KiloGM", qudt_graph) is False


def test_units_compatible_unknown_unit(qudt_graph):
    assert units_compatible(None, "unit:M", qudt_graph) is None  # pyright: ignore[reportArgumentType]


def test_units_compatible_missing_vector(qudt_graph):
    assert units_compatible("unit:FOOBAR", "unit:BAZQUX", qudt_graph) is None


def test_dimension_vector_full_iri(qudt_graph):
    assert dimension_vector("http://qudt.org/vocab/unit/M", qudt_graph) == "A0E0L1I0M0H0T0D0"


def test_suggest_fnml_known_pair(qudt_graph):
    result = suggest_fnml("unit:FT", "unit:M", qudt_graph)
    assert result is not None
    assert "fnml_function" in result
    assert "multiplier" in result
    assert abs(result["multiplier"] - 0.3048) < 1e-6  # pyright: ignore[reportOperatorIssue]


def test_suggest_fnml_offset_pair(qudt_graph):
    result = suggest_fnml("unit:degC", "unit:K", qudt_graph)
    assert result is not None
    assert result["offset"] == pytest.approx(273.15)


def test_suggest_fnml_unknown_pair(qudt_graph):
    assert suggest_fnml("unit:FOOBAR", "unit:BAZQUX", qudt_graph) is None


# ---------------------------------------------------------------------------
# SSSOM proposals lint tests
# ---------------------------------------------------------------------------

_MMC = "semapv:ManualMappingCuration"
_HC = "semapv:HumanCuration"
_SSSOM_HEADER = "# sssom_version: https://w3id.org/sssom/spec/0.15\n# mapping_set_id: test\n"
_SSSOM_COLS = [
    "subject_id",
    "predicate_id",
    "object_id",
    "mapping_justification",
    "confidence",
    "subject_label",
    "object_label",
    "mapping_date",
    "record_id",
]


def _write_sssom(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w") as f:
        f.write(_SSSOM_HEADER)
        writer = csv.DictWriter(f, fieldnames=_SSSOM_COLS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in _SSSOM_COLS})


def _no_accredit_toml(tmp_path: Path) -> Path:
    config = tmp_path / "rosetta.toml"
    config.write_text("[suggest]\ntop_k = 5\n")
    return config


def test_lint_sssom_passes_clean_file(tmp_path: Path) -> None:
    sssom = tmp_path / "clean.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0, result.output


def test_lint_sssom_max_one_mmc_per_pair_fails(tmp_path: Path) -> None:
    sssom = tmp_path / "dup.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
            {
                "subject_id": "a",
                "predicate_id": "skos:relatedMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.8",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 1


def test_lint_sssom_no_reproposal_of_approved_fails(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id="a",
                object_id="b",
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
                subject_id="a",
                object_id="b",
                predicate_id="skos:exactMatch",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )

    sssom = tmp_path / "reproposal.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(tmp_rosetta_toml)])
    assert result.exit_code == 1


def test_lint_sssom_no_reproposal_of_rejected_fails(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id="c",
                object_id="d",
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
                subject_id="c",
                object_id="d",
                predicate_id="owl:differentFrom",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.0,
            )
        ],
        log_path,
    )

    sssom = tmp_path / "reproposal_rejected.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "c",
                "predicate_id": "skos:exactMatch",
                "object_id": "d",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(tmp_rosetta_toml)])
    assert result.exit_code == 1


def test_lint_sssom_invalid_predicate_fails(tmp_path: Path) -> None:
    sssom = tmp_path / "bad_pred.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "bad:predicate",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 1


def test_lint_sssom_no_log_configured_skips_reproposal_check(tmp_path: Path) -> None:
    """Config without [accredit] section → reproposal check skipped."""
    sssom = tmp_path / "no_log.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# New unit/datatype SSSOM tests
# ---------------------------------------------------------------------------

# Extended SSSOM columns including datatype columns
_SSSOM_COLS_EXTENDED = _SSSOM_COLS + ["subject_datatype", "object_datatype"]


def _write_sssom_extended(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a SSSOM TSV including subject_datatype and object_datatype columns."""
    with path.open("w") as f:
        f.write(_SSSOM_HEADER)
        writer = csv.DictWriter(
            f, fieldnames=_SSSOM_COLS_EXTENDED, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in _SSSOM_COLS_EXTENDED})


def test_lint_sssom_unit_dimension_mismatch(tmp_path: Path) -> None:
    """subject altitude_m (meters) vs object speed_kts (knots) → unit_dimension_mismatch BLOCK."""
    sssom = tmp_path / "dim_mismatch.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:altitude_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:speed_kts",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert any(f["rule"] == "unit_dimension_mismatch" for f in data["findings"])
    mismatch = next(f for f in data["findings"] if f["rule"] == "unit_dimension_mismatch")
    assert mismatch["severity"] == "BLOCK"


def test_lint_sssom_unit_conversion_required(tmp_path: Path) -> None:
    """altitude_ft vs altitude_m → unit_conversion_required WARNING, fnml_suggestion not None."""
    sssom = tmp_path / "conv_required.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:altitude_ft",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:altitude_m",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    warnings = [f for f in data["findings"] if f["rule"] == "unit_conversion_required"]
    assert warnings, "Expected unit_conversion_required finding"
    assert warnings[0]["severity"] == "WARNING"
    assert warnings[0]["fnml_suggestion"] is not None


def test_lint_sssom_unit_not_detected(tmp_path: Path) -> None:
    """subject 'callsign' (no unit) → unit_not_detected INFO."""
    sssom = tmp_path / "no_unit.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:callsign",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:callsign_label",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["rule"] == "unit_not_detected"]
    assert infos, "Expected unit_not_detected finding for callsign"
    assert infos[0]["severity"] == "INFO"


def test_lint_sssom_unit_no_iri_mapping(tmp_path: Path) -> None:
    """subject 'signal_dbm' and object 'rx_dbm' → unit_not_detected INFO.

    dBm has no QUDT IRI, so detect_unit returns None directly — the dBm path
    now collapses to the single unit_not_detected finding (no separate
    "no QUDT IRI mapping" step).
    """
    sssom = tmp_path / "dbm.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:signal_dbm",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:rx_dbm",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["rule"] == "unit_not_detected"]
    assert infos, "Expected unit_not_detected finding for dBm"
    assert infos[0]["severity"] == "INFO"
    assert "No detectable unit" in infos[0]["message"]


def test_lint_sssom_datatype_mismatch(tmp_path: Path) -> None:
    """subject_datatype='integer' vs object_datatype='string' → datatype_mismatch WARNING."""
    sssom = tmp_path / "dtype_mismatch.sssom.tsv"
    _write_sssom_extended(
        sssom,
        [
            {
                "subject_id": "ex:callsign",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:callsign_label",
                "mapping_justification": _MMC,
                "confidence": "0.9",
                "subject_datatype": "integer",
                "object_datatype": "string",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    data = json.loads(result.output)
    dt_findings = [f for f in data["findings"] if f["rule"] == "datatype_mismatch"]
    assert dt_findings, "Expected datatype_mismatch finding"
    assert dt_findings[0]["severity"] == "WARNING"


def test_lint_sssom_datatype_both_numeric_no_finding(tmp_path: Path) -> None:
    """subject_datatype='integer' vs object_datatype='float' → no datatype_mismatch."""
    sssom = tmp_path / "both_numeric.sssom.tsv"
    _write_sssom_extended(
        sssom,
        [
            {
                "subject_id": "ex:callsign",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:callsign_label",
                "mapping_justification": _MMC,
                "confidence": "0.9",
                "subject_datatype": "integer",
                "object_datatype": "float",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    dt_findings = [f for f in data["findings"] if f["rule"] == "datatype_mismatch"]
    assert not dt_findings, "Expected no datatype_mismatch for integer vs float"


def test_lint_sssom_datatype_missing_skipped(tmp_path: Path) -> None:
    """Rows without subject_datatype/object_datatype → no datatype finding emitted."""
    sssom = tmp_path / "no_dtype.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:callsign",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:callsign_label",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    dt_findings = [f for f in data["findings"] if f["rule"] == "datatype_mismatch"]
    assert not dt_findings, "Expected no datatype_mismatch when columns absent"


def test_lint_sssom_json_report_structure(tmp_path: Path) -> None:
    """SSSOM-only run with no issues → exit 0, valid JSON with findings list and summary."""
    sssom = tmp_path / "clean2.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:callsign",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:callsign_label",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "findings" in data
    assert isinstance(data["findings"], list)
    assert "summary" in data
    assert "block" in data["summary"]
    assert "warning" in data["summary"]
    assert "info" in data["summary"]


def test_lint_sssom_strict_warning_becomes_block(tmp_path: Path) -> None:
    """unit_conversion_required WARNING → BLOCK with --strict."""
    sssom = tmp_path / "strict_conv.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:altitude_ft",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:altitude_m",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config), "--strict"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    blocks = [f for f in data["findings"] if f["severity"] == "BLOCK"]
    assert any(f["rule"] == "unit_conversion_required" for f in blocks)


def test_lint_sssom_strict_info_stays_info(tmp_path: Path) -> None:
    """--strict only upgrades WARNINGs; INFO findings stay INFO."""
    sssom = tmp_path / "strict_info.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:callsign",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:callsign_label",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config), "--strict"])
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["severity"] == "INFO"]
    # unit_not_detected should remain INFO even with --strict
    assert any(f["rule"] == "unit_not_detected" for f in infos)


def test_lint_sssom_unit_vector_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both units have QUDT IRIs but dimension vector missing → unit_vector_missing INFO."""
    import rosetta.cli.lint as lint_mod

    monkeypatch.setattr(lint_mod, "units_compatible", lambda *_: None)
    sssom = tmp_path / "vec_missing.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:altitude_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:altitude_ft",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["rule"] == "unit_vector_missing"]
    assert infos, "Expected unit_vector_missing INFO finding"
    assert infos[0]["severity"] == "INFO"


def test_lint_sssom_proposals_json_finding(tmp_path: Path) -> None:
    """check_sssom_proposals findings appear in JSON report with correct rule/severity."""
    sssom = tmp_path / "dup2.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:callsign",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:callsign_label",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
            {
                "subject_id": "ex:callsign",
                "predicate_id": "skos:relatedMatch",
                "object_id": "ex:callsign_label",
                "mapping_justification": _MMC,
                "confidence": "0.8",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 1
    data = json.loads(result.output)
    proposal_findings = [f for f in data["findings"] if f["rule"] == "max_one_mmc_per_pair"]
    assert proposal_findings, "Expected max_one_mmc_per_pair finding in JSON"
    assert proposal_findings[0]["severity"] == "BLOCK"
