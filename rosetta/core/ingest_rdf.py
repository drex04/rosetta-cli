"""RDF Turtle emitter: converts a list of FieldSchema objects into an rdflib Graph."""

from __future__ import annotations

from rdflib import Graph, Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, RDFS, XSD

from rosetta.core.parsers import FieldSchema
from rosetta.core.rdf_utils import ROSE_NS as ROSE, bind_namespaces, save_graph

# Pre-build URIRefs for properties that clash with Namespace built-in methods
_ROSE_BASE = "http://rosetta.interop/ns/"
ROSE_FIELD = URIRef(_ROSE_BASE + "Field")
ROSE_DATA_TYPE = URIRef(_ROSE_BASE + "dataType")
ROSE_DETECTED_UNIT = URIRef(_ROSE_BASE + "detectedUnit")
ROSE_STATS = URIRef(_ROSE_BASE + "stats")
ROSE_COUNT = URIRef(_ROSE_BASE + "count")
ROSE_MIN = URIRef(_ROSE_BASE + "min")
ROSE_MAX = URIRef(_ROSE_BASE + "max")
ROSE_MEAN = URIRef(_ROSE_BASE + "mean")
ROSE_DISTINCT_COUNT = URIRef(_ROSE_BASE + "distinctCount")


def fields_to_graph(fields: list[FieldSchema], nation: str, slug: str) -> Graph:
    """Serialize a list of FieldSchema objects into an RDF graph.

    Args:
        fields: Parsed field descriptors (with optional stats).
        nation: Nation code (e.g. "NOR"), used in the field namespace URI.
        slug: Schema slug (e.g. "nor_radar"), used in the field namespace URI.

    Returns:
        An rdflib Graph with all field triples bound to standard Rosetta prefixes.
    """
    g = Graph()
    bind_namespaces(g)
    g.bind("xsd", XSD)

    F = Namespace(f"http://rosetta.interop/field/{nation}/{slug}/")
    g.bind("f", F)

    for field in fields:
        field_uri = F[field.name]

        g.add((field_uri, RDF.type, ROSE_FIELD))
        g.add((field_uri, RDFS.label, Literal(field.name)))
        g.add((field_uri, ROSE_DATA_TYPE, Literal(field.data_type)))

        if field.detected_unit is not None:
            g.add((field_uri, ROSE_DETECTED_UNIT, Literal(field.detected_unit)))

        if field.numeric_stats is not None:
            stats_bn = BNode()
            g.add((stats_bn, ROSE_COUNT, Literal(field.numeric_stats["count"], datatype=XSD.integer)))
            g.add((stats_bn, ROSE_MIN, Literal(field.numeric_stats["min"], datatype=XSD.double)))
            g.add((stats_bn, ROSE_MAX, Literal(field.numeric_stats["max"], datatype=XSD.double)))
            g.add((stats_bn, ROSE_MEAN, Literal(field.numeric_stats["mean"], datatype=XSD.double)))
            g.add((field_uri, ROSE_STATS, stats_bn))
        elif field.categorical_stats is not None:
            stats_bn = BNode()
            g.add((stats_bn, ROSE_COUNT, Literal(field.categorical_stats["count"], datatype=XSD.integer)))
            g.add((stats_bn, ROSE_DISTINCT_COUNT, Literal(field.categorical_stats["distinct_count"], datatype=XSD.integer)))
            g.add((field_uri, ROSE_STATS, stats_bn))

    return g
