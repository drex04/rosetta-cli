---
date: 2026-04-17
plan: .planning/phases/16-rml-gen-v2/16-02-PLAN.md
spec: .planning/phases/16-rml-gen-v2/16-02-SPEC.md
mode: HOLD + harden
kind: plan-review-summary
---

# Plan 16-02 Plan-Review Summary

Human-reference audit trail. Downstream skills read PLAN.md and CONTEXT.md only; this file captures the review narrative and diagrams for future archaeology.

## Mode

**HOLD + harden.** Seven-task plan left intact. No scope cut, no scope added. Six critical/warning defects surfaced and locked into PLAN.md `[review]` truths + CONTEXT.md decisions.

## System audit (pre-review, verified)

- `TransformationSpecification` has `source_schema`, `target_schema`, `prefixes` fields — Task 0 field writes are valid.
- `Compiler` (ABC) + `CompiledSpecification` + `J2BasedCompiler` exist in `linkml_map.compiler` — subclassing `Compiler` directly is correct (J2BasedCompiler.autoescape=True is the documented hazard).
- linkml-map 0.5.2 already installed; `uv pip show linkml-map` confirms. Fork-SHA pin replaces the PyPI line cleanly.
- `demo_out/master_cop.linkml.yaml` name = `master_cop_ontology` (NOT `mc`). Plan Task 0 test assertion was wrong.
- `_build_composite_slot_derivation` in `transform_builder.py:248-271` collapses composite groups to ONE `SlotDerivation` with a joint `composition_expr`. `mapping_group_id` is consumed at grouping and NOT written to the SlotDerivation. Plan Task 2f's assumption was incorrect.

## Findings

| # | Severity      | Area                                 | Decision                                                                                   |
| - | ------------- | ------------------------------------ | ------------------------------------------------------------------------------------------ |
| 1 | CRITICAL GAP  | Composite detection (Task 2f)        | Parse `composition_expr` for member slot names; no mapping_group_id reliance               |
| 2 | CRITICAL GAP  | Schema field value (Task 0 + Task 2a)| Store absolute filesystem path; raise if unavailable; fix Task 0 test assertion            |
| 3 | CRITICAL GAP  | Prefix map coverage (Task 2h)        | rosetta-cli embeds skos/semapv/xsd/qudt into spec.prefixes; fork stays agnostic            |
| 4 | WARNING       | Subject template prefix (Task 2c)    | Use SOURCE schema's default_prefix for `s:`; target URI used only in rdf:type po entry     |
| 5 | CRITICAL GAP  | Composite subject IRI (Task 2c)      | Composite subject = `<parent_subject>/<composite_slot_name>`                               |
| 6 | WARNING       | JSONPath wrapping (Task 2d)          | Use rosetta_jsonpath / rosetta_xpath verbatim; wrap CSV column names; fallback rules set    |

### Minor issues folded into truths without decision

- `--target-schema` option shadowing: verify no collision with existing cli.py line 45 option on a non-compile command.
- Integration test (Task 7) adds a case without `-s` / `--target-schema` overrides — proves spec-carried paths work.
- Commit trailer in Task 6: "Claude Opus 4.7 (1M context)" (plan draft said 4.6).

## Error & Rescue Registry

| Codepath                                               | Failure mode                                  | Rescued? | Test?      | User sees                      | Logged? |
| ------------------------------------------------------ | --------------------------------------------- | -------- | ---------- | ------------------------------ | ------- |
| `build_spec()` in rosetta/core/transform_builder.py    | source path not passed                        | Y (raise) | Needs test | ValueError with actionable msg | N/A    |
| `build_spec()` — target path not passed                | target path not passed                        | Y (raise) | Needs test | ValueError                     | N/A    |
| `YarrrmlCompiler._resolve_schemas`                     | spec.source_schema empty AND no ctor override | Y (raise) | Task 4 #9  | ValueError                     | N/A    |
| `YarrrmlCompiler._resolve_source_format`               | comments has no `rosetta:source_format=`       | Y (raise) | Add test   | ValueError                     | N/A    |
| `YarrrmlCompiler._resolve_subject_template`            | no identifier slot found                      | Y (raise) | Task 4 #10 | ValueError w/ class name       | N/A    |
| `YarrrmlCompiler._resolve_reference`                   | annotation missing for slot                   | Y (fallback + warn) | Add test | stderr warning, fallback IRI | Y (stderr) |
| `YarrrmlCompiler._grel_for_linear`                     | nonlinear conversion                          | Y (raise + fallback) | Add test | stderr warning, skip FnML     | Y (stderr) |
| Composite expr parser                                  | unparseable composition_expr                  | Y (raise) | **NEW TEST** | ValueError with row IDs       | N/A    |
| `spec.prefixes` merge                                  | collision between source + target + globals   | Y (silent — source wins) | Add test | none  | N/A    |

