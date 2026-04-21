"""Phase 19 / Plan 19-01 / Task 4 — tests for rosetta-shacl-gen.

Covers both the helper ``rosetta.core.shacl_generator.generate_shacl`` and the
Click CLI ``rosetta.cli.shacl_gen.cli``. Six required tests, mirroring the plan.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, SH

from rosetta.cli.shacl_gen import cli
from rosetta.core.shacl_generator import generate_shacl
from rosetta.core.shacl_validate import validate_graph

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


def test_open_flag_behaviorally_permits_extra_predicates(tmp_path: Path) -> None:
    """Behavioral proof of ``--open``: a graph that fails under closed-world
    shapes (a typo'd predicate that is not declared on the class) must PASS
    under open-world shapes from the same schema.

    The mirror of ``test_validates_conformant_graph_and_rejects_typo`` — where
    the typo triggers ``sh:ClosedConstraintComponent`` under closed-world —
    pinned from the open-world direction. Without this test, ``--open`` was
    only checked structurally (absence of ``sh:closed true`` triples) and not
    behaviorally.
    """
    schema_yaml = """\
name: tiny-open
id: https://example.org/tiny-open#
imports:
- linkml:types
prefixes:
  linkml:
    prefix_prefix: linkml
    prefix_reference: https://w3id.org/linkml/
  ex:
    prefix_prefix: ex
    prefix_reference: https://example.org/tiny-open#
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
    schema_path = tmp_path / "tiny_open.linkml.yaml"
    schema_path.write_text(schema_yaml, encoding="utf-8")

    open_shapes_g = _parse_turtle(generate_shacl(schema_path, closed=False))

    EX = Namespace("https://example.org/tiny-open#")
    typo_graph = Graph()
    typo_graph.add((EX.widget1, RDF.type, EX.Widget))
    typo_graph.add((EX.widget1, EX.hasName, Literal("ok")))
    typo_graph.add((EX.widget1, EX.hasNaem, Literal("typo")))  # NOT declared

    report = validate_graph(typo_graph, open_shapes_g)
    assert report.summary.conforms, (
        f"open-world shapes must permit undeclared predicates; "
        f"got violations={report.summary.violation} findings={report.findings!r}"
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
    """At least one sh:property block has sh:path qudt:hasUnit and an sh:in
    rdf:List containing recognised QUDT unit IRIs from the master schema.

    The generator emits one consolidated ``sh:in`` constraint per class
    (covering every unit its slots map to). This test walks those lists and
    asserts at least one expected unit appears across the schema.
    """
    g = _parse_turtle(generate_shacl(master_schema_path))
    expected_units: set[URIRef] = {
        UNIT.KN,
        UNIT.DEG,
        URIRef(str(UNIT) + "FT-PER-MIN"),
        UNIT.FT,
    }
    found: set[URIRef] = set()
    for prop_node in g.subjects(SH.path, QUDT.hasUnit):
        for list_head in g.objects(prop_node, SH["in"]):
            if not isinstance(list_head, BNode):
                continue
            for member in Collection(g, list_head):
                if isinstance(member, URIRef):
                    found.add(member)
    overlap = found & expected_units
    assert overlap, (
        f"expected at least one of {expected_units!r} in an sh:in list on a "
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
    report_ok = validate_graph(ok, shapes_g)
    assert report_ok.summary.conforms, "conformant Widget graph should validate"

    # --- 3. Non-conformant: typo'd predicate (closed-world violation) -----
    bad = Graph()
    bad.add((EX.widget1, RDF.type, EX.Widget))
    bad.add((EX.widget1, EX.hasName, Literal("ok")))
    bad.add((EX.widget1, EX.hasNaem, Literal("typo")))  # not declared
    report_bad = validate_graph(bad, shapes_g)
    assert not report_bad.summary.conforms, (
        "graph with undeclared predicate should fail closed shape"
    )
    constraints = {f.constraint for f in report_bad.findings}
    assert any("Closed" in c for c in constraints), (
        f"expected a sh:ClosedConstraintComponent violation; got constraints={constraints!r}"
    )


# ---------------------------------------------------------------------------
# CLI smoke test (covers Click wrapper)
# ---------------------------------------------------------------------------


def test_cli_writes_output_file(master_schema_path: Path, tmp_path: Path) -> None:
    """End-to-end CLI: positional SCHEMA_FILE + --output writes parseable Turtle, exit code 0."""
    out_path = tmp_path / "shapes.ttl"
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [str(master_schema_path), "--output", str(out_path)],
    )
    assert result.exit_code == 0, f"cli exited {result.exit_code}; stderr={result.stderr!r}"
    assert out_path.exists(), "expected --output file to be written"
    g = _parse_turtle(out_path.read_text(encoding="utf-8"))
    assert _node_shapes(g), "CLI-emitted Turtle has no NodeShape triples"


def test_cli_malformed_yaml_exits_nonzero(tmp_path: Path) -> None:
    """Adversarial: syntactically broken LinkML YAML surfaces a non-zero exit
    with a non-empty stderr — not an unhandled traceback."""
    bad = tmp_path / "broken.linkml.yaml"
    bad.write_text("this: : is : not valid yaml\n  - [:\n", encoding="utf-8")
    out_path = tmp_path / "shapes.ttl"
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [str(bad), "--output", str(out_path)],
    )
    assert result.exit_code != 0, "malformed YAML should surface non-zero exit"
    assert result.stderr, "malformed YAML should emit a non-empty stderr message"
    assert not out_path.exists(), "no shapes file should be written on parse failure"


def test_curie_to_unit_iri_rejects_non_curie(
    monkeypatch: pytest.MonkeyPatch, master_schema_path: Path
) -> None:
    """``_curie_to_unit_iri`` must raise ValueError if ``detect_unit`` ever
    returns a bare string (defensive contract — keeps a regression here loud)."""
    from rosetta.core import shacl_generator as sg
    from rosetta.core import unit_detect

    def fake_detect_unit(name: str, desc: str = "") -> str | None:
        return "kilonewton"  # bare string, not a CURIE like "unit:KN"

    monkeypatch.setattr(unit_detect, "detect_unit", fake_detect_unit)
    monkeypatch.setattr(sg, "detect_unit", fake_detect_unit)

    with pytest.raises(ValueError, match="non-CURIE"):
        sg._curie_to_unit_iri("kilonewton")


def test_validate_graph_wraps_pyshacl_engine_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``validate_graph`` must surface a clear ``pyshacl engine error:`` message
    when the underlying engine raises (malformed shapes, internal bug, …)."""
    from rosetta.core import shacl_validate as sv

    def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("simulated engine failure")

    monkeypatch.setattr(sv.pyshacl, "validate", boom)

    with pytest.raises(RuntimeError, match="pyshacl engine error"):
        sv.validate_graph(Graph(), Graph())


def test_abstract_and_mixin_classes_are_ignored(tmp_path: Path) -> None:
    """Abstract and mixin LinkML classes must not receive a ``sh:NodeShape``.

    They exist for schema composition (inheritance / trait-mixins) and do not
    correspond to instantiable RDF individuals, so emitting shapes for them
    would produce spurious closed-world violations on every concrete subclass.
    """
    schema_yaml = """\
name: mixins
id: https://example.org/mixins#
imports:
- linkml:types
prefixes:
  linkml:
    prefix_prefix: linkml
    prefix_reference: https://w3id.org/linkml/
  ex:
    prefix_prefix: ex
    prefix_reference: https://example.org/mixins#
default_prefix: ex
default_range: string
slots:
  hasName:
    name: hasName
    slot_uri: ex:hasName
classes:
  AbstractBase:
    name: AbstractBase
    class_uri: ex:AbstractBase
    abstract: true
    slots:
    - hasName
  TraitMixin:
    name: TraitMixin
    class_uri: ex:TraitMixin
    mixin: true
    slots:
    - hasName
  Concrete:
    name: Concrete
    class_uri: ex:Concrete
    is_a: AbstractBase
    mixins:
    - TraitMixin
"""
    schema_path = tmp_path / "mixins.linkml.yaml"
    schema_path.write_text(schema_yaml, encoding="utf-8")

    g = _parse_turtle(generate_shacl(schema_path))
    EX = Namespace("https://example.org/mixins#")
    shape_iris = {str(s) for s in _node_shapes(g) if isinstance(s, URIRef)}
    assert str(EX.Concrete) in shape_iris, "concrete class must emit a NodeShape"
    assert str(EX.AbstractBase) not in shape_iris, "abstract class must not emit a NodeShape"
    assert str(EX.TraitMixin) not in shape_iris, "mixin class must not emit a NodeShape"
