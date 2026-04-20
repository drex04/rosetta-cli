"""Integration tests for rosetta-accredit audit-log pipeline (Phase 18-02, Task 3.7).

Per D-18-10: the real CLI has no 'approve'/'revoke' subcommands. Accreditation
is driven by appending SSSOM rows to the audit log:
  - MMC (ManualMappingCuration) → 'pending'
  - HC (HumanCuration) with predicate skos:exactMatch (etc.) → 'approved'
  - HC with predicate owl:differentFrom → 'rejected' (the revocation signal)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.accredit import cli as accredit_cli
from rosetta.core.accredit import (
    AUDIT_LOG_COLUMNS,
    HC_JUSTIFICATION,
    MMC_JUSTIFICATION,
    SSSOM_HEADER,
    load_log,
)
from rosetta.core.models import SSSOMRow

pytestmark = [pytest.mark.integration]


def _build_row(overrides: dict[str, object]) -> SSSOMRow:
    defaults: dict[str, object] = {
        "predicate_id": "skos:exactMatch",
        "mapping_justification": MMC_JUSTIFICATION,
        "confidence": 0.9,
        "subject_label": "",
        "object_label": "",
        "subject_type": None,
        "object_type": None,
        "mapping_group_id": None,
        "composition_expr": None,
    }
    defaults.update(overrides)
    return SSSOMRow(**defaults)  # pyright: ignore[reportArgumentType]


def _cell(row: SSSOMRow, col: str) -> str:
    if col == "confidence":
        return str(row.confidence)
    if col == "mapping_date":
        return row.mapping_date.isoformat() if row.mapping_date else ""
    val = getattr(row, col, None)
    return "" if val is None else str(val)


def _write_sssom(tmp_path: Path, rows: list[dict[str, object]], name: str) -> Path:
    built = [_build_row(r) for r in rows]
    path = tmp_path / name
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(SSSOM_HEADER)
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(AUDIT_LOG_COLUMNS)
        for row in built:
            writer.writerow([_cell(row, col) for col in AUDIT_LOG_COLUMNS])
    return path


def test_accredit_ingest_approve_status(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """Ingest MMC, then ingest HC, then status → 'approved' state for that pair."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    assert not log_path.exists(), "log should not exist before ingest"

    # --- ingest MMC row ---
    mmc_file = _write_sssom(
        tmp_path,
        [
            {
                "subject_id": "nor:alt_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:altitude",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            }
        ],
        "mmc.sssom.tsv",
    )
    mmc_result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "ingest", str(mmc_file)],
    )
    assert mmc_result.exit_code == 0, f"MMC ingest failed: {mmc_result.stderr}"
    assert log_path.exists(), "log file should exist after MMC ingest"
    mmc_size = log_path.stat().st_size
    assert mmc_size > 0

    # --- ingest HC approval ---
    hc_file = _write_sssom(
        tmp_path,
        [
            {
                "subject_id": "nor:alt_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:altitude",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "1.0",
            }
        ],
        "hc.sssom.tsv",
    )
    hc_result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "ingest", str(hc_file)],
    )
    assert hc_result.exit_code == 0, f"HC ingest failed: {hc_result.stderr}"
    assert log_path.stat().st_size > mmc_size, "log should grow after HC ingest"

    # --- status ---
    status_result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "status"],
    )
    assert status_result.exit_code == 0, f"status failed: {status_result.stderr}"

    entries = json.loads(status_result.stdout)
    assert isinstance(entries, list)
    # Behavioural invariant: the specific (subject, object) pair is present + approved.
    matching = [
        e for e in entries if e["subject_id"] == "nor:alt_m" and e["object_id"] == "mc:altitude"
    ]
    assert len(matching) == 1, f"expected exactly 1 entry for the pair, got {entries}"
    assert matching[0]["state"] == "approved"


def test_accredit_revoke_lifecycle(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """After MMC + HC approval, an HC with owl:differentFrom flips state to 'rejected'."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    pair = {"subject_id": "nor:spd_kmh", "object_id": "mc:speed"}

    # Seed MMC.
    mmc_file = _write_sssom(
        tmp_path,
        [
            pair
            | {
                "predicate_id": "skos:exactMatch",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.85",
            }
        ],
        "mmc.sssom.tsv",
    )
    assert (
        CliRunner(mix_stderr=False)
        .invoke(accredit_cli, ["--config", str(tmp_rosetta_toml), "ingest", str(mmc_file)])
        .exit_code
        == 0
    )

    # Approve via HC exactMatch.
    hc_file = _write_sssom(
        tmp_path,
        [
            pair
            | {
                "predicate_id": "skos:exactMatch",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "1.0",
            }
        ],
        "hc.sssom.tsv",
    )
    assert (
        CliRunner(mix_stderr=False)
        .invoke(accredit_cli, ["--config", str(tmp_rosetta_toml), "ingest", str(hc_file)])
        .exit_code
        == 0
    )

    # Revoke via HC owl:differentFrom — a later HC may correct an earlier HC.
    revoke_file = _write_sssom(
        tmp_path,
        [
            pair
            | {
                "predicate_id": "owl:differentFrom",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "1.0",
            }
        ],
        "revoke.sssom.tsv",
    )
    revoke_result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "ingest", str(revoke_file)],
    )
    assert revoke_result.exit_code == 0, f"revoke ingest failed: {revoke_result.stderr}"

    # Status now shows 'rejected' for that pair.
    status_result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "status"],
    )
    assert status_result.exit_code == 0
    entries = json.loads(status_result.stdout)
    matching = [
        e
        for e in entries
        if e["subject_id"] == pair["subject_id"] and e["object_id"] == pair["object_id"]
    ]
    assert len(matching) == 1
    assert matching[0]["state"] == "rejected"

    # Behavioural invariant: the owl:differentFrom revocation signal is in the
    # persisted audit log (parsed via load_log, not the CLI output).
    rows = load_log(log_path)
    revocation_rows = [
        r
        for r in rows
        if r.subject_id == pair["subject_id"]
        and r.object_id == pair["object_id"]
        and r.mapping_justification == HC_JUSTIFICATION
        and r.predicate_id == "owl:differentFrom"
    ]
    assert len(revocation_rows) == 1, f"expected 1 revocation row, got {len(revocation_rows)}"


def test_accredit_status_empty_log(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """status on a fresh (absent) log prints an empty JSON array and exits 0."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    assert not log_path.exists()

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "status"],
    )
    assert result.exit_code == 0, f"status on empty log failed: {result.stderr}"

    stdout = result.stdout.strip()
    assert stdout == "[]", f"expected '[]' on empty log, got: {stdout!r}"
    # Behavioural invariant: stdout parses as JSON list with zero entries.
    parsed = json.loads(stdout)
    assert parsed == []
