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

## Code Quality

### Mandatory checks — run before every commit

- `uv run ruff format .` — auto-format
- `uv run ruff check .` — lint (rules: E, W, F, I, UP)
- `uv run basedpyright` — static type check (strict: source, basic: tests)
- `uv run pytest -m "not slow"` — regression guard

CI enforces all four on every push/PR (`.github/workflows/ci.yml`).

### Type annotation rules

- All functions in `rosetta/core/` and `rosetta/cli/` must have explicit parameter and return annotations.
- Use **broad rdflib types**: `rdflib.term.Node | None`, `rdflib.Graph` — do not narrow to `URIRef`/`Literal` at function boundaries.
- Use `list[dict[str, Any]]` only for internal transient structures. User-facing JSON outputs must use Pydantic models (see below).
- Tests are annotated (basic mode) — annotate fixture return types and non-obvious variables.

### Pydantic models (rosetta/core/models.py)

User-facing JSON outputs are typed via Pydantic v2:

| Output | Model |
|--------|-------|
| `rosetta-lint` | `LintReport` (contains `LintFinding`, `LintSummary`, `FnmlSuggestion`) |
| `rosetta-suggest` | `SuggestionReport` (RootModel) |
| `rosetta-embed` | `EmbeddingReport` (RootModel) |

- Construct model instances in the CLI, not bare dicts.
- Serialise with `model.model_dump(mode="json")` before `json.dumps()`.
- New structured outputs must define a model in `rosetta/core/models.py` first.
- Define Pydantic models only after the underlying function return shape is finalized — or write a failing test first. Redesigning mid-phase is costly.

## Gotchas

- **Orchestrator plan naming:** After `/fh:auto`, check `.planning/phases/NN-*/` for files named `plan0N-*.md`. If present, rename to `NN-01-PLAN.md` — the orchestrator expects this exact format and will fail plan-work on every resume if it doesn't find it. *(learnings: 2026-04-13)*
- **basedpyright in tests:** `# type: ignore[arg-type]` may not suppress errors in test files. Use `# pyright: ignore[reportArgumentType]` instead. *(learnings: 2026-04-13)*
- **rdflib SPARQL boundaries:** `row.attribute` access on query results is untyped — use `# pyright: ignore[reportAttributeAccessIssue]` at every access point. Standard solution for untyped library integration. *(learnings: 2026-04-13)*

## Conventions

- **Stub tests belong in the tool's own test file** — don't put `test_<tool>_stub_exits_1` in `test_ingest.py`. When the real implementation lands, the stub test should be in the right file to update, not delete. *(learnings: 2026-04-13)*
