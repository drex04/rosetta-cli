"""Append-only SSSOM audit log I/O and state-machine validation."""

from __future__ import annotations

import csv
import io
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rosetta.core.models import SSSOMRow

MMC_JUSTIFICATION = "semapv:ManualMappingCuration"
HC_JUSTIFICATION = "semapv:HumanCuration"

# Sentinel for datetime comparisons — tz-aware, sorts before any real audit date.
DATETIME_MIN = datetime(1, 1, 1, tzinfo=UTC)

AUDIT_LOG_COLUMNS = [
    "subject_id",
    "predicate_id",
    "object_id",
    "mapping_justification",
    "confidence",
    "subject_label",
    "object_label",
    "mapping_date",
    "record_id",
    "subject_type",
    "object_type",
    "mapping_group_id",
    "composition_expr",
]

SSSOM_HEADER = """\
# sssom_version: https://w3id.org/sssom/spec/0.15
# mapping_set_id: http://rosetta.interop/audit-log
# curie_map:
#   semapv: https://w3id.org/semapv/vocab/
#   skos: http://www.w3.org/2004/02/skos/core#
#   owl: http://www.w3.org/2002/07/owl#
"""


_OPTIONAL_STR_FIELDS = (
    "record_id",
    "subject_datatype",
    "object_datatype",
    "subject_type",
    "object_type",
    "mapping_group_id",
    "composition_expr",
)


def _parse_mapping_date(raw_date: str) -> datetime | None:
    if not raw_date.strip():
        return None
    dt = datetime.fromisoformat(raw_date.strip())
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _parse_sssom_row(raw: dict[str, str]) -> SSSOMRow:
    """Construct a SSSOMRow from a raw DictReader row dict.

    # SYNC: must match AUDIT_LOG_COLUMNS order in this module.
    """
    optional = {field: (raw.get(field) or None) for field in _OPTIONAL_STR_FIELDS}
    return SSSOMRow(
        subject_id=raw.get("subject_id", ""),
        predicate_id=raw.get("predicate_id", ""),
        object_id=raw.get("object_id", ""),
        mapping_justification=raw.get("mapping_justification", ""),
        confidence=float(raw.get("confidence", "0.0") or "0.0"),
        subject_label=raw.get("subject_label", "") or "",
        object_label=raw.get("object_label", "") or "",
        mapping_date=_parse_mapping_date(raw.get("mapping_date") or ""),
        **optional,
    )


def parse_sssom_tsv(path: Path) -> list[SSSOMRow]:
    """Parse a SSSOM TSV file. Returns [] if file absent.

    Skips malformed rows (bad float, csv parse error) with a stderr warning.
    Reads all 13 audit-log columns using `.get()` defaults; tolerates 9-column
    (pre-16-00 audit log), 11-column (post-Phase-15 suggest output with datatype),
    and 13-column (post-16-00 audit log) inputs. Missing columns yield `None` on
    the resulting `SSSOMRow`.
    """
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    data_lines = [line for line in text.splitlines() if not line.startswith("#")]
    if not data_lines:
        return []

    rows: list[SSSOMRow] = []
    try:
        reader = csv.DictReader(io.StringIO("\n".join(data_lines)), delimiter="\t")
        for lineno, raw in enumerate(reader, start=2):  # 1-based; header is line 1
            try:
                rows.append(_parse_sssom_row(raw.copy()))
            except (ValueError, KeyError) as exc:
                print(
                    f"WARNING: skipping malformed row {lineno} in {path}: {exc}",
                    file=sys.stderr,
                )
    except csv.Error as exc:
        print(f"WARNING: CSV parse error in {path}: {exc}", file=sys.stderr)

    return rows


def _row_value_for_column(row: SSSOMRow, col: str, mapping_date: str, record_id: str) -> str:
    """Return the string value for a given audit-log column. Keeps the writer
    loop symbol-to-column driven so header + body cannot drift."""
    if col == "mapping_date":
        return mapping_date
    if col == "record_id":
        return record_id
    if col == "confidence":
        return str(row.confidence)
    value = getattr(row, col, None)
    return "" if value is None else str(value)


def load_log(path: Path) -> list[SSSOMRow]:
    """Read the audit log. Returns [] if file absent. Delegates to parse_sssom_tsv."""
    return parse_sssom_tsv(path)


def _migrate_audit_log_if_needed(path: Path) -> None:
    """If the audit log at *path* has fewer columns than AUDIT_LOG_COLUMNS,
    rewrite it atomically with the current column list, padding legacy rows
    with empty strings. No-op if file is absent, empty, or already current shape.

    Atomicity: write to <path>.tmp; os.replace(tmp, path). Crash-safe on POSIX.
    Wider-than-current files (future downgrade scenario) are left unchanged.
    """
    if not path.exists() or path.stat().st_size == 0:
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    comment_lines = [ln for ln in lines if ln.startswith("#")]
    data_lines = [ln for ln in lines if not ln.startswith("#")]
    if not data_lines:
        return

    existing_header = data_lines[0].split("\t")
    if len(existing_header) >= len(AUDIT_LOG_COLUMNS):
        return  # already current or wider — downgrade not supported, no-op

    _write_migrated_audit_log(path, comment_lines, data_lines)


