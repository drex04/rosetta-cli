"""Integration tests for rosetta translate (Phase 18-02, Task 3.6).

All DeepL calls are mocked via the ``fake_deepl`` conftest fixture — zero API credits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from click.testing import CliRunner
from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]
from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]

from rosetta.cli.translate import cli as translate_cli

pytestmark = [pytest.mark.integration]


def _write_schema(path: Path, body: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


def _load_schema(path: Path) -> SchemaDefinition:
    return cast(
        SchemaDefinition,
        yaml_loader.load(str(path), target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
    )


def _de_schema_body() -> dict[str, Any]:
    return {
        "id": "https://example.org/de_radar",
        "name": "de_radar",
        "default_prefix": "de_radar",
        "prefixes": {
            "linkml": {
                "prefix_prefix": "linkml",
                "prefix_reference": "https://w3id.org/linkml/",
            },
            "de_radar": {
                "prefix_prefix": "de_radar",
                "prefix_reference": "https://example.org/de_radar#",
            },
        },
        "imports": ["linkml:types"],
        "classes": {
            "spur": {"title": "Spur"},
        },
        "slots": {
            "hoyde_m": {"title": "Hoyde"},
            "geschwindigkeit": {"title": "Geschwindigkeit"},
        },
    }


def _fr_schema_body() -> dict[str, Any]:
    return {
        "id": "https://example.org/fr_radar",
        "name": "fr_radar",
        "default_prefix": "fr_radar",
        "prefixes": {
            "linkml": {
                "prefix_prefix": "linkml",
                "prefix_reference": "https://w3id.org/linkml/",
            },
            "fr_radar": {
                "prefix_prefix": "fr_radar",
                "prefix_reference": "https://example.org/fr_radar#",
            },
        },
        "imports": ["linkml:types"],
        "classes": {
            "piste": {"title": "Piste"},
        },
        "slots": {
            "vitesse": {"title": "Vitesse"},
        },
    }


def test_translate_de_pipeline(tmp_path: Path, fake_deepl: Any) -> None:
    """German-titled LinkML schema → English titles, originals in aliases."""
    fake_deepl(
        {
            "Hoyde": "Altitude",
            "Geschwindigkeit": "Speed",
            "Spur": "Track",
        }
    )

    src = _write_schema(tmp_path / "de.linkml.yaml", _de_schema_body())
    out = tmp_path / "de_translated.linkml.yaml"

    result = CliRunner(mix_stderr=False).invoke(
        translate_cli,
        [
            str(src),
            "--output",
            str(out),
            "--source-lang",
            "DE",
            "--deepl-key",
            "fake-key",
        ],
    )
    assert result.exit_code == 0, f"translate failed: {result.stderr}"
    assert out.exists()

    schema = _load_schema(out)
    slots = schema.slots or {}  # pyright: ignore[reportUnknownMemberType]
    hoyde = slots["hoyde_m"]  # pyright: ignore[reportUnknownVariableType, reportCallIssue, reportArgumentType]
    # Behavioural invariant: translated title present AND original preserved in aliases.
    assert hoyde.title == "Altitude"  # pyright: ignore[reportAttributeAccessIssue]
    assert "Hoyde" in (hoyde.aliases or [])  # pyright: ignore[reportAttributeAccessIssue]

    assert fake_deepl.state["call_count"] >= 1


def test_translate_fr_pipeline(tmp_path: Path, fake_deepl: Any) -> None:
    """French-titled LinkML schema → English titles, originals in aliases."""
    fake_deepl({"Vitesse": "Speed", "Piste": "Track"})

    src = _write_schema(tmp_path / "fr.linkml.yaml", _fr_schema_body())
    out = tmp_path / "fr_translated.linkml.yaml"

    result = CliRunner(mix_stderr=False).invoke(
        translate_cli,
        [
            str(src),
            "--output",
            str(out),
            "--source-lang",
            "FR",
            "--deepl-key",
            "fake-key",
        ],
    )
    assert result.exit_code == 0, f"translate failed: {result.stderr}"

    schema = _load_schema(out)
    slots = schema.slots or {}  # pyright: ignore[reportUnknownMemberType]
    vitesse = slots["vitesse"]  # pyright: ignore[reportUnknownVariableType, reportCallIssue, reportArgumentType]
    assert vitesse.title == "Speed"  # pyright: ignore[reportAttributeAccessIssue]
    assert "Vitesse" in (vitesse.aliases or [])  # pyright: ignore[reportAttributeAccessIssue]


def test_translate_batch_efficiency(tmp_path: Path, fake_deepl: Any) -> None:
    """50 distinct titles → single DeepL batch of 50 texts."""
    # Configure an empty mapping — all texts pass through unchanged. We assert batch
    # count and size, not content.
    fake_deepl({})

    slots: dict[str, dict[str, Any]] = {
        f"slot_{i:02d}": {"title": f"Title_{i:02d}"} for i in range(50)
    }
    body: dict[str, Any] = {
        "id": "https://example.org/batch",
        "name": "batch_schema",
        "default_prefix": "batch_schema",
        "prefixes": {
            "linkml": {
                "prefix_prefix": "linkml",
                "prefix_reference": "https://w3id.org/linkml/",
            },
            "batch_schema": {
                "prefix_prefix": "batch_schema",
                "prefix_reference": "https://example.org/batch#",
            },
        },
        "imports": ["linkml:types"],
        "slots": slots,
    }
    src = _write_schema(tmp_path / "batch.linkml.yaml", body)
    out = tmp_path / "batch_translated.linkml.yaml"

    result = CliRunner(mix_stderr=False).invoke(
        translate_cli,
        [
            str(src),
            "--output",
            str(out),
            "--source-lang",
            "DE",
            "--deepl-key",
            "fake-key",
        ],
    )
    assert result.exit_code == 0, f"translate failed: {result.stderr}"

    # Single batched DeepL call (plan truth #7 — translate_schema dedups + batches).
    assert fake_deepl.state["call_count"] == 1
    last_batch = fake_deepl.state["last_batch"]
    assert last_batch is not None
    assert len(last_batch) == 50, f"expected 50-text batch, got {len(last_batch)}: {last_batch[:5]}"


def test_translate_mixed_language(tmp_path: Path, fake_deepl: Any) -> None:
    """Mixed DE/EN titles in a DE-tagged schema: DE titles get translated;
    EN titles pass through unchanged by the fake translator.

    NOTE: ``translate_schema`` does not language-detect per-title — when
    source_lang != 'EN' it sends every title through DeepL and prepends the
    original to aliases. Our invariant is therefore weaker than "EN titles
    are completely untouched": we assert translated text is correct, and that
    the original was preserved somewhere in aliases.
    """
    fake_deepl({"Deutsch": "German"})

    body: dict[str, Any] = {
        "id": "https://example.org/mixed",
        "name": "mixed_schema",
        "default_prefix": "mixed_schema",
        "prefixes": {
            "linkml": {
                "prefix_prefix": "linkml",
                "prefix_reference": "https://w3id.org/linkml/",
            },
            "mixed_schema": {
                "prefix_prefix": "mixed_schema",
                "prefix_reference": "https://example.org/mixed#",
            },
        },
        "imports": ["linkml:types"],
        "slots": {
            "de_label": {"title": "Deutsch"},
            "en_label": {"title": "Speed"},
            "en_other": {"title": "Bearing"},
        },
    }
    src = _write_schema(tmp_path / "mixed.linkml.yaml", body)
    out = tmp_path / "mixed_translated.linkml.yaml"

    result = CliRunner(mix_stderr=False).invoke(
        translate_cli,
        [
            str(src),
            "--output",
            str(out),
            "--source-lang",
            "DE",
            "--deepl-key",
            "fake-key",
        ],
    )
    assert result.exit_code == 0, f"translate failed: {result.stderr}"

    schema = _load_schema(out)
    slots = schema.slots or {}  # pyright: ignore[reportUnknownMemberType]

    # German title → translated, original preserved in aliases.
    de_slot = slots["de_label"]  # pyright: ignore[reportUnknownVariableType, reportCallIssue, reportArgumentType]
    assert de_slot.title == "German"  # pyright: ignore[reportAttributeAccessIssue]
    assert "Deutsch" in (de_slot.aliases or [])  # pyright: ignore[reportAttributeAccessIssue]

    # English titles are echoed unchanged by the fake translator — their
    # surface form stays as-is in the output schema.
    en_slot = slots["en_label"]  # pyright: ignore[reportUnknownVariableType, reportCallIssue, reportArgumentType]
    assert en_slot.title == "Speed"  # pyright: ignore[reportAttributeAccessIssue]
    en_other = slots["en_other"]  # pyright: ignore[reportUnknownVariableType, reportCallIssue, reportArgumentType]
    assert en_other.title == "Bearing"  # pyright: ignore[reportAttributeAccessIssue]
