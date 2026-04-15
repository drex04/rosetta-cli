"""rosetta-accredit: Manage mapping accreditation via append-only SSSOM audit log."""

from __future__ import annotations

import csv
import json
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
from rosetta.core.models import StatusEntry


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


def _write_sssom_tsv(rows: list[dict[str, str]], out: IO[str]) -> None:
    """Write SSSOM header block + column header + rows to out."""
    out.write(SSSOM_HEADER)
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(AUDIT_LOG_COLUMNS)
    for row in rows:
        writer.writerow([row.get(col, "") for col in AUDIT_LOG_COLUMNS])


@cli.command("ingest")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def ingest(ctx: click.Context, file: Path) -> None:
    """Ingest an SSSOM TSV file into the audit log."""
    log_path: Path = ctx.obj["log"]

    incoming = parse_sssom_tsv(file)
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
        f"Ingested {len(passing_rows)} rows, skipped {skipped} CompositeMatching rows, "
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

    rows = [
        {
            "subject_id": row.subject_id,
            "predicate_id": row.predicate_id,
            "object_id": row.object_id,
            "mapping_justification": row.mapping_justification,
            "confidence": str(row.confidence),
            "subject_label": row.subject_label,
            "object_label": row.object_label,
            "mapping_date": row.mapping_date.isoformat() if row.mapping_date else "",
            "record_id": row.record_id or "",
        }
        for row in pending
    ]

    with open_output(output) as out:
        _write_sssom_tsv(rows, out)


@cli.command("status")
@click.option("--source", default=None, help="Filter by subject_id substring")
@click.option("--target", default=None, help="Filter by object_id substring")
@click.pass_context
def status(ctx: click.Context, source: str | None, target: str | None) -> None:
    """Show accreditation status as JSON array."""
    log_path: Path = ctx.obj["log"]
    log = load_log(log_path)

    if not log:
        click.echo("[]")
        return

    # Collect unique pairs
    pairs: set[tuple[str, str]] = {(r.subject_id, r.object_id) for r in log}

    entries: list[StatusEntry] = []
    for subject_id, object_id in sorted(pairs):
        if source is not None and source not in subject_id:
            continue
        if target is not None and target not in object_id:
            continue

        latest = current_state_for_pair(log, subject_id, object_id)
        if latest is None:
            continue

        if latest.mapping_justification == MMC_JUSTIFICATION:
            state = "pending"
        elif latest.mapping_justification == HC_JUSTIFICATION:
            if latest.predicate_id == "owl:differentFrom":
                state = "rejected"
            else:
                state = "approved"
        else:
            continue  # unknown justification — skip

        entries.append(
            StatusEntry(
                subject_id=subject_id,
                object_id=object_id,
                state=state,
                predicate_id=latest.predicate_id,
                mapping_date=latest.mapping_date.isoformat() if latest.mapping_date else None,
            )
        )

    click.echo(json.dumps([e.model_dump(mode="json") for e in entries]))


@cli.command("dump")
@click.option("-o", "--output", "output", default=None, help="Output file (default stdout)")
@click.pass_context
def dump(ctx: click.Context, output: str | None) -> None:
    """Dump current accreditor decisions as SSSOM TSV."""
    log_path: Path = ctx.obj["log"]
    log = load_log(log_path)

    rows: list[dict[str, str]] = []

    if log:
        pairs: set[tuple[str, str]] = {(r.subject_id, r.object_id) for r in log}
        for subject_id, object_id in sorted(pairs):
            latest = current_state_for_pair(log, subject_id, object_id)
            if latest is None:
                continue
            # Only emit rows where the latest decision is HumanCuration
            if latest.mapping_justification != HC_JUSTIFICATION:
                continue
            rows.append(
                {
                    "subject_id": latest.subject_id,
                    "predicate_id": latest.predicate_id,
                    "object_id": latest.object_id,
                    "mapping_justification": latest.mapping_justification,
                    "confidence": str(latest.confidence),
                    "subject_label": latest.subject_label,
                    "object_label": latest.object_label,
                    "mapping_date": latest.mapping_date.isoformat() if latest.mapping_date else "",
                    "record_id": latest.record_id or "",
                }
            )

    with open_output(output) as out:
        _write_sssom_tsv(rows, out)
