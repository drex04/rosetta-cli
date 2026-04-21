# rosetta accredit

Manages the two-role accreditation pipeline using an append-only audit log (`audit-log.sssom.tsv`). The log is the single source of truth for accreditation decisions and feeds directly into `rosetta suggest` (boost/derank) and `rosetta lint` (conflict checking).

For the conceptual flow and state machine, see [Accreditation workflow](../concepts/accreditation.md).

## Command reference

::: mkdocs-click
    :module: rosetta.cli.accredit
    :command: cli
    :prog_name: rosetta accredit
    :depth: 2

## Subcommand semantics

### `append FILE`

Validates each row against the state machine before writing. If *any* row violates a rule, all errors are printed to stderr and **nothing is written** — no partial writes. Accepts both `ManualMappingCuration` and `HumanCuration` rows.

### `review`

Outputs pending proposals — all `ManualMappingCuration` rows that have no corresponding `HumanCuration` decision yet — as SSSOM TSV. This is the Accreditor's work list.

### `dump`

Outputs the latest `HumanCuration` row per pair as SSSOM TSV — suitable for external pipeline consumption.

## Example session

```bash
# 1. Generate candidates (audit-log read automatically from rosetta.toml)
uv run rosetta suggest nor.emb.json master.emb.json -o candidates.sssom.tsv

# 2. Analyst edits candidates.sssom.tsv, marking ManualMappingCuration rows.

# 3. Lint check
uv run rosetta lint candidates.sssom.tsv

# 4. Stage analyst proposals
uv run rosetta accredit append candidates.sssom.tsv

# 5. Generate accreditor work list
uv run rosetta accredit review -o review.sssom.tsv

# 6. Accreditor edits review.sssom.tsv, marking HumanCuration rows.

# 7. Ingest decisions
uv run rosetta accredit append review.sssom.tsv

# 8. Correct a prior decision
uv run rosetta accredit append update.sssom.tsv
```

## Exit codes

- `0` — success.
- `1` — state-machine violation or I/O error.
