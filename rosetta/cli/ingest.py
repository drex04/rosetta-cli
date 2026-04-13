"""rosetta-ingest: Ingest a national schema into the RDF store."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from rosetta.core.config import load_config
from rosetta.core.ingest_rdf import fields_to_graph
from rosetta.core.io import open_input, open_output
from rosetta.core.parsers import dispatch_parser
from rosetta.core.rdf_utils import save_graph


@click.command()
@click.option(
    "--input",
    "-i",
    "input_path",
    default="-",
    show_default=True,
    help="Input file path (default: stdin).",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    default="-",
    show_default=True,
    help="Output file path (default: stdout).",
)
@click.option(
    "--format",
    "-f",
    "fmt",
    default="turtle",
    show_default=True,
    type=click.Choice(["turtle", "n3", "nt", "xml", "json-ld"], case_sensitive=False),
    help="Output RDF format.",
)
@click.option(
    "--input-format",
    "input_fmt",
    default=None,
    type=click.Choice(["csv", "json-schema", "openapi"], case_sensitive=False),
    help="Input format (auto-detected from extension if omitted).",
)
@click.option("--nation", "-n", required=True, help="Nation code (e.g. NOR, DEU, USA). Required.")
@click.option(
    "--max-sample-rows",
    "max_sample_rows",
    default=1000,
    show_default=True,
    help="Max rows read from CSV for stats computation.",
)
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(input_path, output_path, fmt, input_fmt, nation, max_sample_rows, config):
    """Ingest a national schema into the RDF store."""
    load_config(config)
    # Guard: stdin without explicit format
    if input_path == "-" and input_fmt is None:
        click.echo("--input-format required when reading from stdin", err=True)
        sys.exit(1)
    try:
        path = Path(input_path) if input_path != "-" else None
        with open_input(input_path) as src:
            fields, slug = dispatch_parser(src, path, input_fmt, nation, max_sample_rows)
        g = fields_to_graph(fields, nation, slug)
        with open_output(output_path) as out:
            save_graph(g, out, fmt)
    except Exception as e:
        click.echo(str(e), err=True)
        sys.exit(1)
