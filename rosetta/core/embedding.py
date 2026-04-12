"""Embedding utilities for the Rosetta CLI toolkit."""

from __future__ import annotations

from rdflib import Graph, Namespace, RDF

from rosetta.core.rdf_utils import query_graph

ROSE_NS = Namespace("http://rosetta.interop/ns/")

_MASTER_SPARQL = """
PREFIX rose: <http://rosetta.interop/ns/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?attr ?attrLabel ?comment ?conceptLabel WHERE {
  ?attr a rose:Attribute ;
        rdfs:label ?attrLabel .
  OPTIONAL { ?attr rdfs:comment ?comment . }
  OPTIONAL { ?concept rose:hasAttribute ?attr ;
                      rdfs:label ?conceptLabel . }
}
"""

_NATIONAL_SPARQL = """
PREFIX rose: <http://rosetta.interop/ns/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?field ?label WHERE {
  ?field a rose:Field ;
         rdfs:label ?label .
}
"""


def extract_text_inputs(g: Graph) -> list[tuple[str, str]]:
    """Return (uri_str, text_str) pairs for every embeddable attribute in *g*.

    Detects master-ontology graphs (containing rose:Attribute triples) and
    national-schema graphs (containing rose:Field triples) and builds an
    appropriate text representation for each node.
    """
    is_master = any(True for _ in g.triples((None, RDF.type, ROSE_NS.Attribute)))

    results: list[tuple[str, str]] = []

    if is_master:
        for row in query_graph(g, _MASTER_SPARQL):
            attr_uri = row["attr"]
            attr_label = str(row["attrLabel"])
            concept_label = str(row["conceptLabel"]) if row.get("conceptLabel") is not None else ""
            comment = str(row["comment"]) if row.get("comment") is not None else ""
            text = f"{concept_label} / {attr_label} — {comment}"
            results.append((str(attr_uri), text))
    else:
        for row in query_graph(g, _NATIONAL_SPARQL):
            field_uri = row["field"]
            label = str(row["label"])
            # Parent slug is the second-to-last path segment of the URI
            schema_slug = str(field_uri).split("/")[-2]
            text = f"{schema_slug} / {label} — "
            results.append((str(field_uri), text))

    return results


class EmbeddingModel:
    """Thin wrapper around a SentenceTransformer model."""

    def __init__(self, model_name: str = "sentence-transformers/LaBSE") -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts; return as list of Python float lists (JSON-serializable)."""
        vectors = self._model.encode(texts)  # numpy array shape (n, dim)
        return [v.tolist() for v in vectors]
