"""Integration test for rosetta suggest on inheritance schema (Phase 18-02)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import sentence_transformers
from click.testing import CliRunner

from rosetta.cli.suggest import cli as suggest_cli
from rosetta.core.ledger import parse_sssom_tsv

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class _FakeLaBSE:
    """Return deterministic non-collinear 768-dim vectors keyed off text content.

    Using pure zeros would collapse cosine similarity; we hash the input text
    into a small bucket of orthogonal-ish vectors so the cosine matrix is
    well-defined and suggest can rank candidates.
    """

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), 768), dtype=np.float32)
        for i, t in enumerate(texts):
            seed = hash(t) & 0xFFFF
            rng = np.random.default_rng(seed)
            v = rng.normal(size=768).astype(np.float32)
            out[i] = v / (np.linalg.norm(v) + 1e-12)
        return out


def _install_fake_labse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sentence_transformers,
        "SentenceTransformer",
        lambda _name: _FakeLaBSE(),
    )


def test_suggest_inheritance_schema(
    tmp_path: Path,
    stress_dir: Path,
    master_schema_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inheritance LinkML → suggest against master produces SSSOM rows."""
    _install_fake_labse(monkeypatch)

    src_linkml = stress_dir / "linkml_inheritance.linkml.yaml"

    # Run suggest directly from schema YAMLs — embeddings are computed internally.
    out_tsv = tmp_path / "suggestions.sssom.tsv"
    audit_log = tmp_path / "audit-log.sssom.tsv"
    from rosetta.core.ledger import append_log

    append_log([], audit_log)

    result = CliRunner(mix_stderr=False).invoke(
        suggest_cli,
        [
            str(src_linkml),
            str(master_schema_path),
            "--output",
            str(out_tsv),
            "--audit-log",
            str(audit_log),
        ],
    )
    assert result.exit_code == 0, f"suggest failed: {result.stderr}"

    # Parse SSSOM TSV via the canonical loader.
    rows = parse_sssom_tsv(out_tsv)

    # Behavioural invariant: at least one suggestion row was emitted.
    # (We use the weak-form assertion from plan 18-02: inherited-slot coverage
    # is nice-to-have but depends on cosine neighbours, which — even with
    # randomised fake embeddings — is not reproducible without gaming the seed.)
    assert rows, "expected at least one SSSOM suggestion row"
