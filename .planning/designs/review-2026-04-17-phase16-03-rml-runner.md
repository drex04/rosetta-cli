---
plan: 16-03
review_date: 2026-04-17
mode: HOLD
reviewer: plan-review (business + engineering agents, parallel dispatch)
---

# Plan Review — Plan 16-03 (morph-kgc runner + JSON-LD framing + E2E)

Human-reference summary. Findings are folded into `16-03-PLAN.md` (must_haves.truths with `[review]` prefix) and `CONTEXT.md` (16-03 review decisions section). Build skill picks these up automatically.

## Mode

**HOLD + harden.** Scope locked; all findings are failure-mode hardening, test coverage additions, and error-path tightening. No feature expansion, no feature cuts.

## Completion summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | 8 findings; 7 carried into merged review    |
| Step 0               | HOLD mode locked; 3 decisions to user       |
| Section 1  (Scope)   | 2 issues found (0 CRITICAL, 2 WARNING)      |
| Section 2  (Errors)  | 3 error paths, 2 CRITICAL unrescued writes  |
| Section 3  (UX)      | 3 issues (1 CRITICAL, 2 WARNING)            |
| Section 4  (Risk)    | 4 issues (1 CRITICAL, 3 WARNING)            |
| Section 5  (Deps)    | 2 issues (0 CRITICAL, 1 WARNING + 1 OK)     |
| Section 6  (Correct) | 4 issues (1 CRITICAL, 3 WARNING)            |
+--------------------------------------------------------------------+
| Section 7  (Eng Arch)| 3 issues (0 CRITICAL, 3 WARNING, 3 OK)      |
| Section 8  (Tests)   | 7 issues (2 CRITICAL, 4 WARNING, 1 OK)      |
| Section 9  (Perf)    | 4 issues (0 CRITICAL, 3 WARNING, 1 OK)      |
| Section 10 (Security)| 7 issues (0 CRITICAL, 4 WARNING, 3 OK)      |
+--------------------------------------------------------------------+
| PLAN.md updated      | 17 [review] truths added, 0 artifacts added |
| CONTEXT.md updated   | 3 decisions locked, 2 items deferred        |
| Error/rescue registry| 16 methods mapped, 5 CRITICAL → truths       |
| Failure modes        | 12 total, 7 CRITICAL GAPs → truths          |
| Diagrams produced    | Test Coverage + Failure Modes Registry      |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## The 3 user-input decisions (locked)

| # | Question | Choice | Why |
|---|----------|--------|-----|
| 1 | Tempdir cleanup strategy | Context manager + always `--workdir` in tests | Clean, testable, no `atexit`/`CliRunner` incompatibility |
| 2 | Empty morph-kgc graph handling | Warn + exit 0 | Unix-pipeline friendly; condition visible without breaking composability |
| 3 | E2E unit-conversion assertion strictness | `pytest.approx(rel=1e-2)` + structural guard | Robust to GREL/morph-kgc upgrades; still proves conversion |

## Failure Modes Registry (final)

| Codepath | Failure | Rescued? | Tested? | User sees | Logged? | Status |
|----------|---------|----------|---------|-----------|---------|--------|
| `YarrrmlCompiler(…)` signature | `TypeError` | NOW YES | Fast CLI test | Clean stderr | Yes | RESOLVED |
| `morph_kgc.materialize()` INFO logs | stdout pollution | NOW YES (setLevel) | Unit asserts stdout is JSON | No log interleaving | N/A | RESOLVED |
| `atexit.rmtree` in CliRunner | Cleanup never fires | NOW YES (ctx mgr) | CLI tests pass `--workdir tmp_path` | No leak | N/A | RESOLVED |
| `--jsonld-output` OSError | Raw traceback | NOW YES | Fast CLI test (monkeypatched) | exit 1 + stderr | stderr | RESOLVED |
| `_generate_jsonld_context` no `@context` | Silent wrong-shape | NOW YES (raise ValueError) | Unit test | exit 1 + stderr | stderr | RESOLVED |
| Empty morph-kgc graph | Silent exit 0 | NOW YES (stderr warn) | Unit + E2E | Warning + JSON-LD | stderr | RESOLVED |
| `run_materialize` raises | Generic catch | NOW YES (unit test) | Unit test | exit 1 + stderr | stderr | RESOLVED |
| `graph.serialize(json-ld)` | Opaque rdflib error | NOW YES (RuntimeError wrap) | Implicit via E2E | Clean stderr | stderr | RESOLVED |
| `$(DATA_FILE)` placeholder drift | E2E-only detection | NOW YES (fast-CI assert) | Fast test (fork drift guard) | Clean stderr | stderr | RESOLVED |
| `--workdir` non-writable | Unclear | NOW YES (Path.touch probe) | Fast CLI test | exit 1 + stderr | stderr | RESOLVED |
| E2E CSV cols ≠ schema slots | Silent empty JSON-LD | NOW YES (set ⊆ set) | E2E assertion | Diagnostic AssertionError | pytest | RESOLVED |
| E2E unit-conv numeric | Ordering-brittle | NOW YES (compaction-tolerant + approx) | E2E | pytest diff | pytest | RESOLVED |

All 12 failure modes now have rescue paths + tests.

## Test Coverage Diagram (final, post-review)

