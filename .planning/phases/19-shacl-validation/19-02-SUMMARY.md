---
plan: 19-02
title: SHACL override workflow + legacy cleanup
status: complete
completed: 2026-04-19
test_metrics:
  total: 449
  pass: 449
  new_tests: 6   # test_shacl_overrides
quality_gates: all 9 pass
---

# Plan 19-02 — Build Summary

## Implemented

| Task | Status | Key files |
|---|---|---|
| T1 — Dir scaffolding + `mapping.shacl.ttl` retirement + `test_validate.py` migration | ✅ | `rosetta/policies/shacl/{generated,overrides}/README.md`, `rosetta/tests/test_validate.py`, `README.md`, `docs/cli/validate.md`, deleted `rosetta/policies/mapping.shacl.ttl` |
| T2 — Generate `master.shacl.ttl` | ✅ | `rosetta/policies/shacl/generated/master.shacl.ttl` (130KB, 43 NodeShapes, 127 `qudt:hasUnit` paths) |
| T3 — Worked-example override | ✅ | `rosetta/policies/shacl/overrides/track_bearing_range.ttl` |
| T4 — `shapes_loader` + recursive `--shapes-dir` | ✅ | `rosetta/core/shapes_loader.py` (new); `rosetta/cli/validate.py` calls it |
| T5 — Tests | ✅ | `rosetta/tests/test_shacl_overrides.py` (6 tests) |
| T6 — Quality gates | ✅ | All 9 mandatory checks pass |

## Truth verification (must_haves)

| Truth | Evidence |
|---|---|
| 1. `generated/master.shacl.ttl` exists, parses | T2 done-criteria: 130KB, 3985 triples, 43 NodeShapes |
| 2. `overrides/` contains additive override | T3 `track_bearing_range.ttl` (1 NodeShape, range 0-360) |
| 3. Legacy `mapping.shacl.ttl` deleted; 0 grep hits | T1 verified |
| 4. Override survives regen | T5 `test_override_survives_regen` (sha256 byte-identical pre/post) |
| 5. `--shapes-dir` recursively walks both subdirs | T5 `test_shapes_dir_recursive_merge` |
| 6. Docs updated | T1 README + docs/cli/validate.md swapped |
| 7. **[review]** `test_validate.py` inlined `_SHAPES_TTL` | T1 sub-step 1.5: `shutil.copy` removed; tests still pass 9/9 |
| 8. **[review-harden]** Symlink-loop safe | T5 `test_shapes_loader_does_not_follow_symlink_loop` (creates loop, asserts no hang + no double-load) |
| 9. **[review-harden]** Non-shape Turtle warning | T5 `test_shapes_loader_warns_on_non_shape_turtle` (capsys asserts stderr + still merges) |

## Fix-on-Sight

- 1 refurb FURB184 (`runner = CliRunner(); result = runner.invoke(...)` → chained) in test_shacl_overrides.py
- 4 basedpyright errors on `report_g.objects(...)` (pyshacl returns Union; needed `isinstance(report_g, rdflib.Graph)` narrowing — same pattern as Plan 19-01 test_shacl_gen.py)

## Cross-session output

**[plan-build-output]** Phase 19 Plan 19-02: COMPLETE. 449/449 tests (+6). New module: `rosetta/core/shapes_loader.py`. Legacy `mapping.shacl.ttl` retired. Override workflow live with worked example. All hardening truths verified (symlink-safe walker + non-shape-warned).
