"""rosetta-validate: Validate RDF graphs against SHACL constraints."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, cast

import click
import pyshacl
import rdflib
import rdflib.query

from rosetta.core.io import open_output
from rosetta.core.models import ValidationFinding, ValidationReport, ValidationSummary
from rosetta.core.shapes_loader import load_shapes_from_dir

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


@click.command()
@click.option(
    "--data",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="RDF Turtle file to validate.",
)
@click.option(
    "--shapes",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Single SHACL shapes Turtle file.",
)
@click.option(
    "--shapes-dir",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Directory; loads all *.ttl files as shapes.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(dir_okay=False),
    help="Output file (default: stdout).",
)
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(
    data: str,
    shapes: str | None,
    shapes_dir: str | None,
    output: str | None,
    config: str | None,
) -> None:
    """Validate RDF graphs against SHACL constraints."""
    try:
        if shapes is None is shapes_dir:
            raise click.UsageError("At least one of --shapes or --shapes-dir must be provided.")

        # Load data graph
        data_g = rdflib.Graph()
        data_g.parse(data, format="turtle")

        # Build shapes graph
        shapes_g = rdflib.Graph()
        if shapes is not None:
            shapes_g.parse(shapes, format="turtle")
        if shapes_dir is not None:
            shapes_g += load_shapes_from_dir(Path(shapes_dir))

        # Run pySHACL — pyshacl stubs do not reflect the tuple return type
        pyshacl_result: tuple[bool, rdflib.Graph, str] = pyshacl.validate(  # pyright: ignore[reportAssignmentType]
            data_g,
            shacl_graph=shapes_g,
            do_owl_imports=False,
            meta_shacl=False,
        )
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
            if severity_str not in ("Violation", "Warning", "Info"):
                severity_str = "Violation"
            severity = cast(Literal["Violation", "Warning", "Info"], severity_str)

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
        report = ValidationReport(findings=findings, summary=summary)

        with open_output(output) as fh:
            fh.write(report.model_dump_json(indent=2))
            fh.write("\n")

        sys.exit(0 if conforms else 1)

    except click.UsageError:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
