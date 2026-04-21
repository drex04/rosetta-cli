# rosetta compile

Compiles an approved SSSOM audit log plus source and master LinkML schemas into a [YARRRML](https://rml.io/yarrrml/) mapping file, ready for `rosetta run`.

Internally, this builds a `linkml-map` [`TransformationSpecification`](https://linkml.io/linkml-map/) YAML, then compiles it to YARRRML via the forked `YarrrmlCompiler`.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.compile
    :command: cli
    :prog_name: rosetta compile
    :depth: 2

## Examples

### Compile to YARRRML (stdout)

```bash
rosetta compile store/audit-log.sssom.tsv \
  --source-schema demo_out/nor_radar.linkml.yaml \
  --master-schema demo_out/master_cop.linkml.yaml
```

### Compile to file with coverage report

```bash
rosetta compile store/audit-log.sssom.tsv \
  --source-schema demo_out/nor_radar.linkml.yaml \
  --master-schema demo_out/master_cop.linkml.yaml \
  -o demo_out/nor_to_mc.yarrrml.yml \
  --coverage-report demo_out/nor_to_mc.coverage.json
```

### Also save the intermediate TransformSpec

```bash
rosetta compile store/audit-log.sssom.tsv \
  --source-schema demo_out/nor_radar.linkml.yaml \
  --master-schema demo_out/master_cop.linkml.yaml \
  -o demo_out/nor_to_mc.yarrrml.yml \
  --spec-output demo_out/nor_to_mc.transform.yaml
```

## Coverage report

When `--coverage-report` is provided, a JSON file matching the `CoverageReport` Pydantic model is written. Fields include: row-stage counts, resolved and unresolved class/slot mappings, datatype mismatches, composite-group resolution status, and required master slots that remain unmapped.

## Exit codes

- `0` — success. YARRRML written to output.
- `1` — any of: malformed input; unresolvable CURIEs; mixed-kind mapping; missing class-level mapping; inconsistent `composition_expr`; empty filtered SSSOM; source schema has no `default_prefix`; missing `annotations.rosetta_source_format` on source schema.
- `2` — Click validation error (missing required option).

## See also

- [`rosetta run`](run.md) — execute the compiled YARRRML mapping against a data file.
- [`rosetta-shacl-gen`](shacl-gen.md) — generate SHACL shapes for validation.
