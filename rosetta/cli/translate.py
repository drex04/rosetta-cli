"""rosetta translate — translate class/slot titles in a LinkML schema using DeepL."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import cast

import click


@click.command(
    epilog="""Examples:

  rosetta translate schema.linkml.yaml -o schema.en.linkml.yaml

  rosetta -v translate schema.linkml.yaml --source-lang DE -o schema.en.linkml.yaml"""
)
@click.argument("schema_file", type=click.Path(exists=True))
@click.option(
    "--source-lang",
    default="auto",
    show_default=True,
    help="Source language code (e.g. DE, FR) or 'auto'. Use 'EN' to skip translation.",
)
@click.option(
    "-o",
    "--output",
    "output",
    default=None,
    type=click.Path(),
    help="Output path for translated .linkml.yaml file (default: stdout).",
)
@click.option(
    "--deepl-key",
    default=None,
    help="DeepL API key (overrides DEEPL_API_KEY env var).",
)
def cli(
    schema_file: str,
    source_lang: str,
    output: str | None,
    deepl_key: str | None,
) -> None:
    """Translate class and slot titles in a LinkML schema to English using DeepL."""
    try:
        from linkml_runtime.dumpers import yaml_dumper  # type: ignore[import-untyped]
        from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]
        from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]

        from rosetta.core.translation import translate_schema

        resolved_key = deepl_key or os.environ.get("DEEPL_API_KEY")
        if not resolved_key and not source_lang.upper().startswith("EN"):
            click.echo(
                "Error: DeepL API key required. Set DEEPL_API_KEY or use --deepl-key.",
                err=True,
            )
            raise SystemExit(1)

        input_path = Path(schema_file)
        schema = cast(
            "SchemaDefinition",
            yaml_loader.load(str(input_path), target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
        )
        result = translate_schema(
            schema,
            source_lang=source_lang,
            target_lang="EN-US",
            deepl_key=resolved_key,
        )
        yaml_text: str = yaml_dumper.dumps(result)  # pyright: ignore[reportUnknownMemberType]

        if output is None:
            sys.stdout.write(yaml_text)
        else:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(yaml_text)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc
