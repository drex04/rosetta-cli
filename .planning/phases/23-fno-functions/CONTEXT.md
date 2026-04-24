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

### [review] D-23-19: Bridge uses new rfns: IRIs, not old udf/ IRIs
Prototype stage — backward compatibility with rml_runner's _UDF_SOURCE is not required.
The bridge emits `https://rosetta.interop/functions#meterToFoot` (new FnO namespace).
Unit conversion E2E tests may break until Plan 23-04 migrates rml_runner. Accepted.

### [review] D-23-20: Test assertions use full IRIs, not CURIEs
YARRRML output renders full IRIs. Fork tests must assert exact full IRI strings
(e.g., `https://rosetta.interop/functions#meterToFoot`), not CURIEs.

### D-23-21: Undeclared conversion_function → BLOCK
Lint gate BLOCKs when `conversion_function` is set on a row but the function CURIE is
not present in the FunctionLibrary. Catches typos and misconfiguration early. Consistent
with D-23-06 (lint validates function type signatures).

### [review] D-23-22: suggest TSV writer must serialize conversion_function
The existing `writer.writerow(...)` in `suggest.py` hardcodes 15 fields. Must append
`row.conversion_function or ""` as the 16th field. Without this, the column is in the
header but never in the data rows — silent data loss.

### [review] D-23-23: suggest CLI must call load_config() for rosetta.toml
Without `load_config()`, `load_conversion_policies({})` always returns an empty dict
and `populate_conversion_functions` never matches any policy. The primary deliverable
(conversion_function in suggest output) silently fails.

### [review] D-23-24: Early return after undeclared-function BLOCK in check_units
Without `return` after appending `undeclared_function` BLOCK, the original
`unit_conversion_required` WARNING also fires — double finding on the same row.

## Plan 23-04 Decisions (2026-04-24)

### D-23-25: Remove _SlotMapping.source_unit/target_unit
Dead fields after build_slot_derivation no longer uses hardcoded unit pairs. detect_unit
import also removed from transform_builder. vulture would flag otherwise.

### D-23-26: FunctionLibrary parameter is optional (None default) on build_spec
Preserves backward compatibility for existing callers/tests that don't care about
function calls. When None, conversion_function on SSSOM rows is silently ignored
(same behavior as today for rows without it).

### D-23-27: NOR SSSOM fixture updated to 16 columns in-place
No separate fixture. The ledger parser's _detect_existing_columns handles mixed-width.
The hoyde_m→hasAltitudeFt row gets conversion_function=rfns:meterToFoot.

### D-23-28: build_composite_slot_derivation unchanged
No function support on composites. Design doc doesn't require it.

### D-23-29: FunctionCallConfiguration uses full IRIs (not CURIEs)
Fork YARRRML compiler renders function_id directly into YARRRML. Full IRIs required
for morph-kgc resolution. Use library.resolve_curie() to expand SSSOM CURIEs.

## Review Decisions (Plan 23-04, 2026-04-24)

### [review] D-23-30: KeyError from get_parameter_predicate caught in build_slot_derivation
build_slot_derivation wraps the FunctionLibrary calls in try/except KeyError and re-raises
as ValueError naming the unknown CURIE. Prevents raw traceback when compile runs on SSSOM
that bypassed the lint gate. Both review agents flagged this independently.

### [review] D-23-31: Guarded output_datatype resolution
`get_output_type` returns `str | None`. The `resolve_curie` call is only made when the
return is non-None. Original plan code `resolve_curie(... or "")` would crash on empty
string. Fix: `library.resolve_curie(raw_out) if raw_out else None`.

### [review] D-23-32: _remap_to_mapped_classes reconstruction site
`_remap_to_mapped_classes` at L466-473 reconstructs `_SlotMapping` with `source_unit=`
and `target_unit=` kwargs. These must be removed when the fields are deleted from the
dataclass, otherwise `TypeError` at runtime on any mapping with inheritance remapping.

### [review] D-23-33: Unknown-CURIE test required
A dedicated test must verify that `build_slot_derivation` raises clean `ValueError` (not
`KeyError`) when given a CURIE not in the FunctionLibrary. Covers the compile-without-lint
user path.

## Deferred Ideas

- **Config validation at parse time:** `load_conversion_policies` does not validate CURIEs
  against FunctionLibrary. Deferred to plan 23-03 (lint gate validates at append time).
- **FunctionLibrary singleton caching:** Module-level lazy singleton to avoid re-parsing
  Turtle on every caller. Deferred — premature optimization for 11 functions.
