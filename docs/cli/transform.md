# rosetta transform

Materializes a YARRRML mapping against a concrete data file via [morph-kgc](https://morph-kgc.readthedocs.io/), then frames the resulting RDF as JSON-LD using a `@context` derived from the master LinkML schema.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.transform
    :command: cli
    :prog_name: rosetta transform
    :depth: 2

## SHACL validation

Every `transform` invocation must explicitly declare its validation intent. Pass `--shapes` to enable inline SHACL validation, or `--no-validate` to opt out. Passing neither (or both) is a usage error (exit 2).

`--shapes` accepts a single `.ttl` file or a directory of `.ttl` files (walked recursively). When provided, SHACL validation runs against the in-memory materialized graph **before** emitting JSON-LD. On any violation, JSON-LD emission is blocked, the validation report is written to `--validate-report` (or stderr), and the process exits 1.

When `--no-validate` is provided, validation is skipped and a warning is emitted to stderr to record the opt-out in the audit trail.

Datatype validation failures (e.g., "Value is not Literal with datatype xsd:double") typically mean the source value was emitted as a plain string instead of a typed literal. See [Datatype handling](../concepts/type-handling.md) for causes and fixes.

## Examples

### With SHACL validation — directory of shapes (recommended)

```bash
rosetta transform demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  --shapes rosetta/policies/shacl/ \
  -o demo_out/nor_tracks.jsonld
```

### With SHACL validation — single shapes file

```bash
rosetta transform demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  --shapes master_cop.shapes.ttl \
  -o demo_out/nor_tracks.jsonld
```

### With validation report written to file

```bash
rosetta transform demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  --shapes rosetta/policies/shacl/ \
  -o demo_out/nor_tracks.jsonld \
  --validate-report report.json
```

### Skipping validation (opt-out)

```bash
rosetta transform demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  --no-validate \
  -o demo_out/nor_tracks.jsonld
```

A warning is emitted to stderr when `--no-validate` is used.

## Stdout collision guard

Both `--output` and `--validate-report` can target stdout. Setting both to stdout simultaneously is a `UsageError` (exit 2).

## Exit codes

- `0` — success. JSON-LD emitted. Empty materialized graph (0 triples) is not an error — a warning prints to stderr.
- `1` — runtime error or SHACL validation failure.
- `2` — usage error (missing `--shapes`/`--no-validate`, both provided, stdout collision).

## See also

- [`rosetta compile`](compile.md) — produce the YARRRML mapping file consumed by `transform`.
