---
phase: 17
plan: 1
title: "QUDT-native multi-library unit detection"
status: complete
completed: 2026-04-17
test_metrics:
  total: 367
  passing: 367
  deselected_slow: 3
  new_since_phase16: 35
  spec_tests_count: 0
---

# Summary — Plan 17-01

## What Shipped

- `detect_unit(name, description)` now returns QUDT IRI strings directly (`"unit:M"`, `"unit:MegaHZ"`, …) or `None`. The two-step `detect_unit → UNIT_STRING_TO_IRI.get` indirection is gone.
- **`UNIT_STRING_TO_IRI` deleted** from `rosetta/core/units.py`. Single source of truth for the pint→IRI map is `_PINT_TO_QUDT_IRI` inside `unit_detect.py`.
- **Three-layer cascade** in `detect_unit`:
  1. `_NAME_PATTERNS` — end-anchored regex on field name.
  2. `_DESC_PATTERNS` — prose regex on description.
  3. `_detect_from_nlp` — quantulum3 extracts candidates, pint canonicalises, `_PINT_TO_QUDT_IRI` maps to QUDT IRI. Lazy imports; module-level `_ureg` singleton; `ImportError`, `q3.parse()` exceptions, and `parse_expression` exceptions all collapse to `None`.
- **Expanded unit coverage:** 9 new QUDT IRIs emitted (HZ/KiloHZ/MegaHZ/GigaHZ, MilliRAD, HectoPa, DEG_F, MI-PER-HR, M-PER-SEC). Matching TTL triples added to `rosetta/policies/qudt_units.ttl` (26 units total, +8 new; `unit:MIN` was already present).
- **`rosetta-lint` wired to IRI output:** `_check_units` passes `row.subject_label` / `row.object_label` as the description arg so the NLP layer is reachable on real inputs. Message text now carries IRIs (`unit:KiloM vs unit:M`).

## Files Changed

- `rosetta/core/unit_detect.py` — full rewrite (regex tables → IRI, NLP cascade added)
- `rosetta/core/units.py` — `UNIT_STRING_TO_IRI` dict and its comment block removed
- `rosetta/cli/lint.py` — drop lookup; thread description; IRI-carrying messages
- `rosetta/policies/qudt_units.ttl` — +8 unit entries
- `rosetta/tests/test_unit_detect.py` — IRI-based assertions; NLP-path tests added
- `rosetta/tests/test_lint.py` — obsolete `UNIT_STRING_TO_IRI` tests removed; dBm message-text assertion relaxed
- `pyproject.toml`, `uv.lock` — `quantulum3` + `pint` added

## Verification

| Gate | Result |
|------|--------|
| `ruff format` | clean |
| `ruff check` | clean |
| `basedpyright` | 0 errors |
| `pytest -m "not slow"` | 367 passed, 3 deselected |
| `radon cc rosetta/core/ -n C -s` | no C+ grade |
| `vulture --min-confidence 80` | clean |
| `bandit -ll` | no issues |
| `refurb` | clean |

## Notes for Next Phase

- `quantulum3` emits a `DeprecationWarning` from `re.sub(..., re.IGNORECASE)` passed positionally. Non-actionable from our side; pin/upstream fix eventually.
- Name-pattern matcher is still permissive on short suffixes (`_m$`, `_pa$`). No false positives observed in the current test corpus, but corpus-driven precision/recall is deferred.
- `_check_units` now exercises the NLP layer through `row.subject_label`; lint performance impact is bounded by quantulum3's parse cost per row and has not been measured end-to-end on large SSSOM inputs.
