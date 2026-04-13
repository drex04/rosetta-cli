# Phase 06 — rosetta-rml-gen Context

## Locked Decisions

- **D06-01:** One `rr:TriplesMap` per decisions file (all fields share a single logical source and subject map). Multi-source decisions are out of scope for Plan 01.
- **D06-02:** Use `rdflib.Graph` with `BNode()` for all anonymous RML resources — no f-string template serialization.
- **D06-03:** `source_format=json` → `ql:JSONPath` + `$.fieldname` references; `source_format=csv` → `ql:CSV` + bare column name.
- **D06-04:** `field_ref` defaults to last URI path segment when absent (`source_uri.rsplit("/",1)[-1]`).
- **D06-05:** FnML (`fnml_function`) is deferred to Plan 02. Plan 01 emits plain `rml:reference` only.

## Decisions (added during plan-review 2026-04-13)

- [review] D-06-R01: README must NOT document `conversion_fn` — the model field is `fnml_function`; pydantic silently ignores unknown fields so passing `conversion_fn` gives exit 0 but no FnML block. Removed from README until Plan 02 ships.
- [review] D-06-R02: `rr:subjectMap` template hardcodes `{id}` as the source record key for subject IRI generation. Documented in README. Convention: source data must have an `id` field.
- [review] D-06-R03: `URIRef(decision.target_uri)` accepts malformed URIs without validation — deferred. URIs originate from approved decisions, which upstream SHACL validation should enforce.
- [review] D-06-R04: README `--source-format` type label corrected from `TEXT` to `[json|csv]` to match Click's actual rendering.

## Deferred Ideas

- FnML `fnml_function` branch in `_add_predicate_object_map` — Plan 02 scope.
- `extra="forbid"` on `MappingDecision` to catch unknown JSON keys at parse time — low priority; decisions come from approved upstream sources.
- Per-decision `rr:subjectMap` (different subject templates per source field) — not needed for Phase 1 flat-schema use case.
- URI validation for `target_uri` before `URIRef()` construction — low priority given upstream SHACL gate.
