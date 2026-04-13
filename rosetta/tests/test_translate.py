"""Tests for rosetta-translate CLI and core translation logic."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import RDFS, Graph

from rosetta.cli.translate import cli
from rosetta.core.rdf_utils import ROSE_NS
from rosetta.core.translation import translate_labels

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_field_ttl(label: str, lang_tag: str | None = None) -> str:
    """Build minimal TTL with one rose:Field node having the given rdfs:label."""
    lang_suffix = f"@{lang_tag}" if lang_tag else ""
    return f"""
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rose: <http://rosetta.interop/ns/> .

rose:field_001 rdf:type rose:Field ;
    rdfs:label "{label}"{lang_suffix} .
"""


def _graph_from_ttl(ttl: str) -> Graph:
    g = Graph()
    g.parse(data=ttl, format="turtle")
    return g


# ---------------------------------------------------------------------------
# Fake DeepL stubs
# ---------------------------------------------------------------------------


class FakeResult:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeTranslator:
    instantiated: int = 0
    call_count: int = 0
    last_source_lang: str | None = None

    def __init__(self, api_key: str) -> None:
        FakeTranslator.instantiated += 1
        FakeTranslator.call_count = 0

    def translate_text(
        self,
        texts: list[str],
        *,
        target_lang: str,
        source_lang: str | None = None,
    ) -> list[FakeResult]:
        FakeTranslator.call_count += 1
        FakeTranslator.last_source_lang = source_lang
        return [FakeResult("Translated text") for _ in texts]


class FakeTranslatorCustom:
    """Translator that returns a configurable mapping."""

    call_count: int = 0
    last_texts: list[str] = []
    last_source_lang: str | None = None

    def __init__(self, api_key: str, mapping: dict[str, str]) -> None:
        FakeTranslatorCustom.call_count = 0
        self._mapping = mapping

    def translate_text(
        self,
        texts: list[str],
        *,
        target_lang: str,
        source_lang: str | None = None,
    ) -> list[FakeResult]:
        FakeTranslatorCustom.call_count += 1
        FakeTranslatorCustom.last_texts = list(texts)
        FakeTranslatorCustom.last_source_lang = source_lang
        return [FakeResult(self._mapping.get(t, t)) for t in texts]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_translate_passthrough_source_lang_en(monkeypatch: pytest.MonkeyPatch) -> None:
    """EN source_lang must return graph unchanged with no DeepL call."""
    instantiated: list[bool] = []

    class TrackingTranslator:
        def __init__(self, api_key: str) -> None:
            instantiated.append(True)

    monkeypatch.setattr("deepl.Translator", TrackingTranslator)

    g = _graph_from_ttl(_make_field_ttl("Zielreichweite"))
    result = translate_labels(g, source_lang="EN", api_key="fake")

    labels = list(result.objects(ROSE_NS.field_001, RDFS.label))  # pyright: ignore[reportArgumentType]
    assert len(labels) == 1
    assert str(labels[0]) == "Zielreichweite"
    assert list(result.subject_objects(ROSE_NS.originalLabel)) == []
    assert instantiated == [], "deepl.Translator must NOT be instantiated for EN passthrough"


def test_translate_passthrough_source_lang_en_us(monkeypatch: pytest.MonkeyPatch) -> None:
    """EN-US source_lang must also pass through (startswith('EN') guard)."""
    instantiated: list[bool] = []

    class TrackingTranslator:
        def __init__(self, api_key: str) -> None:
            instantiated.append(True)

    monkeypatch.setattr("deepl.Translator", TrackingTranslator)

    g = _graph_from_ttl(_make_field_ttl("Zielreichweite"))
    result = translate_labels(g, source_lang="EN-US", api_key="fake")

    labels = list(result.objects(ROSE_NS.field_001, RDFS.label))  # pyright: ignore[reportArgumentType]
    assert str(labels[0]) == "Zielreichweite"
    assert list(result.subject_objects(ROSE_NS.originalLabel)) == []
    assert instantiated == []


def test_translate_adds_original_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """Translator stub returns 'Target range'; graph must show new label and originalLabel."""
    mapping = {"Zielreichweite": "Target range"}

    def make_translator(api_key: str) -> FakeTranslatorCustom:
        return FakeTranslatorCustom(api_key, mapping)

    monkeypatch.setattr("deepl.Translator", make_translator)

    g = _graph_from_ttl(_make_field_ttl("Zielreichweite"))
    result = translate_labels(g, source_lang="DE", api_key="fake")

    labels = list(result.objects(ROSE_NS.field_001, RDFS.label))  # pyright: ignore[reportArgumentType]
    assert len(labels) == 1
    assert str(labels[0]) == "Target range"

    orig_labels = list(result.objects(ROSE_NS.field_001, ROSE_NS.originalLabel))  # pyright: ignore[reportArgumentType]
    assert len(orig_labels) == 1
    assert str(orig_labels[0]) == "Zielreichweite"


def test_translate_deduplicates_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two fields with the same label should result in a single translate_text call with 1 item."""
    mapping = {"Entfernung": "Distance"}

    def make_translator(api_key: str) -> FakeTranslatorCustom:
        return FakeTranslatorCustom(api_key, mapping)

    monkeypatch.setattr("deepl.Translator", make_translator)

    ttl = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rose: <http://rosetta.interop/ns/> .

