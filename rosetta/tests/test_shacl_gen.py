"""Phase 19 / Plan 19-01 / Task 4 — tests for rosetta-shacl-gen.

Covers both the helper ``rosetta.core.shacl_generator.generate_shacl`` and the
Click CLI ``rosetta.cli.shacl_gen.cli``. Six required tests, mirroring the plan.
"""

from __future__ import annotations

from pathlib import Path

import pyshacl
from click.testing import CliRunner
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, SH

from rosetta.cli.shacl_gen import cli
from rosetta.core.shacl_generator import generate_shacl

PROV = Namespace("http://www.w3.org/ns/prov#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
MC = Namespace("https://ontology.nato.int/core/MasterCOP#")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_turtle(turtle: str) -> Graph:
    g = Graph()
    g.parse(data=turtle, format="turtle")
    return g


def _node_shapes(g: Graph) -> list[URIRef | BNode]:
    return [s for s in g.subjects(RDF.type, SH.NodeShape) if isinstance(s, (URIRef, BNode))]


def _ignored_lists_for_shape(g: Graph, shape: URIRef | BNode) -> list[list[URIRef]]:
    out: list[list[URIRef]] = []
    for head in g.objects(shape, SH.ignoredProperties):
        if isinstance(head, BNode):
            members = [m for m in Collection(g, head) if isinstance(m, URIRef)]
            out.append(members)
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_generates_valid_turtle(master_schema_path: Path) -> None:
    """Helper output parses as Turtle and contains at least one sh:NodeShape."""
    turtle = generate_shacl(master_schema_path)
    g = _parse_turtle(turtle)
    shapes = _node_shapes(g)
    assert shapes, "expected at least one sh:NodeShape in generator output"


def test_closed_default_adds_sh_closed_true(master_schema_path: Path) -> None:
    """Every NodeShape in default (closed) output has (shape, sh:closed, true)."""
    g = _parse_turtle(generate_shacl(master_schema_path))
    shapes = _node_shapes(g)
    assert shapes
    true_lit = Literal(True)
    for shape in shapes:
        assert (shape, SH.closed, true_lit) in g, f"shape {shape!r} missing sh:closed true triple"


def test_closed_default_adds_ignored_properties(master_schema_path: Path) -> None:
    """Every NodeShape's sh:ignoredProperties list contains the 5 baked-in IRIs."""
    g = _parse_turtle(generate_shacl(master_schema_path))
    shapes = _node_shapes(g)
    assert shapes
    expected: set[URIRef] = {
        PROV.wasGeneratedBy,
        PROV.wasAttributedTo,
        DCTERMS.created,
        DCTERMS.source,
        RDF.type,
    }
    for shape in shapes:
        lists = _ignored_lists_for_shape(g, shape)
        assert lists, f"shape {shape!r} has no sh:ignoredProperties list"
        # Union of all rdf:Lists hung off this shape (typically exactly one).
        members: set[URIRef] = set()
        for lst in lists:
            members.update(lst)
        missing = expected - members
        assert not missing, (
            f"shape {shape!r} ignoredProperties missing {missing!r}; got {members!r}"
        )


def test_open_flag_omits_closed_and_ignored(master_schema_path: Path) -> None:
    """With closed=False: no `sh:closed true` triples, and no Phase-19 ignored entries.

    The upstream LinkML generator may emit its own ignoredProperties lists; we
    assert specifically that ``dcterms:created`` (a baked-in we add only in
    closed mode) is not in any such list.
    """
    g = _parse_turtle(generate_shacl(master_schema_path, closed=False))
    true_lit = Literal(True)
    closed_true_triples = list(g.triples((None, SH.closed, true_lit)))
    assert not closed_true_triples, (
        f"open mode emitted sh:closed true triples: {closed_true_triples!r}"
    )

    # Walk every ignoredProperties list in the graph; none should contain
    # dcterms:created (our baked-in marker for closed-mode extension).
    for _, _, head in g.triples((None, SH.ignoredProperties, None)):
        if not isinstance(head, BNode):
            continue
        members = list(Collection(g, head))
        assert DCTERMS.created not in members, (
            f"open mode unexpectedly added dcterms:created to ignoredProperties: {members!r}"
        )


def test_unit_aware_shape_emitted_for_qudt_slot(master_schema_path: Path) -> None:
    """At least one sh:property block has sh:path qudt:hasUnit and sh:hasValue
    pointing to a recognised QUDT unit IRI from the master schema's slots."""
    g = _parse_turtle(generate_shacl(master_schema_path))
    expected_units: set[URIRef] = {
        UNIT.KN,
        UNIT.DEG,
        URIRef(str(UNIT) + "FT-PER-MIN"),
        UNIT.FT,
    }
    found: set[URIRef] = set()
    # Every property shape with sh:path qudt:hasUnit should carry sh:hasValue.
    for prop_node in g.subjects(SH.path, QUDT.hasUnit):
        for value in g.objects(prop_node, SH.hasValue):
            if isinstance(value, URIRef):
                found.add(value)
    overlap = found & expected_units
    assert overlap, (
        f"expected at least one of {expected_units!r} as a sh:hasValue on a "
        f"qudt:hasUnit property shape; found {found!r}"
    )


def test_validates_conformant_graph_and_rejects_typo(tmp_path: Path) -> None:
    """Round-trip via a tiny inline schema: conformant data passes; typo'd
    predicate violates sh:closed under closed-world shapes."""
    # --- 1. Tiny schema ---------------------------------------------------
    schema_yaml = """\
name: tiny
id: https://example.org/tiny#
imports:
- linkml:types
prefixes:
  linkml:
    prefix_prefix: linkml
    prefix_reference: https://w3id.org/linkml/
  ex:
    prefix_prefix: ex
    prefix_reference: https://example.org/tiny#
default_prefix: ex
default_range: string
slots:
  hasName:
    name: hasName
    slot_uri: ex:hasName
    range: string
classes:
  Widget:
    name: Widget
    class_uri: ex:Widget
    slots:
    - hasName
"""
    schema_path = tmp_path / "tiny.linkml.yaml"
    schema_path.write_text(schema_yaml, encoding="utf-8")

    shapes_g = _parse_turtle(generate_shacl(schema_path))

    EX = Namespace("https://example.org/tiny#")

    # --- 2. Conformant data graph -----------------------------------------
    ok = Graph()
    ok.add((EX.widget1, RDF.type, EX.Widget))
    ok.add((EX.widget1, EX.hasName, Literal("ok")))
    conforms_ok, _, _ = pyshacl.validate(
        data_graph=ok, shacl_graph=shapes_g, inference="none", advanced=False
    )
    assert conforms_ok, "conformant Widget graph should validate"

    # --- 3. Non-conformant: typo'd predicate (closed-world violation) -----
    bad = Graph()
    bad.add((EX.widget1, RDF.type, EX.Widget))
    bad.add((EX.widget1, EX.hasName, Literal("ok")))
    bad.add((EX.widget1, EX.hasNaem, Literal("typo")))  # not declared
    conforms_bad, report_g, _ = pyshacl.validate(
        data_graph=bad, shacl_graph=shapes_g, inference="none", advanced=False
    )
    assert not conforms_bad, "graph with undeclared predicate should fail closed shape"
    assert isinstance(report_g, Graph), "pyshacl should return a Graph as the report"

    sources = {str(o) for _, _, o in report_g.triples((None, SH.sourceConstraintComponent, None))}
    assert any("Closed" in src for src in sources), (
        f"expected a sh:ClosedConstraintComponent violation; got sources={sources!r}"
    )


# ---------------------------------------------------------------------------
# CLI smoke test (covers Click wrapper)
# ---------------------------------------------------------------------------


def test_cli_writes_output_file(master_schema_path: Path, tmp_path: Path) -> None:
    """End-to-end CLI: --input + --output writes parseable Turtle, exit code 0."""
    out_path = tmp_path / "shapes.ttl"
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        ["--input", str(master_schema_path), "--output", str(out_path)],
    )
    assert result.exit_code == 0, f"cli exited {result.exit_code}; stderr={result.stderr!r}"
    assert out_path.exists(), "expected --output file to be written"
    g = _parse_turtle(out_path.read_text(encoding="utf-8"))
    assert _node_shapes(g), "CLI-emitted Turtle has no NodeShape triples"
