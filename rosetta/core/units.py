"""Unit utilities for rosetta lint: QUDT IRI mapping, dimension vectors,
compatibility, and FnML suggestions."""

from __future__ import annotations

from importlib.resources import files

import rdflib

from rosetta.core.models import FnmlSuggestion

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNIT_NS = "http://qudt.org/vocab/unit/"
QUDT_NS = "http://qudt.org/schema/qudt/"


# ---------------------------------------------------------------------------
# Graph loading
# ---------------------------------------------------------------------------


def load_qudt_graph() -> rdflib.Graph:
    """Load qudt_units.ttl and fnml_registry.ttl into a single merged Graph."""
    data = files("rosetta.policies")
    g = rdflib.Graph()
    g.parse(data=data.joinpath("qudt_units.ttl").read_text(), format="turtle")
    g.parse(data=data.joinpath("fnml_registry.ttl").read_text(), format="turtle")
    return g


# ---------------------------------------------------------------------------
# Dimension vector lookup
# ---------------------------------------------------------------------------


def dimension_vector(unit_iri: str, qudt_graph: rdflib.Graph) -> str | None:
    """Return the qudt:hasDimensionVector string for *unit_iri*, or None if absent.

    *unit_iri* may be short form ``"unit:M"`` or full IRI
    ``"http://qudt.org/vocab/unit/M"``.
    """
    if unit_iri.startswith("unit:"):
        full_iri = UNIT_NS + unit_iri[5:]
    else:
        full_iri = unit_iri
    subj = rdflib.URIRef(full_iri)
    pred = rdflib.URIRef(QUDT_NS + "hasDimensionVector")
    val = qudt_graph.value(subj, pred)
    return str(val) if val is not None else None


# ---------------------------------------------------------------------------
# Compatibility check
# ---------------------------------------------------------------------------


def units_compatible(src_iri: str, tgt_iri: str, qudt_graph: rdflib.Graph) -> bool | None:
    """Compare dimension vectors of two unit IRIs.

    Returns:
        True   — both vectors equal (compatible dimensions).
        False  — both vectors present but differ (incompatible).
        None   — either IRI is falsy or dimension vector is missing.
    """
    if not src_iri or not tgt_iri:
        return None
    src_vec = dimension_vector(src_iri, qudt_graph)
    tgt_vec = dimension_vector(tgt_iri, qudt_graph)
    if src_vec is None or tgt_vec is None:
        return None
    return src_vec == tgt_vec


# ---------------------------------------------------------------------------
# IRI expansion helper
# ---------------------------------------------------------------------------


def expand_unit_iri(iri: str) -> str:
    """Expand a short-form ``"unit:X"`` IRI to its full QUDT equivalent."""
    return UNIT_NS + iri[5:] if iri.startswith("unit:") else iri


# ---------------------------------------------------------------------------
# FnML conversion function suggestion
# ---------------------------------------------------------------------------

_FNML_QUERY = """
PREFIX rose: <http://rosetta.interop/ns/>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?fn ?label ?multiplier ?offset WHERE {
    ?fn rose:fromUnit ?from ;
        rose:toUnit   ?to ;
        rdfs:label    ?label .
    OPTIONAL { ?fn qudt:conversionMultiplier ?multiplier }
    OPTIONAL { ?fn qudt:conversionOffset     ?offset }
}
"""


def suggest_fnml(src_iri: str, tgt_iri: str, qudt_graph: rdflib.Graph) -> FnmlSuggestion | None:
    """Query the merged policy graph for a conversion function between two unit IRIs.

    Both qudt_units.ttl and fnml_registry.ttl must already be merged in *qudt_graph*
    (as returned by :func:`load_qudt_graph`).

    Returns a dict with keys ``fnml_function``, ``label``, ``multiplier``, ``offset``
    or None if no matching conversion function is found.
    """
    src_full = expand_unit_iri(src_iri)
    tgt_full = expand_unit_iri(tgt_iri)

    results = list(
        qudt_graph.query(
            _FNML_QUERY,
            initBindings={
                "from": rdflib.URIRef(src_full),
                "to": rdflib.URIRef(tgt_full),
            },
        )
    )
    if not results:
        return None

    row = results[0]  # pyright: ignore[reportIndexIssue]
    # None-guard all OPTIONAL SPARQL vars before use; rdflib ResultRow attrs are dynamic
    fn_val = row.fn  # pyright: ignore[reportAttributeAccessIssue]
    label_val = row.label  # pyright: ignore[reportAttributeAccessIssue]
    mult_val = row.multiplier  # pyright: ignore[reportAttributeAccessIssue]
    off_val = row.offset  # pyright: ignore[reportAttributeAccessIssue]
    multiplier = float(mult_val) if mult_val is not None else None
    offset = float(off_val) if off_val is not None else None
    return FnmlSuggestion(
        fnml_function=str(fn_val),
        label=str(label_val) if label_val is not None else None,
        multiplier=multiplier,
        offset=offset,
    )
