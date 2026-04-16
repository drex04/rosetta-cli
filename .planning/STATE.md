---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: LinkML + SSSOM migration
status: in_progress
last_updated: "2026-04-16T13:00:00.000Z"
progress:
  total_phases: 17
  completed_phases: 15
  total_plans: 17
  completed_plans: 18
---

# State

## Current Position

- **Phase:** 16 (rml-gen v2 — SSSOM → linkml-map TransformSpec → YARRRML → JSON-LD)
- **Plan:** 16-00 and 16-01 complete; 16-02 next (YarrrmlCompiler in linkml-map fork)
- **Status:** Plan 16-01 (TransformSpec builder) complete on 2026-04-16; `rosetta-yarrrml-gen` CLI live; 294/294 tests passing; 8/8 quality gates clean

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

## Next Action

Plan 16-01 complete. Plan 16-02 (`YarrrmlCompiler` — TransformSpec → YARRRML, contributed to linkml-map fork) ready to plan. Prerequisites locked: source-format annotation contract, per-slot path annotations (`rosetta_jsonpath`/`rosetta_xpath`/`rosetta_csv_column`), TransformSpec.comments carrying effective source format.
