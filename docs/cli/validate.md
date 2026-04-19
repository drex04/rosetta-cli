# rosetta-validate

Validates an RDF Turtle file against [SHACL](https://www.w3.org/TR/shacl/) shape constraints using [pySHACL](https://github.com/RDFLib/pySHACL).

## Command reference

::: mkdocs-click
    :module: rosetta.cli.validate
    :command: cli
    :prog_name: rosetta-validate
    :depth: 2

At least one of `--shapes` or `--shapes-dir` must be provided.

## Examples

```bash
# Load all *.ttl shapes (generated + hand-authored overrides) from a directory
uv run rosetta-validate \
  --data mapping.rml.ttl \
  --shapes-dir rosetta/policies/shacl/ \
  -o validation.json
```

## Exit codes

- `0` — RDF conforms to the shapes.
- `1` — SHACL violations found (non-empty `sh:ValidationReport`).
