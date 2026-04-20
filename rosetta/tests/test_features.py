"""Tests for rosetta/core/features.py — structural feature extraction."""

from __future__ import annotations

from typing import Any

import pytest
from linkml_runtime.linkml_model import (  # type: ignore[import-untyped]
    ClassDefinition,
    SchemaDefinition,
    SlotDefinition,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_schema(
    classes: dict[str, dict[str, Any]] | None = None,
    slots: dict[str, dict[str, Any]] | None = None,
    name: str = "test_schema",
) -> SchemaDefinition:
    """Build a minimal SchemaDefinition for testing."""
    schema = SchemaDefinition(id=f"https://example.org/{name}", name=name)
    for cls_name, attrs in (classes or {}).items():
        cls = ClassDefinition(cls_name)
        for k, v in attrs.items():
            setattr(cls, k, v)
        schema.classes[cls_name] = cls  # pyright: ignore[reportCallIssue,reportOptionalSubscript,reportArgumentType]
    for slot_name, attrs in (slots or {}).items():
        slot = SlotDefinition(slot_name)
        for k, v in attrs.items():
            setattr(slot, k, v)
        schema.slots[slot_name] = slot  # pyright: ignore[reportCallIssue,reportOptionalSubscript,reportArgumentType]
    return schema


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_structural_features_classes_and_slots() -> None:
    """Schema with 2 classes + 3 slots → 5 entries; classes f0=1.0, slots f0=0.0."""
    from rosetta.core.features import extract_structural_features_linkml

    schema = _make_schema(
        classes={"ClassA": {}, "ClassB": {}},
        slots={"slot1": {}, "slot2": {}, "slot3": {}},
    )
    result = extract_structural_features_linkml(schema)

    assert len(result) == 5

    for cls_name in ("ClassA", "ClassB"):
        node_id = f"test_schema:{cls_name}"
        assert node_id in result
        assert result[node_id][0] == 1.0, f"{node_id} f0 should be 1.0 (is_class)"

    for slot_name in ("slot1", "slot2", "slot3"):
        node_id = f"test_schema:{slot_name}"
        assert node_id in result
        assert result[node_id][0] == 0.0, f"{node_id} f0 should be 0.0 (is_slot)"


def test_structural_features_hierarchy_depth() -> None:
    """A → B → C chain: depths 0, 1, 2 → normalized 0.0, 0.5, 1.0."""
    from rosetta.core.features import extract_structural_features_linkml

    schema = _make_schema(
        classes={
            "A": {},
            "B": {"is_a": "A"},
            "C": {"is_a": "B"},
        },
    )
    result = extract_structural_features_linkml(schema)

    assert len(result) == 3
    # max depth = 2; A=0→0.0, B=1→0.5, C=2→1.0
    assert result["test_schema:A"][1] == pytest.approx(0.0)
    assert result["test_schema:B"][1] == pytest.approx(0.5)
    assert result["test_schema:C"][1] == pytest.approx(1.0)


def test_structural_features_required_multivalued() -> None:
    """Slot with required=True, multivalued=True → f2=1.0, f3=1.0."""
    from rosetta.core.features import extract_structural_features_linkml

    schema = _make_schema(
        slots={"my_slot": {"required": True, "multivalued": True}},
    )
    result = extract_structural_features_linkml(schema)

    node_id = "test_schema:my_slot"
    assert node_id in result
    assert result[node_id][2] == pytest.approx(1.0), "f2 should be 1.0 (required)"
    assert result[node_id][3] == pytest.approx(1.0), "f3 should be 1.0 (multivalued)"


def test_structural_features_slot_usage_count() -> None:
    """Slot used by 2 of 4 classes → f4 = 2/4 = 0.5."""
    from rosetta.core.features import extract_structural_features_linkml

    schema = _make_schema(
        classes={
            "ClassA": {"slots": ["my_slot"]},
            "ClassB": {"slots": ["my_slot"]},
            "ClassC": {},
            "ClassD": {},
        },
        slots={"my_slot": {}},
    )
    result = extract_structural_features_linkml(schema)

    node_id = "test_schema:my_slot"
    assert node_id in result
    assert result[node_id][4] == pytest.approx(0.5), "f4 should be 2/4 = 0.5"


def test_structural_features_no_hierarchy() -> None:
    """Flat schema (no is_a) → all hierarchy_depth values 0.0."""
    from rosetta.core.features import extract_structural_features_linkml

    schema = _make_schema(
        classes={"X": {}, "Y": {}, "Z": {}},
    )
    result = extract_structural_features_linkml(schema)

    for node_id, features in result.items():
        assert features[1] == pytest.approx(0.0), f"{node_id} depth should be 0.0 in flat schema"


def test_structural_features_empty_schema() -> None:
    """Schema with no classes/slots → empty dict."""
    from rosetta.core.features import extract_structural_features_linkml

    schema = _make_schema()
    result = extract_structural_features_linkml(schema)

    assert not result
