# Technology Stack

**Analysis Date:** 2026-04-13

## Languages
**Primary:** Python 3.11+ — all application code, CLI tools, and tests

## Runtime
**Environment:** Python 3.11+ (specified in `pyproject.toml` requires-python)
**Package Manager:** uv — lockfile present at `uv.lock`; use `uv sync` to install, `uv add <pkg>` to add deps

## Frameworks
**CLI:** Click >=8.1 — all 8 entrypoints in `rosetta/cli/` use `@click.command()`
**RDF:** rdflib >=6.3 — semantic graph representation, SPARQL querying, Turtle/N-Triples serialization
**Validation:** pySHACL >=0.20 — SHACL shape validation; shapes in `rosetta/policies/`
**Testing:** pytest >=9.0 — tests in `rosetta/tests/`; run with `uv run pytest`
**Build:** hatchling — wheel backend, packages `rosetta/` only

## Key Dependencies
**rdflib >=6.3** — RDF graph parsing, SPARQL execution; core to all semantic operations in `rosetta/core/rdf_utils.py`
**click >=8.1** — CLI argument parsing, file I/O orchestration, exit code handling
**sentence-transformers >=3.0** — LaBSE model for multilingual embeddings; drives `rosetta-embed` and `rosetta-suggest`
**pySHACL >=0.20** — SHACL validation engine for `rosetta-lint` conformance checks
**numpy >=1.26** — vector math for cosine similarity in `rosetta/core/similarity.py`
**pydantic >=2.13** — typed user-facing JSON output; all models in `rosetta/core/models.py`
**pyyaml >=6.0** — YAML/config parsing used by core parsers

## Configuration
**Primary config:** `rosetta.toml` at repo root — store path, RDF namespaces, embed model, suggest thresholds, lint strictness
**Override:** all `rosetta.toml` settings overridable via CLI flags at runtime
**No required env vars** for core operation — model weights downloaded on first run by sentence-transformers

## Linting & Type Checking
**Formatter:** `uv run ruff format .` (line-length 100, target py311)
**Linter:** `uv run ruff check .` — rules E, W, F, I, UP
**Type checker:** `uv run basedpyright` — strict on `rosetta/core/` and `rosetta/cli/`; basic on tests

## Platform Requirements
**Development:** Linux/macOS; uv installed; Python 3.11+
**Production:** Python 3.11+ only; no containerization config present; tools are Unix-composable CLI utilities (stdin/stdout, exit codes 0/1)

---
*Stack analysis: 2026-04-13*
