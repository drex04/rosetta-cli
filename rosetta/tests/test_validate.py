"""Tests for rosetta/cli/validate.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.validate import cli
from rosetta.core.models import ValidationReport

# Inline SHACL fixture (D-19-13): keeps the test self-contained and removes the
# legacy dependency on the retired v1 policies file. Modeled after the pattern
# in rosetta/tests/integration/test_validate_pipeline.py.
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

CONFORMANT_TTL = """\
@prefix ex:  <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:alice a ex:Person ;
    ex:age "30"^^xsd:integer .
"""

VIOLATING_TTL = """\
@prefix ex:  <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:bob a ex:Person ;
    ex:age "not-a-number"^^xsd:string .
"""

# Shape with minCount 1 but NO sh:message (tests that violations without
# sh:resultMessage are not silently dropped)
SHAPE_NO_MESSAGE_TTL = """\
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix ex:   <http://example.org/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

ex:PersonShapeNoMsg
    a sh:NodeShape ;
    sh:targetClass ex:Person ;
    sh:property [
        sh:path ex:age ;
        sh:minCount 1 ;
        sh:datatype xsd:integer ;
    ] .
"""


@pytest.fixture(scope="module")
def tmp_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    base: Path = tmp_path_factory.mktemp("validate_fixtures")

    shapes = base / "shapes.ttl"
    shapes.write_text(_SHAPES_TTL, encoding="utf-8")

    conformant = base / "conformant_data.ttl"
    conformant.write_text(CONFORMANT_TTL, encoding="utf-8")

    violating = base / "violating_data.ttl"
    violating.write_text(VIOLATING_TTL, encoding="utf-8")

    shape_no_msg = base / "shape_no_message.ttl"
    shape_no_msg.write_text(SHAPE_NO_MESSAGE_TTL, encoding="utf-8")

    # shapes-dir with the inline shapes file
    shapes_dir = base / "shapes_dir"
    shapes_dir.mkdir()
    (shapes_dir / "shapes.ttl").write_text(_SHAPES_TTL, encoding="utf-8")

    # empty shapes-dir for UsageError test
    empty_shapes_dir = base / "empty_shapes_dir"
    empty_shapes_dir.mkdir()

    return {
        "shapes": shapes,
        "conformant": conformant,
        "violating": violating,
        "shape_no_msg": shape_no_msg,
        "shapes_dir": shapes_dir,
        "empty_shapes_dir": empty_shapes_dir,
        "base": base,
    }


def test_validate_conformant(tmp_files: dict[str, Path]) -> None:
    result = CliRunner().invoke(
        cli,
        ["--data", str(tmp_files["conformant"]), "--shapes", str(tmp_files["shapes"])],
    )
    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["summary"]["conforms"] is True
    assert report["findings"] == []


def test_validate_violation(tmp_files: dict[str, Path]) -> None:
    result = CliRunner().invoke(
        cli,
        ["--data", str(tmp_files["violating"]), "--shapes", str(tmp_files["shapes"])],
    )
    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["summary"]["conforms"] is False
    assert len(report["findings"]) >= 1
    assert report["findings"][0]["severity"] == "Violation"


def test_validate_missing_shapes_arg(tmp_files: dict[str, Path]) -> None:
    result = CliRunner().invoke(cli, ["--data", str(tmp_files["conformant"])])
    assert result.exit_code != 0


def test_validate_shapes_dir(tmp_files: dict[str, Path]) -> None:
    result = CliRunner().invoke(
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
    result = CliRunner().invoke(
        cli,
        [
            "--data",
            str(tmp_files["conformant"]),
            "--shapes",
            str(tmp_files["shapes"]),
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
    result = CliRunner().invoke(
        cli,
        ["--data", str(tmp_files["violating"]), "--shapes", str(tmp_files["shapes"])],
    )
    assert result.exit_code == 1
    data = json.loads(result.output)
    report = ValidationReport.model_validate(data)
    assert isinstance(report, ValidationReport)


def test_validate_finding_fields(tmp_files: dict[str, Path]) -> None:
    result = CliRunner().invoke(
        cli,
        ["--data", str(tmp_files["violating"]), "--shapes", str(tmp_files["shapes"])],
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
    result = CliRunner().invoke(
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
    result = CliRunner().invoke(
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


# ---------------------------------------------------------------------------
# Plan 19-03 Task 4 — JSON-LD input + --data-format wiring tests
# ---------------------------------------------------------------------------

# Conformant data expressed as JSON-LD (matches the ex:PersonShape constraint:
# ex:Person with ex:age xsd:integer, minCount 1).
_CONFORMANT_JSONLD = """\
{
  "@context": {
    "ex": "http://example.org/",
    "xsd": "http://www.w3.org/2001/XMLSchema#"
  },
  "@id": "ex:alice",
  "@type": "ex:Person",
  "ex:age": {"@value": "30", "@type": "xsd:integer"}
}
"""


def test_validate_jsonld_input_autodetect(tmp_files: dict[str, Path], tmp_path: Path) -> None:
    """`.jsonld` suffix triggers JSON-LD parsing under default --data-format=auto."""
    data = tmp_path / "person.jsonld"
    data.write_text(_CONFORMANT_JSONLD, encoding="utf-8")
    out = tmp_path / "report.json"

    result = CliRunner().invoke(
        cli,
        [
            "--data",
            str(data),
            "--shapes",
            str(tmp_files["shapes"]),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"unexpected exit; stderr/output={result.output!r}"
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["summary"]["conforms"] is True


def test_validate_json_input_autodetect(tmp_files: dict[str, Path], tmp_path: Path) -> None:
    """`.json` suffix is treated as JSON-LD by the auto-resolver."""
    data = tmp_path / "person.json"
    data.write_text(_CONFORMANT_JSONLD, encoding="utf-8")
    out = tmp_path / "report.json"

    result = CliRunner().invoke(
        cli,
        [
            "--data",
            str(data),
            "--shapes",
            str(tmp_files["shapes"]),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"unexpected exit; stderr/output={result.output!r}"
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["summary"]["conforms"] is True


def test_validate_data_format_override(tmp_files: dict[str, Path], tmp_path: Path) -> None:
    """`--data-format json-ld` forces JSON-LD parsing despite a non-matching suffix."""
    data = tmp_path / "person.txt"
    data.write_text(_CONFORMANT_JSONLD, encoding="utf-8")
    out = tmp_path / "report.json"

    result = CliRunner().invoke(
        cli,
        [
            "--data",
            str(data),
            "--data-format",
            "json-ld",
            "--shapes",
            str(tmp_files["shapes"]),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"unexpected exit; stderr/output={result.output!r}"


def test_validate_data_format_unknown_raises(tmp_files: dict[str, Path]) -> None:
    """Click's `Choice` rejects unknown formats with usage-error exit code 2."""
    result = CliRunner().invoke(
        cli,
        [
            "--data",
            str(tmp_files["conformant"]),
            "--data-format",
            "xml",
            "--shapes",
            str(tmp_files["shapes"]),
        ],
    )
    assert result.exit_code == 2, (
        f"expected Click Choice-violation exit 2; got {result.exit_code}: {result.output!r}"
    )


