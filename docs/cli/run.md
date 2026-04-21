# rosetta run

Materializes a YARRRML mapping against a concrete data file via [morph-kgc](https://morph-kgc.readthedocs.io/), then frames the resulting RDF as JSON-LD using a `@context` derived from the master LinkML schema.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.run
    :command: cli
    :prog_name: rosetta run
    :depth: 2

## Examples

### Basic materialization

```bash
rosetta run demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml
```

### Write JSON-LD to file

```bash
rosetta run demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  -o demo_out/nor_tracks.jsonld
```

### With inline SHACL validation

```bash
rosetta run demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  -o demo_out/nor_tracks.jsonld \
  --validate rosetta/policies/shacl/ \
  --validate-report report.json
```

When `--validate` is provided, SHACL validation runs against the in-memory materialized graph BEFORE emitting JSON-LD. On any violation, JSON-LD emission is blocked, the validation report is written to `--validate-report` (or stderr), and the process exits 1.

## Stdout collision guard

Both `--output` and `--validate-report` can target stdout. Setting both to stdout simultaneously is a `UsageError` (exit 2).

## Exit codes

- `0` — success. JSON-LD emitted. Empty materialized graph (0 triples) is not an error — a warning prints to stderr.
- `1` — runtime error or SHACL validation failure.
- `2` — Click validation error (missing required option, stdout collision).

## See also

- [`rosetta compile`](compile.md) — produce the YARRRML mapping file consumed by `run`.
- [`rosetta shacl-gen`](shacl-gen.md) — generate the shapes directory for `--validate`.
- [`rosetta validate`](validate.md) — standalone validator for offline validation.
