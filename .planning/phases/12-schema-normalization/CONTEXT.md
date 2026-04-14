# Phase 12: Schema Normalization — Locked Decisions

## Scope
One plan:
- **12-01:** Replace all custom parsers with schema-automator importers; adopt LinkML SchemaDefinition as the internal schema representation; update `rosetta-translate` for LinkML YAML I/O.

This is the first phase of the v2 migration. After Phase 12, `rosetta-embed` and downstream tools are intentionally non-functional pending Phase 13 (Semantic Matching) and Phase 14 (User Review).

---

## Format → Importer Decisions

### G1 — All 7 formats via schema-automator
All schema ingestion goes through schema-automator (v0.5.5+). No custom parsers.

| Format | Class | Module |
|--------|-------|--------|
| `json-schema` | `JsonSchemaImportEngine` | `schema_automator.importers.jsonschema_import_engine` |
| `openapi` | `json_schema_from_open_api()` + `JsonSchemaImportEngine` | same |
| `xsd` | `XsdImportEngine` | `schema_automator.importers.xsd_import_engine` |
| `csv` | `CsvDataGeneralizer(column_separator=",")` | `schema_automator.generalizers.csv_data_generalizer` |
| `tsv` | `CsvDataGeneralizer(column_separator="\t")` | same |
| `json-sample` | `genson.SchemaBuilder` → tmp JSON Schema → `JsonSchemaImportEngine` | genson (existing dep) |
| `rdfs` | `RdfsImportEngine(format="turtle")` | `schema_automator.importers.rdfs_import_engine` |

Rationale: `RdfsImportEngine` accepts Turtle natively (confirmed via source inspection: `rdflib.Graph().parse(file, format=format)`). Handles `rdfs:Class`, `rdfs:subClassOf`, `rdfs:comment`, `owl:DatatypeProperty`, `owl:ObjectProperty`. No format conversion needed for `.ttl` master ontology files.

### G2 — `json-sample` keeps genson
genson is retained for `json-sample` mode. In v2 we no longer need `numeric_stats` at ingestion time (stats were a v1 concern for RDF annotation), so genson's schema-only output is sufficient. `genson` → tmp JSON Schema → `JsonSchemaImportEngine` is the pipeline.

### G3 — `linkml-owl` is NOT used
`linkml-owl` goes LinkML → OWL (the reverse direction). Do not confuse with `RdfsImportEngine` which goes OWL/RDFS → LinkML.

---

## CLI Decisions

### G4 — Clean break: `rosetta-ingest` always outputs LinkML YAML
No backward compatibility shim. Output extension convention: `.linkml.yaml`. Downstream tools (`rosetta-embed`, `rosetta-suggest`, etc.) will be updated in Phase 13 and 14.

### G5 — `--nation` removed
The `--nation` flag was used to generate RDF URI slugs. LinkML schemas use `schema_name` as the identifier prefix. Not needed.

### G6 — `--schema-name` defaults to filename stem
`JsonSchemaImportEngine.convert(path, name=name)` requires a name. Default: `Path(input_path).stem`. Overridable with `--schema-name TEXT`.

### G7 — `rosetta-ingest` is role-agnostic
No `--mode source|master` flag. The caller decides whether a normalized schema is the source or the master. Roles are a concern of the matching step (Phase 13), not ingestion.

---

## Translation Decisions

### G8 — Translate `title` and `description`; preserve original in `aliases`
The `name` field (LinkML identifier, e.g. `geschwindigkeit_kmh`) is **never** modified — it is the structural key.

For each `ClassDefinition` and `SlotDefinition`:
- `title`: translated English label (derived from `name.replace("_", " ").title()` if absent)
- `description`: translated if present
- `aliases[0]`: original non-English `title` preserved here (prepend to existing aliases)

Rationale: `name` is used as a foreign key in schema references. Changing it breaks structural integrity. Phase 13 embed step will use `title` + `description` as the text for embedding.

### G9 — `--source-lang EN` is a passthrough
When `source_lang.upper() == "EN"`, return the schema object unchanged. No DeepL call.

---

## Dependency Decisions

### G10 — `sssom >= 0.4.15` added in Phase 12
`sssom` is added to deps in Phase 12 even though SSSOM output is not produced until Phase 13. Rationale: makes Phase 13 a pure implementation phase with no dep changes.

### G11 — `defusedxml` removed
`defusedxml` was only used by the v1 `xsd_parser.py`. Now that XSD parsing is handled by `XsdImportEngine` (which uses `lxml`), `defusedxml` is no longer needed.

---

## Review Decisions (2026-04-14)

- [review] json-sample array handling: iterate list items individually via `for item in data: builder.add_object(item)` — passing a raw list to `add_object` produces a top-level array schema that `JsonSchemaImportEngine` cannot extract slots from.
- [review] schema_name propagation: post-assign `schema.name = name` after all importer calls (uniform, API-agnostic) rather than passing `name=` per-importer — `XsdImportEngine` does not accept a `name` param.
- [review] CsvDataGeneralizer constructor API: `schema_name` is a method-level kwarg on `.convert()`, not the constructor — `CsvDataGeneralizer(column_separator=sep).convert(path, schema_name=name)`.
- [review] Temp file cleanup: both openapi and json-sample branches use `try/finally os.unlink(tmp_path)` to avoid leaking temp files on error.
- [review] XSD test fixture: `test_normalize_xsd` creates an inline minimal XSD via `tmp_path` — no fixture file; no dependency on Phase 11 artifacts.
- [review] `json_schema_from_open_api` function name must be verified pre-build: `python -c "from schema_automator.importers.jsonschema_import_engine import json_schema_from_open_api"`.
- [user] DeepL errors in `translate_schema` are caught and re-raised as `RuntimeError` with human-readable messages — three tiers: AuthorizationException, QuotaExceededException, DeepLException (catch-all). Tested in `test_translate_deepl_api_error`.
- [user] `rosetta-embed` rewritten in Phase 12 (Task 7) to accept LinkML YAML input only; TTL/RDF v1 path deleted entirely; `extract_text_inputs` and SPARQL helpers removed from `embedding.py`; 9 v1 tests deleted from `test_embed.py`; `--mode` option removed.
- [user] `--include-ancestors` supersedes `--include-parents` (ancestors is a strict superset). Both flags can be independently combined with `--include-children`.
- [user] Children are computed as classes where `is_a == node_name` — no SchemaView method needed; direct dict iteration over `schema.classes`.

## Deferred Ideas

- DeepL timeout/retry in `translate_schema` — low priority for CLI tool; deferred to Phase 14 polish.
- CLI-level error messages enriched with supported format list — deferred, current ValueError text is adequate.
- README note about Phase 12 downstream tool breakage — optional; plan design notes document this.

## Deferred to Later Phases

- SSSOM candidate output (Phase 13 — rosetta-suggest)
- Structural feature extraction / graph-neighborhood embedding (Phase 13)
- User review workflow and approved SSSOM file (Phase 14)
- Accreditation SSSOM store (Phase 14)
- FnO conversion functions / linting (Phase 15+, TBD)
