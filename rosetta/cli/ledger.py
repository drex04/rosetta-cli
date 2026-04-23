"""rosetta ledger: Manage mapping accreditation via append-only SSSOM audit log."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import IO

import click

from rosetta.core.io import open_output
from rosetta.core.ledger import (
    AUDIT_LOG_COLUMNS,
    HC_JUSTIFICATION,
    MMC_JUSTIFICATION,
    SSSOM_HEADER,
    append_log,
    check_ingest_row,
    current_state_for_pair,
    load_log,
    parse_sssom_tsv,
    query_pending,
)
from rosetta.core.lint import run_lint
from rosetta.core.models import LintReport, LintSummary, SSSOMRow


@click.group(
    "ledger",
    epilog="""Examples:

  rosetta ledger --audit-log log.tsv append --role analyst proposals.sssom.tsv \\
      --source-schema s.yaml --master-schema m.yaml

  rosetta ledger --audit-log log.tsv append --role analyst --dry-run proposals.sssom.tsv \\
      --source-schema s.yaml --master-schema m.yaml

  rosetta ledger --audit-log log.tsv review -o pending.sssom.tsv""",
)
@click.option("--audit-log", "log", required=True, help="Path to audit-log SSSOM TSV")
@click.pass_context
def cli(ctx: click.Context, log: str) -> None:
    """Manage mapping accreditation via append-only SSSOM audit log."""
    ctx.ensure_object(dict)
    ctx.obj["log"] = Path(log)


def _row_to_tsv_cell(row: SSSOMRow, col: str) -> str:
    """Serialise a single SSSOMRow field to its TSV cell representation.

    Mirrors the column-driven serialisation used by core.accredit.append_log so
    review/dump emit values for every AUDIT_LOG_COLUMNS entry, not just the
    first nine.
    """
    if col == "mapping_date":
        return row.mapping_date.isoformat() if row.mapping_date else ""
    if col == "confidence":
        return str(row.confidence)
    value = getattr(row, col, None)
    return "" if value is None else str(value)


def _write_sssom_tsv(rows: list[SSSOMRow], out: IO[str]) -> None:
    """Write SSSOM header block + column header + rows to out."""
    out.write(SSSOM_HEADER)
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(AUDIT_LOG_COLUMNS)
    for row in rows:
        writer.writerow([_row_to_tsv_cell(row, col) for col in AUDIT_LOG_COLUMNS])


@cli.command(
    "append",
    epilog="""Examples:

  rosetta ledger --audit-log log.tsv append --role analyst proposals.sssom.tsv \\
      --source-schema s.yaml --master-schema m.yaml

  rosetta ledger --audit-log log.tsv append --role analyst --dry-run proposals.sssom.tsv \\
      --source-schema s.yaml --master-schema m.yaml""",
)
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--role",
    type=click.Choice(["analyst", "accreditor"]),
    required=True,
    help="Role determines which rows are accepted and how they are linted",
)
@click.option(
    "--source-schema",
    type=click.Path(exists=True),
    required=True,
    help="Source LinkML schema YAML",
)
@click.option(
    "--master-schema",
    type=click.Path(exists=True),
    required=True,
    help="Master LinkML schema YAML",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Run lint checks without appending to the audit log",
)
@click.option("--strict", is_flag=True, default=False, help="Upgrade all WARNINGs to BLOCKs.")
@click.pass_context
def append_cmd(
    ctx: click.Context,
    file: Path,
    role: str,
    source_schema: str,
    master_schema: str,
    dry_run: bool,
    strict: bool,
) -> None:
    """Append an SSSOM TSV file into the audit log."""
    log_path: Path = ctx.obj["log"]

    try:
        incoming = parse_sssom_tsv(file)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    log = load_log(log_path)

    # 1. Run lint on ALL unfiltered candidates
    report = run_lint(incoming, log, source_schema, master_schema, strict=strict)

    # For accreditor, HC rows are expected — strip hc_in_candidates findings
    if role == "accreditor":
        filtered_findings = [f for f in report.findings if f.rule != "hc_in_candidates"]
        summary = LintSummary(
            block=sum(1 for f in filtered_findings if f.severity == "BLOCK"),
            warning=sum(1 for f in filtered_findings if f.severity == "WARNING"),
            info=sum(1 for f in filtered_findings if f.severity == "INFO"),
        )
        report = LintReport(findings=filtered_findings, summary=summary)

    has_blocks = report.summary.block > 0

    # 2. Dry-run: report to stdout and exit
    if dry_run:
        click.echo(report.model_dump_json(indent=2))
        sys.exit(1 if has_blocks else 0)

    # 3. Lint gate: block on BLOCK findings
    if has_blocks:
        click.echo(report.model_dump_json(indent=2), err=True)
        click.echo(
            "Lint failed: records were not appended. Resolve blocking issues then try again.",
            err=True,
        )
        sys.exit(1)

    # 4. Print warnings to stderr if any
    if report.summary.warning > 0:
        click.echo(report.model_dump_json(indent=2), err=True)

    # 5. Role-based filtering
    if role == "analyst":
        target_justification = MMC_JUSTIFICATION
    else:
        target_justification = HC_JUSTIFICATION

    filtered = [r for r in incoming if r.mapping_justification == target_justification]
    skipped = len(incoming) - len(filtered)

    # 6. For accreditor: validate HC state machine transitions
    if role == "accreditor":
        errors: list[str] = []
        valid_rows: list[SSSOMRow] = []
        for row in filtered:
            try:
                check_ingest_row(row, log)
                valid_rows.append(row)
            except ValueError as exc:
                errors.append(str(exc))
        if errors:
            for err in errors:
                click.echo(f"Error: {err}", err=True)
            sys.exit(1)
        filtered = valid_rows

    # 7. Deduplicate against existing log
    existing_keys = {
        (r.subject_id, r.predicate_id, r.object_id, r.mapping_justification) for r in log
    }
    deduped = [
        r
        for r in filtered
        if (r.subject_id, r.predicate_id, r.object_id, r.mapping_justification) not in existing_keys
    ]
    dup_count = len(filtered) - len(deduped)

    # 8. Append
    append_log(deduped, log_path)
    parts = [f"Appended {len(deduped)} rows"]
    if skipped:
        parts.append(f"skipped {skipped} non-{role} rows")
    if dup_count:
        parts.append(f"skipped {dup_count} duplicate triples")
    click.echo(", ".join(parts), err=True)


@cli.command(
    "review",
    epilog="""Examples:

  rosetta ledger review

  rosetta ledger review -o pending.sssom.tsv""",
)
@click.option("-o", "--output", "output", default=None, help="Output file (default stdout)")
@click.pass_context
def review(ctx: click.Context, output: str | None) -> None:
    """List pending mappings (ManualMappingCuration with no subsequent HumanCuration)."""
    log_path: Path = ctx.obj["log"]
    log = load_log(log_path)
    pending = query_pending(log)

    with open_output(output) as out:
        _write_sssom_tsv(pending, out)


@cli.command(
    "dump",
    epilog="""Examples:

  rosetta ledger dump

  rosetta ledger dump -o accredited.sssom.tsv""",
)
@click.option("-o", "--output", "output", default=None, help="Output file (default stdout)")
@click.pass_context
def dump(ctx: click.Context, output: str | None) -> None:
    """Dump current accreditor decisions as SSSOM TSV."""
    log_path: Path = ctx.obj["log"]
    log = load_log(log_path)

    rows: list[SSSOMRow] = []

    if log:
        pairs: set[tuple[str, str]] = {(r.subject_id, r.object_id) for r in log}
        for subject_id, object_id in sorted(pairs):
            latest = current_state_for_pair(log, subject_id, object_id)
            if latest is None:
                continue
            # Only emit rows where the latest decision is HumanCuration
            if latest.mapping_justification != HC_JUSTIFICATION:
                continue
            rows.append(latest)

    with open_output(output) as out:
        _write_sssom_tsv(rows, out)
