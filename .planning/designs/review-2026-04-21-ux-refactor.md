# Plan Review — Phase 20 UX Refactor

**Date:** 2026-04-21
**Mode:** HOLD SCOPE
**Plans reviewed:** 20-01, 20-02, 20-03, 20-04

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | No prior learnings; codebase fresh           |
| Step 0               | HOLD — pure refactor, maximize rigor         |
+--------------------------------------------------------------------+
| Section 1  (Scope)   | 1 WARNING — 20-01 truth listed compile/run   |
|                      | before they exist (FIXED)                     |
| Section 2  (Users)   | 1 WARNING — --audit-log exists=True is        |
|                      | confusing for new users (FIXED → manual       |
|                      | validation)                                   |
| Section 3  (UX)      | 2 WARNINGs — -v/-q parent group positioning;  |
|                      | accredit group flag ordering (NOTED in help)  |
| Section 4  (Risk)    | 1 CRITICAL — pipeline-demo.sh breakage        |
|                      | window (FIXED → holding fix in 20-01)         |
| Section 5  (Deps)    | 1 CRITICAL — Task 5 ordering                  |
|                      | delete-before-migrate (FIXED → migrate first) |
| Section 6  (Complete) | 1 CRITICAL — design doc said TransformSpec,   |
|                      | plan said YARRRML (FIXED → YARRRML)           |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 3 findings: lazy imports (DECIDED: lazy),      |
|                      | stale --force messages (FIXED), open_output   |
|                      | reuse confirmed OK                             |
| Section 8  (Tests)   | 3 findings: combined-flow test rewrites,       |
|                      | exit code 2 flip, config fallback test gap     |
|                      | (ALL FIXED as review truths)                   |
| Section 9  (Perf)    | 2 findings: lazy imports (DECIDED),            |
|                      | spec.comments propagation (TEST ADDED)         |
| Section 10 (Security)| 3 findings: SIGPIPE portability (FIXED →       |
|                      | BrokenPipeError), exit code audit (ADDED),     |
|                      | provenance deletion accepted                   |
+--------------------------------------------------------------------+
| PLAN.md updated      | 11 truths added, 0 artifacts added             |
| CONTEXT.md updated   | 6 decisions locked, 2 items deferred           |
| Failure modes        | 3 CRITICAL GAPS → all resolved in PLAN.md      |
| Diagrams produced    | 1 (test coverage ASCII)                        |
| Unresolved decisions | 0                                              |
+====================================================================+
```

## Key Decisions Made

1. **D-20-16:** compile outputs YARRRML (not TransformSpec). --spec-output for intermediate.
2. **D-20-17:** Lazy imports via importlib.import_module for all subcommands.
3. **D-20-18:** pipeline-demo.sh holding fix in Plan 20-01 prevents inter-plan breakage.
4. **D-20-19:** --audit-log uses click.Path() without exists=True; manual validation with clear error.
5. **D-20-20:** transform_builder.py --force error messages updated in Plan 20-02.
6. **D-20-21:** SIGPIPE via BrokenPipeError try/except (portable).

## Deferred

- Verbose/quiet wiring into subcommand stderr output (flags accepted, not consumed)
- Dead `force`/`include_manual` parameters on `build_spec()` signature

## Test Coverage Diagram

```
PLAN 20-02: compile.py / run.py split
  compile.py
  +-- SSSOM -> TransformSpec           [COVERED: migrated tests]
  +-- TransformSpec -> YARRRML         [COVERED: migrated tests]
  +-- source_format annotation         [NEW TEST: review truth]
  +-- --spec-output                    [NEW TEST: needed]
  +-- coverage-report                  [COVERED: migrated tests]

  run.py
  +-- YARRRML + data -> JSON-LD        [COVERED: migrated tests]
  +-- --validate <shapes-dir>          [COVERED: migrated tests]
  +-- stdout-collision guard           [COVERED: ported from yarrrml_gen]
  +-- missing SOURCE_FILE -> exit 2    [REWRITE: was exit 1]
  +-- --workdir writability            [COVERED: migrated tests]

PLAN 20-03: option changes
  suggest --audit-log required         [COVERED: updated tests]
  suggest audit-log config fallback    [NEW TEST: review truth]
  lint positional + required flags     [COVERED: updated tests]
  validate JSON-LD only                [COVERED: updated tests]
```
