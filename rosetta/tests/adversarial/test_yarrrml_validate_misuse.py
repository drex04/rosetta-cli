"""Adversarial CLI-misuse tests for `rosetta-yarrrml-gen --validate` (Plan 19-03 Task 4).

Each test pins one observable: exit code + stderr substring + behavioural
invariant for a flag-combination misuse. The CLI's step-0 guards run before
any I/O, so misuse must never leave partial artifacts on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.yarrrml_gen import cli as yarrrml_gen_cli

pytestmark = [pytest.mark.adversarial]


# Two SHACL shapes reused across tests below. Both are valid Turtle so the
# --shapes-dir guard passes when present.
_PERMISSIVE_SHAPE_TTL = """\
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix mc: <https://ontology.nato.int/core/MasterCOP#> .

mc:TrackPermissiveShape a sh:NodeShape ;
    sh:targetClass mc:Track .
"""

_IMPOSSIBLE_SHAPE_TTL = """\
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix mc: <https://ontology.nato.int/core/MasterCOP#> .

mc:TrackImpossibleShape a sh:NodeShape ;
    sh:targetClass mc:Track ;
    sh:property [
        sh:path mc:hasMode5 ;
        sh:minCount 1 ;
        sh:message "every track requires Mode 5" ;
    ] .
"""


def _shapes_dir(tmp_path: Path, shape_ttl: str = _PERMISSIVE_SHAPE_TTL) -> Path:
    """Materialize a single-shape directory and return its path."""
    d = tmp_path / "shapes"
    d.mkdir()
    (d / "shape.shacl.ttl").write_text(shape_ttl, encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# Flag-combination guards (no materialization needed — fail at step 0)
# ---------------------------------------------------------------------------


def test_validate_without_shapes_dir_errors(
    tmp_path: Path,
    sssom_nor_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`--validate --run` without `--shapes-dir` -> exit 2 (UsageError) before any I/O."""
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
            "--source-format",
            "csv",
            "--output",
            str(output_yaml),
            "--jsonld-output",
            str(jsonld_out),
            "--run",
            "--data",
            str(nor_csv_sample_path),
            "--validate",
        ],
    )

    # 1. Exit code — Click's UsageError convention.
    assert result.exit_code == 2, (
        f"expected Click UsageError exit 2; got {result.exit_code}: stderr={result.stderr!r}"
    )
    # 2. Stderr substring — names the missing dependency.
    assert "--validate requires --shapes-dir" in result.stderr, (
        f"missing 'requires --shapes-dir' phrase: {result.stderr!r}"
    )
    # 3. Behavioural invariant: no artifact lands on disk.
    assert not output_yaml.exists()
    assert not jsonld_out.exists()


def test_validate_without_run_errors(
    tmp_path: Path,
    sssom_nor_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
) -> None:
    """`--validate --shapes-dir` without `--run` -> exit 2 (UsageError) before any I/O."""
    output_yaml = tmp_path / "spec.transform.yaml"
    shapes_dir = _shapes_dir(tmp_path)

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
            str(output_yaml),
            "--validate",
            "--shapes-dir",
            str(shapes_dir),
        ],
    )

    # 1. Exit code — Click's UsageError convention.
    assert result.exit_code == 2, (
        f"expected Click UsageError exit 2; got {result.exit_code}: stderr={result.stderr!r}"
    )
    # 2. Stderr substring — names the missing dependency.
    assert "--validate requires --run" in result.stderr, (
        f"missing 'requires --run' phrase: {result.stderr!r}"
    )
    # 3. Behavioural invariant: no TransformSpec written.
    assert not output_yaml.exists()


# ---------------------------------------------------------------------------
# stdout-collision guards (also step 0; no materialization)
# ---------------------------------------------------------------------------


