---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: LinkML + SSSOM migration
status: in_progress
last_updated: "2026-04-18T10:58:00.000Z"
progress:
  total_phases: 18
  completed_phases: 17
  total_plans: 21
  completed_plans: 22
---

# State

## Current Position

- **Phase:** 18 (Integration & E2E Test Hardening) in progress
- **Plan:** 18-01 (Test infrastructure foundation) complete
- **Status:** Plan 18-01 complete on 2026-04-18; 378/378 fast tests passing + 2 slow (380/381 total; 1 pre-existing e2e failure in `test_e2e_nor_radar_csv_to_jsonld` m→ft unit conversion — fork SHA drift per Phase 16-03 follow-up, unrelated to Phase 18). 8/8 quality gates clean. pytest markers `integration` + `e2e` declared; `nations/` fixture subdir live with 9 relocated fixtures; `fake_deepl` fixture proven via smoke test; CI has a new `fast-gate` job running `-m "not slow and not e2e"`. Plans 18-02 (positive-path) and 18-03 (adversarial) unblocked.

## Phase Progress

| Phase | Name | Status |
|-------|------|--------|
| 1 | Project scaffolding and core setup | Complete |
| 2 | rosetta-ingest | Complete |
| 3 | rosetta-embed + rosetta-suggest | Complete |
| 4 | rosetta-lint | Complete |
| 5 | Code quality infrastructure | Complete |
| 6 | rosetta-rml-gen | Complete |
| 7 | rosetta-provenance | Complete |
| 8 | rosetta-validate | Complete |
| 9 | rosetta-accredit + feedback loop | Complete |
| 10 | rosetta-translate | Complete |
| 11 | rosetta-ingest extensions (XSD + JSON sample) | Complete |
| 12 | Schema Normalization (LinkML + schema-automator) | Complete |
| 13 | Semantic Matching (embed + suggest → SSSOM) | Complete |
| 14 | User Review (approve/reject → approved SSSOM) | Complete |
| 15 | rosetta-lint SSSOM enrichment | Complete |
| 16 | rml-gen v2 (SSSOM → YARRRML → JSON-LD) | Complete |
| 17 | QUDT-native unit detection (quantulum3 + pint) | Complete |
| 18 | Integration & E2E Test Hardening | In progress (1/3 plans) |

## Phase 1 Completion

- **Commit:** c5ea044
- **Tests:** 12/12 passing
- **Completed:** 2026-04-12

## Phase 3 Plan 01 Completion

- **Commit:** 7f0dea1
- **Tests:** 40/40 passing (8 new embed tests, 1 slow deselected)
- **Completed:** 2026-04-12

## Phase 3 Plan 02 Completion

- **Commit:** 5acccf0
- **Tests:** 63/63 passing (19 new suggest tests)
- **Completed:** 2026-04-12

## Phase 4 Plan 01 Completion

- **Commit:** 20a804c
- **Tests:** 91/91 passing (27 new lint tests)
- **Completed:** 2026-04-13

## Phase 5 Plan 01 Completion

- **Commit:** 31b8a96
- **Tests:** 111/111 passing
- **Completed:** 2026-04-13

## Phase 5 Plan 02 Completion

- **Commit:** ae3f612
- **Tests:** 122/122 passing (11 new model tests)
- **Completed:** 2026-04-13

## Phase 8 Plan 01 Completion

- **Commit:** ffe2e14 (pre-existing)
- **Tests:** 9/9 validate tests passing; 165/165 total
- **Completed:** 2026-04-13

## Phase 9 Plan 02 Completion

- **Commit:** ffe2e14 (pre-existing — all artifacts already committed)
- **Tests:** 7/7 integration tests passing; 165/165 total
- **Completed:** 2026-04-13

## Phase 6 Plan 01 Completion

- **Commit:** 4e76f65 (pre-existing — all artifacts already committed)
- **Tests:** 9/9 rml-gen tests passing; 175/175 total
- **Completed:** 2026-04-13

## Phases 7, 10, 11 Completion

- **Tests:** 203/203 passing (38 new tests across phases 6–11)
- **Completed:** 2026-04-13

## Phase 12 Plan 01 Completion

- **Commit:** b002a57
- **Tests:** 166/166 passing (20 new tests; 48 v1 parser tests removed)
- **Completed:** 2026-04-14
- **Key changes:** LinkML-based ingest pipeline, normalize.py (7 formats), translate/embed rewritten for YAML I/O

## Phase 13 Plan 01 Completion

- **Commit:** 9d63eb8
- **Tests:** 166/166 passing
- **Completed:** 2026-04-14
- **Key changes:** linkml 1.10.0 upgrade, monkey-patch removed, SSSOM TSV output for rosetta-suggest, apply_sssom_feedback, SSSOMRow model, --approved-mappings flag

