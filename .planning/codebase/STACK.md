# Technology Stack

**Analysis Date:** 2026-04-14

## Languages
**Primary:** Python 3.11+ — all application code, CLI tools, and tests

## Runtime
**Environment:** Python 3.11+ (specified in `pyproject.toml` requires-python)
**Package Manager:** uv — lockfile present at `uv.lock`; use `uv sync` to install, `uv add <pkg>` to add deps

## Frameworks
**CLI:** Click >=8.1 — all 9 entrypoints in `rosetta/cli/` use `@click.command()`
**RDF:** rdflib >=6.3 — semantic graph representation, SPARQL querying, Turtle/N-Triples serialization
**Validation:** pySHACL >=0.20 — SHACL shape validation; shapes in `rosetta/policies/`
**Testing:** pytest >=9.0 — tests in `rosetta/tests/`; run with `uv run pytest`
**Build:** hatchling — wheel backend, packages `rosetta/` only

## Key Dependencies
**rdflib >=6.3** — RDF graph parsing, SPARQL execution; core to all semantic operations in `rosetta/core/rdf_utils.py`
**click >=8.1** — CLI argument parsing, file I/O orchestration, exit code handling
**linkml >=1.10.0** — LinkML YAML schema parsing, OWL emission; `.linkml.yaml` is the primary schema format consumed by `rosetta-embed` and `rosetta-suggest`
**sentence-transformers >=3.0** — embedding generation; default model `intfloat/e5-large-v2` (set in `rosetta.toml [embed]`)
**schema-automator >=0.5.5** — auto-generates LinkML schemas from JSON/RDF/OpenAPI in `rosetta-ingest`
**sssom >=0.4.15** — SSSOM mapping set I/O; `rosetta-suggest` outputs `.sssom.tsv`
**pySHACL >=0.20** — SHACL validation engine for `rosetta-lint` and `rosetta-validate`
**numpy >=1.26** — cosine similarity computation in `rosetta/core/similarity.py`
**pydantic >=2.13** — typed user-facing JSON output; all models in `rosetta/core/models.py`
**deepl >=1.18,<2** — translation via DeepL API in `rosetta-translate`
**genson >=1.2** — JSON schema inference in `rosetta-ingest` (json-sample path)

## Configuration
**Primary config:** `rosetta.toml` at repo root — store path, RDF namespaces, embed model (`intfloat/e5-large-v2`), suggest thresholds, translate source lang, lint strictness
**Override:** all `rosetta.toml` settings overridable via CLI flags at runtime

## Linting & Type Checking
**Formatter:** `uv run ruff format .` (line-length 100, target py311)
**Linter:** `uv run ruff check .` — rules E, W, F, I, UP
**Type checker:** `uv run basedpyright` — strict on `rosetta/core/` and `rosetta/cli/`; basic on tests

## Platform Requirements
**Development:** Linux/macOS; uv installed; Python 3.11+; pre-commit hooks via `pre-commit >=4.5.1`
**Production:** Python 3.11+ only; no containerization config present; tools are Unix-composable CLI utilities (stdin/stdout, exit codes 0/1)

---
*Stack analysis: 2026-04-14*
