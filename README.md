# rosetta-cli

Composable CLI toolkit for semantic mapping between NATO defense schemas and a master ontology. Each tool reads from files or stdin and writes to files or stdout, chaining cleanly with Unix pipes.

## Installation

```bash
uv sync
```

All tools are available via `uv run <tool>` after syncing.

---

## Tools

### rosetta-ingest

Parses a schema file and emits a LinkML schema YAML (`.linkml.yaml`). Input format is auto-detected from the file extension.

#### Supported formats

| Extension / `--input-format` | Format | Notes |
|------------------------------|--------|-------|
| `.csv` / `csv` | CSV with statistical annotations | Auto-detected |
| `.tsv` / `tsv` | TSV with statistical annotations | Auto-detected |
| `.json` / `json-schema` | JSON Schema | Auto-detected from `.json` |
| `.yaml` / `.yml` / `openapi` | OpenAPI 3.x | Auto-detected |
| `.xsd` / `xsd` | XML Schema | Auto-detected |
| `json-sample` | JSON sample data | **Must pass `--input-format json-sample`** — no extension auto-detect |
| `rdfs` | RDFS/OWL vocabulary | **Must pass `--input-format rdfs`** |

**json-sample** accepts three input shapes:
- Top-level array: `[{"field": value, ...}, ...]`
- Flat object (treated as single-row sample): `{"field": value, ...}`
- Single-key envelope: `{"key": [{"field": value, ...}, ...]}`

Nested objects are preserved as nested classes in the LinkML output. Leaf field statistics (count, min, max, mean, stddev, histogram) are computed from the actual sample values.

```
Usage: rosetta-ingest [OPTIONS]

Options:
  -i, --input PATH         Input file (default: stdin)
  -o, --output PATH        Output file (default: stdout)
  --input-format TEXT      Force input format: csv, tsv, json-schema, openapi, xsd, json-sample, rdfs
  --schema-name TEXT       Schema name (default: filename stem)
  --max-sample-rows INT    Max rows read from sample for statistics  [default: 1000]
  -c, --config PATH        Path to rosetta.toml
```

**Example:**

```bash
uv run rosetta-ingest -i rosetta/tests/fixtures/nor_radar.csv    -o nor.linkml.yaml
uv run rosetta-ingest -i rosetta/tests/fixtures/deu_patriot.json -o deu.linkml.yaml
uv run rosetta-ingest -i rosetta/tests/fixtures/usa_c2.yaml      -o usa.linkml.yaml
uv run rosetta-ingest -i rosetta/tests/fixtures/deu_patriot_sample.json --input-format json-sample -o deu_sample.linkml.yaml
```

**Exit codes:** 0 on success, 1 on parse or I/O error.

---

### rosetta-translate

Normalises non-English class titles, slot titles, and descriptions to English via DeepL before embedding. Accepts a `.linkml.yaml` file and outputs a `.linkml.yaml` file with translated titles and descriptions; original values are preserved in `aliases`.

**Synopsis**

```bash
rosetta-translate [OPTIONS]
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--input FILE`, `-i FILE` | `-` (stdin) | LinkML YAML input file |
| `--output FILE`, `-o FILE` | `-` (stdout) | LinkML YAML output (English-normalised) |
| `--source-lang LANG` | `auto` | Source language code (`DE`, `NO`, etc.) or `auto` for server-side detection. Any `EN`/`EN-US`/`en` variant triggers passthrough — no API call. |
| `--config FILE`, `-c FILE` | `rosetta.toml` | Config file path |

**Requirements**

Set `DEEPL_API_KEY` to your DeepL API key. For English-source schemas, use `--source-lang EN` to bypass DeepL entirely.

**Pipeline example**

```bash
rosetta-ingest nor_radar.csv -o nor.linkml.yaml
rosetta-translate nor.linkml.yaml -o nor_en.linkml.yaml --source-lang NO
rosetta-embed nor_en.linkml.yaml -o nor_embeddings.json
rosetta-suggest nor_embeddings.json master_embeddings.json -o suggestions.json
```

For English schemas, `--source-lang EN` keeps the pipeline uniform:

```bash
rosetta-translate eng_schema.linkml.yaml -o eng_schema_en.linkml.yaml --source-lang EN
```

