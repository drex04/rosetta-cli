# Design: Generic FnO Function Mechanism

**Date:** 2026-04-24
**Status:** Draft — approved, pending formal planning
**Phase:** 23 (proposed)

## Problem

1. The lint gate BLOCKs all type mismatches and narrowing casts with no escape hatch. Users
   mapping schemas where type coercion is intentional cannot proceed without editing schemas.
2. Unit conversions are hardcoded in the fork's YARRRML compiler (`LINEAR_CONVERSION_FUN_IDS`).
   This is not the compiler's responsibility, produces engine-specific YARRRML, and prevents
   portability to Java-based RMLMapper.
3. There is no unified mechanism for value-level transformations. Unit conversions, type
   conversions, string operations, and custom functions should all flow through one generic path.

## Core principle

**One generic function mechanism.** The compiler does not know or care whether a function
converts units, casts types, splits strings, or does anything else. It receives an FnO
function IRI and parameters on a SlotDerivation and emits a YARRRML `function:` block.
Domain-specific logic (which type pairs need conversion, which unit pairs need functions)
lives in the rosetta config layer and FnO library, not in the compiler.

## Design decisions (locked)

1. **Hybrid granularity.** Global type-pair policies in `rosetta.toml` + per-row override
   via `conversion_function` column in SSSOM. Global policies are applied at suggest time.
2. **Suggest populates conversion_function.** `rosetta suggest` reads `[conversions]` from
   config and pre-populates the column on candidate rows with type or unit mismatches. The
   user sees the proposed conversion when reviewing candidates.
3. **Audit log is single source of truth.** Once a candidate is approved and appended, the
   audit log carries the `conversion_function` value. `rosetta compile` reads from the audit
   log only — no config lookup needed downstream.
4. **FnO IRIs for function references.** All function references use FnO (Function Ontology)
   IRIs. Standard GREL functions use the canonical `grel:` namespace. Custom functions use
   user-chosen namespaces, declared in FnO Turtle files.
5. **Language-agnostic YARRRML.** The compiled YARRRML references FnO function IRIs, not
   implementation-specific code. Portable between morph-kgc (Python) and RMLMapper (Java).
6. **Type compatibility checking.** The lint gate validates that the declared function's
   input/output types are compatible with the source/target datatypes on the SSSOM row.
7. **Single function per slot.** No function chaining. If a slot needs both unit conversion
   and type conversion, the user provides a single custom function that does both.
8. **FnO Turtle for declarations.** Function type signatures are declared in FnO Turtle
   files (`.fno.ttl`), parsed at runtime via rdflib. Both builtins and custom functions use
   the same format.
9. **Migrate unit conversions to FnO.** The hardcoded `LINEAR_CONVERSION_FUN_IDS` in the
   fork and `_LINEAR_CONVERSION_PAIRS` in transform_builder are replaced with FnO function
   references flowing through the generic mechanism. The compiler becomes fully generic.
10. **No function discovery CLI.** Registration in `rosetta.toml` + lint-time validation is
    sufficient. No `rosetta functions` subcommand.
11. **Generic SlotDerivation extension.** The fork's transformer model gains a generic
    `FunctionCallConfiguration` on `SlotDerivation`, not a type-conversion-specific field.
12. **New phase 23** — not folded into Phase 22.

## End-to-end flow

