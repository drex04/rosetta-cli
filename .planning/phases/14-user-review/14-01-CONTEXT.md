---
phase: 14
plan: "01"
title: "audit-log accreditation pipeline"
---

# Context: Phase 14-01

## Locked Decisions (from plan-work 2026-04-15)

### Audit log

- **Single append-only log** (`audit-log.sssom.tsv`) is the single source of truth for all accreditation decisions. Path configured via `rosetta.toml [accredit].log`; default `store/audit-log.sssom.tsv`.
- **Only `rosetta-accredit ingest` writes to the log.** `rosetta-suggest` and `rosetta-lint` read it; they never write.
- **Log contains only human decisions**: `ManualMappingCuration` (analyst proposals) and `HumanCuration` (accreditor decisions). `CompositeMatching` rows are never ingested. The suggest output (`candidates.sssom.tsv`) is the ephemeral artifact preserving `CompositeMatching` provenance.
- **Append-only, latest wins**: for a given (subject_id, object_id) pair, the most recent row (by `mapping_date`) is the current state. Corrections are applied by ingesting a new row.
- **`mapping_date`** (ISO 8601) and **`record_id`** (UUID4) are stamped by `accredit ingest` at write time — never set by humans editing files.

### SSSOMRow model

- Add `mapping_date: datetime | None = None` — stamped by ingest
- Add `record_id: str | None = None` — UUID4 stamped by ingest
- Remove `Ledger` and `LedgerEntry` models from `models.py`. `MappingDecision` is retained (RML generation).

### State machine (enforced by `accredit ingest`)

| Row type being ingested | Rule |
|-------------------------|------|
| `ManualMappingCuration` | BLOCK if pair has **any** `HumanCuration` row in log (approved or rejected — final) |
| `HumanCuration` | BLOCK if pair has **no** `ManualMappingCuration` predecessor in log |
| `HumanCuration` correction | Allowed — new `HumanCuration` over existing `HumanCuration`; latest wins |

Consequence: once an accreditor makes any decision (approve or reject), the analyst cannot re-propose that pair. Only the accreditor can reverse the decision by ingesting a corrected `HumanCuration` row.

### `rosetta-accredit` command surface

Replaces `submit / approve / revoke / status` + `ledger.json` entirely.

| Command | Purpose |
|---------|---------|
| `ingest <file.sssom.tsv>` | Validate and append ManualMappingCuration or HumanCuration rows to log |
| `review [-o FILE]` | Output ManualMappingCuration rows with no HumanCuration yet (pending proposals) |
| `status [--source] [--target]` | Show current state per pair |
| `dump [-o FILE]` | Export current HumanCuration rows for pipeline use |

Global option: `--log PATH` (replaces `--ledger PATH`).

### `rosetta-suggest` behavior change

- **Remove `--approved-mappings` flag.** Log is read automatically from `rosetta.toml [accredit].log` if the file exists. If log path is not configured or file is absent, suggest runs without boost/derank (backward-compatible).
- **Existing-pair merge**: for each computed candidate, if (subject_id, object_id) already has a row in the log, include that log row in `candidates.sssom.tsv` with `mapping_justification` and `predicate_id` preserved, but `confidence` updated to the freshly computed score. No filtering — all candidates are always returned.
- Boost/derank is applied using `HumanCuration` rows from the log (same `apply_sssom_feedback` logic; `owl:differentFrom` = derank, any other predicate = boost).

### `rosetta-lint --sssom` mode

New mode: `rosetta-lint --sssom candidates.sssom.tsv`

Checks (log path read from config; optional — conflict check skipped if no log configured):
1. **MaxOneMmcPerPair** — at most 1 `ManualMappingCuration` per (subject_id, object_id)
2. **NoHumanCurationReproposal** — no `ManualMappingCuration` for a pair that has any `HumanCuration` in the log
3. **ValidPredicate** — `predicate_id` must be a recognised SKOS or OWL mapping predicate

Unit/datatype compatibility checks: **deferred** to a future plan (requires linkage between SSSOM subject_id/object_id URIs and LinkML YAML schema slots — out of scope for Phase 14).

### `ledger.json` removal

- `ledger.json` is removed entirely.
- `Ledger`, `LedgerEntry` Pydantic models removed from `models.py`.
- Old `accredit` CLI subcommands (`submit / approve / revoke` with `--ledger`) removed.
- All existing ledger-based tests replaced by log-based tests.

## Deferred Ideas

- **Unit/datatype compatibility checks in lint SSSOM mode**: requires resolving subject_id/object_id URIs to LinkML YAML schema slots. Deferred to Phase 15 or a lint-extension plan.
- **`--approved-mappings` backward-compat alias**: not added — clean break with the ledger-based API is intentional.
- **`mapping_id` for optimistic concurrency**: deferred — state-machine enforcement in `ingest` provides sufficient protection.
- **`rosetta-suggest --no-log` flag**: deferred — if log is absent/unconfigured, suggest already runs without boost/derank.
