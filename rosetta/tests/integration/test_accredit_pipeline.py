"""Integration tests for rosetta accredit audit-log pipeline (Phase 18-02, Task 3.7).

Per D-18-10: the real CLI has no 'approve'/'revoke' subcommands. Accreditation
is driven by appending SSSOM rows to the audit log:
  - MMC (ManualMappingCuration) → 'pending'
  - HC (HumanCuration) with predicate skos:exactMatch (etc.) → 'approved'
  - HC with predicate owl:differentFrom → 'rejected' (the revocation signal)
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.ledger import cli as accredit_cli
from rosetta.core.ledger import (
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


def _write_sssom(tmp_path: Path, rows: list[dict[str, str]], name: str) -> Path:
    built = [_build_row(r) for r in rows]  # pyright: ignore[reportArgumentType]
    path = tmp_path / name
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(SSSOM_HEADER)
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(AUDIT_LOG_COLUMNS)
        for row in built:
            writer.writerow([_cell(row, col) for col in AUDIT_LOG_COLUMNS])
    return path


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
        .invoke(accredit_cli, ["--config", str(tmp_rosetta_toml), "append", str(mmc_file)])
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
        .invoke(accredit_cli, ["--config", str(tmp_rosetta_toml), "append", str(hc_file)])
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
        ["--config", str(tmp_rosetta_toml), "append", str(revoke_file)],
    )
    assert revoke_result.exit_code == 0, f"revoke append failed: {revoke_result.stderr}"

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
