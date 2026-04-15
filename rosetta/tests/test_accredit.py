"""Unit tests for accreditation audit-log pipeline and CLI."""

from __future__ import annotations

import csv
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.accredit import cli
from rosetta.core.accredit import (
    HC_JUSTIFICATION,
    MMC_JUSTIFICATION,
    append_log,
    check_ingest_row,
    current_state_for_pair,
    load_log,
    parse_sssom_tsv,
    query_pending,
)
from rosetta.core.models import SSSOMRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMPOSITE_JUSTIFICATION = "semapv:CompositeMatching"


def _row(
    subject_id: str,
    object_id: str,
    justification: str,
    predicate: str = "skos:exactMatch",
    confidence: float = 0.9,
) -> SSSOMRow:
    return SSSOMRow(
        subject_id=subject_id,
        object_id=object_id,
        predicate_id=predicate,
        mapping_justification=justification,
        confidence=confidence,
    )


def _make_sssom_tsv(
    tmp_path: Path,
    rows: list[dict[str, str]],
    filename: str = "input.sssom.tsv",
) -> Path:
    path = tmp_path / filename
    header = "# sssom_version: https://w3id.org/sssom/spec/0.15\n# mapping_set_id: test\n"
    cols = [
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
    with path.open("w") as f:
        f.write(header)
        writer = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in cols})
    return path


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def test_load_log_returns_empty_when_file_absent(tmp_path: Path) -> None:
    assert not load_log(tmp_path / "nope.tsv")


def test_append_log_creates_file_with_sssom_header(tmp_path: Path) -> None:
    path = tmp_path / "log.tsv"
    row = _row("a", "b", MMC_JUSTIFICATION)
    append_log([row], path)
    content = path.read_text()
    assert content.startswith("# sssom_version")
    assert "subject_id" in content  # header row


def test_append_log_stamps_mapping_date_and_record_id(tmp_path: Path) -> None:
    path = tmp_path / "log.tsv"
    row = _row("a", "b", MMC_JUSTIFICATION)
    append_log([row], path)
    rows = load_log(path)
    assert len(rows) == 1
    assert rows[0].mapping_date is not None
    assert rows[0].record_id is not None
    uuid.UUID(rows[0].record_id)  # valid UUID4


def test_append_log_appends_to_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "log.tsv"
    append_log([_row("a", "b", MMC_JUSTIFICATION)], path)
    append_log([_row("a", "b", HC_JUSTIFICATION)], path)
    rows = load_log(path)
    assert len(rows) == 2


def test_current_state_for_pair_returns_latest_by_date(tmp_path: Path) -> None:
    path = tmp_path / "log.tsv"
    append_log([_row("a", "b", MMC_JUSTIFICATION)], path)
    append_log([_row("a", "b", HC_JUSTIFICATION)], path)
    rows = load_log(path)
    latest = current_state_for_pair(rows, "a", "b")
    assert latest is not None
    assert latest.mapping_justification == HC_JUSTIFICATION


def test_current_state_for_pair_returns_none_when_absent() -> None:
    assert current_state_for_pair([], "x", "y") is None


def test_query_pending_returns_unreviewed_mmc_rows(tmp_path: Path) -> None:
    path = tmp_path / "log.tsv"
    append_log([_row("a", "b", MMC_JUSTIFICATION), _row("c", "d", MMC_JUSTIFICATION)], path)
    rows = load_log(path)
    pending = query_pending(rows)
    assert len(pending) == 2


def test_query_pending_excludes_mmc_with_subsequent_hc(tmp_path: Path) -> None:
    path = tmp_path / "log.tsv"
    append_log([_row("a", "b", MMC_JUSTIFICATION)], path)
    append_log([_row("a", "b", HC_JUSTIFICATION)], path)
    rows = load_log(path)
    assert not query_pending(rows)


def test_check_ingest_mmc_blocked_by_any_human_curation() -> None:
    log = [_row("a", "b", MMC_JUSTIFICATION), _row("a", "b", HC_JUSTIFICATION)]
    with pytest.raises(ValueError, match="HumanCuration"):
        check_ingest_row(_row("a", "b", MMC_JUSTIFICATION), log)


