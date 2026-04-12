"""rosetta-ingest: Ingest a national schema into the RDF store."""

import click

from rosetta.core.config import load_config


@click.command()
@click.option("--input", "-i", "input_path", default="-", show_default=True, help="Input file path (default: stdin).")
@click.option("--output", "-o", "output_path", default="-", show_default=True, help="Output file path (default: stdout).")
@click.option("--format", "-f", "fmt", default="turtle", show_default=True, help="Output RDF format.")
@click.option("--nation", "-n", default=None, help="Source nation code, e.g. NOR, DEU, USA.")
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(input_path, output_path, fmt, nation, config):
    """Ingest a national schema into the RDF store."""
    load_config(config)
    click.echo("Not yet implemented")
