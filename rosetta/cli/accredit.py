"""rosetta-accredit: Accredit mappings for operational use."""

import sys

import click


@click.command()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(config):
    """Accredit approved mappings for operational deployment."""
    click.echo("Not yet implemented", err=True)
    sys.exit(1)