## Phase 13 Plan 02 Completion

- **Commit:** cbdd2dd
- **Tests:** 177/177 passing (+11 new)
- **Completed:** 2026-04-15
- **Key changes:** features.py (structural feature extraction), EmbeddingVectors.structural field, embed populates structural, rank_suggestions blends lexical+structural, suggest CLI wires structural_weight from rosetta.toml

## Phase 14 Plan 01 Completion

- **Plan:** `.planning/phases/14-user-review/14-01-PLAN.md`
- **Status:** Complete
- **Key changes:** Audit-log accreditation pipeline — append-only SSSOM log replaces ledger.json; accredit CLI (ingest/review/status/dump); suggest auto-reads log for boost/derank; lint --sssom mode; SSSOMRow.mapping_date + record_id fields added

## Phase 15 Plan 01 Completion

- **Plan:** `.planning/phases/15-lint-sssom/15-01-PLAN.md`
- **Commit:** a78d5ca
- **Tests:** 253/253 passing (12 new SSSOM unit/datatype tests; 17 RDF-mode tests removed)
- **Completed:** 2026-04-15
- **Key changes:** RDF lint mode removed; rosetta-lint now SSSOM-only; unit/datatype compatibility checks via QUDT; datatype propagates LinkML slot.range → embed → suggest → lint; 11-column SSSOM TSV; DATETIME_MIN public rename

## Phase 16 Plan 00 Completion

- **Plan:** `.planning/phases/16-rml-gen-v2/16-00-PLAN.md`
- **Commit:** 52e4999
- **Tests:** 266/266 passing (12 new tests across 4 files)
- **Completed:** 2026-04-16
- **Key changes:** SSSOMRow +4 composite-entity fields (subject_type, object_type, mapping_group_id, composition_expr); suggest TSV 11→15 cols; audit log 9→13 cols with atomic migration of pre-16-00 9-col files via `_migrate_audit_log_if_needed`; `check_prefix_collision` in rosetta-ingest; `rosetta-ingest` stamps `annotations.rosetta_source_format` + per-slot path annotations (`rosetta_csv_column`/`rosetta_jsonpath`/`rosetta_xpath`) for downstream consumption by Plan 16-01.

## Phase 16 Plan 01 Completion

- **Plan:** `.planning/phases/16-rml-gen-v2/16-01-PLAN.md`
- **Tests:** 294/294 passing (37 new yarrrml-gen tests; 9 old rml-gen tests removed)
- **Completed:** 2026-04-16
- **Key changes:** `rosetta-rml-gen` → `rosetta-yarrrml-gen` (entry point + all docs); legacy `rml_builder.py` + `rml_gen.py` deleted; new `transform_builder.py` (filter/classify/compose/derive/orchestrate) + `yarrrml_gen.py` CLI; `CoverageReport` Pydantic model (replaces `MappingDecision`) with `extra="forbid"`; `linkml-map 0.5.2` + `curies 0.13.3` pinned; GA4 hybrid source-format resolution (CLI flag OR schema annotation); 13-col SSSOM → linkml-map `TransformationSpecification` round-trips through `model_validate`; composite mappings (`mapping_group_id` + `composition_expr`) flow to `SlotDerivation.expr`; `--force` bypasses unresolvable CURIEs only — mixed-kind / missing-class / inconsistent-composite always fatal.

## Phase 16 Plan 02 Completion

- **Plan:** `.planning/phases/16-rml-gen-v2/16-02-PLAN.md`
- **Commit:** 9a8ee53
- **Fork SHA:** 48afe2799453c9cd8405ed9df8d8debf74d594c9 (`feat/yarrrml-compiler` on `drex04/linkml-map`)
- **Tests:** 305/305 fast tests passing (+6 new `test_build_spec_*` unit tests; 4 new integration tests — 2 fast, 2 slow); fork-side: 13 YarrrmlCompiler unit tests + 1 CLI integration test
- **Completed:** 2026-04-17
- **Key changes:** `YarrrmlCompiler` added to forked linkml-map, compiles `TransformationSpecification` → YARRRML consumable by morph-kgc; `Compiler` subclass with own `Environment(autoescape=False)` to preserve YAML; composite slots emit separate TriplesMap blocks via `parentTriplesMap` references; composite subject template = `<parent_subject>/<composite_slot_name>`; source-class subjects use SOURCE schema's default_prefix; JSONPath/XPath annotations read verbatim, CSV column names wrapped in `$(…)`; GREL emitted for linear unit conversions. rosetta-cli: `build_spec()` extended with required `source_schema_path` / `target_schema_path` kwargs (absolute paths, fail-fast on missing) and `spec.prefixes` pre-merging (source + target + rosetta globals {skos, semapv, xsd, qudt}; source wins on collision). Fork pinned via `[tool.uv.sources]` in rosetta-cli `pyproject.toml`. 13 `[review]` truths from plan-review 2026-04-17 all honored; latent `all_slots(class_name=...)` → `class_slots(...)` bug surfaced by Task 4 was fixed in-place.

