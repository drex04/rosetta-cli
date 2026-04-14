# Plan Review: Phase 12-01 Schema Normalization
Date: 2026-04-14
Mode: HOLD SCOPE

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | schema_automator not installed (expected);  |
|                      | parsers/ exists (expected); no XSD fixture  |
| Step 0               | HOLD — migration phase, scope correct       |
| Section 1 (Scope)    | 0 issues                                    |
| Section 2 (AC)       | 1 warning — DeepL mock target wording       |
| Section 3 (UX)       | 1 warning — downstream breakage undocumented|
| Section 4 (Risk)     | 0 issues                                    |
| Section 5 (Deps)     | 0 issues                                    |
| Section 6 (Correct.) | 1 warning — csv_parser.py omit from list    |
+--------------------------------------------------------------------+
| Section 7 (Arch)     | 4 issues: array handling, temp leaks,       |
|                      | CsvDataGeneralizer API, XSD schema_name     |
| Section 8 (Code Ql)  | 1 warning — translate_labels caller update  |
| Section 9 (Tests)    | 2 CRITICAL GAPS: no XSD fixture,           |
|                      | json-sample list input → empty schema       |
| Section 10 (Perf)    | 1 warning — no DeepL timeout                |
+--------------------------------------------------------------------+
| PLAN.md updated      | 5 truths added                              |
| CONTEXT.md updated   | 6 decisions locked, 3 items deferred        |
| Error/rescue registry| 7 methods, 1 CRITICAL GAP (DeepL uncaught) |
| Failure modes        | 6 total, 5 addressed → PLAN.md truths       |
| Diagrams produced    | data flow, error flow, test coverage below  |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## Data Flow Diagram

```
Input file
    │
    ▼
normalize_schema(path, fmt, schema_name)
    │
    ├─ fmt=None → auto-detect from extension
    │       .json → json-schema
    │       .xsd  → xsd
    │       .csv  → csv
    │       .tsv  → tsv
    │       .ttl/.owl/.rdf → rdfs
    │       .yaml/.yml → peek 512B → openapi? else ValueError
    │       other → ValueError ◄── RESCUED (CLI catch)
    │
    ├─ json-schema ──► JsonSchemaImportEngine().convert(path, name=name)
    │
    ├─ openapi ──────► json_schema_from_open_api(path)
    │                  → tmp.json (cleaned in finally)
    │                  → JsonSchemaImportEngine().convert(tmp, name=name)
    │
    ├─ xsd ──────────► XsdImportEngine().convert(path)
    │
    ├─ csv/tsv ──────► CsvDataGeneralizer(column_separator=sep)
    │                  .convert(path, schema_name=name)
    │
    ├─ json-sample ──► json.loads(path)
    │                  → iterate list items (if list) or add_object
    │                  → genson SchemaBuilder → inferred JSON Schema
    │                  → tmp.json (cleaned in finally)
    │                  → JsonSchemaImportEngine().convert(tmp, name=name)
    │
    └─ rdfs ─────────► RdfsImportEngine().convert(path, format="turtle")
           │
           ▼ (all branches)
    schema.name = name  (if name provided — post-assign uniformly)
           │
           ▼
    SchemaDefinition
           │
    ingest.py: yaml_dumper.dumps(schema) → output.write_text(...)
```

## Error Flow

```
normalize_schema raises ValueError (bad format)
    → ingest CLI: except Exception as e → click.echo(str(e), err=True) → sys.exit(1)

importer raises (malformed input)
    → propagates through normalize_schema
    → ingest CLI: caught → raw exception text → sys.exit(1)

translate_schema deepl failure
    → NOT caught → crash (⚠ uncaught — deferred fix)
    → translate CLI has no except block ← WARNING
```

## Test Coverage Diagram

```
normalize.py
├── json-schema  ✓ test_normalize_json_schema
├── openapi      ✓ test_normalize_openapi
├── xsd          ✓ test_normalize_xsd (inline tmp_path XSD)
├── csv          ✓ test_normalize_csv
├── tsv          ✓ test_normalize_tsv
├── json-sample  ✓ test_normalize_json_sample
├── rdfs         ✓ test_normalize_rdfs
├── auto .ttl    ✓ test_normalize_auto_detect_ttl
├── auto .json   ✓ test_normalize_auto_detect_json
├── stem name    ✓ test_normalize_schema_name_from_stem
├── override name✓ test_normalize_schema_name_override
└── bad ext      ✓ test_normalize_unsupported_raises

ingest.py CLI
├── json-schema  ✓ test_ingest_json_schema_cli
├── rdfs         ✓ test_ingest_rdfs_cli
├── --schema-name✓ test_ingest_schema_name_override
└── no --nation  ✓ test_ingest_no_nation_flag

translation.py
├── DE→EN class  ✓ test_translate_linkml_de_to_en
├── DE→EN slot   ✓ test_translate_linkml_slot
└── EN passthru  ✓ test_translate_linkml_passthrough

GAPS:
├── description translation  ✗ no test
├── empty schema (0 classes) ✗ no test
└── DeepL API failure        ✗ no test (deferred)
```

## What Already Exists

- `rosetta/tests/fixtures/`: `deu_patriot.json`, `deu_patriot_sample.json`, `nor_radar.csv`, `usa_c2.yaml` — all usable for format tests
- `deu_patriot.ttl` / `deu_patriot.ttl` in repo root — usable for rdfs test
- `genson` already installed — json-sample dep retained per G2
- `deepl` already installed — translate dep retained
- `rosetta/core/translation.py` exports `translate_labels` — complete rewrite to `translate_schema`

## Dream State Delta

After Phase 12, the pipeline is at: `ingest → normalize (LinkML) → translate`. Three phases remain:
- Phase 13: embed + suggest producing SSSOM output
- Phase 14: user review workflow

The plan correctly leaves downstream tools non-functional — this is the right call. The only risk is a confusing developer experience if someone tries the full pipeline before Phase 13.
