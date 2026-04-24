"""Shared SHACL validation helper.

Used by ``rosetta validate`` and ``rosetta run --validate`` so the
two entrypoints share one invocation path and produce structurally identical
``ValidationReport`` outputs.
"""

from __future__ import annotations

from typing import Literal, cast

import pyshacl
import rdflib
import rdflib.query
import rdflib.term

from rosetta.core.models import ValidationFinding, ValidationReport, ValidationSummary

_SHACL_NS = "http://www.w3.org/ns/shacl#"

_SPARQL = """\
PREFIX sh: <http://www.w3.org/ns/shacl#>
SELECT ?focusNode ?severity ?message ?constraint ?shape ?path ?value WHERE {
    ?result a sh:ValidationResult ;
            sh:focusNode ?focusNode ;
            sh:resultSeverity ?severity ;
            sh:sourceConstraintComponent ?constraint .
    OPTIONAL { ?result sh:resultMessage ?message . }
    OPTIONAL { ?result sh:sourceShape ?shape . }
    OPTIONAL { ?result sh:resultPath ?path . }
    OPTIONAL { ?result sh:value ?value . }
}
"""


_SEVERITY_MAP: dict[str, Literal["Violation", "Warning", "Info"]] = {
    "Warning": "Warning",
    "Info": "Info",
}


def _strip_shacl_prefix(iri: str) -> str:
    """Strip the SHACL namespace prefix from a severity IRI."""
    if iri.startswith(_SHACL_NS):
        return iri[len(_SHACL_NS) :]
    return iri


def _parse_finding(row: rdflib.query.ResultRow) -> ValidationFinding:
    """Extract a single ``ValidationFinding`` from a SPARQL result row."""
    raw_shape = row.shape  # pyright: ignore[reportAttributeAccessIssue]
    is_named = raw_shape is not None and not isinstance(raw_shape, rdflib.term.BNode)
    severity_str = _strip_shacl_prefix(str(row.severity))  # pyright: ignore[reportAttributeAccessIssue]
    return ValidationFinding(
        focus_node=str(row.focusNode),  # pyright: ignore[reportAttributeAccessIssue]
        severity=_SEVERITY_MAP.get(severity_str, "Violation"),
        constraint=_strip_shacl_prefix(str(row.constraint)),  # pyright: ignore[reportAttributeAccessIssue]
        property_path=str(row.path) if row.path is not None else None,
        value=str(row.value) if row.value is not None else None,
        source_shape=str(raw_shape) if is_named else None,
        message=str(row.message) if row.message is not None else None,  # pyright: ignore[reportAttributeAccessIssue]
    )


def validate_graph(
    data_graph: rdflib.Graph,
    shapes_graph: rdflib.Graph,
    *,
    inference: str = "none",
) -> ValidationReport:
    """Run pySHACL and return a structured ``ValidationReport``."""
    try:
        pyshacl_result: tuple[bool, rdflib.Graph, str] = pyshacl.validate(  # pyright: ignore[reportAssignmentType]
            data_graph,
            shacl_graph=shapes_graph,
            inference=inference,
            do_owl_imports=False,
            meta_shacl=False,
        )
    except Exception as exc:
        raise RuntimeError(f"pyshacl engine error: {exc}") from exc
    conforms, results_graph, _ = pyshacl_result

    findings = [
        _parse_finding(cast(rdflib.query.ResultRow, raw)) for raw in results_graph.query(_SPARQL)
    ]
    counts: dict[str, int] = {"Violation": 0, "Warning": 0, "Info": 0}
    for f in findings:
        counts[f.severity] += 1

    return ValidationReport(
        findings=findings,
        summary=ValidationSummary(
            violation=counts["Violation"],
            warning=counts["Warning"],
            info=counts["Info"],
            conforms=conforms,
        ),
    )
