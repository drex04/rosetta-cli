# Comprehensive Review — Full Codebase (2026-04-18)

Scope: entire `rosetta/` source tree. Phase 18 complete, all v2.0 phases closed.

## Evidence (all gates green)
- ruff format: 70 files formatted ✅
- ruff check: pass ✅
- basedpyright (core+cli strict): **0 errors**, 449 warnings ✅
- pytest -m "not slow": **424 passed**, 9 deselected, 0 failed ✅
- radon cc -n C: no grade C+ ✅ (highest B/CC 10)
- radon mi: all files grade A
- vulture: 0 findings ✅
- bandit: 0 med/high, 2 low (assert_used, try_except_continue)
- refurb: 0 findings ✅

## Findings

### Critical — none

### Important (should fix)

**I1. Pydantic models missing `extra="forbid"`** (both agents flagged)
- `rosetta/core/models.py` — only `CoverageReport` has it; 12 others do not
- Highest risk: `SSSOMRow` (constructed from external TSV)
- Per memory `feedback_pydantic_silent_extra_fields.md` — prior production bug pattern
- Fix: add `model_config = ConfigDict(extra="forbid")` to all user-facing models

**I2. Private-symbol leak across CLI/core boundary**
- `rosetta/cli/ingest.py:11-16` imports `_detect_format`, `_stamp_slot_paths`, `_stamp_source_format`
- Fix: promote to public (drop `_`) or wrap in `normalize_schema(stamp=True)`

**I3. `rosetta-accredit review`/`dump` emit 13-column header but only populate 9**
- `rosetta/cli/accredit.py:121-133, 208-221` bypass `SSSOMRow`; trailing 4 columns always empty
- Fix: drive serialization from `AUDIT_LOG_COLUMNS` via `SSSOMRow.model_dump`

**I4. `_adjusted_score` branches untested directly**
- `rosetta/core/similarity.py:101-122` — 4 branches (exact-diff-from, soft-subject-breadth 0.25 coeff, boost match, passthrough) covered only transitively
- Fix: add unit tests in `test_suggest.py` for boundaries and the 0.25 coefficient

### Minor

- `rosetta/cli/embed.py:69-76` — non-conditional imports inside handler; move to module level
- `rosetta/cli/yarrrml_gen.py:235` — `assert data is not None` becomes a runtime NoneType error under `python -O`; replace with `ClickException`
- `rosetta/core/unit_detect.py:189` — broad `except Exception: continue` swallows errors silently; narrow to `(ValueError, AttributeError, ArithmeticError)` and add `_log.debug(exc)`
- `rosetta/core/lint.py:29-30` — local `MMC`/`HC` duplicates `MMC_JUSTIFICATION`/`HC_JUSTIFICATION` in `accredit.py`; import instead
- `rosetta/core/similarity.py:141` — `import copy` inside function; move to module top

### Nitpick

- `test_similarity.py` / `test_units.py` files don't exist; tests live in sibling files. Functional but non-obvious for triage

### Deprecation watch

- `schema_automator` (via `normalize.py`) drives most of the 1269 pytest warnings; add `filterwarnings` to `pyproject.toml` until upstream fixes
- `funowl` `typing._eval_type` → Python 3.15 upstream issue; no action until 3.15 is our minimum

## Strengths
- Clean layering: core is genuinely Click-free
- Error surface uniform across all 8 CLIs (exit 1, stderr, `open_output`)
- SSSOM state machine correctly implemented (dual-predicate revocation, 9-column backward compat, conditional justification)
- Atomic migration via `os.replace` in `accredit.py`

## Gate Decision: WARN
All gates pass. Two important findings (I1 + I3) converged across both agents. No runtime/test failures. Fix-on-sight per CLAUDE.md applies.

## Architecture Score: 8/10
