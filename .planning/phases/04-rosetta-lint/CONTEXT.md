# Phase 4 Context — rosetta-lint

## Locked Decisions

### D1 — CLI inputs
`rosetta-lint --source <national.ttl> --master <master.ttl> --suggestions <suggestions.json> [--output <lint.json>] [--strict]`

Three inputs required: source national RDF, master RDF, and suggestions JSON from rosetta-suggest. Unix-composable; output defaults to stdout.

### D2 — QUDT unit comparison via curated TTL
- Source unit: `rose:detectedUnit` string literal (e.g. `"metre"`) → mapped to QUDT IRI via dict in `units.py`
- Master unit: `qudt:unit` triple already contains a QUDT IRI (e.g. `unit:M`) — no mapping needed
- Compatibility: load `rosetta/policies/qudt_units.ttl`; compare `qudt:hasDimensionVector` literals between source and target unit IRIs
- Same dimension vector = compatible (possibly different units → WARNING + FnML)
- Different dimension vector = incompatible → BLOCK

### D3 — FnML registry as Turtle RDF
`rosetta/policies/fnml_registry.ttl` — unit conversion pairs as RDF triples with proper QUDT unit IRIs and FnML function IRIs. Queried via SPARQL in `units.py`. Chosen over JSON for linked-data consistency, SPARQL queryability, and clean Phase 5 (rml-gen) consumption.

### D4 — Severity rules
| Condition | Severity |
|-----------|----------|
| Incompatible dimension vectors | BLOCK |
| Compatible dims, different units (conversion needed) | WARNING + FnML suggestion |
| Source field has no detected unit | INFO |
| Master attribute has no `qudt:unit` | INFO |
| `rose:dataType` mismatch (numeric vs string) | WARNING |

### D5 — Exit codes and --strict
- Exit 0: no BLOCK findings
- Exit 1: one or more BLOCK findings
- `--strict`: WARNING findings promoted to BLOCK before exit-code check

### D6 — pyproject.toml already wired
`rosetta-lint = "rosetta.cli.lint:cli"` already registered. No pyproject.toml changes needed.

### D7 — Lint only checks top suggestion per field
For each source field URI, lint checks the #1 ranked suggestion only. This keeps output actionable; checking all top-k would produce noise. Top suggestion is `data[src_uri]["suggestions"][0]`; target URI is at key `"uri"`. Users who see unexpected BLOCKs should re-run rosetta-suggest with higher `--top-k`.

---

## Decisions (Review 2026-04-13)

- [review] UNIT_STRING_TO_IRI keys must be exact detect_unit() output strings: `"meter"`, `"kilometer"`, `"km_per_hour"`, `"foot"`, `"knot"`, `"degree"`, `"dBm"`. The example in Task 3 showing `"metre"` was wrong — ingest writes `Literal(field.detected_unit)` from detect_unit() return values directly.
- [review] `"dBm"` maps to `None` in UNIT_STRING_TO_IRI. No standard QUDT IRI exists; assigning a zero-dimension vector would produce false-compatible results with angle units. Emit `unit_not_detected` INFO and skip compatibility check.
- [review] New rule `unit_vector_missing` → INFO: emitted when `units_compatible()` returns `None` because both unit IRIs are present but their dimension vectors are absent from qudt_units.ttl. Prevents silent fallthrough.
- [review] `rosetta/policies/__init__.py` must be created (empty file) so `importlib.resources.files("rosetta.policies")` resolves without `ModuleNotFoundError`.
- [review] `suggest_fnml()` parameter renamed `fnml_graph` → `qudt_graph`. Both policy files are merged into one graph; the old name was misleading.
- [review] `dimension_vector()` must accept both short-form (`unit:M`) and full IRI (`http://qudt.org/vocab/unit/M`) inputs — source units arrive as short-form from UNIT_STRING_TO_IRI; master units arrive as full URIRefs from the graph query.
- [review] Summary counts reflect final post-`--strict` severities: if `--strict` is active, `summary.warning == 0`.

## Deferred Ideas

- Add `--top-k` lint flag to check top-N suggestions per field instead of just top-1 (deferred — top-1 is correct for actionability; revisit in Phase 8 accredit feedback loop)
- Performance: pre-build `{iri: vector}` dict from qudt_units.ttl to replace per-call SPARQL in `dimension_vector()` — not needed for ~20 units but worth doing if schema sizes grow past 500 fields
