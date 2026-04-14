# Architecture

**Analysis Date:** 2026-04-14

## Pattern Overview
**Overall:** Unix-composable pipeline of single-responsibility CLI tools
**Key Characteristics:**
- Each tool reads from file/stdin, writes to file/stdout — composable in shell pipelines
- Strict layer separation: CLI (I/O + Click) → Core (pure logic) → Store (file persistence)
- Canonical intermediate format is LinkML YAML (`.linkml.yaml`); SSSOM TSV for mapping candidates
- No shared in-process state — tools communicate through files on disk

## Layers

**CLI Layer:**
- Purpose: Click entrypoints, argument parsing, I/O orchestration, exit codes
- Contains: One module per tool; calls core functions; constructs Pydantic models for output
- Location: `rosetta/cli/`
- Depends on: `rosetta/core/`
- Used by: Users, shell pipelines

**Core Layer:**
- Purpose: Pure business logic — normalization, embedding, similarity, RDF utilities, provenance
- Contains: Stateless functions + `EmbeddingModel` class; all Pydantic output models
- Location: `rosetta/core/`
- Depends on: rdflib, linkml-runtime, schema-automator, sentence-transformers, pydantic
- Used by: `rosetta/cli/`

**Policies Layer:**
- Purpose: Static knowledge graphs and validation rules (package data)
- Contains: `mapping.shacl.ttl`, `qudt_units.ttl`, `fnml_registry.ttl`
- Location: `rosetta/policies/`
- Depends on: nothing (static files loaded via `importlib.resources`)
- Used by: `rosetta-validate`, `rosetta-lint`

**Store Layer:**
- Purpose: Local file-based repository for accredited mappings and ontologies
- Contains: Turtle files by nation (`store/national-schemas/`), master ontology (`store/master-ontology/`), approved mappings (`store/accredited-mappings/`)
- Location: `store/`
- Used by: `rosetta-accredit`, `rosetta-suggest`

## Data Flow

**rosetta-ingest (canonical ingestion):**
1. `rosetta/cli/ingest.py` — accepts input file (CSV, TSV, JSON Schema, OpenAPI, RDFS/TTL, XSD, LinkML YAML) + `--schema-name`
2. `rosetta/core/normalize.py:normalize_schema()` — dispatches to schema-automator importers for 7 formats; hoists nested objects into `$defs`
3. Output: `.linkml.yaml` (LinkML `SchemaDefinition`)

**rosetta-embed:**
1. `rosetta/cli/embed.py` — reads `.linkml.yaml`
2. `rosetta/core/embedding.py:extract_text_inputs_linkml()` — extracts slot/class titles + descriptions as text strings
3. `rosetta/core/embedding.py:EmbeddingModel.encode()` — encodes with `intfloat/e5-large-v2`; E5 passage prefix applied
4. Output: embedding JSON (`EmbeddingReport` Pydantic model)

**rosetta-suggest:**
1. `rosetta/cli/suggest.py` — reads source embedding JSON + master embedding JSON
2. `rosetta/core/similarity.py:cosine_matrix()` → `rank_suggestions()` — cosine similarity, top-k
3. `rosetta/core/similarity.py:apply_ledger_feedback()` / `apply_sssom_feedback()` — optional boost/revoke
4. Output: `.sssom.tsv` (SSSOM TSV format, rows typed as `SSSOMRow`)

**rosetta-translate:**
- `rosetta/cli/translate.py` → `rosetta/core/translation.py` — LLM/DeepL translation of LinkML YAML field labels

**rosetta-lint → rosetta-validate → rosetta-accredit:**
- Lint: checks slots against QUDT units + SHACL shapes; outputs `LintReport` JSON
- Validate: runs pySHACL against `rosetta/policies/mapping.shacl.ttl`; exit code only
- Accredit: stamps approved SSSOM mappings into `store/accredited-mappings/`

## Key Abstractions

**`normalize_schema()` (`rosetta/core/normalize.py`):**
- Purpose: Single dispatch point for all 7 input formats → `SchemaDefinition`
- Contract: Always returns `SchemaDefinition`; raises `ValueError` for unsupported formats

**`EmbeddingModel` (`rosetta/core/embedding.py`):**
- Purpose: Wraps sentence-transformers with E5 passage/query prefix logic for asymmetric retrieval
- Contract: Default model `intfloat/e5-large-v2`; use `encode()` for passages, `encode_query()` for queries

**`SSSOMRow` (`rosetta/core/models.py`):**
- Purpose: Typed row for SSSOM TSV output from `rosetta-suggest`
- Contract: Fields match SSSOM spec column names; serialize via `model_dump(mode="json")`

**Pydantic output models (`rosetta/core/models.py`):**
- Purpose: All user-facing structured output is typed — never bare dicts at CLI boundaries
- Contract: Construct in CLI layer; serialize with `model.model_dump(mode="json")` before `json.dumps()`

**Config precedence (`rosetta/core/config.py`):**
- Contract: CLI flag > env var (`ROSETTA_SECTION_KEY`) > `rosetta.toml`

## Entry Points

All 9 tools in `pyproject.toml [project.scripts]`:
- `rosetta-ingest` → `rosetta/cli/ingest.py:cli`
- `rosetta-embed` → `rosetta/cli/embed.py:cli`
- `rosetta-suggest` → `rosetta/cli/suggest.py:cli`
- `rosetta-translate` → `rosetta/cli/translate.py:cli`
- `rosetta-lint` → `rosetta/cli/lint.py:cli`
- `rosetta-validate` → `rosetta/cli/validate.py:cli`
- `rosetta-rml-gen` → `rosetta/cli/rml_gen.py:cli`
- `rosetta-provenance` → `rosetta/cli/provenance.py:cli`
- `rosetta-accredit` → `rosetta/cli/accredit.py:cli`

## Error Handling
**Strategy:** Exit 0 = success, exit 1 = errors/violations. CLI catches core `ValueError`, prints to stderr, calls `sys.exit(1)`. Core raises `ValueError` with human-readable message — no internal recovery.

---
*Architecture analysis: 2026-04-14*