def test_stdout_collision_output_validate_report(
    tmp_path: Path,
    sssom_nor_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`--output -` + `--validate-report -` -> exit 2, stderr cites the collision."""
    shapes_dir = _shapes_dir(tmp_path)
    workdir = tmp_path / "wd"  # would be created if step-0 didn't catch the misuse

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
            "--validate-report",
            "-",
            "--validate",
            "--run",
            "--data",
            str(nor_csv_sample_path),
            "--shapes-dir",
            str(shapes_dir),
            "--workdir",
            str(workdir),
        ],
    )

    # 1. Exit code — UsageError convention.
    assert result.exit_code == 2, (
        f"expected exit 2 from stdout-collision UsageError; got {result.exit_code}: "
        f"stderr={result.stderr!r}"
    )
    # 2. Stderr cites both colliding flags + 'stdout'.
    assert "stdout" in result.stderr.lower()
    assert "--output" in result.stderr and "--validate-report" in result.stderr
    # 3. Behavioural invariant: morph-kgc workdir was never touched.
    assert not workdir.exists(), (
        f"workdir should not be created when step-0 guard fails; "
        f"contents={list(workdir.iterdir()) if workdir.exists() else None}"
    )


def test_stdout_collision_jsonld_validate_report(
    tmp_path: Path,
    sssom_nor_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`--jsonld-output -` + `--validate-report -` -> exit 2, no materialization."""
    shapes_dir = _shapes_dir(tmp_path)
    workdir = tmp_path / "wd"

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
            "--jsonld-output",
            "-",
            "--validate-report",
            "-",
            "--validate",
            "--run",
            "--data",
            str(nor_csv_sample_path),
            "--shapes-dir",
            str(shapes_dir),
            "--workdir",
            str(workdir),
        ],
    )

    # 1. Exit code — UsageError convention.
    assert result.exit_code == 2, (
        f"expected exit 2 from stdout-collision UsageError; got {result.exit_code}: "
        f"stderr={result.stderr!r}"
    )
    # 2. Stderr cites both colliding flags + 'stdout'.
    assert "stdout" in result.stderr.lower()
    assert "--jsonld-output" in result.stderr and "--validate-report" in result.stderr
    # 3. Behavioural invariant: morph-kgc workdir was never touched.
    assert not workdir.exists(), (
        f"workdir should not be created when step-0 guard fails; "
        f"contents={list(workdir.iterdir()) if workdir.exists() else None}"
    )


# ---------------------------------------------------------------------------
# No-partial-output invariant (full-chain materialization)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_validate_no_partial_jsonld_on_violation(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """Pre-existing file at --jsonld-output stays unmodified when validation fails.

    Pins the "no partial output" invariant: even if a previous run already
    wrote bytes to the JSON-LD path, a violation aborts BEFORE truncating
    or rewriting that file.
    """
    import shutil

    # Patch the dateTime typo so materialization runs (the violation needs to
    # surface during shacl validate, not during context generation).
    nor_dst = tmp_path / "nor_radar.linkml.yaml"
    mc_dst = tmp_path / "master_cop.linkml.yaml"
    sssom_dst = tmp_path / "sssom_nor_approved.sssom.tsv"
    csv_dst = tmp_path / "nor_radar_sample.csv"
    shutil.copy(nor_linkml_path, nor_dst)
    shutil.copy(sssom_nor_path, sssom_dst)
    shutil.copy(nor_csv_sample_path, csv_dst)
    mc_dst.write_text(
        master_schema_path.read_text(encoding="utf-8").replace("dateTime", "datetime"),
        encoding="utf-8",
    )

    shapes_dir = _shapes_dir(tmp_path, _IMPOSSIBLE_SHAPE_TTL)

    spec_out = tmp_path / "spec.transform.yaml"
    jsonld_out = tmp_path / "out.jsonld"
    report_out = tmp_path / "validate-report.json"
    workdir = tmp_path / "wd"

    # Pre-create the JSON-LD output with sentinel content. The CLI must not
    # overwrite or truncate this file when SHACL validation flags a violation.
    sentinel = "PREVIOUS CONTENT"
    jsonld_out.write_text(sentinel, encoding="utf-8")

    result = CliRunner(mix_stderr=False).invoke(
        yarrrml_gen_cli,
        [
            "--sssom",
            str(sssom_dst),
            "--source-schema",
            str(nor_dst),
            "--master-schema",
            str(mc_dst),
            "--output",
            str(spec_out),
            "--force",
            "--run",
            "--data",
            str(csv_dst),
            "--jsonld-output",
            str(jsonld_out),
            "--validate",
            "--shapes-dir",
            str(shapes_dir),
            "--validate-report",
            str(report_out),
            "--workdir",
            str(workdir),
        ],
    )

    # 1. Exit code — SHACL violation aborts the pipeline.
    assert result.exit_code == 1, (
        f"expected exit 1 from SHACL violation; got {result.exit_code}\n"
        f"stderr={result.stderr!r}\nexception={result.exception!r}"
    )
    # 2. Pre-existing JSON-LD file is untouched (byte-for-byte equal to sentinel).
    assert jsonld_out.read_text(encoding="utf-8") == sentinel, (
        "JSON-LD output file must not be overwritten or truncated when SHACL validation fails"
    )
