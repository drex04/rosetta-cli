# rosetta ingest

Parses a source schema and emits a [LinkML](https://linkml.io/) schema YAML (`.linkml.yaml`). Input format is auto-detected from the file extension; pass `--schema-format` / `-f` to force a specific parser.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.ingest
    :command: cli
    :prog_name: rosetta ingest
    :depth: 2

## Supported formats

| Extension / `-f`/`--schema-format` | Format | Notes |
|------------------------------------|--------|-------|
| `.csv` / `csv` | CSV | Auto-detected |
| `.tsv` / `tsv` | TSV | Auto-detected |
| `.json` / `json-schema` | JSON Schema | Auto-detected from `.json` |
| `.yaml` / `.yml` / `openapi` | OpenAPI 3.x | Auto-detected |
| `.xsd` / `xsd` | XML Schema | Auto-detected |
| `json-sample` | JSON sample data | **Must pass `-f json-sample`** — no extension auto-detect |
| `.ttl` / `.owl` / `.rdf` / `rdfs` | RDFS/OWL vocabulary | Auto-detected from `.ttl`, `.owl`, `.rdf` |

### JSON-sample input shapes

`-f json-sample` accepts three shapes:

- **Top-level array** — `[{"field": value, ...}, ...]`
- **Flat object** (treated as a single-row sample) — `{"field": value, ...}`
- **Single-key envelope** — `{"key": [{"field": value, ...}, ...]}`

Nested objects are preserved as nested classes in the LinkML output.

## Stamped annotations

Every generated `.linkml.yaml` carries:

- `annotations.rosetta_source_format` — the detected or forced input format.
- Per-slot path annotations — `rosetta_csv_column` (CSV/TSV), `rosetta_jsonpath` (JSON Schema / JSON sample), or `rosetta_xpath` (XSD) — recording the original field path.

Downstream tools (notably `rosetta compile`) consume these annotations to emit source-format-aware RML mappings automatically.

## Prefix collision detection

If a `.linkml.yaml` file already exists in the same output directory with the same `default_prefix` or `id` (namespace IRI), `rosetta ingest` exits `1` with an error naming the conflicting file. This prevents ambiguous mappings downstream — use a unique output path for each schema sharing an output directory.

## Examples

```bash
uv run rosetta ingest rosetta/tests/fixtures/nations/nor_radar.csv \
                      --output nor_radar.linkml.yaml

uv run rosetta ingest rosetta/tests/fixtures/nations/deu_patriot.json \
                      --output deu_patriot.linkml.yaml

uv run rosetta ingest rosetta/tests/fixtures/nations/usa_c2.yaml \
                      --output usa_c2.linkml.yaml

uv run rosetta ingest rosetta/tests/fixtures/nations/deu_radar_sample.json \
                      -f json-sample \
                      --output deu_radar_sample.linkml.yaml
```

## Exit codes

- `0` — success.
- `1` — parse error, I/O error, or prefix collision.
