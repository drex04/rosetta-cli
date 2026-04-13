"""Integration tests for rosetta-ingest CLI and supporting functions."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Graph, Namespace, URIRef

from rosetta.cli.accredit import cli as accredit_cli
from rosetta.cli.ingest import cli
from rosetta.cli.provenance import cli as provenance_cli
from rosetta.cli.rml_gen import cli as rml_gen_cli
from rosetta.cli.validate import cli as validate_cli
from rosetta.core.ingest_rdf import fields_to_graph
from rosetta.core.parsers import FieldSchema, dispatch_parser, schema_slug
from rosetta.core.parsers.json_schema_parser import parse_json_schema
from rosetta.core.parsers.openapi_parser import parse_openapi
from rosetta.core.unit_detect import compute_stats, detect_unit

ROSE = Namespace("http://rosetta.interop/ns/")
FIXTURES = Path(__file__).parent / "fixtures"


def test_ingest_csv():
    """Invoke CLI with nor_radar.csv --nation NOR; assert 11 rose:Field triples + stats + unit."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--input", str(FIXTURES / "nor_radar.csv"), "--nation", "NOR"])
    assert result.exit_code == 0, result.output
    g = Graph()
    g.parse(data=result.output, format="turtle")

    from rdflib.namespace import RDF

    field_subjects = list(g.subjects(RDF.type, ROSE.Field))
    assert len(field_subjects) == 11

    # hoyde_m has rose:stats
    hoyde_uri = URIRef("http://rosetta.interop/field/NOR/nor_radar/hoyde_m")
    stats_nodes = list(g.objects(hoyde_uri, ROSE.stats))
    assert len(stats_nodes) == 1

    # hoyde_m has rose:detectedUnit "meter"
    detected_units = list(g.objects(hoyde_uri, ROSE.detectedUnit))
    assert len(detected_units) == 1
    assert str(detected_units[0]) == "meter"


def test_ingest_json_schema():
    """Invoke CLI with deu_patriot.json --nation DEU.

    Assert 9 rose:Field triples + stats on Hoehe_Meter.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["--input", str(FIXTURES / "deu_patriot.json"), "--nation", "DEU"])
    assert result.exit_code == 0, result.output
    g = Graph()
    g.parse(data=result.output, format="turtle")

    from rdflib.namespace import RDF

    field_subjects = list(g.subjects(RDF.type, ROSE.Field))
    assert len(field_subjects) == 9

    # Hoehe_Meter field has rose:stats
    hoehe_uri = URIRef("http://rosetta.interop/field/DEU/deu_patriot/Hoehe_Meter")
    stats_nodes = list(g.objects(hoehe_uri, ROSE.stats))
    assert len(stats_nodes) == 1


def test_ingest_openapi():
    """Invoke CLI with usa_c2.yaml --nation USA.

    Assert 9 rose:Field triples + altitude_ft detectedUnit foot.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["--input", str(FIXTURES / "usa_c2.yaml"), "--nation", "USA"])
    assert result.exit_code == 0, result.output
    g = Graph()
    g.parse(data=result.output, format="turtle")

    from rdflib.namespace import RDF

    field_subjects = list(g.subjects(RDF.type, ROSE.Field))
    assert len(field_subjects) == 9

    # altitude_ft has rose:detectedUnit "foot"
    alt_uri = URIRef("http://rosetta.interop/field/USA/usa_c2/altitude_ft")
    detected_units = list(g.objects(alt_uri, ROSE.detectedUnit))
    assert len(detected_units) == 1
    assert str(detected_units[0]) == "foot"


@pytest.mark.parametrize(
    "name,desc,expected",
    [
        ("hoyde_m", "", "meter"),
        ("speed_kts", "", "knot"),
        ("hastighet_kmh", "", "km_per_hour"),
        ("altitude_ft", "", "foot"),
        ("dist_km", "", "kilometer"),
        ("track_id", "", None),
    ],
)
def test_unit_detect(name, desc, expected):
    """Parametrized unit detection checks."""
    assert detect_unit(name, desc) == expected


def test_schema_slug():
    """schema_slug converts titles to lowercase URL-safe slugs."""
    assert schema_slug("NOR Radar/Track") == "nor_radar_track"


def test_openapi_external_ref_raises():
    """parse_openapi raises ValueError with 'External $ref' for external $ref in schema."""
    yaml_str = """
openapi: "3.0.3"
info:
  title: Test API
  version: "1.0"
components:
  schemas:
    Foo:
      type: object
      properties:
        bar:
          $ref: "./other.json#/Foo"
"""
    src = io.StringIO(yaml_str)
    with pytest.raises(ValueError, match="External \\$ref"):
        parse_openapi(src, None, "TST")


