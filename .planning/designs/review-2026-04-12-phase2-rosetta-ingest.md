# Plan Review — Phase 2 rosetta-ingest
**Date:** 2026-04-12  
**Mode:** HOLD SCOPE  
**Plan:** `.planning/phases/02-rosetta-ingest/02-01-PLAN.md`

---

## Mode Selected
HOLD SCOPE — plan boundaries accepted as-is; review focused on correctness, error paths, and test coverage.

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | Phase 1 complete; 12 tests passing;         |
|                      | 4 uncommitted files (Task 1 residuals)      |
|                      | No architecture artifacts (.planning/codebase/) |
| Step 0               | Scope accepted; no expansions               |
| Section 1  (Scope)   | 2 issues found (dispatch_parser contract)   |
| Section 2  (AccCrit) | 3 issues found (exit code, examples key)    |
| Section 3  (UX)      | 2 issues found (stdin guard, --nation)      |
| Section 4  (Risk)    | 4 issues found (ROSE_NS, slug fallback,     |
|                      |   multi-schema, blank node stability)        |
| Section 5  (Deps)    | 3 issues found (xsd prefix, TextIO contract)|
| Section 6  (Correct) | 4 issues found (_m regex, sample_values     |
|                      |   typing, examples key conflict)             |
+--------------------------------------------------------------------+
| Section 7  (Eng Arch)| 2 issues (circular import, double-parse)    |
| Section 8  (Code Ql) | 2 issues (stats layer, _m regex)            |
| Section 9  (Tests)   | Diagram produced; 9/17 paths untested       |
| Section 10 (Perf/Err)| 3 issues (OOM risk, opaque exceptions,      |
|                      |   stdin fallback)                            |
+--------------------------------------------------------------------+
| PLAN.md updated      | 8 truths added ([review] prefix)            |
|                      | 2 artifacts updated (unit_detect, test_ingest)|
| CONTEXT.md updated   | 9 decisions locked; 3 items deferred        |
| Error/rescue registry| 9 methods mapped, 2 CRITICAL GAPS → PLAN.md |
| Failure modes        | 9 total, 2 CRITICAL GAPS (exit 1 test,      |
|                      |   dispatch_parser contract)                  |
| Delight opps         | N/A (HOLD mode)                             |
| Diagrams produced    | 1 (test coverage ASCII)                     |
| Unresolved decisions | 0                                           |
+====================================================================+
```

---

## Critical Findings Resolved

### C1: dispatch_parser / open_input contract contradiction
**Problem:** Plan had `dispatch_parser(path: Path, ...)` but individual parsers need `TextIO`. File would be opened twice, or `open_input` handle unused. JSON Schema slug also requires pre-parsing (can't derive slug from path alone).  
**Resolution:** `dispatch_parser(src: TextIO, path: Path, input_format, nation)` — CLI opens file once via `open_input()`; parsers return `(list[FieldSchema], slug)`.

### C2: schema_slug fallback undefined
**Problem:** When JSON Schema has no `title` and no `$id`, the implementer would produce `""` or `"unknown"` slugs, causing URI collisions.  
**Resolution:** Fall back to `path.stem` with a stderr warning. Identical behavior to CSV.

### C3: ROSE_NS import not specified
**Problem:** `ingest_rdf.py` references `ROSE.Field`, `ROSE.stats`, etc. with no import specified — NameError on first run.  
**Resolution:** Added explicit import to Task 6: `from rosetta.core.rdf_utils import ROSE_NS as ROSE, bind_namespaces, save_graph`.

---

## Key Architectural Change: Stats Layer

Stats computation moved from `fields_to_graph()` (RDF emitter) to a `compute_stats()` helper in `unit_detect.py`. `FieldSchema` gains `numeric_stats: dict | None` and `categorical_stats: dict | None`. This makes `fields_to_graph` a pure serializer, enables independent stats testing, and prepares for `rosetta-embed` (Phase 3) to consume stats without needing rdflib.

---

## Test Coverage Diagram

```
CODEPATH COVERAGE — Plan 02-01 (after review additions)
==========================================================================
Path                                              Status
--------------------------------------------------------------------------
1.  CSV parse happy path                          [✓] test_ingest_csv
2.  CSV all-empty column → string type            [✗] not planned
3.  JSON Schema parse happy path                  [✓] test_ingest_json_schema
4.  JSON Schema no `examples` → no stats          [✓] test_json_schema_no_examples (added)
5.  JSON Schema no title/id → slug fallback       [✗] not planned (low risk, stderr only)
6.  OpenAPI parse happy path                      [✓] test_ingest_openapi
7.  OpenAPI with internal $ref                    [~] one $ref covered; chained not tested
8.  OpenAPI external $ref → ValueError            [✓] test_openapi_external_ref_raises
9.  OpenAPI multiple schemas in components        [✗] not planned (documented limitation)
10. Unit detect — all 8 patterns + no-match       [✓] test_unit_detect (parametrized + None)
11. fields_to_graph numeric stats                 [~] via test_ingest_csv SPARQL
12. fields_to_graph categorical stats             [✗] not planned
13. fields_to_graph no sample values → no stats   [✓] test_ingest_no_sample_data (added)
14. CLI exit 0 on success                         [✓] implicit in runner tests
15. CLI exit 1 on parse error (stderr message)    [✓] test_ingest_error_exit (added)
16. schema_slug with special characters           [~] test_schema_slug (scope unspecified)
17. stdin + missing --input-format guard          [✓] test_stdin_missing_format (added)
==========================================================================
After additions: [✓]: 9   [~]: 3   [✗]: 5
```

---

## Error & Rescue Registry

| # | Origin | Exception | Trigger | CLI Behavior | Tested |
|---|--------|-----------|---------|--------------|--------|
| 1 | `io.open_input` | `FileNotFoundError` | Input file missing | exit 1, str(e) to stderr | Yes (added) |
| 2 | `dispatch_parser` | `ValueError` | Unknown ext + no `--input-format` | exit 1, descriptive msg | Yes (added) |
| 3 | `parse_csv` | `csv.Error` | Malformed CSV | exit 1 | No |
| 4 | `parse_json_schema` | `json.JSONDecodeError` | Invalid JSON | exit 1 | No |
| 5 | `parse_json_schema` | `ValueError` | Missing `properties` key | exit 1, readable msg | No |
| 6 | `parse_openapi` | `yaml.YAMLError` | Invalid YAML | exit 1 | No |
| 7 | `parse_openapi` | `ValueError` | External `$ref` | exit 1 | Yes |
| 8 | `fields_to_graph` | *(none — pure serializer)* | — | — | — |
| 9 | `save_graph` | `OSError` | Output path not writable | exit 1 | No |

---

## Data Flow Diagram

```
stdin / file
     │
     ▼