```
NEW CODEPATH                                  TEST FILE                 STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_substitute_data_path — placeholder present   test_rml_runner.py        COVERED
_substitute_data_path — placeholder absent    test_rml_runner.py        COVERED
_build_ini — section structure                test_rml_runner.py        COVERED
_build_ini — OSError wrapped RuntimeError     test_rml_runner.py        COVERED (review)
_generate_jsonld_context — @context present   test_rml_runner.py        COVERED
_generate_jsonld_context — @context absent    test_rml_runner.py        COVERED (review)
_generate_jsonld_context — upstream error     test_rml_runner.py        COVERED (review)
run_materialize — happy path                  test_rml_runner.py        COVERED
run_materialize — morph-kgc raises            test_rml_runner.py        COVERED (review)
run_materialize — logging suppressed          test_rml_runner.py        COVERED (review)
run_materialize — ctx mgr cleanup             test_rml_runner.py        COVERED (review)
graph_to_jsonld — typed instance              test_rml_runner.py        COVERED
graph_to_jsonld — empty graph                 test_rml_runner.py        COVERED (review)
graph_to_jsonld — context_output write        test_rml_runner.py        COVERED (review)
graph_to_jsonld — serialize wrapped error     test_rml_runner.py        COVERED (review)
CLI: --run without --data                     test_yarrrml_gen.py       COVERED
CLI: morph-kgc error → exit 1                 test_yarrrml_gen.py       COVERED
CLI: happy path stdout JSON-LD                test_yarrrml_gen.py       COVERED
CLI: --jsonld-output writes file              test_yarrrml_gen.py       COVERED
CLI: --jsonld-output OSError                  test_yarrrml_gen.py       COVERED (review)
CLI: --workdir supplied (kept)                test_yarrrml_gen.py       COVERED (review)
CLI: --workdir non-writable                   test_yarrrml_gen.py       COVERED (review)
CLI: --context-output writes file             test_yarrrml_gen.py       COVERED (review)
CLI: --run + --output both                    test_yarrrml_gen.py       COVERED (review)
CLI: empty graph → stderr warn + exit 0       test_yarrrml_gen.py       COVERED (review)
CLI: non-run path unchanged                   test_yarrrml_gen.py       COVERED
E2E: NOR CSV → JSON-LD exit 0 typed           test_yarrrml_run_e2e.py   COVERED (slow)
E2E: unit-converted field approx              test_yarrrml_run_e2e.py   COVERED (slow)
E2E: csv_cols ⊆ schema_slots precondition     test_yarrrml_run_e2e.py   COVERED (review, slow)
Fork drift: $(DATA_FILE) placeholder          test_yarrrml_compile_     COVERED (review)
                                               integration.py
```

All codepaths covered. Fast test count impact: ~+5 over original plan (empty graph, @context missing, --workdir probe, --context-output, OSError paths).

## What already exists (leveraged)

- `test_yarrrml_compile_integration.py` — already exercises `YarrrmlCompiler` in-process from rosetta-cli. Extended with `$(DATA_FILE)` placeholder assertion.
- `rosetta/core/accredit.py` — audit log seeding helpers used by both the existing Task 5 fast CLI tests and Task 6 E2E.
- `click.testing.CliRunner` — existing test harness pattern from `test_yarrrml_gen.py` and `test_lint.py`.
- `_resolve_schema_path` + `_ROSETTA_CWD` pattern (Phase 16-02 portable-cwd learning) — reused verbatim in Task 6.

## Dream state delta (12-month)

Where this plan leaves us vs. the ideal:

**Shipped:** End-to-end pipeline (SSSOM → JSON-LD) executable from a single CLI invocation, in-process, with coverage reports, error handling, and E2E validation. Master ontology drives the JSON-LD shape.

**Gaps (acknowledged, deferred):**
- No streaming materialization — bounded by `morph_kgc.materialize()`'s in-memory model.
- No multi-source data binding — single `--data` file only.
- No JSON-LD `@frame` output — context-compaction only.
- No Python-UDF unit conversion — linear GREL only (per 16-02).
- No cached `ContextGenerator` output — re-parses master schema per `--run` invocation.

Each gap is documented in `CONTEXT.md` "Deferred Ideas" with a trigger condition (e.g., "revisit if deployment workloads push past ~100k triples").

## Unresolved decisions

None.

## Diagrams produced

1. Failure Modes Registry (above)
2. Test Coverage Diagram (above)

Data-flow diagram and error-flow diagram live in SPEC.md §3 and §5 respectively.

## Cross-session outputs

**[plan-review-output]** Phase 16 Plan 03: Mode=HOLD. New truths: 17. Decisions added: 3 (tempdir ctx-mgr / empty-graph warn+0 / E2E approx). Gate: PASS (with hardening integrated). Critical findings: constructor signature, morph-kgc logging, atexit+CliRunner, unrescued jsonld-output write, `@context` fallback, empty-graph silent success, run_materialize-raises unit gap — all resolved via `[review]` truths.

**[plan-review-learning]** rosetta-cli testing: `atexit.register(shutil.rmtree, …)` does NOT fire per-test inside `click.testing.CliRunner` — handlers only run on interpreter exit. Use context managers for per-invocation cleanup instead. Rationale: every `--run` CLI test would leak `/tmp/rosetta-yarrrml-*` dirs across the whole pytest session.

**[plan-review-learning]** rosetta-cli Unix composability: third-party libs (morph-kgc, likely others) emit INFO logs to stdout by default; must suppress via `logging.getLogger(name).setLevel(WARNING)` before any stdout-is-the-payload CLI path. Rationale: without suppression, `cli --run | jq .` breaks because JSON-LD is interleaved with progress logs.

**[plan-review-learning]** rosetta-cli fork contracts: cross-repo placeholder strings (e.g., `$(DATA_FILE)` emitted by forked `YarrrmlCompiler`, consumed by rosetta-cli runner) should be defined as module-level constants and asserted in fast CI, not just E2E. Rationale: fork rebases silently change emitted template strings; fast-CI assertion catches drift before slow E2E runs.
