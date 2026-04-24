"""Adversarial tests for rosetta accredit SSSOM ingest mistakes (Phase 18-03, Task 4).

These tests pin the observable error behaviour of `rosetta accredit append` against
malformed SSSOM inputs:

- Duplicate MMC rows in a single file (in-file pre-scan at `rosetta/cli/accredit.py::append_cmd`)
- Too-few-column TSV (observed behaviour documented per test)
- Phantom derank (HC with owl:differentFrom when no prior MMC exists) — rejected via
  `check_ingest_row`'s HC→MMC transition guard in `rosetta/core/accredit.py`
- Clean single-row MMC baseline (positive control)

Three-level assertion contract (D-18-08) is applied to every test:
1. Exit code
2. Stderr substring match
3. Behavioural invariant (log file presence / size)
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.ledger import cli as accredit_cli
from rosetta.core.ledger import HC_JUSTIFICATION, MMC_JUSTIFICATION
from rosetta.core.lint import check_sssom_proposals
from rosetta.core.models import SSSOM_COLUMNS, LintReport, LintSummary, SSSOMRow

pytestmark = [pytest.mark.integration]


_MINIMAL_SCHEMA = """\
id: https://example.org/test
name: test_schema
prefixes:
  linkml: https://w3id.org/linkml/
imports:
  - linkml:types
classes:
  TestClass:
    attributes:
      test_field:
        range: string
"""


def _schema_file(tmp_path: Path, name: str = "schema.yaml") -> Path:
    p = tmp_path / name
    p.write_text(_MINIMAL_SCHEMA)
    return p


def _noop_lint(
    rows: list[SSSOMRow],
    log: list[SSSOMRow],
    source_schema: str | Path,
    master_schema: str | Path,
    *,
    strict: bool = False,
) -> LintReport:
    return LintReport(findings=[], summary=LintSummary(block=0, warning=0, info=0))


def _proposals_only_lint(
    rows: list[SSSOMRow],
    log: list[SSSOMRow],
    source_schema: str | Path,
    master_schema: str | Path,
    *,
    strict: bool = False,
) -> LintReport:
    findings = check_sssom_proposals(rows, log)
    summary = LintSummary(
        block=sum(1 for f in findings if f.severity == "BLOCK"),
        warning=sum(1 for f in findings if f.severity == "WARNING"),
        info=sum(1 for f in findings if f.severity == "INFO"),
    )
    return LintReport(findings=findings, summary=summary)


_SSSOM_FILE_HEADER: str = (
    "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
    "# mapping_set_id: http://rosetta.interop/test-adversarial\n"
    "# curie_map:\n"
    "#   semapv: https://w3id.org/semapv/vocab/\n"
    "#   skos: http://www.w3.org/2004/02/skos/core#\n"
    "#   owl: http://www.w3.org/2002/07/owl#\n"
)


def _write_sssom(tmp_path: Path, rows: list[dict[str, str]], name: str) -> Path:
    """Write an SSSOM TSV with the canonical column set."""
    path = tmp_path / name
    with path.open("w", encoding="utf-8") as f:
        f.write(_SSSOM_FILE_HEADER)
        writer = csv.DictWriter(f, fieldnames=SSSOM_COLUMNS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in SSSOM_COLUMNS})
    return path


def test_accredit_duplicate_mmc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two MMC rows with the same (subject_id, object_id) in one file → exit 1, no log write.

    The duplicate guard lives in `check_sssom_proposals` (max_one_mmc_per_pair rule).
    """
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _proposals_only_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    src = _schema_file(tmp_path, "src.yaml")
    mst = _schema_file(tmp_path, "mst.yaml")
    assert not log_path.exists()

    tsv_file = _write_sssom(
        tmp_path,
        [
            {
                "subject_id": "nor:alt_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:altitude",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "nor:alt_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:altitude",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.85",
            },
        ],
        "dup_mmc.sssom.tsv",
    )

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
            str(tsv_file),
        ],
    )

    # 1. Exit code.
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stderr}"
    # 2. Stderr — lint report JSON with max_one_mmc_per_pair rule.
    assert "max_one_mmc_per_pair" in result.stderr
    assert "nor:alt_m" in result.stderr
    # 3. Behavioural invariant: nothing was appended to the audit log.
    assert not log_path.exists(), "log file must not be created on a rejected append"


def test_accredit_wrong_column_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TSV header with wrong columns → exit 1, clear diagnostic, no log write."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    src = _schema_file(tmp_path, "src.yaml")
    mst = _schema_file(tmp_path, "mst.yaml")
    assert not log_path.exists()

    tsv_file = tmp_path / "missing_required_cols.sssom.tsv"
    bad_cols = ["subject_id", "predicate_id", "object_id"]
    with tsv_file.open("w", encoding="utf-8") as f:
        f.write(_SSSOM_FILE_HEADER)
        f.write("\t".join(bad_cols) + "\n")
        f.write("\t".join(["a", "skos:exactMatch", "b"]) + "\n")

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
            str(tsv_file),
        ],
    )

    assert result.exit_code == 1, f"expected exit 1 on wrong columns; got {result.exit_code}"
    assert "wrong columns" in result.stderr.lower()
    assert not log_path.exists(), "log file must not be created on a rejected append"


def test_accredit_phantom_rejection_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HC with owl:differentFrom but no prior MMC → exit 1, no log write.

    Flow: accreditor role accepts HC rows, then `check_ingest_row` raises ValueError
    when no prior MMC exists for the pair.
    """
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    src = _schema_file(tmp_path, "src.yaml")
    mst = _schema_file(tmp_path, "mst.yaml")
    assert not log_path.exists()

    tsv_file = _write_sssom(
        tmp_path,
        [
            {
                "subject_id": "nor:spd",
                "predicate_id": "owl:differentFrom",
                "object_id": "mc:speed",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "1.0",
            }
        ],
        "phantom_rejection.sssom.tsv",
    )

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "accreditor",
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
            str(tsv_file),
        ],
    )

    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stderr}"
    assert (
        "no ManualMappingCuration" in result.stderr
        or "Cannot ingest HumanCuration" in result.stderr
    ), f"stderr did not name the missing-MMC transition: {result.stderr!r}"
    assert "nor:spd" in result.stderr
    assert "mc:speed" in result.stderr
    assert not log_path.exists(), "log file must not be created on a rejected append"


def test_accredit_clean_append_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: a single valid MMC row ingests cleanly."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    src = _schema_file(tmp_path, "src.yaml")
    mst = _schema_file(tmp_path, "mst.yaml")
    assert not log_path.exists()

    tsv_file = _write_sssom(
        tmp_path,
        [
            {
                "subject_id": "nor:alt_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:altitude",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            }
        ],
        "clean.sssom.tsv",
    )

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(src),
            "--master-schema",
            str(mst),
            str(tsv_file),
        ],
    )

    assert result.exit_code == 0, f"clean append should succeed; stderr: {result.stderr}"
    assert "Error" not in result.stderr
    assert log_path.exists(), "log file must be created on a successful append"
    assert log_path.stat().st_size > 0
