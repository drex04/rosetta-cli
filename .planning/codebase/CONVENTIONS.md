# Coding Conventions

**Analysis Date:** 2026-04-13

## Naming Patterns
**Files:** `snake_case.py`; CLI files named after tool (`rml_gen.py` → `rosetta-rml-gen`)
**Functions:** `snake_case` verbs — `load_ledger`, `approve_mapping`, `bind_namespaces`; private helpers prefixed `_`
**Variables:** `snake_case`; short locals (`g` for Graph, `led` for Ledger); UPPER_SNAKE constants (`UNIT_STRING_TO_IRI`, `ROSE_NS`)
**Classes:** `PascalCase` Pydantic models — `LintFinding`, `ValidationReport`, `MappingDecision`
**Test URIs:** Module-level uppercase aliases — `SRC = "http://..."`, `TGT = "http://..."`

## Code Style
**Formatting:** `uv run ruff format .` — line length 100, target py311
**Linting:** `uv run ruff check .` — rules E, W, F, I, UP
**Type Checking:** `uv run basedpyright` — strict for `rosetta/core/` and `rosetta/cli/`; basic for `rosetta/tests/`

## Import Organization
**Always first:** `from __future__ import annotations`
**Order:**
1. Standard library (`json`, `sys`, `pathlib`)
2. Third-party (`click`, `rdflib`, `pydantic`)
3. Internal (`from rosetta.core.X import Y`) — always absolute, never relative

## Type Annotations
**Policy:** All functions in `rosetta/core/` and `rosetta/cli/` require explicit parameter and return type annotations.
**Broad rdflib types:** Use `rdflib.term.Node | None`, `rdflib.Graph` — do not narrow to `URIRef`/`Literal` at function boundaries.
**SPARQL rows:** Add `# pyright: ignore[reportAttributeAccessIssue]` at every `row.attribute` access.
**Test suppression:** Use `# pyright: ignore[reportArgumentType]` — NOT `# type: ignore[arg-type]` (basedpyright ignores the latter in test files).

## Error Handling
**Core functions:** Raise `ValueError` with descriptive messages matching what callers can `match` on (`"Cannot approve"`, `"already exists"`).
**CLI commands:** Catch `ValueError`, emit `click.echo(f"Error: {e}", err=True)`, then `sys.exit(1)`.
**Exit codes:** 0 = success/conformant, 1 = errors/violations — enforced for shell composability.

## Module Design
**Separation:** `rosetta/cli/` = Click entrypoints only, no business logic. All logic in `rosetta/core/`.
**CLI group pattern:** `@click.group()` + `@click.pass_context`; share state via `ctx.obj` dict.
**Exports:** No `__all__` — import explicitly by name.
**SPARQL strings:** Store as module-level string constants (e.g., `_SRC_UNIT_QUERY` in `lint.py`).

## Pydantic Models
**Location:** `rosetta/core/models.py` — all models in one file, grouped by tool.
**When to use:** All structured user-facing JSON outputs. Internal transient structures use `list[dict[str, Any]]`.
**Serialization:** `model.model_dump(mode="json")` before `json.dumps()` — never pass model instances directly.
**RootModel pattern:** Use `RootModel[dict[str, FieldType]]` for dict-shaped reports (`SuggestionReport`, `EmbeddingReport`).
**Timing:** Define models after function return shape is finalized — or write a failing test first.

---
*Convention analysis: 2026-04-13*