def test_check_ingest_mmc_blocked_by_rejected_human_curation() -> None:
    log = [
        _row("a", "b", MMC_JUSTIFICATION),
        _row("a", "b", HC_JUSTIFICATION, predicate="owl:differentFrom"),
    ]
    with pytest.raises(ValueError):
        check_ingest_row(_row("a", "b", MMC_JUSTIFICATION), log)


def test_check_ingest_mmc_allowed_when_no_prior_decisions() -> None:
    check_ingest_row(_row("a", "b", MMC_JUSTIFICATION), [])  # no exception


def test_check_ingest_mmc_allowed_when_only_mmc_in_log() -> None:
    log = [_row("a", "b", MMC_JUSTIFICATION)]
    check_ingest_row(_row("a", "b", MMC_JUSTIFICATION), log)  # no exception


def test_check_ingest_hc_blocked_without_mmc_predecessor() -> None:
    with pytest.raises(ValueError, match="ManualMappingCuration"):
        check_ingest_row(_row("a", "b", HC_JUSTIFICATION), [])


def test_check_ingest_hc_allowed_with_mmc_predecessor() -> None:
    log = [_row("a", "b", MMC_JUSTIFICATION)]
    check_ingest_row(_row("a", "b", HC_JUSTIFICATION), log)  # no exception


def test_check_ingest_hc_correction_allowed_over_existing_hc() -> None:
    log = [_row("a", "b", MMC_JUSTIFICATION), _row("a", "b", HC_JUSTIFICATION)]
    check_ingest_row(_row("a", "b", HC_JUSTIFICATION), log)  # no exception


# ---------------------------------------------------------------------------
# CLI — ingest
# ---------------------------------------------------------------------------


def test_accredit_ingest_cli_adds_mmc_rows_to_log(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            }
        ],
    )
    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)])
    assert result.exit_code == 0, result.output + str(result.exception)
    log_path = tmp_path / "audit-log.sssom.tsv"
    rows = load_log(log_path)
    assert len(rows) == 1
    assert rows[0].subject_id == "a"


def test_accredit_ingest_cli_adds_hc_rows_to_log(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("a", "b", MMC_JUSTIFICATION)], log_path)

    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.95",
            }
        ],
    )
    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)])
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = load_log(log_path)
    assert len(rows) == 2
    assert rows[1].mapping_justification == HC_JUSTIFICATION


def test_accredit_ingest_cli_rejects_mmc_with_human_curation(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("a", "b", MMC_JUSTIFICATION)], log_path)
    append_log([_row("a", "b", HC_JUSTIFICATION)], log_path)

    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            }
        ],
    )
    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)])
    assert result.exit_code == 1


def test_accredit_ingest_cli_rejects_hc_without_predecessor(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.95",
            }
        ],
    )
    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)])
    assert result.exit_code == 1