**CRITICAL GAP → PLAN.md `[review]` truths:** 6 (findings 1–6). Already added.

## Failure Modes Registry

| Codepath                                    | Failure Mode                       | RESCUED? | TEST? | USER SEES?    | LOGGED? |
| ------------------------------------------- | ---------------------------------- | -------- | ----- | ------------- | ------- |
| path→SchemaView resolution                  | path exists but YAML malformed     | N        | N     | Traceback     | N       |
| prefix merge                                | global prefix overrides schema URI | Y        | N     | Silent        | N       |
| Fork/rosetta-cli version drift              | fork refactors Compiler base       | N        | Y (integration) | ImportError | Y    |

Top two are **CRITICAL GAPs** that deserve follow-up tests during build; they're already captured in truths list (raise on build_spec path-missing; integration test coverage).

## Delight Opportunities

Mode is HOLD. None surfaced for this plan. Three already deferred in CONTEXT "Deferred Ideas" (dry-run/stats, nested JSONPath, reader-side audit log reconciliation) remain out of scope.

## Diagrams

### Data flow — with review hardening applied

```
rosetta-yarrrml-gen CLI
       │  passes src_path, tgt_path, SchemaDefinitions
       ▼
  build_spec()
       │  spec.source_schema = str(src_path)          ← [review-2]
       │  spec.target_schema = str(tgt_path)          ← [review-2]
       │  spec.prefixes = merge(src, tgt, globals)    ← [review-3]
       │  spec.comments = [rosetta:source_format=…]
       ▼
  TransformSpec YAML  ────────────[ self-describing ]─────────────┐
                                                                  │
  fork CLI: linkml-tr compile yarrrml -T spec.yaml [--target-schema X] --source-schema Y
                                                                  │
                                                                  ▼
                                                   YarrrmlCompiler.compile()
                                                   ├ _resolve_schemas: SchemaView(path)
                                                   ├ _resolve_source_format: parse spec.comments
                                                   ├ for class_deriv:
                                                   │   subject_template: SOURCE prefix + $(id)  [review-4]
                                                   │   for slot_deriv:
                                                   │     if expr: mark as composite             [review-1]
                                                   │     if range: emit datatype                [GA-02-3]
                                                   │     if unit_conv: GREL                    [E2]
                                                   │     else: simple po:
                                                   ├ for each composite slot_deriv:
                                                   │   parse composition_expr → member slots    [review-1]
                                                   │   subject = parent_subj/<slot_name>        [review-5]
                                                   │   emit separate mapping block
                                                   │   owning class's po references via mapping:
                                                   └ render yarrrml.j2
                                                                  │
                                                                  ▼
                                                          YARRRML YAML
```

### Shadow paths

```
Happy:          TransformSpec complete → YARRRML yaml.safe_load() ok → top-level keys {prefixes, mappings}
Nil input:      build_spec() called with source_path=None → ValueError (no silent "") [review]
Empty rows:     filter_rows returns [] → build_spec raises (existing --allow-empty flow, unchanged)
Upstream err:   fork Compiler signature drift → import fails → integration test breaks CI
Composite w/o parent: composite SlotDeriv whose owning ClassDeriv has no identifier → Task 2c raises
Missing annotation (json): rosetta_jsonpath absent → stderr warn, fallback $.<slot_name>
Missing annotation (xml):  rosetta_xpath absent → raise (no safe fallback for XPath)
```

### Test coverage diagram

