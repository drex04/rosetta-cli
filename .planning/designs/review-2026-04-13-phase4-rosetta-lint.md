# Plan Review — Phase 4 rosetta-lint (2026-04-13)

## Mode: HOLD

---

## Data Flow (with shadow paths)

```
suggestions.json → data[src_uri]
     │
     ├─ data[src_uri]["suggestions"] is empty → SKIP (no finding)
     │
     └─ data[src_uri]["suggestions"][0]["uri"] → target_field_uri
          │
          ▼
source.ttl ──SPARQL rose:detectedUnit──► string literal ("meter", "foot", ...)
          │
          ├─ not found → unit_not_detected INFO ──┐
          ├─ UNIT_STRING_TO_IRI → None (e.g."dBm") → unit_not_detected INFO ──┤
          │                                                                    │
          └─ UNIT_STRING_TO_IRI → "unit:FT" ──────────────────────────────────┘
               │                                                               │
               ▼                                                     continue to datatype check
master.ttl ──SPARQL qudt:unit──► URIRef or None
               │
               └─ None → master_unit_missing INFO → continue to datatype check
               │
               ▼
units_compatible(src_iri, tgt_iri, qudt_graph)
               │
               ├─ False → unit_dimension_mismatch BLOCK, fnml_suggestion: null
               ├─ True, same IRI → no unit finding
               ├─ True, diff IRI → suggest_fnml() → unit_conversion_required WARNING
               │                   (fnml_suggestion: null if no registry entry)
               └─ None → unit_vector_missing INFO

source.ttl rose:dataType vs master rdfs:range
               │
               └─ numeric vs string (or vice versa) → datatype_mismatch WARNING

--strict flag: reclassify all WARNING → BLOCK before exit check
Exit 1 if any BLOCK, else 0
```

---

## Error & Rescue Registry

| Method | Error | Rescued? | Rescue Action | User Sees |
|--------|-------|----------|---------------|-----------|
| `rdflib.Graph.parse(source_ttl)` | ParseError, FileNotFoundError | Y | CLI try/except → click.echo(err=True) + sys.exit(1) | error message |
| `rdflib.Graph.parse(master_ttl)` | ParseError, FileNotFoundError | Y | same | error message |
| `json.load(suggestions_fp)` | JSONDecodeError, FileNotFoundError | Y | same | error message |
| `importlib.resources.files("rosetta.policies")` | ModuleNotFoundError | Y (if __init__.py present) | fatal crash if missing | traceback |
| `units_compatible()` | None return (missing vector) | Y | emit unit_vector_missing INFO | finding in output |
| `suggest_fnml()` SPARQL | None result | Y | emit WARNING with fnml_suggestion: null | finding in output |
| SPARQL OPTIONAL vars | None in row | Y (must None-guard) | coerce before string use | silent corruption if missed |
| URIRef as json.dumps key | TypeError | Y (must coerce) | str(uri) before dict key | TypeError if missed |

---

## Failure Modes Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES | LOGGED? |
|----------|-------------|----------|-------|-----------|---------|
| UNIT_STRING_TO_IRI["dBm"] | Returns None | Y | Y (test_unit_string_to_iri_dbm) | unit_not_detected INFO | - |
| dimension_vector() full IRI | Returns None silently | Y (after fix) | Y (test_dimension_vector_full_iri) | unit_vector_missing INFO | - |
| units_compatible() → None | Missing vector, silent skip | Y (after fix) | Y (test_lint_cli_unit_vector_missing) | unit_vector_missing INFO | - |
| policies/__init__.py missing | ModuleNotFoundError crash | Y (after fix) | N | traceback | - |
| suggest_fnml() no registry entry | Returns None | Y | partial | WARNING with fnml_suggestion:null | - |
| SPARQL OPTIONAL None | Silent string corruption | Y (required) | N | "None" in output | - |

---

## Test Coverage Diagram

