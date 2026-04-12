"""rosetta-suggest: Suggest ontology mappings for schema fields."""
import click


@click.command()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(config):
    """Suggest ontology mappings for schema fields using embeddings."""
    click.echo("Not yet implemented")
