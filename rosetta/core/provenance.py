"""PROV-O metadata stamping and querying for Rosetta mapping artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, XSD

from rosetta.core.models import ProvenanceRecord
from rosetta.core.rdf_utils import _PROV as PROV
from rosetta.core.rdf_utils import ROSE_NS, bind_namespaces, query_graph

_STAMP_SPARQL = """
SELECT (MAX(?v) AS ?max_v) WHERE {
    ?artifact rose:version ?v .
}
"""

_QUERY_SPARQL = """
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX rose: <http://rosetta.interop/ns/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?activity ?agent ?label ?started ?ended ?version WHERE {
    ?artifact prov:wasGeneratedBy ?activity ;
              rose:version ?version .
    ?activity prov:startedAtTime ?started ;
              prov:endedAtTime   ?ended ;
              prov:wasAssociatedWith ?agent .
    OPTIONAL { ?activity rdfs:label ?label }
}
ORDER BY ASC(?started)
"""


def stamp_artifact(
    g: Graph,
    artifact_uri: str,
    agent_uri: str = "http://rosetta.interop/ns/agent/rosetta-cli",
    label: str | None = None,
    now: datetime | None = None,
) -> int:
    """Stamp PROV-O metadata onto *g* for the artifact identified by *artifact_uri*.

    Increments ``rose:version`` by 1 on each call and records a minimal
    PROV-O Activity/Entity/Agent triple set.  Returns the new version number.

    Parameters
    ----------
    g:
        The RDF graph to augment in-place.
    artifact_uri:
        URI string identifying the artifact (becomes the PROV Entity).
    agent_uri:
        URI string identifying the agent performing the stamp.
    label:
        Optional human-readable label for this stamp event (``rdfs:label``).
    now:
        Timestamp to use for ``prov:startedAtTime`` / ``prov:endedAtTime``.
        Defaults to ``datetime.now(timezone.utc)``; inject for deterministic tests.
    """
    if now is None:
        now = datetime.now(UTC)

    # Determine current version (None-guard MAX aggregate on empty graph)
    rows = query_graph(
        g,
        _STAMP_SPARQL,
        bindings={"artifact": URIRef(artifact_uri)},
    )
    max_v = int(rows[0]["max_v"]) if rows and rows[0].get("max_v") is not None else 0
    new_version = max_v + 1

    artifact_ref = URIRef(artifact_uri)
    agent_ref = URIRef(agent_uri)

    # Update rose:version (single-value triple — remove old, add new)
    g.remove((artifact_ref, ROSE_NS.version, None))
    g.add((artifact_ref, ROSE_NS.version, Literal(new_version, datatype=XSD.integer)))

    # Generate a unique activity URI
    activity = ROSE_NS[f"activity/{uuid4()}"]

    ts_literal = Literal(now.isoformat(), datatype=XSD.dateTime)

    # PROV-O triples
    g.add((activity, PROV.type, PROV.Activity))  # type: ignore[attr-defined]
    g.add((activity, PROV.startedAtTime, ts_literal))  # type: ignore[attr-defined]
    g.add((activity, PROV.endedAtTime, ts_literal))  # type: ignore[attr-defined]
    g.add((activity, PROV.wasAssociatedWith, agent_ref))  # type: ignore[attr-defined]
    if label is not None:
        g.add((activity, RDFS.label, Literal(label)))

    g.add((artifact_ref, PROV.type, PROV.Entity))  # type: ignore[attr-defined]
    g.add((artifact_ref, PROV.wasGeneratedBy, activity))  # type: ignore[attr-defined]
    g.add((agent_ref, PROV.type, PROV.Agent))  # type: ignore[attr-defined]

    # Bind namespaces
    bind_namespaces(g)
    g.bind("xsd", XSD)
    g.bind("rdfs", RDFS)

    return new_version


def query_provenance(
    g: Graph,
    artifact_uri: str,
) -> list[ProvenanceRecord]:
    """Return all PROV-O stamp records for *artifact_uri* in *g*.

    ``rose:version`` is a single-value triple (only the current version is
    stored).  All returned records carry the same ``version`` value — the
    artifact's version at query time.  Records are sorted by ``started_at``
    ascending.
    """
    rows = query_graph(
        g,
        _QUERY_SPARQL,
        bindings={"artifact": URIRef(artifact_uri)},
    )

    records: list[ProvenanceRecord] = []
    for row in rows:
        label_val = row.get("label")
        records.append(
            ProvenanceRecord(
                activity_uri=str(row["activity"]),
                agent_uri=str(row["agent"]),
                label=str(label_val) if label_val is not None else None,
                started_at=str(row["started"]),
                ended_at=str(row["ended"]),
                version=int(row["version"]),
            )
        )

    return records
