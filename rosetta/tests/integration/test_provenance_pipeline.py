"""Integration tests for rosetta-provenance (Phase 18-02, Task 3.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import rdflib
from click.testing import CliRunner

from rosetta.cli.provenance import cli as provenance_cli
from rosetta.core.rdf_utils import ROSE_NS

pytestmark = [pytest.mark.integration]


_INPUT_TTL = """\
@prefix rose: <http://rosetta.interop/ns/rose#> .

rose:SampleField a rose:Field ;
    rose:label "Sample Field" .
"""

PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")


def test_provenance_stamp_then_query(tmp_path: Path) -> None:
    """Stamp a TTL artifact, then query it — both commands exit 0 and report PROV data."""
    # Write a tiny RDF input.
    src = tmp_path / "artifact.ttl"
    src.write_text(_INPUT_TTL, encoding="utf-8")

    # --- stamp ---
    # NOTE: artifact URI is derived from the input filename stem (rose:<stem>),
    # so stamping to a different output path would change the stem and the
    # subsequent query would see no records. Use an output path whose stem
    # matches the input, and have query read the stamped file in-place.
    stamped = tmp_path / "artifact.ttl"
    stamp_result = CliRunner(mix_stderr=False).invoke(
        provenance_cli,
        [
            "stamp",
            str(src),
            "--output",
            str(stamped),
            "--label",
            "integration-test-stamp",
            "--format",
            "json",
        ],
    )
    assert stamp_result.exit_code == 0, f"stamp failed: {stamp_result.stderr}"
    assert stamped.exists(), "stamp did not write output file"

    # Parse the stamped graph and assert one of each PROV term exists.
    g = rdflib.Graph()
    g.parse(str(stamped), format="turtle")

    activities = list(g.subjects(rdflib.RDF.type, PROV.Activity))
    entities = list(g.subjects(rdflib.RDF.type, PROV.Entity))
    agents = list(g.subjects(rdflib.RDF.type, PROV.Agent))
    assert activities, "expected at least one prov:Activity in stamped graph"
    assert entities, "expected at least one prov:Entity in stamped graph"
    assert agents, "expected at least one prov:Agent in stamped graph"

    # Behavioural invariant: the artifact URI is derived as rose:<stem>.
    expected_artifact = str(ROSE_NS[src.stem])
    assert rdflib.URIRef(expected_artifact) in set(entities), (
        f"expected entity URI {expected_artifact} in entities {entities}"
    )

    # --- query ---
    query_result = CliRunner(mix_stderr=False).invoke(
        provenance_cli,
        ["query", str(stamped), "--format", "json"],
    )
    assert query_result.exit_code == 0, f"query failed: {query_result.stderr}"

    stdout = query_result.stdout.strip()
    assert stdout, "query produced empty stdout"
    records = json.loads(stdout)
    assert isinstance(records, list)
    assert records, "expected at least one provenance record"

    # Every record should reference the stamped activity IRI we just wrote.
    stamped_activity_iris = {str(a) for a in activities}
    record_activity_iris = {r["activity_uri"] for r in records}
    assert stamped_activity_iris & record_activity_iris, (
        f"stamped activities {stamped_activity_iris} not in query output {record_activity_iris}"
    )
