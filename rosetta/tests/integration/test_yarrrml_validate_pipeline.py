"""Integration tests for `rosetta compile` + `rosetta run --validate` (Plan 19-03 Task 4).

These walk the full chain:

    SSSOM audit log → YARRRML (rosetta compile)
                    → morph-kgc graph (rosetta run)
                    → SHACL validate → JSON-LD (only on conform)

Two truths:
  - Happy path: when validation conforms, JSON-LD is emitted.
  - Violation path: when validation flags a violation, exit code 1, JSON-LD
    output file is NOT created, and the validation report is written.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.compile import cli as compile_cli
from rosetta.cli.shapes import cli as shacl_gen_cli
from rosetta.cli.transform import cli as run_cli

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixture-prep helpers (mirror test_yarrrml_run_e2e.py — patch the dateTime typo
# so the ContextGenerator step succeeds).
# ---------------------------------------------------------------------------


def _copy_and_patch_schemas(
    dst_dir: Path,
    nor_schema_src: Path,
    master_schema_src: Path,
    sssom_src: Path,
    csv_src: Path,
) -> tuple[Path, Path, Path, Path]:
    """Copy fixtures to ``dst_dir`` and patch the LinkML ``dateTime`` typo."""
    nor_dst = dst_dir / "nor_radar.linkml.yaml"
    mc_dst = dst_dir / "master_cop.linkml.yaml"
    sssom_dst = dst_dir / "sssom_nor_approved.sssom.tsv"
    csv_dst = dst_dir / "nor_radar_sample.csv"

    shutil.copy(nor_schema_src, nor_dst)
    shutil.copy(sssom_src, sssom_dst)
    shutil.copy(csv_src, csv_dst)

    text = master_schema_src.read_text(encoding="utf-8")
    mc_dst.write_text(text.replace("dateTime", "datetime"), encoding="utf-8")

    return nor_dst, mc_dst, sssom_dst, csv_dst


def _compile_to_yarrrml(
    tmp_path: Path,
    sssom: Path,
    nor_schema: Path,
    mc_schema: Path,
) -> Path:
    """Helper: run compile and return the YARRRML output path."""
    yarrrml_out = tmp_path / "mapping.yarrrml.yaml"
    result = CliRunner(mix_stderr=False).invoke(
        compile_cli,
        [
            str(sssom),
            "--source-schema",
            str(nor_schema),
            "--master-schema",
            str(mc_schema),
            "-o",
            str(yarrrml_out),
        ],
    )
    assert result.exit_code == 0, (
        f"compile failed: exit={result.exit_code} stderr={result.stderr!r} "
        f"exception={result.exception!r}"
    )
    return yarrrml_out


# Permissive shape: matches every materialized triple's expected
# subject-class (mc:Track) but adds no minCount constraints.
_PERMISSIVE_SHAPE_TTL = """\
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix mc: <https://ontology.nato.int/core/MasterCOP#> .

mc:TrackPermissiveShape a sh:NodeShape ;
    sh:targetClass mc:Track .
"""

# Impossible shape: every mc:Track must declare mc:hasMode5.
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_yarrrml_run_validate_happy_path(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`rosetta run --validate` with a permissive shape: exit 0, JSON-LD written."""
    nor_schema, mc_schema, sssom, csv = _copy_and_patch_schemas(
        tmp_path, nor_linkml_path, master_schema_path, sssom_nor_path, nor_csv_sample_path
    )

    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    (shapes_dir / "permissive.shacl.ttl").write_text(_PERMISSIVE_SHAPE_TTL, encoding="utf-8")

    yarrrml_out = _compile_to_yarrrml(tmp_path, sssom, nor_schema, mc_schema)

    jsonld_out = tmp_path / "out.jsonld"
    workdir = tmp_path / "wd"

    result = CliRunner(mix_stderr=False).invoke(
        run_cli,
        [
            str(yarrrml_out),
            str(csv),
            "--master-schema",
            str(mc_schema),
            "-o",
            str(jsonld_out),
            "--shapes-dir",
            str(shapes_dir),
            "--workdir",
            str(workdir),
        ],
    )

    assert result.exit_code == 0, (
        f"expected exit 0 with permissive shape; got {result.exit_code}\n"
        f"stderr={result.stderr!r}\nexception={result.exception!r}"
    )
    assert jsonld_out.exists(), "JSON-LD output file was not written"
    payload = json.loads(jsonld_out.read_text(encoding="utf-8"))
    assert payload, "JSON-LD payload is empty"


