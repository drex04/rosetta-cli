"""Adversarial schema-mismatch tests (Plan 18-03 Task 3).

Precondition (verified against production at plan-write time):
the only lint rule codes emitted by ``rosetta/cli/lint.py`` are
``datatype_mismatch`` (line 212) and ``unit_dimension_mismatch`` (line 171).
Neither ``missing_required`` nor ``unit_incompatible`` exist — do not
reference them here.

Note on the removed ``missing_required`` test: the original plan proposed
a third test asserting a ``missing_required`` lint rule. That rule code is
not present in production. LinkML-level ``required`` is covered by
``rosetta/tests/integration/test_validate_pipeline.py`` (Plan 18-02
Task 3 item 4), so it is not duplicated here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from rosetta.cli.ledger import cli as ledger_cli
from rosetta.cli.suggest import cli as suggest_cli
from rosetta.core.ledger import parse_sssom_tsv
from rosetta.core.models import LintReport

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# LaBSE mock — deterministic per-text vectors (see rosetta/tests/test_embed.py
# and rosetta/tests/integration/test_full_chain.py for the canonical pattern).
# ---------------------------------------------------------------------------


class _FakeLaBSE:
    """Deterministic LaBSE stand-in. Vectors bucketed by semantic keyword."""

    def encode(self, texts: list[str]) -> np.ndarray:
        rows: list[list[float]] = []
        for i, tx in enumerate(texts):
            v = np.zeros(4, dtype=np.float32)
            lower = tx.lower()
            if "speed" in lower:
                v[0] = 1.0
            elif "altitude" in lower or "alt" in lower:
                v[1] = 1.0
            else:
                v[i % 4] = 0.5
            rows.append(v.tolist())
        return np.array(rows, dtype=np.float32)


def _install_fake_labse(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentence_transformers

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda _name: _FakeLaBSE())


def _write_src_schema(path: Path, slot_name: str, slot_range: str) -> None:
    path.write_text(
        "id: https://w3id.org/rosetta/adversarial/src\n"
        "name: src\n"
        "default_prefix: src\n"
        "prefixes:\n"
        "  src: https://w3id.org/rosetta/adversarial/src/\n"
        "  linkml: https://w3id.org/linkml/\n"
        "classes:\n"
        "  Track:\n"
        "    slots:\n"
        f"      - {slot_name}\n"
        "slots:\n"
        f"  {slot_name}:\n"
        f"    range: {slot_range}\n"
    )


def _write_master_schema(path: Path, slot_name: str, slot_range: str) -> None:
    path.write_text(
        "id: https://w3id.org/rosetta/adversarial/master\n"
        "name: master\n"
        "default_prefix: mc\n"
        "prefixes:\n"
        "  mc: https://w3id.org/rosetta/adversarial/master/\n"
        "  linkml: https://w3id.org/linkml/\n"
        "classes:\n"
        "  Track:\n"
        "    slots:\n"
        f"      - {slot_name}\n"
        "slots:\n"
        f"  {slot_name}:\n"
        f"    range: {slot_range}\n"
    )


def test_suggest_type_divergence_flagged_by_lint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source ``speed_kts: integer`` vs master ``speed_kts: string`` → lint
    emits a ``datatype_mismatch`` WARNING.

    OBSERVED-BEHAVIOR NOTE: Plan 18-03 Task 3 originally proposed
    ``integer`` vs ``float`` for the type divergence. Production's
    ``_NUMERIC_LINKML`` set (``rosetta/cli/lint.py`` line 33) treats both
    as numeric, so numeric/numeric pairs do NOT trigger
    ``datatype_mismatch``. This test uses ``integer`` vs ``string`` — the
    minimal numeric-vs-non-numeric mismatch that the rule actually fires
    on. If ``_NUMERIC_LINKML`` or ``_check_datatype`` changes (e.g. adds
    numeric-granularity comparisons), update this test deliberately.

    Pinned observed values:
    - ``suggest.exit_code == 0``
    - ``lint.exit_code == 0`` (WARNING-only findings; no BLOCK ⇒ exit 0)
    - at least one finding has ``rule == "datatype_mismatch"``
    """
    _install_fake_labse(monkeypatch)

    src_yaml = tmp_path / "src.linkml.yaml"
    master_yaml = tmp_path / "master.linkml.yaml"
    _write_src_schema(src_yaml, "speed_kts", "integer")
    _write_master_schema(master_yaml, "speed_kts", "string")

    runner = CliRunner(mix_stderr=False)

    dummy_log = tmp_path / "audit-log.sssom.tsv"
    dummy_log.write_text("")

    sssom_out = tmp_path / "candidates.sssom.tsv"
    suggest_result = runner.invoke(
        suggest_cli,
        [
            str(src_yaml),
            str(master_yaml),
            "--output",
            str(sssom_out),
            "--audit-log",
            str(dummy_log),
        ],
    )

    # 1. Exit code — suggest succeeds
    assert suggest_result.exit_code == 0, (
        f"suggest failed: exit={suggest_result.exit_code} stderr={suggest_result.stderr!r}"
    )
    assert sssom_out.exists()

    # Lint only checks user-confirmed mappings (MMC/HC), so we keep only the
    # speed_kts→speed_kts slot row (one mapping per subject) and patch the
    # justification to MMC to simulate the accredit step. Keeping all rows
    # would trigger max_one_mmc_per_subject BLOCK (multiple rows per subject).
    lines = sssom_out.read_text().splitlines(keepends=True)
    header = [ln for ln in lines if ln.startswith("#")]
    col_line = next(ln for ln in lines if not ln.startswith("#"))
    data_lines = [ln for ln in lines if not ln.startswith("#") and ln != col_line]
    # Keep only the slot-to-slot row (speed_kts → speed_kts)
    slot_rows = [
        ln
        for ln in data_lines
        if "speed_kts" in ln.split("\t")[0] and "speed_kts" in ln.split("\t")[2]
    ]
    filtered = "".join(header) + col_line + "".join(slot_rows)
    patched = filtered.replace("semapv:LexicalMatching", "semapv:ManualMappingCuration").replace(
        "semapv:CompositeMatching", "semapv:ManualMappingCuration"
    )
    sssom_out.write_text(patched)

    # Run lint via ledger append --dry-run over the SSSOM output
    lint_result = runner.invoke(
        ledger_cli,
        [
            "--audit-log",
            str(dummy_log),
            "append",
            "--dry-run",
            "--role",
            "analyst",
            "--source-schema",
            str(src_yaml),
            "--master-schema",
            str(master_yaml),
            str(sssom_out),
        ],
    )

    # 1. Exit code — observed: 0 (WARNING-only, no BLOCK).
    # Pin the observed value so a future severity-to-exit-code change breaks
    # this test intentionally.
    assert lint_result.exit_code == 0, (
        f"lint exit drift: expected 0 (WARNING-only), got {lint_result.exit_code}; "
        f"stderr={lint_result.stderr!r}"
    )

    # 2. Structured output — parse via Pydantic model; confirm the rule fires
    report = LintReport.model_validate_json(lint_result.output)
    dt_findings = [f for f in report.findings if f.rule == "datatype_mismatch"]
    assert dt_findings, (
        f"expected at least one datatype_mismatch finding; "
        f"got rules={[f.rule for f in report.findings]}"
    )

    # 3. Behavioral invariant — the mismatch finding names both the integer
    # source and the string target in its message
    msg = dt_findings[0].message.lower()
    assert "integer" in msg and "string" in msg, (
        f"datatype_mismatch message should mention both types; got {dt_findings[0].message!r}"
    )


