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

| Extension / `--format`            | Format              | Notes                                                           |
| --------------------------------- | ------------------- | --------------------------------------------------------------- |
| `.csv` / `csv`                    | CSV                 | Auto-detected                                                   |
| `.tsv` / `tsv`                    | TSV                 | Auto-detected                                                   |
| `.json` / `json-schema`           | JSON Schema         | Auto-detected from `.json`                                      |
| `.yaml` / `.yml` / `openapi`      | OpenAPI 3.x         | Auto-detected                                                   |
| `.xsd` / `xsd`                    | XML Schema          | Auto-detected                                                   |
| `json-sample`                     | JSON sample data    | **Must pass `--format json-sample`** — no extension auto-detect |
| `.ttl` / `.owl` / `.rdf` / `rdfs` | RDFS/OWL vocabulary | Auto-detected from `.ttl`, `.owl`, `.rdf`                       |

**json-sample** accepts three input shapes:

- Top-level array: `[{"field": value, ...}, ...]`
- Flat object (treated as single-row sample): `{"field": value, ...}`
- Single-key envelope: `{"key": [{"field": value, ...}, ...]}`

Nested objects are preserved as nested classes in the LinkML output.

```
Usage: rosetta-ingest [OPTIONS]

Options:
  --input PATH         Input schema file.  [required]
  --format TEXT        Force input format: csv, tsv, json-schema, openapi, xsd, json-sample, rdfs
  --schema-name TEXT   Schema identifier (default: filename stem).
  --output PATH        Output path for .linkml.yaml file.  [required]
```

**Example:**

```bash
uv run rosetta-ingest --input rosetta/tests/fixtures/nor_radar.csv --output nor_radar.linkml.yaml
uv run rosetta-ingest --input rosetta/tests/fixtures/deu_patriot.json --output deu_patriot.linkml.yaml
uv run rosetta-ingest --input rosetta/tests/fixtures/usa_c2.yaml --output usa_c2.linkml.yaml
uv run rosetta-ingest --input rosetta/tests/fixtures/deu_radar_sample.json --format json-sample --output deu_radar_sample.linkml.yaml
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

| Option               | Default | Description                                                                                                                                    |
| -------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `--input PATH`       | —       | LinkML YAML input file **[required]**                                                                                                          |
| `--output PATH`      | —       | Output path for translated `.linkml.yaml` **[required]**                                                                                       |
| `--source-lang LANG` | `auto`  | Source language code (`DE`, `NB`, etc.) or `auto` for server-side detection. Any `EN`/`EN-US`/`en` variant triggers passthrough — no API call. |
| `--deepl-key TEXT`   | —       | DeepL API key (overrides `DEEPL_API_KEY` env var)                                                                                              |

**Requirements**

Set `DEEPL_API_KEY` to your DeepL API key. For English-source schemas, use `--source-lang EN` to bypass DeepL entirely.

**Pipeline example**

```bash
uv run rosetta-ingest --input rosetta/tests/fixtures/nor_radar.csv --output nor_radar.linkml.yaml
uv run rosetta-translate --input nor_radar.linkml.yaml --output nor_radar_en.linkml.yaml --source-lang auto
// Norwegian embeddings
uv run rosetta-embed --input nor_radar.linkml.yaml --output nor_radar_nb_embeddings.json
// English embeddings
uv run rosetta-embed --input nor_radar_en.linkml.yaml --output nor_radar_en_embeddings.json

uv run rosetta-ingest --input rosetta/tests/fixtures/master_cop_ontology.ttl --format rdfs --output master_cop.linkml.yaml
uv run rosetta-translate --input master_cop.linkml.yaml --output master_cop_en.linkml.yaml --source-lang EN # translate with --source-lang EN should be a no-op
uv run rosetta-embed --input master_cop_en.linkml.yaml --output master_cop_embeddings.json

