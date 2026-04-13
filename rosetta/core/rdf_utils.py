"""Shared RDF I/O utilities for the Rosetta CLI toolkit."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TextIO, Union

from rdflib import Graph, Namespace, URIRef, Literal  # noqa: F401 — re-exported

# ---------------------------------------------------------------------------
# Namespace declarations
# ---------------------------------------------------------------------------

ROSE_NS = Namespace("http://rosetta.interop/ns/")
ROSE_STATS_NS = Namespace("http://rosetta.interop/ns/stats/")

_QUDT = Namespace("http://qudt.org/schema/qudt/")
_PROV = Namespace("http://www.w3.org/ns/prov#")
_SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def bind_namespaces(g: Graph) -> Graph:
    """Bind the standard Rosetta prefixes onto *g* and return it."""
    g.bind("rose", ROSE_NS)
    g.bind("rose-stats", ROSE_STATS_NS)
    g.bind("qudt", _QUDT)
    g.bind("prov", _PROV)
    g.bind("skos", _SKOS)
    return g


def load_graph(
    path: Union[Path, TextIO],
    fmt: str = "turtle",
) -> Graph:
    """Load an RDF graph from *path* (file path or file-like object).

    Raises
    ------
    ValueError
        When the source cannot be parsed as valid RDF — wraps the underlying
        rdflib exception so callers receive a human-readable message.
    """
    g = Graph()
    try:
        if isinstance(path, Path):
            g.parse(str(path), format=fmt)
        else:
            # File-like object — read content and parse from string
            g.parse(data=path.read(), format=fmt)
    except Exception as exc:
        source_label = str(path) if isinstance(path, Path) else repr(path)
        raise ValueError(
            f"Failed to parse RDF from {source_label!r} as {fmt!r}: {exc}"
        ) from exc

    return bind_namespaces(g)


def save_graph(
    g: Graph,
    path: Union[Path, TextIO],
    fmt: str = "turtle",
) -> None:
    """Serialize *g* to *path* (file path or file-like object)."""
    bind_namespaces(g)
    serialized = g.serialize(format=fmt)
    if isinstance(serialized, bytes):
        serialized = serialized.decode("utf-8")

    if isinstance(path, Path):
        path.write_text(serialized, encoding="utf-8")
    else:
        path.write(serialized)


def query_graph(g: Graph, sparql: str, bindings: dict | None = None) -> list[dict]:
    """Execute a SPARQL SELECT query and return results as a list of dicts.

    Each dict maps variable name (str) to an rdflib term.
    Use *bindings* (passed as ``initBindings``) instead of string interpolation
    to avoid SPARQL injection.
    """
    results = g.query(sparql, initBindings=bindings or {})
    return [
        {str(var): row[var] for var in results.vars}
        for row in results
    ]
