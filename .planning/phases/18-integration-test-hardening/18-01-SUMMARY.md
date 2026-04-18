---
name: 18-01-SUMMARY
phase: 18-integration-test-hardening
plan: 18-01
requirement: REQ-TEST-INFRA-01
status: complete
completed: 2026-04-18
commit: 86b3738
test_metrics:
  fast_passing: 378
  fast_total: 378
  slow_passing: 2
  slow_total: 3
  spec_tests_count: 0
---

# Plan 18-01 — Test Infrastructure Foundation (Summary)

## Goal achieved

Landed the plumbing every subsequent integration/e2e test will rely on:
pytest markers, shared fixture paths in `conftest.py`, reusable DeepL mock,
subdirectory reorganization under `fixtures/`, retag of the three existing
integration test files, CI wiring, and README update.

Phase 18 is additive — zero production code under `rosetta/core/` or
`rosetta/cli/` was modified.

## Truths verified

| # | Truth | Result |
|---|-------|--------|
| 1 | `pytest -m integration` selects 3 retagged files; no `PytestUnknownMarkWarning` | PASS (14 tests across 3 files) |
| 2 | `pytest -m e2e` selects `test_yarrrml_run_e2e.py` only | PASS (1 test) |
| 3 | Migrated integration files use fixture injection, not hardcoded paths | PASS |
| 4 | `_FIXTURES = Path` absent from 3 migrated integration files | PASS |
| 5 | CI default job runs full suite; new `fast-gate` job runs constrained selector | PASS |
| 6 | README documents marker scheme with 2+ selection examples | PASS (5 examples) |
| 7 | `uv run pytest` still green after reorganization | 378/378 fast pass; 1 pre-existing slow failure |
| 8 | Atomic-commit rule: Tasks 2–5 staged together | PASS (single commit 86b3738) |
| 9 | `fake_deepl` smoke test declares only `fake_deepl` in signature | PASS |
| 10 | Truth #4 scoped to plan-completion snapshot | PASS (planned growth documented) |

## Artifacts delivered

- `pyproject.toml` — markers `slow`, `integration`, `e2e`
- `rosetta/tests/conftest.py` — 11 fixture-path fixtures + `fake_deepl`
- `rosetta/tests/fixtures/nations/` — 9 relocated fixtures (via `git mv`, history preserved)
- `rosetta/tests/fixtures/{stress,adversarial}/` — tracked placeholder dirs
- `rosetta/tests/test_accredit_integration.py` — `pytestmark = [pytest.mark.integration]`
- `rosetta/tests/test_yarrrml_compile_integration.py` — `pytestmark = [pytest.mark.integration]`, fixture-path migration
- `rosetta/tests/test_yarrrml_run_e2e.py` — `pytestmark = [integration, e2e, slow]`, fixture-path migration
- `.github/workflows/ci.yml` — default `test` job runs full suite; new `fast-gate` job
- `README.md` — rewritten "Running tests" section with marker docs

## Additional fixes (Fix-on-Sight / risk-mitigation per plan)

The plan's Risks section warned that test files outside the retag list might
reference the old flat paths. Three fixes were applied in the same commit:

- `rosetta/tests/test_ingest.py` — `FIXTURES` constant moved to `fixtures/nations/`
- `rosetta/tests/test_normalize.py` — `FIXTURES` constant moved to `fixtures/nations/`
- `rosetta/tests/test_yarrrml_gen.py` — module-level `_FIXTURES` moved to `fixtures/nations/`
- `README.md` (outside the Running-tests section) — CLI example paths updated

## Quality gates (all pass)

- `uv run ruff format .` — clean
- `uv run ruff check .` — clean
- `uv run basedpyright` — 0 errors, 1297 warnings (pre-existing noise)
- `uv run pytest` — 380 passed, 1 failed (pre-existing)
- `uv run radon cc rosetta/core/ -n C -s` — no C+ findings
- `uv run vulture rosetta/ --exclude rosetta/tests --min-confidence 80` — clean
- `uv run bandit -r rosetta/ -x rosetta/tests -ll` — no issues
- `uv run refurb rosetta/ rosetta/tests/` — clean (after `list(texts)` → `texts.copy()` fix)

## Issues Encountered

- **Pre-existing e2e failure (not caused by Phase 18):** `test_e2e_nor_radar_csv_to_jsonld`
  fails on the m→ft unit conversion assertion. Verified by stashing all Phase 18 changes
  and re-running the test on clean `master` — same failure. STATE.md's Phase 16 Plan 03
  Follow-up section flags fork-SHA drift: the unit-conversion fix was on a local checkout
  at commit `89e79d4` but `pyproject.toml` currently pins the published fork at
  `00150683e9ad03cefa00e3c0e2d55f0e3cc6df9f`, which appears to not contain the
  `UnitConversionConfiguration → GREL` patch. Out of scope for Phase 18
  (infrastructure-only); logged here so Plan 18-02 / 18-03 can opt to skip or
  mark-xfail this test.

## Not done in this plan

- Authoring new integration tests → Plan 18-02
- Adversarial test scaffolding → Plan 18-03