```
rosetta.toml                                    FnO function library
┌──────────────────────┐                       ┌─────────────────────────┐
│ [conversions]        │                       │ builtins.fno.ttl        │
│ float:integer =      │                       │ ─────────────────────── │
│   grel:math_round    │                       │ grel:math_round         │
│ string:double =      │                       │   expects: xsd:decimal  │
│   grel:string_toNumber                       │   returns: xsd:integer  │
│                      │                       │                         │
│ [conversions.units]  │                       │ unit-conversions.fno.ttl│
│ "unit:M:unit:FT" =   │                       │ ─────────────────────── │
│   rfns:meterToFoot   │                       │ rfns:meterToFoot        │
│                      │                       │   expects: xsd:decimal  │
│ [functions]          │                       │   returns: xsd:decimal  │
│ declarations = [     │                       │ ...                     │
│   "fns/custom.fno.ttl"                       │                         │
│ ]                    │                       │ custom.fno.ttl          │
│ implementations = [  │                       │ ─────────────────────── │
│   "fns/custom_udfs.py"                       │ myfn:dateToDatetime     │
│ ]                    │                       │   expects: xsd:date     │
└──────────┬───────────┘                       │   returns: xsd:dateTime │
           │                                   └────────────┬────────────┘
           ▼                                                │
┌──────────────────────────────────┐                        │
│ rosetta suggest                  │◄───────────────────────┘
│                                  │  (validates function exists,
│  auto-detects:                   │   resolves type signatures)
│   - type mismatches (from        │
│     subject_datatype vs          │
│     object_datatype)             │
│   - unit mismatches (from        │
│     detect_unit() on both sides) │
│                                  │
│  looks up [conversions] policy   │
│  populates conversion_function   │
│                                  │
│  output: candidates.sssom.tsv   │
│    subject_datatype = float      │
│    object_datatype  = integer    │
│    conversion_function =         │
│      grel:math_round             │
└──────────┬───────────────────────┘
           │
           │  user reviews, can edit/remove/add conversion_function
           ▼
┌──────────────────────────────────┐
│ rosetta ledger append            │
│                                  │
│  lint gate:                      │
│    type mismatch detected?       │
│    ├─ conversion_function set?   │
│    │  ├─ function in library?    │
│    │  │  ├─ types compatible?    │
│    │  │  │  └─ INFO (will apply) │
│    │  │  └─ BLOCK (bad types)    │
│    │  └─ BLOCK (unknown fn)      │
│    └─ BLOCK (no conversion)      │
│                                  │
│    unit mismatch detected?       │
│    ├─ conversion_function set?   │
│    │  └─ (same validation)       │
│    └─ WARNING (no conversion)    │
│                                  │
│  writes to audit-log.sssom.tsv   │
│  with conversion_function column │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ rosetta compile                  │
│  reads conversion_function from  │
│  audit log rows (no config)      │
│                                  │
│  transform_builder emits:        │
│    SlotDerivation(               │
│      name="hasAltitude",         │
│      populated_from="altitude",  │
│      function_call=              │
│        FunctionCallConfiguration(│
│          function_id=            │
│            "grel:math_round",    │
│          parameters=[...]        │
│        )                         │
│    )                             │
│                                  │
│  YARRRML compiler emits:         │
│    po:                           │
│      - p: mc:hasAltitude         │
│        o:                        │
│          function: grel:math_round
│          parameters:             │
│            - [grel:p_dec_n,      │
│               $(altitude)]       │
│          datatype: xsd:integer   │
└──────────┬───────────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│ rosetta transform                │
│  morph-kgc resolves FnO IRIs:   │
│    grel:* → built-in impls      │
│    rfns:* → rosetta UDF file    │
│    myfn:* → user UDF file       │
│                                  │
│  output: "42"^^xsd:integer       │
│  (was "42.3"^^xsd:double)       │
└──────────────────────────────────┘
```

## Function library

### Builtin typecasts (ship with rosetta)

Standard GREL FnO IRIs — supported natively by morph-kgc and RMLMapper:

| Function | FnO IRI | Parameter IRI | Input type | Output type | Use case |
|----------|---------|---------------|------------|-------------|----------|
| Round | `grel:math_round` | `grel:p_dec_n` | `xsd:decimal` | `xsd:integer` | float → integer |
| Floor | `grel:math_floor` | `grel:p_dec_n` | `xsd:decimal` | `xsd:integer` | float → integer (down) |
| Ceiling | `grel:math_ceil` | `grel:p_dec_n` | `xsd:decimal` | `xsd:integer` | float → integer (up) |
| To number | `grel:string_toNumber` | `grel:p_any_e` | `xsd:string` | `xsd:double` | string → numeric |
| To string | `grel:string_toString` | `grel:p_any_e` | any | `xsd:string` | any → string |

GREL namespace: `http://users.ugent.be/~bjdmeest/function/grel.ttl#`

### Builtin unit conversions (ship with rosetta, migrate from hardcoded)

Rosetta-namespaced FnO functions with Python UDF implementations:

| Function | FnO IRI | Input | Output | Use case |
|----------|---------|-------|--------|----------|
| Meter → Foot | `rfns:meterToFoot` | `xsd:decimal` | `xsd:decimal` | m → ft |
| Foot → Meter | `rfns:footToMeter` | `xsd:decimal` | `xsd:decimal` | ft → m |
| Kg → Pound | `rfns:kgToPound` | `xsd:decimal` | `xsd:decimal` | kg → lb |
| Pound → Kg | `rfns:poundToKg` | `xsd:decimal` | `xsd:decimal` | lb → kg |
| Celsius → Fahrenheit | `rfns:celsiusToFahrenheit` | `xsd:decimal` | `xsd:decimal` | °C → °F |

Rosetta functions namespace: `https://rosetta.interop/functions#` (prefix `rfns:`)

These declarations live in `rosetta/functions/unit-conversions.fno.ttl`. Python UDF
implementations live in `rosetta/functions/unit_conversion_udfs.py`.

### Custom functions (user-defined)

Users declare custom functions in their own FnO Turtle files:

