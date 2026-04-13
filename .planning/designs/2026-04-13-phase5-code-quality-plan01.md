# Design: Phase 5 Plan 01 — Static Typing Infrastructure

## Approved Design

**basedpyright strict** on `rosetta/cli/` and `rosetta/core/` source; **basic** on `rosetta/tests/`.  
**ruff** configured with rules E, W, F, I, UP.  
**GitHub Actions CI** runs both checks on every push/PR.

## Decisions Locked

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | basedpyright strict for source, basic for tests | Strict where it matters; tests are verified by running, not static analysis |
| 2 | rdflib node types annotated broadly (`rdflib.term.Node \| None`) | Narrowing requires casts everywhere; broad types keep signatures stable |
| 3 | `reportMissingModuleSource = "none"` for rdflib/sentence-transformers | These libs have incomplete stubs; suppress globally rather than per-site |
| 4 | CI via GitHub Actions (`.github/workflows/ci.yml`) | Enforce checks on every push/PR; no Makefile/justfile overhead |
| 5 | ruff rules: E, W, F, I, UP | Core flake8 + isort + pyupgrade; skip ANN (basedpyright covers annotations) |
| 6 | Test files annotated (basic mode, not strict) | Coverage without friction from fixture type noise |

## Deferred to Plan 02

- pydantic models for structured output (`LintFinding`, `LintReport`, etc.)
- Replacing bare `dict` returns with typed models
