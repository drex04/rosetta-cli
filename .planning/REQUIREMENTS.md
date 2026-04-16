# Requirements

## Milestone 1: "Can we ingest and compare?" (Phase 1–3)

- REQ-01: `rosetta-ingest` converts national schemas (CSV, JSON Schema, OpenAPI) to RDF Turtle
- REQ-02: `rosetta-ingest` detects units from field names/descriptions via regex; annotates as RDF
- REQ-03: `rosetta-ingest` computes statistical summaries (min, max, mean, stddev, null_rate, histogram) from sample data
- REQ-04: `rosetta-embed` generates lexical embeddings (LaBSE) for all attributes in an RDF schema
- REQ-05: `rosetta-embed` supports `--mode lexical-only` for MVP; `lexical+stats` and `full` for later
- REQ-06: `rosetta-suggest` computes cosine similarity between national and master embeddings
- REQ-07: `rosetta-suggest` returns ranked suggestions with confidence scores and breakdown by signal type
- REQ-08: `rosetta-suggest` supports configurable weights via `--weights`
- REQ-09: Shared `rosetta.toml` config file; all settings overridable via CLI flags
- REQ-10: All tools read from files or stdin, write to files or stdout (Unix-composable)

## Milestone 2: "Can we catch mistakes?" (Phase 4–5)

- REQ-11: `rosetta-lint` checks unit compatibility (source vs. target) using QUDT definitions
- REQ-12: `rosetta-lint` checks data type compatibility and CRS/timestamp format issues
- REQ-13: `rosetta-lint` suggests FnML functions from repository when unit mismatch is detected
- REQ-14: `rosetta-lint` exits with code 1 on BLOCK findings (composable in shell scripts)
- REQ-15: `rosetta-lint` supports `--strict` mode (WARNINGs treated as BLOCKs)
- REQ-16: `rosetta-yarrrml-gen` generates a linkml-map `TransformationSpecification` YAML from an approved SSSOM audit log plus source and master LinkML schemas
- REQ-17: `rosetta-yarrrml-gen` emits a `CoverageReport` JSON when `--coverage-report` is specified

## Milestone 3: "Can we track who did what?" (Phase 6–8)

- REQ-18: `rosetta-provenance` appends PROV-O triples to mapping artifacts (creation, accreditation)
- REQ-19: `rosetta-provenance --query` prints human-readable provenance summary
- REQ-20: `rosetta-validate` wraps pySHACL; validates mapping RML against SHACL shapes
- REQ-21: `rosetta-validate` exits with code 0 (conformant) or 1 (violations)
- REQ-22: `rosetta-accredit submit` runs lint + validate as prerequisites; blocks if either fails
- REQ-23: `rosetta-accredit approve` updates status, stamps provenance, copies to accredited store, updates ledger
- REQ-24: `rosetta-accredit revoke` updates status to REVOKED, stamps reason, removes from ledger
- REQ-25: `rosetta-suggest` reads `ledger.json` to boost confidence for accredited precedents; excludes revoked
- REQ-26: Synthetic test fixtures: Master Air Defense Ontology (~20 concepts) + 3 national schemas (NOR/DEU/USA)

## Milestone 4 (Future)

- REQ-27: `rosetta-embed` adds GCN structural embeddings (PyTorch Geometric)
- REQ-28: `rosetta-embed` adds statistical embedding layer
- REQ-29: Validate against real logistics data (GS1 EPCIS, public supply chain APIs)
