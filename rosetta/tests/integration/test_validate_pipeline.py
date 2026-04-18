"""Integration tests for rosetta-validate (Phase 18-02, Task 3.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.validate import cli as validate_cli
from rosetta.core.models import ValidationReport

pytestmark = [pytest.mark.integration]


_SHAPES_TTL = """\
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix ex:   <http://example.org/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

ex:PersonShape a sh:NodeShape ;
    sh:targetClass ex:Person ;
    sh:property [
        sh:path ex:age ;
        sh:datatype xsd:integer ;
        sh:minCount 1 ;
    ] .
"""


_CONFORMANT_TTL = """\
@prefix ex:  <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:alice a ex:Person ;
    ex:age "30"^^xsd:integer .
"""


_VIOLATING_TTL = """\
@prefix ex:  <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:bob a ex:Person ;
    ex:age "not-a-number"^^xsd:string .
"""


def test_validate_accredited_output(tmp_path: Path) -> None:
    """Happy path conforms (exit 0); violating data flags ≥1 violation (exit 1)."""
    shapes = tmp_path / "shapes.ttl"
    shapes.write_text(_SHAPES_TTL, encoding="utf-8")

    # --- happy path ---
    ok_data = tmp_path / "ok.ttl"
    ok_data.write_text(_CONFORMANT_TTL, encoding="utf-8")
    ok_out = tmp_path / "ok-report.json"

    ok_result = CliRunner(mix_stderr=False).invoke(
        validate_cli,
        [
            "--data",
            str(ok_data),
            "--shapes",
            str(shapes),
            "--output",
            str(ok_out),
        ],
    )
    assert ok_result.exit_code == 0, f"expected conforming data to exit 0: {ok_result.stderr}"

    ok_report = ValidationReport.model_validate_json(ok_out.read_text(encoding="utf-8"))
    assert ok_report.summary.conforms is True
    assert ok_report.summary.violation == 0

    # --- violating path ---
    bad_data = tmp_path / "bad.ttl"
    bad_data.write_text(_VIOLATING_TTL, encoding="utf-8")
    bad_out = tmp_path / "bad-report.json"

    bad_result = CliRunner(mix_stderr=False).invoke(
        validate_cli,
        [
            "--data",
            str(bad_data),
            "--shapes",
            str(shapes),
            "--output",
            str(bad_out),
        ],
    )
    assert bad_result.exit_code == 1, f"expected violating data to exit 1: {bad_result.stderr}"

    bad_report_json = json.loads(bad_out.read_text(encoding="utf-8"))
    bad_report = ValidationReport.model_validate(bad_report_json)
    assert bad_report.summary.conforms is False
    # Behavioural invariant: at least one recorded finding at Violation severity.
    assert bad_report.summary.violation >= 1
    assert any(f.severity == "Violation" for f in bad_report.findings)
