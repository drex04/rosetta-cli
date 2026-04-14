# Summary: Plan 12-01 — Schema Normalization (LinkML-based ingest pipeline)

## Status: Complete

- **Tests:** 166/166 passing (was 203 before; 48 v1 parser tests removed as planned)
- **New tests:** 20 (12 normalize + 4 ingest + 4 translate) + 9 embed tests rewritten
- **Ruff:** clean
- **basedpyright:** 0 errors (warnings only from untyped third-party stubs)

## What was built

### Deleted
- `rosetta/core/parsers/` — entire directory (7 files: _types.py, csv_parser.py, json_sample_parser.py, json_schema_parser.py, openapi_parser.py, xsd_parser.py, __init__.py)
- `rosetta/tests/test_ingest_json_sample.py`

### New files
- `rosetta/core/normalize.py` — `normalize_schema()` dispatcher for all 7 formats via schema-automator
- `rosetta/tests/test_normalize.py` — 12 tests covering all 7 formats + meta-tests

### Rewritten
- `rosetta/cli/ingest.py` — calls `normalize_schema()`, outputs `.linkml.yaml`; `--nation` removed; `--schema-name` added
- `rosetta/core/translation.py` — `translate_schema(SchemaDefinition)` replaces `translate_labels(Graph)`
- `rosetta/cli/translate.py` — LinkML YAML I/O; DeepL errors wrapped as RuntimeError
- `rosetta/core/embedding.py` — `extract_text_inputs_linkml()` added; v1 `extract_text_inputs()` + rdflib imports deleted
- `rosetta/cli/embed.py` — YAML-only input; `--mode` removed; 4 `--include-*` flags added
- `rosetta/tests/test_ingest.py` — 4 CLI tests for LinkML YAML output
- `rosetta/tests/test_translate.py` — 4 tests for `translate_schema()`
- `rosetta/tests/test_embed.py` — v1 TTL tests deleted; 9 new `extract_text_inputs_linkml` tests added

### Updated
- `pyproject.toml` — added `schema-automator>=0.5.5`, `sssom>=0.4.15`; removed `defusedxml`
- `README.md` — rosetta-ingest, rosetta-translate, rosetta-embed sections updated

## Issues Encountered

### Issue 1: `json_schema_from_open_api` takes a dict, not a path
The function signature differs from the plan — it accepts a parsed dict, not a file path string. Fixed by reading+parsing the YAML file before passing to the function.

### Issue 2: `linkml_runtime.Format.JSON` dropped
`linkml_runtime` dropped `Format.JSON` (only `Format.JSONLD` exists). Applied module-level monkey-patch inside `normalize.py` before any schema-automator importer loads.

### Issue 3: pyparsing DEFAULT_WHITE_CHARS pollution (critical)
`schema_automator`/`pydbml` strips `\n` from `pyparsing.ParserElement.DEFAULT_WHITE_CHARS`, which corrupts rdflib's SPARQL parser in the same process. Fixed: `normalize_schema()` now saves and restores the whitespace chars around every importer call.

### Issue 4: OpenAPI branch used `json.loads` on YAML
The initial normalize.py read the YAML file with `json.loads`, which fails for valid YAML. Fixed to use `yaml.safe_load`.

## Quality Warnings

- basedpyright reports `reportMissingTypeStubs` and `reportUnknownMemberType` for schema-automator, genson, linkml_runtime (all untyped third-party libraries). Not actionable.
- pydbml emits `PyparsingDeprecationWarning` during tests (upstream issue, not ours).

## Known Broken State (by design)

After Phase 12, `rosetta-suggest`, `rosetta-accredit`, and other downstream tools that consume embed JSON output are non-functional pending Phase 13/14 updates. `rosetta-embed` itself is updated (Task 7) to accept LinkML YAML.
