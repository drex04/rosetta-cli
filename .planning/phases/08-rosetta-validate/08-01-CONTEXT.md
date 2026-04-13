---
phase: 8
plan: 1
title: "rosetta-validate — SHACL validation of mapping artifacts"
created: 2026-04-13
---

# Context: Plan 08-01

## Locked Decisions

- pySHACL is already a declared dependency (`>=0.20`); no install step needed.
- `do_owl_imports=False, meta_shacl=False` — prevents OWL imports from external URLs (security) and skips meta-SHACL overhead.
- Exit codes follow project convention: 0 = conforms, 1 = violations or error.
- Results are parsed from `results_graph` via SPARQL (not from `results_text`).

## Decisions (added in review)

- [review] `sh:resultMessage` is OPTIONAL in the SPARQL query. Per the SHACL spec, `sh:resultMessage` is not present on every `sh:ValidationResult` — only when the shape declares `sh:message`. A bare binding silently drops violations without custom messages.
- [review] `ValidationFinding.message` is `str | None = None`, not `str`. Matches the OPTIONAL SPARQL binding.
- [review] `--shapes-dir` must guard against zero `.ttl` files: raise `click.UsageError` if the resulting shapes graph has zero triples. Empty shapes graph → trivial conforms=True on any data (silent false-positive).
- [review] All path options use `click.Path(exists=True)` with `dir_okay=False` / `file_okay=False` as appropriate. Fail fast before rdflib touches the filesystem.
- [review] Pydantic `# --- Validate ---` section appended after `# --- Provenance ---` (not after Embeddings — phase 7 already appended Provenance there).

## Deferred Ideas

- Warning/Info severity threshold flag (`--severity-filter`) — deferred, not in REQ-20/21 scope.
- HTML report output format — deferred, JSON is sufficient for composability.
- SPARQL-based custom constraint extensions — deferred to a future phase.
