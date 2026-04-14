"""rosetta-ingest — normalise a schema file to LinkML YAML."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from rosetta.core.normalize import normalize_schema


@click.command()
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Input schema file.",
)
@click.option(
    "--format",
    "fmt",
    default=None,
    help="json-schema | openapi | xsd | csv | tsv | json-sample | rdfs",
)
@click.option(
    "--schema-name",
    default=None,
    help="Schema identifier (default: filename stem).",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Output path for .linkml.yaml file.",
)
def cli(
    input_path: Path,
    fmt: str | None,
    schema_name: str | None,
    output: Path,
) -> None:
    """Normalise a schema file to LinkML YAML."""
    try:
        from linkml_runtime.dumpers import yaml_dumper  # type: ignore[import-untyped]

        schema_def = normalize_schema(input_path, fmt=fmt, schema_name=schema_name)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(yaml_dumper.dumps(schema_def))
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
