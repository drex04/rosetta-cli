"""Adversarial tests for unit-detection pitfalls (Phase 18-03, Task 6).

Tests 1-3 exercise ``rosetta.core.unit_detect`` directly — pure-core, no CLI.
Test 4 is the integration bridge: unit-detect → rosetta-lint surfaces the
'recognized but unmapped' dBm diagnostic as a finding in LintReport.

Locked-in context:
- Commit 3fc820b: ``detect_unit`` snake-cases CamelCase so ``hasAltitudeFt`` →
  ``has_Altitude_Ft`` and matches ``(?:^|_)ft$`` → ``unit:FT``.
- Commit ee69efb: lint's dBm diagnostic is restored — ``_unit_not_detected``
  emits an INFO finding whose message distinguishes "recognized but no QUDT IRI"
  from "no detectable unit at all".
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.lint import cli as lint_cli
from rosetta.core.models import LintReport
from rosetta.core.unit_detect import detect_unit, recognized_unit_without_iri

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Tests 1-3 — pure core: detect_unit / recognized_unit_without_iri
# ---------------------------------------------------------------------------


def test_detect_dbm_known_but_unmapped() -> None:
    """dBm is a recognized unit but has no QUDT IRI → (None, True).

    Locked by rosetta/core/unit_detect.py: the name-pattern for ``dbm`` maps
    to ``None`` (dBm has no standard QUDT IRI). ``detect_unit`` returns None
    for unrecognized AND for "recognized but no IRI"; ``recognized_unit_without_iri``
    disambiguates.
    """
    assert detect_unit("signal_dbm", "") is None
    assert recognized_unit_without_iri("signal_dbm", "")


def test_detect_british_metre_via_nlp() -> None:
    """British 'metre' spelling is caught via the description cascade.

    The name regex targets American 'meter'; 'metre' in the name won't fire
    the name pattern. When the description reads 'altitude in metres',
    the description regex / NLP cascade resolves to ``unit:M``.

    This pins that the cascade (name → description → quantulum3 NLP) does
    handle British spelling through the description path. If this ever
    regresses, update the description to exercise the fallback more
    aggressively OR pin a detailed xfail reason for the broken cascade.
    """
    result = detect_unit("height_metre", "altitude in metres")
    assert result == "unit:M", (
        f"expected British 'metres' in description to resolve to unit:M via the "
        f"description/NLP cascade; got {result!r}"
    )


def test_detect_ambiguous_slot_name() -> None:
    """'count' has no unit — cascade returns None and NOT 'recognized-without-IRI'.

    Distinguishes a genuinely unitless field from a dBm-style 'recognized but
    unmapped' case: ``recognized_unit_without_iri`` must be False.
    """
    assert detect_unit("count", "") is None
    assert not recognized_unit_without_iri("count", "")


# ---------------------------------------------------------------------------
# Test 4 — integration: lint surfaces the 'recognized but unmapped' finding
# ---------------------------------------------------------------------------


_MMC: str = "semapv:ManualMappingCuration"
_SSSOM_HEADER: str = (
    "# sssom_version: https://w3id.org/sssom/spec/0.15\n"
    "# mapping_set_id: http://rosetta.interop/test-adversarial-units\n"
    "# curie_map:\n"
    "#   ex: http://example.org/\n"
    "#   semapv: https://w3id.org/semapv/vocab/\n"
    "#   skos: http://www.w3.org/2004/02/skos/core#\n"
)
_SSSOM_COLS: list[str] = [
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


def _write_sssom(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write(_SSSOM_HEADER)
        writer = csv.DictWriter(f, fieldnames=_SSSOM_COLS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in _SSSOM_COLS})


def _no_accredit_toml(tmp_path: Path) -> Path:
    config = tmp_path / "rosetta.toml"
    config.write_text("[suggest]\ntop_k = 5\n")
    return config


def test_lint_surfaces_recognized_but_unmapped_unit(tmp_path: Path) -> None:
    """rosetta-lint emits a finding for a 'recognized but unmapped' dBm field.

    The lint pipeline calls ``_check_units``; for each row where ``detect_unit``
    returns None on either side, ``_unit_not_detected`` emits an INFO finding.
    When the name/description is recognized (e.g. contains 'dbm') but has no
    QUDT IRI, the finding's message contains "recognized" per commit ee69efb.

    This test is the bridge between core unit-detect and the lint pipeline.
    """
    sssom = tmp_path / "dbm_case.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                # subject field is recognized (dBm) but has no QUDT IRI mapping.
                "subject_id": "ex:signal_dbm",
                "predicate_id": "skos:exactMatch",
                # target: another dBm field on the master side — keeps this row
                # firmly in the "unit_not_detected on both sides" regime so we
                # don't accidentally cross into a dimension-compat check.
                "object_id": "ex:rx_dbm",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            }
        ],
    )
    config = _no_accredit_toml(tmp_path)

    result = CliRunner(mix_stderr=False).invoke(
        lint_cli,
        ["--sssom", str(sssom), "--config", str(config)],
    )

    # 1. Exit code — INFO-level findings do not raise exit to 1. Any BLOCK finding
    #    would surface as exit 1, so a dBm-only run should exit 0.
    assert result.exit_code == 0, (
        f"expected exit 0 (INFO-only findings) but got {result.exit_code}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    # 2. Stderr is quiet for INFO-only runs; stdout holds the JSON LintReport.
    assert result.stdout, "lint should emit a JSON LintReport on stdout"
    report = LintReport.model_validate_json(result.stdout)
    # 3. Behavioural invariant: at least one INFO finding targets the recognized-
    #    but-unmapped dBm slot and its message carries the "recognized" phrasing
    #    introduced in the dBm diagnostic restore (commit ee69efb).
    dbm_findings = [
        f
        for f in report.findings
        if f.rule == "unit_not_detected" and "recognized" in f.message.lower()
    ]
    assert dbm_findings, (
        f"expected at least one 'unit_not_detected' finding whose message mentions "
        f"'recognized' (the dBm diagnostic path); got findings="
        f"{[(f.rule, f.severity, f.message) for f in report.findings]!r}"
    )
