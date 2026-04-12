# Rosetta CLI

## Code Exploration

Use claude-mem smart tools as the primary tools for understanding code:
- `smart_outline` — see file structure without reading the full file
- `smart_unfold` — read a specific function by name
- `smart_search` — find symbols and patterns across the codebase
- `search` / `get_observations` — recall decisions and patterns from prior sessions

Fall back to Read only when you need the full file for editing.

## Project

Composable CLI tools for semantic mapping between NATO defense schemas and a master ontology.
Tools: `rosetta-ingest`, `rosetta-embed`, `rosetta-suggest`, `rosetta-lint`, `rosetta-validate`, `rosetta-rml-gen`, `rosetta-provenance`, `rosetta-accredit`.

## Stack

- **Language:** Python 3.11+ | **Package manager:** uv
- `uv run pytest` — run tests
- `uv run rosetta-ingest` — run a tool
- `uv sync` — install deps
- `uv add <pkg>` — add dependency

## Architecture

- `rosetta/cli/` — Click entrypoints (one per tool)
- `rosetta/core/` — shared library (rdf_utils, embedding, similarity, units, provenance)
- `rosetta/policies/` — SHACL shapes + Rego policies
- `rosetta/store/` — local file-based RDF repository
- `rosetta/tests/` — pytest tests + synthetic fixtures
- `rosetta.toml` — shared config (all settings overridable via CLI flags)

## Conventions

- All tools: read from files or stdin, write to files or stdout (Unix-composable)
- RDF serialization: Turtle (.ttl) for human artifacts, N-Triples for machine interchange
- Exit code 0 = success/conformant, 1 = errors/violations (composable in shell scripts)
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`

## Planning

- Current phase: `.planning/STATE.md`
- Roadmap: `.planning/ROADMAP.md`
- Architecture decisions: `.planning/DECISIONS.md`
- Full implementation plan: `PLAN.md`
