# Phase 23: Generic FnO Function Mechanism — Context

## Locked Decisions

### D-23-01: Hybrid granularity
Global type-pair and unit-pair policies in `rosetta.toml` `[conversions]` section, with
per-row override via `conversion_function` column in SSSOM. Global policies applied at
suggest time.

### D-23-02: Suggest populates conversion_function
`rosetta suggest` reads `[conversions]` config, auto-detects type and unit mismatches,
and pre-populates the `conversion_function` column on candidate SSSOM rows. User sees the
proposed conversion when reviewing candidates.

### D-23-03: Audit log is single source of truth
Once appended, the audit log carries `conversion_function`. `rosetta compile` reads from
audit log only — no config lookup downstream.

### D-23-04: FnO IRIs for all function references
Standard GREL functions use canonical `grel:` namespace
(`http://users.ugent.be/~bjdmeest/function/grel.ttl#`). Rosetta unit conversions use
`rfns:` namespace (`https://rosetta.interop/functions#`). Custom functions use
user-chosen namespaces.

### D-23-05: Language-agnostic YARRRML
Compiled YARRRML references FnO function IRIs only. Portable between morph-kgc and
RMLMapper. No engine-specific code in YARRRML output.

### D-23-06: Type compatibility checking
Lint gate validates declared function's input/output types against source/target
datatypes on the SSSOM row. Uses FnO Turtle declarations for type signatures.

### D-23-07: Single function per slot
No function chaining. If a slot needs both unit and type conversion, user provides one
custom function that does both.

### D-23-08: FnO Turtle for declarations
Function type signatures declared in FnO Turtle files (`.fno.ttl`), parsed at runtime
via rdflib. Both builtins and custom functions use the same format.

### D-23-09: Migrate unit conversions to FnO
Hardcoded `LINEAR_CONVERSION_FUN_IDS` in fork and `_LINEAR_CONVERSION_PAIRS` /
`_QUDT_TO_FORK_UNIT` in transform_builder replaced with FnO function references
flowing through generic mechanism. Compiler becomes fully generic.

### D-23-10: No function discovery CLI
Registration via `rosetta.toml` + lint-time validation sufficient.

### D-23-11: Generic SlotDerivation extension
Fork's transformer model gains `FunctionCallConfiguration` class and `function_call`
field on `SlotDerivation`. Not type-conversion-specific.

### D-23-12: Compiler is a dumb pipe
Compiler does not know or care whether a function converts units, casts types, or does
anything else. Receives FnO IRI + parameters, emits YARRRML function block. All
domain-specific logic lives in rosetta config and FnO library.

## Dependencies

- **Phase 22** (command consolidation) must complete first — suggest/ledger/compile CLI
  surfaces change in Phase 22.

## Design Document

`.planning/designs/2026-04-24-datatype-conversions.md`

## Plan Decomposition

5 plans (approved during brainstorm):
1. FnO function library + FunctionLibrary loader
2. Fork model extension + compiler generification
3. Lint gate + suggest population
4. Transform builder migration + E2E
5. Custom functions + docs

## Review Decisions (Plan 23-01, 2026-04-24)

### [review] D-23-13: _OPTIONAL_STR_FIELDS must include conversion_function
Adding a field to SSSOMRow without adding it to `_OPTIONAL_STR_FIELDS` in ledger.py causes
silent data loss on parse. The field is silently dropped. This is the root cause of the
round-trip failure pattern seen in prior SSSOM column migrations.

### [review] D-23-14: append_log must detect existing column width
Appending 16-column rows to a 15-column file produces corrupt TSV. `append_log` must read
the existing header width and use matching columns. A 15-col file stays 15-col;
`conversion_function` is silently dropped for consistency.

### [review] D-23-15: FnO Turtle must use inline blank node list syntax
The SPARQL property path `fno:expects/rdf:first` only resolves correctly when the Turtle
uses `fno:expects ( [ fno:predicate ... ] )` inline syntax. This encoding is mandatory for
all FnO Turtle files (builtin and custom).

### [review] D-23-16: grel:string_toString input type is xsd:anySimpleType
The function converts any value to string, not just strings. Using `xsd:string` as input
type would make the lint gate reject valid uses like `integer→string`.

### [review] D-23-17: kelvin_to_celsius preserved as 6th unit conversion builtin
Total builtins: 11 (5 GREL typecasts + 6 unit conversions). The existing `_UDF_SOURCE` in
rml_runner.py includes it; dropping it would be a silent regression.

### [review] D-23-18: Guard @udf import with try/except ImportError
The static UDF file must be importable without morph-kgc installed (for testing, lint, etc.).
Provide a no-op stub when morph-kgc is not available.

## Deferred Ideas

- **Config validation at parse time:** `load_conversion_policies` does not validate CURIEs
  against FunctionLibrary. Deferred to plan 23-03 (lint gate validates at append time).
- **FunctionLibrary singleton caching:** Module-level lazy singleton to avoid re-parsing
  Turtle on every caller. Deferred — premature optimization for 11 functions.
