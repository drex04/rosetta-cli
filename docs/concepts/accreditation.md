# Accreditation workflow

Every mapping in a `rosetta-cli` production graph traces back to a human decision. This page describes the two-role workflow, the state machine, and the audit-log format.

## Two roles

| Role | Responsibility | Typical persona |
|------|----------------|-----------------|
| **Analyst** | Reviews ranked candidates, proposes mappings | Subject-matter expert on the partner schema |
| **Accreditor** | Approves or rejects proposals | Ontology owner, data governance lead |

The roles are enforced by workflow, not by user accounts. `rosetta-cli` doesn't authenticate — you're expected to run it inside a governed environment (shared filesystem, git-backed, CI-gated, etc.).

## State machine

```
                  ┌────────────────────────────┐
                  │  rosetta suggest           │
                  │  (candidate generation)    │
                  └─────────────┬──────────────┘
                                │
                                ▼
               ┌────────────────────────────────┐
               │  Analyst edits candidates:     │
               │   - set mapping_justification  │
               │     to ManualMappingCuration   │
               │   - set predicate_id           │
               └─────────────┬──────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  rosetta lint        │ ← block on errors
                  └─────────────┬────────┘
                                │
                                ▼
           ┌─────────────────────────────────────┐
           │  rosetta accredit append            │
           │  (ManualMappingCuration → log)      │
           └─────────────┬───────────────────────┘
                         │
                         ▼
           ┌─────────────────────────────────────┐
           │  rosetta accredit review            │
           │  (pending proposals → review.tsv)   │
           └─────────────┬───────────────────────┘
                         │
                         ▼
           ┌─────────────────────────────────────┐
           │  Accreditor edits review.tsv:       │
           │   - HumanCuration + skos predicate  │
           │     (approve)                       │
           │   - HumanCuration + owl:different   │
           │     From (reject)                   │
           └─────────────┬───────────────────────┘
                         │
                         ▼
           ┌─────────────────────────────────────┐
           │  rosetta accredit append            │
           │  (HumanCuration → log)              │
           └─────────────────────────────────────┘
```

## Business rules

| Rule | Enforced by |
|------|-------------|
| Max 1 `ManualMappingCuration` per (subject_id, object_id) | `rosetta lint` |
| Cannot re-propose a pair with **any** `HumanCuration` in the log | `rosetta accredit append` + `rosetta lint` |
| `HumanCuration` requires a `ManualMappingCuration` predecessor | `rosetta accredit append` |
| Once rejected, only an Accreditor can un-reject | Workflow convention |
| Approved pairs boost subsequent `rosetta suggest` scores | `rosetta suggest` (log integration) |
| Rejected pairs (`owl:differentFrom`) derank subsequent candidates | `rosetta suggest` (log integration) |

## Predicate guide

| Situation | `predicate_id` |
|-----------|----------------|
| Same concept, same units | `skos:exactMatch` |
| Same concept, different units | `skos:exactMatch` — lint flags unit mismatch |
| Close but not exact match | `skos:closeMatch` |
| Source narrower than target | `skos:narrowMatch` |
| Source broader than target | `skos:broadMatch` |
| Related, neither narrows nor broadens | `skos:relatedMatch` |
| Reject — different concept | `owl:differentFrom` |

## Audit-log format

`audit-log.sssom.tsv` is an append-only SSSOM TSV with **13 columns**. Two are stamped at append time (`mapping_date`, `record_id`); the other eleven come from the ingested SSSOM row.

| Column | Description |
|--------|-------------|
| `subject_id` | Source field URI |
| `predicate_id` | SKOS/OWL mapping predicate |
| `object_id` | Master ontology field URI |
| `mapping_justification` | SEMAPV justification CURIE |
| `confidence` | Score at time of proposal |
| `subject_label` | Human-readable source field name |
| `object_label` | Human-readable target field name |
| `mapping_date` | ISO 8601 UTC timestamp — stamped at ingest |
| `record_id` | UUID4 — stamped at ingest |
| `subject_type` | `"composed entity expression"` for composite mappings, else empty |
| `object_type` | `"composed entity expression"` for composite mappings, else empty |
| `mapping_group_id` | Shared identifier across rows composing one logical mapping |
| `composition_expr` | Python/GREL composition expression for 1:N or N:1 mappings |

!!! note "Schema-derived fields"
    `subject_datatype` and `object_datatype` appear in `rosetta suggest` output but are *not* stored in the audit log. Downstream tools re-derive them from the source and master LinkML schemas, so the log remains the single reviewer-asserted record.

!!! info "Migration"
    Pre-Phase-16 audit logs with 9 columns are auto-upgraded to the 13-column format on the first `rosetta accredit append`. No manual migration required.

## Composite mappings

When a single source field maps to a combination of master fields (or vice versa), rosetta-cli uses the SSSOM composite-entity pattern. The Analyst sets `subject_type` and/or `object_type` to `"composed entity expression"` and provides a `composition_expr` describing the transformation. Rows that belong to the same logical mapping share a `mapping_group_id`.

A single NOR `position` field decomposing into master `latitude` + `longitude`:

```
subject_id    predicate_id     object_id       mapping_justification   subject_type                  object_type  mapping_group_id      composition_expr
nor:position  skos:closeMatch  mst:latitude    semapv:HumanCuration    composed entity expression                grp-position-001      record["position"].split(",")[0]
nor:position  skos:closeMatch  mst:longitude   semapv:HumanCuration    composed entity expression                grp-position-001      record["position"].split(",")[1]
```

See the [SSSOM composite-entity spec](https://mapping-commons.github.io/sssom/spec-model/#composite-entity) for the full specification.

## Correcting decisions

To override a prior decision, the Accreditor manually creates a file with a new `HumanCuration` row for the target pair and runs `rosetta accredit append` again. The log is append-only; the latest entry wins for state-machine purposes.

## Example session

```bash
# 1. Generate candidates (log read automatically from rosetta.toml)
uv run rosetta suggest nor.emb.json master.emb.json -o candidates.sssom.tsv

# 2. Analyst edits candidates.sssom.tsv, marking ManualMappingCuration rows.

# 3. Lint check
uv run rosetta lint --sssom candidates.sssom.tsv

# 4. Stage analyst proposals
uv run rosetta accredit append candidates.sssom.tsv

# 5. Generate accreditor work list
uv run rosetta accredit review -o review.sssom.tsv

# 6. Accreditor edits review.sssom.tsv, marking HumanCuration rows.

# 7. Ingest decisions
uv run rosetta accredit append review.sssom.tsv

# 8. Check current state
uv run rosetta accredit status
```
