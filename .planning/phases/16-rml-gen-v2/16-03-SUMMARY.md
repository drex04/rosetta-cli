---
plan: 16-03
phase: 16
title: "morph-kgc runner + JSON-LD framing + E2E"
status: complete
completed: 2026-04-17
plan_doc: 16-03-PLAN.md
spec_doc: 16-03-SPEC.md
design_doc: .planning/designs/2026-04-17-phase16-plan03-rml-runner.md
review_doc: .planning/designs/review-2026-04-17-phase16-03-rml-runner.md
---

# Plan 16-03 Summary — morph-kgc Runner + JSON-LD Framing + E2E

Closes Phase 16: the SSSOM → JSON-LD pipeline is now executable end-to-end.

## What shipped

**`rosetta/core/rml_runner.py` (new):**
- `run_materialize(yarrrml_text, data_path, work_dir)` — `@contextlib.contextmanager` yielding `rdflib.Graph`. Internally substitutes `$(DATA_FILE)`, writes `work_dir/mapping.yml`, builds INI string, calls `morph_kgc.materialize(ini)`. Suppresses morph-kgc logging before invocation. Cleans internally-created workdirs on exit; caller-supplied workdir is left alone.
- `graph_to_jsonld(graph, master_schema_path, context_output=None) -> bytes` — generates JSON-LD context via `ContextGenerator(schema).serialize()`, raises `ValueError` if parsed dict lacks `@context` key (no silent fallback), wraps `graph.serialize(format="json-ld", ...)` in `RuntimeError`. Optionally writes context JSON to `context_output`.
- Private helpers: `_substitute_data_path`, `_build_ini`, `_generate_jsonld_context`. Module constant `_DATA_FILE_PLACEHOLDER = "$(DATA_FILE)"`.

**`rosetta/cli/yarrrml_gen.py` (extended):**
- New flags: `--run`, `--data`, `--jsonld-output`, `--workdir`, `--context-output`.
- Uses `YarrrmlCompiler(source_schemaview=SchemaView(...), target_schemaview=SchemaView(...)).compile(spec)` — matches `test_yarrrml_compile_integration.py` pattern.
- `--workdir` canonicalized via `Path.resolve()` with `Path.touch()` writability probe; absent workdir delegates to `run_materialize`'s internal tempdir.
- Empty morph-kgc graph → `Warning: materialization produced 0 triples; check data file and mappings` to stderr, JSON-LD still written, exit 0.
- Output via `click.get_binary_stream("stdout").write(...)` (CliRunner-safe, platform-portable).
- All library errors wrapped → `click.echo(err=True); sys.exit(1)` — no raw tracebacks.

**Tests (`+24 fast, +1 slow`):**
- `rosetta/tests/test_rml_runner.py` (new) — 15 unit tests covering substitute/build_ini/context/materialize/framing happy + error + edge paths.
- `rosetta/tests/test_yarrrml_gen.py` (extended) — 9 new CLI tests: `--run` validation, monkeypatched happy path, `--jsonld-output`, `--workdir`, `--context-output`, empty-graph warning, stdout matrix, non-`--run` regression.
- `rosetta/tests/test_yarrrml_compile_integration.py` (extended) — `$(DATA_FILE)` placeholder assertion (fork-drift guard in fast CI).
- `rosetta/tests/test_yarrrml_run_e2e.py` (new, slow) — full NOR-CSV → JSON-LD round-trip.
- `rosetta/tests/fixtures/nor_radar_sample.csv` (new) — 3-row fixture.

**Dependencies:**
- `morph-kgc==2.10.0` pinned.

**Docs:**
- `README.md` — `rosetta-yarrrml-gen` section rewritten: synopsis with all flags, stdout matrix, worked example (NOR CSV → JSON-LD), exit codes, single-source note.

## Test metrics

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Fast (`-m "not slow"`) | 305 | 329 | +24 |
| Slow | 2 | 3 | +1 |
| Total | 307 | 332 | +25 |