## Phase 16 Plan 03 Completion

- **Plan:** `.planning/phases/16-rml-gen-v2/16-03-PLAN.md`
- **Tests:** 332/332 passing (329 fast + 3 slow; +24 fast tests: 15 rml_runner unit + 9 CLI `--run` + 1 fork-drift assertion — plus +1 slow E2E)
- **Completed:** 2026-04-17
- **Key changes:** `rosetta/core/rml_runner.py` new module — `run_materialize` as `@contextlib.contextmanager` yielding `rdflib.Graph`, `graph_to_jsonld` with in-process `linkml.generators.jsonldcontextgen.ContextGenerator` (raises `ValueError` if parsed dict lacks `@context` — no silent fallback), private helpers `_substitute_data_path` / `_build_ini` / `_generate_jsonld_context`, morph-kgc logging suppressed to keep stdout clean for `| jq`, RuntimeError wrapping on `mapping.yml` / `graph.serialize` / `ContextGenerator` errors, `_DATA_FILE_PLACEHOLDER` module constant. `rosetta-yarrrml-gen` extended with `--run`, `--data`, `--jsonld-output`, `--workdir` (with `Path.resolve()` + `Path.touch()` writability probe), `--context-output`; empty-graph → stderr warning + exit 0; uses `click.get_binary_stream("stdout").write(...)` for CliRunner-safe output. 17 `[review]` truths from plan-review 2026-04-17 all honored. Fork-drift guard added to `test_yarrrml_compile_integration.py`. README section rewritten with worked example + stdout matrix + exit codes.

## Phase 16 Plan 03 Follow-up (2026-04-17)

- **Truth #3 closed end-to-end.** `transform_builder.build_slot_derivation` now detects units via `detect_unit()` on source + target slot names/descriptions and emits `UnitConversionConfiguration` for known linear pairs (m↔ft, etc.). Fork's `YarrrmlCompiler` patched to emit FnML function refs at stable rosetta UDF IRIs (replacing the broken `grel:value` emission). `rml_runner` writes a Python UDF file into `work_dir` and wires it via morph-kgc's `udfs=` INI option. E2E verifies numeric conversion (4100 m → ~13451 ft) within 1% via `pytest.approx(rel=1e-2)`.
- **Fork SHA:** local commit `89e79d4` on `feat/yarrrml-compiler`. Until pushed, `pyproject.toml` `[tool.uv.sources]` points at the local checkout at `/home/ubuntu/dev/linkml-map-fork`. Re-pin to the pushed SHA after `git push origin feat/yarrrml-compiler` on the fork.

## Phase 18 Plan 01 Completion

- **Plan:** `.planning/phases/18-integration-test-hardening/18-01-PLAN.md`
- **Commit:** 86b3738
- **Tests:** 378/378 fast + 2/3 slow passing (1 pre-existing e2e failure — unit-conversion fork drift, not caused by Phase 18)
- **Completed:** 2026-04-18
- **Key changes:** pytest markers `integration` + `e2e` declared in `pyproject.toml`; 9 fixtures relocated to `rosetta/tests/fixtures/nations/` (with `stress/` + `adversarial/` placeholders); `conftest.py` now exposes fixture-path fixtures (`nor_csv_path`, `master_schema_path`, etc.) + reusable `fake_deepl` translator mock; existing integration tests (`test_accredit_integration.py`, `test_yarrrml_compile_integration.py`, `test_yarrrml_run_e2e.py`) retagged with module-level `pytestmark` and migrated to fixture-path fixtures; unit-test fixture paths in `test_ingest.py`, `test_normalize.py`, `test_yarrrml_gen.py` + README examples updated to `nations/` subdir; CI `test` job now runs full suite (`-m "not slow"` removed); new `fast-gate` job runs `-m "not slow and not e2e"`; README "Running tests" section documents marker scheme.

## Next Action

Plan 18-02 (positive-path pipeline coverage, including 4 translate mocks + 2 subprocess smoke tests) is unblocked. Plan 18-03 (adversarial / negative input stress tests) also unblocked — can run after or alongside 18-02. Both depend only on the 18-01 infrastructure.