# NB-to-EN cosine distance
uv run rosetta-suggest --output suggestions_nb.sssom.tsv nor_radar_nb_embeddings.json master_cop_embeddings.json
# EN-to-EN cosine distance
uv run rosetta-suggest --output suggestions_en.sssom.tsv nor_radar_en_embeddings.json master_cop_embeddings.json
```

For English schemas, `--source-lang EN` keeps the pipeline uniform and is a no-op:

```bash
rosetta-translate eng_schema.linkml.yaml -o eng_schema_en.linkml.yaml --source-lang EN
```

---

### rosetta-embed

Reads a `.linkml.yaml` file and computes embeddings for every schema slot. Outputs a JSON map of slot URI → embedding vector.

> **Output format note:** Each entry in the output JSON now includes a `"label"` field (derived from the schema class or slot name) in addition to the `"lexical"` vector. The `"label"` field is used by `rosetta-suggest` to populate the `subject_label` and `object_label` columns in SSSOM TSV output. Each entry also includes a `"structural"` array of 5 floats encoding schema-structural features (is_class, hierarchy_depth, is_required, is_multivalued, slot_usage_count — all normalized to [0.0, 1.0]). Old embed files without this field still load correctly and fall back to lexical-only scoring.

> **Note:** The first run downloads the model (~1.2 GB) from HuggingFace. Subsequent runs use the local cache.

```
Usage: rosetta-embed [OPTIONS]

Options:
  --input PATH            LinkML YAML input file  [required]
  --output PATH           JSON output file         (default: stdout)
  --include-definitions   Include slot definitions in the embedding text
  --include-parents       Include immediate parent class context
  --include-ancestors     Include full ancestor chain context (supersedes --include-parents)
  --include-children      Include direct child slot names in the embedding text
  --model TEXT            Sentence-transformer model  [default: intfloat/e5-large-v2]
```

> **E5 models** (`intfloat/multilingual-e5-*`) receive the `"passage: "` prefix automatically on indexed texts. No extra flags needed.

**Example:**

```bash
uv run rosetta-embed --input nor.linkml.yaml --output nor_emb.json
uv run rosetta-embed --input usa.linkml.yaml --output usa_emb.json

# Richer context — include full ancestor chain and slot definitions
uv run rosetta-embed --input nor.linkml.yaml --output nor_emb.json \
  --include-ancestors --include-definitions

# Cross-verify with multilingual E5 (stronger on non-English schemas)
uv run rosetta-embed --input nor.linkml.yaml --output nor_emb_e5.json \
  --model intfloat/multilingual-e5-base
```

**Exit codes:** 0 on success, 1 on error.

---

### rosetta-suggest

Compares source embeddings against master embeddings and ranks candidates by cosine similarity. Outputs SSSOM TSV format. When an audit log is configured (see `rosetta-accredit`), automatically boosts previously approved mappings and deranks rejected ones.

```
Usage: rosetta-suggest [OPTIONS] SOURCE MASTER

Arguments:
  SOURCE                     Source embeddings JSON (positional)
  MASTER                     Master embeddings JSON (positional)

Options:
  --top-k INT                Max suggestions per field  [default: 5]
  --min-score FLOAT          Minimum cosine score  [default: 0.0]
  --output PATH              Output file  (default: stdout)
  --config PATH              Path to rosetta.toml
