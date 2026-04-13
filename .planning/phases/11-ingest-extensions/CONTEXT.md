# Phase 11: rosetta-ingest Extensions — Locked Decisions

## Scope
Two independent plans:
- **11-01:** XSD parser — `.xsd` files → `list[FieldSchema]` → Turtle
- **11-02:** JSON sample deduction — raw JSON instance data → inferred schema → Turtle

---

## Plan 11-01: XSD Parser

### G1 — xs:choice branch representation
All branches of `xs:choice` are emitted as separate optional fields (`required=False`,
regardless of `minOccurs` on the parent `xs:choice`). No data is lost; consumers see all
possible field alternatives.

### G2 — Named type resolution
Named `xs:complexType` definitions (global, within the same document) are fully resolved.
`dispatch_parser` builds a type registry from all top-level `xs:complexType[@name]` before
walking elements. Nested anonymous complex types are resolved inline.
`xs:include` and `xs:import` are **not** supported — raise `ValueError`:
`"XSD xs:include/xs:import is not supported; inline all types before ingestion."`.

### G3 — Entry point for field extraction
Prefer top-level `xs:element` nodes that reference or inline a `xs:complexType`.
If no top-level element exists, walk all global named `xs:complexType` definitions.
Result is a `list[FieldSchema]` that includes **both containers and leaves**. Container
elements (`xs:complexType` with children) are emitted with `data_type="object"` and their
`children` list populated. Leaf elements emit no children. `rose:hasChild` arcs link
containers to their children in the Turtle output.

### XSD type → FieldSchema.data_type mapping
| XSD types | data_type |
|-----------|-----------|
| `string`, `token`, `normalizedString`, `NMTOKEN`, `ID`, `IDREF`, `anyURI`, `date`, `dateTime`, `time`, `duration`, `language`, `Name`, `NCName` | `"string"` |
| `decimal`, `float`, `double` | `"number"` |
| `integer`, `int`, `long`, `short`, `byte`, `nonNegativeInteger`, `positiveInteger`, `unsignedInt`, `unsignedLong` | `"integer"` |
| `boolean` | `"boolean"` |
| anything else / unknown | `"string"` |

### Slug derivation
1. `targetNamespace` last path segment (split on `/` or `:`), slugified
2. Fallback: filename stem
3. Fallback: `"schema"`

### Field name strategy
Use the leaf `xs:element/@name` directly (no path qualification). If two elements at
different nesting levels share the same name, last-encountered-wins (consistent with
OpenAPI multi-schema merge behaviour). Document as known limitation in README.

### xs:attribute handling
`xs:attribute` elements within a `xs:complexType` are emitted as fields with
`required = (use == "required")` and `data_type` mapped via the same XSD type table.

### xs:restriction handling
Treat as the same `data_type` as the base type. Enumeration constraints are captured in
`sample_values` (the `xs:enumeration` values, if present).

### sample_values / stats
XSD files carry no instance data. `sample_values = []`, `numeric_stats = None`,
`categorical_stats = None` for all fields. `rose:stats` blank nodes are **not** emitted.
`xs:enumeration` values from `xs:restriction` are collected into `sample_values` (strings).

---

## Plan 11-02: JSON Sample Deduction

### G4 — Degenerate input (direct data walking, no genson)
After `_build_fields` runs on the normalised object list, if no fields are produced
(e.g. input was `[]`, `[1,2,3]`, scalar, or `{}`), raise:
`ValueError("Sample JSON produced no fields — input must be a non-empty object or array of objects")`

### G5 — Slug for stdin
When `--input-format json-sample` is used with stdin (no path), slug defaults to `"sample"`.
Consistent with JSON Schema fallback behaviour.

### Pipeline — direct recursive data walking (no genson)
genson was originally chosen but discards sample values, leaving all `numeric_stats=None`.
Since graph embeddings require real stats on leaf fields, we walk the raw data directly:

```
sample.json  →  json.load()  →  envelope unwrap  →  _build_fields() recursive walk
             →  list[FieldSchema] with children + sample_values + numeric_stats
```

Type inference is done in Python from the actual values across all objects
(bool → "boolean", int → "integer", float/mixed → "number", dict → "object", else → "string").
No `genson` dependency.

### RDF nesting model
Container fields (`data_type="object"`) emit `rose:hasChild` arcs to child field URIs.
Child URIs use `__` separator: `f:position__hoehe_m`.
`rdfs:label` on child fields is the **leaf name only** (e.g. `"hoehe_m"`), not the full path.
This is the representation intended for graph embeddings in a future `rosetta-embed` phase.

