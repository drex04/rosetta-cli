"""Tests for rosetta.core.rdf_utils."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef

from rosetta.core.rdf_utils import (
    ROSE_NS,
    ROSE_STATS_NS,
    bind_namespaces,
    load_graph,
    query_graph,
    save_graph,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_simple_graph() -> Graph:
    """Return a small graph with two rose: triples."""
    g = Graph()
    bind_namespaces(g)
    subject = ROSE_NS["Thing1"]
    g.add((subject, ROSE_NS["label"], Literal("hello")))
    g.add((subject, ROSE_NS["value"], Literal(42)))
    return g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_roundtrip(tmp_path: Path) -> None:
    """Save a graph to Turtle, reload it, and confirm triples survive."""
    g = _make_simple_graph()
    out_file = tmp_path / "output.ttl"

    save_graph(g, out_file)
    assert out_file.exists()

    g2 = load_graph(out_file)
    assert len(g2) == len(g), f"Expected {len(g)} triples, got {len(g2)}"

    for triple in g:
        assert triple in g2, f"Triple missing after roundtrip: {triple}"


def test_bind_namespaces() -> None:
    """All expected prefixes must be bound after bind_namespaces."""
    g = Graph()
    result = bind_namespaces(g)

    # bind_namespaces must return the same object (in-place + chaining)
    assert result is g

    bound = {prefix for prefix, _ in g.namespaces()}
    expected = {"rose", "rose-stats", "qudt", "prov", "skos"}
    missing = expected - bound
    assert not missing, f"Missing namespace prefixes: {missing}"

    # Spot-check URIs
    ns_map = {prefix: str(uri) for prefix, uri in g.namespaces()}
    assert ns_map["rose"] == "http://rosetta.interop/ns/"
    assert ns_map["rose-stats"] == "http://rosetta.interop/ns/stats/"
    assert ns_map["qudt"] == "http://qudt.org/schema/qudt/"
    assert ns_map["prov"] == "http://www.w3.org/ns/prov#"
    assert ns_map["skos"] == "http://www.w3.org/2004/02/skos/core#"


def test_query_graph() -> None:
    """query_graph returns dicts whose values are rdflib terms."""
    g = _make_simple_graph()

    results = query_graph(
        g,
        """
        SELECT ?s ?p ?o
        WHERE { ?s ?p ?o }
        ORDER BY ?p
        """,
    )

    assert len(results) == 2, f"Expected 2 rows, got {len(results)}"
    for row in results:
        assert "s" in row and "p" in row and "o" in row
        # Values must be rdflib terms, not plain strings
        assert hasattr(row["s"], "toPython") or isinstance(row["s"], URIRef)

    # Confirm we can retrieve the literal value
    values = {str(row["o"]) for row in results}
    assert "hello" in values
    assert "42" in values


def test_save_graph_to_filelike() -> None:
    """save_graph to a file-like object (e.g. stdout) must serialize without error."""
    g = _make_simple_graph()
    buf = io.StringIO()
    save_graph(g, buf)
    output = buf.getvalue()
    assert "rosetta.interop" in output
    assert "hello" in output


def test_load_graph_invalid_rdf(tmp_path: Path) -> None:
    """Invalid RDF input must raise ValueError with a clear message."""
    bad_file = tmp_path / "bad.ttl"
    bad_file.write_text("this is not valid turtle @@@ !!!", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse RDF"):
        load_graph(bad_file)

    # Also test with a file-like object containing invalid RDF
    bad_stream = io.StringIO("<<< completely broken >>>")
    with pytest.raises(ValueError, match="Failed to parse RDF"):
        load_graph(bad_stream)


def test_query_graph_with_bindings() -> None:
    """query_graph passes bindings as initBindings to avoid SPARQL injection."""
    from rdflib import Literal

    g = Graph()
    g.parse(data="""
        @prefix ex: <http://example.org/> .
        ex:a ex:name "Alice" .
        ex:b ex:name "Bob" .
    """, format="turtle")

    results = query_graph(
        g,
        "SELECT ?name WHERE { ?s <http://example.org/name> ?name }",
        bindings={"s": URIRef("http://example.org/a")},
    )
    assert len(results) == 1
    assert str(results[0]["name"]) == "Alice"
