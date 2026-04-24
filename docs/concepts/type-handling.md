# Datatype handling

Rosetta tracks datatypes from schema ingestion through to RDF emission. This page explains how types flow through the pipeline, what the lint gate checks, and how to resolve type mismatches.

## How types flow through the pipeline

```
Source schema          Master schema
(range: float)         (range: double)
     │                       │
     ▼                       ▼
rosetta suggest ──────────────────────────────────▶ candidates.sssom.tsv
  (reads slot ranges,                               subject_datatype=float
   populates SSSOM                                   object_datatype=double
   datatype columns)
     │
     ▼
rosetta ledger append ────────────────────────────▶ audit-log.sssom.tsv
  (lint gate checks                                  subject_datatype=float
   type compatibility)                               object_datatype=double
     │
     ▼
rosetta compile ──────────────────────────────────▶ mapping.yarrrml.yaml
  (YarrrmlCompiler looks up                          datatype: xsd:double
   target slot range from                            (from master schema,
   the master LinkML schema)                          NOT from SSSOM)
     │
     ▼
rosetta transform ────────────────────────────────▶ output.jsonld
  (morph-kgc tags literals                           "65.88"^^xsd:double
   with the declared XSD type;
   SHACL validates the result)
```

### Key design decisions

**The master LinkML schema is the authoritative source for datatypes.** The SSSOM audit log carries `subject_datatype` and `object_datatype` columns for human review, but the YARRRML compiler reads the target slot's `range` directly from the master schema via `SchemaView.get_type()`. This prevents accidental modification of type information in the audit log from affecting RDF output.

**morph-kgc annotates but does not convert.** When the YARRRML declares `datatype: xsd:double`, morph-kgc tags the literal with that XSD type. It does not parse or validate the value. If the source data contains a non-numeric string in a `double`-typed slot, the literal will be emitted as-is and SHACL validation will catch the violation.

**String types are not annotated.** The compiler skips `xsd:string` and `xsd:anyURI` since morph-kgc emits plain (untyped) literals by default, which are equivalent to `xsd:string` in SPARQL 1.1.

## Lint gate rules

The lint gate in `rosetta ledger append` checks datatype compatibility between source and target slots. Both datatypes must be present in the SSSOM row for a check to fire.

| Source type | Target type | Lint result | Rationale |
|---|---|---|---|
| `string` | `double` | **BLOCK** | Numeric vs non-numeric: morph-kgc cannot validate that string values are actually numeric |
| `double` | `string` | **BLOCK** | Numeric vs non-numeric: likely a mapping error |
| `double` | `integer` | **BLOCK** | Narrowing: morph-kgc cannot truncate decimal values; the resulting literal would be invalid |
| `integer` | `double` | pass | Widening: lossless promotion, no action needed |
| `float` | `double` | pass | Same family, no precision loss |
| `double` | `double` | pass | Same type |
| (missing) | any | pass | Missing datatypes are not checked |

### Numeric type families

- **Float family:** `float`, `double`, `decimal`
- **Integer family:** `integer`, `int`, `long`, `short`, `nonNegativeInteger`, `positiveInteger`
- **Non-numeric:** `string`, `boolean`, `date`, `datetime`, `uri`, `uriorcurie`, and all others

## Resolving type mismatches

When the lint gate blocks a mapping due to a type mismatch, the fix depends on the situation:

### Fix the schema (preferred)

If the source schema has the wrong type (e.g., `range: string` for a field that actually contains numbers), update the source LinkML schema to declare the correct range, then re-run `rosetta suggest`.

```yaml
# Before (wrong)
slots:
  latitude:
    range: string

# After (correct)
slots:
  latitude:
    range: double
```

### Fix the master schema

If the master schema's type is overly restrictive (e.g., `integer` when `double` is appropriate), update the master schema.

### Accept the types as-is

If both types are correct and the mapping is intentional, consider whether the narrowing is acceptable. Currently, there is no mechanism for value-level type conversion (e.g., rounding a float to an integer). The pipeline only annotates literals with XSD types; it does not transform values between types.

## SHACL validation errors

When `rosetta transform` runs with `--shapes`, SHACL validates that every literal in the materialized graph has the correct datatype. A validation finding includes:

| Field | Description |
|---|---|
| `focus_node` | The RDF node that failed validation |
| `property_path` | The property whose value failed (e.g., `mc:hasLatitude`) |
| `value` | The actual value that was rejected |
| `constraint` | The SHACL constraint that fired (e.g., `DatatypeConstraintComponent`) |
| `message` | Human-readable explanation |

Common causes of datatype validation failures:

- **Missing `datatype:` in YARRRML** — the value was emitted as a plain string instead of a typed literal. Fixed by ensuring the master schema declares the correct `range` on the slot.
- **Invalid value for the declared type** — e.g., `"hello"^^xsd:double`. Fix the source data or the schema type declaration.

## See also

- [`rosetta ledger`](../cli/ledger.md) — the lint gate that checks type compatibility
- [`rosetta compile`](../cli/compile.md) — YARRRML compilation with schema-derived datatypes
- [`rosetta transform`](../cli/transform.md) — SHACL validation of typed literals
