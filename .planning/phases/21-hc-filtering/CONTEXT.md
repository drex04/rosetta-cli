# Phase 21: HumanCuration Filtering — Decisions

## D-21-01: Filtering function extraction
**Decision:** Extract `filter_decided_suggestions()` as a standalone function in `similarity.py` with its own unit tests.
**Why:** User preference for testable units, even though the logic is simple (two set lookups).

## D-21-02: Lint audit-log always required
**Decision:** `--audit-log` becomes required on `rosetta lint`. If the file doesn't exist, create a blank one at the given path.
**Why:** HC-in-candidates detection needs the audit log context. Creating a blank file avoids user friction on first run.

## D-21-03: HC rows in candidates always BLOCK
**Decision:** Any row in candidates with `mapping_justification == semapv:HumanCuration` produces a BLOCK finding, unconditionally (not gated by audit log contents).
**Why:** HC rows belong exclusively in the audit log. Their presence in a candidates file is always a mistake.

## D-21-04: Remove ALL derank functionality
**Decision:** Delete `apply_sssom_feedback()`, `_adjusted_score()`, and all penalty-based scoring. No soft deranking of sibling candidates when a rejection exists.
**Why:** User decision — derank replaced entirely by binary filtering (approved subject → remove all; rejected pair → remove pair only).

## D-21-05: Keep log_index refresh logic
**Decision:** The `log_index` refresh that updates `mapping_justification` and `predicate_id` for existing pairs stays in `suggest.py`.
**Why:** Pre-existing analyst proposals (not yet reviewed) should still appear in suggestions with their current log state.

## D-21-06: Approved = subject-level, Rejected = pair-level
**Decision:** Approved HC (predicate != `owl:differentFrom`) filters ALL suggestions for that subject. Rejected HC (`owl:differentFrom`) filters only that specific (subject, object) pair.
**Why:** An approved mapping means the subject is fully resolved — no more suggestions needed. A rejection only invalidates that specific candidate.

## [review] D-21-07: Approved wins over rejected for same subject
**Decision:** If subject X has an approved HC mapping (for any object) AND a rejected HC mapping (for a different object), the subject-level approved filter wins — all suggestions for X are removed.
**Why:** Subject-level approval means the subject is fully resolved. A rejection for a different pair on the same subject is moot.

## [review] D-21-08: filter_decided_suggestions returns new dict
**Decision:** `filter_decided_suggestions` returns a new dict, does not mutate the input.
**Why:** Consistent with the old `apply_sssom_feedback` deep-copy pattern. Prevents caller surprises.

## [review] D-21-09: Auto-create audit-log with mkdir and clean error
**Decision:** Auto-create wraps in `try/except OSError` → `click.UsageError`. Uses `parent.mkdir(parents=True, exist_ok=True)` before `touch()`.
**Why:** Review found that bare `touch()` fails with traceback if parent dir is missing or path is unwritable.

## [review] D-21-10: No config fallbacks anywhere
**Decision:** Remove ALL `get_config_value` usage from ALL CLI commands. Every input must be an explicit CLI flag — either `required=True` or with a hardcoded `default`. `rosetta.toml` and `config.py` left in place for later cleanup.
**Why:** User wants all inputs explicit. Config-based resolution hides state and breaks reproducibility. Manual cleanup pass planned later.

## Deferred Ideas
- Config module cleanup (`rosetta/core/config.py`, `rosetta.toml`) — deferred to user's manual pass
- TypedDict for `rank_suggestions` return shape — pre-existing weak typing, not Phase 21 scope
