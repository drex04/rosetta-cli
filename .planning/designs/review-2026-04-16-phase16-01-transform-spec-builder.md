---
review_date: 2026-04-16
plan: 16-01
plan_title: "SSSOM → linkml-map TransformSpec builder"
mode: HOLD
gate: PASS_WITH_CHANGES
reviewers: fh:code-reviewer (business + engineering, parallel)
pre_validated_by: plan-check (F1–F8 applied 2026-04-16 before review)
---

# Plan 16-01 — Plan Review Summary

Human-reference audit trail. Findings persisted as `[review]` truths in `.planning/phases/16-rml-gen-v2/16-01-PLAN.md`; cross-phase contracts in `CONTEXT.md`. Follow-on ingest annotation task added to Plan 16-00 as Task 7.

## Mode selected
**HOLD.** Plan is large (9 tasks, new module + new CLI + model changes + fixtures) but was pre-validated by plan-check with F1–F8 already applied. Redistribution would require rewriting the phase split from the design doc. Reducing CoverageReport or expanding with `--dry-run` both rejected — scope is correctly sized.

## Completion summary

| Dimension | Result |
|-----------|--------|
| Mode | HOLD |
| System audit | 1 ambiguity (test-file rename), 1 field gap (SSSOMRow prereq), 1 contradiction (GA4 vs Task 3/5), 1 unverified dep (linkml-map PyPI), 1 dead coverage field |
| Step 0 | HOLD locked; 3 follow-up decisions locked |
| Section 1 (Scope) | WARNING — 16-02 per-slot path annotation contract unspecified; CLOSED by locking key names in CONTEXT.md + 16-00 Task 7 |
| Section 2 (Errors) | 11 methods registered; 3 unrescued paths (schema load variants) → wrapped in CLI try/except |
| Section 3 (Security) | 0 High; yaml_loader wrapped to prevent traceback leakage |
| Section 4 (Data/UX) | GA4 contradiction was the critical gap; resolved by implementing annotation-read hybrid |
| Section 5 (Tests) | Test diagram produced; 4 gaps identified (`unmapped_required_master_slots` missing code path was the worst) |
| Section 6 (Future) | Reversibility: 5/5 (no data writes beyond audit log); debt items: 0 |
| Section 7 (Eng Arch) | `_owning_class` O(N×M) rewritten to pre-built index; `_ClassifyContext` dataclass threads indices through |
| Section 8 (Code Qual) | 0 DRY violations; F5 helper factoring verified sufficient |
| Section 9 (Eng Test) | Added 6 new tests: `unmapped_required_master_slots`, `coverage_datatype_warnings`, `source_format` annotation fallback, `source_format` exit-1, stdout mode, malformed-source-schema error path |
| Section 10 (Perf) | 1 issue fixed (slot-owner index); otherwise OK at CLI scale |
| PLAN.md updated | 11 `[review]` truths added, 4 follow-on prerequisites, 1 artifact updated |
| CONTEXT.md updated | 10 decisions locked under "From plan-review"; 4 items deferred; GA4 revised in-place |
| Plan 16-00 updated | 2 `[review from 16-01]` truths + new Task 7 (ingest annotation stamping) |
| Error/rescue registry | 11 methods mapped; 0 remaining CRITICAL GAPs |
| Failure modes | GA4 contradiction + dead coverage field were critical; both closed |
| Diagrams | Test coverage diagram + error/rescue registry |

## Key decisions

1. **GA4 contradiction resolved — implement annotation read.** `--source-format` becomes optional at the CLI; when absent, `rosetta-yarrrml-gen` reads `annotations.rosetta_source_format` from the source schema. Exit 1 with documented message if neither present. Cascading: `rosetta-ingest` now stamps this annotation (Plan 16-00 Task 7).

2. **`unmapped_required_master_slots` populated.** `_assemble_class_derivations` now takes `master_view` and computes `{required master slots on target class} − {resolved slot derivations}` per class-mapping. New dedicated test.

3. **16-02 cross-phase contract locked.** Annotation keys for per-slot source paths: `rosetta_jsonpath` (JSON), `rosetta_xpath` (XML/XSD), `rosetta_csv_column` (CSV/TSV). `rosetta-ingest` stamps these (16-00 Task 7). `YarrrmlCompiler` (16-02) reads them from the source schema at compile time. 16-01 passes the schemas through unchanged.

