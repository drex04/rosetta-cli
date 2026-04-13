# Codebase Structure

**Analysis Date:** 2026-04-13

## Directory Layout
```
rosetta-cli/
  rosetta/
    cli/           # 8 Click entrypoints (one per tool)
    core/          # Shared domain logic (RDF, embedding, similarity, units)
    policies/      # Static RDF graphs (QUDT, FnML)
    tests/         # pytest fixtures and test files
  pyproject.toml   # Python package config; defines 8 CLI tools
  rosetta.toml     # Runtime config (embed model, lint strictness, suggest top-k)
```

## Directory Purposes

**`rosetta/cli/`:**
- Purpose: CLI argument parsing and orchestration for all 8 tools
- Key files: `ingest.py`, `embed.py`, `suggest.py`, `lint.py`, `validate.py`, `rml_gen.py`, `provenance.py`, `accredit.py`
- Pattern: Each file = one Click command; reads config, calls core function, handles I/O and exit codes

**`rosetta/core/`:**
- Purpose: Reusable domain logic shared across all CLI tools
- Key files:
  - `rdf_utils.py` — RDF graph loading/saving, SPARQL execution, namespace binding
  - `embedding.py` — Extract text from RDF for embedding models; support master vs national schema detection
  - `similarity.py` — Cosine similarity ranking, top-k filtering, anomaly detection
  - `units.py` — QUDT unit lookup, dimension vector comparison, FnML suggestions
  - `unit_detect.py` — Detect units from field labels (meter, kilometer, knot, dBm, etc.)
  - `ingest_rdf.py` — Parse national schemas into RDF
  - `config.py` — 3-tier config loader (file < env < CLI)
  - `io.py` — Unix-composable stdin/stdout wrappers

**`rosetta/policies/`:**
- Purpose: Static knowledge graphs embedded as package data
- Key files: `qudt_units.ttl`, `fnml_registry.ttl`
- Pattern: Loaded at runtime by `rosetta.core.units.load_qudt_graph()`

**`rosetta/tests/`:**
- Purpose: Unit and integration tests
- Key files: `conftest.py` (synthetic RDF fixtures), `test_*.py` (per-module tests)

## Key File Locations

**Entry Points:** `rosetta/cli/{tool}.py:cli` — 8 Click decorators + main function
**Configuration:** `rosetta.toml` — shared defaults; `rosetta/core/config.py` — 3-tier loader
**Core Logic:** `rosetta/core/{rdf_utils,embedding,similarity,units}.py`
**Testing:** `rosetta/tests/{conftest,test_*.py}` — fixtures and pytest cases
**Policies:** `rosetta/policies/{qudt_units,fnml_registry}.ttl` — RDF knowledge bases

## Naming Conventions

**Files:** `{feature}.py` — lowercase, one concept per file (e.g., `units.py`, `embedding.py`)
**Functions:** `snake_case`; core functions prefixed `_` for private/internal use
**Classes:** `PascalCase` (e.g., `EmbeddingModel`)
**Tests:** `test_{module}.py` — filename matches tested module
**RDF files:** `*.ttl` in policies, `*.toml` for config

## Where to Add New Code

**New CLI tool:**
- Implementation: Create `rosetta/cli/{tool_name}.py` with Click @command decorator
- Tests: Add `rosetta/tests/test_{tool_name}.py`
- Register: Add entrypoint in `pyproject.toml` [project.scripts]

**New core module (e.g., validation logic):**
- Location: `rosetta/core/{feature}.py`
- Pattern: Implement pure functions or classes; depend only on rdflib, numpy, or existing core modules
- Tests: Add corresponding test file in `rosetta/tests/`

**New test fixture (e.g., synthetic graph):**
- Location: `rosetta/tests/conftest.py` (if shared across tests)
- Pattern: Use pytest @fixture decorator; return rdflib.Graph or other test data

**New policy/ontology:**
- Location: `rosetta/policies/{name}.ttl`
- Loading: Add to `rosetta.core.units.load_qudt_graph()` or similar function
- Pattern: Embed as package data via importlib.resources

---
*Structure analysis: 2026-04-13*