---

### rosetta-embed

Reads a `.linkml.yaml` file and computes embeddings for every schema slot. Outputs a JSON map of slot URI → embedding vector.

> **Note:** The first run downloads the model (~1.2 GB) from HuggingFace. Subsequent runs use the local cache.

```
Usage: rosetta-embed [OPTIONS]

Options:
  -i, --input PATH            LinkML YAML input file  (default: stdin)
  -o, --output PATH           JSON output file         (default: stdout)
  --include-definitions       Include slot definitions in the embedding text
  --include-parents           Include immediate parent class context
  --include-ancestors         Include full ancestor chain context (supersedes --include-parents)
  --include-children          Include direct child slot names in the embedding text
  --model TEXT                Sentence-transformer model  [default: intfloat/e5-large-v2]
  -c, --config PATH           Path to rosetta.toml
```

> **E5 models** (`intfloat/multilingual-e5-*`) receive the `"passage: "` prefix automatically on indexed texts. No extra flags needed.

**Example:**

```bash
uv run rosetta-embed -i nor.linkml.yaml -o nor_emb.json
uv run rosetta-embed -i usa.linkml.yaml -o usa_emb.json

# Richer context — include full ancestor chain and slot definitions
uv run rosetta-embed -i nor.linkml.yaml -o nor_emb.json \
  --include-ancestors --include-definitions

# Cross-verify with multilingual E5 (stronger on non-English schemas)
uv run rosetta-embed -i nor.linkml.yaml -o nor_emb_e5.json \
  --model intfloat/multilingual-e5-base
```

**Exit codes:** 0 on success, 1 on error.

---

### rosetta-suggest

Compares source embeddings against master embeddings and ranks candidates by cosine similarity. Flags low-confidence matches as anomalies. Optionally reads a ledger to boost accredited mappings and exclude revoked ones.

```
Usage: rosetta-suggest [OPTIONS]

Options:
  --source PATH              Source embeddings JSON   [required]
  --master PATH              Master embeddings JSON   [required]
  --top-k INT                Max suggestions per field  [default: 5]
  --min-score FLOAT          Minimum cosine score  [default: 0.0]
  --anomaly-threshold FLOAT  Anomaly flag threshold  [default: 0.3]
  --ledger PATH              Accreditation ledger.json (boosts accredited, excludes revoked)
  --output PATH              Output file  (default: stdout)
  --config PATH              Path to rosetta.toml
```

**Example:**

```bash
uv run rosetta-suggest \
  --source nor_emb.json \
  --master usa_emb.json \
  --output suggestions.json

# With accreditation feedback
uv run rosetta-suggest \
  --source nor_emb.json \
  --master usa_emb.json \
  --ledger store/ledger.json \
  --output suggestions.json
```

**Output format** — one entry per source field:

```json
{
  "http://rosetta.interop/ns/NOR/nor_radar/altitude_m": {
    "suggestions": [
      { "target_uri": "http://rosetta.interop/ns/master/altitude", "score": 0.94 }
    ],
    "anomaly": false
  }
}
```

**Exit codes:** 0 on success, 1 on error.

---

### rosetta-lint

Validates mapping suggestions against QUDT unit compatibility and XSD datatype rules. Emits a structured JSON report.

```
Usage: rosetta-lint [OPTIONS]

Options:
  --source PATH       National schema RDF (Turtle)   [required]
  --master PATH       Master ontology RDF (Turtle)   [required]
  --suggestions PATH  Suggestions JSON from rosetta-suggest  [required]
  --output PATH       Output file  (default: stdout)
  --strict            Treat WARNINGs as BLOCKs
  --config PATH       Path to rosetta.toml
```

**Findings:**

| Severity | Rule | Meaning |
|----------|------|---------|
| BLOCK | `unit_dimension_mismatch` | Source and target units measure different physical quantities |
| WARNING | `unit_conversion_required` | Same dimension, different scale — FnML conversion suggested |
| WARNING | `datatype_mismatch` | Numeric vs string type clash |
| INFO | `unit_not_detected` | Source field has no detectable unit |
| INFO | `master_unit_missing` | Master field has no `qudt:unit` annotation |
| INFO | `unit_vector_missing` | QUDT dimension vector absent for one or both units |