4. **Hard prerequisite check.** Test file's module-level `_verify_sssomrow_shape()` asserts `SSSOMRow` has all four composite fields at import time — CI fails loudly if 16-00 regressed.

5. **linkml-map pre-flight.** Task 1 gains a "step 0" that verifies `uv add linkml-map` + the required imports resolve in a scratch venv BEFORE any pyproject edits. Prevents the 9-task domino of import failures if the package moved or renamed.

6. **Test-file rename disambiguated.** `git mv test_rml_gen.py test_yarrrml_gen.py` is explicitly followed by a body overwrite in the same commit — prevents pytest from breaking between Task 3 and Task 6.

7. **Slot-owner index.** `_build_slot_owner_index(view)` computes `slot_name → owning_class` once per SchemaView; passed via `_ClassifyContext` to `classify_row`. Replaces O(classes × slots) `class_induced_slots` per call.

8. **CLI error handling tightened.** Schema loads wrapped in `try/except (FileNotFoundError, OSError, yaml.YAMLError, Exception)` → `click.echo(f"Error: {exc}", err=True); sys.exit(1)`.

9. **Doc-sweep coverage expanded.** Task 9 adds `.planning/REQUIREMENTS.md`, `.planning/DECISIONS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md` to the `rml_gen` → `yarrrml_gen` rename list.

## Test Coverage Diagram

```
CODEPATH                                                          | TEST
------------------------------------------------------------------|----------------------
filter_rows: prefix / predicate / owl:differentFrom / HC / MMC     | Task 6 ×5
classify_row: class→class / slot→slot / unresolved / mixed-kind    | Task 6 ×4
group_composites + build_composite (consistent / multi-target)     | Task 6 ×3
build_spec: round-trip / list container / force semantics          | Task 6 ×4
build_spec F7 missing-class + composite-only owner                 | Task 6 ×2
build_spec datatype_warning / composite-expr flow                   | Task 6 ×2
[review] build_spec unmapped_required_master_slots populated        | Task 6 (new)
[review] build_spec coverage.datatype_warnings populated            | Task 6 (new)
[review] spec.comments carries effective source_format              | Task 6 (new)
CLI: happy / unresolvable / empty / allow-empty / include-manual   | Task 8 ×5
CLI: filters by source prefix                                       | Task 8
[review] CLI source_format falls back to schema annotation          | Task 8 (new)
[review] CLI exits 1 when neither flag nor annotation               | Task 8 (new)
[review] CLI stdout mode when --output omitted                      | Task 8 (new)
[review] CLI malformed source schema exits 1 cleanly                | Task 8 (new)
[review] CLI missing master schema exits 1 cleanly                  | Task 8 (new)
```

## Error & Rescue Registry

| METHOD | ERROR TYPE | RESCUED? | TEST? | USER SEES | LOGGED |
|--------|-----------|----------|-------|-----------|--------|
| classify_row — unresolved subject/object | `_Unresolved` returned | Yes | Task 6 | coverage + exit 1 | coverage.unresolved_* |
| classify_row — mixed kind | `_Unresolved(side='mixed')` → ValueError | Yes | Task 6 | exit 1 | — |
| build_composite — inconsistent expr | `ValueError` | Yes, CLI try/except | Task 6 | exit 1 | — |
| build_composite — multi-target | `ValueError` | Yes | Task 6 | exit 1 | — |
| build_spec — missing class mapping (F7) | `ValueError` | Yes | Task 6 | exit 1 | — |
| CLI — build_spec ValueError | try/except | Yes | Task 8 | exit 1 | — |
| CLI — yaml_loader (source) [review] | try/except (FileNotFound, OSError, YAMLError, Exception) | Yes | Task 8 (new) | exit 1 | — |
| CLI — yaml_loader (master) [review] | try/except | Yes | Task 8 (new) | exit 1 | — |
| CLI — _resolve_source_format missing both [review] | explicit exit 1 | Yes | Task 8 (new) | exit 1 | — |
| parse_sssom_tsv — absent | returns `[]` existing | Yes (indirect) | existing | triggers empty-filtered path | — |
| SchemaView construction — cyclic is_a | likely wrapped in schema-load try/except via bottom Exception | Yes (via catch-all) | implicit | exit 1 | — |