def test_ingest_error_exit():
    """CLI exits with code 1 and a descriptive error message when input file does not exist."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--input", "/nonexistent/path/file.csv", "--nation", "NOR"])
    assert result.exit_code == 1
    assert "nonexistent" in result.stderr or "No such file" in result.stderr


def test_ingest_no_sample_data():
    """fields_to_graph emits no rose:stats triple for a field with no sample values."""
    fields = [
        FieldSchema(
            name="empty_field",
            data_type="string",
            description="",
            required=False,
            detected_unit=None,
            sample_values=[],
            numeric_stats=None,
            categorical_stats=None,
        )
    ]
    g = fields_to_graph(fields, "NOR", "test")
    subject = URIRef("http://rosetta.interop/field/NOR/test/empty_field")
    assert (subject, ROSE.stats, None) not in g


def test_json_schema_no_examples():
    """parse_json_schema succeeds on a schema with no top-level examples.

    All fields should have no stats.
    """
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Test Schema",
        "type": "object",
        "properties": {
            "field_a": {"type": "string"},
            "field_b": {"type": "number"},
        },
    }
    src = io.StringIO(json.dumps(schema))
    fields, slug = parse_json_schema(src, None, "TST")
    assert len(fields) == 2
    for f in fields:
        assert f.numeric_stats is None
        assert f.categorical_stats is None


def test_stdin_missing_format():
    """CLI exits with code 1 when stdin is used without --input-format."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--nation", "NOR"], input="col1,col2\n1,2\n")
    assert result.exit_code == 1
    assert "--input-format required" in result.output


def test_compute_stats_numeric_full():
    """compute_stats returns all 8 spec-mandated fields for a numeric column."""
    values = ["1.0", "2.0", "3.0", "4.0", "5.0"]
    numeric_stats, cat_stats = compute_stats(values)
    assert cat_stats is None
    assert numeric_stats is not None
    expected_keys = {
        "count",
        "min",
        "max",
        "mean",
        "stddev",
        "null_rate",
        "cardinality",
        "histogram",
    }
    assert set(numeric_stats.keys()) >= expected_keys
    assert numeric_stats["count"] == 5
    assert isinstance(numeric_stats["count"], int)
    assert numeric_stats["min"] == pytest.approx(1.0)
    assert numeric_stats["max"] == pytest.approx(5.0)
    assert numeric_stats["mean"] == pytest.approx(3.0)
    assert numeric_stats["stddev"] > 0  # pyright: ignore[reportOperatorIssue]
    assert numeric_stats["null_rate"] == pytest.approx(0.0)
    assert numeric_stats["cardinality"] == 5
    assert isinstance(numeric_stats["histogram"], str)  # JSON-encoded list of 10 bin counts


def test_compute_stats_null_rate():
    """compute_stats correctly computes null_rate from original sample list."""
    values = ["1.0", None, "3.0", "", "5.0"]
    numeric_stats, _ = compute_stats(values)
    assert numeric_stats is not None
    # 2 of 5 values are null/empty → null_rate = 0.4
    assert numeric_stats["null_rate"] == pytest.approx(0.4)


def test_unit_detect_from_description():
    """detect_unit falls through to description patterns when name gives no match."""
    assert detect_unit("altitude", "Height in metres above sea level") == "meter"
    assert detect_unit("speed", "Speed in knots") == "knot"
    assert detect_unit("no_match", "") is None


def test_dispatch_unknown_extension():
    """dispatch_parser raises ValueError for unrecognised file extensions."""
    src = io.StringIO("<schema/>")
    with pytest.raises(ValueError, match="Cannot auto-detect format"):
        dispatch_parser(src, Path("schema.xml"), None, "NOR")


def test_schema_slug_non_ascii_raises():
    """schema_slug raises ValueError when the title contains only non-ASCII characters."""
    with pytest.raises(ValueError, match="empty slug"):
        schema_slug("飞行高度")


