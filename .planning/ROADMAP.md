# Roadmap

## Phase 1: Project scaffolding and core setup
**Goal:** Working Python project with uv, package structure, shared config loading, RDF utilities, and test harness. Ready to build tools on top.

**Delivers:**
- `pyproject.toml` with uv + all dependencies declared
- Package structure: `rosetta/cli/`, `rosetta/core/`, `rosetta/policies/`, `rosetta/store/`, `rosetta/tests/`
- `rosetta/core/rdf_utils.py` — RDF I/O helpers (load/save Turtle, SPARQL helpers)
- `rosetta.toml` config loading with Click integration
- Pytest setup with fixtures directory
- Synthetic Master Air Defense Ontology (`store/master-ontology/master.ttl`)
- All 3 synthetic national schema test fixtures (NOR CSV, DEU JSON Schema, USA OpenAPI)

**Requirements:** REQ-09, REQ-10, REQ-26

---

## Phase 2: rosetta-ingest
**Goal:** Convert national schemas (CSV, JSON Schema, OpenAPI) into RDF Turtle.

**Delivers:**
- `rosetta/cli/ingest.py` with Click entrypoint
- Per-format parser modules: CSV, JSON Schema, OpenAPI (with `$ref` resolution)
- Unit detection via regex (field name + description patterns)
- Statistical summary computation from sample data
- Output: valid Turtle with `rosetta:stats` annotations

**Requirements:** REQ-01, REQ-02, REQ-03

---

## Phase 3: rosetta-embed + rosetta-suggest
**Goal:** Generate embeddings and get mapping suggestions.

**Delivers:**
- `rosetta/cli/embed.py` — LaBSE embeddings in `lexical-only` mode
- `rosetta/core/embedding.py` — model wrapper (sentence-transformers)
- `rosetta/cli/suggest.py` — cosine similarity + ranked suggestions
- `rosetta/core/similarity.py` — cosine sim, k-NN, anomaly detection
- Output formats defined: embedding JSON, suggestions JSON
- End-to-end: NOR CSV → embeddings → suggestions against master → correct cross-lingual matches

**Requirements:** REQ-04, REQ-05, REQ-06, REQ-07, REQ-08

---

## Phase 4: rosetta-lint
**Goal:** Catch unit mismatches, type issues, and suggest FnML conversions.

**Delivers:**
- `rosetta/cli/lint.py` with Click entrypoint
- `rosetta/core/units.py` — QUDT unit comparison
- FnML repository search (by source/target unit pair)
- BLOCK/WARNING/INFO lint report (JSON)
- Exit code 1 on BLOCKs
- `--strict` mode

**Requirements:** REQ-11, REQ-12, REQ-13, REQ-14, REQ-15

---

## Phase 5: Code quality infrastructure
**Goal:** Establish a robust, enforced code quality baseline — static type checking, consistent formatting/linting config, and Pydantic runtime validation for structured data — before building further tools on top.

**Delivers:**
- `basedpyright` configured in strict mode (pyproject.toml); clean check on all `rosetta/` source
- `ruff` fully configured (format + lint rules, target Python 3.11+)
- Full type annotations on all `rosetta/core/` and `rosetta/cli/` modules
- `pydantic>=2` added; Pydantic models for `LintFinding`, `LintReport`, `Suggestion`, `SuggestionReport`, `EmbeddingEntry`
- Bare `dict` returns replaced with typed models at core function boundaries
- Runtime validation at CLI output boundaries (models validated before JSON serialisation)

**Requirements:** REQ-QA-01, REQ-QA-02

---

## Phase 6: rosetta-rml-gen
**Goal:** Generate valid RML/FnML Turtle from approved decisions.

**Delivers:**
- `rosetta/cli/rml_gen.py` with Click entrypoint
- RML template engine (LogicalSource, SubjectMap, PredicateObjectMap)
- FnML `functionValue` wrapping when conversion function specified
- Output: valid RML executable by RMLMapper

**Requirements:** REQ-16, REQ-17

---

## Phase 7: rosetta-provenance
**Goal:** Stamp PROV-O metadata on mapping artifacts.

**Delivers:**
- `rosetta/cli/provenance.py` with Click entrypoint
- `rosetta/core/provenance.py` — PROV-O triple generation
- `--query` mode: human-readable provenance summary
- Version increment on each stamp

**Requirements:** REQ-18, REQ-19

---

## Phase 8: rosetta-validate
**Goal:** SHACL validation of mapping artifacts.

**Delivers:**
- `rosetta/cli/validate.py` with Click entrypoint
- pySHACL wrapper (single shape file or `--shapes-dir`)
- Structured JSON report
- Exit code 0/1

**Requirements:** REQ-20, REQ-21

---

## Phase 9: rosetta-accredit + feedback loop
**Goal:** Full governance layer. Accreditation state machine + suggestion feedback loop.

**Delivers:**
- `rosetta/cli/accredit.py` with Click entrypoints (submit/approve/revoke/status)
- `ledger.json` maintenance (accredited, revoked, deprecated mappings)
- `rosetta-suggest` reads ledger: boosts accredited precedents, excludes revoked
- `scripts/pipeline.sh` — end-to-end composition demo
- Full Milestone 3 test: approve NOR mapping → German suggestions improve; revoke → disappears

**Requirements:** REQ-22, REQ-23, REQ-24, REQ-25