```turtle
@prefix fno:  <https://w3id.org/function/ontology#> .
@prefix myfn: <https://example.org/functions#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

myfn:dateToDatetime a fno:Function ;
    fno:name "Date to Datetime" ;
    fno:expects ( [ a fno:Parameter ;
                     fno:predicate myfn:value ;
                     fno:type xsd:date ] ) ;
    fno:returns ( [ a fno:Output ;
                     fno:predicate myfn:result ;
                     fno:type xsd:dateTime ] ) .
```

Python UDF implementation (for morph-kgc):

```python
from morph_kgc.udfs import udf

@udf(
    fun_id="https://example.org/functions#dateToDatetime",
    return_type="xsd:dateTime",
    value="https://example.org/functions#value",
)
def date_to_datetime(value: str) -> str:
    return value + "T00:00:00Z"
```

## Config format

```toml
[conversions]
# Type-pair policies: "source_type:target_type" → FnO function IRI
"float:integer" = "grel:math_round"
"double:integer" = "grel:math_round"
"string:double" = "grel:string_toNumber"

[conversions.units]
# Unit-pair policies: "source_qudt:target_qudt" → FnO function IRI
"unit:M:unit:FT" = "rfns:meterToFoot"
"unit:FT:unit:M" = "rfns:footToMeter"
"unit:KiloGM:unit:LB" = "rfns:kgToPound"
"unit:LB:unit:KiloGM" = "rfns:poundToKg"
"unit:DEG_C:unit:DEG_F" = "rfns:celsiusToFahrenheit"

[functions]
# Custom function library (optional)
# declarations = ["functions/custom.fno.ttl"]
# implementations = ["functions/custom_udfs.py"]
```

## SSSOM model extension

Add `conversion_function: str | None` to `SSSOMRow` in `rosetta/core/models.py`:

```python
class SSSOMRow(BaseModel):
    # ... existing fields ...
    conversion_function: str | None = None  # FnO function IRI (CURIE or full URI)
```

Column count: 15 → 16 (suggest TSV), 13 → 14 (audit log).

A single slot may need both unit conversion and type conversion (e.g., meters/float →
feet/integer). Per decision #7, this requires one custom function that does both operations.

## Lint gate changes

`check_datatype()` and `check_units()` in `rosetta/core/lint.py` gain function-aware paths:

```
Type mismatch path:
  same type → pass
  mismatch + conversion_function present →
    function in library? →
      function input type compatible with source? →
        function output type compatible with target? →
          INFO ("will apply grel:math_round: float → integer")
        BLOCK ("grel:math_round returns xsd:integer, target is xsd:string")
      BLOCK ("grel:math_round expects xsd:decimal, source is xsd:boolean")
    BLOCK ("unknown function: myfn:nonExistent")
  mismatch + no conversion_function → BLOCK

Unit mismatch path:
  same unit → pass (no function needed)
  different units + conversion_function present →
    (same validation cascade as above)
  different units + no conversion_function → WARNING (existing behavior)
```

The lint gate needs a `FunctionLibrary` object (loaded from builtin + custom FnO Turtle
files) that provides:
- `has_function(iri: str) -> bool`
- `get_input_type(iri: str) -> str | None`
- `get_output_type(iri: str) -> str | None`
- `get_parameter_predicate(iri: str) -> str`

## linkml-map fork changes

### Research findings

- Models are **generated from LinkML YAML** (`transformer_model.yaml` → `gen-pydantic`)
- `SlotDerivation` has `unit_conversion: UnitConversionConfiguration | None` — specific field
- `expr` field is NOT viable — holds LinkML expression language strings
- No existing generic function mechanism in the model

### Approach: add `FunctionCallConfiguration` to transformer model

In `transformer_model.yaml`, add:

```yaml
FunctionCallConfiguration:
  description: >-
    Configuration for applying an FnO function to a slot's value during
    compilation. The compiler emits a YARRRML function block with the
    given function IRI and parameter binding.
  attributes:
    function_id:
      description: FnO function IRI (CURIE or full URI)
      range: string
      required: true
    parameter_predicate:
      description: FnO parameter predicate IRI for the input value binding
      range: string
      required: true
    output_datatype:
      description: XSD datatype IRI for the function's return value
      range: string
```

On `SlotDerivation`, add:

```yaml
function_call:
  description: >-
    Generic FnO function to apply to this slot's value. Replaces
    type-specific mechanisms (unit_conversion). The compiler emits
    a YARRRML function block referencing function_id with the slot's
    source reference bound to parameter_predicate.
  range: FunctionCallConfiguration
```

Regenerate `transformer_model.py` via `gen-pydantic`.

### Compiler changes

`YarrrmlCompiler._build_mapping_context` gains a generic function path:

```python
# Generic function call (replaces unit_conversion branch)
if slot_deriv.function_call is not None:
    fc = slot_deriv.function_call
    po = {
        "predicate": predicate,
        "reference": reference,
        "function": {
            "name": fc.function_id,
            "parameters": [
                {"name": fc.parameter_predicate, "value": reference}
            ],
        },
    }
    if datatype:
        po["function"]["datatype"] = datatype
```

