---
plan: 19-03
title: --validate wiring + JSON-LD input for rosetta-validate
status: complete
completed: 2026-04-19
test_metrics:
  total: 457
  pass: 457
  new_tests: 11   # 4 test_validate + 2 integration + 5 adversarial
quality_gates: all 9 pass
---

# Plan 19-03 — Build Summary

## Implemented

| Task | Status | Key files |
|---|---|---|
| T1 — Shared `shacl_validate.py` helper | ✅ | `rosetta/core/shacl_validate.py` (new) |
| T2 — `validate.py` refactor + JSON-LD input | ✅ | `rosetta/cli/validate.py` modified; `--data-format` flag; `_resolve_data_format` helper |
| T3 — `yarrrml-gen --validate` wiring + step-0 stdout-collision guard | ✅ | `rosetta/cli/yarrrml_gen.py` modified; 3 new flags; collision guard for all 3 stdout pairs |
| T4 — Tests | ✅ | `test_validate.py` +4; `test_yarrrml_validate_pipeline.py` (new, 2); `test_yarrrml_validate_misuse.py` (new, 5) |
| T5 — Documentation | ✅ | `docs/cli/validate.md`, `docs/cli/yarrrml-gen.md`, `README.md` |
| T6 — Quality gates | ✅ | All 9 mandatory checks pass |

## Truth verification (must_haves)

| Truth | Evidence |
|---|---|
| 1. `validate_graph` shared helper used by both CLIs | T1 created module; T2 + T3 both call `from rosetta.core.shacl_validate import validate_graph`. `git grep "pyshacl.validate"` returns just one site (the helper). |
| 2. `rosetta-validate` accepts JSON-LD `--data` | T4 `test_validate_jsonld_input_autodetect` + `test_validate_json_input_autodetect` + `test_validate_data_format_override` |
| 3. `--validate` happy path emits JSON-LD on conformance | T4 `test_yarrrml_run_validate_happy_path` |
| 4. `--validate` violation blocks JSON-LD emission, exit 1 | T4 `test_yarrrml_run_validate_violation_blocks_emission` + `test_validate_no_partial_jsonld_on_violation` |
| 5. `--validate` without `--shapes-dir` → UsageError | T4 `test_validate_without_shapes_dir_errors` |
| 6. **[review-harden]** Stdout-collision guard for all 3 pairs | T4 `test_stdout_collision_output_validate_report` + `test_stdout_collision_jsonld_validate_report` (existing `test_yarrrml_gen_stdout_and_file_collision` covers the third pair) |

## Fix-on-Sight

- **Phase 18 adversarial test broke** when Task 3 unified the stdout-collision guard onto `click.UsageError` (exit 2). Previously it used `sys.exit(1)`. Updated `test_yarrrml_gen_stdout_and_file_collision` in `test_cli_misuse.py` from `exit_code == 1` → `== 2`. Real fix; tests now pin the unified behavior.
- **Missing pytest marker**: `pytest.mark.adversarial` was used in fixtures but not declared in `pyproject.toml`. Added to `[tool.pytest.ini_options].markers`.

## Concerns

- **Integration tests marked `slow`:** `test_yarrrml_validate_pipeline.py` exercises the full SSSOM → YARRRML → morph-kgc → SHACL chain (~7s each). Marked `slow` consistent with existing `test_yarrrml_compile_integration.py` convention. They run in `-m slow` / `-m e2e` jobs, not the fast PR gate. If desired, dropping the `slow` marker would add ~14s to fast-gate.

## Cross-session output

**[plan-build-output]** Phase 19 Plan 19-03: COMPLETE. 457/457 tests (+11). New module: `rosetta/core/shacl_validate.py` (shared helper). `rosetta-validate` accepts JSON-LD via `--data-format`. `rosetta-yarrrml-gen --validate --shapes-dir --validate-report` validates in-memory graph against SHACL before JSON-LD emission; blocks emission + exits 1 on violation. All 3 stdout-collision pairs guarded at step 0. **Phase 19 complete.**