```

**Example:**

```bash
uv run rosetta-suggest nor_emb.json usa_emb.json --output candidates.sssom.tsv
```

**Output format** — SSSOM TSV with 7 columns and a YAML comment header:

```
# mapping_set_id: https://rosetta-cli/mappings
# mapping_tool: rosetta-suggest
# license: https://creativecommons.org/licenses/by/4.0/
# curie_map:
#   skos: http://www.w3.org/2004/02/skos/core#
#   semapv: https://w3id.org/semapv/vocab/
subject_id	predicate_id	object_id	mapping_justification	confidence	subject_label	object_label	mapping_date	record_id
http://rosetta.interop/ns/NOR/nor_radar/altitude_m	skos:relatedMatch	http://rosetta.interop/ns/master/altitude	semapv:LexicalMatching	0.94	Altitude M	Altitude
```

Columns: `subject_id`, `predicate_id`, `object_id`, `mapping_justification`, `confidence`, `subject_label`, `object_label`, `mapping_date`, `record_id`.

`mapping_date` and `record_id` are populated only for rows carried over from the audit log; they are empty for freshly computed candidates.

**Structural blending:** When both embed files contain a `"structural"` array per node, `rosetta-suggest` automatically blends lexical and structural cosine similarity. The blend weight is controlled by `structural_weight` in `rosetta.toml` under `[suggest]` (default: `0.2`). Set it to `0.0` to disable blending. If either embed file lacks `"structural"` arrays (e.g., older files), scoring falls back to lexical-only automatically. When blending is active, `mapping_justification` is `semapv:CompositeMatching`; otherwise it is `semapv:LexicalMatching`.

**Audit log integration:** When `[accredit].log` is set in `rosetta.toml` and the log file exists, `rosetta-suggest` automatically:

- **Boosts** candidates whose (subject, object) pair has an approved `HumanCuration` row in the log
- **Deranks** candidates whose pair has a rejected `HumanCuration` row (`predicate_id = owl:differentFrom`)
- **Preserves log row justification and predicate** for already-tracked pairs: if a source–target pair already appears in the audit log with a `ManualMappingCuration` or `HumanCuration` row, that row is included in `candidates.sssom.tsv` with its existing justification and predicate, but with a freshly computed confidence score. All other pairs appear as new `CompositeMatching` (or `LexicalMatching`) candidates.

This means `candidates.sssom.tsv` provides a complete picture: newly computed candidates alongside the current state of all previously decided pairs.

**Exit codes:** 0 on success, 1 on error.

---

### rosetta-lint

Validates analyst-proposed SSSOM TSV files before they are staged for accreditor review. Reads the audit log (from `rosetta.toml [accredit].log`) to check for conflicts with existing decisions.

```
Usage: rosetta-lint [OPTIONS]

Options:
  --sssom PATH    SSSOM TSV file to validate  [required]
  --output PATH   Output file (default: stdout)
  --strict        Treat WARNINGs as BLOCKs (useful as a CI gate)
  --config PATH   Path to rosetta.toml
```

**Lint rules:**

| Rule | Severity | Description |
| ---- | -------- | ----------- |
| `unit_dimension_mismatch` | BLOCK | Subject and object fields have incompatible physical dimensions |
| `unit_conversion_required` | WARNING | Fields share the same dimension but use different units (FnML conversion suggested) |
| `unit_not_detected` | INFO | No recognizable unit in field name, or unit has no QUDT IRI mapping |
| `unit_vector_missing` | INFO | QUDT dimension vector missing for a recognized unit |
| `datatype_mismatch` | WARNING | Subject/object differ in numeric vs string datatype |
| `max_one_mmc_per_pair` | BLOCK | More than one ManualMappingCuration row for the same pair |
| `reproposal_of_approved` | BLOCK | Pair already has an approved HumanCuration decision in the audit log |
| `reproposal_of_rejected` | BLOCK | Pair already has a rejected HumanCuration decision in the audit log |
| `invalid_predicate` | BLOCK | Predicate is not one of the allowed SKOS/OWL predicates |

When `--strict` is passed, all WARNINGs are upgraded to BLOCKs.

**Output format:** JSON `LintReport` with a `findings` list (each entry has `rule`, `severity`, `source_uri`, `target_uri`, `message`, `fnml_suggestion`) and a `summary` with block/warning/info counts.

**Example:**

```bash
rosetta-lint --sssom proposals.sssom.tsv [--output report.json] [--strict] [--config rosetta.toml]

# Validate analyst proposals
uv run rosetta-lint --sssom candidates.sssom.tsv

# Strict mode — WARNINGs become BLOCKs (useful as a CI gate)
uv run rosetta-lint --strict --sssom candidates.sssom.tsv --output lint.json

# Then stage for accreditor review if clean
uv run rosetta-accredit ingest candidates.sssom.tsv
```

**Exit codes:** 0 if no BLOCKs, 1 if at least one BLOCK found.

---

### rosetta-accredit

Manages the mapping accreditation pipeline using an append-only audit log (`audit-log.sssom.tsv`). The log is the single source of truth for accreditation decisions and feeds directly into `rosetta-suggest` (boost/derank) and `rosetta-lint` (conflict checking).

#### User flow

The pipeline involves two roles — **Analyst** and **Accreditor** — coordinated through file editing and CLI commands.

```
rosetta-suggest → candidates.sssom.tsv
                        │
              Analyst edits file:
              change ManualMappingCuration rows,
              set predicate_id
                        │
              rosetta-lint --sssom candidates.sssom.tsv
              (fix errors if exit 1, re-run lint)
                        │
              rosetta-accredit ingest candidates.sssom.tsv
              (ManualMappingCuration rows → audit log)
                        │
              rosetta-accredit review -o review.sssom.tsv
                        │
              Accreditor edits review.sssom.tsv:
              change HumanCuration + update predicate_id
              (owl:differentFrom = reject)
                        │
              rosetta-accredit ingest review.sssom.tsv
              (HumanCuration rows → audit log)
                        │
              Next rosetta-suggest run reads updated log
