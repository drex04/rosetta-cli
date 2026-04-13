# rosetta-cli

Composable CLI tools for semantic mapping between NATO defense schemas and a master ontology.

Each tool reads from files or stdin and writes to files or stdout, so they chain together with Unix pipes.

## Installation

```bash
uv sync
```

After syncing, all tools are available via `uv run <tool>`.

## Tools

### rosetta-ingest

Parses a national schema file and emits an RDF graph (Turtle by default).

**Supported input formats** (auto-detected from file extension):

| Extension        | Format         |
| ---------------- | -------------- |
| `.csv`           | CSV with stats |
| `.json`          | JSON Schema    |
| `.yaml` / `.yml` | OpenAPI 3.x    |

```
Usage: rosetta-ingest [OPTIONS]

  Ingest a national schema into the RDF store.

Options:
  -i, --input PATH          Input file path  [default: stdin]
  -o, --output PATH         Output file path [default: stdout]
  -f, --format TEXT         Output RDF format [default: turtle]
  --input-format TEXT       Force input format: csv, json-schema, openapi
  -n, --nation TEXT         Nation code (e.g. NOR, DEU, USA)  [required]
  --max-sample-rows INT     Max CSV rows for stats [default: 1000]
  -c, --config PATH         Path to rosetta.toml
```

**Example:**

```bash
uv run rosetta-ingest -i rosetta/tests/fixtures/nor_radar.csv -n NOR -o nor_radar.ttl
uv run rosetta-ingest -i rosetta/tests/fixtures/usa_c2.yaml -n USA -o usa_c2.ttl

```

---

### rosetta-embed

Reads a Turtle file produced by `rosetta-ingest` and computes LaBSE embeddings for every schema attribute. Outputs a JSON file mapping each attribute URI to its embedding vector.

```
Usage: rosetta-embed [OPTIONS]

  Embed RDF schema attributes using LaBSE.

Options:
  -i, --input PATH    Turtle input file [default: stdin]
  -o, --output PATH   JSON output file  [default: stdout]
  --mode TEXT         Embedding mode    [default: lexical-only]
  --model TEXT        Model name        [default: sentence-transformers/LaBSE]
  -c, --config PATH   Path to rosetta.toml
```

**Example:**

```bash
uv run rosetta-embed -i nor_radar.ttl -o nor_radar_emb.json
uv run rosetta-embed -i usa_c2.ttl -o usa_c2_emb.json
```

To cross-verify with a different model, pass `--model`:

```bash
# multilingual-E5 (strong on Norwegian and other non-English schemas)
uv run rosetta-embed -i nor_radar.ttl -o nor_radar_emb_e5.json \
  --model intfloat/multilingual-e5-base

# Norwegian-specific (National Library of Norway BERT)
uv run rosetta-embed -i nor_radar.ttl -o nor_radar_emb_nb.json \
  --model NbAiLab/nb-bert-base
```

> **E5 models** (`intfloat/multilingual-e5-*`) require a `"passage: "` prefix on indexed texts and `"query: "` on query texts. `rosetta-embed` applies the passage prefix automatically when an E5 model is detected; no extra flags needed.

---

### rosetta-suggest

Compares source embeddings against master ontology embeddings and ranks the best matches by cosine similarity. Flags low-confidence matches as anomalies.

```
Usage: rosetta-suggest [OPTIONS]

  Rank master ontology candidates for source schema fields.

Options:
  --source PATH           Source embeddings JSON   [required]
  --master PATH           Master embeddings JSON   [required]
  --top-k INT             Max suggestions per field
  --min-score FLOAT       Minimum cosine score
  --anomaly-threshold FLOAT  Anomaly flag threshold
  --output PATH           Output file [default: stdout]
  --config PATH           rosetta.toml [default: rosetta.toml]
```

**Example:**

```bash
uv run rosetta-suggest --source nor_radar_emb.json --master usa_c2_emb.json --output nor_radar_to_usa_c2_suggestions.json
```

**Output format** — one entry per source field:

```json
{
  "http://rosetta.interop/ns/DEU/deu_patriot/Breite": {
    "suggestions": [
      { "uri": "http://rosetta.interop/ns/USA/usa_c2/lat_dd", "score": 0.94 },
      ...
    ],
    "anomaly": false
  }
}
```

---

## Configuration

`rosetta.toml` controls defaults for all tools. CLI flags take precedence over the config file.

```toml
[general]
store_path = "store"
default_format = "turtle"

[embed]
model = "sentence-transformers/LaBSE"
mode  = "lexical-only"

[suggest]
top_k             = 5
min_score         = 0.0
anomaly_threshold = 0.3
```

---

## End-to-end demo

The script below runs all three tools against the bundled fixture files. It ingests schemas from three nations, embeds them, then uses the USA schema as the master ontology to generate mapping suggestions for Germany and Norway.

```bash
scripts/demo.sh
```

See [`scripts/demo.sh`](scripts/demo.sh) for the full walkthrough, or run it directly:

```bash
bash scripts/demo.sh
```

---

## Running tests

```bash
uv run pytest
```

Slow tests (model downloads) are marked with `@pytest.mark.slow` and can be skipped:

```bash
uv run pytest -m "not slow"
```
