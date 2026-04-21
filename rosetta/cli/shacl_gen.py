"""rosetta-shacl-gen: Generate SHACL shapes from a master LinkML schema."""

from __future__ import annotations

import sys

import click

from rosetta.core.io import open_output
from rosetta.core.shacl_generator import generate_shacl


@click.command()
@click.argument(
    "schema_file",
    type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(dir_okay=False),
    help="Output Turtle file (default: stdout).",
)
@click.option(
    "--open",
    "open_flag",
    is_flag=True,
    default=False,
    help=(
        "Emit open-world shapes (no `sh:closed true`, no `sh:ignoredProperties`). "
        "Default: closed-world with prov:wasGeneratedBy, prov:wasAttributedTo, "
        "dcterms:created, dcterms:source, and rdf:type ignored."
    ),
)
@click.option(
    "--config",
    "-c",
    default=None,
    type=click.Path(dir_okay=False),
    help="Path to rosetta.toml.",
)
def cli(
    schema_file: str,
    output: str | None,
    open_flag: bool,
    config: str | None,
) -> None:
    """Generate SHACL shapes (Turtle) from a master LinkML YAML schema.

    By default, emits closed-world shapes (`sh:closed true`) with a baked-in
    `sh:ignoredProperties` list covering prov:wasGeneratedBy, prov:wasAttributedTo,
    dcterms:created, dcterms:source, and rdf:type. Pass --open to emit open-world
    shapes without these closures.
    """
    del config  # Reserved for parity with other CLIs; no settings consumed yet.
    try:
        turtle = generate_shacl(schema_file, closed=not open_flag)
        with open_output(output) as fh:
            fh.write(turtle)
            if not turtle.endswith("\n"):
                fh.write("\n")
        sys.exit(0)
    except click.UsageError:
        raise
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