All 8 mandatory quality gates green. `refurb` emits a duplicate-module warning that is pre-existing on `master@4da33be` (not introduced by this plan).

## Review truths honored (17)

All `[review]` must-have truths from the 2026-04-17 plan-review were implemented. Key hardenings:
- Constructor signature matches canonical test pattern (no TypeError at runtime).
- morph-kgc logging silenced pre-`materialize()` (stdout stays JSON-LD-only).
- Context manager for tempdir cleanup (no `atexit` + CliRunner incompatibility).
- `$(DATA_FILE)` placeholder is a module constant + asserted in fast-CI.
- `click.get_binary_stream` replaces `sys.stdout.buffer.write`.
- Enumerated exception types in SPEC §5 all caught.
- `RuntimeError` re-wrapping preserves file paths in error messages.
- Empty-graph warning + exit 0 (Unix-pipeline-friendly).

## Deviations from plan

**[Rule 1 — Bug fix during implementation]** `run_materialize` creates `work_dir` with `mkdir(parents=True, exist_ok=True)` when a caller supplies an absent path. Needed because morph-kgc's mapping.yml write fails otherwise; CLI pre-creates, but direct Python callers (tests/notebooks) should not have to. Wrapped in `RuntimeError` on failure. Does not violate any review truth.

**[Follow-up applied, 2026-04-17]** The known-gap relaxation was closed. `transform_builder` now wires `UnitConversionConfiguration` through; the fork compiler was patched to emit FnML function refs at rosetta UDF IRIs (`https://rosetta.interop/udf/meter_to_foot` etc.) with matching `grel:valueParameter` binding; `rml_runner` writes a Python UDF module into `work_dir` and passes `udfs=<path>` to morph-kgc. Master fixture now carries `hasAltitudeFt` and SSSOM r004 routes `hoyde_m → hasAltitudeFt`. E2E asserts converted numeric values with `pytest.approx(rel=1e-2)` (4100 m → ~13451 ft, etc.). Truth #3 fully satisfied end-to-end.

**[Fixture patch in test]** The nor_radar master schema fixture has `range: dateTime` (LinkML canonical is `datetime`). `ContextGenerator` rejects it; `SchemaView` tolerates. The E2E rewrites the fixture to `datetime` in `tmp_path` before invoking the CLI. Documented in the test's docstring. Upstream fixture unchanged.

## Cross-phase contracts closed

- Phase 16's `$(DATA_FILE)` placeholder contract (16-02 GA-02-4) now has a fast-CI assertion in `test_yarrrml_compile_integration.py` — fork rebase changes surface as test failures instead of runtime errors.
- TransformSpec self-describing contract (16-02: absolute `source_schema`/`target_schema` paths + pre-merged `spec.prefixes`) is exercised end-to-end by the E2E.

## Deferred items (per CONTEXT.md)

- JSON-LD `@frame` output mode
- Multi-source data binding
- Non-linear unit conversion via Python UDF
- Streaming materialization (memory ceiling noted in risk register)
- Cached `ContextGenerator` output across `--run` invocations
- `--dry-run` / `--stats` delight flags
- Upstream PR of `YarrrmlCompiler` to `linkml/linkml-map` (user-managed)
- Numeric unit conversion wiring in `transform_builder.build_slot_derivation` (blocks full satisfaction of review truth #3)

## Issues encountered

None that blocked the plan. One pre-existing refurb warning on master (duplicate `rosetta/tests/__init__.py` module) persists but is orthogonal to this work.

## What's next

Phase 16 is complete. Phase 17 (QUDT-native unit detection) is independent and can begin any time. If numeric unit conversion needs to be proven end-to-end before Phase 17 ships, a small 16-01 patch (wiring `unit_conversion` through `build_slot_derivation` from existing FnML suggestions) would close the remaining gap.
