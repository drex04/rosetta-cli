---
phase: 16
title: "rosetta-rml-gen v2 — SSSOM → TransformSpec → YARRRML → JSON-LD"
design_doc: .planning/designs/2026-04-16-phase16-rml-gen-v2.md
research_doc: .planning/phases/16-rml-gen-v2/RESEARCH.md
status: locked
locked_date: 2026-04-16
---

# Phase 16 Context

## Architecture (locked)

**Pipeline:** SSSOM audit log → linkml-map `TransformationSpecification` → YARRRML (via forked linkml-map `YarrrmlCompiler`) → N-Triples (via morph-kgc) → JSON-LD (via rdflib + `linkml gen-jsonld-context`).

**Plan split (4 plans):**

| Plan | Scope | Repo |
|------|-------|------|
| 16-00 | SSSOM audit-log schema extension (composite-entity support) + `rosetta-ingest` prefix collision lint | rosetta-cli |
| 16-01 | SSSOM → TransformSpec builder; schema coverage check; per-schema filtering | rosetta-cli |
| 16-02 | YarrrmlCompiler in forked linkml-map | linkml-map fork |
| 16-03 | morph-kgc runner + JSON-LD framing + E2E | rosetta-cli |

## Stack (locked)

- `linkml-map` — forked, pinned via git SHA in `pyproject.toml`
- `morph-kgc >= 2.10` — RML/YARRRML execution engine
- `curies >= 0.7` — CURIE ↔ IRI resolution
- `rdflib` — existing; handles N-Triples → JSON-LD framing
- `linkml` — existing; `gen-jsonld-context`, `gen-owl`

## Locked decisions

### From brainstorm

1. Class-level SSSOM rows auto-populate `ClassDerivation.populated_from`. Missing class row for a referenced source class → exit 1 with `"add class mapping for src:X"`.
2. Multi-class schemas: one TransformSpec file with multiple `class_derivations`.
3. Unit conversion: marked on TransformSpec via `unit_conversion: {target_unit: …}` in 16-01; compiled to FnML GREL in 16-02 (linear); UDF escape hatch deferred post-phase.
4. JSON-LD output: context-only (compaction) in 16-03. `--frame` behind flag is post-phase work.
5. Master ontology starts as `.ttl`/`.owl`; LinkML form produced by `rosetta-ingest` (verified: `normalize.py:58` dispatches `.ttl`/`.owl`/`.rdf` → schema-automator `rdfs` importer).
6. `--sssom` points at the full audit log; builder filters for `mapping_justification in {semapv:HumanCuration, semapv:ManualMappingCuration}`; `--include-manual` bypasses the filter.
7. Empty filtered SSSOM → exit 1 unless `--allow-empty`.
8. Fork hosted under user's GitHub account; installed via git URL in `pyproject.toml`.
9. No upstream PR during Phase 16. User tests manually, files PR later.
10. Fork base: latest `main`; pin SHA; rebase on demand.
11. YarrrmlCompiler PR scope (when filed): compiler + tests only. SSSOM importer contribution deferred.

### From 16-01 brainstorm (schema-as-registry)

- **CURIE resolution model — schema-as-registry:** each LinkML schema produced by `rosetta-ingest` already declares a unique `default_prefix` + namespace `id` (verified: `demo_out/master_cop.linkml.yaml` uses `mc`; `demo_out/nor_radar.linkml.yaml` uses `nor_radar`). Schemas are authoritative for their own prefixes; `transform_builder` resolves CURIEs by merging source-schema `prefixes:`, master-schema `prefixes:`, and `rosetta.toml` globals (`skos`, `semapv`, `xsd`, `qudt`). No collision possible by construction if unique `--schema-name` per ingest.
- **SSSOM header `curie_map` is informational only.** `transform_builder` does not consult it for resolution; it trusts the schemas.
- **Multi-schema audit log:** the audit log accumulates rows from every source schema mapped against the master. `transform_builder --source-schema nor_radar.linkml.yaml` filters rows where `subject_id.startswith("nor_radar:")`; other-schema rows are ignored silently. One audit log, per-schema builds.
- **Prefix collision lint (added to 16-00 Task 6):** `rosetta-ingest` refuses to write a LinkML output whose `default_prefix` or `id` collides with an existing `*.linkml.yaml` sibling. Fails fast at the earliest point.

