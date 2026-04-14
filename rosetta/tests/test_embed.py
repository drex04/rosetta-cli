"""Tests for rosetta-embed: embedding.py core + embed CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from linkml_runtime.linkml_model import SchemaDefinition

# ---------------------------------------------------------------------------
# Shared fake model + fixture
# ---------------------------------------------------------------------------


class _FakeModel:
    def encode(self, texts):
        return np.zeros((len(texts), 4), dtype=np.float32)


@pytest.fixture
def mock_sentence_transformer(monkeypatch):
    import sentence_transformers

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda name: _FakeModel())


# ---------------------------------------------------------------------------
# Unit tests (no CLI runner)
# ---------------------------------------------------------------------------


def test_embedding_model_encode_shape(mock_sentence_transformer):
    """EmbeddingModel.encode returns a list of vectors with the expected shape."""
    from rosetta.core.embedding import EmbeddingModel

    model = EmbeddingModel("fake")
    result = model.encode(["a", "b"])

    assert len(result) == 2
    assert len(result[0]) == 4
    assert len(result[1]) == 4


class _FakeModelCapture:
    """Fake model that captures the texts passed to encode."""

    def __init__(self):
        self.last_texts = None

    def encode(self, texts):
        self.last_texts = texts
        return np.zeros((len(texts), 4), dtype=np.float32)


def test_encode_query_e5_prefix(monkeypatch):
    """encode_query applies 'query: ' prefix for E5 models."""
    import sentence_transformers

    from rosetta.core.embedding import EmbeddingModel

    fake = _FakeModelCapture()
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda name: fake)

    model = EmbeddingModel("intfloat/multilingual-e5-base")
    model.encode_query(["test query"])

    assert fake.last_texts == ["query: test query"]


def test_encode_passage_e5_prefix(monkeypatch):
    """encode applies 'passage: ' prefix for E5 models."""
    import sentence_transformers

    from rosetta.core.embedding import EmbeddingModel

    fake = _FakeModelCapture()
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda name: fake)

    model = EmbeddingModel("intfloat/multilingual-e5-large")
    model.encode(["test passage"])

    assert fake.last_texts == ["passage: test passage"]


def test_encode_query_non_e5_no_prefix(monkeypatch):
    """encode_query does NOT apply prefix for non-E5 models."""
    import sentence_transformers

    from rosetta.core.embedding import EmbeddingModel

    fake = _FakeModelCapture()
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda name: fake)

    model = EmbeddingModel("sentence-transformers/LaBSE")
    model.encode_query(["test query"])

    assert fake.last_texts == ["test query"]


# ---------------------------------------------------------------------------
# extract_text_inputs_linkml tests
# ---------------------------------------------------------------------------


def _make_schema(
    classes: dict[str, dict[str, Any]] | None = None,
    slots: dict[str, dict[str, Any]] | None = None,
    name: str = "test_schema",
) -> SchemaDefinition:
    """Build a minimal SchemaDefinition for testing."""
    from linkml_runtime.linkml_model import ClassDefinition, SlotDefinition

    schema = SchemaDefinition(id=f"https://example.org/{name}", name=name)
    for cls_name, attrs in (classes or {}).items():
        cls = ClassDefinition(cls_name)
        for k, v in attrs.items():
            setattr(cls, k, v)
        schema.classes[cls_name] = cls
    for slot_name, attrs in (slots or {}).items():
        slot = SlotDefinition(slot_name)
        for k, v in attrs.items():
            setattr(slot, k, v)
        schema.slots[slot_name] = slot
    return schema


def test_embed_linkml_base() -> None:
    """Minimal schema with one class, no flags → 1 result, text == class title."""
    from rosetta.core.embedding import extract_text_inputs_linkml

    schema = _make_schema(classes={"speed": {"title": "Speed"}})
    results = extract_text_inputs_linkml(schema)
    assert len(results) == 1
    node_id, label, text = results[0]
    assert node_id == "test_schema/speed"
    assert label == "Speed"
    assert text == "Speed"


def test_embed_linkml_definitions() -> None:
    """Class with description + include_definitions=True → description in text."""
    from rosetta.core.embedding import extract_text_inputs_linkml

    schema = _make_schema(classes={"speed": {"title": "Speed", "description": "Rate of movement"}})
    results = extract_text_inputs_linkml(schema, include_definitions=True)
    assert len(results) == 1
    assert "Rate of movement" in results[0][2]


def test_embed_linkml_parents() -> None:
    """Child class with is_a + include_parents=True → parent title in text."""
    from rosetta.core.embedding import extract_text_inputs_linkml

    schema = _make_schema(
        classes={
            "parent_class": {"title": "Parent"},
            "child_class": {"title": "Child", "is_a": "parent_class"},
        }
    )
    results = extract_text_inputs_linkml(schema, include_parents=True)
    child_result = next(r for r in results if "child_class" in r[0])
    assert "Parent" in child_result[2]


def test_embed_linkml_ancestors() -> None:
    """Grandchild → child → parent chain + include_ancestors=True → ancestor titles in text."""
    from rosetta.core.embedding import extract_text_inputs_linkml

    schema = _make_schema(
        classes={
            "grandparent": {"title": "Grandparent"},
            "parent": {"title": "Parent", "is_a": "grandparent"},
            "child": {"title": "Child", "is_a": "parent"},
        }
    )
    results = extract_text_inputs_linkml(schema, include_ancestors=True)
    child_result = next(r for r in results if "/child" in r[0])
    assert "Parent" in child_result[2]
    assert "Grandparent" in child_result[2]


def test_embed_linkml_children() -> None:
    """Parent class + child (is_a=parent) + include_children=True → child name in parent's text."""
    from rosetta.core.embedding import extract_text_inputs_linkml

    schema = _make_schema(
        classes={
            "vehicle": {"title": "Vehicle"},
            "car": {"title": "Car", "is_a": "vehicle"},
        }
    )
    results = extract_text_inputs_linkml(schema, include_children=True)
    parent_result = next(r for r in results if "/vehicle" in r[0])
    assert "Car" in parent_result[2]


