"""Tests for rosetta/cli/validate.py."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.validate import cli
from rosetta.core.models import ValidationReport

SHAPES_FILE = Path(__file__).parent.parent / "policies" / "mapping.shacl.ttl"

CONFORMANT_TTL = """\
@prefix rose: <http://rosetta.interop/ns/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
<http://example.org/f1> a rose:Field ;
    rdfs:label "Field One"^^xsd:string ;
    rose:dataType xsd:integer .
"""

VIOLATING_TTL = """\
@prefix rose: <http://rosetta.interop/ns/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
<http://example.org/f2> a rose:Field ;
    rose:dataType xsd:integer .
"""

# Shape with minCount 1 but NO sh:message (tests that violations without
# sh:resultMessage are not silently dropped)
SHAPE_NO_MESSAGE_TTL = """\
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix rose: <http://rosetta.interop/ns/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
rose:FieldShapeNoMsg
    a sh:NodeShape ;
    sh:targetClass rose:Field ;
    sh:property [
        sh:path rdfs:label ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] .
"""


@pytest.fixture(scope="module")
def tmp_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    base: Path = tmp_path_factory.mktemp("validate_fixtures")

    conformant = base / "conformant_data.ttl"
    conformant.write_text(CONFORMANT_TTL, encoding="utf-8")

    violating = base / "violating_data.ttl"
    violating.write_text(VIOLATING_TTL, encoding="utf-8")

    shape_no_msg = base / "shape_no_message.ttl"
    shape_no_msg.write_text(SHAPE_NO_MESSAGE_TTL, encoding="utf-8")

    # shapes-dir with a copy of the main shapes file
    shapes_dir = base / "shapes_dir"
    shapes_dir.mkdir()
    shutil.copy(SHAPES_FILE, shapes_dir / "mapping.shacl.ttl")

    # empty shapes-dir for UsageError test
    empty_shapes_dir = base / "empty_shapes_dir"
    empty_shapes_dir.mkdir()

    return {
        "conformant": conformant,
        "violating": violating,
        "shape_no_msg": shape_no_msg,
        "shapes_dir": shapes_dir,
        "empty_shapes_dir": empty_shapes_dir,
        "base": base,
    }


def test_validate_conformant(tmp_files: dict[str, Path]) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--data", str(tmp_files["conformant"]), "--shapes", str(SHAPES_FILE)],
    )
    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["summary"]["conforms"] is True
    assert report["findings"] == []


def test_validate_violation(tmp_files: dict[str, Path]) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--data", str(tmp_files["violating"]), "--shapes", str(SHAPES_FILE)],
    )
    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["summary"]["conforms"] is False
    assert len(report["findings"]) >= 1
    assert report["findings"][0]["severity"] == "Violation"


def test_validate_missing_shapes_arg(tmp_files: dict[str, Path]) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--data", str(tmp_files["conformant"])])
    assert result.exit_code != 0


def test_validate_shapes_dir(tmp_files: dict[str, Path]) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--data",
            str(tmp_files["violating"]),
            "--shapes-dir",
            str(tmp_files["shapes_dir"]),
        ],
    )
    assert result.exit_code == 1
    report = json.loads(result.output)
    assert len(report["findings"]) >= 1


def test_validate_output_file(tmp_files: dict[str, Path]) -> None:
    out_file = tmp_files["base"] / "report.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--data",
            str(tmp_files["conformant"]),
            "--shapes",
            str(SHAPES_FILE),
            "--output",
            str(out_file),
        ],
    )
    assert result.exit_code == 0
    assert result.output.strip() == ""
    assert out_file.exists()
    report = json.loads(out_file.read_text())
    assert "summary" in report


def test_validate_report_schema(tmp_files: dict[str, Path]) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--data", str(tmp_files["violating"]), "--shapes", str(SHAPES_FILE)],
    )
    assert result.exit_code == 1
    data = json.loads(result.output)
    report = ValidationReport.model_validate(data)
    assert isinstance(report, ValidationReport)


def test_validate_finding_fields(tmp_files: dict[str, Path]) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--data", str(tmp_files["violating"]), "--shapes", str(SHAPES_FILE)],
    )
    assert result.exit_code == 1
    report = json.loads(result.output)
    finding = report["findings"][0]
    assert "focus_node" in finding
    assert "severity" in finding
    assert "constraint" in finding
    assert finding["focus_node"] != ""
    assert finding["constraint"] != ""


def test_validate_shapes_dir_empty(tmp_files: dict[str, Path]) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--data",
            str(tmp_files["conformant"]),
            "--shapes-dir",
            str(tmp_files["empty_shapes_dir"]),
        ],
    )
    assert result.exit_code != 0


def test_validate_finding_message_none(tmp_files: dict[str, Path]) -> None:
    """A shape without sh:message must produce a finding — the OPTIONAL SPARQL clause
    must not silently drop violations. pySHACL auto-generates sh:resultMessage even
    when sh:message is absent, so message is a string here; the model supports None
    for implementations that truly omit sh:resultMessage."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--data",
            str(tmp_files["violating"]),
            "--shapes",
            str(tmp_files["shape_no_msg"]),
        ],
    )
    assert result.exit_code == 1
    report = json.loads(result.output)
    assert len(report["findings"]) >= 1
    # Violation must be present (not dropped by OPTIONAL sh:resultMessage binding)
    finding = report["findings"][0]
    assert "message" in finding  # field exists; may be str or None per model
