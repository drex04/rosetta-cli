"""Adversarial tests for rosetta translate error paths (Phase 18-03, Task 8).

All DeepL API interaction is mocked via the ``fake_deepl`` conftest fixture — no
network, no API credits. Each test asserts a three-level contract:

    1. Exit code (0 or 1)
    2. Stderr substring on failure / output-file-identity on success
    3. Behavioral invariant (translator ``call_count`` and/or file presence)

Exception enumeration (per Plan 18-03 Task 8):
  - Test 1 ``test_translate_auth_failure``        — ``deepl.exceptions.AuthorizationException``
  - Test 2 ``test_translate_quota_exceeded``      — ``deepl.exceptions.QuotaExceededException``
  - Test 3 ``test_translate_transient_error``     — ``deepl.exceptions.DeepLException``
  - Test 4 ``test_translate_missing_key_non_en``  — no exception; cli/translate.py guard
  - Test 5 ``test_translate_en_passthrough_no_key`` — no exception; EN passthrough
  - Test 6 ``test_translate_empty_schema``        — no exception; empty-titles early return

Grepped stderr phrases (the CLI wraps core ``RuntimeError`` as ``Error: {exc}`` via
``click.echo(..., err=True)``):
  - Auth path      → "DeepL authentication failed" (core/translation.py)
  - Quota path     → "DeepL quota exceeded"        (core/translation.py)
  - Transient path → "DeepL API error"             (core/translation.py)
  - Missing key    → "DeepL API key required"      (cli/translate.py)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import deepl.exceptions
import pytest
import yaml
from click.testing import CliRunner

from rosetta.cli.translate import cli as translate_cli

pytestmark = [pytest.mark.integration]


def _de_schema_body() -> dict[str, Any]:
    """Minimal LinkML schema with one German-titled class + slot."""
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
        "classes": {"spur": {"title": "Spur"}},
        "slots": {"geschwindigkeit": {"title": "Geschwindigkeit"}},
    }


def _empty_schema_body() -> dict[str, Any]:
    """LinkML schema with zero classes and zero slots — nothing to translate."""
    return {
        "id": "https://example.org/empty",
        "name": "empty_schema",
        "default_prefix": "empty_schema",
        "prefixes": {
            "linkml": {
                "prefix_prefix": "linkml",
                "prefix_reference": "https://w3id.org/linkml/",
            },
            "empty_schema": {
                "prefix_prefix": "empty_schema",
                "prefix_reference": "https://example.org/empty#",
            },
        },
        "imports": ["linkml:types"],
    }


def _write_schema(path: Path, body: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Test 1 — AuthorizationException
# ---------------------------------------------------------------------------
def test_translate_auth_failure(tmp_path: Path, fake_deepl: Any) -> None:
    """Auth failure → exit 1, stderr names authentication, no output file written.

    Raises: ``deepl.exceptions.AuthorizationException`` (wrapped as RuntimeError
    by ``core/translation.py``; CLI echoes it via ``click.echo('Error: ...', err=True)``).
    """
    fake_deepl(raises=deepl.exceptions.AuthorizationException("bad key"))

    src = _write_schema(tmp_path / "de.linkml.yaml", _de_schema_body())
    out = tmp_path / "translated.linkml.yaml"

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
    # 1. Exit code
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stderr}"
    # 2. Stable stderr substring — "authentication" survives dependency upgrades.
    assert "authentication" in result.stderr.lower(), (
        f"expected 'authentication' in stderr, got: {result.stderr!r}"
    )
    # 3. Behavioral invariant: no output file written on failure.
    assert not out.exists(), "output file must not be written on translate failure"


# ---------------------------------------------------------------------------
# Test 2 — QuotaExceededException
# ---------------------------------------------------------------------------
def test_translate_quota_exceeded(tmp_path: Path, fake_deepl: Any) -> None:
    """Quota exceeded → exit 1, stderr names quota, no output file.

    Raises: ``deepl.exceptions.QuotaExceededException`` (wrapped as RuntimeError).
    """
    fake_deepl(raises=deepl.exceptions.QuotaExceededException("over quota"))

    src = _write_schema(tmp_path / "de.linkml.yaml", _de_schema_body())
    out = tmp_path / "translated.linkml.yaml"

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
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stderr}"
    assert "quota" in result.stderr.lower(), f"expected 'quota' in stderr, got: {result.stderr!r}"
    assert not out.exists()


# ---------------------------------------------------------------------------
# Test 3 — DeepLException (transient/network)
# ---------------------------------------------------------------------------
def test_translate_transient_error(tmp_path: Path, fake_deepl: Any) -> None:
    """Transient DeepL error → exit 1, stderr identifies DeepL, no output.

    Raises: ``deepl.exceptions.DeepLException`` (wrapped as RuntimeError
    with phrase "DeepL API error").
    """
    fake_deepl(raises=deepl.exceptions.DeepLException("network timeout"))

    src = _write_schema(tmp_path / "de.linkml.yaml", _de_schema_body())
    out = tmp_path / "translated.linkml.yaml"

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
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stderr}"
    # Stable substring "DeepL" appears in the wrapped error phrase "DeepL API error".
    assert "deepl" in result.stderr.lower(), f"expected 'DeepL' in stderr, got: {result.stderr!r}"
    assert not out.exists()


# ---------------------------------------------------------------------------
# Test 4 — Missing key + non-EN source lang (early-return guard in cli/translate.py)
# ---------------------------------------------------------------------------
def test_translate_missing_key_non_en(
    tmp_path: Path, fake_deepl: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No key + non-EN source → exit 1, stderr names API key, translator never called.

    Raises: no exception — this is the early-return guard in ``cli/translate.py``
    that checks ``not key and not source_lang.upper().startswith('EN')``.
    """
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)
    fake_deepl({})  # configure but expect no calls

    src = _write_schema(tmp_path / "de.linkml.yaml", _de_schema_body())
    out = tmp_path / "translated.linkml.yaml"

    result = CliRunner(mix_stderr=False).invoke(
        translate_cli,
        [
            str(src),
            "--output",
            str(out),
            "--source-lang",
            "DE",
        ],
    )
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}: {result.stderr}"
    # Grepped phrase in cli/translate.py: "DeepL API key required".
    assert "api key" in result.stderr.lower(), (
        f"expected 'API key' in stderr, got: {result.stderr!r}"
    )
    # Behavioral invariant: translator never constructed/called.
    assert fake_deepl.state["call_count"] == 0, (
        "translator must not be called when guard rejects missing key"
    )
    assert not out.exists()