### Shared infrastructure (added in 11-01 Task 1, used by both plans)
- `FieldSchema.children: list[FieldSchema]` — default `[]`, backward-compatible
- `ROSE_HAS_CHILD = URIRef("http://rosetta.interop/ns/hasChild")`
- `_emit_field(g, field, F, uri_key)` — recursive helper in `ingest_rdf.py`; replaces
  flat loop in `fields_to_graph`

### Format detection
`json-sample` is **never** auto-detected from file extension (`.json` already means
`json-schema`). Must be passed explicitly via `--input-format json-sample`.

### Input shape — three accepted patterns
1. **Direct array:** `[{"field": val}, ...]` — items fed to genson directly
2. **Envelope (single-key dict wrapping array):** `{"key": [{"field": val}, ...]}` —
   if the dict has exactly one value that is a non-empty list of objects, unwrap it.
   Handles real-world fixtures like `deu_patriot_sample.json` (`{"erkannte_ziele": [...]}`).
3. **Flat single object:** `{"field": val, ...}` — treated as one sample object

### Nested objects
Nested object fields (e.g. `position`, `identifikation`) receive `data_type="object"`
as inferred by genson. They are emitted in output but have no unit detection or stats.
Document as known limitation in README.

---

## Shared

---

## Decisions (added in review)

- [review] **defusedxml for XSD parsing**: `xsd_parser.py` uses `defusedxml.ElementTree`
  instead of stdlib `xml.etree.ElementTree`. Rationale: prevents XXE (billion-laughs,
  external entity) attacks when processing externally-sourced NATO XSD files. Drop-in
  compatible API. Added to `pyproject.toml` dependencies.

- [review] **Circular xs:complexType guard**: `_collect` receives `visited: set[str] | None`
  and skips (with stderr warning) any named type already in the set. Prevents
  `RecursionError` on self-referencing schemas.

- [review] **Empty XSD raises ValueError**: `parse_xsd` raises `ValueError("No xs:element
  declarations found in XSD")` when `_collect` returns an empty list. Consistent with other
  parsers that reject empty/degenerate input.

- [review] **Multi-key envelope → each list-of-dicts key becomes a container**: `_infer_data_type`
  extended to return `"object"` for list-of-dicts values; `_build_fields` recurses into
  the combined items of such keys. Multi-key dicts like `{"targets": [...], "metadata": [...]}`
  produce multiple top-level container fields rather than being silently mangled to "string".

- [review] **Multi-key envelope implementation strategy**: normalisation `objects = [data]` for `len(list_values) > 1` is correct; `_infer_data_type` extended to return `"object"` for list-of-dicts values; `_build_fields` flattens list items when recursing. This achieves truth #10 without changing the normalisation path.

- [review] **`json.load` exception wrapping**: `JSONDecodeError` and `RecursionError` both caught and re-raised as `ValueError` for consistent exit-1 behavior. Pattern matches json_schema_parser error handling convention.

- [review] **`unit_detect.py` `_grad` → `"degree"`**: `grad` added to degree pattern. This affects all parsers using `detect_unit()`. Acceptable — `grad` is a legitimate German/international degree abbreviation in NATO field naming conventions.

- [review] **`max_sample_rows` threading to json-sample**: `parse_json_sample` receives `max_sample_rows` from `dispatch_parser`, applies `objects[:max_sample_rows]` after normalisation. Consistent with CSV parser cap behavior.

- [review] **Post-`_build_fields` empty-fields guard**: Empty dict `{}` produces `objects=[{}]`, passes `if not objects`, but `_build_fields([{}])` returns `[]`. Guard added after build step raises ValueError. Consistent with G4 decision.

## Deferred Ideas

- Language tag preservation on `rose:originalLabel` — deferred from phase 10 review
- XSD xs:choice containing nested xs:complexType branch — only leaf xs:choice branches tested;
  complex branch is handled correctly by _collect logic but has no dedicated test (phase 11)

---

### dispatch_parser changes
- Add `elif ext == ".xsd": fmt = "xsd"` to extension detection block
- Add `elif fmt == "xsd": ...` dispatch case (lazy import `xsd_parser`)
- Add `elif fmt == "json-sample": ...` dispatch case (lazy import `json_sample_parser`)
- Error message for unknown format updated to include new values

### CLI help text
`--input-format` help updated to: `"csv, json-schema, openapi, xsd, json-sample"`
