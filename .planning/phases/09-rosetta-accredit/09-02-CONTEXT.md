---
phase: 9
plan: 2
generated_by: plan-review
---

# Phase 9 Plan 02 — Context

## Locked Decisions

- [D-09-03] Feedback mechanism: accredited → multiply score by 1.2 capped at 1.0; revoked → exclude from list.
- [D-09-04] `apply_ledger_feedback` lives in `rosetta/core/similarity.py` (not a new module).
- [D-09-05] `Ledger` is imported under `TYPE_CHECKING` only in `similarity.py` — no circular import risk since `models.py` does not import from `similarity.py`.

## Decisions (added in review)

- [review] Use `TYPE_CHECKING` guard for `Ledger` import in `similarity.py`, NOT a forward-ref string or local import. Reason: basedpyright strict mode on `rosetta/core/` requires the type to be statically resolvable.
- [review] The `{**c, "score": ...}` pattern is required in the accredited branch to preserve all input dict keys (including `rank`). The earlier plan had `{"uri": target, "score": ...}` which produced a mixed-shape list.
- [review] After `apply_ledger_feedback`, re-sort by score descending and re-assign 1-based `rank` values before building `SuggestionReport`. Reason: boosted items must surface to the top; stale ranks would mislead callers.
- [review] Top-level imports only in `suggest.py` (`load_ledger`, `apply_ledger_feedback`). Inline imports inside the `if ledger is not None:` block fail ruff `PLC0415`.
- [review] `uv run python -c` not `python3 -c` in `pipeline.sh`. System `python3` may not have rosetta installed.
- [review] `test_boost_cap_at_1` must NOT declare `tmp_path` — unused fixture parameter triggers ruff `ARG001`.
- [review] 8 integration tests, not 5. Added: `test_empty_candidates` and `test_suggest_cli_with_ledger` (CliRunner end-to-end).

## Deferred Ideas

- O(1) ledger lookup dict (`{(src, tgt): entry}`) — already incorporated into the plan per review finding. Not deferred.
- Ledger size warning at load time if `len(mappings) > 10_000` — deferred, not needed for MVP.
- `pipeline.sh` self-test mode (verify output JSON shapes with assertions) — deferred, script is a demo not a test harness.