### From gray-area discussion

- **GA1:** Mapping-generating predicates: `skos:exactMatch` + `skos:closeMatch`. Other predicates → coverage-report entry, excluded from TransformSpec output. `owl:differentFrom` (Phase 14 derank marker) always excluded.
- **GA2 (overridden from initial recommendation):** 1:N and N:1 mappings use the SSSOM composite-entity pattern. Four new columns: `subject_type`, `object_type`, `mapping_group_id`, `composition_expr`. Rows sharing a `mapping_group_id` compose one logical mapping; `composition_expr` flows into linkml-map `SlotDerivation.expr`. Implemented in Plan 16-00 as a prerequisite schema extension.
- **GA3:** Datatype mismatch without unit context → emit `slot_derivation.range: <target xsd type>` (linkml native type coercion). Lossy coercion → coverage-report warning only. `rosetta-lint` remains authoritative for suspicious cases.
- **GA4 [revised in review]:** Source-format resolution: hybrid. `rosetta-ingest` stamps `annotations.rosetta_source_format` on every data-source schema (see 16-00 Task 7); `rosetta-yarrrml-gen`'s `--source-format` CLI flag is **optional** and overrides the annotation when present; exit 1 if neither is available. Implemented across 16-00 Task 7 (stamping) and 16-01 Task 5 step 4 (resolution).
- **GA5:** Fork CI is separate. Fork's own GitHub Actions run YarrrmlCompiler tests. rosetta-cli CI installs the fork via git URL and runs integration tests only. Fork README links back to this design doc.

### From plan-review (2026-04-16)

Findings and decisions from reviewing Plans 16-00 and 16-01. Both plans locked in HOLD mode with targeted hardening.

**Plan 16-00:**
- **[review] Live audit-log migration (Task 3b + 4e):** `rosetta/core/accredit.py::append_log` detects a pre-16-00 header (fewer columns than `AUDIT_LOG_COLUMNS`) and rewrites the audit log in-place with `tmp + os.replace` atomicity. Pads legacy rows with empty trailing fields. Covered by `test_accredit_append_log_migrates_9col_file` + `test_accredit_append_log_no_migration_on_current_shape`.
- **[review] AUDIT_LOG_COLUMNS-driven writer (Task 3 step 2):** `append_log` now constructs `writer.writerow` via `[_row_value_for_column(row, col, …) for col in AUDIT_LOG_COLUMNS]` instead of a parallel positional literal. Prevents silent header/body drift on future column additions.
- **[review] `check_prefix_collision` hardening (Task 6a):** uses `parent.is_dir()` guard (covers missing and is_file cases); emits stderr warning on YAMLError/OSError sibling reads instead of silently continuing. Tests added for `id`-field collision and malformed-sibling warning.
- **[review] Ingest annotation stamping (Task 7, scope creep from 16-01):** `rosetta-ingest` writes `annotations.rosetta_source_format` at schema level + per-slot `rosetta_csv_column` / `rosetta_jsonpath` / `rosetta_xpath`. Realises GA4 hybrid and locks the **16-02 cross-phase contract** for per-slot path references.