## What already exists that partially solved this

- `rosetta/core/accredit.py::parse_sssom_tsv` is the SSSOM reader — reused verbatim.
- `rosetta/core/models.py` Pydantic pattern — new `CoverageReport` follows the existing convention.
- `rosetta/cli/lint.py` error handling style — referenced as the parity target for CLI error handling.
- Plan-check had already applied F1–F8 before this review began; review confirmed F1–F8 fixes are correctly integrated and did not re-litigate them.

## Dream-state delta

Relative to a 12-month ideal where SSSOM audit logs drive a fully-material RDF knowledge graph: 16-01 delivers the data-format-agnostic half of that pipeline. What remains: 16-02 (YARRRML emission), 16-03 (morph-kgc execution + JSON-LD framing). The 16-02 cross-phase contract locked during this review is load-bearing for that follow-on work.

## Unresolved decisions

None. All three AskUserQuestion answers received (GA4 resolution, CoverageReport field, 16-02 contract); no silent defaults.

---

## Second-Pass Review (2026-04-16, post-16-00-merge)

**Reviewer:** orchestrator (compressed inline review — first-pass plan-checker had already done deep validation; F1-F8 already patched into PLAN.md lines 114-120).

**Trigger:** User invoked `/fh:plan-review 16-01` after 16-00 shipped (commit `52e4999`). Goal: verify 16-00 contracts now match 16-01 prerequisites and surface any residual edges.

### Verified

- **linkml-map pre-flight (Task 1 step 0)** — ran live in scratch venv: `TransformationSpecification, ClassDerivation, SlotDerivation, UnitConversionConfiguration` all import. `linkml_map.__version__` is missing (use `uv pip show` instead).
- **16-00 prerequisites all satisfied** — SSSOMRow has the four composite fields, audit log = 13 cols, `rosetta-ingest` stamps source-format + per-slot path annotations.
- **`MappingDecision` consumer enumeration** — confirmed limited to `cli/rml_gen.py`, `core/rml_builder.py`, `core/models.py:147`, `tests/test_rml_gen.py`. All deleted/stubbed by Tasks 2 + 3. No dead-import gotcha (unlike Phase 14's `similarity.py` precedent).
- **Mid-build pytest safety** — Task 3 step 2a addresses the rename gotcha (overwrites `test_yarrrml_gen.py` body in same commit as `git mv`).

### Warnings added (4)

1. **W1 — `CoverageReport` lacks `extra="forbid"`** (Task 2). Same gotcha as SSSOMRow in 16-00. Truth + decision added.
2. **W2 — `linkml-map` version pin is hand-wavy** (Task 1 step 1). `__version__` attr missing — must use `uv pip show`. Truth + decision added.
3. **W3 — Task 4 is 424 lines, too big for one subagent**. Wave map: 4a (removed) | (4b ∥ 4c) → 4d → 4e → 4f. Truth + decision added.
4. **W4 — No explicit wave annotations**. Wave order must put T7 fixtures before T6+T8 tests. Truth + decision added.

### No CRITICAL gaps.

### Buildable now? YES.

Apply W1-W4 truths to PLAN.md (done) and W1-W4 decisions to CONTEXT.md (done), then proceed to `/fh:build`.

### Updated Completion Summary

```
+====================================================================+
|       PLAN 16-01 SECOND-PASS REVIEW — COMPLETION SUMMARY           |
+====================================================================+
| Mode selected        | HOLD SCOPE (unchanged from first pass)      |
| Pre-flight (Task 1)  | linkml-map imports resolve — PASS           |
| Critical gaps        | 0                                           |
| Warnings added       | 4 (W1-W4)                                   |
| PLAN.md truths added | 4 (with [plan-review-2] prefix)             |
| CONTEXT.md decisions | 6 (4 W1-W4 + 2 verification confirmations)  |
| Plan size            | 985 lines (was 981)                         |
| Buildable now?       | YES                                         |
| Gate                 | PASS_WITH_CHANGES (W1-W4 applied)           |
+====================================================================+
```
