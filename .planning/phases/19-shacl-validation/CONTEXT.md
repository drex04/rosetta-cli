# Phase 19 — SHACL validation refactor

**Goal:** Refit `rosetta-validate` to the v2.0 pipeline. Auto-generate SHACL shapes from the master LinkML schema, expose a clean override workflow for hand edits, and wire validation into `rosetta-yarrrml-gen --run` against the in-memory materialized graph (blocking JSON-LD emission on violation).

**Status:** planning. v2.0 (Phases 12–18) complete; legacy `rosetta/policies/mapping.shacl.ttl` targets retired v1 `rose:Field` / `rose:Mapping` classes and will be deleted in 19-02.

---

## Locked decisions (from planning session 2026-04-18)

| # | Decision | Rationale |
|---|---|---|
| D-19-01 | Three plans: 19-01 generator, 19-02 override workflow, 19-03 pipeline wiring + JSON-LD input | Each stays under 6 tasks; matches the user's three asks (auto-gen, edit, validate) |
| D-19-02 | New CLI `rosetta-shacl-gen` (separate tool, Unix-composable) — not a `--generate` flag on `rosetta-validate` | Matches every other tool's one-responsibility shape; lets generated shapes live in version control independently from validation |
| D-19-03 | Wrap `linkml.generators.shaclgen.ShaclGenerator` rather than hand-rolling | Keeps source-of-truth in the LinkML schema; transitive dep already present |
| D-19-04 | Override strategy: `rosetta/policies/shacl/generated/` (regen output, never hand-edited) + `rosetta/policies/shacl/overrides/` (user shapes, regen-safe) | Simplest model; works with existing `--shapes-dir` recursive merge; survives regen without parser tricks |
| D-19-05 | `rosetta-yarrrml-gen --validate` runs pySHACL on the in-memory `rdflib.Graph` from `rml_runner.run_materialize`, **before** `graph_to_jsonld` | No re-parse cost; blocks emission cleanly |
| D-19-06 | `--validate` blocks JSON-LD emission on any violation; exit 1; no partial JSON-LD file written | Same fail-fast contract as Phase 18 hardening for `--run` validation |
| D-19-07 | `rosetta-validate --data` accepts JSON-LD (`.jsonld`/`.json`) in addition to Turtle, autodetected by suffix or explicit `--data-format` | The v2 pipeline's terminal artifact is JSON-LD; standalone validation must work on it |
| D-19-08 | Shared validation helper: new `rosetta/core/shacl_validate.py` with `validate_graph(graph, shapes_graph) -> ValidationReport`. Both `rosetta-validate` and `rosetta-yarrrml-gen --validate` call it. | Single source of truth for SHACL invocation + report shape; avoids drift between the two entrypoints |
| D-19-09 | Drop legacy `rosetta/policies/mapping.shacl.ttl` in 19-02 | Targets retired v1 vocabulary (`rose:Field`/`rose:Mapping`); no v2 consumer |
| D-19-10 | **Closed-world default** with `sh:ignoredProperties` baked in for `prov:*`, `dcterms:*`, `rdf:type`. `--open` flag emits open-world shapes. | Catches predicate-name typos in YARRRML (highest-value mistake at this layer); ignored-list survives downstream PROV-O stamping |
| D-19-11 | **Full ownership of the SHACL generator:** subclass `linkml.generators.shaclgen.ShaclGenerator` in `rosetta/core/shacl_generator.py`. Inject closed-default + ignored-properties + **unit-aware value shapes** (`qudt:hasUnit` constraint from `slot.unit.ucum_code` / QUDT annotations). | Vanilla `ShaclGenerator` ignores QUDT unit info, which is the most v2-pipeline-specific signal we can validate. Subclass gives a single extension point. |
| D-19-12 | **[review]** Plan 19-01 ships with extended `detect_unit` coverage (`Knots` → `unit:KN`, `Bearing`/`Degrees` → `unit:DEG`, `VerticalRate` + fpm-description → `unit:FT-PER-MIN`) so unit-aware shape generation has practical value on the master schema, not just `hasAltitudeM`. | System audit (2026-04-18) found only 1/6 sampled master slots produced a QUDT IRI. User picked option 2C: expand 19-01 scope to extend Phase-17 detection rather than ship a feature with thin coverage. Trade: minor scope creep into Phase 17 territory; benefit: closed-shape unit constraints fire on every unit-bearing master slot. |
| D-19-13 | **[review]** Plan 19-02 inlines the `test_validate.py` SHACL fixture (5-line `_SHAPES_TTL` string) instead of depending on `rosetta/policies/mapping.shacl.ttl`. | The legacy file was being reused as a generic test fixture, masking the v1-vocab-only purpose. Inlining decouples the tests from the policies dir layout, makes the test self-contained, and unblocks the legacy file deletion in 19-02 Task 1. Real-shape coverage is preserved by `test_validate_pipeline.py` integration tests. |
| D-19-14 | **[review]** Plan 19-01 Task 1 includes a ≤30-min spike to inspect `ShaclGenerator`'s constructor / public attribute surface before subclassing. If the spike shows `closed` + ignored-properties are achievable via constructor + a single `as_graph` post-walk, the subclass collapses to a thin wrapper. | System audit confirmed `ShaclGenerator.closed` is a public attribute. Avoid pre-committing to a subclass that may not be needed; document the spike outcome in the module docstring. |
| D-19-15 | **[review-harden]** Plan 19-03 Task 3 step-0 stdout-collision guard rejects all three pairwise combinations of `--output -`, `--jsonld-output -`, `--validate-report -`. Mirrors the existing `_check_stdout_collisions` pattern at `yarrrml_gen.py:134`. Three adversarial tests pin the contract. | User directive 2026-04-19: "don't defer anything, harden now." Failure-mode registry surfaced this as a CRITICAL gap; promoted from "Risks" note to a tested acceptance criterion. |
| D-19-16 | **[review-harden]** Shapes-dir discovery is extracted into `rosetta/core/shapes_loader.load_shapes_from_dir` (new in Plan 19-02 Task 4). Shared by `rosetta-validate` and `rosetta-yarrrml-gen --validate`. Uses `os.walk(followlinks=False)` to prevent symlink-loop hangs; emits stderr warning for any loaded `.ttl` containing zero `sh:NodeShape` / `sh:PropertyShape` triples (file is still merged — open-world principle). | Failure-mode registry surfaced symlink-loop and silent non-shape absorption as latent edges. Centralizing the walker prevents drift between the two CLI consumers. |
| D-19-17 | **[review-harden]** Non-shape Turtle policy: warn but still merge. The user explicitly placed the file in `--shapes-dir`; rosetta surfaces the surprise via stderr but does not second-guess the merge. | Alternative considered: warn + skip merge. Rejected — silent skip would be more surprising than silent absorption (user thinks file is loaded; it isn't). Warn-and-merge is explicit + safe. |

---

## Open gray areas (to resolve during plan brainstorms)

| # | Question | Notes |
|---|---|---|
| G-19-02 | **Generator output: one file or per-class?** | One `master.shacl.ttl` is simpler; per-class allows finer-grained override (drop one class, keep others). Default to one file; revisit if override granularity becomes an issue. |
| G-19-03 | **`--shapes-dir` discovery: should `rosetta-validate` learn a default `policies/shacl/` location?** | Currently `--shapes-dir` is required. Could default to `rosetta/policies/shacl/` if neither `--shapes` nor `--shapes-dir` is passed. Probably no — keeps the tool config-free. |
| G-19-04 | **Validation report destination for `--validate`:** stderr only, `--validate-report PATH`, or both? | Lean toward `--validate-report` flag; default to stderr summary line + non-zero exit. |

---

## Key references

- Existing validator: `rosetta/cli/validate.py:1-160`
- Legacy SHACL (to delete): `rosetta/policies/mapping.shacl.ttl`
- Master schema: `rosetta/tests/fixtures/nations/master_cop.linkml.yaml`
- Master ontology Turtle (parallel hand-authored): `rosetta/tests/fixtures/nations/master_cop_ontology.ttl`
- morph-kgc materialize entrypoint: `rosetta/core/rml_runner.py` (`run_materialize` yields `rdflib.Graph`)
- LinkML SHACL generator: `linkml.generators.shaclgen.ShaclGenerator`
- Pydantic models: `rosetta/core/models.py` (`ValidationReport`, `ValidationFinding`, `ValidationSummary` already exist — reuse)

---

## Plan files

- `19-01-PLAN.md` — `rosetta-shacl-gen` ✅ ready
- `19-02-PLAN.md` — Override workflow + legacy cleanup ✅ ready
- `19-03-PLAN.md` — `--validate` wiring + JSON-LD input ✅ ready

## Execution order

Plans must build sequentially:

1. **19-01 first** — generator must exist before 19-02 can populate `generated/master.shacl.ttl`.
2. **19-02 second** — `generated/master.shacl.ttl` artifact is referenced by 19-03's integration tests; recursive `--shapes-dir` from 19-02 is required by 19-03's `--validate` wiring.
3. **19-03 last** — wires the prior two together at the pipeline level.

`/fh:build` should run them in this order; do not parallelize.
