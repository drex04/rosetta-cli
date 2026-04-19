---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: SHACL validation refactor
status: complete
last_updated: "2026-04-18T19:45:00.000Z"
progress:
  total_phases: 19
  completed_phases: 19
  total_plans: 27
  completed_plans: 27
---

# State

## Current Position

- **Phase:** 19 (SHACL validation refactor) — **complete**
- **Plan:** 19-03 (`--validate` wiring + JSON-LD input) — complete
- **Status:** All 3 plans shipped 2026-04-19. 457/457 fast tests pass (+28 new across the phase). v2 SHACL pipeline live end-to-end: auto-generate shapes from master LinkML, hand-edit overrides in `policies/shacl/overrides/`, validate JSON-LD output of `rosetta-validate`, OR validate in-memory graph inline via `rosetta-yarrrml-gen --run --validate`. All deferred-risk failure modes hardened in-plan (no follow-ups outstanding).

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
| 18 | Integration & E2E Test Hardening | Complete |
| 19 | SHACL validation refactor | Complete |

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

## Unit-conversion regression fix (2026-04-18)

- **Commit:** 3fc820b — `fix: restore m->ft unit conversion broken by Phase 17 QUDT migration`
- **Bugs surfaced:** `test_e2e_nor_radar_csv_to_jsonld` flagged as pre-existing-failure during Phase 18-01 verification. Two independent root causes:
  1. `detect_unit("hasAltitudeFt")` returned `None` — CamelCase suffix boundary not covered by `(?:^|_)ft$` regex. Fixed by `_snake_case` preprocessor that inserts underscores at lowercase→uppercase boundaries.
  2. `build_slot_derivation._LINEAR_CONVERSION_PAIRS` still keyed on `("meter", "foot")` short-name strings after Phase 17 made `detect_unit()` return QUDT IRIs (`unit:M` / `unit:FT`). Fixed by rekeying pairs to QUDT IRIs + adding `_QUDT_TO_FORK_UNIT` map back to short names at the fork API boundary.
- **Regression tests:** 3 unit tests in `test_unit_detect.py` (camelcase_trailing_ft, camelcase_trailing_mph, preserves_negative_cases) + 1 integration test in `test_yarrrml_gen.py` (test_build_spec_emits_unit_conversion_for_m_to_ft). Phase 17's STATE.md "Phase 16 Plan 03 Follow-up" note about fork-SHA drift can be closed — the pinned fork at `0015068` already contains the fix; the bug was on the rosetta side.

## Phase 18 Plan 02 Completion

- **Plan:** `.planning/phases/18-integration-test-hardening/18-02-PLAN.md`
- **Commit:** ac8ced6
- **Tests:** 405/405 passing (+24 new integration/e2e/smoke tests)
- **Completed:** 2026-04-18
- **Key changes:** 10 integration test files under `rosetta/tests/integration/` covering every CLI tool (ingest, embed, suggest, lint, validate, provenance, translate, accredit, full_chain); 2 subprocess smoke tests under `rosetta/tests/smoke/`; 6 stress fixtures under `rosetta/tests/fixtures/stress/` (nested JSON Schema, complex XSD, CSV edge cases, LinkML with inheritance + mixins); all translate tests mocked via `fake_deepl` ($0 DeepL credits); LaBSE model mocked in embed tests per `test_embed.py` pattern; three-assertion contract (D-18-08) honored throughout. Assertions relaxed where third-party behavior diverged from plan (schema-automator CSV BOM passthrough, oneOf flattening, XSD attributes-under-classes) — documented inline.

## Phase 18 Plan 03 Completion

