"""Unit tests for accreditation audit-log pipeline and CLI."""

from __future__ import annotations

import csv
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.ledger import cli
from rosetta.core.ledger import (
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
from rosetta.core.lint import check_datatype
from rosetta.core.models import SSSOM_COLUMNS, LintFinding, LintReport, LintSummary, SSSOMRow

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
    with path.open("w") as f:
        f.write(header)
        writer = csv.DictWriter(
            f,
            fieldnames=SSSOM_COLUMNS,
            delimiter="\t",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in SSSOM_COLUMNS})
    return path


# ---------------------------------------------------------------------------
# Schema fixtures for append tests that invoke run_lint
# ---------------------------------------------------------------------------

_MINIMAL_SCHEMA = """\
id: https://example.org/test
name: test_schema
prefixes:
  linkml: https://w3id.org/linkml/
imports:
  - linkml:types
classes:
  TestClass:
    attributes:
      test_field:
        range: string
"""


@pytest.fixture()
def source_schema(tmp_path: Path) -> Path:
    p = tmp_path / "source.yaml"
    p.write_text(_MINIMAL_SCHEMA, encoding="utf-8")
    return p


@pytest.fixture()
def master_schema(tmp_path: Path) -> Path:
    p = tmp_path / "master.yaml"
    p.write_text(_MINIMAL_SCHEMA.replace("test_schema", "master_schema"), encoding="utf-8")
    return p


def _noop_lint(*args: object, **kwargs: object) -> LintReport:
    """Return an empty LintReport — used in tests that don't exercise the lint gate."""
    return LintReport(findings=[], summary=LintSummary(block=0, warning=0, info=0))


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
# CLI — append
# ---------------------------------------------------------------------------


def test_accredit_append_cli_adds_mmc_rows_to_log(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
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
            }
        ],
    )
    result = CliRunner().invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = load_log(log_path)
    assert len(rows) == 1
    assert rows[0].subject_id == "a"


