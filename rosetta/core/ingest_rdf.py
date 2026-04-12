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
ROSE_STDDEV = URIRef(_ROSE_BASE + "stddev")
ROSE_NULL_RATE = URIRef(_ROSE_BASE + "nullRate")
ROSE_CARDINALITY = URIRef(_ROSE_BASE + "cardinality")
ROSE_HISTOGRAM = URIRef(_ROSE_BASE + "histogram")
ROSE_HISTOGRAM_EDGES = URIRef(_ROSE_BASE + "histogramEdges")
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
            ns = field.numeric_stats
            stats_bn = BNode()
            g.add((stats_bn, ROSE_COUNT, Literal(ns["count"], datatype=XSD.integer)))
            g.add((stats_bn, ROSE_MIN, Literal(ns["min"], datatype=XSD.double)))
            g.add((stats_bn, ROSE_MAX, Literal(ns["max"], datatype=XSD.double)))
            g.add((stats_bn, ROSE_MEAN, Literal(ns["mean"], datatype=XSD.double)))
            g.add((stats_bn, ROSE_STDDEV, Literal(ns["stddev"], datatype=XSD.double)))
            g.add((stats_bn, ROSE_NULL_RATE, Literal(ns["null_rate"], datatype=XSD.double)))
            g.add((stats_bn, ROSE_CARDINALITY, Literal(ns["cardinality"], datatype=XSD.integer)))
            g.add((stats_bn, ROSE_HISTOGRAM, Literal(ns["histogram"])))
            g.add((stats_bn, ROSE_HISTOGRAM_EDGES, Literal(ns["histogram_edges"])))
            g.add((field_uri, ROSE_STATS, stats_bn))
        elif field.categorical_stats is not None:
            cs = field.categorical_stats
            stats_bn = BNode()
            g.add((stats_bn, ROSE_COUNT, Literal(cs["count"], datatype=XSD.integer)))
            g.add((stats_bn, ROSE_DISTINCT_COUNT, Literal(cs["distinct_count"], datatype=XSD.integer)))
            g.add((stats_bn, ROSE_NULL_RATE, Literal(cs["null_rate"], datatype=XSD.double)))
            g.add((field_uri, ROSE_STATS, stats_bn))

    return g
