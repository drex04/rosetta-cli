"""rosetta-accredit: Manage mapping accreditation via append-only SSSOM audit log."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import IO

import click

from rosetta.core.accredit import (
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
from rosetta.core.config import get_config_value, load_config
from rosetta.core.io import open_output
from rosetta.core.models import SSSOMRow


@click.group()
@click.option("--log", default=None, help="Path to audit-log SSSOM TSV")
@click.option("--config", "-c", "config", default=None, help="Path to rosetta.toml")
@click.pass_context
def cli(ctx: click.Context, log: str | None, config: str | None) -> None:
    """Manage mapping accreditation via append-only SSSOM audit log."""
    cfg = load_config(Path(config)) if config else load_config()
    log_path_str = log or get_config_value(cfg, "accredit", "log") or "store/audit-log.sssom.tsv"
    ctx.ensure_object(dict)
    ctx.obj["log"] = Path(log_path_str)


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


@cli.command("append")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def append_cmd(ctx: click.Context, file: Path) -> None:
    """Append an SSSOM TSV file into the audit log."""
    log_path: Path = ctx.obj["log"]

    try:
        incoming = parse_sssom_tsv(file)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    log = load_log(log_path)

    errors: list[str] = []

    # Pre-scan for in-file duplicate MMC pairs
    seen: set[tuple[str, str]] = set()
    for row in incoming:
        if row.mapping_justification == MMC_JUSTIFICATION:
            pair = (row.subject_id, row.object_id)
            if pair in seen:
                errors.append(f"Duplicate MMC pair in file: ({row.subject_id}, {row.object_id})")
            seen.add(pair)

    # Pairs that are pending review (MMC with no subsequent HC) — re-ingesting MMC is a no-op
    pending_pairs: set[tuple[str, str]] = {(r.subject_id, r.object_id) for r in query_pending(log)}

    # Validate each MMC/HC row against the log
    passing_rows = []
    skipped = 0
    skipped_dupes = 0
    for row in incoming:
        if row.mapping_justification in {MMC_JUSTIFICATION, HC_JUSTIFICATION}:
            if (
                row.mapping_justification == MMC_JUSTIFICATION
                and (row.subject_id, row.object_id) in pending_pairs
            ):
                skipped_dupes += 1
                continue
            try:
                check_ingest_row(row, log)
                passing_rows.append(row)
            except ValueError as exc:
                errors.append(str(exc))
        else:
            skipped += 1

    if errors:
        for err in errors:
            click.echo(f"Error: {err}", err=True)
        sys.exit(1)

    append_log(passing_rows, log_path)
    click.echo(
        f"Appended {len(passing_rows)} rows, skipped {skipped} CompositeMatching rows, "
        f"{skipped_dupes} duplicate MMC rows",
        err=True,
    )


@cli.command("review")
@click.option("-o", "--output", "output", default=None, help="Output file (default stdout)")
@click.pass_context
def review(ctx: click.Context, output: str | None) -> None:
    """List pending mappings (ManualMappingCuration with no subsequent HumanCuration)."""
    log_path: Path = ctx.obj["log"]
    log = load_log(log_path)
    pending = query_pending(log)

    with open_output(output) as out:
        _write_sssom_tsv(pending, out)


@cli.command("dump")
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
