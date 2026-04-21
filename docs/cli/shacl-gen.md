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

# Short-flag equivalent for --output
uv run rosetta-shacl-gen --input master.linkml.yaml -o master.shacl.ttl

# Open-world shapes (no sh:closed true, no sh:ignoredProperties from rosetta)
uv run rosetta-shacl-gen \
  --input master.linkml.yaml \
  --open \
  --output master.open.shacl.ttl

# Stream to stdout for piping
uv run rosetta-shacl-gen --input master.linkml.yaml | head -40
```

## Closed-world defaults

By default, every emitted `sh:NodeShape` has `sh:closed true` plus an `sh:ignoredProperties` list that tolerates downstream metadata stamping and unit declarations:

- `prov:wasGeneratedBy`
- `prov:wasAttributedTo`
- `dcterms:created`
- `dcterms:source`
- `rdf:type`
- `qudt:hasUnit`

Pass `--open` to disable both — useful when the master schema is intentionally extensible.

## Unit-aware shapes

For each class whose slots resolve to one or more QUDT units via `rosetta.core.unit_detect.detect_unit`, the generator attaches a single consolidated `sh:property` block:

```turtle
mc:AirTrack sh:property [
    sh:path qudt:hasUnit ;
    sh:in (unit:DEG unit:KN unit:FT unit:FT-PER-MIN unit:NauticalMile)
] .
```

Semantics: **if** an instance of the class declares `qudt:hasUnit`, it must be one of the units the schema recognises for that class. Instances that omit `qudt:hasUnit` entirely vacuously satisfy the constraint — so the shape never blocks valid data, but does catch a typo'd or foreign unit IRI.

`qudt:hasUnit` is whitelisted in the baked-in `sh:ignoredProperties` list so closed-world shapes do not reject data that opts in to declaring its unit.

Coverage today (after Phase 19 Task 0):

| Slot suffix pattern | QUDT IRI |
|---|---|
| `*_m`, `*_meter`, `*_meters` | `unit:M` |
| `*_ft`, `*_foot`, `*_feet` | `unit:FT` |
| `*_knot`, `*_knots` | `unit:KN` |
| `*_bearing`, `*_degrees`, `*_degree` | `unit:DEG` |
| `*_vertical_rate` + description containing `feet per minute` / `ft/min` / `fpm` | `unit:FT-PER-MIN` |

Slots whose name doesn't match a recognized pattern produce no unit shape — no false-positive constraint. Add explicit `unit:` annotations to the master schema to broaden coverage.

## Override workflow

The canonical production layout splits generated and hand-authored shapes into sibling directories so regenerations are lossless:

```
rosetta/policies/shacl/
├── generated/
│   └── master.shacl.ttl        ← written by rosetta-shacl-gen (rerunnable)
└── overrides/
    └── track_bearing_range.ttl  ← hand-authored tightening (never touched by regen)
```

- **`generated/`** — the output of `rosetta-shacl-gen`. Treat it as a build artifact: check in to track drift, but do not edit it directly.
- **`overrides/`** — any `.ttl` files here are merged on top of the generated shapes by `rosetta-validate --shapes-dir` and `rosetta-yarrrml-gen --validate --shapes-dir` (both walk the directory recursively). Use this directory for:
    - Tightening a generated constraint (e.g., `mc:AirTrackBearingRangeShape` adds `0–360` range to the `mc:hasBearing` slot).
    - Cross-class constraints not expressible in LinkML.
    - Experimental shapes before deciding to teach the generator.

**Regen safety:** `rosetta-shacl-gen --output generated/master.shacl.ttl` only writes its single `--output` target — it will never read, modify, or delete anything under `overrides/`. A byte-identity test (`test_override_survives_regen`) pins this invariant.

**Non-shape files** — if a `.ttl` in `--shapes-dir` contains no `sh:NodeShape` / `sh:PropertyShape` triples, the loader emits a stderr warning and merges it anyway (e.g., a vocabulary file used to resolve prefixes). This is intentional: silent skip would be more surprising than silent absorption.

**Symlink safety** — the walker uses `os.walk(followlinks=False)`, so symlink loops inside a shapes dir cannot hang the loader or cause duplicate merges.

## Exit codes

- `0` — success; SHACL Turtle written.
- `1` — generation failed (parse error, unwritable output, etc.).
- `2` — Click usage error (missing `--input`, etc.).

## See also

- [`rosetta-validate`](validate.md) — consume the generated shapes against a data graph (`--shapes` or `--shapes-dir`).
- [`rosetta run`](run.md) — materialize a pipeline and validate inline with `--validate <shapes-dir>`.
