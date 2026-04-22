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


_MINIMAL_SOURCE_SCHEMA_YAML = """\
name: source
id: https://example.org/source
imports:
- linkml:types
prefixes:
  linkml:
    prefix_prefix: linkml
    prefix_reference: https://w3id.org/linkml/
default_range: string
classes:
  Thing:
    name: Thing
"""

_MINIMAL_MASTER_SCHEMA_YAML = """\
name: master
id: https://example.org/master
imports:
- linkml:types
prefixes:
  linkml:
    prefix_prefix: linkml
    prefix_reference: https://w3id.org/linkml/
default_range: string
classes:
  Thing:
    name: Thing
"""


def _write_minimal_schemas(tmp_path: Path) -> tuple[Path, Path]:
    """Write minimal source and master schema YAML files. Returns (source, master)."""
    src = tmp_path / "source.yaml"
    src.write_text(_MINIMAL_SOURCE_SCHEMA_YAML)
    mst = tmp_path / "master.yaml"
    mst.write_text(_MINIMAL_MASTER_SCHEMA_YAML)
    return src, mst


def _write_empty_audit_log(tmp_path: Path) -> Path:
    """Write an empty (header-only) audit log. Returns its path."""
    from rosetta.core.ledger import AUDIT_LOG_COLUMNS, SSSOM_HEADER

    log = tmp_path / "audit-log.sssom.tsv"
    import csv

    with log.open("w") as f:
        f.write(SSSOM_HEADER)
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(AUDIT_LOG_COLUMNS)
    return log


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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 1


def test_lint_sssom_max_one_mmc_per_subject_fails(tmp_path: Path) -> None:
    """Same subject confirmed-mapped to two different objects → BLOCK."""
    sssom = tmp_path / "dup_subject.sssom.tsv"
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
                "predicate_id": "skos:exactMatch",
                "object_id": "c",
                "mapping_justification": _MMC,
                "confidence": "0.8",
            },
        ],
    )
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 1
    data = json.loads(result.output)
    subject_findings = [f for f in data["findings"] if f["rule"] == "max_one_mmc_per_subject"]
    assert len(subject_findings) == 1
    assert "a" in subject_findings[0]["message"]
    assert "b" in subject_findings[0]["message"]
    assert "c" in subject_findings[0]["message"]


def test_lint_sssom_no_reproposal_of_approved_fails(tmp_path: Path) -> None:
    from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
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
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(log_path),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 1


def test_lint_sssom_no_reproposal_of_rejected_fails(tmp_path: Path) -> None:
    from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
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
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(log_path),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 1


def test_lint_sssom_empty_audit_log_skips_reproposal_check(tmp_path: Path) -> None:
    """Empty audit log (no HC entries) → reproposal check finds nothing, exits 0."""
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["rule"] == "unit_not_detected"]
    assert infos, "Expected unit_not_detected finding for dBm"
    assert infos[0]["severity"] == "INFO"
    # dBm: recognized unit with no QUDT IRI → distinct message from 'no unit found'
    assert "no QUDT IRI mapping" in infos[0]["message"]


def test_lint_sssom_unit_detected_from_prose_label(tmp_path: Path) -> None:
    """Description-arg threading: subject_label carries prose like 'Altitude in metres'
    so detect_unit's _DESC_PATTERNS layer fires on the human label, not the field id.
    Confirms _check_units wires label → description correctly.
    """
    sssom = tmp_path / "prose.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:value_a",
                "subject_label": "Altitude in metres",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:value_b",
                "object_label": "Ceiling in feet",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    # Prose labels drive detection: metre + foot share dimension → WARNING
    warnings = [f for f in data["findings"] if f["rule"] == "unit_conversion_required"]
    assert warnings, "Expected unit_conversion_required finding driven by prose labels"
    assert "M vs FT" in warnings[0]["message"]


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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
            "--strict",
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
            "--strict",
        ],
    )
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["severity"] == "INFO"]
    # unit_not_detected should remain INFO even with --strict
    assert any(f["rule"] == "unit_not_detected" for f in infos)


def test_lint_sssom_unit_vector_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both units have QUDT IRIs but dimension vector missing → unit_vector_missing INFO."""
    import rosetta.core.lint as lint_mod

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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 1
    data = json.loads(result.output)
    proposal_findings = [f for f in data["findings"] if f["rule"] == "max_one_mmc_per_pair"]
    assert proposal_findings, "Expected max_one_mmc_per_pair finding in JSON"
    assert proposal_findings[0]["severity"] == "BLOCK"


def test_lint_sssom_skips_composite_matching_rows(tmp_path: Path) -> None:
    """CompositeMatching rows are system-generated suggestions — lint skips them entirely."""
    sssom = tmp_path / "composite.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:altitude_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:speed_kts",
                "mapping_justification": "semapv:CompositeMatching",
                "confidence": "0.8",
            },
        ],
    )
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["findings"] == []


def test_lint_sssom_mixed_composite_and_mmc_only_lints_mmc(tmp_path: Path) -> None:
    """File with both CompositeMatching and MMC rows — only the MMC row produces findings."""
    sssom = tmp_path / "mixed.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:altitude_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:speed_kts",
                "mapping_justification": "semapv:CompositeMatching",
                "confidence": "0.8",
            },
            {
                "subject_id": "ex:altitude_ft",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:altitude_m",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    data = json.loads(result.output)
    assert all(
        f["source_uri"] != "ex:altitude_m" or f["target_uri"] != "ex:speed_kts"
        for f in data["findings"]
    ), "CompositeMatching row should not produce findings"
    assert any(f["source_uri"] == "ex:altitude_ft" for f in data["findings"]), (
        "MMC row should still be linted"
    )


# ---------------------------------------------------------------------------
# Structural reachability check (--source-schema + --master-schema)
# ---------------------------------------------------------------------------

_MASTER_SCHEMA_YAML = """\
name: master
id: https://example.org/master
imports:
- linkml:types
prefixes:
  linkml:
    prefix_prefix: linkml
    prefix_reference: https://w3id.org/linkml/