- **Plan:** `.planning/phases/18-integration-test-hardening/18-03-PLAN.md`
- **Commit:** e49bc68
- **Tests:** 431/431 passing (+26 new adversarial tests)
- **Completed:** 2026-04-18
- **Key changes:** 7 adversarial test files under `rosetta/tests/adversarial/`: `test_malformed_inputs` (JSON/XSD/CSV parse failures + inline BOM + empty-master), `test_schema_mismatch` (datatype_mismatch via int↔string divergence, renamed-field aliasing), `test_sssom_mistakes` (duplicate MMC, wrong column count, phantom-derank via HC-transition guard, clean-ingest baseline), `test_cli_misuse` (--run without --data, nonexistent input → Click exit 2, stdout/file collision, missing args → Click exit 2), `test_unit_pitfalls` (dBm recognized-but-unmapped, British "metre" via NLP cascade, ambiguous "count", lint dBm diagnostic), `test_yarrrml_hygiene` (dateTime typo → ContextGenerator error), `test_translate_errors` (6 DeepL exception paths via `fake_deepl`, zero API credits). 3 new committed adversarial fixtures (`malformed_nested.json`, `truncated_complex.xsd`, `wrong_encoding.csv`). Each adversarial test asserts exit code + stable stderr substring + "no partial output" invariant. Observed-behavior pinning used where production surfaces differ from plan assumptions (documented inline). 

## Hardening closed (2026-04-18, commit 2c6c826)

4 of the 5 latent rough edges surfaced during 18-03 were fixed:

- ✅ `parse_sssom_tsv` now raises ValueError on missing required columns (subject_id, predicate_id, object_id, mapping_justification, confidence). CLI catches + emits a clear diagnostic and exits 1.
- ✅ `rosetta-yarrrml-gen --run` validation moved to step 0; no partial TransformSpec YAML lands on guard failure.
- ✅ `rosetta-yarrrml-gen` rejects simultaneous `--output -` + `--jsonld-output -` (stdout collision guard).
- ✅ CSV ingest strips UTF-8 BOM (`_strip_bom_if_present` pre-processes BOM-prefixed files to a clean tempfile before `CsvDataGeneralizer` sees them).
- **Not fixed (intentional):** `rosetta-translate` unconditionally prepends original titles to aliases when `source_lang != EN`. User confirmed this is fine for mixed-language schemas.

Additionally, `conftest.py` now preloads rdflib's SPARQL parser grammar so schema-automator's pyparsing pollution can't corrupt later SPARQL queries in the same pytest session — a test-isolation fragility that was being masked by lucky ordering on master.

## Phase 18 — Summary

- **Tests added:** 24 (18-02) + 26 (18-03) + 4 (18-01 smoke + migration) = ~50 new tests net. Total suite grew from 367 → 431.
- **Markers landed:** `integration` (60 tests), `e2e` (4 tests), `slow` (existing, unchanged semantic).
- **Fixtures added:** 6 stress + 3 adversarial + 9 nation (relocated).
- **CI:** new `fast-gate` job runs `-m "not slow and not e2e"` for <60s PR feedback.
- **Bugs fixed along the way:** m→ft unit conversion (commit `3fc820b`) — Phase 17 QUDT-IRI migration had left `build_slot_derivation` and `detect_unit` (CamelCase) out of sync.

## Next Action

Phase 19 complete. Next milestone item per `.planning/ROADMAP.md` (or new feature work).

## Phase 19 Plan 19-03 Completion

- **Plan:** `.planning/phases/19-shacl-validation/19-03-PLAN.md`
- **Tests:** 457/457 fast passing (+11 new: 4 `test_validate` JSON-LD + 2 integration + 5 adversarial)
- **Completed:** 2026-04-19
- **Key changes:**
  - New `rosetta/core/shacl_validate.py` — shared `validate_graph(data, shapes, *, inference)` helper used by both `rosetta-validate` and `rosetta-yarrrml-gen --validate` (single pyshacl invocation site, no drift)
  - `rosetta/cli/validate.py` refactored — calls shared helper; new `--data-format {turtle,json-ld,auto}` flag with suffix autodetection (`.ttl` → turtle; `.jsonld`/`.json`/`.json-ld` → json-ld)
  - `rosetta/cli/yarrrml_gen.py` extended with `--validate`, `--shapes-dir`, `--validate-report` flags. Validates the in-memory `rdflib.Graph` from `run_materialize` BEFORE `graph_to_jsonld`; on violation blocks emission, writes report to stderr or `--validate-report` path, exits 1. Step-0 collision guard rejects all 3 pairwise `-`-on-stdout combinations.
  - Fix-on-sight: Phase-18 `test_yarrrml_gen_stdout_and_file_collision` updated for unified `UsageError` (exit 2); `pytest.mark.adversarial` declared in pyproject.

