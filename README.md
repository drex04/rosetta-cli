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

Parses a national schema file and emits an RDF graph (Turtle by default). Input format is auto-detected from the file extension.

| Extension | Format |
|-----------|--------|
| `.csv` | CSV with statistical annotations |
| `.json` | JSON Schema |
| `.yaml` / `.yml` | OpenAPI 3.x |

```
Usage: rosetta-ingest [OPTIONS]

Options:
  -i, --input PATH         Input file (default: stdin)
  -o, --output PATH        Output file (default: stdout)
  -f, --format TEXT        Output RDF serialization: turtle, nt  [default: turtle]
  --input-format TEXT      Force input format: csv, json-schema, openapi
  -n, --nation TEXT        Nation code (e.g. NOR, DEU, USA)  [required]
  --max-sample-rows INT    Max CSV rows for statistics  [default: 1000]
  -c, --config PATH        Path to rosetta.toml
```

**Example:**

```bash
uv run rosetta-ingest -i rosetta/tests/fixtures/nor_radar.csv    -n NOR -o nor.ttl
uv run rosetta-ingest -i rosetta/tests/fixtures/deu_patriot.json -n DEU -o deu.ttl
uv run rosetta-ingest -i rosetta/tests/fixtures/usa_c2.yaml      -n USA -o usa.ttl
```

**Exit codes:** 0 on success, 1 on parse or I/O error.

---

### rosetta-embed

Reads a Turtle file and computes LaBSE embeddings for every schema attribute. Outputs a JSON map of attribute URI → embedding vector.

> **Note:** The first run downloads the LaBSE model (~900 MB) from HuggingFace. Subsequent runs use the local cache.

```
Usage: rosetta-embed [OPTIONS]

Options:
  -i, --input PATH    Turtle input file  (default: stdin)
  -o, --output PATH   JSON output file   (default: stdout)
  --mode TEXT         Embedding mode  [default: lexical-only]
  --model TEXT        Sentence-transformer model  [default: sentence-transformers/LaBSE]
  -c, --config PATH   Path to rosetta.toml
```

> **Caveat:** Only `lexical-only` mode is active. Other values for `--mode` are accepted but have no effect.

> **E5 models** (`intfloat/multilingual-e5-*`) receive the `"passage: "` prefix automatically on indexed texts. No extra flags needed.

**Example:**

```bash
uv run rosetta-embed -i nor.ttl -o nor_emb.json
uv run rosetta-embed -i usa.ttl -o usa_emb.json

# Cross-verify with multilingual E5 (stronger on non-English schemas)
uv run rosetta-embed -i nor.ttl -o nor_emb_e5.json \
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
  --source-format TEXT  Reference formulation: json, csv  [default: json]
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
    "conversion_fn": "http://rosetta.interop/fn/knot-to-metre-per-second"
  }
}
```

`conversion_fn` is optional. Include it when `rosetta-lint` reports `unit_conversion_required` and provides an FnML suggestion — the generated Turtle will wrap that field in an `fnml:functionValue` block.

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

uv run rosetta-accredit submit --source "$SRC" --target "$TGT" \
  --actor alice --notes "Validated against NOR field manual"
uv run rosetta-accredit approve --source "$SRC" --target "$TGT"
uv run rosetta-accredit status

# Later: withdraw or deny
uv run rosetta-accredit revoke --source "$SRC" --target "$TGT"
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
model = "sentence-transformers/LaBSE"
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