```
rosetta-cli side (Task 0, Task 7):
  ┌────────────────────────────────────────────────┐
  │ test_yarrrml_gen.py                             │
  │  ├ test_build_spec_populates_source_and_target_schema (abs path)  [NEW]
  │  ├ test_build_spec_raises_on_missing_source_path                  [NEW]
  │  ├ test_build_spec_raises_on_missing_target_path                  [NEW]
  │  ├ test_build_spec_prefixes_merge_includes_rosetta_globals        [NEW]
  │  └ (existing 20+ tests unchanged)
  │                                                 │
  │ test_yarrrml_compile_integration.py (NEW)       │
  │  ├ test_yarrrml_compile_produces_valid_yaml     │
  │  ├ test_yarrrml_compile_csv_references_match_annotations │
  │  ├ test_yarrrml_compile_cli_end_to_end (with -s / --target-schema overrides)  │
  │  └ test_yarrrml_compile_cli_self_describing (NO -s / --target-schema)   [review]
  └────────────────────────────────────────────────┘

Fork side (Tasks 4, 5):
  ┌────────────────────────────────────────────────┐
  │ tests/test_yarrrml_compiler.py (10 cases + 3 new):
  │  ├ #1 compile_class_derivation_produces_valid_yarrrml
  │  ├ #2 compile_slot_references_use_csv_annotations
  │  ├ #3 compile_datatype_emitted_when_range_set
  │  ├ #4 compile_unit_conversion_emits_grel
  │  ├ #5 compile_composite_separate_triplesmap (parse composition_expr) [review-1]
  │  ├ #6 compile_subject_template_uses_identifier_slot
  │  ├ #7 compile_sources_placeholder
  │  ├ #8 compile_json_format_uses_jsonpath_verbatim (no re-wrap)  [review-6]
  │  ├ #9 compile_missing_source_schema_raises
  │  ├ #10 compile_no_identifier_slot_raises
  │  ├ #11 compile_composite_subject_is_parent_slash_slot   [review-5, NEW]
  │  ├ #12 compile_subject_uses_source_prefix               [review-4, NEW]
  │  └ #13 compile_composition_expr_parser                  [review-1, NEW]
  └────────────────────────────────────────────────┘
```

## What already exists

- **16-01 TransformSpec builder** — committed 3f21a32. Produces TransformSpec YAML with `comments=["rosetta:source_format=<fmt>"]` and composite SlotDerivations with joint `composition_expr`.
- **16-00 schema annotations** — `rosetta-ingest` stamps `annotations.rosetta_source_format` on schema + per-slot `rosetta_csv_column` / `rosetta_jsonpath` / `rosetta_xpath`. Locked 16-02 contract.
- **linkml-map 0.5.2 upstream** — `Compiler` ABC, `CompiledSpecification`, `J2BasedCompiler`. The fork base is expected to track upstream `main`, which should be ≥ 0.5.2 when forked.

## Dream-state delta

Phase 16 whole pipeline after 16-03:

```
data.csv / data.json / data.xml
    │
    ├── rosetta-ingest ──> source.linkml.yaml (with annotations)
    │
SSSOM audit log (curated) ──> rosetta-yarrrml-gen ──> TransformSpec.yaml (self-describing)
                                                        │
                                                        ▼
                                     linkml-tr compile yarrrml ──> YARRRML.yaml
                                                        │
                                                        ▼
                                         morph-kgc ──> N-Triples
                                                        │
                                                        ▼
                          linkml gen-jsonld-context + rdflib ──> JSON-LD
```

Plan 16-02 delivers the middle step. After this, Plan 16-03 wires morph-kgc execution + JSON-LD framing. The self-describing TransformSpec locked here (absolute-path `source_schema` + `target_schema` + merged `prefixes`) is the reason 16-03 can run without re-specifying schemas on the command line.

## Completion summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD + harden                               |
| System audit         | 5 pre-review checks, 2 latent bugs caught   |
| Step 0               | HOLD; no scope delta                         |
| Section 1  (Arch)    | 0 issues (fork subclassing sound)           |
| Section 2  (Errors)  | 9 error paths mapped, 2 CRITICAL GAPS       |
| Section 3  (Security)| 0 High severity                             |
| Section 4  (Data/UX) | 6 edge cases mapped (shadow paths), 0 unhandled |
| Section 5  (Tests)   | Diagram produced; +4 new tests ID'd          |
| Section 6  (Future)  | Reversibility good (fork unpin = revert)     |
+--------------------------------------------------------------------+
| Section 7  (Eng Arch)| 1 contract fix (16-01 composite shape)      |
| Section 8  (Code Ql) | 0 DRY violations                            |
| Section 9  (Eng Test)| Test diagram produced; 7 new tests           |
| Section 10 (Perf)    | 0 issues (compiler is I/O-bound, ~KB output)|
+--------------------------------------------------------------------+
| PLAN.md updated      | 13 [review] truths added, 1 artifact added  |
| CONTEXT.md updated   | 9 [review] decisions locked                  |
| Error/rescue registry| 9 codepaths, 2 CRITICAL → truths             |
| Failure modes        | 3 total, 2 CRITICAL → tests                  |
| Delight opportunities| 0 (HOLD)                                    |
| Diagrams produced    | 3 (data flow, shadow paths, test coverage)  |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## Unresolved decisions

None. All 6 findings decided by user; remaining minor issues folded into truths without requiring a choice.