**Plan 16-01:**
- **[review] `--source-format` now optional**, falls back to `annotations.rosetta_source_format` on the source schema. Eliminates the GA4 contradiction between CONTEXT and Task 3/5 that existed before review.
- **[review] `CoverageReport.unmapped_required_master_slots` populated**: `_assemble_class_derivations` computes `{required master slots per target class} − {resolved slot-derivation names}` and records `Class.slot` entries. Was previously declared but never written — a silent lie in the coverage artifact.
- **[review] SchemaView slot-owner index (Task 4c):** `classify_row` takes a pre-built `slot_name → owning_class` dict (one per SchemaView) via a `_ClassifyContext` dataclass. Removes the O(classes × slots) `class_induced_slots` repeat-scan that was being executed per row.
- **[review] Task 3 test-file overwrite:** after `git mv test_rml_gen.py test_yarrrml_gen.py`, the file body is replaced with a stub in the same commit — includes an import-time `_verify_sssomrow_shape()` guard that fails fast if Plan 16-00 regressed on `SSSOMRow` field additions.
- **[review] CLI error handling (Task 5):** all schema loads wrapped in `try/except (FileNotFoundError, OSError, yaml.YAMLError, Exception)` → `click.echo(err=True); sys.exit(1)`. No raw Python tracebacks on malformed inputs.
- **[review] linkml-map pre-flight verification (Task 1 step 0):** verify `uv add linkml-map` + `from linkml_map.datamodel.transformer_model import TransformationSpecification, …` succeeds in a scratch venv BEFORE committing Task 1; pin the resolved version.
- **[review] 16-02 cross-phase contract (locked here, implemented in 16-00 Task 7):** per-slot source-path annotations use keys `rosetta_jsonpath` (JSON), `rosetta_xpath` (XML/XSD), `rosetta_csv_column` (CSV/TSV). 16-02's `YarrrmlCompiler` reads these off the source schema to construct RML references. 16-01 does NOT copy them onto `SlotDerivation` — they stay on the schema. `TransformationSpecification.comments = ["rosetta:source_format=<fmt>"]` carries the effective format.
- **[review] Task 9 rename sweep extended:** also updates `.planning/REQUIREMENTS.md`, `.planning/DECISIONS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md` — each contains live `rosetta-rml-gen` references beyond the originally-listed files.
- **[review] Confirmed OK:** `TransformationSpecification.comments` is inherited from `SpecificationComponent` (verified upstream); fixture directory has no existing `*.linkml.yaml` to collide with; `MappingDecision` deletion is safe (only referenced by files being deleted).

**Plan 16-01 (second-pass review, 2026-04-16, post-16-00-merge):**

- **[review-2] `CoverageReport.model_config = ConfigDict(extra="forbid")`** — and by extension all new Pydantic v2 models in this phase. Catches field-name typos at construction time. Same gotcha that bit `SSSOMRow` in 16-00 (silent extra-field acceptance). Cheap to fix at model birth.
- **[review-2] linkml-map version pin captured at pre-flight time, not assumed.** Task 1 step 1 must `uv pip show linkml-map | awk '/Version:/ {print $2}'` and write the resolved version to `pyproject.toml`. Guards against `>=0.3.0` placeholders drifting from what actually resolved on the dev machine.
- **[review-2] Task 4 sub-task wave map: 4a (removed) | (4b ∥ 4c) → 4d → 4e → 4f.** Task 4 is 424 lines — too large for a single subagent dispatch. Build orchestrator splits across 3 waves to bound context per agent and avoid OOM/context-burn.
- **[review-2] Task 7 (fixtures) precedes Tasks 6 + 8 (tests).** Wave order: T1 → T2 → T3 → (T4 sub-waves) → T5 → T7 → (T6 ∥ T8) → T9. Otherwise pytest fails on missing fixture files mid-build.
- **[review-2] Pre-flight verified live:** `linkml_map.datamodel.transformer_model.{TransformationSpecification, ClassDerivation, SlotDerivation, UnitConversionConfiguration}` all import successfully in a scratch venv against current PyPI. `linkml_map.__version__` attribute is missing — use `uv pip show` to capture instead.
- **[review-2] 16-00 prerequisites all satisfied** (commit 52e4999): SSSOMRow has the four composite fields, audit log is 13 columns, `rosetta-ingest` stamps `rosetta_source_format` and per-slot path annotations. `MappingDecision` consumers confirmed limited to `cli/rml_gen.py`, `core/rml_builder.py`, `core/models.py`, `tests/test_rml_gen.py` — all deleted/stubbed by Tasks 2 + 3.

### From plan-review of 16-02 (2026-04-17)

Plan 16-02 locked in **HOLD + harden** mode. Six decisions locked:

- **[review] Schema field carries absolute filesystem path, not name.** `build_spec()` writes `spec.source_schema = str(source_path)` and `spec.target_schema = str(target_path)` where the paths are the `--source-schema` / `--master-schema` CLI arguments into `rosetta-yarrrml-gen`. The YarrrmlCompiler passes them to `SchemaView()` verbatim. Rationale: Plan 16-02 Task 2a's pseudocode calls `SchemaView(specification.source_schema)` expecting a path; `source.name` ("nor_radar", "master_cop_ontology") would fail that call. build_spec must therefore accept paths, which means `yarrrml_gen.py` passes them in beside the already-loaded SchemaDefinitions.
- **[review] build_spec raises on missing schema paths; never writes `""`.** Silent empty strings would bypass compile-time validation and surface as opaque ValueErrors later. Fail fast.
- **[review] Composite member extraction: parse `composition_expr`, not `mapping_group_id`.** 16-01's `_build_composite_slot_derivation` collapses groups into a single SlotDerivation with a joint `composition_expr` and does NOT preserve `mapping_group_id` on the output. Plan 16-02 Task 2f's original "group by mapping_group_id in SlotDerivation.comments" rule has no data to act on. Compiler detects composites via `slot_deriv.expr is not None` and parses member source-slot names from the expression string. Composition_expr parser is documented + tested.
- **[review] Composite TriplesMap subject = `<parent_subject>/<composite_slot_name>`.** Composites lack source-class identifiers. Deterministic parent-qualified suffix is 1:1 with the parent row and avoids blank-node portability issues across morph-kgc.
- **[review] Source-class subject template uses SOURCE schema default_prefix.** Preserves provenance and round-trip row identity. `rdf:type` to target class URI still fires via po entry. Target-prefix alternative would collapse identity across source systems.
- **[review] YarrrmlCompiler receives `spec.prefixes` pre-merged by rosetta-cli.** `build_spec()` merges source prefixes + target prefixes + rosetta globals ({skos, semapv, xsd, qudt}) into `spec.prefixes`. Fork compiler reads `spec.prefixes` directly into the YARRRML `prefixes:` block — no fork-side hardcoded rosetta vocabulary. Keeps the fork agnostic of rosetta-cli conventions.
- **[review] JSONPath / XPath annotations consumed verbatim.** 16-00 Task 7 already stamps `rosetta_jsonpath = "$.<slot>"` in proper JSONPath form. Re-wrapping yields `$.($.latitude)`. CSV annotation (column name) is wrapped in `$(column)`. XML (XPath) is verbatim. Fallback branch wraps for JSON/CSV, raises for XML.
- **[review] `--target-schema` added only on `compile` command.** Upstream cli.py already defines a `--target-schema` option on a non-compile command (line 45). Verify no symbol shadow during Task 5 implementation.
- **[review] Task 7 integration test covers the `-s` / `--target-schema` omitted path.** Proves the self-describing-spec contract (spec carries the paths) actually works when CLI overrides aren't passed — the whole point of Finding 1/2's path-carrying decision.

### From 16-02 brainstorm (2026-04-17)