def test_renamed_field_survives_as_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Source ``altitude_ft`` vs master ``altitude`` → suggest produces a row
    linking the two; the predicate is deterministic (``skos:relatedMatch``).

    OBSERVED-BEHAVIOR NOTE: ``rosetta suggest`` currently emits
    ``skos:relatedMatch`` for every row regardless of score magnitude.
    This test pins that predicate; if suggest's predicate-selection logic
    becomes score-dependent (e.g. ``skos:exactMatch`` for high scores,
    ``skos:relatedMatch`` otherwise), update this test deliberately.
    """
    _install_fake_labse(monkeypatch)

    src_yaml = tmp_path / "src.linkml.yaml"
    master_yaml = tmp_path / "master.linkml.yaml"
    _write_src_schema(src_yaml, "altitude_ft", "float")
    _write_master_schema(master_yaml, "altitude", "float")

    runner = CliRunner(mix_stderr=False)

    dummy_log = tmp_path / "audit-log.sssom.tsv"
    dummy_log.write_text("")

    sssom_out = tmp_path / "candidates.sssom.tsv"
    suggest_result = runner.invoke(
        suggest_cli,
        [
            str(src_yaml),
            str(master_yaml),
            "--output",
            str(sssom_out),
            "--audit-log",
            str(dummy_log),
        ],
    )

    # 1. Exit code
    assert suggest_result.exit_code == 0, (
        f"suggest failed: exit={suggest_result.exit_code} stderr={suggest_result.stderr!r}"
    )
    assert sssom_out.exists()

    # 2. Structured output — parse SSSOM TSV; confirm ≥1 row
    rows = parse_sssom_tsv(sssom_out)
    assert rows, "expected at least one SSSOM row for the renamed-field mapping"

    # 3. Behavioral invariant — the renamed pairing `altitude_ft → altitude`
    # is present among the rows, using `skos:relatedMatch` (deterministic per
    # current suggest output). If predicate selection becomes score-dependent,
    # relax this assertion and keep only the row-existence check.
    rename_rows = [
        r for r in rows if r.subject_id.endswith("altitude_ft") and r.object_id.endswith("altitude")
    ]
    assert rename_rows, (
        f"expected altitude_ft → altitude row; got pairs="
        f"{[(r.subject_id, r.object_id) for r in rows]}"
    )
    assert rename_rows[0].predicate_id == "skos:relatedMatch", (
        f"expected skos:relatedMatch predicate (observed-behavior pinned); "
        f"got {rename_rows[0].predicate_id!r}"
    )
