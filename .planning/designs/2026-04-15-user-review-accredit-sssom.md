# Design: Audit-Log Accreditation Pipeline (Phase 14-01)
**Date:** 2026-04-15

## Problem

The existing `rosetta-accredit` state machine (`submit/approve/revoke` + `ledger.json`) does not fit the two-role (Analyst + Accreditor) workflow and has no connection to SSSOM. Suggestion boost/derank requires a separate `--approved-mappings` flag pointing to a manually maintained file.

## Approved Design

### Single append-only audit log

`audit-log.sssom.tsv` is the single source of truth for all human accreditation decisions. It is an append-only SSSOM TSV file containing only `ManualMappingCuration` (analyst proposals) and `HumanCuration` (accreditor decisions). `CompositeMatching` rows are never written to the log.

`rosetta-accredit ingest` is the only writer. `rosetta-suggest` and `rosetta-lint` are readers.

### Workflow

```
suggest → candidates.sssom.tsv
  ↓
Analyst edits (ManualMappingCuration rows)
  ↓
lint --sssom (structural checks) → fix errors → re-lint
  ↓
accredit ingest (ManualMappingCuration → log)
  ↓
accredit review → review.sssom.tsv
  ↓
Accreditor edits (HumanCuration rows: approve=keep-predicate, reject=owl:differentFrom)
  ↓
accredit ingest (HumanCuration → log)
  ↓
next suggest run reads updated log (boost/derank automatic)
```

### State machine

| Transition | Rule |
|-----------|------|
| ingest ManualMappingCuration | BLOCK if any HumanCuration exists for pair |
| ingest HumanCuration | BLOCK if no ManualMappingCuration predecessor |
| ingest HumanCuration correction | Allowed — latest wins |

Once rejected, only the Accreditor can reverse (by ingesting a new HumanCuration row). Analyst cannot re-propose after any accreditor decision.

### SSSOMRow extensions

- `mapping_date: datetime | None` — stamped by accredit ingest
- `record_id: str | None` — UUID4 stamped by accredit ingest

### Command surface

| Command | Replaces |
|---------|---------|
| `accredit ingest <file>` | `submit` + `approve` |
| `accredit review [-o]` | (new) |
| `accredit status` | `status` |
| `accredit dump [-o]` | (new) |

`ledger.json`, `Ledger`, `LedgerEntry`, `--ledger`, `submit`, `approve`, `revoke` all removed.

### suggest changes

- `--approved-mappings` flag removed
- Log read automatically from `rosetta.toml [accredit].log`
- Existing-pair merge: pairs already in log carry their log row's justification+predicate with freshly computed confidence

### lint --sssom mode

`rosetta-lint --sssom candidates.sssom.tsv` checks:
1. MaxOneMmcPerPair — at most 1 ManualMappingCuration per pair
2. NoHumanCurationReproposal — no re-proposal of decided pairs
3. ValidPredicate — valid SKOS/OWL vocabulary

## Alternatives Considered

- **GUID in subject_id**: rejected — breaks SSSOM semantics; state-machine enforcement is the right protection
- **suggest appending to log**: rejected — makes suggest stateful; double-run causes duplicate rows
- **lint appending to log**: rejected — premature commitment; lint is a validator, not a writer
- **separate rosetta-review tool**: rejected — file editing is sufficient for now; web GUI deferred
- **CompositeMatching rows in log**: rejected — log records decisions only; suggest output is the provenance artifact
- **Two plans (review tool + accredit migration)**: reduced to one plan — review tool dropped entirely
