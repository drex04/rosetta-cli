"""Tests for rosetta-embed: embedding.py core + embed CLI."""

from __future__ import annotations

import json
import numpy as np
import pytest
from pathlib import Path
from click.testing import CliRunner
from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef

ROSE = Namespace("http://rosetta.interop/ns/")

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

def test_extract_national_fields():
    """extract_text_inputs returns 2 pairs for a graph with 2 rose:Field nodes."""
    from rosetta.core.embedding import extract_text_inputs

    g = Graph()
    base = URIRef("http://rosetta.interop/field/NOR/nor_radar/")
    f1 = URIRef(str(base) + "hoyde_m")
    f2 = URIRef(str(base) + "bredde")
    g.add((f1, RDF.type, ROSE.Field))
    g.add((f1, RDFS.label, Literal("Hoyde")))
    g.add((f2, RDF.type, ROSE.Field))
    g.add((f2, RDFS.label, Literal("Bredde")))

    pairs = extract_text_inputs(g)

    assert len(pairs) == 2
    all_text = " ".join(t for _, t in pairs)
    assert "nor_radar" in all_text


def test_extract_master_attributes():
    """extract_text_inputs builds 'ConceptLabel / AttrLabel — Comment' for rose:Attribute."""
    from rosetta.core.embedding import extract_text_inputs

    g = Graph()
    concept = URIRef("http://rosetta.interop/ns/SomeConcept")
    attr = URIRef("http://rosetta.interop/ns/SomeAttr")
    g.add((attr, RDF.type, ROSE.Attribute))
    g.add((attr, RDFS.label, Literal("AttrLabel")))
    g.add((attr, RDFS.comment, Literal("SomeComment")))
    g.add((concept, RDF.type, ROSE.Concept))
    g.add((concept, RDFS.label, Literal("ConceptLabel")))
    g.add((concept, ROSE.hasAttribute, attr))

    pairs = extract_text_inputs(g)

    assert len(pairs) == 1
    uri, text = pairs[0]
    assert text == "ConceptLabel / AttrLabel — SomeComment"


def test_extract_master_no_concept():
    """rose:Attribute with no rose:hasAttribute produces ' / AttrLabel — '."""
    from rosetta.core.embedding import extract_text_inputs

    g = Graph()
    attr = URIRef("http://rosetta.interop/ns/LoneAttr")
    g.add((attr, RDF.type, ROSE.Attribute))
    g.add((attr, RDFS.label, Literal("AttrLabel")))

    pairs = extract_text_inputs(g)

    assert len(pairs) == 1
    _, text = pairs[0]
    assert text == " / AttrLabel — "


def test_embedding_model_encode_shape(mock_sentence_transformer):
    """EmbeddingModel.encode returns a list of vectors with the expected shape."""
    from rosetta.core.embedding import EmbeddingModel

    model = EmbeddingModel("fake")
    result = model.encode(["a", "b"])

    assert len(result) == 2
    assert len(result[0]) == 4
    assert len(result[1]) == 4


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

def _make_national_ttl(n: int = 3) -> str:
    """Return Turtle source with *n* rose:Field nodes."""
    prefixes = (
        "@prefix rose: <http://rosetta.interop/ns/> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
    )
    triples = ""
    for i in range(n):
        triples += (
            f"<http://rosetta.interop/field/NOR/nor_schema/field_{i}>\n"
            f"    a rose:Field ;\n"
            f'    rdfs:label "Field {i}" .\n\n'
        )
    return prefixes + triples


def test_embed_cli_national(tmp_path, mock_sentence_transformer):
    """CLI produces exit 0 and JSON with 3 keys each having a 'lexical' list."""
    from rosetta.cli.embed import cli

    runner = CliRunner()
    inp = tmp_path / "national.ttl"
    inp.write_text(_make_national_ttl(3))
    out = tmp_path / "out.json"

    result = runner.invoke(cli, ["--input", str(inp), "--output", str(out)])

    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    data = json.loads(out.read_text())
    assert len(data) == 3
    for val in data.values():
        assert "lexical" in val
        assert isinstance(val["lexical"], list)


def test_embed_cli_empty_graph(tmp_path):
    """CLI exits with code 1 when the input graph has no embeddable nodes."""
    from rosetta.cli.embed import cli

    runner = CliRunner()
    inp = tmp_path / "empty.ttl"
    inp.write_text("@prefix rose: <http://rosetta.interop/ns/> .\n")
    out = tmp_path / "out.json"

    result = runner.invoke(cli, ["--input", str(inp), "--output", str(out)])

    assert result.exit_code == 1


def test_embed_cli_output_creates_dirs(tmp_path, mock_sentence_transformer):
    """CLI auto-creates nested output directories that do not yet exist."""
    from rosetta.cli.embed import cli

    runner = CliRunner()
    inp = tmp_path / "national.ttl"
    inp.write_text(_make_national_ttl(1))
    out = tmp_path / "nested" / "deep" / "out.json"

    result = runner.invoke(cli, ["--input", str(inp), "--output", str(out)])

    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    assert out.exists()


def test_embed_cli_stdout(tmp_path, mock_sentence_transformer):
    """CLI without --output writes valid JSON to stdout."""
    from rosetta.cli.embed import cli

    runner = CliRunner()
    inp = tmp_path / "national.ttl"
    inp.write_text(_make_national_ttl(2))

    result = runner.invoke(cli, ["--input", str(inp)])

    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    data = json.loads(result.output)
    assert len(data) == 2


# ---------------------------------------------------------------------------
# Slow test (skipped by default — requires model download)
# ---------------------------------------------------------------------------

MASTER_TTL = Path(__file__).resolve().parent.parent.parent / "store/master-ontology/master.ttl"


@pytest.mark.slow
def test_embed_cli_real_model_master_ttl():
    """Real model encodes master.ttl; asserts correct output shape."""
    from rosetta.cli.embed import cli

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, [
            "--input", str(MASTER_TTL),
            "--output", "out.json",
            "--model", "sentence-transformers/all-MiniLM-L6-v2",
        ])
        assert result.exit_code == 0
        data = json.loads(Path("out.json").read_text())
        assert len(data) > 0
        first_vec = next(iter(data.values()))["lexical"]
        assert len(first_vec) == 384  # all-MiniLM-L6-v2 dim