rose:field_001 rdf:type rose:Field ; rdfs:label "Entfernung" .
rose:field_002 rdf:type rose:Field ; rdfs:label "Entfernung" .
"""
    g = _graph_from_ttl(ttl)
    translate_labels(g, source_lang="DE", api_key="fake")

    assert FakeTranslatorCustom.call_count == 1
    assert FakeTranslatorCustom.last_texts == ["Entfernung"]


def test_translate_missing_api_key_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CLI must exit 1 and mention DEEPL_API_KEY when key is absent and source is not EN."""
    ttl_file = tmp_path / "input.ttl"
    ttl_file.write_text(_make_field_ttl("Zielreichweite"))

    # Remove DEEPL_API_KEY from env
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["--input", str(ttl_file), "--source-lang", "DE"], env={})
    assert result.exit_code == 1
    assert "DEEPL_API_KEY" in result.output


def test_translate_cli_passthrough_stdout(tmp_path: Path) -> None:
    """CLI with --source-lang EN must exit 0 and emit the original TTL to stdout."""
    ttl_file = tmp_path / "input.ttl"
    ttl_file.write_text(_make_field_ttl("Zielreichweite"))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--input", str(ttl_file), "--output", "-", "--source-lang", "EN"],
        env={"DEEPL_API_KEY": ""},
    )
    assert result.exit_code == 0
    assert "Zielreichweite" in result.output


def test_translate_empty_graph_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty graph (no rose:Field nodes) should return cleanly; translate_text never called."""
    monkeypatch.setattr("deepl.Translator", FakeTranslator)
    FakeTranslator.instantiated = 0

    g = Graph()
    result = translate_labels(g, source_lang="DE", api_key="fake")

    assert isinstance(result, Graph)
    assert FakeTranslator.call_count == 0


def test_translate_auto_lang_passes_none_to_deepl(monkeypatch: pytest.MonkeyPatch) -> None:
    """source_lang='auto' must translate with source_lang=None passed to DeepL."""
    mapping = {"Hallo": "Hello"}

    def make_translator(api_key: str) -> FakeTranslatorCustom:
        return FakeTranslatorCustom(api_key, mapping)

    monkeypatch.setattr("deepl.Translator", make_translator)

    g = _graph_from_ttl(_make_field_ttl("Hallo"))
    translate_labels(g, source_lang="auto", api_key="fake")

    assert FakeTranslatorCustom.last_source_lang is None


def test_translate_api_error_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """If translate_text raises DeepLException, CLI must exit 1 with the error message."""
    import deepl

    class ErrorTranslator:
        def __init__(self, api_key: str) -> None:
            pass

        def translate_text(
            self,
            texts: list[str],
            *,
            target_lang: str,
            source_lang: str | None = None,
        ) -> list[FakeResult]:
            raise deepl.DeepLException("quota exceeded")

    monkeypatch.setattr("deepl.Translator", ErrorTranslator)

    ttl_file = tmp_path / "input.ttl"
    ttl_file.write_text(_make_field_ttl("Zielreichweite"))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--input", str(ttl_file), "--source-lang", "DE"],
        env={"DEEPL_API_KEY": "fake-key"},
    )
    assert result.exit_code == 1
    assert "quota exceeded" in result.output


def test_translate_already_translated_skips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CLI must skip translation and exit 0 when rose:originalLabel already present."""
    monkeypatch.setattr("deepl.Translator", FakeTranslator)
    FakeTranslator.instantiated = 0

    # Build TTL with an existing rose:originalLabel triple
    ttl = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rose: <http://rosetta.interop/ns/> .

rose:field_001 rdf:type rose:Field ;
    rdfs:label "Target range" ;
    rose:originalLabel "Zielreichweite" .
"""
    ttl_file = tmp_path / "input.ttl"
    ttl_file.write_text(ttl)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--input", str(ttl_file), "--source-lang", "DE"],
        env={"DEEPL_API_KEY": "fake-key"},
    )
    assert result.exit_code == 0

    # Click 8 mixes stderr into output by default
    assert "already contains" in result.output

    # No additional originalLabel triples should be added (still just 1)
    g = Graph()
    g.parse(data=ttl, format="turtle")
    orig_labels = list(g.subject_objects(ROSE_NS.originalLabel))
    assert len(orig_labels) == 1
