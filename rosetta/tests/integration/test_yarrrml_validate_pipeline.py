"""Integration tests for `rosetta-yarrrml-gen --run --validate` (Plan 19-03 Task 4).

These walk the full chain:

    SSSOM audit log → TransformSpec → YARRRML → morph-kgc graph → SHACL validate
                                                                  → JSON-LD (only on conform)

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

from rosetta.cli.yarrrml_gen import cli as yarrrml_gen_cli

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
    """Copy fixtures to ``dst_dir`` and patch the LinkML ``dateTime`` typo.

    The master_cop fixture uses ``range: dateTime`` (capital T) which
    ``ContextGenerator`` rejects. The materialization step is unrelated to
    the validate-flag truths under test, so patch it the same way the
    existing e2e does.
    """
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


# Permissive shape: matches every materialized triple's expected
# subject-class (mc:Track) but adds no minCount constraints — so the data
# trivially conforms and JSON-LD emission proceeds.
_PERMISSIVE_SHAPE_TTL = """\
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix mc: <https://ontology.nato.int/core/MasterCOP#> .

mc:TrackPermissiveShape a sh:NodeShape ;
    sh:targetClass mc:Track .
"""

# Impossible shape: every mc:Track must declare mc:hasMode5 — the NOR data
# never provides such a slot, so every track instance violates this shape.
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
    """`--run --validate` with a permissive shape: exit 0, JSON-LD written.

    Confirms the validate flag does not block emission when the materialized
    graph satisfies the shapes.
    """
    nor_schema, mc_schema, sssom, csv = _copy_and_patch_schemas(
        tmp_path, nor_linkml_path, master_schema_path, sssom_nor_path, nor_csv_sample_path
    )

    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    (shapes_dir / "permissive.shacl.ttl").write_text(_PERMISSIVE_SHAPE_TTL, encoding="utf-8")

    spec_out = tmp_path / "spec.transform.yaml"
    jsonld_out = tmp_path / "out.jsonld"
    workdir = tmp_path / "wd"

    result = CliRunner(mix_stderr=False).invoke(
        yarrrml_gen_cli,
        [
            "--sssom",
            str(sssom),
            "--source-schema",
            str(nor_schema),
            "--master-schema",
            str(mc_schema),
            "--output",
            str(spec_out),
            "--force",
            "--run",
            "--data",
            str(csv),
            "--jsonld-output",
            str(jsonld_out),
            "--validate",
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
    # JSON-LD payload landed on disk.
    assert jsonld_out.exists(), "JSON-LD output file was not written"
    payload = json.loads(jsonld_out.read_text(encoding="utf-8"))
    assert payload, "JSON-LD payload is empty"
    # TransformSpec YAML also landed (--output target).
    assert spec_out.exists(), "TransformSpec YAML was not written"


@pytest.mark.slow
def test_yarrrml_run_validate_violation_blocks_emission(
    tmp_path: Path,
    nor_linkml_path: Path,
    master_schema_path: Path,
    sssom_nor_path: Path,
    nor_csv_sample_path: Path,
) -> None:
    """`--run --validate` with an impossible shape: exit 1, no JSON-LD bytes.

    Confirms (a) the CLI surfaces a non-zero exit, (b) the JSON-LD output
    file is NOT created, (c) the validation report is written to the path
    specified by --validate-report and reports >=1 violation.
    """
    nor_schema, mc_schema, sssom, csv = _copy_and_patch_schemas(
        tmp_path, nor_linkml_path, master_schema_path, sssom_nor_path, nor_csv_sample_path
    )

    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    (shapes_dir / "impossible.shacl.ttl").write_text(_IMPOSSIBLE_SHAPE_TTL, encoding="utf-8")

    spec_out = tmp_path / "spec.transform.yaml"
    jsonld_out = tmp_path / "out.jsonld"
    report_out = tmp_path / "validate-report.json"
    workdir = tmp_path / "wd"

    result = CliRunner(mix_stderr=False).invoke(
        yarrrml_gen_cli,
        [
            "--sssom",
            str(sssom),
            "--source-schema",
            str(nor_schema),
            "--master-schema",
            str(mc_schema),
            "--output",
            str(spec_out),
            "--force",
            "--run",
            "--data",
            str(csv),
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

    # 1. Exit code: SHACL violation aborts the pipeline.
    assert result.exit_code == 1, (
        f"expected exit 1 from SHACL violation; got {result.exit_code}\n"
        f"stderr={result.stderr!r}\nexception={result.exception!r}"
    )

    # 2. No JSON-LD bytes were written — emission was blocked before the
    #    --jsonld-output target was opened.
    assert not jsonld_out.exists(), (
        f"JSON-LD output should not be written on validation failure; "
        f"file exists with {jsonld_out.stat().st_size} bytes"
    )

    # 3. Validation report exists and reports >=1 violation.
    assert report_out.exists(), "--validate-report file was not written"
    report = json.loads(report_out.read_text(encoding="utf-8"))
    assert report["summary"]["conforms"] is False, (
        f"expected conforms=False in report; got {report['summary']!r}"
    )
    assert report["summary"]["violation"] >= 1, (
        f"expected >=1 violation in report; got {report['summary']!r}"
    )
