# Codebase Structure

**Analysis Date:** 2026-04-16 | **Phases:** 14 (audit-log SSSOM), 15 (SSSOM-only lint)

## Directory Layout
```
rosetta-cli/
  rosetta/
    cli/              # 9 Click entrypoints (one per tool)
    core/             # Shared domain logic + Pydantic models
    policies/         # Static RDF knowledge graphs (TTL, package data)
    tests/            # pytest tests + synthetic fixtures
      fixtures/       # Sample national schema files (JSON, CSV, YAML, TTL)
  store/              # Runtime file repository
  pyproject.toml      # Package config; 9 CLI entrypoints; dev dependencies
  rosetta.toml        # Runtime config (model name, lint strictness, top-k, accredit log path)
  scripts/            # Developer utility scripts
```

## Directory Purposes

**`rosetta/cli/` (9 Click entrypoints):**
- Purpose: One Click `@command` per tool; I/O orchestration, exit codes.
- Current files: `ingest.py`, `embed.py`, `suggest.py`, `lint.py`, `validate.py`, `rml_gen.py`, `provenance.py`, `accredit.py`, `translate.py`.
- Pattern: Load config (3-tier precedence) → call core function → construct Pydantic model → serialize via `model.model_dump(mode="json")` → exit code.

**`rosetta/core/` (Pure domain logic):**
- Purpose: Stateless functions + utility classes; full type annotations required; no Click imports.
- Current files:
  - `normalize.py` — `normalize_schema()` dispatches 7 formats (json-schema, openapi, xsd, csv, tsv, json-sample, rdfs/ttl) via schema-automator; returns `SchemaDefinition`.
  - `embedding.py` — `EmbeddingModel` class (default: `intfloat/e5-large-v2`); E5 passage prefix logic ("passage: " for E5, "" for others).
  - `features.py` — `extract_structural_features_linkml()` returns 5-element vectors [depth, child_count, slot_usage, cardinality, parent_depth] per node (normalized to [0,1]).
  - `similarity.py` — `cosine_matrix()`, `rank_suggestions()` (lexical + structural blend, weight=0.2), `apply_sssom_feedback()` (audit-log boost/derank).
  - `accredit.py` — state-machine functions: `load_log()`, `append_log()`, `parse_sssom_tsv()`, `current_state_for_pair()`, `query_pending()`, `check_ingest_row()`.
  - `models.py` — Pydantic v2 output types: `SSSOMRow` (with mapping_date, record_id, subject_datatype, object_datatype), `LintReport`, `EmbeddingReport` (RootModel), `SuggestionReport` (RootModel), `ValidationReport`, `ProvenanceRecord`, `MappingDecision`.
  - `units.py` — QUDT graph loading via importlib.resources; unit compatibility checks; FNML suggestions via `suggest_fnml()`.
  - `unit_detect.py` — regex-based unit detection from field labels; returns detected unit string or None.
  - `rdf_utils.py` — graph load/save, SPARQL query helpers, namespace binding.
  - `translation.py` — DeepL translation of LinkML YAML field labels; source_lang: "auto" or "EN".
  - `config.py` — 3-tier config loader (CLI flag > env var > rosetta.toml > default).
  - `io.py` — `open_input()` / `open_output()` context managers for stdin/stdout.
  - `provenance.py` — provenance record stamping and querying.
  - `rml_builder.py` — RML mapping document construction.
- Deleted: `parsers/` subdirectory (Phase 12); all format dispatch now in `normalize.py`.

**`rosetta/policies/` (Static knowledge graphs):**
- Purpose: Embedded package data (RDF ontologies, SHACL shapes).
- Current files: `qudt_units.ttl` (QUDT unit IRIs), `fnml_registry.ttl` (FNML function definitions), `mapping.shacl.ttl` (SHACL constraints).
- Loading: `importlib.resources` in `rosetta/core/units.py`.

**`rosetta/tests/` (pytest suite):**
- Purpose: Unit and integration tests; one test file per core/cli module.
- Current test files: `conftest.py` (shared fixtures), `test_accredit.py`, `test_accredit_integration.py`, `test_embed.py`, `test_features.py`, `test_ingest.py`, `test_lint.py`, `test_models.py`, `test_normalize.py`, `test_provenance.py`, `test_rdf_utils.py`, `test_rml_gen.py`, `test_suggest.py`, `test_translate.py`, `test_validate.py`, `test_unit_detect.py`, `test_config.py`, `test_io.py`.
- Fixtures: `nor_radar.csv`, `deu_patriot.json`, `deu_radar_sample.json`, `usa_c2.yaml`, `master_cop_ontology.ttl`.
- Convention: Stub tests belong in the tool's own test file (not elsewhere); `test_<tool>_stub_exits_1` stays in `test_<tool>.py` until real implementation lands.

**`store/` (Runtime file repository):**
- Purpose: File persistence written by CLI tools.
- Current file: `audit-log.sssom.tsv` — append-only SSSOM audit log (9 columns: subject_id, predicate_id, object_id, mapping_justification, confidence, subject_label, object_label, mapping_date, record_id).
- Stamped by `rosetta-accredit ingest`: mapping_date (ISO 8601 UTC), record_id (UUID4).
- Phase 15 design: datatype columns are intentionally NOT in the audit log; they live only on the 11-column suggest-output TSV.

**`scripts/` (Developer utilities):**
- Purpose: Demo and testing scripts (not part of CLI).
- Files: Development/testing utilities.

## Key File Locations

**CLI Entry Points:** `rosetta/cli/{tool}.py:cli` (registered in `pyproject.toml [project.scripts]`).

**Config:** 
- Defaults: `rosetta.toml` ([general], [namespaces], [embed], [translate], [suggest], [lint], [accredit]).
- Loader: `rosetta/core/config.py`.
- Precedence: CLI flag > `ROSETTA_SECTION_KEY` env var > `rosetta.toml` > hardcoded default.

**Core Abstractions:**
- `normalize_schema()` — `rosetta/core/normalize.py` — single dispatch for all ingest formats.
- `EmbeddingModel` — `rosetta/core/embedding.py` — E5/LaBSE sentence-transformers wrapper.
- `extract_structural_features_linkml()` — `rosetta/core/features.py` — LinkML → 5-element vectors.
- `rank_suggestions()` — `rosetta/core/similarity.py` — cosine similarity + structural blend.
- `apply_sssom_feedback()` — `rosetta/core/similarity.py` — audit-log boost/derank.
- Accredit state-machine — `rosetta/core/accredit.py` — append-only log I/O + validation.

**Pydantic Models:** `rosetta/core/models.py` — all structured outputs (SSSOMRow, LintReport, EmbeddingReport, SuggestionReport, etc.).

**Policies:** `rosetta/policies/{qudt_units,fnml_registry,mapping.shacl}.ttl`.

**Audit Log:** `store/audit-log.sssom.tsv` — 9-column SSSOM TSV; stamped by accredit ingest.

## Naming Conventions

**Files:** `snake_case.py` — one concept per file.

**CLI tools:** `rosetta/cli/{name}.py` → command `rosetta-{name}` (e.g., `rml_gen.py` → `rosetta-rml-gen`).

**Output formats:** 
- `.linkml.yaml` — ingested schemas (LinkML YAML).
- JSON — embeddings (EmbeddingVectors), suggestions (SuggestionReport), lint reports (LintReport).
- `.sssom.tsv` — SSSOM mappings; 11 columns from `rosetta-suggest` output, 9 columns in the persisted audit log.
- `*.ttl` — human-readable RDF; `*.nt` — machine interchange.

**Tests:** `test_{module}.py` mirrors `rosetta/core/{module}.py` or `rosetta/cli/{module}.py`.

## Where to Add New Code

**New CLI tool:**
- Entrypoint: `rosetta/cli/{tool_name}.py` with `@click.command()` named `cli`.
- Tests: `rosetta/tests/test_{tool_name}.py` — stub test goes here, not elsewhere.
- Register: `pyproject.toml [project.scripts]` → `rosetta-{tool-name} = "rosetta.cli.{tool_name}:cli"`.

**New core module:**
- Location: `rosetta/core/{feature}.py` — pure functions, full type annotations (source: `rosetta/core/`, tests: `rosetta/core/`).
- Contract: Raise `ValueError` on bad input; no internal recovery.

**New Pydantic output model:**
- Location: `rosetta/core/models.py` — finalize return shape before defining model.
- Serialize in CLI layer with `model.model_dump(mode="json")` before `json.dumps()`.

**New ingest format:**
- Add dispatch branch in `rosetta/core/normalize.py:normalize_schema()` using schema-automator importer.
- Add fixture to `rosetta/tests/fixtures/` and test in `rosetta/tests/test_normalize.py`.

**New policy/ontology:**
- Location: `rosetta/policies/{name}.ttl` (static RDF).
- Load via `importlib.resources` in relevant core module.

## Testing

**Run all tests:** `uv run pytest -m "not slow"`.

**Run specific test:** `uv run pytest rosetta/tests/test_lint.py::test_lint_sssom_datatype_mismatch`.

**Fixtures location:** `rosetta/tests/fixtures/` (nor_radar.csv, deu_patriot.json, deu_radar_sample.json, usa_c2.yaml, master_cop_ontology.ttl).

**Shared fixtures:** `rosetta/tests/conftest.py`.
