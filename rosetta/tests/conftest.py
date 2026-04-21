"""Shared pytest fixtures for the Rosetta CLI test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from rdflib import Graph

# Force rdflib's SPARQL parser grammar to compile before any schema-automator
# import touches pyparsing's mutable grammar registry. Without this, test
# ordering that reaches schema-automator first (e.g. through CSV/XSD ingest)
# leaves the SPARQL grammar corrupted by the time later tests try to query
# a Graph, surfacing as `pyparsing.exceptions.ParseException: Expected
# {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}`.
from rdflib.plugins.sparql.parser import parseQuery as _sparql_preload

_sparql_preload("SELECT * WHERE { ?s ?p ?o }")

from rosetta.core.rdf_utils import ROSE_NS, bind_namespaces  # noqa: E402

_FIXTURES_ROOT: Path = Path(__file__).parent / "fixtures"
_NATIONS: Path = _FIXTURES_ROOT / "nations"
_STRESS: Path = _FIXTURES_ROOT / "stress"
_ADVERSARIAL: Path = _FIXTURES_ROOT / "adversarial"


@pytest.fixture()
def tmp_graph() -> Graph:
    """Return a fresh rdflib Graph with Rosetta namespaces bound."""
    g = Graph()
    bind_namespaces(g)
    return g


@pytest.fixture()
def sample_ttl(tmp_path: Path) -> Path:
    """Write a small Turtle file using ROSE_NS and return its Path."""
    ttl_content = f"""@prefix rose: <{ROSE_NS}> .

rose:SampleField a rose:Field ;
    rose:label "Sample Field" .
"""
    out = tmp_path / "sample.ttl"
    out.write_text(ttl_content, encoding="utf-8")
    return out


@pytest.fixture()
def tmp_rosetta_toml(tmp_path: Path) -> Path:
    """Write a minimal rosetta.toml with [ledger].log pointing to a temp file."""
    log_path = tmp_path / "audit-log.sssom.tsv"
    config = tmp_path / "rosetta.toml"
    config.write_text(f'[ledger]\nlog = "{log_path}"\n')
    return config


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Write a minimal rosetta.toml to tmp_path and return the directory."""
    toml_content = """\
[ingest]
default_format = "turtle"

[embed]
model = "sentence-transformers/LaBSE"
"""
    (tmp_path / "rosetta.toml").write_text(toml_content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Fixture-path fixtures (Phase 18 — see CONTEXT.md D-18-01)
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixtures_root() -> Path:
    """Root of the test fixtures directory."""
    return _FIXTURES_ROOT


@pytest.fixture()
def nor_csv_path() -> Path:
    return _NATIONS / "nor_radar.csv"


@pytest.fixture()
def nor_csv_sample_path() -> Path:
    return _NATIONS / "nor_radar_sample.csv"


@pytest.fixture()
def nor_linkml_path() -> Path:
    return _NATIONS / "nor_radar.linkml.yaml"


@pytest.fixture()
def deu_json_path() -> Path:
    return _NATIONS / "deu_patriot.json"


@pytest.fixture()
def deu_sample_json_path() -> Path:
    return _NATIONS / "deu_radar_sample.json"


@pytest.fixture()
def usa_openapi_path() -> Path:
    return _NATIONS / "usa_c2.yaml"


@pytest.fixture()
def master_schema_path() -> Path:
    return _NATIONS / "master_cop.linkml.yaml"


@pytest.fixture()
def master_shapes_path() -> Path:
    return _NATIONS / "master_cop.shapes.ttl"


@pytest.fixture()
def bearing_override_path() -> Path:
    return _NATIONS / "track_bearing_range.override.ttl"


@pytest.fixture()
def master_ontology_path() -> Path:
    return _NATIONS / "master_cop_ontology.ttl"


@pytest.fixture()
def sssom_nor_path() -> Path:
    return _NATIONS / "sssom_nor_approved.sssom.tsv"


@pytest.fixture()
def stress_dir() -> Path:
    return _STRESS


@pytest.fixture()
def adversarial_dir() -> Path:
    return _ADVERSARIAL


# ---------------------------------------------------------------------------
# fake_deepl — reusable DeepL Translator mock (Phase 18 — D-18-05)
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_deepl(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Install a fake DeepL translator.

    Returns a configurator callable. Usage:

        def test_x(fake_deepl):
            fake_deepl({"Geschwindigkeit": "Speed"})       # happy path
            # or
            import deepl
            fake_deepl(raises=deepl.exceptions.QuotaExceededException("mock quota"))

    Call count and last batch live on the configurator's ``state`` attribute:
    ``fake_deepl.state["call_count"]``, ``fake_deepl.state["last_batch"]``.
    """
    state: dict[str, Any] = {"mapping": {}, "raises": None, "call_count": 0, "last_batch": None}

    class _FakeResult:
        def __init__(self, text: str) -> None:
            self.text = text

    def _fake_translate_text(_self: Any, texts: list[str], **_kwargs: Any) -> list[_FakeResult]:
        state["call_count"] += 1
        state["last_batch"] = texts.copy()
        if state["raises"] is not None:
            raise state["raises"]
        mapping = state["mapping"]
        return [_FakeResult(mapping.get(t, t)) for t in texts]

    monkeypatch.setattr("deepl.Translator.translate_text", _fake_translate_text)

    def configure(
        mapping: dict[str, str] | None = None, *, raises: Exception | None = None
    ) -> dict[str, Any]:
        state["mapping"] = mapping or {}
        state["raises"] = raises
        return state

    setattr(configure, "state", state)  # noqa: B010  # basedpyright disallows direct attr set on FunctionType
    return configure
