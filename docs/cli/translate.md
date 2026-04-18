# rosetta-translate

Normalises non-English class titles, slot titles, and descriptions to English via DeepL before embedding. Accepts a LinkML YAML file and outputs a LinkML YAML file with translated titles and descriptions; original values are preserved in `aliases`.

## Command reference

::: mkdocs-click
    :module: rosetta.cli.translate
    :command: cli
    :prog_name: rosetta-translate
    :depth: 2

## Requirements

Set `DEEPL_API_KEY` to your DeepL API key, or pass `--deepl-key`. For English-source schemas, pass `--source-lang EN` — the tool becomes a no-op (no API call), which keeps your pipeline uniform across languages.

## Pipeline example

```bash
# Norwegian side — translate, then embed both originals and English
uv run rosetta-ingest    --input fixtures/nor_radar.csv --output nor_radar.linkml.yaml
uv run rosetta-translate --input nor_radar.linkml.yaml  --output nor_radar_en.linkml.yaml --source-lang auto

uv run rosetta-embed     --input nor_radar.linkml.yaml    --output nor_radar_nb.emb.json
uv run rosetta-embed     --input nor_radar_en.linkml.yaml --output nor_radar_en.emb.json

# Master side
uv run rosetta-ingest    --input fixtures/master_cop.ttl --format rdfs --output master_cop.linkml.yaml
uv run rosetta-translate --input master_cop.linkml.yaml  --output master_cop_en.linkml.yaml --source-lang EN  # no-op
uv run rosetta-embed     --input master_cop_en.linkml.yaml --output master_cop.emb.json

# Compare NB-source vs EN-normalised suggestions
uv run rosetta-suggest --output suggestions_nb.sssom.tsv nor_radar_nb.emb.json master_cop.emb.json
uv run rosetta-suggest --output suggestions_en.sssom.tsv nor_radar_en.emb.json master_cop.emb.json
```

For English schemas, the uniform invocation is:

```bash
uv run rosetta-translate --input eng_schema.linkml.yaml --output eng_schema_en.linkml.yaml --source-lang EN
```

## Exit codes

- `0` — success.
- `1` — translation or I/O error.
