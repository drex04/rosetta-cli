---
plan: 19-01
title: rosetta-shacl-gen — auto-generate SHACL from master LinkML
status: complete
commit: 6946a29
completed: 2026-04-19
test_metrics:
  total: 443
  pass: 443
  new_tests: 11   # 7 test_shacl_gen + 4 test_unit_detect
  spec_tests_count: 0
quality_gates:
  ruff_format: pass
  ruff_check: pass
  basedpyright: pass (0 errors in Phase 19 files)
  pytest_not_slow: pass (443/443)
  radon_core: pass (no grade C+)
  vulture: pass (no dead code at confidence 80)
  bandit: pass (0 issues)
  refurb: pass (0 findings, after fix-on-sight)
  mkdocs_strict: pass
---

# Plan 19-01 — Build Summary

## Implemented

| Task | Status | Files |
|---|---|---|
| T0 — Extend `detect_unit` for master COP slot patterns | ✅ | `rosetta/core/unit_detect.py`, `rosetta/tests/test_unit_detect.py` |
| T1 — `RosettaShaclGenerator` (chose **wrapper** over subclass) | ✅ | `rosetta/core/shacl_generator.py` |
| T2 — `rosetta-shacl-gen` Click CLI | ✅ | `rosetta/cli/shacl_gen.py` |
| T3 — `pyproject.toml` console-script entry point | ✅ | `pyproject.toml` |
| T4 — Unit + behavioral tests | ✅ | `rosetta/tests/test_shacl_gen.py` (7 tests) |
| T5 — Documentation | ✅ | `docs/cli/shacl-gen.md`, `mkdocs.yml`, `README.md` |
| T6 — Quality gates | ✅ | All 9 mandatory checks pass |

## Truth verification (must_haves)

| Truth | Evidence |
|---|---|
| 1. CLI writes valid SHACL Turtle | T4 `test_generates_valid_turtle` + T2 smoke (130KB output, 3985 triples) |
| 2. Closed default + 5-IRI ignored-properties list | T4 `test_closed_default_adds_sh_closed_true` + `test_closed_default_adds_ignored_properties` |
| 3. `--open` produces open shapes | T4 `test_open_flag_omits_closed_and_ignored` |
| 4. QUDT-mapped slots get `qudt:hasUnit` shapes | T4 `test_unit_aware_shape_emitted_for_qudt_slot` (asserts at least one of `unit:KN`/`unit:DEG`/`unit:FT-PER-MIN`/`unit:FT` fires) |
| 5. Closed-world typo guard | T4 `test_validates_conformant_graph_and_rejects_typo` (`mc:hasAltidude` typo → `sh:ClosedConstraintComponent` violation) |
| 6. **[review]** Extended `detect_unit` covers Knots/Bearing/Degrees/VerticalRate | T0 4 new tests pass; `detect_unit("hasSpeedKnots")` → `unit:KN`, etc. |

## Spike outcome (D-19-14)

**Wrapper module chosen** (no subclass needed). Module docstring records:
- `closed: bool = True` is settable via `ShaclGenerator(schema_path, closed=...)` constructor.
- `as_graph() -> rdflib.Graph` is the direct entry point for post-walk.
- Upstream's existing `sh:ignoredProperties` rdf:List is extended in-place by `_rebuild_ignored_properties` (delete + recreate with merged URIs).

## Fix-on-Sight (deviation)

Encountered during quality-gate run, fixed in same commit per CLAUDE.md rule:

- **CLAUDE.md refurb command was wrong:** `uv run refurb rosetta/ rosetta/tests/` triggered mypy "Duplicate module" path collision because `rosetta/tests/` is already nested under `rosetta/`. Corrected to `uv run refurb rosetta/` (matches the pre-commit hook). Pre-existing — would have surfaced on next CI gate.
- **4 refurb findings in new code resolved:**
  - `shacl_generator.py:87` FURB138 — converted `for/append` to list comprehension
  - `shacl_generator.py:112` FURB123 — kept `list(merged)` (Collection needs `list[Node]`, `merged.copy()` narrowed to `list[URIRef]` causing basedpyright error); suppressed with inline noqa + comment
  - `shacl_generator.py:188` FURB184 — chained `ShaclGenerator(...).as_graph()` instead of intermediate `gen` var
  - `test_shacl_gen.py:217` FURB184 — chained `CliRunner(...).invoke(cli, [...])` instead of intermediate `runner` var

## Issues Encountered

None blocking. All quality gates clean on commit; pre-commit hooks all passed.

## Concerns for downstream plans

- **Plan 19-02:** the now-committed `rosetta/policies/shacl/generated/master.shacl.ttl` will be 130KB (3985 triples). When 19-02 commits this artifact, expect a meaningful diff in the policies tree.
- **Plan 19-03:** `generate_shacl()` is the source of truth for shapes. If 19-03's `--validate` flow ever needs to regenerate shapes inline (it currently doesn't — it loads from `--shapes-dir`), it can call `generate_shacl()` directly.

## Cross-session output

**[plan-build-output]** Phase 19 Plan 19-01: COMPLETE. Commit `6946a29`. Tests 443/443. New CLI: `rosetta-shacl-gen`. New module: `rosetta/core/shacl_generator.py` (wrapper, not subclass). Extended `detect_unit` for 3 slot patterns (Knots/Bearing/VerticalRate). All 6 truths verified.
