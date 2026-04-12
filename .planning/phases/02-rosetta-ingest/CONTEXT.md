# Phase 2: rosetta-ingest — Locked Decisions

## Format Detection
Auto-detect input format from file extension:
- `.csv` → csv parser
- `.json` → json-schema parser
- `.yaml` / `.yml` → openapi parser
- stdin (`-`) or ambiguous extension → requires `--input-format` explicit flag

CLI change: add `--input-format` option (separate from `--format` which controls output RDF serialization).

## Field URI Pattern
`http://rosetta.interop/field/{NATION}/{schema_slug}/{field_name}`

Schema slug derivation:
- CSV: filename stem (e.g. `nor_radar` from `nor_radar.csv`)
- JSON Schema: slugify of `title` or last segment of `$id` (e.g. `deu_patriot`)
- OpenAPI: slugify of `info.title` (e.g. `usa_c2`)

In Turtle output, emit a per-schema prefix:
```
@prefix f: <http://rosetta.interop/field/NOR/nor_radar/> .
```
Then use `f:sporings_id`, `f:hoyde_m`, etc.

Rationale: hierarchical (not hash) for SPARQL readability and debuggability; slug provides disambiguation between multiple schemas from the same nation.

## Stats Source per Format
- CSV: compute stats from the data rows in the file
- JSON Schema: compute stats from the top-level `examples` array
- OpenAPI: compute stats from `components.schemas.<name>.examples` array
- If no sample data present: omit `rose:stats` blank node for that field (don't emit empty stats)

## Stats Shape
Blank node (not named node):
```turtle
f:hoyde_m
    a rose:Field ;
    rose:stats [
        rose:count  "7"^^xsd:integer ;
        rose:min    "1500.0"^^xsd:double ;
        rose:max    "11000.0"^^xsd:double ;
        rose:mean   "6328.57"^^xsd:double ;
    ] .
```
Categorical / string fields:
```turtle
f:klassifisering
    a rose:Field ;
    rose:stats [
        rose:count         "7"^^xsd:integer ;
        rose:distinctCount "3"^^xsd:integer ;
    ] .
```

## Unit Detection
Simple regex on field name + description string. Result annotated as `rose:detectedUnit` with a plain string literal (e.g. `"meter"`, `"foot"`, `"knot"`, `"km_per_hour"`, `"degree"`). Full QUDT mapping is deferred to Phase 4 (rosetta-lint).

Key patterns:
- `_m` suffix or `meter` in description → `"meter"`
- `_km` or `kilometer` → `"kilometer"`
- `_ft` or `feet` or `foot` → `"foot"`
- `_kts` or `knot` → `"knot"`
- `_kmh` or `km/h` or `km_h` → `"km_per_hour"`
- `_deg` or `_grader` or `degree` or `decimal degree` → `"degree"`
- `_dbm` or `dBm` → `"dBm"`
- No match → omit `rose:detectedUnit`

## $ref Resolution
Internal (`#/components/schemas/X`) only. External file refs (e.g. `./other.json`) are not resolved — parser raises a clear `ValueError` with message "External $ref not supported: {ref}". README documents this limitation.

## Parser Module Layout
```
rosetta/core/parsers/
    __init__.py       # FieldSchema dataclass, schema_slug(), dispatch_parser()
    csv_parser.py     # parse_csv(src, path, nation, max_sample_rows) -> tuple[list[FieldSchema], str]
    json_schema_parser.py  # parse_json_schema(src, path, nation) -> tuple[list[FieldSchema], str]
    openapi_parser.py      # parse_openapi(src, path, nation) -> tuple[list[FieldSchema], str]
rosetta/core/unit_detect.py   # detect_unit(name, description) -> str | None
                              # compute_stats(sample_values) -> tuple[dict|None, dict|None]
rosetta/core/ingest_rdf.py    # fields_to_graph(fields, nation, slug) -> rdflib.Graph (pure serializer)
```

---

## Decisions (added in plan-review)

- [review] `dispatch_parser(src: TextIO, path: Path, input_format, nation)` — unified API. CLI opens file once via `open_input()`; path used only for extension detection and slug fallback. All three parsers return `(list[FieldSchema], slug)`. Submodule imports inside `dispatch_parser` are lazy (function-local) to avoid circular imports.
- [review] JSON Schema slug fallback: if `title` absent and `$id` absent, use `path.stem` as slug and emit stderr warning. Prevents URI collisions on schemas missing both metadata fields.
- [review] `ingest_rdf.py` explicit import: `from rosetta.core.rdf_utils import ROSE_NS as ROSE, bind_namespaces, save_graph`. `xsd:` prefix explicitly bound so typed literals render correctly in Turtle output.
- [review] `_m` unit regex must be end-anchored (`_m$` or equivalent token boundary) to prevent false-positives on `_kmh`, `_max`, `_mean`, etc. Validated by Done-when test: `detect_unit("hastighet_kmh", "") == "km_per_hour"`.
- [review] Stats computation moved out of `fields_to_graph` into `compute_stats()` in `unit_detect.py`. `FieldSchema` gains `numeric_stats: dict | None` and `categorical_stats: dict | None`. `fields_to_graph` is a pure RDF serializer.
- [review] `--max-sample-rows N` CLI option (default 1000) caps CSV sampling memory. `parse_csv` uses `itertools.islice`.
- [review] `--nation` is `required=True`; stdin without `--input-format` exits 1 with descriptive message.
- [review] OpenAPI stats source is schema-level `examples` only — per-property `example` (singular) keys are ignored.
- [review] OpenAPI multi-schema merge: fields from all `components.schemas` merged into flat list; duplicate field names → last-schema-wins. Documented as Phase 2 known limitation.

## Deferred Ideas

- Streaming CSV parser for rows beyond `--max-sample-rows` (deferred to Phase 4 when real data introduced)
- Per-property `example` key support in OpenAPI (deferred — schema-level `examples` covers all current fixtures)
- Multi-schema OpenAPI namespace isolation (each schema gets its own slug prefix instead of flat merge) — deferred to when a fixture exposes the collision
