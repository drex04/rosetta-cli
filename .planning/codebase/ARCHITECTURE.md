# Architecture

**Analysis Date:** 2026-04-13

## Pattern Overview
**Overall:** Composable CLI toolkit with layered separation (CLI, core logic, RDF utilities, policies)
**Key Characteristics:**
- Unix-composable: tools read/write files or stdin/stdout; exit code 0 = success, 1 = error
- RDF-centric: all data flows through rdflib graphs; Turtle for human artifacts, N-Triples for machine interchange
- Stateless processing: each tool is independent; config via 3-tier precedence (CLI flag > env var > rosetta.toml)
- Policy-driven: QUDT unit registry and FnML mappings embedded in `rosetta/policies/`

## Layers
**CLI (Presentation):**
- Purpose: Parse arguments, call core logic, output results, handle exit codes
- Contains: Click decorators, file I/O coordination, JSON serialization
- Location: `rosetta/cli/{ingest,embed,suggest,lint,validate,rml_gen,provenance,accredit}.py`
- Depends on: `rosetta.core`, `rosetta.core.io`
- Used by: Direct shell invocation via pyproject.toml entrypoints

**Core Logic (Domain):**
- Purpose: Implement semantic mapping, embedding, linting, and RDF manipulation
- Contains: Algorithm implementations (similarity ranking, unit compatibility, RDF SPARQL queries)
- Location: `rosetta/core/{rdf_utils,embedding,similarity,units,unit_detect,ingest_rdf,config,io,models,provenance,accredit,rml_builder}.py`
- Depends on: rdflib, sentence-transformers, numpy, pyyaml, pyshacl, pydantic
- Used by: All CLI tools

**Parser Subsystem:**
- Purpose: Normalize heterogeneous national schemas (CSV, JSON Schema, OpenAPI) to a common field list
- Contains: Format-specific parsers dispatched by file extension or `--input-format`
- Location: `rosetta/core/parsers/{csv_parser,json_schema_parser,openapi_parser,_types}.py`; `__init__.py` exposes `dispatch_parser()`
- Used by: `rosetta/cli/ingest.py`

**Policies (Knowledge Base):**
- Purpose: Static RDF graphs for QUDT units and FnML registry
- Contains: TTL files (qudt_units.ttl, fnml_registry.ttl); no Python logic
- Location: `rosetta/policies/`
- Depends on: None
- Used by: `rosetta.core.units.load_qudt_graph()`

**Tests:**
- Purpose: Pytest fixtures and unit/integration tests
- Location: `rosetta/tests/{conftest,test_*.py}`
- Depends on: pytest, core modules

## Data Flow

**rosetta-ingest (canonical flow):**
1. `cli/ingest.py:cli()` opens stdin/file via `core/io.open_input()`
2. `core/parsers.dispatch_parser()` detects format → returns `list[FieldRecord]`
3. `core/ingest_rdf.fields_to_graph()` converts field list → `rdflib.Graph`
4. `core/rdf_utils.save_graph()` serializes → Turtle/N-Triples to stdout/file

**rosetta-lint (representative pipeline):**
1. Load source + master Turtle graphs via rdflib
2. SPARQL queries extract unit/datatype info; None-guard OPTIONAL vars
3. `rosetta.core.units.units_compatible()` compares QUDT dimension vectors
4. Emit `LintReport` Pydantic model → JSON stdout; exit 1 if --strict + warnings

**rosetta-suggest (embedding pipeline):**
1. Load embeddings JSON {uri → {"lexical": array}} for source and master
2. Build NumPy matrices → `rosetta.core.similarity.rank_suggestions()` (cosine similarity, top-k)
3. Wrap in `SuggestionReport` Pydantic model → JSON stdout

## Key Abstractions

**FieldRecord (`core/parsers/_types.py`):**
- Purpose: Normalized field representation before RDF conversion
- Contract: All parsers return `list[FieldRecord]`; consistent keys across formats

**rdflib.Graph:**
- Purpose: Universal in-memory representation for all semantic data
- Contract: Always bind namespaces via `bind_namespaces()`; use broad `rdflib.term.Node | None` at function boundaries

**Pydantic output models (`core/models.py`):**
- Purpose: Type-safe JSON output for lint (`LintReport`), suggest (`SuggestionReport`), embed (`EmbeddingReport`)
- Contract: Construct in CLI layer; serialize via `model.model_dump(mode="json")` before `json.dumps()`

**Config precedence (`core/config.py`):**
- Purpose: Allow runtime override of rosetta.toml settings
- Contract: CLI flag > env var (ROSETTA_SECTION_KEY) > config file

## Entry Points
**rosetta-ingest:** `rosetta/cli/ingest.py:cli` — parse national schema → RDF Turtle
**rosetta-embed:** `rosetta/cli/embed.py:cli` — extract RDF field labels → LaBSE embeddings JSON
**rosetta-suggest:** `rosetta/cli/suggest.py:cli` — cosine similarity → ranked mapping candidates JSON
**rosetta-lint:** `rosetta/cli/lint.py:cli` — unit/datatype semantic lint → LintReport JSON
**rosetta-validate:** `rosetta/cli/validate.py:cli` — SHACL shape validation → exit code
**rosetta-rml-gen:** `rosetta/cli/rml_gen.py:cli` — generate RML mapping rules
**rosetta-provenance:** `rosetta/cli/provenance.py:cli` — stamp/query mapping provenance
**rosetta-accredit:** `rosetta/cli/accredit.py:cli` — manage accreditation state machine

## Error Handling
**Strategy:** Unix convention — exit 0 on success, 1 on errors/violations
- CLI wraps core logic in `try/except Exception as e: click.echo(str(e), err=True); sys.exit(1)`
- Core raises `ValueError` with human-readable message; no internal recovery
- SHACL violations: exit 1 without exception; findings written to output before exit
- Missing SPARQL OPTIONAL results: return `None`; caller decides if error or info

---
*Architecture analysis: 2026-04-13*
