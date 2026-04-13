"""RML/FnML Turtle generation from approved mapping decisions."""

from __future__ import annotations

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from rosetta.core.models import MappingDecision

RML = Namespace("http://semweb.mmlab.be/ns/rml#")
RR = Namespace("http://www.w3.org/ns/r2rml#")
QL = Namespace("http://semweb.mmlab.be/ns/ql#")

_FORMAT_MAP: dict[str, URIRef] = {
    "json": QL.JSONPath,
    "csv": QL.CSV,
}


def _field_ref(decision: MappingDecision, source_format: str) -> str:
    """Return rml:reference string for the decision."""
    name = decision.field_ref or decision.source_uri.rstrip("/").rsplit("/", 1)[-1]
    return f"$.{name}" if source_format == "json" else name


def _add_logical_source(g: Graph, map_node: BNode, source_file: str, source_format: str) -> None:
    ls = BNode()
    g.add((map_node, RML.logicalSource, ls))
    g.add((ls, RML.source, Literal(source_file)))
    g.add((ls, RML.referenceFormulation, _FORMAT_MAP[source_format]))


def _add_subject_map(g: Graph, map_node: BNode, base_uri: str) -> None:
    sm = BNode()
    g.add((map_node, RR.subjectMap, sm))
    g.add((sm, RR.template, Literal(f"{base_uri.rstrip('/')}/{{id}}")))


def _add_predicate_object_map(
    g: Graph, map_node: BNode, decision: MappingDecision, source_format: str
) -> None:
    pom = BNode()
    g.add((map_node, RR.predicateObjectMap, pom))
    g.add((pom, RR.predicate, URIRef(decision.target_uri)))
    obj_map = BNode()
    g.add((pom, RR.objectMap, obj_map))
    # FnML branch handled in Plan 02; plain reference here
    g.add((obj_map, RML.reference, Literal(_field_ref(decision, source_format))))


def build_rml_graph(
    decisions: list[MappingDecision],
    source_file: str,
    source_format: str,
    base_uri: str,
) -> Graph:
    """Build an rdflib Graph containing a single TriplesMap for all decisions."""
    if source_format not in _FORMAT_MAP:
        raise ValueError(f"Unsupported source_format: {source_format!r}. Use 'json' or 'csv'.")

    g = Graph()
    g.bind("rml", RML)
    g.bind("rr", RR)
    g.bind("ql", QL)

    map_node = BNode()
    g.add((map_node, RDF.type, RR.TriplesMap))
    _add_logical_source(g, map_node, source_file, source_format)
    _add_subject_map(g, map_node, base_uri)
    for decision in decisions:
        _add_predicate_object_map(g, map_node, decision, source_format)
    return g
