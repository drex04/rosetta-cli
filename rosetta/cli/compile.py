"""rosetta compile — compile SSSOM audit log to YARRRML mapping artifact."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import click
import yaml  # for YAMLError
from linkml_runtime.dumpers import yaml_dumper  # type: ignore[import-untyped]
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]
from linkml_runtime.utils.schemaview import SchemaView  # type: ignore[import-untyped]

from rosetta.core.io import open_output
from rosetta.core.ledger import parse_sssom_tsv
from rosetta.core.transform_builder import build_spec, filter_rows


def _resolve_source_format(source_def: SchemaDefinition) -> str:
    """Resolve source format from source schema annotation.

    Reads source_def.annotations['rosetta_source_format'].
    LinkML Annotation wraps the value; handle both raw-string and Annotation forms.
    Exit 1 if annotation is missing or not a valid format ('json'|'csv'|'xml').
    """
    annotations = getattr(source_def, "annotations", {}) or {}
    annot = annotations.get("rosetta_source_format") if isinstance(annotations, dict) else None
    value = getattr(annot, "value", annot) if annot is not None else None
    if isinstance(value, str) and value in {"json", "csv", "xml"}:
        return value
    click.echo(
        (
            "Error: source schema lacks annotations.rosetta_source_format. "
            "Re-run rosetta ingest (which stamps the annotation on new schemas) "
            "to produce a schema with this annotation."
        ),
        err=True,
    )
    sys.exit(1)


@click.command(
    epilog="""Examples:

  rosetta compile audit.sssom.tsv --source-schema src.yaml --master-schema master.yaml -o map.yaml

  rosetta -v compile audit.sssom.tsv --source-schema src.yaml --master-schema master.yaml \\
      -o mapping.yaml --spec-output spec.yaml"""
)
@click.argument("sssom_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--source-schema",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="LinkML source schema (.yaml).",
)
@click.option(
    "--master-schema",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="LinkML master/target schema (.yaml).",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Write YARRRML output to a file. Defaults to stdout.",
)
@click.option(
    "--coverage-report",
    type=click.Path(),
    default=None,
    help="Optional path to write a coverage JSON report.",
)
@click.option(
    "--spec-output",
    type=click.Path(),
    default=None,
    help="Optional path to write the intermediate TransformSpec YAML.",
)
def cli(
    sssom_file: str,
    source_schema: str,
    master_schema: str,
    output: str | None,
    coverage_report: str | None,
    spec_output: str | None,
) -> None:
    """Compile an SSSOM audit log to a YARRRML mapping artifact.

    SSSOM_FILE is the path to the SSSOM audit log TSV produced by rosetta ledger.
    The primary output is YARRRML (the executable artifact consumed by rosetta transform).
    Use --spec-output to also write the intermediate TransformSpec YAML.
    """
    # 1. Parse SSSOM audit log
    try:
        rows = parse_sssom_tsv(Path(sssom_file))
    except Exception as exc:
        click.echo(f"Error reading SSSOM audit log {sssom_file}: {exc}", err=True)
        sys.exit(1)

    # 2. Load source schema
    try:
        source_def = cast(
            SchemaDefinition,
            yaml_loader.load(source_schema, target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
        )
    except Exception as exc:
        click.echo(f"Error loading source schema {source_schema}: {exc}", err=True)
        sys.exit(1)

    # 3. Load master schema
    try:
        master_def = cast(
            SchemaDefinition,
            yaml_loader.load(master_schema, target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
        )
    except Exception as exc:
        click.echo(f"Error loading master schema {master_schema}: {exc}", err=True)
        sys.exit(1)

    # 4. Resolve source format from schema annotation (no CLI flag; exit 1 if missing)
    effective_source_format = _resolve_source_format(source_def)

    # 5. Empty-filter guard: HC-only (include_manual=False hardcoded per D-20-11).
    #    Store prefiltered result to avoid a second O(n) pass in build_spec.
    src_prefix = str(getattr(source_def, "default_prefix", "") or "")
    if not src_prefix:
        click.echo(f"Error: source schema {source_schema} lacks default_prefix", err=True)
        sys.exit(1)
    remaining, excluded = filter_rows(rows, src_prefix, include_manual=False)
    if not remaining:
        msg = (
            f"SSSOM audit log has no rows after filtering for source schema "
            f"prefix '{src_prefix}:', predicates {{exact,close}}, and justification {{HC}}. "
            f"Ensure the audit log contains HC-justified rows for this source schema."
        )
        click.echo(msg, err=True)
        sys.exit(1)

    # 6. Build TransformSpec (prefiltered= avoids a second O(n) filter_rows pass)
    try:
        spec, coverage = build_spec(
            rows,
            source_def,
            master_def,
            source_schema_path=str(Path(source_schema).resolve()),
            target_schema_path=str(Path(master_schema).resolve()),
            include_manual=False,
            force=False,
            prefiltered=(remaining, excluded),
        )
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # 7. Annotate spec with effective source format (16-02 consumer contract)
    spec.comments = [f"rosetta:source_format={effective_source_format}"]

    # 8. Serialize spec to YAML
    try:
        yaml_text: str = yaml_dumper.dumps(spec)  # pyright: ignore[reportUnknownMemberType]
    except Exception as exc:
        click.echo(f"Error serializing TransformSpec: {exc}", err=True)
        sys.exit(1)

    # 9. Optional: write intermediate TransformSpec YAML to --spec-output
    if spec_output:
        try:
            Path(spec_output).write_text(yaml_text)
        except OSError as exc:
            click.echo(f"Error writing TransformSpec to {spec_output}: {exc}", err=True)
            sys.exit(1)

    # 10. Optional coverage report
    if coverage_report:
        try:
            Path(coverage_report).write_text(coverage.model_dump_json(indent=2))
        except OSError as exc:
            click.echo(f"Error writing coverage report {coverage_report}: {exc}", err=True)
            sys.exit(1)

    # 11. Compile TransformSpec → YARRRML via forked linkml-map compiler.
    try:
        from linkml_map.compiler.yarrrml_compiler import (
            YarrrmlCompiler,  # type: ignore[import-untyped]
        )

        compiler = YarrrmlCompiler(
            source_schemaview=SchemaView(str(Path(source_schema).resolve())),
            target_schemaview=SchemaView(str(Path(master_schema).resolve())),
        )
        yarrrml_text: str = compiler.compile(spec).serialization  # pyright: ignore[reportUnknownMemberType]
    except (OSError, PermissionError, FileNotFoundError, yaml.YAMLError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error compiling YARRRML: {exc}", err=True)
        sys.exit(1)

    # 12. Write YARRRML to stdout or --output
    try:
        with open_output(output) as out:
            out.write(yarrrml_text)
    except OSError as exc:
        click.echo(f"Error writing YARRRML output: {exc}", err=True)
        sys.exit(1)

    sys.exit(0)
