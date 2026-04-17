# Plan Review (Pass 2) — Phase 17-01 QUDT-Native Unit Detection

**Date:** 2026-04-17
**Mode:** HOLD (plan already reviewed once, 17 `[review]` truths carried; second pass)
**Gate:** WARN — plan is buildable after adding 2 new truths

## System Audit

- `rosetta/policies/qudt_units.ttl` has 17 `qudt:Unit` entries; `unit:MIN` already present (Task 2 SPARQL-verify truth is low-risk).
- TTL additions Task 2 brings: HZ, KiloHZ, MegaHZ, GigaHZ, MilliRAD, HectoPa, DEG_F, MI-PER-HR (8 new).
- `UNIT_STRING_TO_IRI` has 3 call-site clusters: `lint.py` (lines 15, 161–162), `units.py` (line 22 — definition), `test_lint.py` (lines 14, 37, 41, 45–46, 50; also a comment at line 420).
- `detect_unit()` has no callers outside `cli/lint.py::_check_units` and its test file.
- `_check_units` passes `description=""` to `detect_unit` — description path/NLP cascade is unreachable from production.

## New Findings (beyond the 17 existing `[review]` truths)

### CRITICAL — PLAN body vs. truths drift

The 17 `[review]` truths mandate concrete code changes, but the task bodies in PLAN.md were not regenerated and still show the pre-review code. Conflicts the executor will hit:

| Truth | Stale plan body |
|-------|-----------------|
| Split `deg|grad|grader` and `rad|radians?` | Line 208: combined `(?:deg\|grad\|grader\|rad\|radians?)` |
| `_ureg` module-level singleton | Line 337: `ureg = UnitRegistry()` per call |
| Wrap `q3.parse()` in try/except | Lines 338-345: try wraps only `parse_expression` |
| ImportError → return None | No guard shown |
| Task 5 preserves `_unit_label()` | Lines 387-388: shows `subject_id.split(":")[-1]` |
| Delete 4 detect_unit tests from test_lint.py | Lines 517-529: instructs ADD them |

→ Resolution: new truth `[review-2]` added that makes truths canonical over stale task bodies.

### WARNING — NLP cascade dead code at phase end

Task 3 adds quantulum3 + pint (heavy deps, spaCy model) + `_PINT_TO_QUDT_IRI` for a code path that `_check_units` never triggers (passes `description=""`). Either remove the NLP layer or thread description through. Chose the latter — cheap, preserves scope intent.

→ Resolution: new truth `[review-2]` mandates `_check_units` pass `row.subject_label` / `row.object_label` as the description arg.

## What Already Exists

- `_unit_label()` helper at lint.py:123 works as described by the `[review]` truth.
- `qudt_units.ttl` already includes `unit:MIN`, `unit:DEG`, `unit:RAD`, `unit:M-PER-SEC`, `unit:KiloM-PER-HR` — all referenced by the new `_PINT_TO_QUDT_IRI` table.
- Existing test `test_lint_sssom_unit_no_iri_mapping` comment at test_lint.py:420 still references `UNIT_STRING_TO_IRI["dBm"] is None` — should be refreshed alongside the Issue-4 message-text relaxation already captured in truths.

## Completion Summary

| Section | Status |
|---------|--------|
| Mode | HOLD (2nd-pass review) |
| System audit | 2 new concrete state checks (TTL count, _check_units empty desc) |
| Step 0 | No scope change — HOLD reaffirmed |
| Section 1–6 (business) | No new issues beyond pass 1 |
| Section 7 (eng arch) | 1 CRITICAL (truth/body drift) |
| Section 8 (code quality) | 1 WARNING (NLP dead code) |
| Section 9 (eng test) | No new gaps; comment refresh at test_lint.py:420 optional |
| Section 10 (perf/security) | No new issues |
| PLAN.md updated | 2 truths added (`[review-2]`) |
| CONTEXT.md updated | 2 decisions logged (`[review-2]`) |
| Unresolved | None |

## Cross-Session Output

**[plan-review-learning]** When a plan is re-reviewed and truths are added, the task bodies/code snippets often go stale and contradict the truths — document in CONTEXT.md that truths are canonical, or regenerate task bodies, to keep the executor from flipping a coin.
