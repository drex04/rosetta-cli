# rosetta ingest

Parses one or more source schemas and emits [LinkML](https://linkml.io/) schema YAML (`.linkml.yaml`). Input format is auto-detected from the file extension; pass `--schema-format` / `-f` to force a specific parser.

Optionally translates non-English titles to English via DeepL (`--translate`), aligns output to a master ontology (`--master`), and generates SHACL shapes alongside the LinkML output.

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

## Multi-schema input

Pass multiple source files in a single invocation to batch-ingest them:

```bash
rosetta ingest a.json b.xsd c.csv -o out/
```

Output routing rules:

- If `-o` / `--output` is a directory (or ends with `/`), each input file `name.ext` is written to `out/name.linkml.yaml` in that directory.
- If `-o` is omitted, each output file is written alongside its source file.
- If `-o` names a file (not a directory) and more than one input is given, the command exits `1` with a usage error — a single output path cannot absorb multiple schemas.

Prefix collision detection runs across all outputs in the target directory, including files produced earlier in the same invocation.

## Translation

Pass `--translate` (with an optional `--lang` source-language code) to translate non-English titles and descriptions to English before writing the LinkML output.

```bash
rosetta ingest deu_patriot.json --translate --lang DE -o out/
```

- Translation is performed via the DeepL API. Set the `DEEPL_API_KEY` environment variable before running — there is no CLI flag for the key.
- `--lang EN` (or omitting `--lang` when the source is already English) is a no-op: the command succeeds without making any API calls.
- Translated titles are written back into the `.linkml.yaml` output; the original values are preserved in per-slot `rosetta_original_title` annotations.

## Master ontology

Pass `--master <ontology.ttl>` to align ingested schemas against a master ontology:

```bash
rosetta ingest nor_radar.csv --master master_cop_ontology.ttl -o out/
```

When `--master` is supplied:

- The master ontology is parsed alongside the source schema.
- A SHACL shapes file (`<output-stem>.shacl.ttl`) is generated in the same output directory, derived from the master ontology classes that are reachable from the ingested slots.
- If no `rosetta.toml` exists in the current directory, a minimal scaffold is written to `rosetta.toml` recording the master ontology path and output directory for use by downstream tools.

## Examples

```bash
# Single schema — explicit output path
uv run rosetta ingest rosetta/tests/fixtures/nations/nor_radar.csv \
                      --output nor_radar.linkml.yaml

# Single schema with format override
uv run rosetta ingest rosetta/tests/fixtures/nations/deu_radar_sample.json \
                      -f json-sample \
                      --output deu_radar_sample.linkml.yaml

# Multi-schema batch into a directory
uv run rosetta ingest rosetta/tests/fixtures/nations/nor_radar.csv \
                      rosetta/tests/fixtures/nations/deu_patriot.json \
                      rosetta/tests/fixtures/nations/usa_c2.yaml \
                      -o out/

# Ingest with in-line translation (German source)
uv run rosetta ingest rosetta/tests/fixtures/nations/deu_patriot.json \
                      --translate --lang DE \
                      -o out/

# Ingest with master ontology alignment and SHACL generation
uv run rosetta ingest rosetta/tests/fixtures/nations/nor_radar.csv \
                      --master rosetta/tests/fixtures/nations/master_cop_ontology.ttl \
                      -o out/

# Full pipeline — multi-schema, translation, and master ontology in one call
uv run rosetta ingest rosetta/tests/fixtures/nations/nor_radar.csv \
                      rosetta/tests/fixtures/nations/deu_patriot.json \
                      --translate --lang DE \
                      --master rosetta/tests/fixtures/nations/master_cop_ontology.ttl \
                      -o out/
```

## Exit codes

- `0` — success.
- `1` — parse error, I/O error, prefix collision, or invalid multi-input/output combination.