def _write_migrated_audit_log(path: Path, comment_lines: list[str], data_lines: list[str]) -> None:
    """Atomic rewrite: temp file with new header + padded rows, then os.replace."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        for ln in comment_lines:
            fh.write(ln + "\n")
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(AUDIT_LOG_COLUMNS)
        # Re-parse against the OLD header so values land in their matching
        # new column positions; any unrecognised legacy columns are dropped.
        old_reader = csv.DictReader(io.StringIO("\n".join(data_lines)), delimiter="\t")
        for raw_row in old_reader:
            writer.writerow([raw_row.get(col, "") or "" for col in AUDIT_LOG_COLUMNS])
    os.replace(tmp, path)


def append_log(rows: list[SSSOMRow], path: Path) -> None:
    """Append rows to the log. Creates file + SSSOM header if absent.

    Stamps mapping_date (utcnow ISO 8601) and record_id (uuid4) on each row.
    Migrates stale (< 13-column) audit logs atomically before appending.
    Calls path.parent.mkdir(parents=True, exist_ok=True) before opening.
    Uses csv.writer so field values containing tabs are safely quoted.
    """
    _migrate_audit_log_if_needed(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    write_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", encoding="utf-8", newline="") as fh:
        if write_header:
            fh.write(SSSOM_HEADER)
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        if write_header:
            writer.writerow(AUDIT_LOG_COLUMNS)

        for row in rows:
            # Stamp date and UUID if not already set
            mapping_date = row.mapping_date.isoformat() if row.mapping_date else now
            record_id = row.record_id or str(uuid.uuid4())
            writer.writerow(
                [
                    _row_value_for_column(row, col, mapping_date, record_id)
                    for col in AUDIT_LOG_COLUMNS
                ]
            )


def current_state_for_pair(log: list[SSSOMRow], subject_id: str, object_id: str) -> SSSOMRow | None:
    """Return the most recent row for (subject_id, object_id), ordered by
    mapping_date (None dates sort first). Returns None if pair absent.
    """
    matching = [r for r in log if r.subject_id == subject_id and r.object_id == object_id]
    if not matching:
        return None

    return max(matching, key=lambda r: r.mapping_date or DATETIME_MIN)


def query_pending(log: list[SSSOMRow]) -> list[SSSOMRow]:
    """Return ManualMappingCuration rows that have no subsequent HumanCuration
    for the same (subject_id, object_id) pair.

    O(n) — pre-groups rows by pair to avoid the O(n²) inner scan.
    """
    # Pre-group HC rows by pair for O(1) lookup
    hc_by_pair: dict[tuple[str, str], list[SSSOMRow]] = {}
    for row in log:
        if row.mapping_justification == HC_JUSTIFICATION:
            key = (row.subject_id, row.object_id)
            hc_by_pair.setdefault(key, []).append(row)

    result: list[SSSOMRow] = []
    for row in log:
        if row.mapping_justification != MMC_JUSTIFICATION:
            continue
        pair = (row.subject_id, row.object_id)
        hc_rows = hc_by_pair.get(pair)
        if not hc_rows:
            result.append(row)
        else:
            # MMC is pending only if it is newer than the latest HC for this pair
            latest_hc = max(hc_rows, key=lambda r: r.mapping_date or DATETIME_MIN)
            if (row.mapping_date or DATETIME_MIN) > (latest_hc.mapping_date or DATETIME_MIN):
                result.append(row)

    return result


def _check_mmc_transition(pair_rows: list[SSSOMRow], subject_id: str, object_id: str) -> None:
    if any(r.mapping_justification == HC_JUSTIFICATION for r in pair_rows):
        raise ValueError(
            f"Cannot ingest ManualMappingCuration for ({subject_id}, {object_id}): "
            f"pair already has HumanCuration row(s) in the audit log."
        )


def _check_hc_transition(pair_rows: list[SSSOMRow], subject_id: str, object_id: str) -> None:
    if not any(r.mapping_justification == MMC_JUSTIFICATION for r in pair_rows):
        raise ValueError(
            f"Cannot ingest HumanCuration for ({subject_id}, {object_id}): "
            f"pair has no ManualMappingCuration row in the audit log."
        )


def check_ingest_row(row: SSSOMRow, log: list[SSSOMRow]) -> None:
    """Raise ValueError with a descriptive message if:
    - row.mapping_justification == MMC_JUSTIFICATION AND pair has any HumanCuration row in log
    - row.mapping_justification == HC_JUSTIFICATION AND pair has no ManualMappingCuration row in log

    Uses exact constant matching (not endswith) to avoid future vocab collisions.
    HumanCuration over existing HumanCuration is ALLOWED (accreditor correction).
    """
    pair_rows = [r for r in log if r.subject_id == row.subject_id and r.object_id == row.object_id]
    if row.mapping_justification == MMC_JUSTIFICATION:
        _check_mmc_transition(pair_rows, row.subject_id, row.object_id)
    elif row.mapping_justification == HC_JUSTIFICATION:
        _check_hc_transition(pair_rows, row.subject_id, row.object_id)