- **GA-02-1 (subject identifier strategy):** Auto-detect identifier slot via `SchemaView` standard `identifier: true` discovery, then fall back to `id` / `identifier` / `{class}_id` heuristic, then positional `$(__row)`. Hard fail if nothing found. Emit compiler warning on heuristic fallback.
- **GA-02-2 (composite TriplesMap):** Composites emit separate YARRRML `mappings:` blocks with their own subject template and properties. The owning class's mapping references via `o: mapping: <composite-name>` (YARRRML's `rr:parentTriplesMap` equivalent). Not inline — separate TriplesMaps.
- **GA-02-3 (datatype coercion):** Always emit `datatype:` on `o:` entries when `SlotDerivation.range` is set. Explicit over implicit.
- **GA-02-4 (source reference):** YARRRML emits placeholder `sources:` with `$(DATA_FILE)` substituted at morph-kgc runtime (16-03). Format/iterator derived from `rosetta:source_format` comment on the TransformSpec.
- **GA-02-5 (fork branch policy):** Feature branch `feat/yarrrml-compiler` off upstream-tracking `main`. Atomic commits per subtask. rosetta-cli pins feature-branch SHA.
- **Compiler structure (A2):** YarrrmlCompiler subclasses `Compiler` directly (not `J2BasedCompiler`), rolls own Jinja Environment with `autoescape=False` for YAML safety. Upstream `J2BasedCompiler.autoescape=True` corrupts non-HTML output.
- **CLI registration (B1):** Add `elif target == "yarrrml"` in the fork's `cli/cli.py::compile`. Smallest diff; no plugin registry churn.
- **Schema injection (C2+C1):** 16-01 `build_spec()` extended to populate `spec.source_schema` and `spec.target_schema`. Fork CLI adds `--target-schema` override option. Compiler reads target schema from spec field or CLI override.
- **Template approach (D1):** Single flat `yarrrml.j2` template. Refactor to macros only if template exceeds ~100 lines.
- **FnML GREL (E2):** Pre-compute GREL strings in Python (`_grel_for_linear(m, b)`), pass into template context. Template stays declarative.
- **Fork repo:** `https://github.com/drex04/linkml-map`
- **16-01 prerequisite extension:** `build_spec()` must populate `spec.source_schema` and `spec.target_schema` before 16-02 can proceed. Small rosetta-cli change included as Task 0 of 16-02.

## Deferred Ideas

- **Upgrade `subject_type`/`object_type` from prose string `"composed entity expression"` to the SSSOM CURIE `sssom:CompositeEntity`.** — deferred pending move to full SSSOM validation. Forward-compat note added to README in 16-00 Task 5.3.
- **`--dry-run` and `--stats` flags on `rosetta-yarrrml-gen`.** — delight opportunity surfaced during scope challenge, deferred to keep 16-01 HOLD-tight.
- **Reader-side reconciliation for wider-than-current audit log headers.** — `_migrate_audit_log_if_needed` in 16-00 no-ops if existing header is wider than `AUDIT_LOG_COLUMNS` (future-version tolerance). Full downgrade-migration is not in scope.
- **Auto-inference of deeper JSONPath expressions for nested JSON slots.** — 16-00 Task 7 stamps `$.<slot_name>` flat paths only; nested-object handling deferred.

## Scope and boundaries

**In scope for Phase 16:**
- Composite-entity SSSOM extension (16-00)
- SSSOM → TransformSpec builder with schema coverage checks (16-01)
- YarrrmlCompiler in fork (16-02)
- morph-kgc execution + JSON-LD framing + E2E (16-03)

**Out of scope (deferred):**
- JSON-LD `@frame` support (post-phase flag)
- Nonlinear unit conversion via Python UDF (GREL only in 16-02)
- Class-inheritance handling beyond what `SchemaView` materialises automatically
- Auto-inference of decomposition/aggregation expressions (user authors `composition_expr` via review workflow — future UX)
- Upstream PR to linkml/linkml-map (user-managed post-phase)

## Dependencies on prior phases

- **Phase 14 (audit log):** 16-00 extends the audit log schema. Existing 9-column logs must continue to parse (backward-compat via `.get()` defaults). The `store/audit-log.sssom.tsv` file may need to be regenerated or left empty at phase start; existing tests must still pass.
- **Phase 15 (lint SSSOM):** `rosetta-lint` remains authoritative for datatype/unit warnings. 16-01's coverage report is informational — not a lint replacement.
- **Phase 12 (ingest):** `normalize.py` already handles `.ttl`/`.owl`/`.rdf` → no new ingest code. 16-01 may require adding a `source_format` annotation pass-through; defer decision to 16-01 PLAN.

## Quality gates

All mandatory checks per CLAUDE.md before each plan completes:
- `uv run ruff format .`
- `uv run ruff check .`
- `uv run basedpyright`
- `uv run pytest -m "not slow"`
- `uv run radon cc rosetta/core/ -n C -s`
- `uv run vulture rosetta/ --exclude rosetta/tests --min-confidence 80`
- `uv run bandit -r rosetta/ -x rosetta/tests -ll`
- `uv run refurb rosetta/ rosetta/tests/`
