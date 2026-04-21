# rosetta validate

Validates a JSON-LD data file against [SHACL](https://www.w3.org/TR/shacl/) shape constraints using [pySHACL](https://github.com/RDFLib/pySHACL).

## Command reference

::: mkdocs-click
    :module: rosetta.cli.validate
    :command: cli
    :prog_name: rosetta validate
    :depth: 2

`SHAPES_DIR` is required.

## Examples

```bash
# Load all *.ttl shapes (generated + hand-authored overrides) from a directory
uv run rosetta validate out.jsonld rosetta/policies/shacl/ \
  -o validation.json
```

## Exit codes

- `0` — RDF conforms to the shapes.
- `1` — SHACL violations found (non-empty `sh:ValidationReport`).

## See also

- [`rosetta shapes`](shapes.md) — auto-generate the `SHAPES_DIR` input from a master LinkML schema; documents the `generated/` + `overrides/` directory convention.
- [`rosetta transform`](transform.md) — chain materialization and validation in one step via `--validate <shapes-dir>`.