def test_embed_linkml_ancestors_supersedes_parents() -> None:
    """include_ancestors=True + include_parents=True → ancestor path (superset), not just parent."""
    from rosetta.core.embedding import extract_text_inputs_linkml

    schema = _make_schema(
        classes={
            "gp": {"title": "Grandparent"},
            "p": {"title": "Parent", "is_a": "gp"},
            "c": {"title": "Child", "is_a": "p"},
        }
    )
    results_ancestors = extract_text_inputs_linkml(
        schema, include_ancestors=True, include_parents=True
    )
    child_result = next(r for r in results_ancestors if "/c" in r[0])
    # Both Grandparent and Parent should appear (ancestors is strict superset)
    assert "Grandparent" in child_result[2]
    assert "Parent" in child_result[2]


def test_embed_linkml_children_and_ancestors() -> None:
    """Both flags → text contains both ancestor titles and child names."""
    from rosetta.core.embedding import extract_text_inputs_linkml

    schema = _make_schema(
        classes={
            "root": {"title": "Root"},
            "mid": {"title": "Mid", "is_a": "root"},
            "leaf": {"title": "Leaf", "is_a": "mid"},
        }
    )
    results = extract_text_inputs_linkml(schema, include_ancestors=True, include_children=True)
    mid_result = next(r for r in results if "/mid" in r[0])
    assert "Root" in mid_result[2]  # ancestor
    assert "Leaf" in mid_result[2]  # child


def test_embed_linkml_no_flags() -> None:
    """All flags False → text is title only, no separator artefacts."""
    from rosetta.core.embedding import extract_text_inputs_linkml

    schema = _make_schema(classes={"speed": {"title": "Speed", "description": "A description"}})
    results = extract_text_inputs_linkml(schema)
    assert results[0][2] == "Speed"
    assert ". " not in results[0][2]


def test_embed_linkml_cli(tmp_path: Path, mock_sentence_transformer: pytest.FixtureRequest) -> None:
    """Click runner on a .linkml.yaml tmp file → exit 0, JSON output with at least one key."""
    from click.testing import CliRunner

    from rosetta.cli.embed import cli

    schema_content = {
        "id": "https://example.org/test",
        "name": "test_schema",
        "classes": {
            "Speed": {
                "title": "Speed",
                "description": "Rate of movement",
            }
        },
    }
    schema_file = tmp_path / "test.linkml.yaml"
    schema_file.write_text(yaml.dump(schema_content))
    output_file = tmp_path / "out.json"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--input",
            str(schema_file),
            "--output",
            str(output_file),
        ],
    )
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert len(data) >= 1
    # Each value should have a 'lexical' key
    first_val = next(iter(data.values()))
    assert "lexical" in first_val
