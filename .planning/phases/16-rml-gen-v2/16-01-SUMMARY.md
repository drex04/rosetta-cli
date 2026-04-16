---
plan: 16-01
phase: 16-rml-gen-v2
title: SSSOM → linkml-map TransformSpec builder
status: complete
completed: 2026-04-16
test_metrics:
  total: 294
  passing: 294
  new_tests: 37
  baseline: 266
  removed: 9
  coverage: not_configured
  spec_tests_count: 0
quality_gates:
  ruff_format: pass
  ruff_check: pass
  basedpyright: pass
  pytest: pass
  radon: pass
  vulture: pass
  bandit: pass
  refurb: pass
---

# Plan 16-01 — SSSOM → linkml-map TransformSpec builder

## Outcome

All 9 tasks complete across 11 waves. **294/294 tests passing.** All 8 mandatory quality gates clean. `rosetta-yarrrml-gen` CLI renders end-to-end YAML `TransformationSpecification` output from approved SSSOM audit logs + LinkML schemas; round-trips through `linkml_map.datamodel.transformer_model.TransformationSpecification.model_validate`.

## Wave-by-wave

| Wave | Task(s) | Outcome |
|------|---------|---------|
| W1 | T1 — deps + entry-point rename | `linkml-map>=0.5.2`, `curies>=0.13.3` added; `rosetta-rml-gen` → `rosetta-yarrrml-gen` |
| W2 | T2 — `CoverageReport` model | `MappingDecision` deleted; `CoverageReport` added with `model_config = ConfigDict(extra="forbid")` |
| W3 | T3 — scaffold + legacy delete | `rml_builder.py` / `rml_gen.py` removed; `transform_builder.py` + `yarrrml_gen.py` scaffolded; `test_rml_gen.py` renamed + stubbed with `_verify_sssomrow_shape()` import-time gate |
| W4 | T4b + T4c — row filter + classify helpers | `filter_rows`, `_ClassifyContext`, `_build_slot_owner_index`, `_owning_class`, `classify_row` |
| W5 | T4d + T4e — composites + derivation builders | `group_composites`, `build_class_derivation`, `build_slot_derivation`, `build_composite_slot_derivation` |
| W6 | (consolidated into W5) | — |
| W7 | T4f — `build_spec` orchestrator + helpers | `_classify_singletons`, `_resolve_composite_groups`, `_collect_mappings`, `_populate_required_slot_coverage`, `_assemble_class_derivations`, `build_spec` |
| W8 | T5 — CLI wireup | Full CLI body with `_resolve_source_format` hybrid (flag OR `annotations.rosetta_source_format`); all file-loads wrapped for clean error paths |
| W9 | T7 — test fixtures | `nor_radar.linkml.yaml` + `master_cop.linkml.yaml` generated via `rosetta-ingest`; `sssom_nor_approved.sssom.tsv` hand-authored (11 rows covering all classification paths) |
| W10 | T6 + T8 — unit + integration tests | 37 new tests in `test_yarrrml_gen.py`; covers filter, classify, composite, build_spec, coverage fields, CLI happy-path + all failure modes |
| W11 | T9 — README + docs | README `rosetta-rml-gen` section replaced; CLAUDE.md, `.planning/codebase/*.md`, `.planning/PROJECT.md`, `REQUIREMENTS.md`, `DECISIONS.md`, `ROADMAP.md`, `STATE.md` rename sweep |

Task 4 was split across three dispatches per plan-review-2 guidance (4b+4c, 4d+4e, 4f) to bound context per subagent.

## Plan-text bugs fixed during build

Three plan inconsistencies surfaced during W7 implementation and were resolved inline:

1. **classify_row signature drift** — plan's `_classify_singletons` called the legacy 3-arg form; implementation now uses the `_ClassifyContext` dataclass throughout.
2. **_owning_class index contract** — plan text passed a `SchemaView` where a `dict[str, str]` index was required. Implementation threads the prebuilt `mst_slot_owners` dict through `_resolve_composite_groups` and `_assemble_class_derivations`.
3. **_assemble_class_derivations arity** — plan's `build_spec` called it with 4 args; the function needs `master_view` (5th arg) to compute `unmapped_required_master_slots`. Fixed.

W7 agent also factored the orchestrator into two additional small helpers (`_collect_mappings`, `_populate_required_slot_coverage`) to keep every function under radon grade C.

## Files changed