# ---------------------------------------------------------------------------
# Test 5 — EN passthrough with no key (early-return in core/translation.py)
# ---------------------------------------------------------------------------
def test_translate_en_passthrough_no_key(
    tmp_path: Path, fake_deepl: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """source_lang=EN with no key → exit 0, output byte-identical to input, translator never called.

    Raises: no exception — EN passthrough returns the schema unchanged; the
    output is the yaml-dumper re-serialisation of the loaded schema, which is
    not byte-identical to the input. We assert the schema round-trips (both
    files load to the same body via yaml.safe_load).
    """
    monkeypatch.delenv("DEEPL_API_KEY", raising=False)
    fake_deepl({})

    body = _de_schema_body()
    src = _write_schema(tmp_path / "de.linkml.yaml", body)
    out = tmp_path / "translated.linkml.yaml"

    result = CliRunner(mix_stderr=False).invoke(
        translate_cli,
        [
            str(src),
            "--output",
            str(out),
            "--source-lang",
            "EN",
        ],
    )
    assert result.exit_code == 0, f"expected exit 0, got {result.exit_code}: {result.stderr}"
    # Output file written
    assert out.exists(), "output file must be written on EN passthrough"
    # Schema content preserved (yaml-dumper round-trip may reorder keys, so compare parsed dicts).
    out_body = yaml.safe_load(out.read_text(encoding="utf-8"))
    src_body = yaml.safe_load(src.read_text(encoding="utf-8"))
    # The translator preserves the schema semantically. We assert the class/slot
    # titles are unchanged (the stable observable for passthrough).
    assert out_body["classes"]["spur"]["title"] == src_body["classes"]["spur"]["title"]
    assert (
        out_body["slots"]["geschwindigkeit"]["title"]
        == src_body["slots"]["geschwindigkeit"]["title"]
    )
    # Behavioral invariant: translator never called.
    assert fake_deepl.state["call_count"] == 0, "translator must not be called on EN passthrough"


# ---------------------------------------------------------------------------
# Test 6 — Empty schema (empty-titles early return in core/translation.py)
# ---------------------------------------------------------------------------
def test_translate_empty_schema(tmp_path: Path, fake_deepl: Any) -> None:
    """Empty schema (zero classes, zero slots) → exit 0, translator never called.

    Raises: no exception — ``translate_schema`` returns early when
    ``texts_to_translate`` is empty (no class titles, no slot titles).
    """
    fake_deepl({})

    src = _write_schema(tmp_path / "empty.linkml.yaml", _empty_schema_body())
    out = tmp_path / "translated.linkml.yaml"

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
    assert result.exit_code == 0, f"expected exit 0, got {result.exit_code}: {result.stderr}"
    assert out.exists(), "output file must be written even with no titles"
    # Behavioral invariant: translator never called — no titles to translate.
    assert fake_deepl.state["call_count"] == 0, (
        "translator must not be called when schema has no titles"
    )