@pytest.mark.slow
def test_yarrrml_run_validate_violation_blocks_emission(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`rosetta run --validate` with impossible shape: exit 1, no JSON-LD bytes."""
    nor_schema, mc_schema, sssom, csv = _copy_and_patch_schemas(
        tmp_path, nor_linkml_path, master_schema_path, sssom_nor_path, nor_csv_sample_path
    )

    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    (shapes_dir / "impossible.shacl.ttl").write_text(_IMPOSSIBLE_SHAPE_TTL, encoding="utf-8")

    yarrrml_out = _compile_to_yarrrml(tmp_path, sssom, nor_schema, mc_schema)

    jsonld_out = tmp_path / "out.jsonld"
    report_out = tmp_path / "validate-report.json"
    workdir = tmp_path / "wd"

    result = CliRunner(mix_stderr=False).invoke(
        run_cli,
        [
            str(yarrrml_out),
            str(csv),
            "--master-schema",
            str(mc_schema),
            "-o",
            str(jsonld_out),
            "--shapes-dir",
            str(shapes_dir),
            "--validate-report",
            str(report_out),
            "--workdir",
            str(workdir),
        ],
    )

    assert result.exit_code == 1, (
        f"expected exit 1 from SHACL violation; got {result.exit_code}\n"
        f"stderr={result.stderr!r}\nexception={result.exception!r}"
    )
    assert not jsonld_out.exists(), (
        f"JSON-LD output should not be written on validation failure; "
        f"file exists with {jsonld_out.stat().st_size if jsonld_out.exists() else 0} bytes"
    )
    assert report_out.exists(), "--validate-report file was not written"
    report = json.loads(report_out.read_text(encoding="utf-8"))
    assert report["summary"]["conforms"] is False
    assert report["summary"]["violation"] >= 1


# ---------------------------------------------------------------------------
# Post-review: compile+run → disk JSON-LD → rosetta validate chain
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_yarrrml_run_then_validate_jsonld_file_chain(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """Two-stage chain: compile+run writes JSON-LD to disk; rosetta validate reads it."""
    from rosetta.cli.validate import cli as validate_cli

    nor_schema, mc_schema, sssom, csv = _copy_and_patch_schemas(
        tmp_path, nor_linkml_path, master_schema_path, sssom_nor_path, nor_csv_sample_path
    )

    yarrrml_out = _compile_to_yarrrml(tmp_path, sssom, nor_schema, mc_schema)

    jsonld_out = tmp_path / "pipeline-out.jsonld"
    workdir = tmp_path / "wd"

    # Stage 1: materialize without inline --shapes-dir (write JSON-LD to disk).
    gen_result = CliRunner(mix_stderr=False).invoke(
        run_cli,
        [
            str(yarrrml_out),
            str(csv),
            "--master-schema",
            str(mc_schema),
            "-o",
            str(jsonld_out),
            "--workdir",
            str(workdir),
            "--no-validate",
        ],
    )
    assert gen_result.exit_code == 0, (
        f"run failed: exit={gen_result.exit_code} stderr={gen_result.stderr!r}"
    )
    assert jsonld_out.exists() and jsonld_out.stat().st_size > 0, "no JSON-LD bytes"

    # Stage 2: validate the JSON-LD against a permissive shape dir.
    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    (shapes_dir / "permissive.shacl.ttl").write_text(_PERMISSIVE_SHAPE_TTL, encoding="utf-8")
    report_out = tmp_path / "report.json"

    val_result = CliRunner(mix_stderr=False).invoke(
        validate_cli,
        [
            str(jsonld_out),
            str(shapes_dir),
            "--output",
            str(report_out),
        ],
    )
    assert val_result.exit_code == 0, (
        f"permissive shape should pass JSON-LD output; "
        f"exit={val_result.exit_code} stderr={val_result.stderr!r}"
    )
    report = json.loads(report_out.read_text(encoding="utf-8"))
    assert report["summary"]["conforms"] is True


@pytest.mark.slow
def test_yarrrml_run_validate_with_committed_policy_shapes(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`rosetta run --validate` with shapes generated from the master schema.

    Generates SHACL shapes via shacl-gen rather than relying on committed
    policy shapes (removed in 5e4cf92). Does NOT assert conformance because
    the closed-world shapes are stricter than the NOR sample data populates.
    """
    nor_schema, mc_schema, sssom, csv = _copy_and_patch_schemas(
        tmp_path, nor_linkml_path, master_schema_path, sssom_nor_path, nor_csv_sample_path
    )

    policy_shapes = tmp_path / "shapes"
    policy_shapes.mkdir()
    gen_result = CliRunner(mix_stderr=False).invoke(
        shacl_gen_cli, [str(mc_schema), "--output", str(policy_shapes / "shapes.ttl")]
    )
    assert gen_result.exit_code == 0, f"shacl-gen failed: {gen_result.stderr}"

    yarrrml_out = _compile_to_yarrrml(tmp_path, sssom, nor_schema, mc_schema)

    jsonld_out = tmp_path / "out.jsonld"
    report_out = tmp_path / "validate-report.json"
    workdir = tmp_path / "wd"

    result = CliRunner(mix_stderr=False).invoke(
        run_cli,
        [
            str(yarrrml_out),
            str(csv),
            "--master-schema",
            str(mc_schema),
            "-o",
            str(jsonld_out),
            "--shapes-dir",
            str(policy_shapes),
            "--validate-report",
            str(report_out),
            "--workdir",
            str(workdir),
        ],
    )

    assert result.exit_code in (0, 1), (
        f"unexpected exit {result.exit_code}; "
        f"stderr={result.stderr!r} exception={result.exception!r}"
    )
    assert report_out.exists(), "--validate-report not written"
    report = json.loads(report_out.read_text(encoding="utf-8"))
    assert "summary" in report and "conforms" in report["summary"]
    if result.exit_code == 1:
        assert not jsonld_out.exists() or jsonld_out.stat().st_size == 0, (
            "JSON-LD must not land on violation"
        )
