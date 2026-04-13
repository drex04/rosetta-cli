"""rosetta-provenance: Record and query provenance metadata."""

import sys

import click


@click.command()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(config):
    """Record and query provenance metadata for mapping decisions."""
    click.echo("Not yet implemented", err=True)
    sys.exit(1)
