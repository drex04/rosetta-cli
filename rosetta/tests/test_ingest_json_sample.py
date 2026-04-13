"""Tests for the JSON sample input mode of rosetta-ingest."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import URIRef

from rosetta.cli.ingest import cli as ingest
from rosetta.core.ingest_rdf import ROSE_HAS_CHILD, fields_to_graph
from rosetta.core.parsers import dispatch_parser
from rosetta.core.parsers.json_sample_parser import parse_json_sample

FIXTURE = Path(__file__).parent / "fixtures" / "deu_patriot_sample.json"


def test_json_sample_envelope() -> None:
    """Single-key envelope is unwrapped; top-level array key not present as a field."""
    with FIXTURE.open() as f:
        fields, slug = parse_json_sample(f, FIXTURE, "DEU")

    names = {field.name for field in fields}
    assert "erkannte_ziele" not in names
    assert "geschwindigkeit_kmh" in names
    assert "kurs_grad" in names
    assert "position" in names
    assert "identifikation" in names
    assert slug == "deu_patriot_sample"


def test_json_sample_nesting() -> None:
    """Nested objects produce children with correct types and unit detection."""
    with FIXTURE.open() as f:
        fields, _ = parse_json_sample(f, FIXTURE, "DEU")

    position = next(field for field in fields if field.name == "position")
    assert position.data_type == "object"
    child_names = {c.name for c in position.children}
    assert "hoehe_m" in child_names

    hoehe = next(c for c in position.children if c.name == "hoehe_m")
    assert hoehe.detected_unit == "meter"
    assert hoehe.numeric_stats is not None


def test_json_sample_has_child_in_turtle() -> None:
    """fields_to_graph emits rose:hasChild triple for nested object fields."""
    with FIXTURE.open() as f:
        fields, slug = parse_json_sample(f, FIXTURE, "DEU")

    g = fields_to_graph(fields, "DEU", slug)
    F = "http://rosetta.interop/field/DEU/deu_patriot_sample/"
    assert (URIRef(F + "position"), ROSE_HAS_CHILD, URIRef(F + "position__hoehe_m")) in g


def test_json_sample_unit_detection() -> None:
    """Unit detection resolves _kmh and _grad suffixes correctly."""
    with FIXTURE.open() as f:
        fields, _ = parse_json_sample(f, FIXTURE, "DEU")

    geschw = next(field for field in fields if field.name == "geschwindigkeit_kmh")
    kurs = next(field for field in fields if field.name == "kurs_grad")
    assert geschw.detected_unit == "km_per_hour"
    assert kurs.detected_unit == "degree"


def test_json_sample_stats_populated() -> None:
    """Numeric stats are computed correctly from sample values."""
    with FIXTURE.open() as f:
        fields, _ = parse_json_sample(f, FIXTURE, "DEU")

    geschw = next(field for field in fields if field.name == "geschwindigkeit_kmh")
    assert geschw.numeric_stats is not None
    assert geschw.numeric_stats["count"] == 5
    assert geschw.numeric_stats["min"] == 222.0
    assert geschw.numeric_stats["max"] == 926.0


def test_json_sample_direct_array() -> None:
    """Top-level array of objects is parsed directly without envelope unwrapping."""
    src = io.StringIO('[{"speed_kts": 400, "alt_ft": 1000}]')
    fields, _ = parse_json_sample(src, None, "TST")

    names = {f.name for f in fields}
    assert "speed_kts" in names
    assert "alt_ft" in names

    speed = next(f for f in fields if f.name == "speed_kts")
    alt = next(f for f in fields if f.name == "alt_ft")
    assert speed.detected_unit == "knot"
    assert alt.detected_unit == "foot"


def test_json_sample_single_flat_object() -> None:
    """Flat JSON object (not wrapped in array) is parsed as a single-row sample."""
    src = io.StringIO('{"speed_kts": 400}')
    fields, _ = parse_json_sample(src, None, "TST")

    assert len(fields) == 1
    assert fields[0].detected_unit == "knot"


def test_json_sample_empty_array_raises() -> None:
    """Empty array raises ValueError mentioning 'no fields'."""
    src = io.StringIO("[]")
    with pytest.raises(ValueError, match="no fields"):
        parse_json_sample(src, None, "TST")


def test_json_sample_non_object_array_raises() -> None:
    """Array of non-objects raises ValueError mentioning 'no fields'."""
    src = io.StringIO("[1, 2, 3]")
    with pytest.raises(ValueError, match="no fields"):
        parse_json_sample(src, None, "TST")


def test_json_sample_stdin_slug() -> None:
    """When path is None, slug defaults to 'sample'."""
    src = io.StringIO('[{"x": 1}]')
    _, slug = parse_json_sample(src, None, "TST")
    assert slug == "sample"


def test_json_sample_no_auto_detect() -> None:
    """dispatch_parser routes .json extension to json-schema, not json-sample."""
    src = io.StringIO("{}")
    try:
        dispatch_parser(src, Path("data.json"), None, "DEU")
    except ValueError as exc:
        msg = str(exc)
        assert "json-sample" not in msg
        assert "Unknown" not in msg


def test_json_sample_cli_roundtrip() -> None:
    """CLI roundtrip with --input-format json-sample produces valid Turtle with rose:hasChild."""
    runner = CliRunner()
    result = runner.invoke(
        ingest,
        ["--input", str(FIXTURE), "--nation", "DEU", "--input-format", "json-sample"],
    )
    assert result.exit_code == 0, result.output
    assert "rose:hasChild" in result.output


def test_json_sample_empty_object_raises() -> None:
    """Empty object raises ValueError mentioning 'no fields'."""
    src = io.StringIO("{}")
    with pytest.raises(ValueError, match="no fields"):
        parse_json_sample(src, None, "TST")


def test_json_sample_malformed_json_raises() -> None:
    """Malformed JSON raises ValueError (not raw JSONDecodeError) from parser and CLI."""
    src = io.StringIO("not json")
    with pytest.raises(ValueError):
        parse_json_sample(src, None, "TST")

    runner = CliRunner()
    with runner.isolated_filesystem():
        bad = Path("bad.json")
        bad.write_text("not json")
        result = runner.invoke(
            ingest, ["--input", "bad.json", "--nation", "TST", "--input-format", "json-sample"]
        )
    assert result.exit_code == 1


def test_json_sample_max_depth_truncates() -> None:
    """11-level nested dict is truncated at depth 10; deepest field has no children."""
    nested: dict[str, object] = {}
    current = nested
    for _ in range(11):
        current["child"] = {}
        current = current["child"]

    src = io.StringIO(json.dumps([nested]))
    fields, _ = parse_json_sample(src, None, "TST")

    # Walk down through children 10 levels; the 10th-level field has data_type "object"
    # but children=[] because recursion was blocked at max_depth=10.
    node = fields
    for level in range(10):
        assert len(node) > 0, f"Expected node at level {level}"
        assert node[0].data_type == "object", f"Expected object at level {level}"
        node = node[0].children

    # node is now the children list of the field at depth=10
    assert len(node) == 1
    assert node[0].data_type == "object"
    assert node[0].children == []


def test_json_sample_multi_key_envelope() -> None:
    """Dict with multiple list-valued keys produces both as container fields with children."""
    data = {"targets": [{"speed_kts": 400}], "metadata": [{"version": "1.0"}]}
    src = io.StringIO(json.dumps(data))
    fields, _ = parse_json_sample(src, None, "TST")

    names = {f.name for f in fields}
    assert "targets" in names
    assert "metadata" in names

    targets = next(f for f in fields if f.name == "targets")
    metadata = next(f for f in fields if f.name == "metadata")
    assert targets.data_type == "object"
    assert targets.children != []
    assert metadata.data_type == "object"
    assert metadata.children != []