The hardcoded `LINEAR_CONVERSION_FUN_IDS` dict and the unit-conversion-specific branch
are deleted. The compiler becomes fully generic.

### Migration path for unit_conversion

1. Keep `unit_conversion` field on `SlotDerivation` for backward compatibility
2. In the compiler, if `unit_conversion` is set but `function_call` is not, convert to
   `function_call` internally (deprecation bridge)
3. rosetta-cli always uses `function_call` — never emits `unit_conversion`
4. Future: deprecate and remove `unit_conversion` from the model

## Transform builder changes

`build_slot_derivation()` in `rosetta/core/transform_builder.py`:

### Current (to be replaced)

```python
# Unit conversion via hardcoded pairs
if m.source_unit and m.target_unit and (m.source_unit, m.target_unit) in _LINEAR_CONVERSION_PAIRS:
    unit_conv = UnitConversionConfiguration(
        source_unit=_QUDT_TO_FORK_UNIT[m.source_unit],
        target_unit=_QUDT_TO_FORK_UNIT[m.target_unit],
    )
```

### Target (generic)

```python
# Generic function call from SSSOM conversion_function column
if m.conversion_function:
    fn_call = FunctionCallConfiguration(
        function_id=m.conversion_function,
        parameter_predicate=library.get_parameter_predicate(m.conversion_function),
        output_datatype=library.get_output_type(m.conversion_function),
    )
```

Delete: `_LINEAR_CONVERSION_PAIRS`, `_QUDT_TO_FORK_UNIT` dicts.
Delete: unit-conversion-specific logic in `build_slot_derivation()`.
The function IRI already came through the SSSOM row — the transform builder just
resolves the parameter metadata from the library and emits the config.

## Phase structure

**Phase 23: Generic FnO Function Mechanism**

Depends on: Phase 22 (command consolidation) — suggest/ledger/compile CLI surfaces change
in Phase 22.

### 23-01: FnO function library + FunctionLibrary loader
- FnO Turtle declarations: `rosetta/functions/typecasts.fno.ttl` (GREL builtins),
  `rosetta/functions/unit-conversions.fno.ttl` (rfns: unit conversions)
- Python UDF implementations: `rosetta/functions/unit_conversion_udfs.py`
- `rosetta/core/function_library.py` — `FunctionLibrary` class: loads FnO Turtle, provides
  `has_function()`, `get_input_type()`, `get_output_type()`, `get_parameter_predicate()`
- `rosetta.toml` `[conversions]`, `[conversions.units]`, `[functions]` config parsing
- `SSSOMRow.conversion_function` field + audit log column migration (13 → 14 cols)
- Unit tests for library loader and config parsing

### 23-02: Fork model extension + compiler generification
- Add `FunctionCallConfiguration` to `transformer_model.yaml`
- Add `function_call` field to `SlotDerivation`
- Regenerate `transformer_model.py`
- Refactor `YarrrmlCompiler._build_mapping_context`: generic function path
- Delete `LINEAR_CONVERSION_FUN_IDS` hardcoded dict
- Add `unit_conversion` → `function_call` deprecation bridge
- Fork-side tests for generic function emission
- Pin new fork SHA in rosetta-cli

### 23-03: Lint gate + suggest population
- `check_datatype()` rewrite: function-aware validation with `FunctionLibrary`
- `check_units()` update: function-aware validation
- `rosetta suggest` reads `[conversions]` from config, populates `conversion_function`
  on candidates with type or unit mismatches
- `rosetta ledger append` lint gate validates function compatibility
- `run_lint()` gains `function_library` parameter
- Integration tests: suggest → lint → append with function references

### 23-04: Transform builder migration + E2E
- `build_slot_derivation()` rewrite: uses `FunctionCallConfiguration` from SSSOM row
- Delete `_LINEAR_CONVERSION_PAIRS`, `_QUDT_TO_FORK_UNIT` dicts
- `rml_runner.py` collects UDF files (unit + custom) and passes via `udfs=`
- E2E tests:
  - float → integer roundtrip with `grel:math_round` → correct `xsd:integer` literal
  - m → ft unit conversion via `rfns:meterToFoot` → correct numeric value
  - Custom function via user UDF → correct output
- Verify existing unit conversion E2E tests still pass

### 23-05: Custom functions + docs
- User-defined FnO declarations in custom Turtle files
- User-defined Python UDF registration for morph-kgc
- `rosetta.toml` `[functions]` config for custom library paths
- `docs/concepts/type-handling.md` updated: function mechanism, FnO references
- `docs/concepts/functions.md` new: function library, custom functions, FnO format
- `README.md` updated
- `docs/cli/suggest.md`, `docs/cli/ledger.md`, `docs/cli/compile.md` updated
