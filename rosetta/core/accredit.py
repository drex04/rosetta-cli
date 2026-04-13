"""Accreditation ledger I/O and state transition logic."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rosetta.core.models import Ledger, LedgerEntry


def load_ledger(path: Path) -> Ledger:
    """Load ledger.json; return empty Ledger if file absent."""
    if not path.exists():
        return Ledger()
    return Ledger.model_validate_json(path.read_text())


def save_ledger(ledger: Ledger, path: Path) -> None:
    """Write ledger to path as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger.model_dump(mode="json"), indent=2, default=str))


def find_entry(ledger: Ledger, source_uri: str, target_uri: str) -> LedgerEntry | None:
    """Return first matching entry or None."""
    for entry in ledger.mappings:
        if entry.source_uri == source_uri and entry.target_uri == target_uri:
            return entry
    return None


def submit_mapping(
    ledger: Ledger,
    source_uri: str,
    target_uri: str,
    actor: str,
    notes: str = "",
) -> LedgerEntry:
    """Create a pending entry. Raise ValueError if pair already exists in any state.

    Returns the new entry (does NOT save — caller saves).
    """
    existing = find_entry(ledger, source_uri, target_uri)
    if existing is not None:
        raise ValueError(
            f"Mapping ({source_uri}, {target_uri}) already exists with status={existing.status!r}"
        )
    entry = LedgerEntry(
        source_uri=source_uri,
        target_uri=target_uri,
        status="pending",
        timestamp=datetime.utcnow(),
        actor=actor,
        notes=notes,
    )
    ledger.mappings.append(entry)
    return entry


def approve_mapping(ledger: Ledger, source_uri: str, target_uri: str) -> LedgerEntry:
    """Transition pending → accredited. Raise ValueError if entry not found or wrong state.

    Mutates the entry in-place. Returns the updated entry.
    """
    entry = find_entry(ledger, source_uri, target_uri)
    if entry is None:
        raise ValueError(f"No entry found for ({source_uri}, {target_uri})")
    if entry.status != "pending":
        raise ValueError(f"Cannot approve: entry has status={entry.status!r}, expected 'pending'")
    entry.status = "accredited"
    return entry


def revoke_mapping(ledger: Ledger, source_uri: str, target_uri: str) -> LedgerEntry:
    """Transition pending → revoked or accredited → revoked.

    Raise ValueError if entry not found or already revoked.
    Mutates in-place. Returns updated entry.
    """
    entry = find_entry(ledger, source_uri, target_uri)
    if entry is None:
        raise ValueError(f"No entry found for ({source_uri}, {target_uri})")
    if entry.status == "revoked":
        raise ValueError(f"Cannot revoke: entry is already revoked")
    entry.status = "revoked"
    return entry
