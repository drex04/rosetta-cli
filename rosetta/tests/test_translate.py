"""Tests for rosetta-translate CLI — LinkML YAML input/output."""

from __future__ import annotations

from typing import Any

import deepl
import deepl.exceptions
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_schema(
    name: str = "test_schema",
    classes: dict[str, dict[str, Any]] | None = None,
    slots: dict[str, dict[str, Any]] | None = None,
) -> Any:
    """Build a minimal SchemaDefinition."""
    from linkml_runtime.linkml_model import (  # type: ignore[import-untyped]
        ClassDefinition,
        SchemaDefinition,
        SlotDefinition,
    )

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


# ---------------------------------------------------------------------------
# Unit tests for translate_schema()
# ---------------------------------------------------------------------------


def test_translate_linkml_de_to_en(monkeypatch: pytest.MonkeyPatch) -> None:
    """German-titled class → English title after translation; original in aliases."""
    from rosetta.core.translation import translate_schema

    class FakeResult:
        def __init__(self, text: str) -> None:
            self.text = text

    def fake_translate_text(self: Any, texts: list[str], **kwargs: Any) -> list[FakeResult]:
        mapping = {"Geschwindigkeit": "Speed", "Speed": "Speed"}
        return [FakeResult(mapping.get(t, t)) for t in texts]

    monkeypatch.setattr("deepl.Translator.translate_text", fake_translate_text)

    schema = _make_schema(classes={"geschwindigkeit": {"title": "Geschwindigkeit"}})
    result = translate_schema(schema, source_lang="DE", deepl_key="fake-key")
    cls = result.classes["geschwindigkeit"]
    assert cls.title == "Speed"
    assert "Geschwindigkeit" in (cls.aliases or [])


def test_translate_linkml_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    """German-titled slot → English title after translation; original in aliases."""
    from rosetta.core.translation import translate_schema

    class FakeResult:
        def __init__(self, text: str) -> None:
            self.text = text

    def fake_translate_text(self: Any, texts: list[str], **kwargs: Any) -> list[FakeResult]:
        return [FakeResult("Speed" if "Geschwindigkeit" in t else t) for t in texts]

    monkeypatch.setattr("deepl.Translator.translate_text", fake_translate_text)

    schema = _make_schema(slots={"speed_kts": {"title": "Geschwindigkeit"}})
    result = translate_schema(schema, source_lang="DE", deepl_key="fake-key")
    slot = result.slots["speed_kts"]
    assert slot.title == "Speed"
    assert "Geschwindigkeit" in (slot.aliases or [])


def test_translate_linkml_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """source_lang='EN' → returned object is identical to input (no DeepL call)."""
    from rosetta.core.translation import translate_schema

    called: list[bool] = []

    def fake_translate_text(self: Any, *args: Any, **kwargs: Any) -> list[Any]:
        called.append(True)
        return []

    monkeypatch.setattr("deepl.Translator.translate_text", fake_translate_text)

    schema = _make_schema(classes={"speed": {"title": "Speed"}})
    result = translate_schema(schema, source_lang="EN", deepl_key="fake-key")
    assert result is schema
    assert not called


def test_translate_deepl_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock translate_text raises DeepLException → RuntimeError with 'DeepL API error'."""
    from rosetta.core.translation import translate_schema

    def fake_translate_text(self: Any, *args: Any, **kwargs: Any) -> list[Any]:
        raise deepl.exceptions.DeepLException("network error")

    monkeypatch.setattr("deepl.Translator.translate_text", fake_translate_text)

    schema = _make_schema(classes={"speed": {"title": "Geschwindigkeit"}})
    with pytest.raises(RuntimeError, match="DeepL API error"):
        translate_schema(schema, source_lang="DE", deepl_key="fake-key")
