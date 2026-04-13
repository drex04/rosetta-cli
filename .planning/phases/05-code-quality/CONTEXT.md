# Phase 5 Context: Code Quality Infrastructure

## Locked Decisions

### Tooling
- **basedpyright** (not mypy/pyright) — strict mode for source, basic mode for tests
- **ruff** — already in dev deps; configure `[tool.ruff]` in pyproject.toml; rules: E, W, F, I, UP
- **pydantic v2** — Plan 02 only; not introduced in Plan 01

### Type annotation style
- rdflib node return types use **broad types**: `rdflib.term.Node | None` (not narrowed to `URIRef`/`Literal`)
- `reportMissingModuleSource = "none"` in `pyrightconfig.json` to suppress rdflib/sentence-transformers stub warnings
- Use `from __future__ import annotations` where needed for forward references

### basedpyright split config
- Source (`rosetta/cli/`, `rosetta/core/`) → strict
- Tests (`rosetta/tests/`) → basic
- Implemented via two entries in `pyrightconfig.json` `executionEnvironments`

### CI
- GitHub Actions workflow at `.github/workflows/ci.yml`
- Jobs: ruff (format check + lint), basedpyright, pytest
- Runs on push and pull_request to master

### Out of scope for Plan 01
- pydantic models (Plan 02)
- Pre-commit hooks (not requested)
- Coverage thresholds (pytest-cov already present, not gated)
