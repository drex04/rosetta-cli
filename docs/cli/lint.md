# rosetta-lint

Validates analyst-proposed SSSOM TSV files *before* they are staged for accreditor review. Reads the audit log (from `rosetta.toml [accredit].log`) to check for conflicts with existing decisions.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.lint
    :command: cli
    :prog_name: rosetta-lint
    :depth: 2

## Lint rules

| Rule | Severity | Description |
|------|----------|-------------|
| `unit_dimension_mismatch` | **BLOCK** | Subject and object fields have incompatible physical dimensions |
| `unit_conversion_required` | WARNING | Fields share a dimension but use different units — FnML conversion suggested |
| `unit_not_detected` | INFO | No recognisable unit in field name, or unit has no QUDT IRI mapping |
| `unit_vector_missing` | INFO | QUDT dimension vector missing for a recognised unit |
| `datatype_mismatch` | WARNING | Subject and object differ in numeric vs string datatype |
| `max_one_mmc_per_pair` | **BLOCK** | More than one `ManualMappingCuration` row for the same pair |
| `reproposal_of_approved` | **BLOCK** | Pair already has an approved `HumanCuration` in the audit log |
| `reproposal_of_rejected` | **BLOCK** | Pair already has a rejected `HumanCuration` in the audit log |
| `invalid_predicate` | **BLOCK** | Predicate is not one of the allowed SKOS/OWL predicates |

With `--strict`, all WARNINGs are upgraded to BLOCKs. Use this as a CI gate on a mapping repo.

## Output — `LintReport` JSON

`findings[]` — each finding carries:

- `rule`
- `severity` (`BLOCK`, `WARNING`, `INFO`)
- `source_uri`, `target_uri`
- `message`
- `fnml_suggestion` — optional FnML conversion expression for `unit_conversion_required`

`summary` — counts of blocks, warnings, and info items.

## Example

```bash
# Validate analyst proposals
uv run rosetta-lint --sssom candidates.sssom.tsv

# Strict mode — WARNINGs become BLOCKs (CI-friendly)
uv run rosetta-lint --strict --sssom candidates.sssom.tsv --output lint.json

# Stage for accreditor review if clean
uv run rosetta-accredit ingest candidates.sssom.tsv
```

## Exit codes

- `0` — no BLOCKs.
- `1` — at least one BLOCK found.
