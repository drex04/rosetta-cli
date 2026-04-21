"""Integration tests for the ``rosetta shacl-gen → rosetta validate`` chain.

Phase 19 review follow-up: the 130KB generated ``master.shacl.ttl`` was
committed but never exercised as a live ``--shapes`` / ``--shapes-dir`` target
against realistic data in an end-to-end test. These tests close that gap by
driving the CLI boundary of both tools and round-tripping real Turtle.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.shacl_gen import cli as shacl_gen_cli
from rosetta.cli.validate import cli as validate_cli
from rosetta.core.models import ValidationReport

pytestmark = [pytest.mark.integration]


_CONFORMANT_TRACK_JSONLD = """\
{
  "@context": {
    "mc": "https://ontology.nato.int/core/MasterCOP#"
  },
  "@id": "mc:track-1",
  "@type": "mc:AirTrack"
}
"""


def test_shacl_gen_output_consumed_by_validate_single_file(
    master_schema_path: Path, tmp_path: Path
) -> None:
    """`shacl-gen` writes shapes → `validate` consumes them via shapes dir.

    Confirms the generated Turtle is not just parseable in isolation but
    also round-trips through the validate CLI as a shapes-dir input.
    """
    shapes_dir = tmp_path / "shapes"
    shapes_dir.mkdir()
    shapes_out = shapes_dir / "master.shacl.ttl"

    gen_result = CliRunner(mix_stderr=False).invoke(
        shacl_gen_cli,
        [str(master_schema_path), "--output", str(shapes_out)],
    )
    assert gen_result.exit_code == 0, (
        f"shacl-gen failed: {gen_result.exit_code}; stderr={gen_result.stderr!r}"
    )
    assert shapes_out.exists()
    assert shapes_out.stat().st_size > 1000, "generated shapes file implausibly small"

    data = tmp_path / "track.jsonld"
    data.write_text(_CONFORMANT_TRACK_JSONLD, encoding="utf-8")
    report_out = tmp_path / "report.json"

    val_result = CliRunner(mix_stderr=False).invoke(
        validate_cli,
        [
            str(data),
            str(shapes_dir),
            "--output",
            str(report_out),
        ],
    )
    assert val_result.exit_code == 0, (
        f"conformant data should pass generated shapes; "
        f"exit={val_result.exit_code} stderr={val_result.stderr!r} "
        f"report={report_out.read_text(encoding='utf-8') if report_out.exists() else '<no report>'}"
    )
    report = ValidationReport.model_validate_json(report_out.read_text(encoding="utf-8"))
    assert report.summary.conforms is True
    assert report.summary.violation == 0


def test_shacl_gen_output_consumed_by_validate_shapes_dir(
    master_schema_path: Path, tmp_path: Path
) -> None:
    """`shacl-gen` writes into a directory; `validate --shapes-dir` walks it.

    Mirrors the canonical production layout (``rosetta/policies/shacl/``) —
    generated shapes under one subdir, potentially user overrides beside
    them — and proves the recursive walker works end-to-end off freshly
    generated shapes.
    """
    shapes_dir = tmp_path / "shapes"
    generated = shapes_dir / "generated"
    generated.mkdir(parents=True)

    gen_result = CliRunner(mix_stderr=False).invoke(
        shacl_gen_cli,
        [
            str(master_schema_path),
            "--output",
            str(generated / "master.shacl.ttl"),
        ],
    )
    assert gen_result.exit_code == 0, f"shacl-gen failed: {gen_result.stderr!r}"

    data = tmp_path / "track.jsonld"
    data.write_text(_CONFORMANT_TRACK_JSONLD, encoding="utf-8")
    report_out = tmp_path / "report.json"

    val_result = CliRunner(mix_stderr=False).invoke(
        validate_cli,
        [
            str(data),
            str(shapes_dir),
            "--output",
            str(report_out),
        ],
    )
    assert val_result.exit_code == 0, (
        f"conformant data should pass generated shapes; "
        f"exit={val_result.exit_code} stderr={val_result.stderr!r}"
    )
    report = ValidationReport.model_validate_json(report_out.read_text(encoding="utf-8"))
    assert report.summary.conforms is True
