"""Integration tests for rosetta-ingest CLI and supporting functions."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from rdflib import Graph, Namespace, URIRef

from rosetta.cli.ingest import cli
from rosetta.core.ingest_rdf import fields_to_graph
from rosetta.core.parsers import FieldSchema, schema_slug
from rosetta.core.parsers.json_schema_parser import parse_json_schema
from rosetta.core.parsers.openapi_parser import parse_openapi
from rosetta.core.unit_detect import detect_unit

ROSE = Namespace("http://rosetta.interop/ns/")
FIXTURES = Path(__file__).parent / "fixtures"


def test_ingest_csv():
    """Invoke CLI with nor_radar.csv --nation NOR; assert 11 rose:Field triples + stats + unit."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--input", str(FIXTURES / "nor_radar.csv"), "--nation", "NOR"])
    assert result.exit_code == 0, result.output
    g = Graph()
    g.parse(data=result.output, format="turtle")

    # 11 rose:Field triples
    fields = list(g.subjects(ROSE.Field, None))
    # rdflib: (s, rdf:type, rose:Field)
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
    """Invoke CLI with deu_patriot.json --nation DEU; assert 9 rose:Field triples + stats on Hoehe_Meter."""
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
    """Invoke CLI with usa_c2.yaml --nation USA; assert 9 rose:Field triples + altitude_ft detectedUnit foot."""
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


@pytest.mark.parametrize("name,desc,expected", [
    ("hoyde_m", "", "meter"),
    ("speed_kts", "", "knot"),
    ("hastighet_kmh", "", "km_per_hour"),
    ("altitude_ft", "", "foot"),
    ("dist_km", "", "kilometer"),
    ("track_id", "", None),
])
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
    """CLI exits with code 1 and error text when input file does not exist."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--input", "/nonexistent/path/file.csv", "--nation", "NOR"])
    assert result.exit_code == 1
    assert len(result.output) > 0


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
    """parse_json_schema succeeds on a schema with no top-level examples; all fields have no stats."""
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
    """CLI exits with code 1 and '--input-format required' when stdin used without --input-format."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--nation", "NOR"], input="col1,col2\n1,2\n")
    assert result.exit_code == 1
    assert "--input-format required" in result.output
