# Plan Review: Phase 1 — Project Scaffolding

**Date:** 2026-04-12
**Mode:** HOLD SCOPE
**Plan reviewed:** `.planning/phases/01-scaffolding/01-PLAN.md`

## System Audit

- Greenfield project — no code exists yet
- ROADMAP vs Plan mismatch on synthetic fixtures (resolved: added Task 6)
- `tomli` vs `tomllib` inconsistency (resolved: removed `tomli`)
- No architecture artifacts — expected for Phase 1

## Findings Summary

| # | Section | Severity | Finding | Resolution |
|---|---------|----------|---------|------------|
| 1 | Scope (S1) | CRITICAL | REQ-26 missing from plan | Added REQ-26 + Task 6 for fixtures |
| 2 | Scope (S1) | CRITICAL | Synthetic fixtures have zero tasks | Added Task 6 with 4 fixture files |
| 3 | UX (S3) | CRITICAL | `tomli` contradicts locked CONTEXT.md | Removed; use `tomllib` (stdlib) |
| 4 | Scope (S1) | WARNING | REQ-10 has no acceptance truth | Added stdin/stdout truth |
| 5 | Criteria (S2) | WARNING | Truth #1 too weak (bare stub passes) | Strengthened: all 8 entrypoints + flag check |
| 6 | Criteria (S3) | WARNING | Config 3-tier not fully tested | Added env var test + key derivation spec |
| 7 | Completeness (S6) | WARNING | CLI stubs not enumerated | Listed all 8 explicitly in Task 4 |
| 8 | Testing (S8) | WARNING | I/O helpers have zero tests | Added test_io.py (3 tests) |
| 9 | Error (S10) | WARNING | No error-case tests | Added malformed TOML + invalid RDF tests |
| 10 | Arch (S7) | MINOR | rml_gen.py naming confusion | Added naming note in Task 4 |

## Error & Rescue Registry

| Method | Error Type | Rescued? | Test? | User Sees |
|--------|-----------|----------|-------|-----------|
| load_config(malformed) | TOMLDecodeError | YES (after review) | YES | Clear error message |
| load_graph(invalid) | rdflib ParseError | YES (after review) | YES | Clear error message |
| open_input(missing file) | FileNotFoundError | Implicit | NO | OS error (acceptable) |

## Failure Modes Registry

| Codepath | Failure Mode | Rescued? | Test? | User Sees? | Logged? |
|----------|-------------|----------|-------|------------|---------|
| config.load_config | malformed TOML | Y | Y | Clear msg | N/A CLI |
| rdf_utils.load_graph | invalid RDF | Y | Y | Clear msg | N/A CLI |
| io.open_input | file not found | OS | N | OS error | N/A CLI |
| CLI entrypoint | missing config | Y | Y | empty dict | N/A CLI |

## Test Coverage Diagram

```
                    PLANNED CODEPATHS & TEST STATUS (post-review)
                    =============================================

rosetta/core/config.py
  load_config(path)                    [TESTED]  test_load_config
  load_config(None) → {}               [TESTED]  test_missing_config_returns_empty
  load_config(malformed)               [TESTED]  test_load_config_malformed_toml        ← NEW
  get_config_value(cli_value)          [TESTED]  test_cli_overrides_config
  get_config_value(env var)            [TESTED]  test_env_overrides_config               ← NEW

rosetta/core/rdf_utils.py
  load_graph + save_graph              [TESTED]  test_roundtrip
  bind_namespaces                      [TESTED]  test_bind_namespaces
  query_graph                          [TESTED]  test_query_graph
  load_graph(invalid RDF)              [TESTED]  test_load_graph_invalid_rdf             ← NEW

rosetta/core/io.py
  open_input(file path)                [TESTED]  test_open_input_file                    ← NEW
  open_input('-') → stdin              [TESTED]  test_open_input_stdin                   ← NEW
  open_output('-') → stdout            [TESTED]  test_open_output_stdout                 ← NEW

rosetta/cli/*.py (8 entrypoints)
  --help                               [TRUTH]   all 8 verified
  ingest --config/--input/--output     [TRUTH]   flag presence verified

LEGEND:  [TESTED] = pytest  [TRUTH] = must_haves acceptance criteria
```

## What Already Exists

Nothing — greenfield. The plan creates the entire foundation.

## Dream State Delta

After Phase 1, we have a working Python project skeleton with tested config loading, RDF utilities, I/O helpers, 8 CLI stubs, and complete synthetic test data. This is ~15% of the way to Milestone 1 ("Can we ingest and compare?"). The foundation is solid for parallel development of Phases 2-3.

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | Greenfield, 3 inconsistencies found         |
| Step 0               | HOLD + 2 decisions made                     |
| Section 1  (Scope)   | 3 issues found (2 CRITICAL, 1 WARNING)      |
| Section 2  (Criteria)| 1 issue found (1 WARNING)                   |
| Section 3  (UX)      | 2 issues found (1 CRITICAL, 1 WARNING)      |
| Section 4  (Risk)    | 1 issue found (1 CRITICAL — dup of S1)      |
| Section 5  (Deps)    | 1 issue found (1 CRITICAL — dup of S3)      |
| Section 6  (Complete)| 2 issues found (1 CRITICAL, 1 WARNING)      |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 1 issue found (MINOR — naming)              |
| Section 8  (Testing) | 1 issue found (WARNING — io untested)       |
| Section 9  (Perf)    | 0 issues found (OK for scaffolding)         |
| Section 10 (Error)   | 1 issue found (WARNING — error cases)       |
+--------------------------------------------------------------------+
| PLAN.md updated      | 5 truths added, 6 artifacts added            |
| CONTEXT.md updated   | 5 decisions locked, 3 items deferred         |
| Error/rescue registry| 3 methods, 0 CRITICAL GAPS                  |
| Failure modes        | 4 total, 0 CRITICAL GAPS                    |
| Delight opportunities| N/A (HOLD mode)                             |
| Diagrams produced    | 1 (test coverage)                           |
| Unresolved decisions | 0                                           |
+====================================================================+
```
