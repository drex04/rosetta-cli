# Plan Review — Phase 19 (SHACL validation refactor)

**Date:** 2026-04-19
**Mode:** HOLD (rigor on locked scope)
**Plans reviewed:** 19-01, 19-02, 19-03
**Compression:** SMALL CHANGE Mode (3 plans, ~17 tasks; single batched-findings round)
**Gate:** PASS (3 issues raised + resolved → `[review]` truths in PLAN.md)

## System audit findings

| # | Finding | Action |
|---|---|---|
| A1 | `ShaclGenerator.closed` is a public attribute — subclass may be over-spec'd | → Issue 3 (spike sub-step) |
| A2 | `detect_unit` recognizes only `hasAltitudeM` from 6 sampled master slots | → Issue 2 (extend detect_unit) |
| A3 | `mapping.shacl.ttl` referenced by `test_validate.py` (generic SHACL fixture, not v1 vocab) | → Issue 1 (inline shapes in test) |
| A4 | `rdflib 7.2.1` + `rdflib-jsonld 0.6.1` installed — JSON-LD input is no-new-deps | ✓ confirmed Plan 19-03 risk note |
| A5 | `run_materialize` yields a single `rdflib.Graph` as Plan 19-03 assumes | ✓ confirmed |
| A6 | No prior `shacl_validate.py` / `shacl_generator.py` / `cli/shacl_gen.py` exists | ✓ clean slate |

## Issues + resolutions

### Issue 1 — `mapping.shacl.ttl` deletion breaks `test_validate.py`
**Severity:** WARNING (would break build during 19-02 Task 5 verification)
**User chose:** **1B** — inline `_SHAPES_TTL` string in the test module, decouple from policies dir.
**Applied to:** Plan 19-02 Task 1 (added sub-step 1.5); Truth #7 added with `[review]` prefix; artifact `rosetta/tests/test_validate.py` added.

