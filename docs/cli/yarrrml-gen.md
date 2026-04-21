# rosetta-yarrrml-gen

Generates a `linkml-map` [`TransformationSpecification`](https://linkml.io/linkml-map/) YAML from an approved SSSOM audit log plus source and master LinkML schemas.

With `--run`, the same invocation:

1. Compiles the spec to [YARRRML](https://rml.io/yarrrml/) via the forked `linkml_map.compiler.yarrrml_compiler.YarrrmlCompiler`.
2. Materialises the YARRRML mapping against a concrete data file via [morph-kgc](https://morph-kgc.readthedocs.io/).
3. Frames the resulting RDF as JSON-LD using a `@context` derived from the master LinkML schema.

!!! note "Scope"
    Single-source data binding only. JSON-LD `@frame` output and multi-source binding are deferred.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.yarrrml_gen
    :command: cli
    :prog_name: rosetta-yarrrml-gen
    :depth: 2

## Behavioural matrix (stdout)

| `--run` | `--output` | `--jsonld-output` | stdout contents |
|---------|------------|-------------------|-----------------|
| off | — | n/a | TransformSpec YAML |
| off | set | n/a | (empty; YAML to file) |
| on | — | — | TransformSpec YAML, then JSON-LD |
| on | — | set | TransformSpec YAML only |
| on | set | — | JSON-LD (YAML to file) |
| on | set | set | (empty; YAML to file, JSON-LD to file) |

With `--run + --jsonld-output` (and no `--output`) the CLI still writes the YAML to stdout; pass `--output` to redirect it cleanly.

## Source-format resolution

`--source-format` is **optional**. If omitted, the builder reads `annotations.rosetta_source_format` from the source schema (stamped by `rosetta-ingest` on every generated schema since Phase 16-00). Either must be present — otherwise exit `1`.

## Examples

### Spec only

```bash
uv run rosetta-yarrrml-gen \
  --sssom store/audit-log.sssom.tsv \
  --source-schema demo_out/nor_radar.linkml.yaml \
  --master-schema demo_out/master_cop.linkml.yaml \
  --output demo_out/nor_to_mc.transform.yaml \
  --coverage-report demo_out/nor_to_mc.coverage.json
```

Spec output (excerpt):

```yaml
comments:
- rosetta:source_format=csv
id: https://rosetta.interop/transform/nor_radar-to-mc
class_derivations:
- name: Track
  populated_from: Observation
  slot_derivations:
    hasLatitude:
      name: hasLatitude
      populated_from: breddegrad
```

### Full pipeline (NOR radar CSV → JSON-LD)

```bash
uv run rosetta-yarrrml-gen \
  --sssom store/audit-log.sssom.tsv \
  --source-schema demo_out/nor_radar.linkml.yaml \
  --master-schema demo_out/master_cop.linkml.yaml \
  --output demo_out/nor_to_mc.transform.yaml \
  --run \
  --data demo_out/nor_radar.csv \
  --jsonld-output demo_out/nor_tracks.jsonld \
  --workdir demo_out/morph_artifacts
```

JSON-LD output (excerpt):

```json
{
  "@context": { "mc": "https://ontology.nato.int/core/MasterCOP#" },
  "@graph": [
    {
      "@id": "nor_radar:Observation/NOR-001",
      "@type": "Track",
      "hasAltitude": 4100.0,
      "hasLatitude": 60.1892
    }
  ]
}
```

## Inline SHACL validation

When combined with `--run`, the `--validate` flag runs SHACL validation against the in-memory materialized graph BEFORE emitting JSON-LD. On any violation, JSON-LD emission is blocked, the validation report is written to stderr (or `--validate-report PATH`), and the process exits 1.

```bash
uv run rosetta-yarrrml-gen \
  --sssom approved.sssom.tsv \
  --master-schema master.linkml.yaml \
  --source-schema nor.linkml.yaml \
  --run \
  --data nor.csv \
  --output transform.yaml \
  --jsonld-output out.jsonld \
  --validate \
  --shapes master.shacl.ttl \
  --validate-report report.json
```

### Requirements

`--validate` requires both `--run` AND `--shapes-dir`. Either alone (or `--validate` alone) raises a Click `UsageError` (exit 2).

### Failure-mode contract

On a SHACL violation:

- **No JSON-LD bytes are written** to `--jsonld-output` (file is not created or truncated).
- The `ValidationReport` JSON is written to stderr by default, or to `--validate-report PATH` when supplied.
- A summary line `"SHACL validation failed: N violation(s), M warning(s). JSON-LD emission blocked."` is written to stderr.
- Exit code is `1`.

### Stdout collision guard

Three flags can be set to `-` to write to stdout: `--output -`, `--jsonld-output -`, `--validate-report -`. Setting any two simultaneously is a `UsageError` (exit 2) — caught at step 0 before materialization.

Additionally, `--validate-report -` combined with `--run` **without an explicit `--jsonld-output FILE`** is also rejected: under `--run`, `--jsonld-output` defaults to stdout, so the validation-report bytes would interleave with the materialized JSON-LD stream on the same FD.

### Exit codes

- `0` — TransformSpec generated; if `--run --validate`, validation passed and JSON-LD was emitted.
- `1` — `--validate` violation or generic runtime error.
- `2` — Click usage error (missing/conflicting flags).

## Coverage report

When `--coverage-report` is provided, a JSON file matching the `CoverageReport` Pydantic model is written. Fields include: row-stage counts, resolved and unresolved class/slot mappings, datatype mismatches, composite-group resolution status, and required master slots that remain unmapped.

## Exit codes

- `0` — success. TransformSpec written; JSON-LD emitted if `--run`. Empty materialised graph (0 triples) is *not* an error — a warning prints to stderr and empty-graph JSON-LD is emitted with exit `0`.
- `1` — any of: malformed input file; unresolvable CURIEs (without `--force`); mixed-kind mapping; missing class-level mapping for a mapped slot; inconsistent `composition_expr`; empty filtered SSSOM (without `--allow-empty`); source schema has no `default_prefix`; `--source-format` omitted with no `annotations.rosetta_source_format`; `--run` without `--data`; `--workdir` not writable; YARRRML compilation error; morph-kgc materialisation error; `@context` generation error; JSON-LD serialisation error; `$(DATA_FILE)` placeholder missing from compiled YARRRML; write error on `--jsonld-output` or `--context-output`.
- `2` — Click validation error (missing required option).

## See also

- [`rosetta-shacl-gen`](shacl-gen.md) — generate the `--shapes-dir` contents (the canonical `generated/` + `overrides/` layout).
- [`rosetta-validate`](validate.md) — standalone validator; consumes the same `--shapes` / `--shapes-dir` inputs and can validate JSON-LD pipeline output offline.