```

**Step-by-step:**

1. **Generate candidates** — `rosetta-suggest` produces `candidates.sssom.tsv`. For pairs already in the audit log, the existing row (justification + predicate) is preserved with a freshly computed confidence score.

2. **Analyst proposes** — The analyst edits `candidates.sssom.tsv`: for each mapping they want to propose, change `mapping_justification` to `semapv:ManualMappingCuration` and set `predicate_id` to the appropriate SKOS predicate.

3. **Lint validates** — `rosetta-lint --sssom candidates.sssom.tsv` checks for structural errors (duplicate proposals, conflicts with existing decisions, invalid predicates). Errors are printed to stderr; analyst fixes and re-runs.

4. **Stage proposals** — `rosetta-accredit ingest candidates.sssom.tsv` reads `ManualMappingCuration` rows, validates them against the state machine, and appends them to the audit log with a `mapping_date` timestamp and `record_id`.

5. **Accreditor reviews** — `rosetta-accredit review -o review.sssom.tsv` generates a work list of all pending proposals (ManualMappingCuration rows with no decision yet). The accreditor edits `review.sssom.tsv`:
    - **Approve**: change `mapping_justification` → `semapv:HumanCuration` (keep or refine `predicate_id`)
    - **Reject**: change `mapping_justification` → `semapv:HumanCuration`, set `predicate_id` → `owl:differentFrom`

6. **Ingest decisions** — `rosetta-accredit ingest review.sssom.tsv` validates each `HumanCuration` row has a `ManualMappingCuration` predecessor, then appends to the audit log.

7. **Correct a decision** — To override a prior decision, the accreditor manually creates a file with a new `HumanCuration` row and runs `rosetta-accredit ingest` again. The latest entry wins.

#### Business rules

| Rule                                                                                            | Enforced by                                        |
| ----------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Max 1 `ManualMappingCuration` per (subject_id, object_id)                                       | `rosetta-lint --sssom`                             |
| Cannot re-propose a pair with **any** `HumanCuration` in log (approved or rejected)             | `rosetta-accredit ingest` + `rosetta-lint --sssom` |
| `HumanCuration` can only be ingested if a `ManualMappingCuration` predecessor exists            | `rosetta-accredit ingest`                          |
| Once rejected, only the Accreditor can un-reject (by ingesting a corrected `HumanCuration` row) | Workflow convention                                |
| Approved mappings boost future `rosetta-suggest` results                                        | `rosetta-suggest` (log integration)                |
| Rejected mappings (`owl:differentFrom`) derank future `rosetta-suggest` results                 | `rosetta-suggest` (log integration)                |

#### Predicate guide

| Situation                                         | `predicate_id`                               |
| ------------------------------------------------- | -------------------------------------------- |
| Same concept, same units                          | `skos:exactMatch`                            |
| Same concept, different units (conversion needed) | `skos:exactMatch` — lint flags unit mismatch |
| Close but not exact semantic match                | `skos:closeMatch`                            |
| Source is narrower than target                    | `skos:narrowMatch`                           |
| Source is broader than target                     | `skos:broadMatch`                            |
| Related, neither narrows nor broadens             | `skos:relatedMatch`                          |
| Reject — different concept                        | `owl:differentFrom`                          |

#### Commands

```
Usage: rosetta-accredit [OPTIONS] COMMAND

Global options:
  --log PATH       Path to audit log .sssom.tsv  [default: store/audit-log.sssom.tsv]
  -c, --config PATH