**Example:**

```bash
uv run rosetta-lint \
  --source nor.ttl \
  --master usa.ttl \
  --suggestions suggestions.json \
  --output lint.json

# Strict mode — WARNINGs become BLOCKs (useful as a CI gate)
uv run rosetta-lint --strict \
  --source nor.ttl \
  --master usa.ttl \
  --suggestions suggestions.json
```

**Exit codes:** 0 if no BLOCKs, 1 if any BLOCKs found.

---

### rosetta-validate

Validates an RDF Turtle file against SHACL shape constraints using pySHACL.

```
Usage: rosetta-validate [OPTIONS]

Options:
  --data PATH        RDF Turtle file to validate  [required]
  --shapes PATH      Single SHACL shapes Turtle file
  --shapes-dir PATH  Directory — loads all *.ttl files as shapes
  -o, --output PATH  Output file  (default: stdout)
  -c, --config PATH  Path to rosetta.toml
```

> At least one of `--shapes` or `--shapes-dir` must be provided.

**Example:**

```bash
uv run rosetta-validate \
  --data mapping.rml.ttl \
  --shapes rosetta/policies/mapping.shacl.ttl \
  -o validation.json

# Load all shapes from a directory
uv run rosetta-validate \
  --data mapping.rml.ttl \
  --shapes-dir rosetta/policies/ \
  -o validation.json
```

**Exit codes:** 0 if conforms, 1 if SHACL violations found.

---

### rosetta-rml-gen

Generates valid RML/FnML Turtle from an approved decisions file. The output is executable by RMLMapper.

```
Usage: rosetta-rml-gen [OPTIONS]

Options:
  --decisions PATH      Approved decisions JSON  [required]
  --source-file TEXT    Data file path to embed in rml:logicalSource (referenced, not read)  [required]
  --source-format [json|csv]  Reference formulation: json, csv  [default: json]
  --base-uri TEXT       Subject template base URI  [default: http://rosetta.interop/record]
  --output PATH         Output file  (default: stdout)
```

**Decisions format:**

```json
{
  "http://rosetta.interop/ns/NOR/nor_radar/altitude_m": {
    "target_uri": "http://rosetta.interop/ns/master/altitude"
  },
  "http://rosetta.interop/ns/NOR/nor_radar/speed_kn": {
    "target_uri": "http://rosetta.interop/ns/master/speed",
    "field_ref": "speed_kn"
  }
}
```

`field_ref` is optional — defaults to the last path segment of the source URI. FnML unit-conversion support (`fnml_function`) is added in a later phase.

**Subject field convention:** The generated `rr:subjectMap` uses `{base-uri}/{id}` as the subject template. Your source data must contain an `id` field (JSON key or CSV column) for RMLMapper to construct subject IRIs.

**Example:**

```bash
uv run rosetta-rml-gen \
  --decisions decisions.json \
  --source-file data/nor_radar.csv \
  --source-format csv \
  --output mapping.rml.ttl
```

**Exit codes:** 0 on success, 1 on invalid or empty decisions.

---

### rosetta-provenance

Records and queries PROV-O provenance metadata stamped onto Turtle artifacts. Each stamp increments a version counter.

```
Usage: rosetta-provenance [OPTIONS] COMMAND

Global options:
  -c, --config PATH   Path to rosetta.toml

Commands:
  stamp   Stamp PROV-O metadata onto a Turtle artifact
  query   Query provenance records stamped onto a Turtle artifact
```

**stamp:**

```
Usage: rosetta-provenance stamp [OPTIONS] INPUT

Options:
  -o, --output PATH   Output path (omit to overwrite INPUT in-place; use '-' for stdout)
  --agent TEXT        Agent URI  [default: http://rosetta.interop/ns/agent/rosetta-cli]
  -l, --label TEXT    Human-readable label for this stamp event
  --format TEXT       Stderr summary format: text, json  [default: text]
```

**query:**

```
Usage: rosetta-provenance query [OPTIONS] INPUT

Options:
  --format TEXT   Output format: text, json  [default: text]
```

**Example:**

