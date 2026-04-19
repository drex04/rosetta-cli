# Rosetta CLI

## Response Style

Be concise. State what changed and what's next; skip narration and recap. One or two sentences per update is almost always enough.

## Fix-on-Sight

If you find bugs or code quality issues during review, investigation, or any other work, **fix them immediately in the same change**. Do not file follow-up tickets, deferred-items lists, or "revisit later" notes. Every issue surfaced in review must be addressed before the work is considered done.

**This applies to every severity — Critical, Important, Minor, and Nitpick.** Never defer. Never split minor findings into a "later" pass. If a review surfaces a missing test, a doc drift, a stale comment, or a one-line cleanup, fold it into the same commit as the bigger fixes. The cost of opening the file again later is always higher than fixing it now.

## Code Exploration

Use claude-mem smart tools as the primary tools for understanding code:

- `smart_outline` — see file structure without reading the full file
- `smart_unfold` — read a specific function by name
- `smart_search` — find symbols and patterns across the codebase
- `search` / `get_observations` — recall decisions and patterns from prior sessions

Fall back to Read only when you need the full file for editing.

## Project

Composable CLI tools for semantic mapping between NATO defense schemas and a master ontology.
Tools: `rosetta-ingest`, `rosetta-embed`, `rosetta-suggest`, `rosetta-lint`, `rosetta-validate`, `rosetta-yarrrml-gen`, `rosetta-provenance`, `rosetta-accredit`.

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
- `rosetta/tests/` — pytest tests + synthetic fixtures
- `rosetta.toml` — shared config (all settings overridable via CLI flags)

## Conventions

- **Public API surface changes must update README.md _and_ `docs/`** — any change to CLI commands, option names, option placement (e.g. group-level vs subcommand-level), output formats, or exit codes requires matching updates in the README tool section *and* the corresponding `docs/cli/<tool>.md` narrative content. The `docs/cli/*.md` pages auto-render Click `--help` via `mkdocs-click`, so keep the `help=` strings and command docstrings current — they are the source of truth for options.
- **Docs-as-code is CI-gated** — `uv run mkdocs build --strict` runs in the `docs` CI job and as a pre-commit hook. Broken nav, broken links, and `mkdocs-click` directive failures fail the build. Site deploys from `master` to `https://drex04.github.io/rosetta-cli/` via `.github/workflows/docs.yml`.
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
- `uv run radon cc rosetta/core/ -n C -s` — complexity check (core only; fails on grade C+)
- `uv run vulture rosetta/ --exclude rosetta/tests --min-confidence 80` — dead code detection
- `uv run bandit -r rosetta/ -x rosetta/tests -ll` — security scan
- `uv run refurb rosetta/` — Python modernization (single arg avoids mypy duplicate-module path collision; `rosetta/tests/` is already covered by the recursive walk)
- `uv run mkdocs build --strict` — docs build (fails on broken nav, missing pages, `mkdocs-click` errors)

CI enforces all nine on every push/PR (`.github/workflows/ci.yml`), with dedicated jobs for `analysis` (radon, vulture, bandit) and `docs` (mkdocs).

### Type annotation rules

- All functions in `rosetta/core/` and `rosetta/cli/` must have explicit parameter and return annotations.
- Use **broad rdflib types**: `rdflib.term.Node | None`, `rdflib.Graph` — do not narrow to `URIRef`/`Literal` at function boundaries.
- Use `list[dict[str, Any]]` only for internal transient structures. User-facing JSON outputs must use Pydantic models (see below).
- Tests are annotated (basic mode) — annotate fixture return types and non-obvious variables.

### Pydantic models (rosetta/core/models.py)

User-facing JSON outputs are typed via Pydantic v2:

| Output            | Model                                                                  |
| ----------------- | ---------------------------------------------------------------------- |
| `rosetta-lint`    | `LintReport` (contains `LintFinding`, `LintSummary`, `FnmlSuggestion`) |
| `rosetta-suggest` | `SuggestionReport` (RootModel)                                         |
| `rosetta-embed`   | `EmbeddingReport` (RootModel)                                          |

- Construct model instances in the CLI, not bare dicts.
- Serialise with `model.model_dump(mode="json")` before `json.dumps()`.
- New structured outputs must define a model in `rosetta/core/models.py` first.
- Define Pydantic models only after the underlying function return shape is finalized — or write a failing test first. Redesigning mid-phase is costly.

## Gotchas

- **Orchestrator plan naming:** After `/fh:auto`, check `.planning/phases/NN-*/` for files named `plan0N-*.md`. If present, rename to `NN-01-PLAN.md` — the orchestrator expects this exact format and will fail plan-work on every resume if it doesn't find it. _(learnings: 2026-04-13)_
- **basedpyright in tests:** `# type: ignore[arg-type]` may not suppress errors in test files. Use `# pyright: ignore[reportArgumentType]` instead. _(learnings: 2026-04-13)_
- **rdflib SPARQL boundaries:** `row.attribute` access on query results is untyped — use `# pyright: ignore[reportAttributeAccessIssue]` at every access point. Standard solution for untyped library integration. _(learnings: 2026-04-13)_
- **radon CLI exclusion:** `rosetta/cli/` is excluded from radon complexity checks — Click command handlers have inherently high CC scores (grade F, CC 45–56) that are not actionable. Only `rosetta/core/` business logic is checked. _(learnings: 2026-04-15)_
- **vulture false positives:** Pydantic field declarations and Click decorators trigger vulture false positives — `--min-confidence 80` is required. Test fixtures also fire; tests are excluded via `--exclude rosetta/tests`. _(learnings: 2026-04-15)_
- **linkml-map fork pin:** `linkml-map` is pinned via `[tool.uv.sources]` to SHA `48afe279` on `drex04/linkml-map` (branch `feat/yarrrml-compiler`). Run `uv sync` after any SHA change; the fork's `YarrrmlCompiler` lives at `linkml_map.compiler.yarrrml_compiler`. _(learnings: 2026-04-17)_

## Conventions

- **Stub tests belong in the tool's own test file** — don't put `test_<tool>_stub_exits_1` in `test_ingest.py`. When the real implementation lands, the stub test should be in the right file to update, not delete. _(learnings: 2026-04-13)_