def test_accredit_append_cli_adds_hc_rows_to_log(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
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
    result = CliRunner().invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "accreditor",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = load_log(log_path)
    assert len(rows) == 2
    assert rows[1].mapping_justification == HC_JUSTIFICATION


def test_accredit_append_cli_rejects_mmc_with_human_curation(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
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
    result = CliRunner().invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 1


def test_accredit_append_cli_rejects_hc_without_predecessor(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
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
    result = CliRunner().invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "accreditor",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 1


def test_accredit_append_cli_no_partial_write_on_mixed_file(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HC row with no MMC predecessor → accreditor rejects it, exit 1, log unchanged."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    # Seed only MMC for pair (a, b), not (c, d) — so the HC for (c, d) has no predecessor
    append_log([_row("a", "b", MMC_JUSTIFICATION)], log_path)
    rows_before = load_log(log_path)

    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.95",
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
    result = CliRunner().invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "accreditor",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 1
    # Log unchanged — only the seeded MMC row remains
    rows_after = load_log(log_path)
    assert len(rows_after) == len(rows_before)


def test_accredit_append_cli_skips_composite_matching_rows(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
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
    result = CliRunner().invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0
    assert "skipped 2" in result.output or "skipped 2" in (result.stderr or "")


def test_accredit_append_cli_rejects_in_file_duplicate_mmc(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
) -> None:
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
                "subject_id": "a",
                "predicate_id": "skos:relatedMatch",
                "object_id": "b",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.8",
            },
        ],
    )
    result = CliRunner().invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 1


def test_accredit_append_cli_prints_count_to_stderr(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
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
                "predicate_id": "skos:relatedMatch",
                "object_id": "d",
                "mapping_justification": COMPOSITE_JUSTIFICATION,
                "confidence": "0.7",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0
    stderr = result.stderr if hasattr(result, "stderr") else result.output
    assert "Appended" in stderr
    assert "skipped" in stderr


def test_accredit_append_hc_correction_over_existing_hc(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
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
    result = CliRunner().invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "accreditor",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    rows = load_log(log_path)
    assert len(rows) == 3


def test_accredit_append_cli_appends_mmc_on_reingest(
    tmp_path: Path,
    tmp_rosetta_toml: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-ingesting an MMC row already in the log appends it again (no dedup in new impl)."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("a", "b", MMC_JUSTIFICATION)], log_path)

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
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0, result.output + str(result.exception)
    stderr = result.stderr if hasattr(result, "stderr") else result.output
    assert "Appended" in stderr


# ---------------------------------------------------------------------------
# CLI — review
# ---------------------------------------------------------------------------


def test_accredit_review_cli_outputs_pending_rows(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--audit-log", str(log_path), "review"])
    assert result.exit_code == 0, result.output
    assert "src:A" in result.output


def test_accredit_review_cli_empty_when_all_decided(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)
    append_log([_row("src:A", "mst:B", HC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--audit-log", str(log_path), "review"])
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

    result = CliRunner().invoke(cli, ["--audit-log", str(log_path), "review"])
    assert result.exit_code == 0
    assert result.output.startswith("# sssom_version")
    assert "subject_id" in result.output


def test_accredit_review_cli_empty_when_log_absent(tmp_path: Path) -> None:
    # --audit-log pointing to non-existent file → review returns header-only TSV
    log_path = tmp_path / "no-log.sssom.tsv"

    result = CliRunner().invoke(cli, ["--audit-log", str(log_path), "review"])
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

    result = CliRunner().invoke(cli, ["--audit-log", str(log_path), "dump"])
    assert result.exit_code == 0
    assert "src:A" in result.output
    assert HC_JUSTIFICATION in result.output


def test_accredit_dump_cli_omits_mmc_only_pairs(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--audit-log", str(log_path), "dump"])
    assert result.exit_code == 0
    # No data rows for MMC-only pair
    data_lines = [
        ln
        for ln in result.output.splitlines()
        if ln.strip() and not ln.startswith(("#", "subject_id"))
    ]
    assert not data_lines


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

    result = CliRunner().invoke(cli, ["--audit-log", str(log_path), "dump"])
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
# review → append round-trip
# ---------------------------------------------------------------------------


def test_review_append_round_trip(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    """review output is valid SSSOM TSV that parse_sssom_tsv can re-read."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)

    result = CliRunner().invoke(cli, ["--audit-log", str(log_path), "review"])
    assert result.exit_code == 0

    review_output = tmp_path / "review-output.sssom.tsv"
    review_output.write_text(result.output)
    rows = parse_sssom_tsv(review_output)
    assert len(rows) == 1
    assert rows[0].subject_id == "src:A"
    assert rows[0].mapping_justification == MMC_JUSTIFICATION


# ---------------------------------------------------------------------------
# Task 4a — Composite round-trip (mapping_group_id / composition_expr)
# ---------------------------------------------------------------------------


def test_accredit_audit_log_composite_round_trip(tmp_path: Path) -> None:
    """Two rows sharing a mapping_group_id round-trip through append_log/load_log."""
    log_path = tmp_path / "audit.sssom.tsv"
    rows = [
        SSSOMRow(
            subject_id="src:lat",
            predicate_id="skos:exactMatch",
            object_id="ex:geoPoint-from-lat-lon",
            mapping_justification="semapv:HumanCuration",
            confidence=1.0,
            subject_label="latitude",
            object_label="geoPoint",
            object_type="composed entity expression",
            mapping_group_id="grp-geo-1",
            composition_expr='{lat} + "," + {lon}',
        ),
        SSSOMRow(
            subject_id="src:lon",
            predicate_id="skos:exactMatch",
            object_id="ex:geoPoint-from-lat-lon",
            mapping_justification="semapv:HumanCuration",
            confidence=1.0,
            subject_label="longitude",
            object_label="geoPoint",
            object_type="composed entity expression",
            mapping_group_id="grp-geo-1",
            composition_expr='{lat} + "," + {lon}',
        ),
    ]
    append_log(rows, log_path)

    loaded = load_log(log_path)
    assert len(loaded) == 2
    assert {r.subject_id for r in loaded} == {"src:lat", "src:lon"}
    for r in loaded:
        assert r.object_id == "ex:geoPoint-from-lat-lon"
        assert r.object_type == "composed entity expression"
        assert r.mapping_group_id == "grp-geo-1"
        assert r.composition_expr == '{lat} + "," + {lon}'


# ---------------------------------------------------------------------------
# Task 4b — Strict column validation
# ---------------------------------------------------------------------------


def test_load_log_rejects_9col_file(tmp_path: Path) -> None:
    """A 9-column SSSOM file is rejected with a descriptive error."""
    log_9 = tmp_path / "old_9col.sssom.tsv"
    log_9.write_text(
        SSSOM_HEADER + "subject_id\tpredicate_id\tobject_id\tmapping_justification\t"
        "confidence\tsubject_label\tobject_label\tmapping_date\trecord_id\n"
        "src:a\tskos:exactMatch\tmst:b\tsemapv:HumanCuration\t1.0\ta\tb\t"
        "2026-04-01T00:00:00+00:00\trec-1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="wrong columns"):
        load_log(log_9)


def test_load_log_rejects_11col_file(tmp_path: Path) -> None:
    """An 11-column SSSOM file is rejected with a descriptive error."""
    log_11 = tmp_path / "old_11col.sssom.tsv"
    log_11.write_text(
        SSSOM_HEADER + "subject_id\tpredicate_id\tobject_id\tmapping_justification\t"
        "confidence\tsubject_label\tobject_label\tmapping_date\trecord_id\t"
        "subject_datatype\tobject_datatype\n"
        "src:a\tskos:exactMatch\tmst:b\tsemapv:HumanCuration\t1.0\ta\tb\t"
        "2026-04-01T00:00:00+00:00\trec-1\tinteger\tdouble\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="wrong columns"):
        load_log(log_11)


# ---------------------------------------------------------------------------
# Task 4e — Migration tests (Task 3b coverage)
# ---------------------------------------------------------------------------


def test_load_log_rejects_stale_9col_file(tmp_path: Path) -> None:
    """A 9-column audit log raises ValueError with a descriptive message."""
    log = tmp_path / "audit.sssom.tsv"
    log.write_text(
        SSSOM_HEADER + "subject_id\tpredicate_id\tobject_id\tmapping_justification\t"
        "confidence\tsubject_label\tobject_label\tmapping_date\trecord_id\n"
        "src:a\tskos:exactMatch\tmst:b\tsemapv:HumanCuration\t1.0\ta\tb\t"
        "2026-04-01T00:00:00+00:00\trec-1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="wrong columns"):
        load_log(log)


def test_append_log_second_append_succeeds(tmp_path: Path) -> None:
    """Appending twice to a current-shape file works without errors."""
    log = tmp_path / "audit.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id="src:a",
                predicate_id="skos:exactMatch",
                object_id="mst:b",
                mapping_justification="semapv:HumanCuration",
                confidence=1.0,
            )
        ],
        log,
    )
    append_log(
        [
            SSSOMRow(
                subject_id="src:c",
                predicate_id="skos:exactMatch",
                object_id="mst:d",
                mapping_justification="semapv:HumanCuration",
                confidence=1.0,
            )
        ],
        log,
    )
    loaded = load_log(log)
    assert len(loaded) == 2


# ---------------------------------------------------------------------------
# Task 5 — New append / transform tests
# ---------------------------------------------------------------------------


def test_append_requires_role(tmp_path: Path, source_schema: Path, master_schema: Path) -> None:
    """Missing --role → Click UsageError exit 2."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(tmp_path, [])
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 2


def test_append_analyst_appends_mmc_only(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Analyst role: only MMC rows land in log; CompositeMatching rows are skipped."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "src:C",
                "predicate_id": "skos:relatedMatch",
                "object_id": "mst:D",
                "mapping_justification": COMPOSITE_JUSTIFICATION,
                "confidence": "0.7",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0, result.stderr
    rows = load_log(log_path)
    assert len(rows) == 1
    assert rows[0].subject_id == "src:A"
    assert rows[0].mapping_justification == MMC_JUSTIFICATION


def test_append_analyst_blocks_hc_rows(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
) -> None:
    """Analyst role: HC row in candidates → BLOCK lint finding, exit 1, nothing appended."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    # Seed the log with an MMC predecessor so HC is state-valid
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.95",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 1
    # Log should still have only the original row
    rows = load_log(log_path)
    assert len(rows) == 1
    assert rows[0].mapping_justification == MMC_JUSTIFICATION


def test_append_accreditor_appends_hc_only(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accreditor role: only HC rows are appended; MMC rows are skipped."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    # Seed MMC predecessor required for HC state-machine check
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.95",
            },
            {
                "subject_id": "src:C",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:D",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.8",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "accreditor",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0, result.stderr
    rows = load_log(log_path)
    # Only the HC row is appended (plus the seeded MMC predecessor)
    assert len(rows) == 2
    hc_rows = [r for r in rows if r.mapping_justification == HC_JUSTIFICATION]
    assert len(hc_rows) == 1
    assert hc_rows[0].subject_id == "src:A"


def test_append_lint_gate_block(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
) -> None:
    """Duplicate MMC pair triggers BLOCK lint finding → exit 1, nothing appended."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:X",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:Y",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "src:X",
                "predicate_id": "skos:relatedMatch",
                "object_id": "mst:Y",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.8",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 1
    assert not log_path.exists() or not load_log(log_path)
    assert "Lint failed: records were not appended" in result.stderr


def test_append_lint_gate_warning_proceeds(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WARNING lint finding → rows still appended; report emitted on stderr."""

    def _mock_warning(*args: object, **kwargs: object) -> LintReport:
        return LintReport(
            findings=[
                LintFinding(
                    rule="test_warning",
                    severity="WARNING",
                    source_uri="src:A",
                    message="test warning",
                )
            ],
            summary=LintSummary(block=0, warning=1, info=0),
        )

    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _mock_warning)
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0, result.stderr
    # Row was appended
    rows = load_log(log_path)
    assert len(rows) == 1
    # Warning report was emitted on stderr
    assert "WARNING" in result.stderr


def test_append_dry_run_no_side_effect(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--dry-run: audit log file unchanged, lint report on stdout."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--dry-run",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0
    # Audit log must NOT have been created
    assert not log_path.exists()
    # Report JSON on stdout
    assert "findings" in result.stdout


def test_append_dry_run_exit_code(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
) -> None:
    """--dry-run with BLOCK finding → exit 1; without → exit 0."""
    log_path_block = tmp_path / "audit-block.sssom.tsv"
    # Two duplicate MMC rows → BLOCK
    tsv_block = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:X",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:Y",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "src:X",
                "predicate_id": "skos:relatedMatch",
                "object_id": "mst:Y",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.8",
            },
        ],
        filename="block_input.sssom.tsv",
    )
    result_block = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path_block),
            "append",
            "--role",
            "analyst",
            "--dry-run",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv_block),
        ],
    )
    assert result_block.exit_code == 1

    # Clean single MMC row → no BLOCK → exit 0
    log_path_ok = tmp_path / "audit-ok.sssom.tsv"
    tsv_ok = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
        ],
        filename="ok_input.sssom.tsv",
    )
    result_ok = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path_ok),
            "append",
            "--role",
            "analyst",
            "--dry-run",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv_ok),
        ],
    )
    assert result_ok.exit_code == 0


def test_append_requires_schemas(tmp_path: Path) -> None:
    """Missing --source-schema or --master-schema → Click UsageError exit 2."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(tmp_path, [])

    # Missing both schemas
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            str(tsv),
        ],
    )
    assert result.exit_code == 2

    # Missing --master-schema only
    schema = tmp_path / "src.yaml"
    schema.write_text(_MINIMAL_SCHEMA, encoding="utf-8")
    result2 = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(schema),
            str(tsv),
        ],
    )
    assert result2.exit_code == 2


def test_append_analyst_mixed_hc_mmc_blocks(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
) -> None:
    """Analyst with mixed MMC+HC candidates → BLOCK (hc_in_candidates), exit 1, nothing appended."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    # Seed so HC is state-valid
    append_log([_row("src:A", "mst:B", MMC_JUSTIFICATION)], log_path)
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:C",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:D",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.95",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 1
    # No new rows beyond the seeded one
    rows = load_log(log_path)
    assert len(rows) == 1


def test_append_accreditor_zero_hc_rows(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Accreditor with file containing only MMC rows → exit 0, empty append."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "accreditor",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0
    # No rows appended — file may not exist or be empty
    assert not log_path.exists() or not load_log(log_path)


def test_append_role_plus_dry_run(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--role analyst --dry-run: lint report on stdout, no side effects."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
        ],
    )
    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--dry-run",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(tsv),
        ],
    )
    assert result.exit_code == 0
    # Audit log not written
    assert not log_path.exists()
    # JSON report on stdout
    assert "findings" in result.stdout
    assert "summary" in result.stdout


# ---------------------------------------------------------------------------
# check_datatype unit tests
# ---------------------------------------------------------------------------


def _dtype_row(subject_datatype: str | None, object_datatype: str | None) -> SSSOMRow:
    return SSSOMRow(
        subject_id="src:x",
        predicate_id="skos:exactMatch",
        object_id="mst:y",
        mapping_justification="semapv:ManualMappingCuration",
        confidence=0.9,
        subject_datatype=subject_datatype,
        object_datatype=object_datatype,
    )


def test_check_datatype_numeric_vs_nonnumeric_blocks() -> None:
    """Numeric vs non-numeric → BLOCK."""
    findings: list[LintFinding] = []
    check_datatype(findings, _dtype_row("integer", "string"))
    assert len(findings) == 1
    assert findings[0].rule == "datatype_mismatch"
    assert findings[0].severity == "BLOCK"


def test_check_datatype_narrowing_blocks() -> None:
    """Float-family → integer-family → BLOCK (would truncate decimal values)."""
    findings: list[LintFinding] = []
    check_datatype(findings, _dtype_row("double", "integer"))
    assert len(findings) == 1
    assert findings[0].rule == "datatype_narrowing"
    assert findings[0].severity == "BLOCK"
    assert "truncate" in findings[0].message


def test_check_datatype_widening_no_finding() -> None:
    """Integer-family → float-family → no finding (lossless)."""
    findings: list[LintFinding] = []
    check_datatype(findings, _dtype_row("integer", "double"))
    assert not findings


def test_check_datatype_same_type_no_finding() -> None:
    """Same type → no finding."""
    findings: list[LintFinding] = []
    check_datatype(findings, _dtype_row("float", "float"))
    assert not findings


def test_check_datatype_missing_types_no_finding() -> None:
    """Missing datatypes → no finding."""
    findings: list[LintFinding] = []
    check_datatype(findings, _dtype_row(None, "integer"))
    assert not findings


# ---------------------------------------------------------------------------
# Dedup on append
# ---------------------------------------------------------------------------


def test_append_analyst_skips_duplicate_triples(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-appending the same file should not create duplicate rows."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    log_path = tmp_path / "audit-log.sssom.tsv"
    tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
        ],
    )
    runner = CliRunner(mix_stderr=False)
    cmd = [
        "--audit-log",
        str(log_path),
        "append",
        "--role",
        "analyst",
        "--source-schema",
        str(source_schema),
        "--master-schema",
        str(master_schema),
        str(tsv),
    ]
    # First append
    result1 = runner.invoke(cli, cmd)
    assert result1.exit_code == 0, result1.stderr
    assert len(load_log(log_path)) == 1

    # Second append of same file — should be deduped
    result2 = runner.invoke(cli, cmd)
    assert result2.exit_code == 0, result2.stderr
    assert "skipped 1 duplicate" in result2.stderr
    assert len(load_log(log_path)) == 1


def test_append_dedup_allows_different_justification(
    tmp_path: Path,
    source_schema: Path,
    master_schema: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HC row for an existing MMC triple is not a duplicate (different justification)."""
    monkeypatch.setattr("rosetta.cli.ledger.run_lint", _noop_lint)
    monkeypatch.setattr("rosetta.cli.ledger.check_ingest_row", lambda row, log: None)
    log_path = tmp_path / "audit-log.sssom.tsv"

    mmc_tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": MMC_JUSTIFICATION,
                "confidence": "0.9",
            },
        ],
        filename="mmc.sssom.tsv",
    )
    hc_tsv = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "src:A",
                "predicate_id": "skos:exactMatch",
                "object_id": "mst:B",
                "mapping_justification": HC_JUSTIFICATION,
                "confidence": "0.9",
            },
        ],
        filename="hc.sssom.tsv",
    )
    runner = CliRunner(mix_stderr=False)
    # Analyst appends MMC
    result1 = runner.invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(mmc_tsv),
        ],
    )
    assert result1.exit_code == 0, result1.stderr
    assert len(load_log(log_path)) == 1

    # Accreditor appends HC for same triple — should NOT be deduped
    result2 = runner.invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "accreditor",
            "--source-schema",
            str(source_schema),
            "--master-schema",
            str(master_schema),
            str(hc_tsv),
        ],
    )
    assert result2.exit_code == 0, result2.stderr
    assert "duplicate" not in result2.stderr
    assert len(load_log(log_path)) == 2


