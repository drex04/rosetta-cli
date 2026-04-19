"""Shared SHACL validation helper.

Used by ``rosetta-validate`` and ``rosetta-yarrrml-gen --validate`` so the
two entrypoints share one invocation path and produce structurally identical
``ValidationReport`` outputs.
"""

from __future__ import annotations

from typing import Literal, cast

import pyshacl
import rdflib
import rdflib.query

from rosetta.core.models import ValidationFinding, ValidationReport, ValidationSummary

_SHACL_NS = "http://www.w3.org/ns/shacl#"

_SPARQL = """\
PREFIX sh: <http://www.w3.org/ns/shacl#>
SELECT ?focusNode ?severity ?message ?constraint ?shape WHERE {
    ?result a sh:ValidationResult ;
            sh:focusNode ?focusNode ;
            sh:resultSeverity ?severity ;
            sh:sourceConstraintComponent ?constraint .
    OPTIONAL { ?result sh:resultMessage ?message . }
    OPTIONAL { ?result sh:sourceShape ?shape . }
}
"""


def _strip_shacl_prefix(iri: str) -> str:
    """Strip the SHACL namespace prefix from a severity IRI."""
    if iri.startswith(_SHACL_NS):
        return iri[len(_SHACL_NS) :]
    return iri


def validate_graph(
    data_graph: rdflib.Graph,
    shapes_graph: rdflib.Graph,
    *,
    inference: str = "none",
) -> ValidationReport:
    """Run pySHACL and return a structured ``ValidationReport``.

    Parameters
    ----------
    data_graph
        The data graph to validate. Caller already parsed Turtle / JSON-LD / etc.
    shapes_graph
        The merged SHACL shapes graph.
    inference
        Pass-through to pyshacl. Default ``"none"`` matches the existing
        ``rosetta-validate`` contract.

    Returns
    -------
    ValidationReport
        Pydantic model with ``findings`` list + ``summary`` (counts + conforms).
    """
    # pyshacl stubs do not reflect the tuple return type
    try:
        pyshacl_result: tuple[bool, rdflib.Graph, str] = pyshacl.validate(  # pyright: ignore[reportAssignmentType]
            data_graph,
            shacl_graph=shapes_graph,
            inference=inference,
            do_owl_imports=False,
            meta_shacl=False,
        )
    except Exception as exc:
        # pyshacl can raise on malformed shapes (valid Turtle but nonsensical
        # SHACL), on internal engine bugs, or on unexpected input types. Wrap
        # so callers see "pyshacl engine error: ..." instead of an unattributed
        # ReportableRuntimeError.
        raise RuntimeError(f"pyshacl engine error: {exc}") from exc
    conforms, results_graph, _ = pyshacl_result

    # Parse findings via SPARQL
    findings: list[ValidationFinding] = []
    violation_count = 0
    warning_count = 0
    info_count = 0

    for raw_row in results_graph.query(_SPARQL):
        row = cast(rdflib.query.ResultRow, raw_row)
        focus_node = str(row.focusNode)
        severity_raw = str(row.severity)
        constraint = str(row.constraint)
        source_shape = str(row.shape) if row.shape is not None else None
        message = str(row.message) if row.message is not None else None

        severity_str = _strip_shacl_prefix(severity_raw)
        # Validate severity is one of the expected SHACL terms
        severity: Literal["Violation", "Warning", "Info"]
        if severity_str == "Warning":
            severity = "Warning"
        elif severity_str == "Info":
            severity = "Info"
        else:
            severity = "Violation"

        if severity == "Violation":
            violation_count += 1
        elif severity == "Warning":
            warning_count += 1
        elif severity == "Info":
            info_count += 1

        findings.append(
            ValidationFinding(
                focus_node=focus_node,
                severity=severity,
                constraint=constraint,
                source_shape=source_shape,
                message=message,
            )
        )

    summary = ValidationSummary(
        violation=violation_count,
        warning=warning_count,
        info=info_count,
        conforms=conforms,
    )
    return ValidationReport(findings=findings, summary=summary)
