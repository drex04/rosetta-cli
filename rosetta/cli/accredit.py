"""rosetta-accredit: Accredit mappings for operational use."""
import click


@click.command()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(config):
    """Accredit approved mappings for operational deployment."""
    click.echo("Not yet implemented")
