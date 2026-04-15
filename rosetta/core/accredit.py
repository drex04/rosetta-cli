"""Append-only SSSOM audit log I/O and state-machine validation."""

from __future__ import annotations

import csv
import io
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
]

SSSOM_HEADER = """\
# sssom_version: https://w3id.org/sssom/spec/0.15
# mapping_set_id: http://rosetta.interop/audit-log
# curie_map:
#   semapv: https://w3id.org/semapv/vocab/
#   skos: http://www.w3.org/2004/02/skos/core#
#   owl: http://www.w3.org/2002/07/owl#
"""


def _parse_sssom_row(raw: dict[str, str]) -> SSSOMRow:
    """Construct a SSSOMRow from a raw DictReader row dict."""
    mapping_date: datetime | None = None
    raw_date = raw.get("mapping_date") or ""
    if raw_date.strip():
        dt = datetime.fromisoformat(raw_date.strip())
        mapping_date = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

    return SSSOMRow(
        subject_id=raw.get("subject_id", ""),
        predicate_id=raw.get("predicate_id", ""),
        object_id=raw.get("object_id", ""),
        mapping_justification=raw.get("mapping_justification", ""),
        confidence=float(raw.get("confidence", "0.0") or "0.0"),
        subject_label=raw.get("subject_label", "") or "",
        object_label=raw.get("object_label", "") or "",
        mapping_date=mapping_date,
        record_id=raw.get("record_id") or None,
        subject_datatype=raw.get("subject_datatype") or None,
        object_datatype=raw.get("object_datatype") or None,
    )


def parse_sssom_tsv(path: Path) -> list[SSSOMRow]:
    """Parse a SSSOM TSV file. Returns [] if file absent.

    Skips malformed rows (bad float, csv parse error) with a stderr warning.
    Reads all 9 columns using .get() defaults so it tolerates 7-column files.
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


def load_log(path: Path) -> list[SSSOMRow]:
    """Read the audit log. Returns [] if file absent. Delegates to parse_sssom_tsv."""
    return parse_sssom_tsv(path)


def append_log(rows: list[SSSOMRow], path: Path) -> None:
    """Append rows to the log. Creates file + SSSOM header if absent.

    Stamps mapping_date (utcnow ISO 8601) and record_id (uuid4) on each row.
    Calls path.parent.mkdir(parents=True, exist_ok=True) before opening.
    Uses csv.writer so field values containing tabs are safely quoted.
    """
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
                    row.subject_id,
                    row.predicate_id,
                    row.object_id,
                    row.mapping_justification,
                    str(row.confidence),
                    row.subject_label,
                    row.object_label,
                    mapping_date,
                    record_id,
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
