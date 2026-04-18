"""Integration tests for rosetta-lint on SSSOM fixtures (Phase 18-02)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.lint import cli as lint_cli
from rosetta.core.models import LintReport

pytestmark = [pytest.mark.integration]

_MMC = "semapv:ManualMappingCuration"
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


def test_lint_on_suggest_output(tmp_path: Path, sssom_nor_path: Path) -> None:
    """Clean SSSOM proposal fixture → exit 0, zero BLOCK findings."""
    config = _no_accredit_toml(tmp_path)
    result = CliRunner(mix_stderr=False).invoke(
        lint_cli,
        ["--sssom", str(sssom_nor_path), "--config", str(config)],
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
    config = _no_accredit_toml(tmp_path)
    result = CliRunner(mix_stderr=False).invoke(
        lint_cli,
        ["--sssom", str(sssom), "--config", str(config)],
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