```
CODEPATH                                       | TEST                                    | STATUS
-----------------------------------------------|------------------------------------------|-------
UNIT_STRING_TO_IRI["meter"] → "unit:M"        | test_unit_string_to_iri_meter           | ADDED
UNIT_STRING_TO_IRI["dBm"] → None              | test_unit_string_to_iri_dbm             | ADDED
load_qudt_graph() success                      | test_load_qudt_graph_parses             | OK
dimension_vector() short-form IRI              | test_dimension_vector_metre/kilogram    | OK
dimension_vector() full IRI                    | test_dimension_vector_full_iri          | ADDED
dimension_vector() → None                      | test_dimension_vector_unknown           | OK
units_compatible() True (same dim)             | test_units_compatible_same_dimension    | OK
units_compatible() False                       | test_units_compatible_different_dimension | OK
units_compatible() None (missing vector)       | test_units_compatible_missing_vector    | ADDED
suggest_fnml() multiplier pair                 | test_suggest_fnml_known_pair            | OK
suggest_fnml() offset pair (273.15 exact)      | test_suggest_fnml_offset_pair           | SHARPENED
suggest_fnml() → None                          | test_suggest_fnml_unknown_pair          | OK
lint CLI: BLOCK                                | test_lint_cli_block_on_dimension_mismatch | OK
lint CLI: WARNING + fnml                       | test_lint_cli_warning_unit_conversion   | OK
lint CLI: INFO no unit                         | test_lint_cli_info_no_unit              | OK
lint CLI: --strict exit 1                      | test_lint_cli_strict_warning_becomes_block | OK
lint CLI: --strict summary.warning == 0        | test_lint_cli_strict_summary_warning_zero | ADDED
lint CLI: datatype_mismatch WARNING            | test_lint_cli_datatype_mismatch         | ADDED
lint CLI: unit_vector_missing INFO             | test_lint_cli_unit_vector_missing       | ADDED
lint CLI: --output file                        | test_lint_cli_output_file               | OK
lint CLI: stdout                               | test_lint_cli_stdout                    | OK
lint CLI: summary counts                       | test_lint_cli_summary_counts            | OK
```

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| System Audit         | No FLOWS/ERD/ARCH artifacts; lint stub 10L  |
| Step 0               | HOLD — scope correct for Phase 4            |
| Section 1  (Scope)   | 1 WARNING                                   |
| Section 2  (AC)      | 1 CRITICAL GAP, 2 WARNINGs                  |
| Section 3  (UX)      | 1 CRITICAL GAP, 1 WARNING                   |
| Section 4  (Risk)    | 1 CRITICAL GAP, 2 WARNINGs                  |
| Section 5  (Deps)    | 1 CRITICAL GAP, 1 WARNING                   |
| Section 6  (Correct) | 2 CRITICAL GAPs, 2 WARNINGs                 |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 2 CRITICAL GAPs, 3 WARNINGs                 |
| Section 8  (Quality) | 1 CRITICAL GAP (same as Sec 6), 1 WARNING   |
| Section 9  (Tests)   | 4 CRITICAL gaps, 5 WARNING gaps             |
| Section 10 (Perf)    | 1 WARNING (dimension_vector caching)        |
+--------------------------------------------------------------------+
| PLAN.md updated      | 8 truths added (3 [review]), __init__.py    |
|                      | artifact added, 6 tests added               |
| CONTEXT.md updated   | 7 decisions locked, 2 items deferred        |
| Error/rescue map     | 8 methods mapped, 0 CRITICAL GAPsremaining |
| Failure modes        | 6 total, 0 remaining unrescued              |
| Delight opps         | N/A (HOLD mode)                             |
| Diagrams             | Data flow, error/rescue, test coverage      |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## What already exists
- `detect_unit()` in `unit_detect.py` — returns exact string keys needed for UNIT_STRING_TO_IRI
- `ingest_rdf.py` `fields_to_graph()` — writes `Literal(field.detected_unit)` confirming plain string literal
- `rdf_utils.query_graph()` — SPARQL helper with known None/URIRef gotchas (documented in memory)
- `rosetta/cli/lint.py` — 10-line stub with `@click.command()`, ready for replacement
- `pyproject.toml` entry `rosetta-lint = "rosetta.cli.lint:cli"` already wired

## Dream state delta (12-month)
This plan delivers correct Phase 4 unit validation. Remaining gap: no streaming output, no multi-schema batch mode, no HTML report. These are Phase 8+ concerns.
