---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: LinkML + SSSOM migration
status: in_progress
last_updated: "2026-04-17T16:30:00.000Z"
progress:
  total_phases: 17
  completed_phases: 16
  total_plans: 17
  completed_plans: 20
---

# State

## Current Position

- **Phase:** 16 complete; Phase 17 (QUDT-native unit detection) next
- **Plan:** 16-00, 16-01, 16-02, 16-03 all complete — Phase 16 SSSOM → JSON-LD pipeline closed end-to-end
- **Status:** Plan 16-03 (morph-kgc runner + JSON-LD framing + E2E) complete on 2026-04-17; 332/332 tests passing (329 fast + 3 slow, +27 net new); 8/8 quality gates clean

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

## Known gap (not blocking phase completion)

- **Numeric unit conversion end-to-end:** `transform_builder.build_slot_derivation` in 16-01 leaves `unit_conversion=None`; fork emits GREL only when present. Plan 16-03 E2E asserts passthrough values via compaction-tolerant key lookup + `pytest.approx(rel=1e-2)`. Structural truth #3 satisfied (linear-convertible slot reaches JSON-LD); numeric conversion deferred to a future 16-01 patch or to Phase 17's unit-detect work.

## Next Action

Phase 16 complete. Phase 17 (QUDT-native multi-library unit detection) is independent of Phase 16 and can begin any time. Roadmap entry: `detect_unit()` returns QUDT IRIs directly; expanded regex + quantulum3/pint cascade; `UNIT_STRING_TO_IRI` table retired.
