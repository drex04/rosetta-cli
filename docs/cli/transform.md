# rosetta transform

Materializes a YARRRML mapping against a concrete data file via [morph-kgc](https://morph-kgc.readthedocs.io/), then frames the resulting RDF as JSON-LD using a `@context` derived from the master LinkML schema.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.transform
    :command: cli
    :prog_name: rosetta transform
    :depth: 2

## SHACL validation

Every `transform` invocation must explicitly declare its validation intent. Pass `--shapes-dir` to enable inline SHACL validation, or `--no-validate` to opt out. Passing neither (or both) is a usage error (exit 2).

When `--shapes-dir` is provided, SHACL validation runs against the in-memory materialized graph **before** emitting JSON-LD. On any violation, JSON-LD emission is blocked, the validation report is written to `--validate-report` (or stderr), and the process exits 1.

When `--no-validate` is provided, validation is skipped and a warning is emitted to stderr to record the opt-out in the audit trail.

## Examples

### With SHACL validation (recommended)

```bash
rosetta transform demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  --shapes-dir rosetta/policies/shacl/ \
  -o demo_out/nor_tracks.jsonld
```

### With validation report written to file

```bash
rosetta transform demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  --shapes-dir rosetta/policies/shacl/ \
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

A warning is emitted to stderr when `--no-validate` is used. Use `rosetta shapes` to generate a shapes directory if you do not already have one.

## Stdout collision guard

Both `--output` and `--validate-report` can target stdout. Setting both to stdout simultaneously is a `UsageError` (exit 2).

## Exit codes

- `0` — success. JSON-LD emitted. Empty materialized graph (0 triples) is not an error — a warning prints to stderr.
- `1` — runtime error or SHACL validation failure.
- `2` — Click validation error (missing required option, `--shapes-dir`/`--no-validate` conflict, stdout collision).

## See also

- [`rosetta compile`](compile.md) — produce the YARRRML mapping file consumed by `transform`.
- [`rosetta shapes`](shapes.md) — generate the shapes directory for `--shapes-dir`.
- [`rosetta validate`](validate.md) — standalone validator for offline validation.
