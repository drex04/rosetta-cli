"""Integration tests for rosetta lint on SSSOM fixtures (Phase 18-02)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.lint import cli as lint_cli
from rosetta.core.models import LintReport

pytestmark = [pytest.mark.integration]

_MMC = "semapv:ManualMappingCuration"


def _cell(row: object, col: str) -> str:
    if col == "confidence":
        return str(getattr(row, col))
    if col == "mapping_date":
        d = getattr(row, col, None)
        return d.isoformat() if d else ""
    val = getattr(row, col, None)
    return "" if val is None else str(val)


def _write_sssom(path: Path, rows: list[dict[str, object]]) -> None:
    """Write SSSOM TSV using real SSSOMRow models for format consistency."""
    from rosetta.core.ledger import AUDIT_LOG_COLUMNS
    from rosetta.core.ledger import SSSOM_HEADER as _HEADER
    from rosetta.core.models import SSSOMRow

    built: list[SSSOMRow] = []
    for r in rows:
        defaults: dict[str, object] = {
            "predicate_id": "skos:exactMatch",
            "mapping_justification": _MMC,
            "confidence": 0.9,
            "subject_label": "",
            "object_label": "",
            "subject_type": None,
            "object_type": None,
            "mapping_group_id": None,
            "composition_expr": None,
        }
        defaults.update(r)
        built.append(SSSOMRow(**defaults))  # pyright: ignore[reportArgumentType]

    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(_HEADER)
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(AUDIT_LOG_COLUMNS)
        for row in built:
            writer.writerow([_cell(row, col) for col in AUDIT_LOG_COLUMNS])


def _no_accredit_toml(tmp_path: Path) -> Path:
    config = tmp_path / "rosetta.toml"
    config.write_text("[suggest]\ntop_k = 5\n")
    return config


def test_lint_on_suggest_output(tmp_path: Path, sssom_nor_path: Path) -> None:
    """Clean SSSOM proposal fixture → exit 0, zero BLOCK findings."""
    import csv

    from rosetta.core.ledger import AUDIT_LOG_COLUMNS
    from rosetta.core.ledger import SSSOM_HEADER as _HEADER

    config = _no_accredit_toml(tmp_path)

    audit_log = tmp_path / "audit-log.sssom.tsv"
    with audit_log.open("w") as fh:
        fh.write(_HEADER)
        csv.writer(fh, delimiter="\t").writerow(AUDIT_LOG_COLUMNS)

    src_schema = tmp_path / "source.yaml"
    src_schema.write_text(
        "name: source\nid: https://example.org/source\nimports:\n- linkml:types\n"
        "prefixes:\n  linkml:\n    prefix_prefix: linkml\n"
        "    prefix_reference: https://w3id.org/linkml/\ndefault_range: string\n"
        "classes:\n  Thing:\n    name: Thing\n"
    )
    mst_schema = tmp_path / "master.yaml"
    mst_schema.write_text(
        "name: master\nid: https://example.org/master\nimports:\n- linkml:types\n"
        "prefixes:\n  linkml:\n    prefix_prefix: linkml\n"
        "    prefix_reference: https://w3id.org/linkml/\ndefault_range: string\n"
        "classes:\n  Thing:\n    name: Thing\n"
    )

    result = CliRunner(mix_stderr=False).invoke(
        lint_cli,
        [
            str(sssom_nor_path),
            "--audit-log",
            str(audit_log),
            "--config",
            str(config),
            "--source-schema",
            str(src_schema),
            "--master-schema",
            str(mst_schema),
        ],
    )
    assert result.exit_code == 0, f"lint failed: {result.stdout}\n{result.stderr}"

    report = LintReport.model_validate_json(result.stdout)
    assert report.summary.block == 0, (
        f"expected zero BLOCK findings on clean fixture, got {report.summary.block}: "
        f"{[f.rule for f in report.findings if f.severity == 'BLOCK']}"
    )


def test_lint_unit_dimension_mismatch(tmp_path: Path) -> None:
    """Incompatible unit dimensions (meters vs knots) produce a BLOCK finding."""
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
    import csv

    from rosetta.core.ledger import AUDIT_LOG_COLUMNS
    from rosetta.core.ledger import SSSOM_HEADER as _HEADER

    config = _no_accredit_toml(tmp_path)

    audit_log = tmp_path / "audit-log.sssom.tsv"
    with audit_log.open("w") as fh:
        fh.write(_HEADER)
        csv.writer(fh, delimiter="\t").writerow(AUDIT_LOG_COLUMNS)

    src_schema = tmp_path / "source.yaml"
    src_schema.write_text(
        "name: source\nid: https://example.org/source\nimports:\n- linkml:types\n"
        "prefixes:\n  linkml:\n    prefix_prefix: linkml\n"
        "    prefix_reference: https://w3id.org/linkml/\ndefault_range: string\n"
        "classes:\n  Thing:\n    name: Thing\n"
    )
    mst_schema = tmp_path / "master.yaml"
    mst_schema.write_text(
        "name: master\nid: https://example.org/master\nimports:\n- linkml:types\n"
        "prefixes:\n  linkml:\n    prefix_prefix: linkml\n"
        "    prefix_reference: https://w3id.org/linkml/\ndefault_range: string\n"
        "classes:\n  Thing:\n    name: Thing\n"
    )

    result = CliRunner(mix_stderr=False).invoke(
        lint_cli,
        [
            str(sssom),
            "--audit-log",
            str(audit_log),
            "--config",
            str(config),
            "--source-schema",
            str(src_schema),
            "--master-schema",
            str(mst_schema),
        ],
    )
    # Exit code 1 because BLOCK findings are present.
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stdout}"

    report = LintReport.model_validate_json(result.stdout)
    mismatches = [f for f in report.findings if f.rule == "unit_dimension_mismatch"]
    assert mismatches, (
        f"expected at least one unit_dimension_mismatch finding, got rules: "
        f"{[f.rule for f in report.findings]}"
    )
    assert mismatches[0].severity == "BLOCK"
    assert report.summary.block >= 1
