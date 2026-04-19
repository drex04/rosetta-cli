"""rosetta-validate: Validate RDF graphs against SHACL constraints."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import rdflib

from rosetta.core.io import open_output
from rosetta.core.shacl_validate import validate_graph
from rosetta.core.shapes_loader import load_shapes_from_dir


def _resolve_data_format(data_path: str, data_format: str) -> str:
    """Resolve the rdflib parser format for ``--data``.

    ``data_format`` is constrained by Click ``Choice`` to one of
    ``"turtle"``, ``"json-ld"``, ``"auto"``. The ``"auto"`` value picks
    a format from the file suffix, falling back to ``"turtle"`` for any
    unknown extension to preserve historical behavior.
    """
    if data_format == "turtle":
        return "turtle"
    if data_format == "json-ld":
        return "json-ld"
    # auto
    suffix = Path(data_path).suffix.lower()
    if suffix == ".ttl":
        return "turtle"
    if suffix in (".jsonld", ".json", ".json-ld"):
        return "json-ld"
    return "turtle"


@click.command()
@click.option(
    "--data",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="RDF data file to validate (Turtle or JSON-LD).",
)
@click.option(
    "--data-format",
    type=click.Choice(["turtle", "json-ld", "auto"]),
    default="auto",
    help=(
        "Input data format. 'auto' picks by suffix: .ttl=turtle, "
        ".jsonld/.json/.json-ld=json-ld, fallback=turtle."
    ),
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
    data_format: str,
    shapes: str | None,
    shapes_dir: str | None,
    output: str | None,
    config: str | None,
) -> None:
    """Validate RDF graphs against SHACL constraints."""
    try:
        if shapes is None is shapes_dir:
            raise click.UsageError("At least one of --shapes or --shapes-dir must be provided.")

        # Load data graph (Turtle or JSON-LD)
        fmt = _resolve_data_format(data, data_format)
        data_g = rdflib.Graph()
        data_g.parse(data, format=fmt)

        # Build shapes graph
        shapes_g = rdflib.Graph()
        if shapes is not None:
            shapes_g.parse(shapes, format="turtle")
        if shapes_dir is not None:
            shapes_g += load_shapes_from_dir(Path(shapes_dir))

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