| File | Change |
|------|--------|
| `pyproject.toml` | +linkml-map, +curies; rosetta-rml-gen → rosetta-yarrrml-gen entry point |
| `uv.lock` | regenerated |
| `rosetta/core/models.py` | -MappingDecision; +CoverageReport (extra="forbid") |
| `rosetta/cli/rml_gen.py` | **deleted** |
| `rosetta/core/rml_builder.py` | **deleted** |
| `rosetta/tests/test_rml_gen.py` | renamed → `test_yarrrml_gen.py`; body fully rewritten |
| `rosetta/cli/yarrrml_gen.py` | **new** — Click CLI with `_resolve_source_format`, empty-filter guard, coverage report emission |
| `rosetta/core/transform_builder.py` | **new** — filter/classify/compose/derive/orchestrate (~640 lines) |
| `rosetta/tests/test_yarrrml_gen.py` | 37 tests (unit + CLI integration) |
| `rosetta/tests/fixtures/nor_radar.linkml.yaml` | **new** — csv-sourced schema with `rosetta_source_format: csv` annotation |
| `rosetta/tests/fixtures/master_cop.linkml.yaml` | **new** — rdfs-sourced schema (no source-format annotation per 16-00 contract) |
| `rosetta/tests/fixtures/sssom_nor_approved.sssom.tsv` | **new** — 13-col SSSOM with class/slot/composite/closeMatch/narrowMatch/differentFrom/off-prefix coverage |
| `rosetta/tests/test_embed.py`, `test_normalize.py`, `test_translate.py` | `# pyright: ignore[...]` suppressions — linkml-runtime type tightening after `uv add linkml-map` |
| `README.md` | rosetta-rml-gen section deleted; rosetta-yarrrml-gen section added; incidental refs updated |
| `CLAUDE.md`, `.planning/codebase/{ARCHITECTURE,CONVENTIONS,STACK,STRUCTURE}.md`, `.planning/{PROJECT,REQUIREMENTS,DECISIONS,ROADMAP,STATE}.md` | rename sweep |

## Quality gates

| Gate | Result |
|------|--------|
| `uv run ruff format .` | 2 files reformatted (applied) |
| `uv run ruff check .` | All checks passed |
| `uv run basedpyright` | 0 errors, ~1047 warnings (warnings only in tests, basic mode) |
| `uv run pytest -m "not slow"` | 294 passed |
| `uv run radon cc rosetta/core/ -n C -s` | No grade C+ functions |
| `uv run vulture rosetta/ --exclude rosetta/tests --min-confidence 80` | Clean |
| `uv run bandit -r rosetta/ -x rosetta/tests -ll` | 0 issues |
| `uv run refurb rosetta/core/ rosetta/cli/` | Clean (3 FURB suggestions applied) |

## Cross-phase contracts locked (for 16-02 consumption)

- **Source-format annotation:** `rosetta-ingest` stamps `annotations.rosetta_source_format ∈ {json, csv, xml}` on every non-RDFS schema; `yarrrml-gen` reads it as the fallback when `--source-format` is omitted.
- **Per-slot path annotations** (from 16-00): `rosetta_csv_column`, `rosetta_jsonpath`, `rosetta_xpath`. 16-01 passes schemas through to the TransformSpec unchanged; 16-02's `YarrrmlCompiler` consumes the annotations to emit RML references.
- **TransformSpec.comments:** `rosetta:source_format=<effective>` prefix carries CLI-resolved format forward.

## Issues encountered

- **linkml-runtime type tightening** — `uv add linkml-map` (W1) bumped linkml-runtime to a version where `SchemaDefinition.classes` / `.slots` are typed `dict | list | None` instead of `dict`. 37 basedpyright errors surfaced in pre-existing `test_embed.py` / `test_normalize.py` / `test_translate.py`. Resolved with narrow `# pyright: ignore[...]` suppressions per CLAUDE.md convention.
- **W10 agent report wording** — the W10 subagent reported "test file was already fully implemented from a prior wave"; empirically the 37 tests were present and passing post-dispatch, full suite 294/294. Likely the agent considered its own first writes as "prior state" mid-run. No functional issue.

## Concerns for downstream

- `test_cli_stdout_mode_when_output_omitted` asserts output starts with `comments:` or `id:` — if linkml-map changes YAML key ordering, the assertion becomes fragile. Consider switching to a structural YAML parse if serialisation order drifts.
- `_owning_class` uses "first owner wins" semantics from `SchemaView.all_classes()` iteration order. In the fixture, `mc:hasLatitude` resolves to `Entity` (not `Track`), which is semantically correct but worth noting if 16-02 needs per-track slot grouping.
- `unit_conversion` on `SlotDerivation` is always `None` in 16-01 output — 16-02's `YarrrmlCompiler` populates it from `range` + master schema units.

## Next

Plan 16-02 — `YarrrmlCompiler` contribution to the linkml-map fork; consumes TransformSpec + source-format annotation + per-slot path annotations to emit YARRRML. Plan 16-03 — `morph-kgc` execution path + JSON-LD output (`--frame` behind flag).
