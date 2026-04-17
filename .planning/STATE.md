---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: LinkML + SSSOM migration
status: in_progress
last_updated: "2026-04-17T06:45:00.000Z"
progress:
  total_phases: 17
  completed_phases: 15
  total_plans: 17
  completed_plans: 19
---

# State

## Current Position

- **Phase:** 16 (rml-gen v2 — SSSOM → linkml-map TransformSpec → YARRRML → JSON-LD)
- **Plan:** 16-00, 16-01, 16-02 complete; 16-03 next (morph-kgc execution + JSON-LD framing + E2E)
- **Status:** Plan 16-02 (YarrrmlCompiler in forked linkml-map) complete on 2026-04-17; fork pinned at SHA 48afe27995 on drex04/linkml-map `feat/yarrrml-compiler`; 305/305 fast tests passing (+2 slow subprocess tests); 8/8 quality gates clean

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

## Next Action

Plan 16-02 complete. Plan 16-03 (morph-kgc runner + JSON-LD framing + end-to-end data execution) is next. The self-describing TransformSpec contract locked here — absolute-path `source_schema` / `target_schema` + pre-merged `spec.prefixes` — means 16-03 can invoke morph-kgc without re-specifying schemas on the CLI.