def test_accredit_ingest_cli_no_partial_write_on_mixed_file(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    """One valid MMC + one invalid HC (no predecessor) → exit 1, log unchanged."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "c",
                "predicate_id": "skos:exactMatch",
                "object_id": "d",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.95",
            },
        ],
    )
    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)])
    assert result.exit_code == 1
    # Log should not exist or be empty
    assert not log_path.exists() or not load_log(log_path)


def test_accredit_ingest_cli_skips_composite_matching_rows(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:relatedMatch",
                "object_id": "b",
                "mapping_justification": COMPOSITE_JUSTIFICATION,
                "confidence": "0.7",
            },
            {
                "subject_id": "c",
                "predicate_id": "skos:relatedMatch",
                "object_id": "d",
                "mapping_justification": COMPOSITE_JUSTIFICATION,
                "confidence": "0.6",
            },
        ],
    )
    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)])
    assert result.exit_code == 0
    assert "skipped 2" in result.output or "skipped 2" in (result.stderr or "")


def test_accredit_ingest_cli_rejects_in_file_duplicate_mmc(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "a",
                "predicate_id": "skos:relatedMatch",
                "object_id": "b",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.8",
            },
        ],
    )
    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)])
    assert result.exit_code == 1


def test_accredit_ingest_cli_prints_count_to_stderr(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "c",
                "predicate_id": "skos:relatedMatch",
                "object_id": "d",
                "mapping_justification": COMPOSITE_JUSTIFICATION,
                "confidence": "0.7",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)]
    )
    assert result.exit_code == 0
    stderr = result.stderr if hasattr(result, "stderr") else result.output
    assert "Ingested" in stderr
    assert "skipped" in stderr


def test_accredit_ingest_hc_correction_over_existing_hc(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("a", "b", MMC_JUSTIFICATION)], log_path)
    append_log([_row("a", "b", HC_JUSTIFICATION)], log_path)

    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "owl:differentFrom",
                "object_id": "b",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.1",
            }
        ],
    )
    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "ingest", str(tsv)])
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = load_log(log_path)
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# CLI — review
# ---------------------------------------------------------------------------


def test_accredit_review_cli_outputs_pending_rows(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "review"])
    assert result.exit_code == 0, result.output
    assert "src:A" in result.output


def test_accredit_review_cli_empty_when_all_decided(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)
    append_log([_row("src:A", "mst:B", HC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "review"])
    assert result.exit_code == 0
    # No data rows — only header block
    data_lines = [
        ln
        for ln in result.output.splitlines()
        if ln.strip()
        and not ln.startswith("#")
        and ln
        != "subject_id\t"
        + "\t".join(
            [
                "predicate_id",
                "object_id",
                "mapping_justification",
                "confidence",
                "subject_label",
                "object_label",
                "mapping_date",
                "record_id",
            ]
        )
        and not ln.startswith("subject_id")
    ]
    assert not data_lines


def test_accredit_review_cli_outputs_valid_sssom_tsv(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:X", "mst:Y", MMC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "review"])
    assert result.exit_code == 0
    assert result.output.startswith("# sssom_version")
    assert "subject_id" in result.output


def test_accredit_review_cli_empty_when_log_absent(tmp_path: Path) -> None:
    # Config with log pointing to non-existent file
    log_path = tmp_path / "no-log.sssom.tsv"
    config = tmp_path / "rosetta.toml"
    config.write_text(f'[accredit]\nlog = "{log_path}"\n')

    result = CliRunner().invoke(cli, ["--config", str(config), "review"])
    assert result.exit_code == 0
    assert "subject_id" in result.output  # header-only TSV


# ---------------------------------------------------------------------------
# CLI — dump
# ---------------------------------------------------------------------------


def test_accredit_dump_cli_outputs_latest_hc_per_pair(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)
    append_log([_row("src:A", "mst:B", HC_JUSTIFICATION, predicate="skos:exactMatch")], log_path)

    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "dump"])
    assert result.exit_code == 0
    assert "src:A" in result.output
    assert HC_JUSTIFICATION in result.output


def test_accredit_dump_cli_omits_mmc_only_pairs(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "dump"])
    assert result.exit_code == 0
    # No data rows for MMC-only pair
    data_lines = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert not data_lines


# ---------------------------------------------------------------------------
# CLI — status
# ---------------------------------------------------------------------------


def test_accredit_status_cli_json_output(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["--config", str(tmp_rosetta_toml), "status"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["state"] == "pending"

    # Now add HC approval
    append_log([_row("src:A", "mst:B", HC_JUSTIFICATION, predicate="skos:exactMatch")], log_path)
    result2 = runner.invoke(cli, ["--config", str(tmp_rosetta_toml), "status"])
    assert result2.exit_code == 0
    data2 = json.loads(result2.output)
    assert data2[0]["state"] == "approved"


def test_accredit_status_cli_empty_when_log_absent(tmp_path: Path) -> None:
    log_path = tmp_path / "no-log.sssom.tsv"
    config = tmp_path / "rosetta.toml"
    config.write_text(f'[accredit]\nlog = "{log_path}"\n')

    result = CliRunner().invoke(cli, ["--config", str(config), "status"])
    assert result.exit_code == 0
    assert result.output.strip() == "[]"


# ---------------------------------------------------------------------------
# parse_sssom_tsv — edge cases and correctness
# ---------------------------------------------------------------------------


def test_parse_sssom_tsv_returns_empty_for_empty_file(tmp_path: Path) -> None:
    """parse_sssom_tsv returns [] for a zero-byte file."""
    path = tmp_path / "empty.sssom.tsv"
    path.write_text("")
    assert not parse_sssom_tsv(path)


def test_parse_sssom_tsv_returns_empty_for_header_only_file(tmp_path: Path) -> None:
    """parse_sssom_tsv returns [] for a file with only SSSOM comment header (no data rows)."""
    path = tmp_path / "header-only.sssom.tsv"
    path.write_text("# sssom_version: https://w3id.org/sssom/spec/0.15\n# mapping_set_id: test\n")
    assert not parse_sssom_tsv(path)


def test_parse_sssom_tsv_coerces_tz_naive_date_to_utc(tmp_path: Path) -> None:
    """parse_sssom_tsv coerces tz-naive ISO date strings to UTC-aware datetimes.

    A hand-crafted SSSOM file without '+00:00' suffix must not cause a TypeError
    when compared against tz-aware datetimes written by append_log.
    """
    path = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
                "mapping_date": "2026-04-15T12:00:00",  # tz-naive — no +00:00
            }
        ],
    )
    rows = parse_sssom_tsv(path)
    assert len(rows) == 1
    assert rows[0].mapping_date is not None
    # Must be tz-aware — comparison with tz-aware sentinel must not raise TypeError
    sentinel = datetime(1, 1, 1, tzinfo=UTC)
    assert rows[0].mapping_date.tzinfo is not None
    _ = rows[0].mapping_date > sentinel  # must not raise TypeError


def test_append_log_tab_in_label_does_not_corrupt_log(tmp_path: Path) -> None:
    """append_log uses csv.writer so tab characters in labels don't corrupt the TSV."""
    path = tmp_path / "log.sssom.tsv"
    row = SSSOMRow(
        subject_id="src:A",
        predicate_id="skos:exactMatch",
        object_id="mst:B",
        mapping_justification=MMC_JUSTIFICATION,
        confidence=0.9,
        subject_label="label with\ttab",
    )
    append_log([row], path)
    rows = load_log(path)
    assert len(rows) == 1
    assert rows[0].subject_label == "label with\ttab"


# ---------------------------------------------------------------------------
# dump — with HC correction
# ---------------------------------------------------------------------------


def test_accredit_dump_cli_outputs_latest_hc_after_correction(
    tmp_path: Path, tmp_rosetta_toml: Path
) -> None:
    """dump outputs exactly one row per pair — the latest HC — after an accreditor correction."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)
    append_log([_row("src:A", "mst:B", HC_JUSTIFICATION, predicate="skos:closeMatch")], log_path)
    # Accreditor corrects the decision
    append_log([_row("src:A", "mst:B", HC_JUSTIFICATION, predicate="skos:exactMatch")], log_path)

    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "dump"])
    assert result.exit_code == 0

    data_lines = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert len(data_lines) == 1
    assert "skos:exactMatch" in data_lines[0]
    assert "skos:closeMatch" not in data_lines[0]


# ---------------------------------------------------------------------------
# review → ingest round-trip
# ---------------------------------------------------------------------------


def test_review_ingest_round_trip(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """review output is valid SSSOM TSV that parse_sssom_tsv can re-read."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--config", str(tmp_rosetta_toml), "review"])
    assert result.exit_code == 0

    review_output = tmp_path / "review-output.sssom.tsv"
    review_output.write_text(result.output)
    rows = parse_sssom_tsv(review_output)
    assert len(rows) == 1
    assert rows[0].subject_id == "src:A"
    assert rows[0].mapping_justification == MMC_JUSTIFICATION
