"""FnO function library: loads Turtle declarations and answers type signature queries."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import rdflib

_FNO = rdflib.Namespace("https://w3id.org/function/ontology#")
_GREL = rdflib.Namespace("http://users.ugent.be/~bjdmeest/function/grel.ttl#")
_RFNS = rdflib.Namespace("https://rosetta.interop/functions#")

_SPARQL = """\
PREFIX fno: <https://w3id.org/function/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?fn ?param_pred ?param_type ?out_type WHERE {
  ?fn a fno:Function .
  ?fn fno:expects/rdf:first ?param .
  ?param fno:predicate ?param_pred .
  ?param fno:type ?param_type .
  ?fn fno:returns/rdf:first ?out .
  ?out fno:type ?out_type .
}
"""


class FunctionLibrary:
    """Registry of FnO-declared functions with type signature lookup."""

    def __init__(self) -> None:
        self._graph = rdflib.Graph()
        self._graph.bind("fno", _FNO)
        self._graph.bind("grel", _GREL)
        self._graph.bind("rfns", _RFNS)
        self._graph.bind("xsd", rdflib.XSD)
        self._functions: set[str] = set()
        self._input_types: dict[str, str] = {}
        self._output_types: dict[str, str] = {}
        self._param_predicates: dict[str, str] = {}

    @classmethod
    def load_builtins(cls) -> FunctionLibrary:
        """Factory: empty library populated with the two builtin TTL files."""
        lib = cls()
        pkg = files("rosetta.functions")
        lib.add_declarations(Path(str(pkg.joinpath("typecasts.fno.ttl"))))
        lib.add_declarations(Path(str(pkg.joinpath("unit-conversions.fno.ttl"))))
        return lib

    def add_declarations(self, path: Path) -> None:
        """Parse *path* as FnO Turtle and merge into this library."""
        try:
            self._graph.parse(data=path.read_text(encoding="utf-8"), format="turtle")
        except Exception as exc:
            raise ValueError(f"Failed to parse FnO declaration {path}: {exc}") from exc
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._functions.clear()
        self._input_types.clear()
        self._output_types.clear()
        self._param_predicates.clear()
        for row in self._graph.query(_SPARQL):
            fn_iri = str(row.fn)  # pyright: ignore[reportAttributeAccessIssue]
            param_pred_iri = str(row.param_pred)  # pyright: ignore[reportAttributeAccessIssue]
            param_type_iri = str(row.param_type)  # pyright: ignore[reportAttributeAccessIssue]
            out_type_iri = str(row.out_type)  # pyright: ignore[reportAttributeAccessIssue]
            fn_curie = self._compact(fn_iri)
            self._functions.add(fn_curie)
            self._input_types[fn_curie] = self._compact(param_type_iri)
            self._output_types[fn_curie] = self._compact(out_type_iri)
            self._param_predicates[fn_curie] = self._compact(param_pred_iri)

    def _compact(self, iri: str) -> str:
        """Return the CURIE for *iri* if the namespace manager knows it, else the full IRI."""
        try:
            curie = self._graph.namespace_manager.curie(iri)
            return curie
        except Exception:
            return iri

    def resolve_curie(self, curie: str) -> str:
        """Expand a CURIE to a full IRI using the graph's namespace manager."""
        if curie.startswith(("http://", "https://")):
            return curie
        prefix, local = curie.split(":", 1)
        for ns_prefix, ns_uri in self._graph.namespaces():
            if ns_prefix == prefix:
                return str(ns_uri) + local
        return curie

    def _normalize(self, iri_or_curie: str) -> str:
        """Normalize input to CURIE form used as dict keys."""
        full = self.resolve_curie(iri_or_curie)
        return self._compact(full)

    def has_function(self, iri: str) -> bool:
        """Return True if *iri* (CURIE or full IRI) is a declared fno:Function."""
        return self._normalize(iri) in self._functions

    def get_input_type(self, iri: str) -> str | None:
        """Return CURIE of the expected parameter XSD type, or None if unknown."""
        return self._input_types.get(self._normalize(iri))

    def get_output_type(self, iri: str) -> str | None:
        """Return CURIE of the return XSD type, or None if unknown."""
        return self._output_types.get(self._normalize(iri))

    def get_parameter_predicate(self, iri: str) -> str:
        """Return CURIE of the FnO parameter predicate. Raises KeyError if unknown."""
        key = self._normalize(iri)
        return self._param_predicates[key]
