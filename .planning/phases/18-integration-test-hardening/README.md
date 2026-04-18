# Phase 18: Integration & E2E Test Hardening

**Goal:** Stress-test every CLI tool with realistic pipelines, diverse input formats, and adversarial user-mistake scenarios. Introduce layered pytest markers and consolidate fixtures into `conftest.py`.

**Status:** Draft — awaiting approval + `/fh:plan-review`.

## Plans

| Plan | Focus | Requirement | Depends on |
|------|-------|-------------|------------|
| [18-01](18-01-PLAN.md) | Test infrastructure foundation | `REQ-TEST-INFRA-01` | — |
| [18-02](18-02-PLAN.md) | Positive-path pipeline coverage (incl. 4 translate mocks + 2 subprocess smoke) | `REQ-TEST-POSITIVE-01` | 18-01 |
| [18-03](18-03-PLAN.md) | Adversarial / negative input stress tests (incl. 6 translate error-path mocks) | `REQ-TEST-ADVERSARIAL-01` | 18-01 |

## Context

- [CONTEXT.md](CONTEXT.md) — locked decisions (D-18-01 through D-18-08)

## Scope summary

- **Production code touched:** zero. Phase 18 is additive-only.
- **New pytest markers:** `integration`, `e2e` (composable with existing `slow`).
- **New subdirectories:** `fixtures/{nations, stress, adversarial}/`, `tests/{integration, adversarial, smoke}/`.
- **New tests:** ~12 positive-path integration tests + ~18 adversarial tests + 2 subprocess smoke tests.
- **CI change:** default job runs the full suite; new `fast-gate` job runs `-m "not slow and not e2e"` for sub-minute PR feedback.
- **DeepL API cost:** $0 (all 10 translate tests use the `fake_deepl` mock fixture).

## Requirements introduced

- `REQ-TEST-INFRA-01` — test infrastructure (markers, fixture consolidation, CI, README)
- `REQ-TEST-POSITIVE-01` — positive-path integration coverage for every CLI tool
- `REQ-TEST-ADVERSARIAL-01` — negative-path coverage for user-mistake scenarios