default_range: string
slots:
  hasLongitude:
    name: hasLongitude
    range: double
  hasTrackNumber:
    name: hasTrackNumber
    range: string
classes:
  Entity:
    name: Entity
    slots:
    - hasLongitude
  Track:
    name: Track
    is_a: Entity
    slots:
    - hasTrackNumber
  SensorReport:
    name: SensorReport
"""

_SOURCE_SCHEMA_YAML = """\
name: source
id: https://example.org/source
imports:
- linkml:types
prefixes:
  linkml:
    prefix_prefix: linkml
    prefix_reference: https://w3id.org/linkml/
default_range: string
slots:
  longitude:
    name: longitude
    range: double
classes:
  Observation:
    name: Observation
    slots:
    - longitude
"""


def test_lint_structural_block(tmp_path: Path) -> None:
    """Slot on Entity, class mapped to SensorReport (unreachable) → BLOCK."""
    src = tmp_path / "source.yaml"
    src.write_text(_SOURCE_SCHEMA_YAML)
    mst = tmp_path / "master.yaml"
    mst.write_text(_MASTER_SCHEMA_YAML)
    sssom = tmp_path / "mappings.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "source:Observation",
                "predicate_id": "skos:exactMatch",
                "object_id": "master:SensorReport",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
            {
                "subject_id": "source:longitude",
                "predicate_id": "skos:exactMatch",
                "object_id": "master:hasLongitude",
                "mapping_justification": _MMC,
                "confidence": "0.85",
            },
        ],
    )
    audit_log = _write_empty_audit_log(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 1
    data = json.loads(result.output)
    structural = [f for f in data["findings"] if f["rule"] == "slot_class_unreachable"]
    assert len(structural) == 1
    assert structural[0]["severity"] == "BLOCK"
    assert "Entity" in structural[0]["message"]
    assert "SensorReport" in structural[0]["message"]


def test_lint_structural_pass(tmp_path: Path) -> None:
    """Slot on Entity, class mapped to Track (extends Entity) → no structural finding."""
    src = tmp_path / "source.yaml"
    src.write_text(_SOURCE_SCHEMA_YAML)
    mst = tmp_path / "master.yaml"
    mst.write_text(_MASTER_SCHEMA_YAML)
    sssom = tmp_path / "mappings.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "source:Observation",
                "predicate_id": "skos:exactMatch",
                "object_id": "master:Track",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
            {
                "subject_id": "source:longitude",
                "predicate_id": "skos:exactMatch",
                "object_id": "master:hasLongitude",
                "mapping_justification": _MMC,
                "confidence": "0.85",
            },
        ],
    )
    audit_log = _write_empty_audit_log(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    data = json.loads(result.output)
    structural = [f for f in data["findings"] if f["rule"] == "slot_class_unreachable"]
    assert not structural


def test_lint_schema_one_missing_errors(tmp_path: Path) -> None:
    """--master-schema is required; omitting it → Click error exit 2."""
    src = tmp_path / "source.yaml"
    src.write_text(_SOURCE_SCHEMA_YAML)
    sssom = tmp_path / "mappings.sssom.tsv"
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
    audit_log = _write_empty_audit_log(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
        ],
    )
    assert result.exit_code == 2
    assert "master-schema" in result.output


def test_lint_cli_audit_log_provided(tmp_path: Path) -> None:
    """--audit-log provided explicitly → lint succeeds."""
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
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)

    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)


def test_lint_hc_in_candidates_blocked(tmp_path: Path) -> None:
    """Candidates SSSOM file with an HC row → BLOCK finding with rule 'hc_in_candidates', exit 1."""
    sssom = tmp_path / "hc_candidate.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "ex:fieldA",
                "predicate_id": "skos:exactMatch",
                "object_id": "ex:masterA",
                "mapping_justification": _HC,
                "confidence": "0.95",
            },
        ],
    )
    audit_log = _write_empty_audit_log(tmp_path)
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 1, result.output
    data = json.loads(result.output)
    hc_findings = [f for f in data["findings"] if f["rule"] == "hc_in_candidates"]
    assert hc_findings, "Expected hc_in_candidates BLOCK finding"
    assert hc_findings[0]["severity"] == "BLOCK"


def test_lint_audit_log_autocreated(tmp_path: Path) -> None:
    """--audit-log pointing to nonexistent path → file is created, lint succeeds (exit 0)."""
    sssom = tmp_path / "clean_auto.sssom.tsv"
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
    new_log = tmp_path / "new-subdir" / "audit-log.sssom.tsv"
    assert not new_log.exists()
    src, mst = _write_minimal_schemas(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            str(sssom),
            "--audit-log",
            str(new_log),
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    assert new_log.exists(), "audit-log file should have been auto-created"
