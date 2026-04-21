# rosetta lint

Validates analyst-proposed SSSOM TSV files *before* they are staged for accreditor review. Reads the audit log (from `rosetta.toml [accredit].audit_log` or `--audit-log`) to check for conflicts with existing decisions.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.lint
    :command: cli
    :prog_name: rosetta lint
    :depth: 2

## Lint rules

| Rule | Severity | Description |
|------|----------|-------------|
| `slot_class_unreachable` | **BLOCK** | Slot's owning class is not reachable from any class-level mapping target (requires `--source-schema` + `--master-schema`) |
| `unit_dimension_mismatch` | **BLOCK** | Subject and object fields have incompatible physical dimensions |
| `unit_conversion_required` | WARNING | Fields share a dimension but use different units — FnML conversion suggested |
| `unit_not_detected` | INFO | No recognisable unit in field name, or unit has no QUDT IRI mapping |
| `unit_vector_missing` | INFO | QUDT dimension vector missing for a recognised unit |
| `datatype_mismatch` | WARNING | Subject and object differ in numeric vs string datatype |
| `max_one_mmc_per_pair` | **BLOCK** | More than one `ManualMappingCuration` row for the same (subject, object) pair |
| `max_one_mmc_per_subject` | **BLOCK** | Same subject has multiple confirmed mappings to different objects |
| `reproposal_of_approved` | **BLOCK** | Pair already has an approved `HumanCuration` in the audit log |
| `reproposal_of_rejected` | **BLOCK** | Pair already has a rejected `HumanCuration` in the audit log |
| `invalid_predicate` | **BLOCK** | Predicate is not one of the allowed SKOS/OWL predicates |

With `--strict`, all WARNINGs are upgraded to BLOCKs. Use this as a CI gate on a mapping repo.

## Structural checks

When `--source-schema` and `--master-schema` are provided, lint verifies that each slot mapping's owning class in the master schema is reachable (via `is_a` hierarchy) from at least one class-level mapping target. This catches invalid mappings early — before `rosetta-yarrrml-gen` fails with a cryptic class-resolution error at step 9.

Both flags must be provided together; supplying only one is an error.

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
# Validate analyst proposals (--source-schema and --master-schema required)
uv run rosetta lint candidates.sssom.tsv \
  --source-schema nor_radar_en.linkml.yaml \
  --master-schema master_cop_en.linkml.yaml

# Strict mode — WARNINGs become BLOCKs (CI-friendly)
uv run rosetta lint candidates.sssom.tsv \
  --source-schema nor_radar_en.linkml.yaml \
  --master-schema master_cop_en.linkml.yaml \
  --strict --output lint.json

# Stage for accreditor review if clean
uv run rosetta accredit append candidates.sssom.tsv
```

## Exit codes

- `0` — no BLOCKs.
- `1` — at least one BLOCK found.
