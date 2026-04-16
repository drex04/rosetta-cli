# Code Conventions

**Updated:** 2026-04-16 (phases 14–15)

## Naming Patterns

- **Files:** `snake_case.py`; CLI files named after tool (`rml_gen.py` → `rosetta-rml-gen`)
- **Functions:** `snake_case` verbs — `load_graph()`, `append_log()`, `check_sssom_proposals()`; private helpers prefixed `_`
- **Variables:** `snake_case`; short locals (`g` for Graph); UPPER_SNAKE constants (`UNIT_STRING_TO_IRI`, `ROSE_NS`)
- **Classes:** `PascalCase` Pydantic models — `LintFinding`, `ValidationReport`, `SSSOMRow`
- **Module-level constants:** Private prefix `_` (e.g., `_NUMERIC_LINKML`, `_SSSOM_HEADER_LINES`, `_QUDT`)

## Code Style & Quality Gates

**8 mandatory checks before commit:**
```bash
uv run ruff format .                    # line-length 100, target py311
uv run ruff check .                     # rules: E, W, F, I, UP
uv run basedpyright                     # strict: rosetta/core+cli; basic: tests
uv run pytest -m "not slow"             # regression guard
uv run radon cc rosetta/core/ -n C -s   # complexity (fails grade C+, core only)
uv run vulture rosetta/ --exclude rosetta/tests --min-confidence 80
uv run bandit -r rosetta/ -x rosetta/tests -ll
uv run refurb rosetta/ rosetta/tests/
```

**Gotchas:**
- `rosetta/cli/` **excluded from radon** — Click handlers inherently high CC (45–56).
- `vulture --min-confidence 80` required — Pydantic fields and Click decorators are false positives.

## Imports

```python
from __future__ import annotations      # always first

import sys                              # stdlib
from datetime import UTC, datetime
from pathlib import Path

import click                             # third-party
import rdflib
from pydantic import BaseModel

from rosetta.core.rdf_utils import ...  # internal (always absolute)
```

## Type Annotations

- **All functions in `rosetta/core/` and `rosetta/cli/`:** explicit parameter and return types.
- **rdflib types:** broad — `rdflib.term.Node | None`, `rdflib.Graph`; never `URIRef`/`Literal` at boundaries.
- **SPARQL row access:** `# pyright: ignore[reportAttributeAccessIssue]` at every `.attribute`.
- **Tests (basic mode):** annotate fixture returns and non-obvious variables; use `# pyright: ignore[reportArgumentType]` (NOT `# type: ignore[arg-type]`).

Example:
```python
def load_graph(path: Path | TextIO, fmt: str = "turtle") -> Graph:
    """Load RDF from path or file-like object."""
```

## Error Handling

- **Core:** raise `ValueError` with human-readable message.
- **CLI:** catch `Exception`, emit `click.echo(f"Error: {exc}", err=True)`, `sys.exit(1)`.
- **Exit codes:** 0 = success/conformant, 1 = error/violation (Unix-composable).

```python
try:
    result = check_sssom_proposals(rows, log)
except Exception as exc:
    click.echo(f"Error: {exc}", err=True)
    sys.exit(1)
```

## Module Design

- **`rosetta/cli/*.py`:** Click only, no business logic. Use `@click.group()`, `@click.pass_context`, `ctx.obj` dict.
- **`rosetta/core/*.py`:** pure logic, raise on errors, no I/O except function params.

## Pydantic v2 Models

- **Location:** `rosetta/core/models.py`, grouped by tool.
- **User-facing outputs:** define model, construct in CLI, serialise with `model.model_dump(mode="json")` before `json.dumps()`.
- **RootModel:** for dict-shaped reports (`EmbeddingReport`, `SuggestionReport`).

Current models (see `rosetta/core/models.py`):
- `LintReport`, `LintFinding`, `LintSummary`, `FnmlSuggestion`
- `EmbeddingReport`, `EmbeddingVectors`
- `SuggestionReport`, `FieldSuggestions`, `Suggestion`
- `SSSOMRow` (11 columns: subject_id, predicate_id, object_id, mapping_justification, confidence, subject_label, object_label, mapping_date, record_id, **subject_datatype**, **object_datatype**)
- `ProvenanceRecord`
- `ValidationFinding`, `ValidationSummary`, `ValidationReport`

## LinkML & SSSOM

- **LinkML:** `SchemaDefinition` from `linkml_runtime`; dict-style class/slot access.
- **SSSOM TSV:** **11 columns** (phase 15+): subject_id, predicate_id, object_id, mapping_justification, confidence, subject_label, object_label, mapping_date, record_id, subject_datatype, object_datatype.
- **SSSOM header:** emit `_SSSOM_HEADER_LINES` block (mapping_set_id, tool, license, curie_map) before column header.
- **OWL derank:** `owl:differentFrom` + `HC` justification marks rejection (confidence penalty, not deletion).

## Conventional Commits

`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `perf:`

Example: `fix: five correctness issues found in phase 15 review`

## README Convention

**Public API surface changes require README update before done:** CLI commands, option names, placement, output formats, exit codes.
