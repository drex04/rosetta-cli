"""rosetta-validate: Validate RDF graphs against SHACL constraints."""

import sys

import click


@click.command()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(config):
    """Validate RDF graphs against SHACL constraints."""
    click.echo("Not yet implemented", err=True)
    sys.exit(1)