open_input(path)  ──────── FileNotFoundError → exit 1
     │ TextIO
     ▼
dispatch_parser(src, path, format, nation, max_sample_rows)
     │
     ├─ .csv  → parse_csv()
     │           itertools.islice(reader, max_sample_rows)
     │           infer data_type
     │           detect_unit()      ─── regex (anchored)
     │           compute_stats()    ─── 50% threshold
     │           return (fields, slug)
     │
     ├─ .json → parse_json_schema()
     │           json.load()
     │           slug = title / $id / path.stem
     │           detect_unit()
     │           compute_stats()
     │           return (fields, slug)
     │
     └─ .yaml → parse_openapi()
                 yaml.safe_load()
                 resolve internal $ref
                 slug = info.title
                 detect_unit()
                 compute_stats()
                 return (fields, slug)
                     │
                     └─ external $ref → ValueError → exit 1
     │
     ▼
fields_to_graph(fields, nation, slug)  ← pure RDF serializer
     │
     ▼
save_graph(g, out, "turtle")
     │
     ▼
output .ttl file / stdout
```

---

## What Already Exists
- `rdf_utils.py`: `bind_namespaces()`, `load_graph()`, `save_graph()`, `query_graph()` — all tested
- `io.py`: `open_input()`, `open_output()` with Path + encoding support
- Three fixture files: `nor_radar.csv` (11 cols, 7 rows), `deu_patriot.json` (9 props, 3 examples), `usa_c2.yaml` (9 props, 3 examples)
- `ingest.py` CLI stub (18 lines)

## Dream State Delta
After this plan ships: `rosetta-ingest` is a production-quality converter. Gap to 12-month ideal: streaming mode for large files, external `$ref` resolution, per-property examples support in OpenAPI, multi-schema namespace isolation. All explicitly deferred in CONTEXT.md.
