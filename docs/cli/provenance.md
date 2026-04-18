# rosetta-provenance

Records and queries [PROV-O](https://www.w3.org/TR/prov-o/) provenance metadata stamped onto Turtle artifacts. Each stamp increments a version counter.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.provenance
    :command: cli
    :prog_name: rosetta-provenance
    :depth: 2

## Artifact URI

The artifact URI is derived from the input filename stem: `mapping.rml.ttl` → `rose:mapping.rml`.

## Examples

```bash
# Stamp in place
uv run rosetta-provenance stamp mapping.rml.ttl --label "Initial NOR→USA mapping"

# Stamp to a new file (keep a versioned history on disk)
uv run rosetta-provenance stamp mapping.rml.ttl -o mapping.rml.v2.ttl --label "Reviewed"

# Query provenance history (text)
uv run rosetta-provenance query mapping.rml.ttl
# v1  2026-04-13T12:00:00+00:00  http://rosetta.interop/ns/agent/rosetta-cli  Initial NOR→USA mapping

# Query as JSON
uv run rosetta-provenance query mapping.rml.ttl --format json
```

## Exit codes

- `0` — success.
- `1` — parse or I/O error.