Commands:
  ingest   Append ManualMappingCuration or HumanCuration rows to the audit log
  review   Output pending proposals (ManualMappingCuration with no decision yet)
  status   Show current accreditation state per pair
  dump     Export current HumanCuration rows for pipeline use
```

**ingest:**

```
Usage: rosetta-accredit ingest FILE

Arguments:
  FILE    SSSOM TSV file containing ManualMappingCuration or HumanCuration rows
```

Validates each row against the state machine before writing. If any row violates a rule, all errors are printed to stderr and nothing is written (no partial writes).

**review:**

```
Usage: rosetta-accredit review [OPTIONS]

Options:
  -o, --output PATH    Output file (default: stdout)
```

**status:**

```
Usage: rosetta-accredit status [OPTIONS]

Options:
  --source TEXT    Filter by subject_id (substring match)
  --target TEXT    Filter by object_id (substring match)
```

Prints a JSON array with current state per pair to stdout.

**dump:**

```
Usage: rosetta-accredit dump [OPTIONS]

Options:
  -o, --output PATH    Output file (default: stdout)
```

Outputs the latest `HumanCuration` row per pair as SSSOM TSV. Suitable for external pipeline consumption.

#### Audit log format

`audit-log.sssom.tsv` is an append-only SSSOM TSV file. Two additional columns are stamped at ingest time:

| Column         | Description                                         |
| -------------- | --------------------------------------------------- |
| `mapping_date` | ISO 8601 UTC timestamp — when this row was ingested |
| `record_id`    | UUID4 — unique identifier for this log entry        |

A complete history for an approved mapping:

```
subject_id   predicate_id      object_id    mapping_justification         confidence  mapping_date          record_id
nor:speed    skos:relatedMatch  mst:speed   semapv:ManualMappingCuration  0.87        2026-04-15T09:00:00Z  <uuid>
nor:speed    skos:exactMatch    mst:speed   semapv:HumanCuration          0.87        2026-04-16T14:00:00Z  <uuid>
```

A rejected mapping (feeds derank into next suggest run):

```
nor:bearing  skos:relatedMatch  mst:heading  semapv:ManualMappingCuration  0.72   2026-04-15T09:00:00Z  <uuid>
nor:bearing  owl:differentFrom  mst:heading  semapv:HumanCuration          0.72   2026-04-16T14:00:00Z  <uuid>
```

#### Example session

```bash
# 1. Generate candidates (log is read automatically from rosetta.toml)
uv run rosetta-suggest nor_emb.json master_emb.json -o candidates.sssom.tsv

# 2. Analyst edits candidates.sssom.tsv, marking ManualMappingCuration rows

# 3. Lint check
uv run rosetta-lint --sssom candidates.sssom.tsv

# 4. Stage analyst proposals
uv run rosetta-accredit ingest candidates.sssom.tsv

# 5. Generate accreditor work list
uv run rosetta-accredit review -o review.sssom.tsv

# 6. Accreditor edits review.sssom.tsv, marking HumanCuration rows

# 7. Ingest decisions
uv run rosetta-accredit ingest review.sssom.tsv

# 8. Check current state
uv run rosetta-accredit status

# 9. Correct a previous decision
# (edit update.sssom.tsv with corrected HumanCuration row)
uv run rosetta-accredit ingest update.sssom.tsv
```

**Exit codes:** 0 on success, 1 on state-machine violation or I/O error.

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
structural_weight = 0.2

[lint]
strict = false

[accredit]
log = "store/audit-log.sssom.tsv"
```

---

## End-to-end scripts

| Script                     | Covers                                                                                                                                           |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `scripts/pipeline-demo.sh` | Full accreditation walkthrough: ingest → translate → embed → suggest → lint → accredit, with interactive pauses for analyst and accreditor edits |

```bash
bash scripts/pipeline-demo.sh          # writes output to demo_out/
bash scripts/pipeline-demo.sh my_run   # custom output directory
```

The script uses the bundled fixture files in `rosetta/tests/fixtures/` and pauses at each human-in-the-loop step so you can edit the generated SSSOM files before proceeding.

---

## Running tests

```bash
uv run pytest                  # all tests
uv run pytest -m "not slow"    # skip model-download tests (~900 MB)
uv run pytest -k test_lint     # run a specific module
```
