# rosetta-shacl-gen

Auto-generates SHACL shapes from a master LinkML schema. Supports closed-world default with `sh:ignoredProperties` for PROV-O / dcterms / rdf:type, plus QUDT unit-aware value shapes for slots whose name patterns map to QUDT IRIs via `detect_unit`.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.shacl_gen
    :command: cli
    :prog_name: rosetta-shacl-gen
    :depth: 2

## Examples

```bash
# Default: closed-world shapes with ignored properties baked in
uv run rosetta-shacl-gen \
  --input rosetta/tests/fixtures/nations/master_cop.linkml.yaml \
  --output master.shacl.ttl

# Open-world shapes (no sh:closed true, no sh:ignoredProperties from rosetta)
uv run rosetta-shacl-gen \
  --input master.linkml.yaml \
  --open \
  --output master.open.shacl.ttl

# Stream to stdout for piping
uv run rosetta-shacl-gen --input master.linkml.yaml | head -40
```

## Closed-world defaults

By default, every emitted `sh:NodeShape` has `sh:closed true` plus an `sh:ignoredProperties` list that tolerates downstream metadata stamping:

- `prov:wasGeneratedBy`
- `prov:wasAttributedTo`
- `dcterms:created`
- `dcterms:source`
- `rdf:type`

Pass `--open` to disable both — useful when the master schema is intentionally extensible.

## Unit-aware shapes

Slots whose name or description maps to a QUDT IRI via `rosetta.core.unit_detect.detect_unit` produce a `sh:property` block constraining `qudt:hasUnit` to that IRI. Coverage today (after Phase 19 Task 0):

| Slot suffix pattern | QUDT IRI |
|---|---|
| `*_m`, `*_meter`, `*_meters` | `unit:M` |
| `*_ft`, `*_foot`, `*_feet` | `unit:FT` |
| `*_knot`, `*_knots` | `unit:KN` |
| `*_bearing`, `*_degrees`, `*_degree` | `unit:DEG` |
| `*_vertical_rate` + description containing `feet per minute` / `ft/min` / `fpm` | `unit:FT-PER-MIN` |

Slots whose name doesn't match a recognized pattern produce no unit shape — no false-positive constraint. Add explicit `unit:` annotations to the master schema to broaden coverage.

## Exit codes

- `0` — success; SHACL Turtle written.
- `1` — generation failed (parse error, unwritable output, etc.).
- `2` — Click usage error (missing `--input`, etc.).
