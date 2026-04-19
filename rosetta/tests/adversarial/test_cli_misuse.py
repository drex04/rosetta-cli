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
from rosetta.cli.suggest import cli as suggest_cli
from rosetta.cli.yarrrml_gen import cli as yarrrml_gen_cli

pytestmark = [pytest.mark.integration]


def test_yarrrml_gen_run_without_data(
    tmp_path: Path,
    sssom_nor_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
) -> None:
    """`--run` without `--data` → exit 1 with "--run requires --data" on stderr.

    The guard fires at step 0 of the CLI (before any artifact write). Neither
    the TransformSpec YAML nor the JSON-LD materialization product lands on
    disk.
    """
    output_yaml = tmp_path / "spec.transform.yaml"
    jsonld_out = tmp_path / "out.jsonld"

    result = CliRunner(mix_stderr=False).invoke(
        yarrrml_gen_cli,
        [
            "--sssom",
            str(sssom_nor_path),
            "--source-schema",
            str(nor_linkml_path),
            "--master-schema",
            str(master_schema_path),
            "--output",
            str(output_yaml),
            "--jsonld-output",
            str(jsonld_out),
            "--run",
        ],
    )

    # 1. Exit code.
    assert result.exit_code == 1, (
        f"expected exit 1 when --run is given without --data; got {result.exit_code}: "
        f"{result.stderr}"
    )
    # 2. Stderr substring — stable phrase from the guard.
    assert "--data" in result.stderr
    assert "--run" in result.stderr or "requires" in result.stderr
    # 3. Behavioural invariant: no partial artifact on disk (neither spec YAML
    #    nor JSON-LD) — guard fires before any write.
    assert not jsonld_out.exists(), (
        "JSON-LD output must not be produced when the --run/--data guard fires"
    )
    assert not output_yaml.exists(), (
        "TransformSpec YAML must not be written when the --run/--data guard fires"
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


def test_yarrrml_gen_stdout_and_file_collision(
    tmp_path: Path,
    sssom_nor_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`--output -` + `--jsonld-output -` under `--run` → exit 2, clear diagnostic.

    Both values target stdout; merging the TransformSpec YAML and the JSON-LD
    bytes into a single stream would produce a malformed document. The step-0
    guard rejects the combination before any write. Plan 19-03 Task 3 unified
    the stdout-collision guard onto ``click.UsageError`` (exit 2) so all
    flag-combination misuse exits with the Click usage convention.
    """
    result = CliRunner(mix_stderr=False).invoke(
        yarrrml_gen_cli,
        [
            "--sssom",
            str(sssom_nor_path),
            "--source-schema",
            str(nor_linkml_path),
            "--master-schema",
            str(master_schema_path),
            "--source-format",
            "csv",
            "--output",
            "-",
            "--jsonld-output",
            "-",
            "--run",
            "--data",
            str(nor_csv_sample_path),
        ],
    )

    # 1. Exit code — UsageError convention (Plan 19-03 Task 3).
    assert result.exit_code == 2, (
        f"expected exit 2 (Click UsageError) when --output and --jsonld-output "
        f"both target stdout; got {result.exit_code}"
    )
    # 2. Stderr substring — names both flags + 'stdout'.
    assert "stdout" in result.stderr
    assert "--output" in result.stderr and "--jsonld-output" in result.stderr
    # 3. Behavioural invariant: no traceback on stderr.
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