def test_json_schema_property_ref_raises():
    """parse_json_schema raises ValueError when a property uses $ref instead of an inline type."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Test Schema",
        "type": "object",
        "properties": {
            "target_type": {"$ref": "#/$defs/TargetType"},
        },
        "$defs": {
            "TargetType": {"type": "string", "enum": ["air", "surface"]},
        },
    }
    src = io.StringIO(json.dumps(schema))
    with pytest.raises(ValueError, match="\\$ref"):
        parse_json_schema(src, None, "TST")


def test_histogram_edges_in_rdf():
    """fields_to_graph emits rose:histogramEdges triple when numeric stats are present."""
    from rosetta.core.unit_detect import compute_stats

    values = ["1.0", "2.0", "3.0", "4.0", "5.0"]
    numeric_stats, _ = compute_stats(values)
    fields = [
        FieldSchema(
            name="altitude_m",
            data_type="number",
            numeric_stats=numeric_stats,
        )
    ]
    g = fields_to_graph(fields, "NOR", "test")
    subject = URIRef("http://rosetta.interop/field/NOR/test/altitude_m")
    stats_nodes = list(g.objects(subject, ROSE.stats))
    assert len(stats_nodes) == 1
    histogram_edges = list(g.objects(stats_nodes[0], ROSE.histogramEdges))
    assert len(histogram_edges) == 1, "rose:histogramEdges triple missing from stats blank node"
    import json as _json

    edges = _json.loads(str(histogram_edges[0]))
    assert len(edges) == 11


# ---------------------------------------------------------------------------
# Regression: parser error handling
# ---------------------------------------------------------------------------


def test_openapi_empty_file_raises():
    """OpenAPI parser must raise ValueError on empty/non-dict YAML input."""
    from rosetta.core.parsers.openapi_parser import parse_openapi

    with pytest.raises(ValueError, match="YAML mapping"):
        parse_openapi(io.StringIO(""), None, "TEST")

    with pytest.raises(ValueError, match="YAML mapping"):
        parse_openapi(io.StringIO("just a string"), None, "TEST")


def test_csv_malformed_wraps_csv_error(monkeypatch):
    """csv.Error during parsing is wrapped as ValueError with 'Malformed CSV'."""
    import csv as csv_mod

    from rosetta.core.parsers.csv_parser import parse_csv

    original_init = csv_mod.DictReader.__init__

    def bad_init(self, *a, **kw):
        original_init(self, *a, **kw)

    # Make iterating the reader raise csv.Error
    monkeypatch.setattr(
        csv_mod.DictReader,
        "__next__",
        lambda self: (_ for _ in ()).throw(csv_mod.Error("bad line")),
    )

    src = io.StringIO("name,value\na,1")
    with pytest.raises(ValueError, match="Malformed CSV"):
        parse_csv(src, None, "TEST")


def test_ingest_cli_invalid_input_format():
    """--input-format with invalid value should be rejected by Click."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--nation",
            "NOR",
            "--input-format",
            "xml",
        ],
    )
    assert result.exit_code != 0


def test_ingest_cli_invalid_output_format():
    """--format with invalid RDF format should be rejected by Click."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input",
            str(FIXTURES / "nor_radar.csv"),
            "--nation",
            "NOR",
            "--format",
            "garbage",
        ],
    )
    assert result.exit_code != 0
    assert "Invalid value" in result.output or "invalid choice" in result.output.lower()


def test_json_schema_malformed_raises():
    """parse_json_schema raises ValueError with 'Malformed JSON' for invalid JSON."""
    src = io.StringIO("{invalid json")
    with pytest.raises(ValueError, match="Malformed JSON"):
        parse_json_schema(src, None, "TST")


def test_openapi_chained_ref_resolved():
    """parse_openapi resolves chained $ref (A -> B -> C)."""
    yaml_str = """
openapi: "3.0.3"
info:
  title: Test API
  version: "1.0"
components:
  schemas:
    AliasToBase:
      $ref: "#/components/schemas/BaseType"
    BaseType:
      type: object
      properties:
        field_a:
          type: string
    Wrapper:
      type: object
      properties:
        nested:
          $ref: "#/components/schemas/AliasToBase"
"""
    src = io.StringIO(yaml_str)
    fields, slug = parse_openapi(src, None, "TST")
    # Should have field_a from BaseType (resolved through AliasToBase)
    # and nested from Wrapper
    field_names = {f.name for f in fields}
    assert "field_a" in field_names
    assert "nested" in field_names


# ---------------------------------------------------------------------------
# Stub CLI exit codes
# ---------------------------------------------------------------------------


def test_validate_stub_exits_1():
    """rosetta-validate stub exits with code 1 (not implemented)."""
    runner = CliRunner()
    result = runner.invoke(validate_cli, [])
    assert result.exit_code == 1
    out = result.output.lower()
    assert "not yet implemented" in out or "not implemented" in out


def test_provenance_stub_exits_1():
    """rosetta-provenance stub exits with code 1 (not implemented)."""
    runner = CliRunner()
    result = runner.invoke(provenance_cli, [])
    assert result.exit_code == 1
    out = result.output.lower()
    assert "not yet implemented" in out or "not implemented" in out


def test_rml_gen_stub_exits_1():
    """rosetta-rml-gen stub exits with code 1 (not implemented)."""
    runner = CliRunner()
    result = runner.invoke(rml_gen_cli, [])
    assert result.exit_code == 1
    out = result.output.lower()
    assert "not yet implemented" in out or "not implemented" in out


def test_accredit_stub_exits_1():
    """rosetta-accredit stub exits with code 1 (not implemented)."""
    runner = CliRunner()
    result = runner.invoke(accredit_cli, [])
    assert result.exit_code == 1
    out = result.output.lower()
    assert "not yet implemented" in out or "not implemented" in out
