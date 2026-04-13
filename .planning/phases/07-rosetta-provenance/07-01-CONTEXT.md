# Phase 7 Context — rosetta-provenance

## Locked Decisions (from plan-work)

- D7-01: In-place augmentation (no sidecar files)
- D7-02: UUID activity URI + default agent `rose:agent/rosetta-cli`
- D7-03: `rose:version` integer literal, incremented per stamp
- D7-04: Subcommand group (`stamp` / `query`); `--format json` for machine output
- D7-05: Minimal PROV-O triple set (Activity + Entity + Agent)

## Decisions (from plan-review)

- [review] SPARQL injection prevention: all queries that accept `artifact_uri` MUST use `query_graph()` with `initBindings`, never f-string interpolation. Both the MAX(?v) version query in `stamp_artifact` and the SELECT in `query_provenance` are covered. Reason: rdflib does not sanitize string-interpolated SPARQL.
- [review] Namespace import: import `_PROV` from `rosetta.core.rdf_utils` (aliased as `PROV`), not from `rdflib.namespace`. `bind_namespaces()` already binds this under the "prov" prefix; re-importing from rdflib creates a redundant second `Namespace` object.
- [review] `ProvenanceRecord.label` must default to `None` (`label: str | None = None`) — consistent with all other optional fields in models.py.
- [review] CLI error handling: both `stamp` and `query` wrap their core logic in `try/except Exception` mirroring lint.py: `click.echo(f"Error: {exc}", err=True); sys.exit(1)`. Covers: missing file (ValueError), bad TTL (ValueError), read-only output path (OSError), non-existent output directory (FileNotFoundError).
- [review] `rose:version` is a single-valued triple (only current version stored). `query_provenance` returns N records for N stamps, but all records carry the same `version` value (current at query time). This is documented in `ProvenanceRecord.version` as "current version at query time."
- [review] `--output` on `stamp` defaults to **in-place overwrite** of INPUT (D7-01), not stdout. Pass `--output -` to route to stdout.
- [review] `--format` on both subcommands uses `type=click.Choice(["text", "json"])` to prevent silent format errors.
- [review] CLI stamp summary (stderr) uses an actual `ProvenanceRecord` instance + `.model_dump(mode="json")`, not a bare dict. Consistent with CLAUDE.md "construct model instances in the CLI."
- [review] Artifact URI heuristic (`ROSE_NS[stem]`) is documented in `--help` text: "Artifact URI is derived as `rose:<stem>` from the input filename."
- [review] Concurrent stamps are not safe (last-writer-wins on in-place overwrite). Documented as a known limitation; no locking mechanism in v1.
- [review] RDF.type (not PROV.type) is required for PROV-O type assertions. `PROV.type` evaluates to `http://www.w3.org/ns/prov#type`; `RDF.type` evaluates to `rdf:type`. All three type-assertion triples must use `RDF.type`. Requires `from rdflib.namespace import RDF` in provenance.py. Tests 3–5 must be updated to assert `RDF.type` predicates or they mask the bug.
- [review] Stamp CLI stderr summary uses a synthetic `activity_uri` (`rose:activity/summary`), not the real UUID activity URI written to the graph. Accepted as a known inaccuracy for the informational summary. To fix properly: change stamp_artifact return type to tuple[int, str] (version, activity_uri). Tracked as tech debt.
- [review] Artifact URI stem collision: two files with the same stem in different directories share an artifact URI (ROSE_NS[stem] heuristic). Documented as known limitation; no mitigation in v1. Documented in --help text.
- [review] Test count updated from 16 to 18 — two new tests added: `test_cli_stamp_invalid_input` (exit 1 on bad TTL) and `test_cli_query_no_records` (exit 0 when no stamps).
- [review] `test_query_returns_two_records_after_two_stamps` must assert `version == 2` on both records (not 1 and 2).

## Deferred Ideas

- Per-activity version tracking: store `rose:version` on each Activity node rather than on the artifact. Would make historical queries accurate. Deferred — requires schema change and scope expansion.
- File locking for concurrent stamp safety. Deferred — out of scope for v1 local-first tool.
- Digital signatures on provenance records (PKI). Explicitly deferred in PROJECT.md.