### Issue 2 — Unit-aware shapes deliver value on ~1/6 master slots
**Severity:** WARNING (Truth #5 technically met but with thin coverage)
**User chose:** **2C** — expand Plan 19-01 to extend `detect_unit` for `Knots` / `Bearing`/`Degrees` / `VerticalRate` + fpm.
**Applied to:** Plan 19-01 Task 0 added; Truth #6 added with `[review]` prefix; artifacts `rosetta/core/unit_detect.py` + `rosetta/tests/test_unit_detect.py` added.

### Issue 3 — `RosettaShaclGenerator` may be over-engineered
**Severity:** OK (style nitpick → preventive spike)
**User chose:** **3A** — keep plan + add ≤30-min spike sub-step to Task 1.
**Applied to:** Plan 19-01 Task 1 sub-step 1.0 added; module-docstring requirement added.

## Failure Modes Registry (Phase 19 cross-plan)

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES? | LOGGED? |
|---|---|---|---|---|---|
| `rosetta-shacl-gen` malformed master schema | LinkML parse error | Y (Click try/except → exit 1) | Y (test_shacl_gen Task 4) | Stderr "Error: ..." | Stderr |
| `rosetta-shacl-gen` schema with no slots | Empty SHACL output | N (silent — empty file written) | N | Empty `.ttl` file | No |
| `--shapes-dir` empty after rglob | UsageError | Y (existing guard) | Y (existing test) | Click message | Stderr |
| `--shapes-dir` walks symlink loop | infinite recursion | N | N | Hang | No |
| `--validate` + materialized graph empty | `pyshacl` returns `conforms=True` (vacuously) | N | N | JSON-LD emitted (likely also empty per existing warning at L284 in `rml_runner.py`) | Stderr warning (existing) |
| `--validate-report -` collides with `--output -` / `--jsonld-output -` | stdout corruption | N (Plan 19-03 notes risk in "Risks" but doesn't add an early-guard task) | N | Garbled stdout | No |
| JSON-LD input with malformed `@context` | `rdflib.plugins.parsers.notation3.BadSyntax` (or similar) | Y (Click try/except → exit 1) | Y (Plan 19-03 Task 4) | Stderr "Error: ..." | Stderr |
| `--shapes-dir` walks subdir containing non-shape Turtle (e.g., ontology TTL by mistake) | All triples loaded into shapes graph; non-shape triples are inert; no error | N (silent) | N | Possibly correct validation, possibly extra noise | No |

**CRITICAL GAPs (all hardened in plan, per user directive 2026-04-19 "harden now"):**
- ✅ `--validate-report -` stdout collision → Plan 19-03 Task 3 step-0 guard + 3 adversarial tests (D-19-15, Truth #6 `[review-harden]`).
- ✅ `--shapes-dir` symlink-loop → Plan 19-02 Task 4 uses `os.walk(followlinks=False)` via shared `shapes_loader` (D-19-16, Truth #8 `[review-harden]`).
- ✅ Non-shape Turtle silently absorbed → Plan 19-02 Task 4 emits stderr warning per file (warn-and-merge policy, D-19-17, Truth #9 `[review-harden]`).

No deferred items.

## Diagrams

### Phase 19 data flow (happy path)

```
master.linkml.yaml ──┐
                     │
              ┌──────▼─────────┐
              │ rosetta-shacl- │  Plan 19-01
              │ gen (Task 0–6) │
              └──────┬─────────┘
                     │ master.shacl.ttl
                     ▼
       rosetta/policies/shacl/generated/master.shacl.ttl
                     +
       rosetta/policies/shacl/overrides/track_bearing_range.ttl  (Plan 19-02)
                     │
                     │ --shapes-dir (rglob, sorted)
                     ▼
   ┌─────────────────────────────────────────────────┐
   │ rosetta/core/shacl_validate.validate_graph     │  Plan 19-03 Task 1
   │   (data_g, shapes_g) -> ValidationReport       │
   └────────────┬────────────────────────────┬──────┘
                │                            │
       ┌────────▼─────────┐         ┌────────▼────────────────┐
       │ rosetta-validate │         │ rosetta-yarrrml-gen     │
       │  (CLI; .ttl OR  │         │  --run --validate       │
       │  .jsonld input) │         │  (in-memory graph from  │
       │  Plan 19-03 T2  │         │  run_materialize)       │
       └─────────────────┘         │  Plan 19-03 Task 3      │
                                   └────────┬────────────────┘
                                            │
                                  conforms? │
                                  ┌─────────┴─────────┐
                                  ▼ YES               ▼ NO
                         graph_to_jsonld()    write report → stderr
                         emit JSON-LD         OR --validate-report
                         exit 0               NO JSON-LD bytes
                                              exit 1
```

### Plan execution order (sequential, no parallelization)

```
19-01 (generator) ──→ 19-02 (override workflow + cleanup) ──→ 19-03 (wiring)
       │                          │                                  │
       │                          │                                  │
       ▼                          ▼                                  ▼
detect_unit extended     master.shacl.ttl committed         shacl_validate.py
ShaclGenerator subclass  test_validate.py inlined           --validate flag
test_shacl_gen.py green  --shapes-dir → rglob               JSON-LD input parser
```

## Test coverage diagram (mandatory output)

```
Phase 19 new code paths              Test file
────────────────────────             ─────────────────────────────
detect_unit (extended)        ───→   test_unit_detect.py (4 new)
RosettaShaclGenerator         ───→   test_shacl_gen.py (6 tests)
rosetta-shacl-gen CLI         ───→   test_shacl_gen.py (smoke + fixtures)
--shapes-dir rglob            ───→   test_shacl_overrides.py (4 tests)
override survives regen       ───→   test_shacl_overrides.py test 3
shacl_validate.validate_graph ───→   test_validate.py (existing, refactored)
JSON-LD input parser          ───→   test_validate.py (4 new)
--validate happy path         ───→   test_yarrrml_validate_pipeline.py
--validate violation blocks   ───→   test_yarrrml_validate_pipeline.py
--validate without --shapes   ───→   test_yarrrml_validate_misuse.py
no partial JSON-LD invariant  ───→   test_yarrrml_validate_misuse.py
```

**Coverage gaps:** none surfaced for Phase 19 scope. Failure-mode-registry CRITICAL gaps (stdout collision, symlink loop, non-shape Turtle) are documented but not blocking.

## What already exists (reused, not rebuilt)

- `rosetta/core/io.open_output` — output file/stdout dispatcher (used by every CLI)
- `rosetta/core/models.ValidationReport` / `ValidationFinding` / `ValidationSummary` — Pydantic models from Phase 8 (still v2-compatible; reused by Plan 19-03)
- `pyshacl.validate` invocation pattern (extracted into `shacl_validate.py` in Plan 19-03)
- `rosetta.core.unit_detect.detect_unit` (extended, not replaced, in Plan 19-01 Task 0)
- `rml_runner.run_materialize` context manager (no signature change; Plan 19-03 calls `validate_graph` inside its `with` block)
- `rdflib-jsonld 0.6.1` (already installed; no new dep for JSON-LD input)

## Dream state delta

After Phase 19 ships, the v2 pipeline gains end-to-end validation: source schema → SSSOM → YARRRML → materialized graph → SHACL-validated → JSON-LD. The remaining 12-month delta:

- **Auto-regen on master schema change:** Pre-commit hook to regenerate `generated/master.shacl.ttl` when `master_cop.linkml.yaml` changes. Defer (small follow-up).
- **Cardinality + SHACL-AF rules:** LinkML annotations like `multivalued`, `required`, value sets — covered by `ShaclGenerator` baseline but not exercised. Worth a Phase-20 audit pass once master schema starts using them.
- **OWL imports / inferencing:** `pyshacl` supports `inference="rdfs"` / `"owl-rl"` — currently `inference="none"`. Phase 20+ if validation needs to walk the class hierarchy.
- **Shapes versioning:** `dcterms:created` on generated shapes so users can track which schema version produced which shapes file. Defer.

## Completion summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD (SMALL CHANGE Mode compression)         |
| System Audit         | 6 findings (3 informational, 3 → issues)     |
| Step 0               | HOLD locked; user confirmed scope            |
| Issues raised        | 3 (1 WARNING, 1 WARNING, 1 OK)               |
| Issues resolved      | 3/3 (1B, 2C, 3A)                             |
| PLAN.md updated      | 19-01: +1 truth, +2 artifacts, +1 task       |
|                      | 19-02: +3 truths, +2 artifacts, +1 sub-step, |
|                      |        +2 tests, Task 4 rewritten            |
|                      | 19-03: +1 truth, Task 3 step-0 guard + 2     |
|                      |        adversarial tests added               |
| CONTEXT.md updated   | +6 decisions: D-19-12/13/14 [review],         |
|                      |              D-19-15/16/17 [review-harden]    |
| Failure modes        | 8 mapped, 3 CRITICAL gaps — ALL hardened     |
|                      | (no deferred items per user directive)        |
| Diagrams produced    | 3 (data flow, exec order, test coverage)     |
| Unresolved decisions | 0                                             |
| Gate                 | PASS                                          |
+====================================================================+
```

## Unresolved

None. All 3 issues resolved; PLAN.md + CONTEXT.md updated.

## Recommended next action

`/fh:build` 19-01 — start sequential execution. The plan-checker pre-validation will catch any drift between the updated truths and the task list.
