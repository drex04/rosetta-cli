"""Unit tests for rosetta.core.models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rosetta.core.models import (
    EmbeddingReport,
    EmbeddingVectors,
    FnmlSuggestion,
    LintFinding,
    LintReport,
    LintSummary,
    SSSOMRow,
)

# ---------------------------------------------------------------------------
# LintFinding
# ---------------------------------------------------------------------------


def test_lint_finding_rejects_invalid_severity() -> None:
    with pytest.raises(ValidationError):
        LintFinding(
            rule="E1",
            severity="ERROR",  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
            source_uri="urn:test:field1",
            message="bad severity",
        )


def test_lint_finding_valid_severities() -> None:
    for sev in ("BLOCK", "WARNING", "INFO"):
        f = LintFinding(
            rule="E1",
            severity=sev,  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
            source_uri="urn:test:field1",
            message="ok",
        )
        assert f.severity == sev


def test_lint_finding_fnml_suggestion_none_serialises() -> None:
    data = LintFinding(
        rule="E1",
        severity="INFO",
        source_uri="urn:test:field1",
        message="no suggestion",
    ).model_dump(mode="json")
    assert "fnml_suggestion" in data
    assert data["fnml_suggestion"] is None


def test_lint_finding_target_uri_optional() -> None:
    f = LintFinding(
        rule="E2",
        severity="WARNING",
        source_uri="urn:test:field1",
        message="no target",
    )
    assert f.target_uri is None


# ---------------------------------------------------------------------------
# LintReport
# ---------------------------------------------------------------------------


def test_lint_report_constructs_from_valid_data() -> None:
    finding = LintFinding(
        rule="E1",
        severity="BLOCK",
        source_uri="urn:test:field1",
        target_uri="urn:qudt:Metre",
        message="unit mismatch",
    )
    summary = LintSummary(block=1, warning=0, info=0)
    report = LintReport(findings=[finding], summary=summary)

    assert len(report.findings) == 1
    assert report.summary.block == 1


def test_lint_report_model_dump_round_trip() -> None:
    finding = LintFinding(
        rule="E1",
        severity="BLOCK",
        source_uri="urn:test:field1",
        message="unit mismatch",
    )
    summary = LintSummary(block=1, warning=0, info=0)
    report = LintReport(findings=[finding], summary=summary)

    data = report.model_dump(mode="json")

    assert isinstance(data, dict)
    assert "findings" in data
    assert "summary" in data
    assert isinstance(data["findings"], list)
    assert data["findings"][0]["rule"] == "E1"
    assert data["summary"]["block"] == 1
    assert data["summary"]["warning"] == 0

    # Reconstruct from dumped data
    report2 = LintReport.model_validate(data)
    assert report2 == report


# ---------------------------------------------------------------------------
# FnmlSuggestion
# ---------------------------------------------------------------------------


def test_fnml_suggestion_label_none_serialises() -> None:
    data = FnmlSuggestion(fnml_function="fno:Multiply").model_dump(mode="json")
    assert "label" in data
    assert data["label"] is None


def test_fnml_suggestion_with_all_fields() -> None:
    s = FnmlSuggestion(
        fnml_function="fno:LinearConvert",
        label="metres to feet",
        multiplier=3.28084,
        offset=0.0,
    )
    assert s.label == "metres to feet"
    assert s.multiplier == pytest.approx(3.28084)


def test_fnml_suggestion_getitem() -> None:
    s = FnmlSuggestion(fnml_function="fno:Multiply", multiplier=2.0)
    assert s["fnml_function"] == "fno:Multiply"
    assert "multiplier" in s


# ---------------------------------------------------------------------------
# SSSOMRow
# ---------------------------------------------------------------------------


def test_sssom_row_round_trip() -> None:
    row = SSSOMRow(
        subject_id="http://ex.org/FieldA",
        predicate_id="skos:relatedMatch",
        object_id="http://ex.org/onto#ConceptB",
        mapping_justification="semapv:LexicalMatching",
        confidence=0.85,
        subject_label="FieldA",
        object_label="ConceptB",
    )
    data = row.model_dump(mode="json")
    assert data["subject_id"] == "http://ex.org/FieldA"
    assert data["confidence"] == 0.85
    assert data["subject_label"] == "FieldA"
    roundtrip = SSSOMRow.model_validate(data)
    assert roundtrip == row

    # New fields: mapping_date and record_id
    row_with_extras = SSSOMRow(
        subject_id="ex:foo",
        predicate_id="skos:exactMatch",
        object_id="ex:bar",
        mapping_justification="semapv:ManualMappingCuration",
        confidence=0.95,
        mapping_date=datetime(2026, 1, 1, tzinfo=UTC),
        record_id="abc-123",
    )
    assert row_with_extras.mapping_date == datetime(2026, 1, 1, tzinfo=UTC)
    assert row_with_extras.record_id == "abc-123"

    # Backward compat: row without new fields defaults to None
    row_minimal = SSSOMRow(
        subject_id="ex:foo",
        predicate_id="skos:exactMatch",
        object_id="ex:bar",
        mapping_justification="semapv:ManualMappingCuration",
        confidence=0.5,
    )
    assert row_minimal.mapping_date is None
    assert row_minimal.record_id is None


# ---------------------------------------------------------------------------
# EmbeddingReport
# ---------------------------------------------------------------------------


def test_embedding_report_root_model_serialisation() -> None:
    data = EmbeddingReport(
        root={
            "urn:field:beta": EmbeddingVectors(lexical=[0.1, 0.2, 0.3]),
        }
    ).model_dump(mode="json")

    assert isinstance(data, dict)
    assert "urn:field:beta" in data
    assert data["urn:field:beta"]["lexical"] == pytest.approx([0.1, 0.2, 0.3])
