"""Tests for rosetta-rml-gen: build_rml_graph and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import RDF, Namespace

from rosetta.cli.rml_gen import cli
from rosetta.core.models import MappingDecision
from rosetta.core.rml_builder import build_rml_graph

RML = Namespace("http://semweb.mmlab.be/ns/rml#")
RR = Namespace("http://www.w3.org/ns/r2rml#")
QL = Namespace("http://semweb.mmlab.be/ns/ql#")


def _two_decisions() -> list[MappingDecision]:
    return [
        MappingDecision(
            source_uri="http://rosetta.interop/field/nor/schema/hoyde_m",
            target_uri="http://master.ontology/AltitudeMSL",
            field_ref="hoyde_m",
        ),
        MappingDecision(
            source_uri="http://rosetta.interop/field/nor/schema/bredde_deg",
            target_uri="http://master.ontology/Latitude",
            field_ref="bredde_deg",
        ),
    ]


def test_basic_rml_two_decisions() -> None:
    g = build_rml_graph(
        _two_decisions(),
        source_file="data.json",
        source_format="json",
        base_uri="http://rosetta.interop/record",
    )
    turtle = g.serialize(format="turtle")
    assert turtle  # does not raise

    # Exactly one TriplesMap
    triples_maps = list(g.subjects(RDF.type, RR.TriplesMap))
    assert len(triples_maps) == 1

    map_node = triples_maps[0]

    # Has logicalSource
    logical_sources = list(g.objects(map_node, RML.logicalSource))
    assert len(logical_sources) == 1

    # Two predicateObjectMap triples
    poms = list(g.objects(map_node, RR.predicateObjectMap))
    assert len(poms) == 2

    # Each pom has an objectMap with rml:reference
    refs: set[str] = set()
    for pom in poms:
        for obj_map in g.objects(pom, RR.objectMap):
            refs.update(str(ref) for ref in g.objects(obj_map, RML.reference))
    assert refs == {"$.hoyde_m", "$.bredde_deg"}


def test_field_ref_from_uri() -> None:
    decision = MappingDecision(
        source_uri="http://example.org/field/nor/alt",
        target_uri="http://master.ontology/Altitude",
        field_ref=None,
    )
    g = build_rml_graph(
        [decision],
        source_file="data.json",
        source_format="json",
        base_uri="http://rosetta.interop/record",
    )
    refs = [
        str(ref)
        for pom in g.objects(None, RR.predicateObjectMap)
        for obj_map in g.objects(pom, RR.objectMap)
        for ref in g.objects(obj_map, RML.reference)
    ]
    assert refs == ["$.alt"]


def test_csv_format_bare_ref() -> None:
    decision = MappingDecision(
        source_uri="http://example.org/field/nor/alt",
        target_uri="http://master.ontology/Altitude",
        field_ref=None,
    )
    g = build_rml_graph(
        [decision],
        source_file="data.csv",
        source_format="csv",
        base_uri="http://rosetta.interop/record",
    )
    refs = [
        str(ref)
        for pom in g.objects(None, RR.predicateObjectMap)
        for obj_map in g.objects(pom, RR.objectMap)
        for ref in g.objects(obj_map, RML.reference)
    ]
    assert refs == ["alt"]


def test_unsupported_format_raises() -> None:
    decision = MappingDecision(
        source_uri="http://example.org/field/x",
        target_uri="http://master.ontology/X",
    )
    with pytest.raises(ValueError, match="Unsupported source_format"):
        build_rml_graph(
            [decision], source_file="data.xml", source_format="xml", base_uri="http://x"
        )


def test_cli_empty_decisions_exits_1(tmp_path: Path) -> None:
    f = tmp_path / "decisions.json"
    f.write_text("{}")
    result = CliRunner().invoke(cli, ["--decisions", str(f), "--source-file", "data.json"])
    assert result.exit_code == 1


def test_cli_missing_target_uri_exits_1(tmp_path: Path) -> None:
    f = tmp_path / "decisions.json"
    f.write_text(json.dumps({"http://example.org/field/x": {"field_ref": "x"}}))
    result = CliRunner().invoke(cli, ["--decisions", str(f), "--source-file", "data.json"])
    assert result.exit_code == 1


def test_cli_writes_turtle_to_stdout(tmp_path: Path) -> None:
    f = tmp_path / "decisions.json"
    f.write_text(
        json.dumps(
            {
                "http://rosetta.interop/field/nor/schema/hoyde_m": {
                    "target_uri": "http://master.ontology/AltitudeMSL",
                    "field_ref": "hoyde_m",
                }
            }
        )
    )
    result = CliRunner().invoke(cli, ["--decisions", str(f), "--source-file", "data.json"])
    assert result.exit_code == 0
    assert "rml:logicalSource" in result.output


def test_cli_json_array_input_exits_1(tmp_path: Path) -> None:
    f = tmp_path / "decisions.json"
    f.write_text("[]")
    result = CliRunner().invoke(cli, ["--decisions", str(f), "--source-file", "data.json"])
    assert result.exit_code == 1
    assert "must be a JSON object" in result.output or "must be a JSON object" in (
        result.stderr or ""
    )


def test_cli_invalid_decision_type_exits_1(tmp_path: Path) -> None:
    f = tmp_path / "decisions.json"
    f.write_text(
        json.dumps(
            {
                "http://rosetta.interop/field/nor/schema/hoyde_m": {
                    "target_uri": "http://master.ontology/AltitudeMSL",
                    "multiplier": "not-a-number",
                }
            }
        )
    )
    result = CliRunner().invoke(cli, ["--decisions", str(f), "--source-file", "data.json"])
    assert result.exit_code == 1
