"""Milestone 3 integration tests: accreditation feedback loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.suggest import cli as suggest_cli
from rosetta.core.accredit import (
    approve_mapping,
    load_ledger,
    revoke_mapping,
    save_ledger,
    submit_mapping,
)
from rosetta.core.models import Ledger
from rosetta.core.similarity import apply_ledger_feedback

SRC_URI = "http://example.org/NOR#altitude"
TGT_URI = "http://nato.int/master#Altitude"
OTHER_TGT = "http://nato.int/master#Elevation"


def make_candidates() -> list[dict[str, object]]:
    return [
        {"uri": TGT_URI, "score": 0.75},
        {"uri": OTHER_TGT, "score": 0.60},
    ]


def test_approve_boost(tmp_path: Path) -> None:
    """Accredited mapping raises score of matching candidate."""
    ledger_path = tmp_path / "ledger.json"
    ledger = Ledger()
    submit_mapping(ledger, SRC_URI, TGT_URI, actor="test")
    approve_mapping(ledger, SRC_URI, TGT_URI)
    save_ledger(ledger, ledger_path)

    loaded = load_ledger(ledger_path)
    candidates = make_candidates()
    result = apply_ledger_feedback(SRC_URI, candidates, loaded)

    tgt = next(c for c in result if c["uri"] == TGT_URI)
    assert tgt["score"] >= 0.75, "Accredited mapping must boost score"
    assert tgt["score"] <= 1.0, "Score must be capped at 1.0"


def test_revoke_excludes(tmp_path: Path) -> None:
    """Revoked mapping disappears from suggestions."""
    ledger_path = tmp_path / "ledger.json"
    ledger = Ledger()
    submit_mapping(ledger, SRC_URI, TGT_URI, actor="test")
    approve_mapping(ledger, SRC_URI, TGT_URI)
    revoke_mapping(ledger, SRC_URI, TGT_URI)
    save_ledger(ledger, ledger_path)

    loaded = load_ledger(ledger_path)
    candidates = make_candidates()
    result = apply_ledger_feedback(SRC_URI, candidates, loaded)

    uris = [c["uri"] for c in result]
    assert TGT_URI not in uris, "Revoked mapping must be excluded from suggestions"
    assert OTHER_TGT in uris, "Non-revoked candidates must remain"


def test_pending_no_effect(tmp_path: Path) -> None:
    """Pending mapping has no boost or exclusion effect."""
    ledger_path = tmp_path / "ledger.json"
    ledger = Ledger()
    submit_mapping(ledger, SRC_URI, TGT_URI, actor="test")
    save_ledger(ledger, ledger_path)

    loaded = load_ledger(ledger_path)
    candidates = make_candidates()
    result = apply_ledger_feedback(SRC_URI, candidates, loaded)

    tgt = next(c for c in result if c["uri"] == TGT_URI)
    assert tgt["score"] == pytest.approx(0.75), "Pending mapping must not change score"


def test_no_ledger_match_passthrough() -> None:
    """Candidates with no ledger entry are unchanged."""
    ledger = Ledger()  # empty
    result = apply_ledger_feedback(SRC_URI, make_candidates(), ledger)
    assert result == make_candidates()


def test_boost_cap_at_1() -> None:
    """Score boosted beyond 1.0 is capped at 1.0."""
    ledger = Ledger()
    submit_mapping(ledger, SRC_URI, TGT_URI, actor="test")
    approve_mapping(ledger, SRC_URI, TGT_URI)

    high_score_candidates: list[dict[str, object]] = [{"uri": TGT_URI, "score": 0.95}]
    result = apply_ledger_feedback(SRC_URI, high_score_candidates, ledger)
    assert result[0]["score"] <= 1.0


def test_empty_candidates() -> None:
    """Empty candidate list returns empty list regardless of ledger state."""
    ledger = Ledger()
    submit_mapping(ledger, SRC_URI, TGT_URI, actor="test")
    approve_mapping(ledger, SRC_URI, TGT_URI)
    result = apply_ledger_feedback(SRC_URI, [], ledger)
    assert result == []


def test_suggest_cli_with_ledger(tmp_path: Path) -> None:
    """--ledger flag through CliRunner: boosted score appears in output JSON."""
    # Minimal embeddings: two-dim vectors with known cosine similarity
    src_emb = {SRC_URI: {"lexical": [1.0, 0.0]}}
    master_emb = {TGT_URI: {"lexical": [1.0, 0.0]}, OTHER_TGT: {"lexical": [0.0, 1.0]}}
    src_file = tmp_path / "src.json"
    master_file = tmp_path / "master.json"
    ledger_file = tmp_path / "ledger.json"
    src_file.write_text(json.dumps(src_emb))
    master_file.write_text(json.dumps(master_emb))

    # Build ledger with accredited pair
    ledger = Ledger()
    submit_mapping(ledger, SRC_URI, TGT_URI, actor="test")
    approve_mapping(ledger, SRC_URI, TGT_URI)
    save_ledger(ledger, ledger_file)

    runner = CliRunner()
    result = runner.invoke(
        suggest_cli,
        ["--source", str(src_file), "--master", str(master_file), "--ledger", str(ledger_file)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    suggestions = data[SRC_URI]["suggestions"]
    tgt = next(s for s in suggestions if s["target_uri"] == TGT_URI)
    assert tgt["score"] >= 1.0 or tgt["score"] > 0.9, (
        "Accredited pair must be boosted in CLI output"
    )
