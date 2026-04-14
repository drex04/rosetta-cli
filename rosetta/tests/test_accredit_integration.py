"""Integration tests: SSSOM-based accreditation feedback loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.suggest import cli as suggest_cli
from rosetta.core.models import SSSOMRow
from rosetta.core.similarity import apply_sssom_feedback

SRC_URI = "http://example.org/NOR#altitude"
TGT_URI = "http://nato.int/master#Altitude"
OTHER_TGT = "http://nato.int/master#Elevation"


def make_candidates() -> list[dict[str, object]]:
    return [
        {"uri": TGT_URI, "score": 0.75, "label": "Altitude"},
        {"uri": OTHER_TGT, "score": 0.60, "label": "Elevation"},
    ]


def make_approved_rows(predicate: str = "skos:relatedMatch") -> list[SSSOMRow]:
    return [
        SSSOMRow(
            subject_id=SRC_URI,
            predicate_id=predicate,
            object_id=TGT_URI,
            mapping_justification="semapv:LexicalMatching",
            confidence=0.8,
        )
    ]


def test_approve_boost() -> None:
    """Accredited mapping raises score of matching candidate."""
    approved_rows = make_approved_rows("skos:relatedMatch")
    candidates = make_candidates()
    result = apply_sssom_feedback(SRC_URI, candidates, approved_rows, boost=0.1)

    tgt = next(c for c in result if c["uri"] == TGT_URI)
    old_score = 0.75
    assert tgt["score"] == pytest.approx(old_score + 0.1, abs=0.001)
    assert tgt["score"] <= 1.0


def test_derank_revoked() -> None:
    """owl:differentFrom row decreases score but candidate is NOT removed."""
    approved_rows = make_approved_rows("owl:differentFrom")
    candidates = make_candidates()
    result = apply_sssom_feedback(SRC_URI, candidates, approved_rows, penalty=0.2)

    uris = [c["uri"] for c in result]
    # candidate is still present (not removed)
    assert TGT_URI in uris
    assert OTHER_TGT in uris

    tgt = next(c for c in result if c["uri"] == TGT_URI)
    # hard deranked: 0.75 - 0.2 = 0.55
    assert tgt["score"] < 0.75


def test_no_approved_rows_match_passthrough() -> None:
    """Candidates with no matching approved rows are unchanged."""
    approved_rows: list[SSSOMRow] = []  # empty
    result = apply_sssom_feedback(SRC_URI, make_candidates(), approved_rows)
    original = make_candidates()
    assert len(result) == len(original)
    for res, orig in zip(result, original):
        assert res["uri"] == orig["uri"]
        assert res["score"] == pytest.approx(float(orig["score"]))  # pyright: ignore[reportArgumentType]


def test_boost_cap_at_1() -> None:
    """Score boosted beyond 1.0 is capped at 1.0."""
    approved_rows = make_approved_rows("skos:relatedMatch")
    high_score_candidates: list[dict[str, object]] = [
        {"uri": TGT_URI, "score": 0.95, "label": "Altitude"}
    ]
    result = apply_sssom_feedback(SRC_URI, high_score_candidates, approved_rows, boost=0.1)
    assert result[0]["score"] == pytest.approx(1.0)


def test_empty_candidates() -> None:
    """Empty candidate list returns empty list regardless of approved rows."""
    approved_rows = make_approved_rows("skos:relatedMatch")
    result = apply_sssom_feedback(SRC_URI, [], approved_rows)
    assert result == []


def test_suggest_cli_with_approved_mappings(tmp_path: Path) -> None:
    """--approved-mappings flag through CliRunner: boosted score appears in TSV output."""
    import math

    # Use non-collinear vectors so cosine ~0.9 (leaves room for boost).
    # src: [0.9, 0, sqrt(1-0.81)], master TGT: [1,0,0] → cosine ~0.9
    sin_val = math.sqrt(1.0 - 0.81)
    src_emb = {
        SRC_URI: {"label": "Altitude", "lexical": [0.9, 0.0, sin_val]},
    }
    master_emb = {
        TGT_URI: {"label": "Altitude", "lexical": [1.0, 0.0, 0.0]},
        OTHER_TGT: {"label": "Elevation", "lexical": [0.0, 1.0, 0.0]},
    }
    src_file = tmp_path / "src.json"
    master_file = tmp_path / "master.json"
    src_file.write_text(json.dumps(src_emb))
    master_file.write_text(json.dumps(master_emb))

    # Run without approved mappings to get baseline
    runner = CliRunner()
    baseline = runner.invoke(suggest_cli, [str(src_file), str(master_file)])
    assert baseline.exit_code == 0, baseline.output
    baseline_lines = baseline.output.splitlines()
    baseline_data = [
        ln
        for ln in baseline_lines
        if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
    ]
    # Find TGT_URI row in baseline
    tgt_baseline_rows = [ln for ln in baseline_data if TGT_URI in ln]
    assert tgt_baseline_rows, "TGT_URI not in baseline output"
    baseline_score = float(tgt_baseline_rows[0].split("\t")[4])

    # Write approved SSSOM TSV with a boost row for the pair
    approved_tsv = tmp_path / "approved.sssom.tsv"
    approved_tsv.write_text(
        "# curie_map:\n"
        "#   skos: http://www.w3.org/2004/02/skos/core#\n"
        "#   semapv: https://w3id.org/semapv/vocab/\n"
        "subject_id\tpredicate_id\tobject_id\tmapping_justification\tconfidence\n"
        f"{SRC_URI}\tskos:relatedMatch\t{TGT_URI}\tsemapv:LexicalMatching\t0.8\n"
    )

    result = runner.invoke(
        suggest_cli,
        [str(src_file), str(master_file), "--approved-mappings", str(approved_tsv)],
    )
    assert result.exit_code == 0, result.output

    lines = result.output.splitlines()
    data_rows = [
        ln
        for ln in lines
        if ln.strip() and not ln.startswith("#") and not ln.startswith("subject_id")
    ]
    tgt_rows = [ln for ln in data_rows if TGT_URI in ln]
    assert tgt_rows, "TGT_URI not in boosted output"
    boosted_score = float(tgt_rows[0].split("\t")[4])

    assert boosted_score > baseline_score, (
        f"Expected boosted score ({boosted_score}) > baseline ({baseline_score})"
    )
