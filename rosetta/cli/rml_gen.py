"""rosetta-rml-gen: Generate RML mapping documents."""

import sys

import click


@click.command()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(config):
    """Generate RML mapping documents from approved suggestions."""
    click.echo("Not yet implemented", err=True)
    sys.exit(1)