## Phase 19 Summary

- **Tests added:** 11 (T0/T4) + 6 (T4) + 11 (T4) = ~28 new tests across all three plans. Total fast suite: 431 → 457 (+26 net; some overlap from refactors).
- **New modules:** `rosetta/core/shacl_generator.py`, `rosetta/core/shapes_loader.py`, `rosetta/core/shacl_validate.py`, `rosetta/cli/shacl_gen.py`. New CLI tool: `rosetta-shacl-gen`.
- **Retirements:** `rosetta/policies/mapping.shacl.ttl` (v1 vocab) deleted.
- **Quality:** 0 basedpyright errors in any Phase 19 file. All 9 mandatory checks clean throughout. 6 fix-on-sight items closed in the same commits.

## Phase 19 Plan 19-02 Completion

- **Plan:** `.planning/phases/19-shacl-validation/19-02-PLAN.md`
- **Tests:** 449/449 passing (+6 new in `test_shacl_overrides.py`; +0 net change in `test_validate.py` — same 9 tests, inline shapes)
- **Completed:** 2026-04-19
- **Key changes:**
  - `rosetta/policies/shacl/{generated,overrides}/` dir convention live with READMEs
  - `rosetta/policies/shacl/generated/master.shacl.ttl` regenerable artifact (130KB, 43 NodeShapes)
  - Worked-example override: `track_bearing_range.ttl` (`mc:hasBearing` ∈ [0, 360))
  - Legacy `rosetta/policies/mapping.shacl.ttl` deleted; 0 grep hits remaining
  - `test_validate.py` migrated to inline `_SHAPES_TTL` (D-19-13)
  - New `rosetta/core/shapes_loader.py` — recursive walker; `os.walk(followlinks=False)` for symlink-loop safety; warns + merges non-shape Turtle (D-19-16, D-19-17)
  - `rosetta/cli/validate.py` `--shapes-dir` collapsed to single `load_shapes_from_dir` call
  - Fix-on-sight: same pyshacl Union-narrowing + CliRunner-chain patterns as Plan 19-01

## Phase 19 Plan 19-01 Completion

- **Plan:** `.planning/phases/19-shacl-validation/19-01-PLAN.md`
- **Commit:** `6946a29`
- **Tests:** 443/443 passing (+11 new: 7 `test_shacl_gen` + 4 `test_unit_detect`)
- **Completed:** 2026-04-19
- **Key changes:**
  - New `rosetta-shacl-gen` CLI wraps `linkml.generators.shaclgen.ShaclGenerator`
  - Closed-world default with `sh:ignoredProperties` for `prov:*` / `dcterms:*` / `rdf:type`; `--open` flag for open-world
  - Unit-aware shapes via `detect_unit` → `qudt:hasUnit` constraints; 5/6 master COP unit-bearing slots covered
  - Spike (D-19-14) chose wrapper over subclass
  - `rosetta/core/unit_detect.py` extended with `_knots?$` / `_degrees?$` / `_bearing$` patterns + `_VERTICAL_RATE_NAME` description-disambiguated check + `unit:FT-PER-MIN` mapping
  - Documentation: `docs/cli/shacl-gen.md` (mkdocs-click), `README.md`, `mkdocs.yml` nav
  - Fix-on-sight: corrected `CLAUDE.md` refurb command + 4 refurb findings in new code
