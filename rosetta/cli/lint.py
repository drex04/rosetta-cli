"""rosetta-lint: Lint mapping files against SHACL shapes."""
import click


@click.command()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(config):
    """Lint mapping files against SHACL shapes and policy rules."""
    click.echo("Not yet implemented")
