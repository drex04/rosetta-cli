# Codebase Structure

**Analysis Date:** 2026-04-13

## Directory Layout
```
rosetta-cli/
  rosetta/
    cli/           # 8 Click entrypoints (one per tool)
    core/          # Shared domain logic
      parsers/     # Format-specific schema parsers (CSV, JSON Schema, OpenAPI)
    policies/      # Static RDF knowledge graphs (TTL)
    tests/         # pytest fixtures and test files
  pyproject.toml   # Package config; defines 8 CLI tool entrypoints
  rosetta.toml     # Runtime config (model name, lint strictness, top-k)
```

## Directory Purposes

**`rosetta/cli/`:**
- Purpose: CLI argument parsing and orchestration; one file per tool
- Key files: `ingest.py`, `embed.py`, `suggest.py`, `lint.py`, `validate.py`, `rml_gen.py`, `provenance.py`, `accredit.py`
- Pattern: Each file = one Click `@command`; reads config, calls core function, serializes output, handles exit codes

**`rosetta/core/`:**
- Purpose: Reusable domain logic shared across all CLI tools
- Key files:
  - `rdf_utils.py` — graph load/save, SPARQL helpers, namespace binding
  - `embedding.py` — text extraction from RDF + LaBSE encoding
  - `similarity.py` — cosine similarity ranking, top-k, anomaly detection
  - `units.py` — QUDT unit lookup, dimension vector comparison, FnML suggestions
  - `unit_detect.py` — detect units from field labels (meter, knot, dBm, etc.)
  - `ingest_rdf.py` — convert `FieldRecord` list → `rdflib.Graph`
  - `models.py` — Pydantic output models (`LintReport`, `SuggestionReport`, `EmbeddingReport`)
  - `config.py` — 3-tier config loader (file < env < CLI flag)
  - `io.py` — `open_input()` / `open_output()` stdin/stdout context managers
  - `provenance.py` — provenance record stamping and querying
  - `accredit.py` — accreditation state machine logic
  - `rml_builder.py` — RML mapping document construction

**`rosetta/core/parsers/`:**
- Purpose: Normalize heterogeneous national schemas to `list[FieldRecord]`
- Key files: `_types.py` (FieldRecord type), `csv_parser.py`, `json_schema_parser.py`, `openapi_parser.py`
- Entry: `__init__.py` exposes `dispatch_parser(src, path, fmt, nation, max_rows)`

**`rosetta/policies/`:**
- Purpose: Static knowledge graphs embedded as package data
- Key files: `qudt_units.ttl`, `fnml_registry.ttl`
- Loading: `rosetta.core.units.load_qudt_graph()` via `importlib.resources`

**`rosetta/tests/`:**
- Purpose: Unit and integration tests; one test file per module
- Key files: `conftest.py` (shared synthetic RDF fixtures), `test_{module}.py`

## Key File Locations
**Entry Points:** `rosetta/cli/{tool}.py:cli` — Click command decorated with `@click.command()`
**Configuration:** `rosetta.toml` (defaults), `rosetta/core/config.py` (loader)
**Core Logic:** `rosetta/core/{rdf_utils,embedding,similarity,units,ingest_rdf}.py`
**Output Models:** `rosetta/core/models.py`
**Testing:** `rosetta/tests/{conftest.py,test_*.py}`
**Policies:** `rosetta/policies/{qudt_units,fnml_registry}.ttl`

## Naming Conventions
**Files:** `snake_case.py` — one concept per file (e.g., `unit_detect.py`)
**Functions:** `snake_case`; private/internal prefixed with `_`
**Classes:** `PascalCase` (e.g., `EmbeddingModel`, `LintReport`)
**Tests:** `test_{module}.py` — filename mirrors the tested module
**RDF artifacts:** `*.ttl` (human), `*.nt` (machine interchange)

## Where to Add New Code

**New CLI tool:**
- Entrypoint: `rosetta/cli/{tool_name}.py` with `@click.command()` named `cli`
- Tests: `rosetta/tests/test_{tool_name}.py`
- Register: `pyproject.toml` `[project.scripts]` → `rosetta-{tool-name} = "rosetta.cli.{tool_name}:cli"`

**New core module:**
- Location: `rosetta/core/{feature}.py`
- Pattern: Pure functions with full type annotations; no Click imports; raise `ValueError` on bad input
- Tests: `rosetta/tests/test_{feature}.py`

**New Pydantic output model:**
- Location: `rosetta/core/models.py` — define model after return shape is finalized
- Usage: Construct in CLI layer; serialize via `model.model_dump(mode="json")`

**New parser format:**
- Location: `rosetta/core/parsers/{format}_parser.py`
- Register: Add to `dispatch_parser()` in `rosetta/core/parsers/__init__.py`

**New policy/ontology:**
- Location: `rosetta/policies/{name}.ttl`
- Loading: Load via `importlib.resources` in `rosetta/core/units.py` or a new loader

---
*Structure analysis: 2026-04-13*
