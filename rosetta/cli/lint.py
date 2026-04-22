"""rosetta lint: Validate unit and datatype compatibility in field mappings."""

import sys
from pathlib import Path

import click

from rosetta.core.io import open_output
from rosetta.core.ledger import load_log, parse_sssom_tsv
from rosetta.core.lint import run_lint


@click.command(
    epilog="""Examples:

  rosetta lint proposals.sssom.tsv --source-schema src.yaml --master-schema master.yaml \\
      --audit-log audit-log.sssom.tsv

  rosetta -v lint proposals.sssom.tsv --source-schema src.yaml --master-schema master.yaml \\
      --audit-log audit-log.sssom.tsv -o report.json

  # audit-log will be created if it does not exist:
  rosetta lint proposals.sssom.tsv --source-schema src.yaml --master-schema master.yaml \\
      --audit-log /new/path/audit-log.sssom.tsv"""
)
@click.argument("sssom_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output JSON file (default: stdout).")
@click.option("--strict", is_flag=True, default=False, help="Upgrade all WARNINGs to BLOCKs.")
@click.option(
    "--audit-log",
    type=click.Path(),
    required=True,
    help="Path to SSSOM audit log (created if it does not exist).",
)
@click.option(
    "--source-schema",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help="Source LinkML schema YAML (enables structural checks).",
)
@click.option(
    "--master-schema",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help="Master LinkML schema YAML (enables structural checks).",
)
def cli(
    sssom_file: str,
    output: str | None,
    strict: bool,
    audit_log: str,
    source_schema: str,
    master_schema: str,
) -> None:
    """Lint a SSSOM proposal TSV for unit/datatype compatibility and structural rules."""
    lp = Path(audit_log)
    if not lp.exists():
        try:
            lp.parent.mkdir(parents=True, exist_ok=True)
            lp.touch()
        except OSError as exc:
            raise click.UsageError(f"Cannot create audit log at {audit_log}: {exc}") from exc
    log = load_log(lp)

    rows = parse_sssom_tsv(Path(sssom_file))

    report = run_lint(rows, log, source_schema, master_schema, strict=strict)

    with open_output(output) as fh:
        fh.write(report.model_dump_json(indent=2))

    sys.exit(1 if any(f.severity == "BLOCK" for f in report.findings) else 0)
