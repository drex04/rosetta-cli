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
- Location: `rosetta/core/{rdf_utils,embedding,similarity,units,unit_detect,ingest_rdf,config,io}.py`
- Depends on: rdflib, sentence-transformers, numpy, pyyaml, pyshacl
- Used by: All CLI tools

**Policies (Knowledge Base):**
- Purpose: Static RDF graphs for QUDT units and FnML registry
- Contains: TTL files (qudt_units.ttl, fnml_registry.ttl); no Python logic
- Location: `rosetta/policies/{qudt_units,fnml_registry}.ttl`
- Depends on: None
- Used by: `rosetta.core.units.load_qudt_graph()`

**Tests:**
- Purpose: Pytest fixtures and unit/integration tests
- Contains: Conftest with synthetic RDF fixtures, test files per module
- Location: `rosetta/tests/{conftest,test_*.py}`
- Depends on: pytest, core modules
- Used by: `uv run pytest`

## Data Flow

**rosetta-lint (representative end-to-end flow):**
1. CLI entry: `rosetta/cli/lint.py:cli()` parses `--source`, `--master`, `--suggestions`
2. Load graphs: `rdflib.Graph().parse(source, format="turtle")` → Load RDF into memory
3. SPARQL queries: `_sparql_one()` executes unit/datatype detection queries against source & master
4. Unit compatibility: `rosetta.core.units.units_compatible()` compares dimension vectors from QUDT policy graph
5. Lint rules: Iterate suggestions JSON, check for datatype mismatches (numeric vs string), unit conflicts
6. Output: JSON findings or N-Triples violations to `rosetta.core.io.open_output()`
7. Exit: code 0 if no findings, 1 if --strict and WARNINGs present

**rosetta-embed:**
1. Load graph: `rosetta.core.rdf_utils.load_graph(input_path)` → parses Turtle
2. Extract text: `rosetta.core.embedding.extract_text_inputs(g)` → SPARQL SELECT to find Attributes or Fields
3. Embed: `EmbeddingModel.encode(texts)` → LaBSE model produces float32 vectors
4. Output: JSON {uri_string → {"lexical": [vector]}} to stdout/file

**rosetta-suggest:**
1. Load embeddings: JSON {uri → {"lexical": array}} from source and master files
2. Build matrices: NumPy arrays A (source vectors), B (master vectors)
3. Rank: `rosetta.core.similarity.rank_suggestions()` → cosine similarity, top-k filtering, anomaly detection
4. Output: JSON suggestions with scores and anomaly flags

## Key Abstractions

**RDF Graph (rdflib.Graph):**
- Purpose: Canonical in-memory representation of all semantic data
- Examples: `rosetta/cli/lint.py:96-100`, `rosetta/core/rdf_utils.py:49`
- Contract: All graphs bound with standard namespaces via `bind_namespaces()`

**Config Precedence (3-tier):**
- Purpose: Allow runtime override of settings from rosetta.toml
- Examples: `rosetta/core/config.py:37-67`, `rosetta/cli/embed.py:23-25`
- Contract: CLI value beats env var (ROSETTA_SECTION_KEY) beats config file

**SPARQL Queries (parameterized):**
- Purpose: Extract entities and relationships from RDF without hard-coding triple patterns
- Examples: `rosetta/cli/lint.py:30-60`, `rosetta/core/embedding.py:11-33`
- Contract: Return typed rdflib terms; use None-guards for OPTIONAL results

## Entry Points
**rosetta-ingest:** `rosetta/cli/ingest.py:cli` — Load national schema TTL → store RDF
**rosetta-embed:** `rosetta/cli/embed.py:cli` — Extract text from RDF → LaBSE embeddings JSON
**rosetta-suggest:** `rosetta/cli/suggest.py:cli` — Compare embeddings → ranked candidates JSON
**rosetta-lint:** `rosetta/cli/lint.py:cli` — Validate units/datatypes against master → findings JSON
**rosetta-validate:** `rosetta/cli/validate.py:cli` — SHACL shape validation
**rosetta-rml-gen:** `rosetta/cli/rml_gen.py:cli` — Generate RML mappings
**rosetta-provenance:** `rosetta/cli/provenance.py:cli` — Track mapping provenance
**rosetta-accredit:** `rosetta/cli/accredit.py:cli` — Accredit mapping quality

## Error Handling
**Strategy:** Unix convention — exit 0 on success, 1 on errors
- CLI layer wraps core logic in try/except, logs to stderr via click.echo(..., err=True)
- Core layer raises ValueError with human-readable message; no exception recovery
- RDF parsing failures: wrap rdflib exceptions in ValueError with source label
- Missing SPARQL results: return None, caller decides if error or info

---
*Architecture analysis: 2026-04-13*
