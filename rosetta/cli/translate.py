"""rosetta-translate — translate class/slot titles in a LinkML schema using DeepL."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import click


@click.command()
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Input .linkml.yaml schema file.",
)
@click.option(
    "--source-lang",
    default="auto",
    show_default=True,
    help="Source language code (e.g. DE, FR) or 'auto'. Use 'EN' to skip translation.",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Output path for translated .linkml.yaml file.",
)
@click.option(
    "--deepl-key",
    default=None,
    help="DeepL API key (overrides DEEPL_API_KEY env var).",
)
def cli(
    input_path: Path,
    source_lang: str,
    output: Path,
    deepl_key: str | None,
) -> None:
    """Translate class and slot titles in a LinkML schema to English using DeepL."""
    try:
        from linkml_runtime.dumpers import yaml_dumper  # type: ignore[import-untyped]
        from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]
        from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]

        from rosetta.core.translation import translate_schema

        key = deepl_key or os.environ.get("DEEPL_API_KEY")
        if not key and not source_lang.upper().startswith("EN"):
            click.echo(
                "Error: DeepL API key required. Set DEEPL_API_KEY or use --deepl-key.",
                err=True,
            )
            raise SystemExit(1)

        schema = cast(
            "SchemaDefinition",
            yaml_loader.load(str(input_path), target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
        )
        result = translate_schema(
            schema,
            source_lang=source_lang,
            target_lang="EN-US",
            deepl_key=key,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        yaml_text: str = yaml_dumper.dumps(result)  # pyright: ignore[reportUnknownMemberType]
        output.write_text(yaml_text)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc
