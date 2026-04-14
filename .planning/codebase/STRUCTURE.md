# Codebase Structure

**Analysis Date:** 2026-04-14

## Directory Layout
```
rosetta-cli/
  rosetta/
    cli/           # 9 Click entrypoints (one per tool)
    core/          # Shared domain logic + Pydantic models
      parsers/     # DELETED in Phase 12 — directory is empty
    policies/      # Static RDF knowledge graphs (TTL, package data)
    tests/         # pytest tests + synthetic fixtures
      fixtures/    # Sample national schema files (JSON, CSV, YAML, TTL)
  store/           # Local file-based RDF repository
    national-schemas/
    master-ontology/
    accredited-mappings/
  pyproject.toml   # Package config; 9 CLI entrypoints
  rosetta.toml     # Runtime config (model name, lint strictness, top-k)
  scripts/         # Developer utility scripts
```

## Directory Purposes

**`rosetta/cli/`:**
- Purpose: One Click `@command` per tool; I/O orchestration, exit codes
- Key files: `ingest.py`, `embed.py`, `suggest.py`, `translate.py`, `lint.py`, `validate.py`, `rml_gen.py`, `provenance.py`, `accredit.py`
- Pattern: Read config → call core function → construct Pydantic model → serialize → exit code

**`rosetta/core/`:**
- Purpose: Pure domain logic — no Click imports; full type annotations required
- Key files:
  - `normalize.py` — `normalize_schema()` dispatches 7 formats to schema-automator; outputs `SchemaDefinition`
  - `embedding.py` — `extract_text_inputs_linkml()` + `EmbeddingModel` (default: `intfloat/e5-large-v2`)
  - `similarity.py` — `cosine_matrix()`, `rank_suggestions()`, `apply_ledger_feedback()`, `apply_sssom_feedback()`
  - `models.py` — all Pydantic output models: `LintReport`, `EmbeddingReport`, `SSSOMRow`, `ProvenanceRecord`, `Ledger`, `MappingDecision`
  - `rdf_utils.py` — graph load/save, SPARQL helpers, namespace binding
  - `units.py` — QUDT unit lookup, dimension vector comparison
  - `unit_detect.py` — detect units from field labels
  - `translation.py` — DeepL/LLM translation of LinkML YAML labels
  - `config.py` — 3-tier config loader
  - `io.py` — `open_input()` / `open_output()` stdin/stdout context managers
  - `provenance.py` — provenance record stamping and querying
  - `accredit.py` — accreditation state machine
  - `rml_builder.py` — RML mapping document construction
- Note: `parsers/` subdirectory was deleted in Phase 12; only empty `__pycache__` remains

**`rosetta/policies/`:**
- Purpose: Static knowledge graphs embedded as package data
- Key files: `qudt_units.ttl`, `fnml_registry.ttl`, `mapping.shacl.ttl`
- Loading: `importlib.resources` in `rosetta/core/units.py`

**`rosetta/tests/`:**
- Purpose: Unit and integration tests; one test file per module
- Key files: `conftest.py` (shared fixtures), `test_{module}.py`, `fixtures/` (sample schemas)
- Fixtures: `deu_patriot.json`, `nor_radar.csv`, `usa_c2.yaml`, `master_cop_ontology.ttl`

**`store/`:**
- Purpose: Runtime file repository for national schemas, master ontology, accredited mappings
- Used by: `rosetta-accredit`, `rosetta-suggest` (master embeddings)

## Key File Locations
**Entry Points:** `rosetta/cli/{tool}.py:cli`
**Configuration:** `rosetta.toml` (defaults), `rosetta/core/config.py` (loader)
**Normalization:** `rosetta/core/normalize.py` — single dispatch for all ingest formats
**Embedding:** `rosetta/core/embedding.py` — `EmbeddingModel`, `extract_text_inputs_linkml()`
**Output Models:** `rosetta/core/models.py` — all Pydantic models live here
**Policies:** `rosetta/policies/{qudt_units,fnml_registry,mapping.shacl}.ttl`

## Naming Conventions
**Files:** `snake_case.py` — one concept per file
**CLI tools:** `rosetta/cli/{name}.py` → command `rosetta-{name}` (e.g., `rml_gen.py` → `rosetta-rml-gen`)
**Output formats:** `.linkml.yaml` (ingested schemas), embedding JSON (embeddings), `.sssom.tsv` (suggestions)
**RDF artifacts:** `*.ttl` (human-readable), `*.nt` (machine interchange)
**Tests:** `test_{module}.py` mirrors `rosetta/core/{module}.py` or `rosetta/cli/{module}.py`

## Where to Add New Code

**New CLI tool:**
- Entrypoint: `rosetta/cli/{tool_name}.py` with `@click.command()` named `cli`
- Tests: `rosetta/tests/test_{tool_name}.py` — stub test goes here, not in another tool's file
- Register: `pyproject.toml [project.scripts]` → `rosetta-{tool-name} = "rosetta.cli.{tool_name}:cli"`

**New core module:**
- Location: `rosetta/core/{feature}.py` — pure functions, full type annotations, no Click imports
- Raise `ValueError` on bad input; no internal recovery

**New Pydantic output model:**
- Location: `rosetta/core/models.py` — finalize return shape before defining model
- Serialize in CLI layer with `model.model_dump(mode="json")`

**New ingest format:**
- Add branch in `rosetta/core/normalize.py:normalize_schema()` using schema-automator importer
- Add fixture to `rosetta/tests/fixtures/` and test in `rosetta/tests/test_normalize.py`

**New policy/ontology:**
- Location: `rosetta/policies/{name}.ttl`
- Load via `importlib.resources` in relevant core module

---
*Structure analysis: 2026-04-14*
