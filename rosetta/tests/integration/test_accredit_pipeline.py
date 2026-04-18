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
from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION, load_log

pytestmark = [pytest.mark.integration]


_SSSOM_COLUMNS = [
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

_SSSOM_FILE_HEADER = (
    "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
    "# mapping_set_id: http://rosetta.interop/test-ingest\n"
    "# curie_map:\n"
    "#   semapv: https://w3id.org/semapv/vocab/\n"
    "#   skos: http://www.w3.org/2004/02/skos/core#\n"
    "#   owl: http://www.w3.org/2002/07/owl#\n"
)


def _write_sssom(tmp_path: Path, rows: list[dict[str, str]], name: str) -> Path:
    path = tmp_path / name
    with path.open("w", encoding="utf-8") as f:
        f.write(_SSSOM_FILE_HEADER)
        writer = csv.DictWriter(f, fieldnames=_SSSOM_COLUMNS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in _SSSOM_COLUMNS})
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
