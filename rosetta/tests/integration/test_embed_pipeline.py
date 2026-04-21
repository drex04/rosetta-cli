"""Integration test for rosetta-embed on nested-JSON ingest output (Phase 18-02)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import sentence_transformers
from click.testing import CliRunner

from rosetta.cli.embed import cli as embed_cli
from rosetta.cli.ingest import cli as ingest_cli
from rosetta.core.models import EmbeddingReport

pytestmark = [pytest.mark.integration]

# Pin the LaBSE vector dimension — if this changes, we want a loud failure.
_LABSE_DIM = 768


class _FakeLaBSE:
    """Pretends to be sentence_transformers.SentenceTransformer('LaBSE').

    Returns deterministic 768-dim zero vectors so we can assert the shape
    contract without downloading the real 1.2 GB model.
    """

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.zeros((len(texts), _LABSE_DIM), dtype=np.float32)


def test_embed_on_nested_json(
    tmp_path: Path, stress_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nested-JSON → LinkML → embed produces a 768-dim EmbeddingReport."""
    # 1. Ingest the nested JSON schema to LinkML YAML.
    linkml_out = tmp_path / "nested.linkml.yaml"
    ingest_result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [
            str(stress_dir / "nested_json_schema.json"),
            "--schema-format",
            "json-schema",
            "--output",
            str(linkml_out),
        ],
    )
    assert ingest_result.exit_code == 0, f"ingest failed: {ingest_result.stderr}"

    # 2. Mock LaBSE — same pattern as rosetta/tests/test_embed.py.
    monkeypatch.setattr(
        sentence_transformers,
        "SentenceTransformer",
        lambda _name: _FakeLaBSE(),
    )

    # 3. Embed the LinkML schema.
    embed_out = tmp_path / "nested.embed.json"
    embed_result = CliRunner(mix_stderr=False).invoke(
        embed_cli,
        [
            str(linkml_out),
            "-o",
            str(embed_out),
        ],
    )
    assert embed_result.exit_code == 0, f"embed failed: {embed_result.stderr}"

    # 4. Parse the Pydantic report.
    report = EmbeddingReport.model_validate_json(embed_out.read_text())
    entries = cast(dict[str, Any], report.root)
    assert entries, "expected at least one embedding entry"

    # Behavioural invariant: every lexical vector is 768-dim (LaBSE contract).
    for key, vec in entries.items():
        assert len(vec.lexical) == _LABSE_DIM, (
            f"expected {_LABSE_DIM}-dim lexical vector for {key}, got {len(vec.lexical)}"
        )
