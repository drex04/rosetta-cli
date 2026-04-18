"""rosetta-yarrrml-gen — generate linkml-map TransformSpec from SSSOM + LinkML schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import click
import yaml  # for YAMLError
from linkml_runtime.dumpers import yaml_dumper  # type: ignore[import-untyped]
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]
from linkml_runtime.utils.schemaview import SchemaView  # type: ignore[import-untyped]

from rosetta.core.accredit import parse_sssom_tsv
from rosetta.core.io import open_output
from rosetta.core.rml_runner import graph_to_jsonld, run_materialize
from rosetta.core.transform_builder import build_spec, filter_rows


def _resolve_source_format(cli_flag: str | None, source_def: SchemaDefinition) -> str:
    """Resolve source format from --source-format flag OR schema annotation (GA4 hybrid).

    Flag wins; else look at source_def.annotations['rosetta_source_format'].
    LinkML Annotation wraps the value; handle both raw-string and Annotation forms.
    Exit 1 if neither produces a valid format ('json'|'csv'|'xml').
    """
    if cli_flag:
        return cli_flag
    annotations = getattr(source_def, "annotations", {}) or {}
    annot = annotations.get("rosetta_source_format") if isinstance(annotations, dict) else None
    value = getattr(annot, "value", annot) if annot is not None else None
    if isinstance(value, str) and value in {"json", "csv", "xml"}:
        return value
    click.echo(
        (
            "Error: --source-format not provided and source schema lacks "
            "annotations.rosetta_source_format. Pass --source-format or re-run "
            "rosetta-ingest (which stamps the annotation on new schemas)."
        ),
        err=True,
    )
    sys.exit(1)


@click.command()
@click.option("--sssom", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--source-schema", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--master-schema", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option(
    "--source-format",
    type=click.Choice(["json", "csv", "xml"]),
    default=None,
    help=(
        "Source data format. If omitted, read from source schema's "
        "annotations.rosetta_source_format; exit 1 if neither is present."
    ),
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help=(
        "Write the TransformSpec YAML to a file. Note: --output controls only the "
        "TransformSpec YAML. When combined with --run, the JSON-LD still streams to "
        "stdout (or to --jsonld-output if provided)."
    ),
)
@click.option("--coverage-report", type=click.Path(), default=None)
@click.option("--include-manual", is_flag=True, default=False)
@click.option("--allow-empty", is_flag=True, default=False)
@click.option("--force", is_flag=True, default=False)
@click.option(
    "--run",
    is_flag=True,
    default=False,
    help="After generating the TransformSpec, compile to YARRRML and materialize JSON-LD.",
)
@click.option(
    "--data",
    type=click.Path(),
    default=None,
    help="Source data file (required with --run).",
)
@click.option(
    "--jsonld-output",
    type=click.Path(),
    default=None,
    help="Write JSON-LD to this file instead of stdout.",
)
@click.option(
    "--workdir",
    type=click.Path(),
    default=None,
    help="Directory to retain morph-kgc artifacts for debugging; ephemeral tempdir if omitted.",
)
@click.option(
    "--context-output",
    type=click.Path(),
    default=None,
    help="Optional JSON-LD @context dump path.",
)
def cli(
    sssom: str,
    source_schema: str,
    master_schema: str,
    source_format: str | None,
    output: str | None,
    coverage_report: str | None,
    include_manual: bool,
    allow_empty: bool,
    force: bool,
    run: bool,
    data: str | None,
    jsonld_output: str | None,
    workdir: str | None,
    context_output: str | None,
) -> None:
    """Generate a linkml-map TransformSpec from an approved SSSOM audit log."""
    # 0. Validate flag combinations before any I/O so no partial artifact lands
    #    on a guard failure.
    if run:
        if not data:
            click.echo("Error: --run requires --data", err=True)
            sys.exit(1)
        data_path = Path(data)
        if not data_path.is_file():
            click.echo(f"Error: --data path does not exist or is not a file: {data}", err=True)
            sys.exit(1)
        if output == "-" == jsonld_output:
            click.echo(
                "Error: --output - and --jsonld-output - both target stdout; "
                "use a file path for at least one.",
                err=True,
            )
            sys.exit(1)

    # 1. Parse SSSOM audit log
    try:
        rows = parse_sssom_tsv(Path(sssom))
    except Exception as exc:
        click.echo(f"Error reading SSSOM audit log {sssom}: {exc}", err=True)
        sys.exit(1)

    # 2. Load source schema
    try:
        source_def = cast(
            SchemaDefinition,
            yaml_loader.load(source_schema, target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
        )
    except (FileNotFoundError, OSError, yaml.YAMLError) as exc:
        click.echo(f"Error loading source schema {source_schema}: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error loading source schema {source_schema}: {exc}", err=True)
        sys.exit(1)

    # 3. Load master schema
    try:
        master_def = cast(
            SchemaDefinition,
            yaml_loader.load(master_schema, target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
        )
    except (FileNotFoundError, OSError, yaml.YAMLError) as exc:
        click.echo(f"Error loading master schema {master_schema}: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error loading master schema {master_schema}: {exc}", err=True)
        sys.exit(1)

    # 4. Resolve source format (CLI flag OR schema annotation; exit 1 on neither)
    effective_source_format = _resolve_source_format(source_format, source_def)

    # 5. Empty-filter guard: before running build_spec, check whether filtering leaves any rows.
    #    We store the result to pass as prefiltered= into build_spec — single filter pass.
    src_prefix = str(getattr(source_def, "default_prefix", "") or "")
    if not src_prefix:
        click.echo(f"Error: source schema {source_schema} lacks default_prefix", err=True)
        sys.exit(1)
    remaining, excluded = filter_rows(rows, src_prefix, include_manual)
    if not remaining and not allow_empty:
        mmc = "+MMC" if include_manual else ""
        msg = (
            f"SSSOM audit log has no rows after filtering for source schema "
            f"prefix '{src_prefix}:', predicates {{exact,close}}, and justification "
            f"{{HC{mmc}}}. Pass --allow-empty to proceed with an empty spec."
        )
        click.echo(msg, err=True)
        sys.exit(1)

    # 6. Build spec (prefiltered= avoids a second O(n) filter_rows pass)
    try:
        spec, coverage = build_spec(
            rows,
            source_def,
            master_def,
            source_schema_path=str(Path(source_schema).resolve()),
            target_schema_path=str(Path(master_schema).resolve()),
            include_manual=include_manual,
            force=force,
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

    # 9. Write TransformSpec to stdout or --output
    with open_output(output) as out:
        out.write(yaml_text)

    # 10. Optional coverage report
    if coverage_report:
        try:
            Path(coverage_report).write_text(coverage.model_dump_json(indent=2))
        except OSError as exc:
            click.echo(f"Error writing coverage report {coverage_report}: {exc}", err=True)
            sys.exit(1)

    # 11. Early return when --run is not set; --run flag combinations already
    #     validated in step 0.
    if not run:
        sys.exit(0)
    assert data is not None  # guaranteed by step 0
    data_path = Path(data)

    # 13. Compile TransformSpec → YARRRML via forked linkml-map compiler.
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

    # 14. Resolve workdir with writability probe.
    resolved_workdir: Path | None
    if workdir:
        resolved_workdir = Path(workdir).resolve()
        try:
            resolved_workdir.mkdir(parents=True, exist_ok=True)
            probe = resolved_workdir / ".writable_probe"
            probe.touch()
            probe.unlink()
        except OSError as exc:
            click.echo(f"Error: --workdir {resolved_workdir} not writable: {exc}", err=True)
            sys.exit(1)
    else:
        resolved_workdir = None

    # 15. Materialize + frame as JSON-LD.
    context_out_path = Path(context_output).resolve() if context_output else None
    try:
        with run_materialize(yarrrml_text, data_path, resolved_workdir) as graph:
            if len(graph) == 0:
                click.echo(
                    "Warning: materialization produced 0 triples; check data file and mappings",
                    err=True,
                )
            jsonld_bytes = graph_to_jsonld(
                graph, Path(master_schema), context_output=context_out_path
            )
    except (
        OSError,
        PermissionError,
        FileNotFoundError,
        json.JSONDecodeError,
        yaml.YAMLError,
        UnicodeDecodeError,
        RuntimeError,
        ValueError,
    ) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # 16. Write JSON-LD to file or stdout.
    if jsonld_output:
        try:
            Path(jsonld_output).write_bytes(jsonld_bytes)
        except OSError as exc:
            click.echo(f"Error writing JSON-LD output {jsonld_output}: {exc}", err=True)
            sys.exit(1)
    else:
        click.get_binary_stream("stdout").write(jsonld_bytes)

    sys.exit(0)
