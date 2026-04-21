"""rosetta-ingest — normalise a schema file to LinkML YAML."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from rosetta.core.io import open_output
from rosetta.core.normalize import (
    check_prefix_collision,
    detect_format,
    normalize_schema,
    stamp_slot_paths,
    stamp_source_format,
)


@click.command()
@click.argument("schema_file", type=click.Path(exists=True))
@click.option(
    "--schema-format",
    "-f",
    "fmt",
    default=None,
    help="json-schema | openapi | xsd | csv | tsv | json-sample | rdfs",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(path_type=Path),
    help="Output path for .linkml.yaml file (default: stdout).",
)
@click.option(
    "--config",
    "-c",
    default=None,
    type=click.Path(exists=True),
    help="Path to rosetta.toml config file.",
)
def cli(
    schema_file: str,
    fmt: str | None,
    output: Path | None,
    config: str | None,
) -> None:
    """Normalise a schema file to LinkML YAML."""
    try:
        from linkml_runtime.dumpers import yaml_dumper  # type: ignore[import-untyped]

        input_path = Path(schema_file)
        schema_name = input_path.stem
        resolved_fmt = fmt if fmt is not None else detect_format(input_path)
        schema_def = normalize_schema(input_path, fmt=resolved_fmt, schema_name=schema_name)
        stamp_source_format(schema_def, resolved_fmt)
        stamp_slot_paths(schema_def, resolved_fmt)
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            try:
                check_prefix_collision(output, schema_def)
            except ValueError as exc:
                click.echo(f"Error: {exc}", err=True)
                sys.exit(1)
        with open_output(output) as fh:
            fh.write(yaml_dumper.dumps(schema_def))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
