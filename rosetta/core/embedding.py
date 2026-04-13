"""Embedding utilities for the Rosetta CLI toolkit."""

from __future__ import annotations

from rdflib import RDF, Graph, Namespace

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


def _e5_passage_prefix(model_name: str) -> str:
    """Return the passage prefix required by E5 models, empty string otherwise.

    E5 models (e.g. intfloat/multilingual-e5-*) require all indexed texts to be
    prefixed with ``"passage: "`` and query texts with ``"query: "``.  Other models
    (LaBSE, NB-BERT, …) do not use prefixes.
    """
    low = model_name.lower()
    if "e5" in low and "e5se" not in low:  # exclude unrelated models with 'e5' in name
        return "passage: "
    return ""


class EmbeddingModel:
    """Thin wrapper around a SentenceTransformer model."""

    model_name: str
    _passage_prefix: str
    _query_prefix: str

    def __init__(self, model_name: str = "sentence-transformers/LaBSE") -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model: SentenceTransformer = SentenceTransformer(model_name)
        self._passage_prefix = _e5_passage_prefix(model_name)
        self._query_prefix = "query: " if self._passage_prefix else ""

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode passage texts; return as list of Python float lists (JSON-serializable).

        For E5 models the required ``"passage: "`` prefix is applied automatically.
        """
        if self._passage_prefix:
            texts = [self._passage_prefix + t for t in texts]
        vectors = self._model.encode(texts)  # numpy array shape (n, dim)
        return [v.tolist() for v in vectors]

    def encode_query(self, texts: list[str]) -> list[list[float]]:
        """Encode query texts (used at retrieval time, not indexing).

        For E5 models applies ``"query: "`` prefix; for all others identical to
        :meth:`encode`.
        """
        if self._query_prefix:
            texts = [self._query_prefix + t for t in texts]
        vectors = self._model.encode(texts)
        return [v.tolist() for v in vectors]
