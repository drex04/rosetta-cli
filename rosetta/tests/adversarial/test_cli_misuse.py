"""Adversarial tests for CLI misuse (Phase 18-03, Task 5).

Each test pins the observed exit code + stderr + behavioural invariant for a
common user mistake. Click's `Path(exists=True)` conventionally exits 2 on
missing files; Rosetta's own explicit guards exit 1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.ingest import cli as ingest_cli
from rosetta.cli.run import cli as run_cli
from rosetta.cli.suggest import cli as suggest_cli

pytestmark = [pytest.mark.integration]


def test_run_without_source_file_exits_2(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
) -> None:
    """``rosetta run <mapping>`` without SOURCE_FILE → exit 2 (Click missing argument).

    On run.py, SOURCE_FILE is a required positional argument. Omitting it
    triggers Click's built-in missing-argument error (exit 2) before any I/O.
    """
    mapping = tmp_path / "mapping.yarrrml.yaml"
    mapping.write_text("prefixes:\n  ex: http://example.org/\nmappings: {}\n", encoding="utf-8")

    result = CliRunner(mix_stderr=False).invoke(
        run_cli,
        [
            str(mapping),
            "--master-schema",
            str(master_schema_path),
        ],
    )

    # Click's missing-argument convention is exit 2.
    assert result.exit_code == 2, (
        f"expected exit 2 (missing SOURCE_FILE); got {result.exit_code}: {result.stderr}"
    )


def test_ingest_nonexistent_input_file(tmp_path: Path) -> None:
    """`rosetta-ingest --input <nonexistent>` → Click exits 2 ("does not exist").

    Click's `Path(exists=True)` is the gate. We use an absolute path that does
    not exist so the error is unambiguous across platforms.
    """
    missing = tmp_path / "does_not_exist.csv"
    assert not missing.exists()
    output = tmp_path / "out.linkml.yaml"

    result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [
            "--input",
            str(missing),
            "--format",
            "csv",
            "--output",
            str(output),
        ],
    )

    # 1. Exit code — Click convention for parameter errors is 2, not 1.
    assert result.exit_code == 2, (
        f"expected Click's parameter-error exit 2, got {result.exit_code}: "
        f"{result.stderr or result.output}"
    )
    # 2. Stderr/output substring — Click writes usage + "does not exist".
    combined = (result.stderr or "") + (result.output or "")
    assert "does not exist" in combined, f"missing 'does not exist' phrase: {combined!r}"
    # 3. Behavioural invariant: no output file was written.
    assert not output.exists()


def test_run_stdout_and_validate_report_collision(
    tmp_path: Path,
    master_schema_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`rosetta run` with `-o` (stdout) + `--validate-report -` → exit 2.

    Both target stdout. The step-0 guard in run.py rejects the combination
    before any materialization. Plan 19-03 Task 3 unified the stdout-collision
    guard onto ``click.UsageError`` (exit 2).
    """
    mapping = tmp_path / "mapping.yarrrml.yaml"
    mapping.write_text("prefixes:\n  ex: http://example.org/\nmappings: {}\n", encoding="utf-8")

    result = CliRunner(mix_stderr=False).invoke(
        run_cli,
        [
            str(mapping),
            str(nor_csv_sample_path),
            "--master-schema",
            str(master_schema_path),
            # omit -o → defaults to stdout
            "--validate-report",
            "-",  # also targets stdout
        ],
    )

    # 1. Exit code — UsageError convention.
    assert result.exit_code == 2, (
        f"expected exit 2 (Click UsageError) from stdout collision; got {result.exit_code}: "
        f"stderr={result.stderr!r}"
    )
    # 2. Stderr cites 'stdout'.
    assert "stdout" in result.stderr.lower()
    # 3. No traceback.
    assert "Traceback" not in result.stderr


def test_suggest_missing_required_args(tmp_path: Path) -> None:
    """`rosetta-suggest` with no positional args → Click exits 2 with usage.

    `suggest_cli` declares two `click.argument`s (SOURCE, MASTER). Missing
    either → Click's built-in missing-argument error (exit code 2).
    """
    result = CliRunner(mix_stderr=False).invoke(suggest_cli, [])

    # 1. Exit code — Click's missing-argument convention.
    assert result.exit_code == 2, (
        f"expected Click's missing-argument exit 2, got {result.exit_code}: "
        f"{result.stderr or result.output}"
    )
    # 2. Stderr/output substring — Click prints "Usage:" and "Missing argument".
    combined = (result.stderr or "") + (result.output or "")
    assert "Missing argument" in combined or "Usage:" in combined, (
        f"expected usage/missing-argument message: {combined!r}"
    )
    # 3. Behavioural invariant: no stdout payload beyond the usage message.
    assert "{" not in (result.stdout or ""), (
        "no JSON output should leak on an argument-validation failure"
    )
