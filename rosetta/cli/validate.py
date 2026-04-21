"""rosetta validate: Validate RDF graphs against SHACL constraints."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import rdflib

from rosetta.core.io import open_output
from rosetta.core.shacl_validate import validate_graph
from rosetta.core.shapes_loader import load_shapes_from_dir


@click.command(
    epilog="""Examples:

  rosetta validate output.jsonld rosetta/policies/

  rosetta -v validate output.jsonld rosetta/policies/ -o validation-report.json"""
)
@click.argument("data_file", type=click.Path(exists=True))
@click.argument("shapes_dir", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(dir_okay=False),
    help="Output file (default: stdout).",
)
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(
    data_file: str,
    shapes_dir: str,
    output: str | None,
    config: str | None,
) -> None:
    """Validate RDF graphs against SHACL constraints.

    DATA_FILE is a JSON-LD file to validate.
    SHAPES_DIR is a directory of SHACL Turtle (*.ttl) shape files.
    """
    try:
        # Load data graph (JSON-LD only)
        data_g = rdflib.Graph()
        data_g.parse(data_file, format="json-ld")

        # Build shapes graph from directory
        shapes_g = rdflib.Graph()
        try:
            shapes_g += load_shapes_from_dir(Path(shapes_dir))
        except ValueError as exc:
            raise click.UsageError(str(exc)) from exc

        # Run SHACL via shared helper
        report = validate_graph(data_g, shapes_g)

        with open_output(output) as fh:
            fh.write(report.model_dump_json(indent=2))
            fh.write("\n")

        sys.exit(0 if report.summary.conforms else 1)

    except click.UsageError:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