```bash
# Stamp in-place
uv run rosetta-provenance stamp mapping.rml.ttl --label "Initial NOR→USA mapping"

# Stamp to new file
uv run rosetta-provenance stamp mapping.rml.ttl -o mapping.rml.v2.ttl --label "Reviewed"

# Query provenance history (text)
uv run rosetta-provenance query mapping.rml.ttl
# v1  2026-04-13T12:00:00+00:00  http://rosetta.interop/ns/agent/rosetta-cli  Initial NOR→USA mapping

# Query as JSON
uv run rosetta-provenance query mapping.rml.ttl --format json
```

The artifact URI is derived from the input filename stem: `mapping.rml.ttl` → `rose:mapping.rml`.

**Exit codes:** 0 on success, 1 on error.

---

### rosetta-accredit

Manages the mapping accreditation state machine. Mappings move through `pending` → `accredited` or `pending` → `revoked`. Accredited mappings are boosted in `rosetta-suggest`; revoked ones are excluded. The ledger is created automatically on first use.

```
Usage: rosetta-accredit [OPTIONS] COMMAND

Global options:
  --ledger PATH   Path to ledger.json  [default: store/ledger.json]
  -c, --config PATH

Commands:
  submit    Submit a mapping for review  (→ pending)
  approve   Approve a pending mapping   (pending → accredited)
  revoke    Revoke a pending or accredited mapping  (→ revoked)
  status    Show accreditation status for matching entries
```

**submit:**

```
Options:
  --source TEXT   Source field URI   [required]
  --target TEXT   Target field URI   [required]
  --actor TEXT    Submitter identity  [default: anonymous]
  --notes TEXT    Free-text notes
```

**approve / revoke:**

```
Options:
  --source TEXT   Source field URI   [required]
  --target TEXT   Target field URI   [required]
```

**status:**

```
Options:
  --source TEXT   Filter by source URI
  --target TEXT   Filter by target URI
```

All subcommands print a JSON response to stdout.

**State-machine rules:**
- `approve` only valid from `pending`
- `revoke` valid from `pending` or `accredited`
- Re-submitting an existing `(source, target)` pair is an error

**Example:**

```bash
SRC="http://rosetta.interop/ns/NOR/nor_radar/altitude_m"
TGT="http://rosetta.interop/ns/master/altitude"

# --ledger is a GLOBAL option — it must come before the subcommand name
uv run rosetta-accredit --ledger my/ledger.json submit \
  --source "$SRC" --target "$TGT" \
  --actor alice --notes "Validated against NOR field manual"
uv run rosetta-accredit --ledger my/ledger.json approve \
  --source "$SRC" --target "$TGT"
uv run rosetta-accredit --ledger my/ledger.json status

# Later: withdraw or deny
uv run rosetta-accredit --ledger my/ledger.json revoke \
  --source "$SRC" --target "$TGT"

# Omit --ledger to use the default (store/ledger.json)
uv run rosetta-accredit submit --source "$SRC" --target "$TGT" --actor alice
```

**Exit codes:** 0 on success, 1 on state-machine violations.

---

## Configuration

`rosetta.toml` controls defaults for all tools. Precedence: **CLI flag** > **env var** > **config file**.

Environment variable naming: `ROSETTA_<SECTION>_<KEY>` (uppercase), e.g. `ROSETTA_SUGGEST_TOP_K=10`.

```toml
[general]
store_path     = "store"
default_format = "turtle"

[embed]
model = "intfloat/e5-large-v2"
mode  = "lexical-only"

[suggest]
top_k             = 5
min_score         = 0.0
anomaly_threshold = 0.3

[lint]
strict = false
```

---

## End-to-end scripts

Two runnable scripts use the fixture files in `rosetta/tests/fixtures/` and write output to a local directory.

| Script | Covers |
|--------|--------|
| `scripts/quickstart.sh` | Core pipeline: ingest → embed → suggest |
| `scripts/full-pipeline.sh` | All 8 tools: adds lint, rml-gen, provenance, validate, accredit |

```bash
bash scripts/quickstart.sh
bash scripts/full-pipeline.sh
```

---

## Running tests

```bash
uv run pytest                  # all tests
uv run pytest -m "not slow"    # skip model-download tests (~900 MB)
uv run pytest -k test_lint     # run a specific module
```