# ---------------------------------------------------------------------------
# conversion_function field — Task 4
# ---------------------------------------------------------------------------


def test_sssom_columns_includes_conversion_function() -> None:
    from rosetta.core.models import SSSOM_COLUMNS

    assert "conversion_function" in SSSOM_COLUMNS
    assert len(SSSOM_COLUMNS) == 16


def test_sssom_row_with_conversion_function() -> None:
    from rosetta.core.models import SSSOMRow

    row = SSSOMRow(
        subject_id="src:field1",
        predicate_id="skos:exactMatch",
        object_id="tgt:field1",
        mapping_justification="semapv:ManualMappingCuration",
        confidence=0.95,
        conversion_function="grel:math_round",
    )
    assert row.conversion_function == "grel:math_round"


def test_parse_old_15col_sssom(tmp_path: Path) -> None:
    """15-column SSSOM files parse with conversion_function=None."""
    from rosetta.core.ledger import _SSSOM_COLUMNS_V15, parse_sssom_tsv

    log_path = tmp_path / "old.sssom.tsv"
    header = "\t".join(_SSSOM_COLUMNS_V15)
    data_row = "\t".join(
        [
            "src:a",
            "skos:exactMatch",
            "tgt:a",
            "semapv:ManualMappingCuration",
            "0.8",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    log_path.write_text(f"# comment\n{header}\n{data_row}\n", encoding="utf-8")
    rows = parse_sssom_tsv(log_path)
    assert len(rows) == 1
    assert rows[0].conversion_function is None


def test_roundtrip_16col_sssom(tmp_path: Path) -> None:
    """Write row with conversion_function, re-read, verify preserved."""
    from rosetta.core.ledger import append_log, parse_sssom_tsv
    from rosetta.core.models import SSSOMRow

    row = SSSOMRow(
        subject_id="src:x",
        predicate_id="skos:exactMatch",
        object_id="tgt:x",
        mapping_justification="semapv:ManualMappingCuration",
        confidence=0.9,
        conversion_function="grel:math_round",
    )
    log_path = tmp_path / "log.sssom.tsv"
    append_log([row], log_path)
    rows = parse_sssom_tsv(log_path)
    assert len(rows) == 1
    assert rows[0].conversion_function == "grel:math_round"


def test_append_to_existing_15col_stays_consistent(tmp_path: Path) -> None:
    """Appending to 15-col file doesn't corrupt it with mixed-width rows."""
    from rosetta.core.ledger import _SSSOM_COLUMNS_V15, append_log, parse_sssom_tsv
    from rosetta.core.models import SSSOMRow

    log_path = tmp_path / "log.sssom.tsv"
    # Write a minimal 15-col file manually
    header = "\t".join(_SSSOM_COLUMNS_V15)
    data_row = "\t".join(
        [
            "src:a",
            "skos:exactMatch",
            "tgt:a",
            "semapv:ManualMappingCuration",
            "0.8",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    log_path.write_text(f"# comment\n{header}\n{data_row}\n", encoding="utf-8")

    # Append a new row via append_log
    new_row = SSSOMRow(
        subject_id="src:b",
        predicate_id="skos:exactMatch",
        object_id="tgt:b",
        mapping_justification="semapv:ManualMappingCuration",
        confidence=0.75,
        conversion_function="grel:math_floor",  # will be dropped in 15-col mode
    )
    append_log([new_row], log_path)

    # All data lines (non-comment) must have exactly 15 tab-separated fields
    lines = [
        ln for ln in log_path.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")
    ]
    for line in lines:
        assert len(line.split("\t")) == 15, f"Line has wrong column count: {line}"

    # Parse succeeds and returns 2 rows with conversion_function=None
    rows = parse_sssom_tsv(log_path)
    assert len(rows) == 2
    assert all(r.conversion_function is None for r in rows)


def test_validate_header_wrong_count_raises(tmp_path: Path) -> None:
    """14 or 17 column headers raise ValueError."""
    import pytest

    from rosetta.core.ledger import parse_sssom_tsv

    bad_path = tmp_path / "bad.sssom.tsv"
    bad_path.write_text("col1\tcol2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_sssom_tsv(bad_path)