def test_validate_hyphenated_jsonld_suffix_autodetect(
    tmp_files: dict[str, Path], tmp_path: Path
) -> None:
    """`.json-ld` (hyphenated) is an accepted variant alongside `.jsonld` / `.json`.

    Pins the suffix list in ``_resolve_data_format`` so a future edit cannot
    silently drop the hyphen form.
    """
    data = tmp_path / "person.json-ld"
    data.write_text(_CONFORMANT_JSONLD, encoding="utf-8")
    out = tmp_path / "report.json"
    result = CliRunner().invoke(
        cli,
        [
            "--data",
            str(data),
            "--shapes",
            str(tmp_files["shapes"]),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"unexpected exit; output={result.output!r}"
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["summary"]["conforms"] is True


def test_validate_jsonld_missing_context_surfaces_clean_error(
    tmp_files: dict[str, Path], tmp_path: Path
) -> None:
    """JSON-LD lacking an ``@context`` either parses as an empty graph (producing
    a conformant report because no triples → no violations) *or* surfaces a
    non-zero exit with a clear error — what it must NOT do is hang on a network
    fetch or crash with an unattributed traceback."""
    data = tmp_path / "no_context.jsonld"
    data.write_text(
        '{"@id": "http://example.org/alice", "@type": "http://example.org/Person"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    result = CliRunner().invoke(
        cli,
        [
            "--data",
            str(data),
            "--shapes",
            str(tmp_files["shapes"]),
            "--output",
            str(out),
        ],
    )
    # Acceptable outcomes: exit 0 (empty/unresolved graph) or exit 1 (clean
    # rdflib/jsonld error surfaced as "Error: ..."). Any other exit suggests
    # an unhandled traceback.
    assert result.exit_code in (0, 1), (
        f"unexpected exit {result.exit_code}; output={result.output!r}"
    )
