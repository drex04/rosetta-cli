"""rosetta-embed: Embed ontology terms into vector space."""

import click


@click.command()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(config):
    """Embed ontology terms into vector space for similarity search."""
    click.echo("Not yet implemented")
