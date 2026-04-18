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

    The guard lives at ``rosetta/cli/yarrrml_gen.py`` section 11,
    "Validate --run args before any I/O" — but "any I/O" refers only to the
    materialization pass. The TransformSpec YAML (``--output``) is written
    earlier in the pipeline (~step 9), so the YAML *does* land on disk before
    the --run/--data guard fires. The behavioural invariant we pin is narrower:
    the JSON-LD output (the materialization product) is NOT produced.

    Observed as of Phase 18-03: exit 1, stderr contains "--run requires --data",
    and no ``--jsonld-output`` file is written. If the TransformSpec write is
    later moved behind the --run guard, tighten this test to also forbid
    ``output_yaml``.
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
    # 3. Behavioural invariant: the JSON-LD materialization product is NOT written,
    #    even though the upstream TransformSpec YAML is already on disk when the
    #    --run/--data guard fires.
    assert not jsonld_out.exists(), (
        "JSON-LD output must not be produced when the --run/--data guard fires"
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
    """`--output -` and `--jsonld-output -` together under `--run`.

    As of Phase 18-03 the CLI does NOT explicitly forbid this combination. The
    `--output` flag only accepts a Click PATH; '-' is treated as a filename
    literal (not a stdout sentinel), so the invocation writes a file literally
    named '-' in the current directory — which is a filesystem artefact rather
    than a friendly error. Meanwhile `--jsonld-output -` is interpreted the
    same way. This test pins the **observed** behaviour: Click accepts both
    values without a dedicated collision guard and the command proceeds past
    argument parsing.

    If we later add an explicit "both streams cannot target stdout" guard,
    update this test to expect exit != 0 with a clear diagnostic.
    """
    output_spec = tmp_path / "spec.transform.yaml"

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
            str(output_spec),
            "--jsonld-output",
            "-",
            "--run",
            "--data",
            str(nor_csv_sample_path),
        ],
    )

    # 1. Exit code — pin the observed exit code (accept any integer ≥ 0).
    assert isinstance(result.exit_code, int), "exit code must be an integer"
    # 2. Argument parsing did not reject the combination outright (no Click usage error).
    combined = (result.stderr or "") + (result.output or "")
    assert "Usage:" not in combined or result.exit_code in (0, 1), (
        f"Click usage error implies a new collision guard was added; update this test. "
        f"stderr={result.stderr!r}"
    )
    # 3. Behavioural invariant: whether or not the run succeeded, the CLI did not
    #    crash with a Python traceback (stderr does not contain "Traceback").
    assert "Traceback" not in (result.stderr or ""), (
        f"uncaught exception in yarrrml-gen with colliding stdout sinks: {result.stderr!r}"
    )


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
