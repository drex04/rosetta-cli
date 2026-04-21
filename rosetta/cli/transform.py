"""rosetta transform — materialize a YARRRML mapping against a data file into JSON-LD."""

from __future__ import annotations

import json
import sys
from contextlib import suppress
from pathlib import Path

import click
import yaml  # for YAMLError

from rosetta.core.io import open_output
from rosetta.core.rml_runner import graph_to_jsonld, run_materialize


@click.command(
    epilog="""Examples:

  rosetta transform mapping.yarrrml.yaml data.json \\
      --master-schema master.linkml.yaml -o output.jsonld

  rosetta -v transform mapping.yarrrml.yaml data.json --master-schema master.linkml.yaml \\
      --validate rosetta/policies/ -o output.jsonld"""
)
@click.argument("mapping_file", type=click.Path(exists=True, dir_okay=False))
@click.argument("source_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False),
    default=None,
    help=(
        "Write JSON-LD to this file. Defaults to stdout ('-'). "
        "Mutually exclusive with --validate-report stdout."
    ),
)
@click.option(
    "--master-schema",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to the master LinkML schema (.yaml/.yml). Required for JSON-LD context generation.",
)
@click.option(
    "--validate",
    type=click.Path(exists=True, file_okay=False),
    default=None,
    help=(
        "Directory containing SHACL shape .ttl files. When provided, validates "
        "the in-memory RDF graph before JSON-LD emission. On any violation: "
        "write the validation report (stderr or --validate-report) and exit 1 "
        "with no JSON-LD output."
    ),
)
@click.option(
    "--workdir",
    type=click.Path(),
    default=None,
    help="Directory to retain morph-kgc artifacts for debugging; ephemeral tempdir if omitted.",
)
@click.option(
    "--context-output",
    type=click.Path(dir_okay=False),
    default=None,
    help="Optional path for JSON-LD @context dump.",
)
@click.option(
    "--validate-report",
    type=click.Path(dir_okay=False),
    default=None,
    help=(
        "Path to write the SHACL validation report JSON. If '-', writes to "
        "stdout (mutually exclusive with JSON-LD stdout output). If omitted, "
        "the report is written to stderr on violation."
    ),
)
def cli(
    mapping_file: str,
    source_file: str,
    output: str | None,
    master_schema: str,
    validate: str | None,
    workdir: str | None,
    context_output: str | None,
    validate_report: str | None,
) -> None:
    """Materialize a YARRRML mapping against SOURCE_FILE and emit JSON-LD.

    MAPPING_FILE is the YARRRML mapping file (.yml/.yaml) produced by
    ``rosetta compile`` or written manually.

    SOURCE_FILE is the data file to map (JSON, CSV, or XML).
    """
    # 0. Stdout collision guard: reject simultaneous stdout targets.
    #    --output defaulting to None means stdout; validate-report "-" also targets stdout.
    output_is_stdout = output is None or output == "-"
    report_is_stdout = validate_report == "-"
    if output_is_stdout and report_is_stdout:
        raise click.UsageError(
            "--output (stdout) and --validate-report - both target stdout; "
            "use a file path for one of them."
        )

    # 1. Read YARRRML mapping file.
    try:
        yarrrml_text = Path(mapping_file).read_text(encoding="utf-8")
    except OSError as exc:
        click.echo(f"Error reading mapping file {mapping_file}: {exc}", err=True)
        sys.exit(1)

    # 2. Resolve workdir with writability probe.
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

    # 3. Materialize + (optionally validate) + frame as JSON-LD.
    data_path = Path(source_file)
    master_schema_path = Path(master_schema).resolve()
    context_out_path = Path(context_output).resolve() if context_output else None

    try:
        with run_materialize(yarrrml_text, data_path, resolved_workdir) as graph:
            if len(graph) == 0:
                click.echo(
                    "Warning: materialization produced 0 triples; check data file and mappings",
                    err=True,
                )

            # 3a. Optional SHACL validation BEFORE JSON-LD framing/emission so
            #     a violation aborts with no partial output written anywhere.
            if validate is not None:
                from rosetta.core.shacl_validate import validate_graph
                from rosetta.core.shapes_loader import load_shapes_from_dir

                try:
                    shapes_g = load_shapes_from_dir(Path(validate))
                except ValueError as exc:
                    raise click.UsageError(str(exc)) from exc

                report = validate_graph(graph, shapes_g)
                if not report.summary.conforms:
                    report_json = report.model_dump_json(indent=2)
                    if validate_report is not None:
                        with open_output(validate_report) as fh:
                            fh.write(report_json)
                            fh.write("\n")
                    else:
                        click.echo(report_json, err=True)
                    click.echo(
                        f"SHACL validation failed: "
                        f"{report.summary.violation} violation(s), "
                        f"{report.summary.warning} warning(s). "
                        f"JSON-LD emission blocked.",
                        err=True,
                    )
                    sys.exit(1)

            # 3b. Frame graph as JSON-LD.
            jsonld_bytes = graph_to_jsonld(
                graph, master_schema_path, context_output=context_out_path
            )

    except SystemExit:
        raise
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

    # 4. Write JSON-LD to file or stdout.
    if output and output != "-":
        try:
            Path(output).write_bytes(jsonld_bytes)
        except OSError as exc:
            click.echo(f"Error writing JSON-LD output {output}: {exc}", err=True)
            sys.exit(1)
    else:
        with suppress(BrokenPipeError):
            click.get_binary_stream("stdout").write(jsonld_bytes)

    sys.exit(0)
