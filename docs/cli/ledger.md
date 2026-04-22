# rosetta ledger

Manages the two-role accreditation pipeline using an append-only audit log (`audit-log.sssom.tsv`). The log is the single source of truth for accreditation decisions and feeds directly into `rosetta suggest` (boost/derank) and `rosetta lint` (conflict checking).

For the conceptual flow and state machine, see [Accreditation workflow](../concepts/accreditation.md).

## Command reference

::: mkdocs-click
    :module: rosetta.cli.ledger
    :command: cli
    :prog_name: rosetta ledger
    :depth: 2

## Subcommand semantics

### `append FILE`

Requires `--role` (analyst or accreditor), `--source-schema`, and `--master-schema`. The append pipeline:

1. **Lint gate** — runs `rosetta lint` on all rows in the file (before role filtering). Any `BLOCK`-severity finding rejects the entire append; nothing is written. `WARNING`-severity findings are printed to stderr and the append continues.
2. **Role filtering** — after lint passes, only the rows matching the role are written:
   - `--role analyst` — accepts only `ManualMappingCuration` rows; `HumanCuration` rows trigger a `BLOCK`.
   - `--role accreditor` — accepts only `HumanCuration` rows; `ManualMappingCuration` rows are silently skipped.
3. **State-machine validation** — each accepted row is validated before writing. If any row violates a rule, all errors are printed to stderr and **nothing is written** — no partial writes.

Pass `--dry-run` to run the lint gate and state-machine checks without writing anything to the audit log. Useful for CI pre-flight checks.

### `review`

Outputs pending proposals — all `ManualMappingCuration` rows that have no corresponding `HumanCuration` decision yet — as SSSOM TSV. This is the Accreditor's work list.

### `dump`

Outputs the latest `HumanCuration` row per pair as SSSOM TSV — suitable for external pipeline consumption.

## Example session

### Analyst workflow

```bash
# 1. Generate candidates (audit-log read automatically from rosetta.toml)
uv run rosetta suggest nor.emb.json master.emb.json -o candidates.sssom.tsv

# 2. Analyst edits candidates.sssom.tsv, marking ManualMappingCuration rows.

# 3. Dry-run to verify lint and state machine before committing
uv run rosetta ledger append candidates.sssom.tsv \
  --role analyst \
  --source-schema schemas/nor.linkml.yaml \
  --master-schema schemas/master.linkml.yaml \
  --dry-run

# 4. Stage analyst proposals
uv run rosetta ledger append candidates.sssom.tsv \
  --role analyst \
  --source-schema schemas/nor.linkml.yaml \
  --master-schema schemas/master.linkml.yaml
```

### Accreditor workflow

```bash
# 5. Generate accreditor work list
uv run rosetta ledger review -o review.sssom.tsv

# 6. Accreditor edits review.sssom.tsv, marking HumanCuration rows.

# 7. Dry-run accreditor review
uv run rosetta ledger append review.sssom.tsv \
  --role accreditor \
  --source-schema schemas/nor.linkml.yaml \
  --master-schema schemas/master.linkml.yaml \
  --dry-run

# 8. Ingest decisions
uv run rosetta ledger append review.sssom.tsv \
  --role accreditor \
  --source-schema schemas/nor.linkml.yaml \
  --master-schema schemas/master.linkml.yaml

# 9. Correct a prior decision
uv run rosetta ledger append update.sssom.tsv \
  --role accreditor \
  --source-schema schemas/nor.linkml.yaml \
  --master-schema schemas/master.linkml.yaml
```

## Exit codes

- `0` — success (or `--dry-run` with no blocking findings).
- `1` — lint BLOCK, state-machine violation, or I/O error.
