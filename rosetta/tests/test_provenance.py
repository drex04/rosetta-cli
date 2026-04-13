"""Tests for rosetta/core/provenance.py and rosetta/cli/provenance.py."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import RDF, Graph, URIRef

from rosetta.cli.provenance import cli
from rosetta.core.models import ProvenanceRecord
from rosetta.core.provenance import query_provenance, stamp_artifact
from rosetta.core.rdf_utils import _PROV as PROV
from rosetta.core.rdf_utils import ROSE_NS, bind_namespaces

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_ARTIFACT_URI = "http://rosetta.interop/ns/test_artifact"

_MINIMAL_TTL = """\
@prefix rose: <http://rosetta.interop/ns/> .
rose:test_artifact a rose:MappingArtifact .
"""

_MALFORMED_TTL = "this is not valid turtle @@@@"


@pytest.fixture
def empty_graph() -> Graph:
    """A graph with a single subject triple to stamp."""
    g = Graph()
    bind_namespaces(g)
    g.add((URIRef(_ARTIFACT_URI), RDF.type, ROSE_NS.MappingArtifact))
    return g


@pytest.fixture
def stamped_graph(empty_graph: Graph) -> tuple[Graph, int]:
    """Graph stamped once; returns (graph, version)."""
    version = stamp_artifact(empty_graph, _ARTIFACT_URI)
    return empty_graph, version


# ---------------------------------------------------------------------------
# Unit tests — stamp_artifact
# ---------------------------------------------------------------------------


def test_stamp_returns_version_1_on_first_call(empty_graph: Graph) -> None:
    version = stamp_artifact(empty_graph, _ARTIFACT_URI)
    assert version == 1


def test_stamp_increments_version(empty_graph: Graph) -> None:
    v1 = stamp_artifact(empty_graph, _ARTIFACT_URI)
    v2 = stamp_artifact(empty_graph, _ARTIFACT_URI)
    assert v1 == 1
    assert v2 == 2


def test_stamp_adds_prov_entity_triple(stamped_graph: tuple[Graph, int]) -> None:
    g, _ = stamped_graph
    assert (URIRef(_ARTIFACT_URI), PROV.type, PROV.Entity) in g  # type: ignore[attr-defined]


def test_stamp_adds_activity_triple(stamped_graph: tuple[Graph, int]) -> None:
    g, _ = stamped_graph
    activities = list(g.subjects(PROV.type, PROV.Activity))  # type: ignore[attr-defined]
    assert len(activities) >= 1


def test_stamp_adds_agent_triple(stamped_graph: tuple[Graph, int]) -> None:
    g, _ = stamped_graph
    default_agent = URIRef("http://rosetta.interop/ns/agent/rosetta-cli")
    assert (default_agent, PROV.type, PROV.Agent) in g  # type: ignore[attr-defined]


def test_stamp_datetime_injected(empty_graph: Graph) -> None:
    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    stamp_artifact(empty_graph, _ARTIFACT_URI, now=fixed)
    # Find activity node
    activities = list(empty_graph.subjects(PROV.type, PROV.Activity))  # type: ignore[attr-defined]
    assert activities, "No activity node found"
    activity = activities[0]
    started_values = list(empty_graph.objects(activity, PROV.startedAtTime))  # type: ignore[attr-defined]
    assert started_values, "No startedAtTime found"
    assert str(started_values[0]) == fixed.isoformat()


def test_stamp_label_optional(empty_graph: Graph) -> None:
    from rdflib.namespace import RDFS

    stamp_artifact(empty_graph, _ARTIFACT_URI)
    labels = list(empty_graph.objects(predicate=RDFS.label))
    # No rdfs:label should have been added
    assert len(labels) == 0


def test_stamp_label_present(empty_graph: Graph) -> None:
    from rdflib.namespace import RDFS

    stamp_artifact(empty_graph, _ARTIFACT_URI, label="foo")
    labels = [str(o) for o in empty_graph.objects(predicate=RDFS.label)]
    assert "foo" in labels


# ---------------------------------------------------------------------------
# Unit tests — query_provenance
# ---------------------------------------------------------------------------


def test_query_empty_graph_returns_empty_list(empty_graph: Graph) -> None:
    records = query_provenance(empty_graph, _ARTIFACT_URI)
    assert records == []


def test_query_returns_one_record_after_stamp(empty_graph: Graph) -> None:
    stamp_artifact(empty_graph, _ARTIFACT_URI)
    records = query_provenance(empty_graph, _ARTIFACT_URI)
    assert len(records) == 1
    rec = records[0]
    assert rec.version == 1
    assert rec.agent_uri == "http://rosetta.interop/ns/agent/rosetta-cli"


def test_query_returns_two_records_after_two_stamps(empty_graph: Graph) -> None:
    stamp_artifact(empty_graph, _ARTIFACT_URI)
    stamp_artifact(empty_graph, _ARTIFACT_URI)
    records = query_provenance(empty_graph, _ARTIFACT_URI)
    assert len(records) == 2
    # rose:version is a single-value triple — both records report current version (2)
    assert records[0].version == 2
    assert records[1].version == 2


# ---------------------------------------------------------------------------
# Model round-trip
# ---------------------------------------------------------------------------


def test_provenance_record_model_roundtrip() -> None:
    rec = ProvenanceRecord(
        activity_uri="http://rosetta.interop/ns/activity/abc",
        agent_uri="http://rosetta.interop/ns/agent/rosetta-cli",
        label="test label",
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:00:00+00:00",
        version=1,
    )
    dumped = rec.model_dump(mode="json")
    restored = ProvenanceRecord(**dumped)
    assert restored == rec
    assert restored.label == "test label"
    assert restored.version == 1


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def ttl_file(tmp_path: Path) -> Path:
    """Write a minimal valid Turtle file and return its path."""
    p = tmp_path / "artifact.ttl"
    p.write_text(_MINIMAL_TTL, encoding="utf-8")
    return p


@pytest.fixture
def malformed_ttl_file(tmp_path: Path) -> Path:
    """Write a malformed Turtle file and return its path."""
    p = tmp_path / "bad.ttl"
    p.write_text(_MALFORMED_TTL, encoding="utf-8")
    return p


def test_cli_stamp_writes_valid_turtle(ttl_file: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.ttl"
    runner = CliRunner()
    result = runner.invoke(cli, ["stamp", str(ttl_file), "--output", str(out)])
    assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
    g = Graph()
    g.parse(str(out), format="turtle")
    assert len(g) > 0


def test_cli_stamp_exits_zero(ttl_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["stamp", str(ttl_file)])
    assert result.exit_code == 0


def test_cli_stamp_invalid_input(malformed_ttl_file: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["stamp", str(malformed_ttl_file)])
    assert result.exit_code == 1
    # Error message should appear on stderr (mix_stderr=True by default in CliRunner)
    assert "Error" in result.output or "error" in result.output.lower()


def test_cli_query_after_stamp(ttl_file: Path) -> None:
    runner = CliRunner()
    # First stamp
    result = runner.invoke(cli, ["stamp", str(ttl_file)])
    assert result.exit_code == 0
    # Then query
    result = runner.invoke(cli, ["query", str(ttl_file)])
    assert result.exit_code == 0
    assert "v1" in result.output


def test_cli_query_json_format(ttl_file: Path) -> None:
    runner = CliRunner()
    runner.invoke(cli, ["stamp", str(ttl_file)])
    result = runner.invoke(cli, ["query", str(ttl_file), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "activity_uri" in data[0]


def test_cli_query_no_records(ttl_file: Path) -> None:
    """Querying an un-stamped artifact exits 0 with a message on stderr."""
    runner = CliRunner()
    result = runner.invoke(cli, ["query", str(ttl_file)])
    assert result.exit_code == 0
    # CliRunner mixes stderr into output by default
    assert "No provenance records found" in result.output
