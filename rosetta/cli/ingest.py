"""rosetta ingest — normalise one or more schema files to LinkML YAML.

Optionally translates titles/descriptions via DeepL (--translate --lang),
and optionally normalises a master ontology and generates SHACL shapes
(--master).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]

from rosetta.core.io import open_output, resolve_output_paths
from rosetta.core.normalize import (
    check_prefix_collision,
    detect_format,
    normalize_schema,
    stamp_slot_paths,
    stamp_source_format,
)


@click.command(
    epilog="""Examples:

  rosetta ingest schema.json -o output.linkml.yaml

  rosetta ingest a.json b.xsd -o out/

  rosetta ingest schema.json --translate --lang DE -o output.linkml.yaml

  rosetta ingest schema.xsd --master ontology.ttl -o out/

  rosetta -v ingest schema.xsd --schema-format xsd -o output.linkml.yaml"""
)
@click.argument("schema_files", nargs=-1, required=True, type=click.Path(exists=True))
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
    help="Output path: file (single input), directory (multiple inputs), or omit for stdout.",
)
@click.option(
    "--translate",
    is_flag=True,
    default=False,
    help="Translate schema titles/descriptions to English via DeepL.",
)
@click.option(
    "--lang",
    default="EN",
    show_default=True,
    help="Source language code (e.g. DE, FR). EN is a no-op passthrough.",
)
@click.option(
    "--master",
    "master_path",
    default=None,
    type=click.Path(exists=True),
    help="Master ontology file (.ttl/.owl) — normalises and generates SHACL shapes.",
)
def cli(
    schema_files: tuple[str, ...],
    fmt: str | None,
    output: Path | None,
    translate: bool,
    lang: str,
    master_path: str | None,
) -> None:
    """Normalise one or more schema files to LinkML YAML."""
    try:
        from linkml_runtime.dumpers import yaml_dumper  # type: ignore[import-untyped]

        # --- Validate --schema-format with multiple inputs ---
        if fmt is not None and len(schema_files) > 1:
            # Detect formats for all inputs; error if they differ
            formats = [detect_format(Path(sf)) for sf in schema_files]
            if len(set(formats)) > 1:
                raise click.UsageError(
                    "--schema-format with mixed-format inputs is ambiguous; omit for auto-detect."
                )

        # --- Resolve output paths ---
        pairs = resolve_output_paths(schema_files, output)

        # --- Process --master BEFORE source schemas ---
        master_out_path: Path | None = None
        if master_path is not None:
            master_file = Path(master_path)
            master_stem = master_file.stem
            master_fmt = detect_format(master_file)
            if master_fmt not in ("ttl", "owl", "rdfs"):
                raise click.UsageError(
                    f"--master requires a TTL/OWL/RDFS file; detected format: {master_fmt}"
                )

            master_def = normalize_schema(master_file, fmt=master_fmt, schema_name=master_stem)
            stamp_source_format(master_def, master_fmt)
            stamp_slot_paths(master_def, master_fmt)

            if translate and not lang.upper().startswith("EN"):
                master_def = _do_translate(master_def, lang)

            # Determine where the master output file lives
            if output is not None and str(output) != "-":
                if output.is_dir() or str(output).endswith(("/", "\\")):
                    master_out_dir = output
                else:
                    # single-file -o means the master lands beside it
                    master_out_dir = output.parent
            else:
                master_out_dir = Path()
            master_out_dir.mkdir(parents=True, exist_ok=True)
            master_out_path = master_out_dir / f"{master_stem}.linkml.yaml"

            try:
                check_prefix_collision(master_out_path, master_def)
            except ValueError as exc:
                click.echo(f"Error: {exc}", err=True)
                sys.exit(1)

            with open_output(master_out_path) as fh:
                _ = fh.write(yaml_dumper.dumps(master_def))
            click.echo(f"Master written: {master_out_path}", err=True)

            # Generate SHACL from the written file
            _write_shacl(master_out_path)

            # Task 4: scaffold rosetta.toml if absent
            _scaffold_rosetta_toml(master_out_path)

        # --- Process source schemas ---
        for input_path, out_path in pairs:
            resolved_fmt = fmt if fmt is not None else detect_format(input_path)
            schema_name = input_path.stem
            schema_def = normalize_schema(input_path, fmt=resolved_fmt, schema_name=schema_name)
            stamp_source_format(schema_def, resolved_fmt)
            stamp_slot_paths(schema_def, resolved_fmt)

            if translate and not lang.upper().startswith("EN"):
                schema_def = _do_translate(schema_def, lang)

            if out_path is not None:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    check_prefix_collision(out_path, schema_def)
                except ValueError as exc:
                    click.echo(f"Error: {exc}", err=True)
                    sys.exit(1)

            with open_output(out_path) as fh:
                _ = fh.write(yaml_dumper.dumps(schema_def))

    except SystemExit:
        raise
    except click.UsageError:
        raise
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _do_translate(schema_def: SchemaDefinition, lang: str) -> SchemaDefinition:
    """Translate *schema_def* from *lang* to EN-US via DeepL env key."""
    from rosetta.core.translation import translate_schema  # type: ignore[import-untyped]

    deepl_key = os.environ.get("DEEPL_API_KEY")
    if not deepl_key:
        raise click.UsageError("DEEPL_API_KEY environment variable required for --translate.")
    result: SchemaDefinition = translate_schema(
        schema_def, source_lang=lang, target_lang="EN-US", deepl_key=deepl_key
    )
    return result


def _write_shacl(linkml_path: Path) -> None:
    """Generate SHACL shapes from *linkml_path* and write alongside it."""
    from rosetta.core.shacl_generator import generate_shacl

    shacl_path = linkml_path.with_suffix("").with_suffix(".shacl.ttl")
    turtle = generate_shacl(linkml_path, closed=True)
    shacl_path.write_text(turtle, encoding="utf-8")  # pyright: ignore[reportUnusedCallResult]
    click.echo(f"SHACL shapes written: {shacl_path}", err=True)


def _scaffold_rosetta_toml(master_out_path: Path) -> None:
    """Write a minimal rosetta.toml in cwd if one does not already exist."""
    toml_path = Path("rosetta.toml")
    if toml_path.exists():
        click.echo("rosetta.toml already exists — skipping scaffold.", err=True)
        return

    shacl_path = master_out_path.with_suffix("").with_suffix(".shacl.ttl")
    content = (
        "# rosetta.toml — auto-generated by `rosetta ingest --master`\n"
        "\n"
        "[master]\n"
        f'linkml = "{master_out_path}"\n'
        f'shacl  = "{shacl_path}"\n'
    )
    toml_path.write_text(content, encoding="utf-8")  # pyright: ignore[reportUnusedCallResult]
    click.echo(f"Scaffolded rosetta.toml -> {toml_path}", err=True)
