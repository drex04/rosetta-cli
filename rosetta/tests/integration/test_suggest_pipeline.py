"""Integration test for rosetta suggest on inheritance schema (Phase 18-02)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import sentence_transformers
from click.testing import CliRunner

from rosetta.cli.embed import cli as embed_cli
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


def _embed_schema(linkml_path: Path, out_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sentence_transformers,
        "SentenceTransformer",
        lambda _name: _FakeLaBSE(),
    )
    result = CliRunner(mix_stderr=False).invoke(
        embed_cli,
        [str(linkml_path), "--output", str(out_path)],
    )
    assert result.exit_code == 0, f"embed failed: {result.stderr}"


def test_suggest_inheritance_schema(
    tmp_path: Path,
    stress_dir: Path,
    master_schema_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inheritance LinkML → embed → suggest against master produces SSSOM rows."""
    # 1. Embed the inheritance fixture directly (it is already LinkML YAML).
    src_linkml = stress_dir / "linkml_inheritance.linkml.yaml"
    src_embed = tmp_path / "src.embed.json"
    _embed_schema(src_linkml, src_embed, monkeypatch)

    # 2. Embed the master schema.
    master_embed = tmp_path / "master.embed.json"
    _embed_schema(master_schema_path, master_embed, monkeypatch)

    # 3. Run suggest — writes SSSOM TSV.
    out_tsv = tmp_path / "suggestions.sssom.tsv"
    audit_log = tmp_path / "audit-log.sssom.tsv"
    from rosetta.core.ledger import append_log

    append_log([], audit_log)

    result = CliRunner(mix_stderr=False).invoke(
        suggest_cli,
        [
            str(src_embed),
            str(master_embed),
            "--output",
            str(out_tsv),
            "--audit-log",
            str(audit_log),
        ],
    )
    assert result.exit_code == 0, f"suggest failed: {result.stderr}"

    # 4. Parse SSSOM TSV via the canonical loader.
    rows = parse_sssom_tsv(out_tsv)

    # Behavioural invariant: at least one suggestion row was emitted.
    # (We use the weak-form assertion from plan 18-02: inherited-slot coverage
    # is nice-to-have but depends on cosine neighbours, which — even with
    # randomised fake embeddings — is not reproducible without gaming the seed.)
    assert rows, "expected at least one SSSOM suggestion row"
