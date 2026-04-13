"""rosetta-rml-gen: Generate RML/FnML Turtle from approved mapping decisions."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from rosetta.core.io import open_output
from rosetta.core.models import MappingDecision
from rosetta.core.rml_builder import build_rml_graph


@click.command()
@click.option(
    "--decisions",
    required=True,
    type=click.Path(exists=True),
    help="Approved decisions JSON (source_uri → {target_uri, ...})",
)
@click.option(
    "--source-file",
    required=True,
    help="Data file path to embed in rml:logicalSource (not read, just referenced)",
)
@click.option(
    "--source-format",
    default="json",
    show_default=True,
    type=click.Choice(["json", "csv"]),
    help="RML reference formulation (json=JSONPath, csv=CSV)",
)
@click.option(
    "--base-uri",
    default="http://rosetta.interop/record",
    show_default=True,
    help="Subject template base URI",
)
@click.option("--output", default=None, type=click.Path(), help="Output file (default: stdout)")
def cli(
    decisions: str,
    source_file: str,
    source_format: str,
    base_uri: str,
    output: str | None,
) -> None:
    """Generate RML/FnML Turtle from approved mapping decisions."""
    try:
        data: Any = json.loads(Path(decisions).read_text())
    except Exception as e:
        click.echo(f"Error reading decisions: {e}", err=True)
        sys.exit(1)

    if not isinstance(data, dict):
        click.echo("Error: decisions file must be a JSON object.", err=True)
        sys.exit(1)

    raw: dict[str, Any] = data

    if not raw:
        click.echo("Error: decisions file is empty.", err=True)
        sys.exit(1)

    parsed: list[MappingDecision] = []
    for src_uri, props in raw.items():
        if "target_uri" not in props:
            click.echo(f"Error: missing 'target_uri' for {src_uri}", err=True)
            sys.exit(1)
        try:
            parsed.append(MappingDecision(source_uri=src_uri, **props))
        except Exception as e:
            click.echo(f"Error: invalid decision for {src_uri}: {e}", err=True)
            sys.exit(1)

    try:
        g = build_rml_graph(parsed, source_file, source_format, base_uri)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    with open_output(output) as fh:
        fh.write(g.serialize(format="turtle"))
