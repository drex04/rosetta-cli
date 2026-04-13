# Coding Conventions

**Analysis Date:** 2026-04-13

## Naming Patterns
**Files:** `snake_case.py` for modules; CLI files are named after their tool (`ingest.py`, `lint.py`)
**Functions:** `snake_case()` for all functions; helper functions prefixed with `_` (e.g., `_sparql_one()`)
**Variables:** `snake_case` for all locals; UPPERCASE constants (`ROSE`, `QUDT`, `XSD`)
**Classes:** `PascalCase` (e.g., `FieldSchema`, `Graph`); very few custom classes — mostly use rdflib/Click types

## Code Style
**Formatting:** No explicit linter configured; rely on `from __future__ import annotations` for type hints
**Python version:** 3.11+ (`requires-python = ">=3.11"` in `pyproject.toml`)
**Imports:** Use absolute imports from `rosetta.*`, never relative imports
**Docstrings:** Module-level docstring with tool purpose (see `rosetta/cli/ingest.py` line 1); function docstrings for public APIs

## Import Organization
**Order:**
1. `from __future__ import annotations` (always first)
2. Standard library (sys, pathlib, json, io)
3. Third-party (click, rdflib, pyyaml, sentence_transformers, numpy)
4. Local (`from rosetta.core.X import Y`)

See `rosetta/cli/lint.py` lines 1–21 for reference.

## Error Handling
**Patterns:** Catch broad `Exception`, emit user-friendly message via `click.echo(..., err=True)`, exit with code 1
**CLI errors:** Always surfaced to stderr with `click.echo(str(e), err=True)` then `sys.exit(1)`
**JSON output:** CLI tools that emit JSON still output error details as JSON with error field (see `rosetta/cli/lint.py` lines 275–284)

## Logging
**Framework:** Built-in `logging` module not used; prefer explicit `click.echo()` for user-facing messages
**Patterns:** No structured logging; errors written to stderr, success output to stdout (Unix principle)

## CLI Design
**Framework:** Click 8.1+ (from `pyproject.toml`)
**Options:** Use long-form names with `-` separators (`--input`, `--output`, `--strict`); short flags for common options (`-i`, `-o`)
**Output:** Stdout for data (RDF, JSON), stderr for errors; use `click.Path(exists=True)` for input validation
**Exit codes:** 0 = success/compliant, 1 = errors/violations; composable in shell scripts

## RDF Conventions
**Serialization:** Turtle (`.ttl`) for human-readable artifacts; N-Triples for machine interchange (see `rosetta.toml` line 3)
**Prefixes:** Inline namespace declarations using `rdflib.Namespace()` (see `rosetta/cli/lint.py` lines 18–21)
**Namespaces:** `rose:` = `http://rosetta.interop/ns/`, `qudt:` = `http://qudt.org/schema/qudt/`, `unit:` = QUDT unit vocab
**SPARQL:** Queries stored as module-level string constants (e.g., `_SRC_UNIT_QUERY`, `_TGT_UNIT_QUERY` in `lint.py`)

## Module Design
**Exports:** No `__all__` used; import directly from module (e.g., `from rosetta.core.units import UNIT_STRING_TO_IRI`)
**Patterns:** Core logic in `rosetta/core/`, CLI entry points in `rosetta/cli/`; each tool has one CLI command per file

---
*Convention analysis: 2026-04-13*
