# Technology Stack

**Analysis Date:** 2026-04-13

## Languages
**Primary:** Python 3.11+ — all application code, CLI tools, and tests

## Runtime
**Environment:** Python 3.11+ (specified in `pyproject.toml` requires-python)
**Package Manager:** uv (lockfile: `uv-5ee6d68394d92c70.lock`)

## Frameworks
**Core:** Click 8.1+ — command-line interface framework for all 8 CLI tools (`rosetta-ingest`, `rosetta-embed`, `rosetta-suggest`, `rosetta-lint`, `rosetta-validate`, `rosetta-rml-gen`, `rosetta-provenance`, `rosetta-accredit`)
**RDF:** rdflib 6.3+ — semantic graph representation, SPARQL querying, Turtle/N-Triples serialization
**Validation:** pySHACL 0.20+ — shape-based RDF validation (SHACL profiles in `rosetta/policies/`)
**Testing:** pytest 7.4+ (dev) — unit and integration tests in `rosetta/tests/`

## Key Dependencies
**Critical:**
- **rdflib** (6.3+) — RDF graph parsing, SPARQL execution, URI/literal handling; core to all semantic operations
- **click** (8.1+) — CLI argument parsing, file I/O orchestration, exit code handling
- **sentence-transformers** (3.0+) — embedding models (LaBSE, E5) for semantic similarity in `rosetta-embed` and `rosetta-suggest`
- **pySHACL** (0.20+) — SHACL validation engine for `rosetta-lint` conformance checks
- **numpy** (1.26+) — vector math for embedding similarity calculations in `rosetta/core/similarity.py`
- **pyyaml** (6.0+) — YAML parsing (used by parsers in `rosetta/core/parsers/`)

## Configuration
**Environment:** 3-tier config precedence (CLI flag > env var > config file):
- Config file: `rosetta.toml` in CWD (loaded by `rosetta/core/config.py`)
- Env vars: prefix `ROSETTA_{SECTION}_{KEY}` (uppercase), e.g., `ROSETTA_EMBED_MODEL`
- CLI flags: override both (see each tool's `--config` option)

**Config sections (rosetta.toml):**
- `[general]` — store_path, default_format (Turtle)
- `[embed]` — model (default: sentence-transformers/LaBSE), mode
- `[suggest]` — top_k, min_score, anomaly_threshold
- `[lint]` — strict (boolean)

## Platform Requirements
**Development:** Linux/macOS/Windows with Python 3.11+ and uv package manager
**Production:** Python 3.11+ runtime; no external services required (all operations local to filesystem)

---
*Stack analysis: 2026-04-13*
