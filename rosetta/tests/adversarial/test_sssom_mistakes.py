"""Adversarial tests for rosetta-accredit SSSOM ingest mistakes (Phase 18-03, Task 4).

These tests pin the observable error behaviour of `rosetta-accredit ingest` against
malformed SSSOM inputs:

- Duplicate MMC rows in a single file (in-file pre-scan at `rosetta/cli/accredit.py`)
- Too-few-column TSV (observed behaviour documented per test)
- Phantom derank (HC with owl:differentFrom when no prior MMC exists) — rejected via
  `check_ingest_row`'s HC→MMC transition guard in `rosetta/core/accredit.py`
- Clean single-row MMC baseline (positive control)

Three-level assertion contract (D-18-08) is applied to every test:
1. Exit code
2. Stderr substring match
3. Behavioural invariant (log file presence / size)
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.accredit import cli as accredit_cli
from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION

pytestmark = [pytest.mark.integration]


# Full 13-column audit-log SSSOM shape (post-Phase 16-00).
# Matches rosetta/tests/integration/test_accredit_pipeline.py — kept local so
# this adversarial suite has zero cross-file test helper coupling.
_SSSOM_COLUMNS: list[str] = [
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

_SSSOM_FILE_HEADER: str = (
    "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
    "# mapping_set_id: http://rosetta.interop/test-adversarial\n"
    "# curie_map:\n"
    "#   semapv: https://w3id.org/semapv/vocab/\n"
    "#   skos: http://www.w3.org/2004/02/skos/core#\n"
    "#   owl: http://www.w3.org/2002/07/owl#\n"
)


def _write_sssom(tmp_path: Path, rows: list[dict[str, str]], name: str) -> Path:
    """Write a valid 9-of-13-column SSSOM TSV (the rest default to empty)."""
    path = tmp_path / name
    with path.open("w", encoding="utf-8") as f:
        f.write(_SSSOM_FILE_HEADER)
        writer = csv.DictWriter(f, fieldnames=_SSSOM_COLUMNS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in _SSSOM_COLUMNS})
    return path


def _log_path_from_toml(tmp_rosetta_toml: Path) -> Path:
    """The tmp_rosetta_toml fixture writes log = "<tmp_path>/audit-log.sssom.tsv"."""
    return tmp_rosetta_toml.parent / "audit-log.sssom.tsv"


def test_accredit_duplicate_mmc(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """Two MMC rows with the same (subject_id, object_id) in one file → exit 1, no log write.

    The in-file duplicate guard lives at `rosetta/cli/accredit.py::ingest` and emits
    stderr lines shaped like:

        Error: Duplicate MMC pair in file: (nor:alt_m, mc:altitude)
    """
    log_path = _log_path_from_toml(tmp_rosetta_toml)
    assert not log_path.exists()

    tsv_file = _write_sssom(
        tmp_path,
        [
            {
                "subject_id": "nor:alt_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:altitude",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "nor:alt_m",
                "predicate_id": "skos:exactMatch",
                "object_id": "mc:altitude",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.85",
            },
        ],
        "dup_mmc.sssom.tsv",
    )

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "ingest", str(tsv_file)],
    )

    # 1. Exit code.
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stderr}"
    # 2. Stderr substring — "Duplicate" and the subject id must appear.
    assert "Duplicate" in result.stderr
    assert "nor:alt_m" in result.stderr
    assert "mc:altitude" in result.stderr
    # 3. Behavioural invariant: nothing was appended to the audit log.
    assert not log_path.exists(), "log file must not be created on a rejected ingest"


def test_accredit_wrong_column_count(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """TSV header missing required SSSOM columns → exit 1, clear diagnostic, no log write.

    `parse_sssom_tsv` raises `ValueError` at the parse boundary when the header
    lacks any of the 5 required SSSOM columns (subject_id, predicate_id, object_id,
    mapping_justification, confidence). The CLI catches the exception and emits
    a clean error naming the missing columns. No log file is created.
    """
    log_path = _log_path_from_toml(tmp_rosetta_toml)
    assert not log_path.exists()

    tsv_file = tmp_path / "missing_required_cols.sssom.tsv"
    # Header lacks `confidence` and `mapping_justification` — both required.
    bad_cols = ["subject_id", "predicate_id", "object_id"]
    with tsv_file.open("w", encoding="utf-8") as f:
        f.write(_SSSOM_FILE_HEADER)
        f.write("\t".join(bad_cols) + "\n")
        f.write("\t".join(["a", "skos:exactMatch", "b"]) + "\n")

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "ingest", str(tsv_file)],
    )

    # 1. Exit code — explicit failure from the new header guard.
    assert result.exit_code == 1, (
        f"expected exit 1 on missing required columns; got {result.exit_code}"
    )
    # 2. Stderr — names the missing columns for the user.
    assert "missing required" in result.stderr.lower()
    assert "confidence" in result.stderr or "mapping_justification" in result.stderr
    # 3. Behavioural invariant: no audit-log file was created.
    assert not log_path.exists(), "log file must not be created on a rejected ingest"


def test_accredit_phantom_derank(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """HC with owl:differentFrom but no prior MMC → exit 1, no log write.

    Flow: `check_ingest_row` routes HC-justified rows to `_check_hc_transition`,
    which raises ValueError when `pair_rows` has no MMC row. The CLI converts this
    into an entry in its `errors` list and exits 1. Stderr contains:

        Error: Cannot ingest HumanCuration for (nor:spd, mc:speed): \
            pair has no ManualMappingCuration row in the audit log.

    Note: the CLI does NOT have a dedicated "cannot derank" check — it relies on
    the broader HC→MMC transition guard. The substring match below targets phrasing
    that is stable in the current core implementation.
    """
    log_path = _log_path_from_toml(tmp_rosetta_toml)
    assert not log_path.exists()

    tsv_file = _write_sssom(
        tmp_path,
        [
            {
                "subject_id": "nor:spd",
                "predicate_id": "owl:differentFrom",
                "object_id": "mc:speed",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "1.0",
            }
        ],
        "phantom_derank.sssom.tsv",
    )

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "ingest", str(tsv_file)],
    )

    # 1. Exit code.
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stderr}"
    # 2. Stderr substring — stable phrasing from _check_hc_transition.
    assert (
        "no ManualMappingCuration" in result.stderr
        or "Cannot ingest HumanCuration" in result.stderr
    ), f"stderr did not name the missing-MMC transition: {result.stderr!r}"
    # The specific pair must appear.
    assert "nor:spd" in result.stderr
    assert "mc:speed" in result.stderr
    # 3. Behavioural invariant: no log write.
    assert not log_path.exists(), "log file must not be created on a rejected ingest"


def test_accredit_clean_ingest_baseline(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """Positive control: a single valid MMC row ingests cleanly.

    Guarantees the above negative tests fail for the *right* reason — a valid TSV
    under the same fixture really does produce exit 0 + a non-empty log.
    """
    log_path = _log_path_from_toml(tmp_rosetta_toml)
    assert not log_path.exists()

    tsv_file = _write_sssom(
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
        "clean.sssom.tsv",
    )

    result = CliRunner(mix_stderr=False).invoke(
        accredit_cli,
        ["--config", str(tmp_rosetta_toml), "ingest", str(tsv_file)],
    )

    # 1. Exit code.
    assert result.exit_code == 0, f"clean ingest should succeed; stderr: {result.stderr}"
    # 2. No error on stderr.
    assert "Error" not in result.stderr
    # 3. Behavioural invariant: log file exists and is non-empty.
    assert log_path.exists(), "log file must be created on a successful ingest"
    assert log_path.stat().st_size > 0
