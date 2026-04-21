# rosetta validate

Validates an RDF data file (Turtle or JSON-LD) against [SHACL](https://www.w3.org/TR/shacl/) shape constraints using [pySHACL](https://github.com/RDFLib/pySHACL).

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
uv run rosetta validate mapping.rml.ttl rosetta/policies/shacl/ \
  -o validation.json
```

## JSON-LD input

`rosetta validate` accepts JSON-LD as data input — useful for validating output from `rosetta run`. Format is autodetected by suffix:

- `.ttl` → Turtle
- `.jsonld`, `.json`, `.json-ld` → JSON-LD
- Anything else → fallback to Turtle

```bash
# Validate JSON-LD output from rosetta run
uv run rosetta validate out.jsonld rosetta/policies/shacl/ \
  -o validation.json
```

## Exit codes

- `0` — RDF conforms to the shapes.
- `1` — SHACL violations found (non-empty `sh:ValidationReport`).

## See also

- [`rosetta shacl-gen`](shacl-gen.md) — auto-generate the `SHAPES_DIR` input from a master LinkML schema; documents the `generated/` + `overrides/` directory convention.
- [`rosetta run`](run.md) — chain materialization and validation in one step via `--validate <shapes-dir>`.
