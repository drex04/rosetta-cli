# rosetta-cli

**Map partner-nation schemas to a shared ontology — systematically, transparently, and with auditable human review.**

> Full documentation: **[drex04.github.io/rosetta-cli](https://drex04.github.io/rosetta-cli/)** — the CLI reference there is auto-rendered from the source on every push.

Defense coalitions speak in many tongues. Norwegian radar tracks, German Patriot telemetry, US C2 feeds — each schema has its own language, units, field names, and structure. Making them interoperate is the difference between a commander seeing one coherent picture and juggling seven.

`rosetta-cli` is a composable Unix toolkit that takes heterogeneous partner schemas and produces a materialised, standards-compliant RDF knowledge graph aligned to a master ontology. Every step is a discrete tool you can script, pipe, inspect, and audit.

## What it does

- **Ingests** schemas in seven formats (CSV, TSV, JSON Schema, OpenAPI, XSD, RDFS/OWL, JSON samples) and normalises them to [LinkML](https://linkml.io/).
- **Translates** non-English titles via DeepL so multilingual schemas embed in a common semantic space — originals preserved as aliases.
- **Embeds** every class and slot with multilingual sentence transformers, blending **lexical** and **structural** similarity.
- **Suggests** candidate mappings ranked by cosine similarity, automatically boosted by prior approvals and deranked by prior rejections.
- **Lints** analyst proposals against physical-unit dimensionality, datatype compatibility, and audit-log conflicts — *before* a human reviewer ever sees them.
- **Records** every decision in an append-only [SSSOM](https://mapping-commons.github.io/sssom/) audit log that feeds straight back into the next `suggest` run.
- **Generates** a [YARRRML](https://rml.io/yarrrml/) mapping from the approved log, compiles it, and materialises it against concrete source data via [morph-kgc](https://morph-kgc.readthedocs.io/) — producing JSON-LD framed against your master ontology's `@context`.
- **Validates** the resulting RDF against [SHACL](https://www.w3.org/TR/shacl/) shapes — exit `0` conformant, `1` violations — so the pipeline composes cleanly into CI gates.

## Why this way

**Standards, not reinvention.** LinkML, SSSOM, SKOS, OWL, SEMAPV, PROV-O, SHACL, RML/YARRRML, JSON-LD — every intermediate artifact is a W3C or OBO-community standard readable by tools other than `rosetta-cli`.

**Unix philosophy, strictly.** Each of the nine commands does one thing, reads from files or stdin, writes to files or stdout, and returns meaningful exit codes. No orchestrator, no daemon — just binaries you pipe together.

**Human-in-the-loop.** Similarity is a candidate generator, not a decider. A two-role state machine (Analyst proposes, Accreditor approves) is enforced through an append-only audit log. Every mapping in production traces back to a reviewer, a timestamp, and a justification.

**Multilingual by construction.** Coalition schemas are not monolingual. Norwegian `breddegrad` should match English `latitude` on first pass — without hand-maintained alias tables.

**Auditable, always.** The audit log is a 13-column SSSOM TSV you can `git diff`. No decisions live in someone's email.

## Who it's for

- Coalition data architects aligning partner-nation schemas to a shared operational picture.
- Ontology engineers who need a repeatable, reviewable mapping pipeline — not a one-off notebook.
- Defense integrators producing accreditable RDF for downstream C2, sensor-fusion, or intelligence systems.
- Anyone who has tried to reconcile a dozen CSVs to one schema by hand and sworn *never again*.

---

## Installation

```bash
uv sync
```

All tools are available via `uv run rosetta <command>` after syncing.

---

## Tools

### rosetta ingest

Parses a schema file and emits a LinkML schema YAML (`.linkml.yaml`). Input format is auto-detected from the file extension. The schema name is derived from the input filename stem.

#### Supported formats

| Extension / `-f`/`--schema-format` | Format              | Notes                                                                    |
| ---------------------------------- | ------------------- | ------------------------------------------------------------------------ |
| `.csv` / `csv`                     | CSV                 | Auto-detected                                                            |
| `.tsv` / `tsv`                     | TSV                 | Auto-detected                                                            |
| `.json` / `json-schema`            | JSON Schema         | Auto-detected from `.json`                                               |
| `.yaml` / `.yml` / `openapi`       | OpenAPI 3.x         | Auto-detected                                                            |
| `.xsd` / `xsd`                     | XML Schema          | Auto-detected                                                            |
| `json-sample`                      | JSON sample data    | **Must pass `-f json-sample`** — no extension auto-detect                |
| `.ttl` / `.owl` / `.rdf` / `rdfs`  | RDFS/OWL vocabulary | Auto-detected from `.ttl`, `.owl`, `.rdf`                                |

**json-sample** accepts three input shapes:

- Top-level array: `[{"field": value, ...}, ...]`
- Flat object (treated as single-row sample): `{"field": value, ...}`
- Single-key envelope: `{"key": [{"field": value, ...}, ...]}`

Nested objects are preserved as nested classes in the LinkML output.

```
Usage: rosetta ingest [OPTIONS] SCHEMA_FILE

Arguments:
  SCHEMA_FILE               Input schema file.

Options:
  -f, --schema-format TEXT  Force input format: csv, tsv, json-schema, openapi, xsd, json-sample, rdfs
  -o, --output PATH         Output path for .linkml.yaml file (default: stdout)
  -c, --config PATH         Path to rosetta.toml
```

**Example:**

```bash
uv run rosetta ingest rosetta/tests/fixtures/nations/nor_radar.csv -o nor_radar.linkml.yaml
uv run rosetta ingest rosetta/tests/fixtures/nations/deu_patriot.json -o deu_patriot.linkml.yaml
uv run rosetta ingest rosetta/tests/fixtures/nations/usa_c2.yaml -o usa_c2.linkml.yaml
uv run rosetta ingest rosetta/tests/fixtures/nations/deu_radar_sample.json -f json-sample -o deu_radar_sample.linkml.yaml
```

**Prefix collision detection:** If a `.linkml.yaml` file already exists in the same output directory with the same `default_prefix` or `id` (namespace IRI), `rosetta ingest` exits 1 with an error message naming the conflicting file. This prevents downstream tools (e.g., `rosetta compile`) from producing ambiguous mappings when filtering by source schema prefix. Each input file's stem uniquely determines the schema name.

**Source-format and path annotations:** Every generated `.linkml.yaml` is stamped with:

- `annotations.rosetta_source_format` — the detected or forced input format (e.g., `csv`, `json-schema`, `xsd`).
- Per-slot path annotations — `rosetta_csv_column` (CSV/TSV), `rosetta_jsonpath` (JSON Schema / JSON sample), or `rosetta_xpath` (XSD) — recording the original field path in the source schema.

These annotations are consumed by `rosetta compile` to generate source-format-aware YARRRML mapping templates automatically.

**Exit codes:** 0 on success, 1 on parse, I/O, or prefix-collision error.

---

### rosetta translate

Normalises non-English class titles, slot titles, and descriptions to English via DeepL before embedding. Accepts a `.linkml.yaml` file and outputs a `.linkml.yaml` file with translated titles and descriptions; original values are preserved in `aliases`.

**Synopsis**

```bash
rosetta translate [OPTIONS] INPUT_FILE
```

**Options**

| Option               | Default | Description                                                                                                                                    |
| -------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `INPUT_FILE`         | —       | LinkML YAML input file **[required]**                                                                                                          |
| `-o, --output PATH`  | stdout  | Output path for translated `.linkml.yaml`                                                                                                      |
| `--source-lang LANG` | `auto`  | Source language code (`DE`, `NB`, etc.) or `auto` for server-side detection. Any `EN`/`EN-US`/`en` variant triggers passthrough — no API call. |
| `--deepl-key TEXT`   | —       | DeepL API key (overrides `DEEPL_API_KEY` env var)                                                                                              |
| `-c, --config PATH`  | —       | Path to rosetta.toml                                                                                                                           |

**Requirements**

Set `DEEPL_API_KEY` to your DeepL API key. For English-source schemas, use `--source-lang EN` to bypass DeepL entirely.

**Pipeline example**

```bash
uv run rosetta ingest rosetta/tests/fixtures/nations/nor_radar.csv -o nor_radar.linkml.yaml
uv run rosetta translate nor_radar.linkml.yaml -o nor_radar_en.linkml.yaml --source-lang auto
# Norwegian embeddings
uv run rosetta embed nor_radar.linkml.yaml -o nor_radar_nb_embeddings.json
# English embeddings
uv run rosetta embed nor_radar_en.linkml.yaml -o nor_radar_en_embeddings.json

uv run rosetta ingest rosetta/tests/fixtures/nations/master_cop_ontology.ttl -f rdfs -o master_cop.linkml.yaml
uv run rosetta translate master_cop.linkml.yaml -o master_cop_en.linkml.yaml --source-lang EN  # no-op for English
uv run rosetta embed master_cop_en.linkml.yaml -o master_cop_embeddings.json

# NB-to-EN cosine distance
uv run rosetta suggest nor_radar_nb_embeddings.json master_cop_embeddings.json -o suggestions_nb.sssom.tsv
# EN-to-EN cosine distance
uv run rosetta suggest nor_radar_en_embeddings.json master_cop_embeddings.json -o suggestions_en.sssom.tsv
```

For English schemas, `--source-lang EN` keeps the pipeline uniform and is a no-op:

```bash
uv run rosetta translate eng_schema.linkml.yaml -o eng_schema_en.linkml.yaml --source-lang EN
```

---

### rosetta embed

Reads a `.linkml.yaml` file and computes embeddings for every schema slot. Outputs a JSON map of slot URI → embedding vector.

> **Output format note:** Each entry in the output JSON now includes a `"label"` field (derived from the schema class or slot name) in addition to the `"lexical"` vector. The `"label"` field is used by `rosetta suggest` to populate the `subject_label` and `object_label` columns in SSSOM TSV output. Each entry also includes a `"structural"` array of 5 floats encoding schema-structural features (is_class, hierarchy_depth, is_required, is_multivalued, slot_usage_count — all normalized to [0.0, 1.0]). Old embed files without this field still load correctly and fall back to lexical-only scoring.

> **Note:** The first run downloads the model (~1.2 GB) from HuggingFace. Subsequent runs use the local cache.

```
Usage: rosetta embed [OPTIONS] INPUT_FILE

Arguments:
  INPUT_FILE              LinkML YAML input file

Options:
  -o, --output PATH       JSON output file  (default: stdout)
  --include-definitions   Include slot definitions in the embedding text
  --include-parents       Include immediate parent class context
  --include-ancestors     Include full ancestor chain context (supersedes --include-parents)
  --include-children      Include direct child slot names in the embedding text
  --model TEXT            Sentence-transformer model  [default: intfloat/e5-large-v2]
  -c, --config PATH       Path to rosetta.toml
```

> **E5 models** (`intfloat/multilingual-e5-*`) receive the `"passage: "` prefix automatically on indexed texts. No extra flags needed.

**Example:**

```bash
uv run rosetta embed nor.linkml.yaml -o nor_emb.json
uv run rosetta embed usa.linkml.yaml -o usa_emb.json

# Richer context — include full ancestor chain and slot definitions
uv run rosetta embed nor.linkml.yaml -o nor_emb.json \
  --include-ancestors --include-definitions

# Cross-verify with multilingual E5 (stronger on non-English schemas)
uv run rosetta embed nor.linkml.yaml -o nor_emb_e5.json \
  --model intfloat/multilingual-e5-base
```

**Exit codes:** 0 on success, 1 on error.

---

### rosetta suggest

Compares source embeddings against master embeddings and ranks candidates by cosine similarity. Outputs SSSOM TSV format. When an audit log is configured (see `rosetta accredit`), automatically boosts previously approved mappings and deranks rejected ones.

```
Usage: rosetta suggest [OPTIONS] SOURCE MASTER

Arguments:
  SOURCE                     Source embeddings JSON (positional)
  MASTER                     Master embeddings JSON (positional)

Options:
  --top-k INT                Max suggestions per field  [default: 5]
  --min-score FLOAT          Minimum cosine score  [default: 0.0]
  -o, --output PATH          Output file  (default: stdout)
  --audit-log PATH           Path to audit log .sssom.tsv (overrides rosetta.toml)
  -c, --config PATH          Path to rosetta.toml
```

**Example:**

```bash
uv run rosetta suggest nor_emb.json usa_emb.json -o candidates.sssom.tsv
```

**Output format** — SSSOM TSV with 15 columns and a YAML comment header:

```
# mapping_set_id: https://rosetta-cli/mappings
# mapping_tool: rosetta suggest
# license: https://creativecommons.org/licenses/by/4.0/
# curie_map:
#   skos: http://www.w3.org/2004/02/skos/core#
#   semapv: https://w3id.org/semapv/vocab/
subject_id	predicate_id	object_id	mapping_justification	confidence	subject_label	object_label	mapping_date	record_id	subject_datatype	object_datatype	subject_type	object_type	mapping_group_id	composition_expr
http://rosetta.interop/ns/NOR/nor_radar/altitude_m	skos:relatedMatch	http://rosetta.interop/ns/master/altitude	semapv:LexicalMatching	0.94	Altitude M	Altitude	2026-04-16T00:00:00Z	<uuid>	xsd:float	xsd:float
```

| Column | Description |
| ------ | ----------- |
| `subject_id` | Source field URI |
| `predicate_id` | SKOS/OWL mapping predicate |
| `object_id` | Master ontology field URI |
| `mapping_justification` | SEMAPV justification CURIE |
| `confidence` | Cosine similarity score (0.0–1.0) |
| `subject_label` | Human-readable source field name |
| `object_label` | Human-readable target field name |
| `mapping_date` | ISO 8601 UTC timestamp (populated for audit-log rows; empty for fresh candidates) |
| `record_id` | UUID4 (populated for audit-log rows; empty for fresh candidates) |
| `subject_datatype` | XSD datatype of the source field, re-derived from the source LinkML schema |
| `object_datatype` | XSD datatype of the target field, re-derived from the master LinkML schema |
| `subject_type` | SSSOM entity type; `"composed entity expression"` for composite mappings, else empty |
| `object_type` | SSSOM entity type; `"composed entity expression"` for composite mappings, else empty |
| `mapping_group_id` | Optional identifier shared across rows that compose one logical mapping |
| `composition_expr` | Python/GREL expression that composes fields for 1:N decomposition or N:1 aggregation; consumed by `rosetta compile` |

`mapping_date` and `record_id` are populated only for rows carried over from the audit log; they are empty for freshly computed candidates. `subject_datatype` and `object_datatype` are re-derived at suggest time from the source and master LinkML schemas; they are not stored in the audit log (see [Audit log format](#audit-log-format)).

**Structural blending:** When both embed files contain a `"structural"` array per node, `rosetta suggest` automatically blends lexical and structural cosine similarity. The blend weight is controlled by `structural_weight` in `rosetta.toml` under `[suggest]` (default: `0.2`). Set it to `0.0` to disable blending. If either embed file lacks `"structural"` arrays (e.g., older files), scoring falls back to lexical-only automatically. When blending is active, `mapping_justification` is `semapv:CompositeMatching`; otherwise it is `semapv:LexicalMatching`.

**Audit log integration:** When `[accredit].log` is set in `rosetta.toml` (or `--audit-log` is passed) and the log file exists, `rosetta suggest` automatically:

- **Boosts** candidates whose (subject, object) pair has an approved `HumanCuration` row in the log
- **Deranks** candidates whose pair has a rejected `HumanCuration` row (`predicate_id = owl:differentFrom`)
- **Preserves log row justification and predicate** for already-tracked pairs: if a source–target pair already appears in the audit log with a `ManualMappingCuration` or `HumanCuration` row, that row is included in `candidates.sssom.tsv` with its existing justification and predicate, but with a freshly computed confidence score. All other pairs appear as new `CompositeMatching` (or `LexicalMatching`) candidates.

This means `candidates.sssom.tsv` provides a complete picture: newly computed candidates alongside the current state of all previously decided pairs.

**Exit codes:** 0 on success, 1 on error.

---

### rosetta lint

Validates analyst-proposed SSSOM TSV files before they are staged for accreditor review. Reads the audit log (from `rosetta.toml [accredit].log` or `--audit-log`) to check for conflicts with existing decisions.

```
Usage: rosetta lint [OPTIONS] SSSOM_FILE

Arguments:
  SSSOM_FILE            SSSOM TSV file to validate

Options:
  -o, --output PATH     Output file (default: stdout)
  --strict              Treat WARNINGs as BLOCKs (useful as a CI gate)
  --audit-log PATH      Path to audit log .sssom.tsv (overrides rosetta.toml)
  --source-schema PATH  Source LinkML schema YAML (enables structural checks) [required]
  --master-schema PATH  Master LinkML schema YAML (enables structural checks) [required]
  -c, --config PATH     Path to rosetta.toml
```

**Lint rules:**

| Rule | Severity | Description |
| ---- | -------- | ----------- |
| `slot_class_unreachable` | BLOCK | Slot's owning class unreachable from any class-level mapping target (requires `--source-schema` + `--master-schema`) |
| `unit_dimension_mismatch` | BLOCK | Subject and object fields have incompatible physical dimensions |
| `unit_conversion_required` | WARNING | Fields share the same dimension but use different units (FnML conversion suggested) |
| `unit_not_detected` | INFO | No recognizable unit in field name, or unit has no QUDT IRI mapping |
| `unit_vector_missing` | INFO | QUDT dimension vector missing for a recognized unit |
| `datatype_mismatch` | WARNING | Subject/object differ in numeric vs string datatype |
| `max_one_mmc_per_pair` | BLOCK | More than one ManualMappingCuration row for the same (subject, object) pair |
| `max_one_mmc_per_subject` | BLOCK | Same subject has multiple confirmed mappings to different objects |
| `reproposal_of_approved` | BLOCK | Pair already has an approved HumanCuration decision in the audit log |
| `reproposal_of_rejected` | BLOCK | Pair already has a rejected HumanCuration decision in the audit log |
| `invalid_predicate` | BLOCK | Predicate is not one of the allowed SKOS/OWL predicates |

When `--strict` is passed, all WARNINGs are upgraded to BLOCKs.

**Output format:** JSON `LintReport` with a `findings` list (each entry has `rule`, `severity`, `source_uri`, `target_uri`, `message`, `fnml_suggestion`) and a `summary` with block/warning/info counts.

**Example:**

```bash
# Validate analyst proposals (source-schema and master-schema are required)
uv run rosetta lint candidates.sssom.tsv \
  --source-schema nor_radar_en.linkml.yaml \
  --master-schema master_cop_en.linkml.yaml

# Strict mode — WARNINGs become BLOCKs (useful as a CI gate)
uv run rosetta lint --strict candidates.sssom.tsv \
  --source-schema nor_radar_en.linkml.yaml \
  --master-schema master_cop_en.linkml.yaml \
  -o lint.json

# Then stage for accreditor review if clean
uv run rosetta accredit append candidates.sssom.tsv
```

**Exit codes:** 0 if no BLOCKs, 1 if at least one BLOCK found.

---

### rosetta accredit

Manages the mapping accreditation pipeline using an append-only audit log (`audit-log.sssom.tsv`). The log is the single source of truth for accreditation decisions and feeds directly into `rosetta suggest` (boost/derank) and `rosetta lint` (conflict checking).

#### User flow

The pipeline involves two roles — **Analyst** and **Accreditor** — coordinated through file editing and CLI commands.

```
rosetta suggest → candidates.sssom.tsv
                        │
              Analyst edits file:
              change ManualMappingCuration rows,
              set predicate_id
                        │
              rosetta lint candidates.sssom.tsv
              (fix errors if exit 1, re-run lint)
                        │
              rosetta accredit append candidates.sssom.tsv
              (ManualMappingCuration rows → audit log)
                        │
              rosetta accredit review -o review.sssom.tsv
                        │
              Accreditor edits review.sssom.tsv:
              change HumanCuration + update predicate_id
              (owl:differentFrom = reject)
                        │
              rosetta accredit append review.sssom.tsv
              (HumanCuration rows → audit log)
                        │
              Next rosetta suggest run reads updated log
```

**Step-by-step:**

1. **Generate candidates** — `rosetta suggest` produces `candidates.sssom.tsv`. For pairs already in the audit log, the existing row (justification + predicate) is preserved with a freshly computed confidence score.

2. **Analyst proposes** — The analyst edits `candidates.sssom.tsv`: for each mapping they want to propose, change `mapping_justification` to `semapv:ManualMappingCuration` and set `predicate_id` to the appropriate SKOS predicate.

3. **Lint validates** — `rosetta lint candidates.sssom.tsv` checks for structural errors (duplicate proposals, conflicts with existing decisions, invalid predicates). Errors are printed to stderr; analyst fixes and re-runs.

4. **Stage proposals** — `rosetta accredit append candidates.sssom.tsv` reads `ManualMappingCuration` rows, validates them against the state machine, and appends them to the audit log with a `mapping_date` timestamp and `record_id`.

5. **Accreditor reviews** — `rosetta accredit review -o review.sssom.tsv` generates a work list of all pending proposals (ManualMappingCuration rows with no decision yet). The accreditor edits `review.sssom.tsv`:
    - **Approve**: change `mapping_justification` → `semapv:HumanCuration` (keep or refine `predicate_id`)
    - **Reject**: change `mapping_justification` → `semapv:HumanCuration`, set `predicate_id` → `owl:differentFrom`

6. **Ingest decisions** — `rosetta accredit append review.sssom.tsv` validates each `HumanCuration` row has a `ManualMappingCuration` predecessor, then appends to the audit log.

7. **Correct a decision** — To override a prior decision, the accreditor manually creates a file with a new `HumanCuration` row and runs `rosetta accredit append` again. The latest entry wins.

#### Business rules

| Rule                                                                                            | Enforced by                                        |
| ----------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Max 1 `ManualMappingCuration` per (subject_id, object_id)                                       | `rosetta lint`                             |
| Max 1 confirmed mapping per subject (no subject maps to multiple targets)                       | `rosetta lint`                             |
| Cannot re-propose a pair with **any** `HumanCuration` in log (approved or rejected)             | `rosetta accredit append` + `rosetta lint` |
| `HumanCuration` can only be ingested if a `ManualMappingCuration` predecessor exists            | `rosetta accredit append`                  |
| Once rejected, only the Accreditor can un-reject (by ingesting a corrected `HumanCuration` row) | Workflow convention                        |
| Approved mappings boost future `rosetta suggest` results                                        | `rosetta suggest` (log integration)        |
| Rejected mappings (`owl:differentFrom`) derank future `rosetta suggest` results                 | `rosetta suggest` (log integration)        |

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
Usage: rosetta accredit [OPTIONS] COMMAND

Global options:
  --audit-log PATH   Path to audit log .sssom.tsv  [default: store/audit-log.sssom.tsv]
  -c, --config PATH

Commands:
  append   Append ManualMappingCuration or HumanCuration rows to the audit log
  review   Output pending proposals (ManualMappingCuration with no decision yet)
  dump     Export current HumanCuration rows for pipeline use
```

**append:**

```
Usage: rosetta accredit append FILE

Arguments:
  FILE    SSSOM TSV file containing ManualMappingCuration or HumanCuration rows
```

Validates each row against the state machine before writing. If any row violates a rule, all errors are printed to stderr and nothing is written (no partial writes).

**review:**

```
Usage: rosetta accredit review [OPTIONS]

Options:
  -o, --output PATH    Output file (default: stdout)
```

**dump:**

```
Usage: rosetta accredit dump [OPTIONS]

Options:
  -o, --output PATH    Output file (default: stdout)
```

Outputs the latest `HumanCuration` row per pair as SSSOM TSV. Suitable for external pipeline consumption.

#### Audit log format

`audit-log.sssom.tsv` is an append-only SSSOM TSV file with 13 columns. Two columns are stamped at append time; the remaining 11 come from the appended SSSOM row.

| Column | Description |
| ------ | ----------- |
| `subject_id` | Source field URI |
| `predicate_id` | SKOS/OWL mapping predicate |
| `object_id` | Master ontology field URI |
| `mapping_justification` | SEMAPV justification CURIE |
| `confidence` | Score at time of proposal |
| `subject_label` | Human-readable source field name |
| `object_label` | Human-readable target field name |
| `mapping_date` | ISO 8601 UTC timestamp — when this row was ingested |
| `record_id` | UUID4 — unique identifier for this log entry |
| `subject_type` | SSSOM entity type (e.g., `"composed entity expression"` for composite mappings) |
| `object_type` | SSSOM entity type (e.g., `"composed entity expression"` for composite mappings) |
| `mapping_group_id` | Optional group identifier shared across rows that compose one logical mapping |
| `composition_expr` | Python/GREL composition expression for 1:N or N:1 mappings |

> The audit log persists reviewer-asserted fields only. Schema-derived fields (`subject_datatype`, `object_datatype`) appear in `rosetta suggest` output but are not stored in the audit log; they are re-derived by downstream tools from the source/master LinkML schemas.

> **Migration:** Pre-16-00 audit logs with 9 columns are automatically upgraded to the 13-column format on the first `rosetta accredit append` call. No manual migration is required.

A complete history for an approved mapping:

```
subject_id   predicate_id      object_id   mapping_justification         confidence  mapping_date          record_id  subject_type  object_type  mapping_group_id  composition_expr  subject_label  object_label
nor:speed    skos:relatedMatch  mst:speed  semapv:ManualMappingCuration  0.87        2026-04-15T09:00:00Z  <uuid>
nor:speed    skos:exactMatch    mst:speed  semapv:HumanCuration          0.87        2026-04-16T14:00:00Z  <uuid>
```

A rejected mapping (feeds derank into next suggest run):

```
nor:bearing  skos:relatedMatch  mst:heading  semapv:ManualMappingCuration  0.72  2026-04-15T09:00:00Z  <uuid>
nor:bearing  owl:differentFrom  mst:heading  semapv:HumanCuration          0.72  2026-04-16T14:00:00Z  <uuid>
```

#### Composite mappings

When a single source field maps to a combination of master fields (or vice versa), rosetta-cli uses the SSSOM composite-entity pattern. The analyst sets `subject_type` and/or `object_type` to `"composed entity expression"` and provides a `composition_expr` describing the transformation. Rows that belong to the same logical mapping share a `mapping_group_id`.

Example — a single NOR `position` field decomposes into separate master `latitude` and `longitude` slots:

```
subject_id       predicate_id    object_id          mapping_justification  confidence  subject_type                  object_type  mapping_group_id  composition_expr
nor:position     skos:closeMatch mst:latitude       semapv:HumanCuration   0.81        composed entity expression                grp-position-001  record["position"].split(",")[0]
nor:position     skos:closeMatch mst:longitude      semapv:HumanCuration   0.81        composed entity expression                grp-position-001  record["position"].split(",")[1]
```

See the [SSSOM composite-entity pattern documentation](https://mapping-commons.github.io/sssom/spec-model/#composite-entity) for the full specification.

> Note: rosetta-cli stores `subject_type` / `object_type` as the prose string `"composed entity expression"`, matching the canonical SSSOM example. The SSSOM Python package also accepts the CURIE `sssom:CompositeEntity`; rosetta-cli may migrate to the CURIE form in a future phase without changing behaviour.

#### Example session

```bash
# 1. Generate candidates (log is read automatically from rosetta.toml)
uv run rosetta suggest nor_emb.json master_emb.json -o candidates.sssom.tsv

# 2. Analyst edits candidates.sssom.tsv, marking ManualMappingCuration rows

# 3. Lint check
uv run rosetta lint candidates.sssom.tsv \
  --source-schema nor_radar_en.linkml.yaml \
  --master-schema master_cop_en.linkml.yaml

# 4. Stage analyst proposals
uv run rosetta accredit append candidates.sssom.tsv

# 5. Generate accreditor work list
uv run rosetta accredit review -o review.sssom.tsv

# 6. Accreditor edits review.sssom.tsv, marking HumanCuration rows

# 7. Ingest decisions
uv run rosetta accredit append review.sssom.tsv

# 8. Correct a previous decision
# (edit update.sssom.tsv with corrected HumanCuration row)
uv run rosetta accredit append update.sssom.tsv
```

**Exit codes:** 0 on success, 1 on state-machine violation or I/O error.

---

### rosetta validate

Validates an RDF data file (JSON-LD) against SHACL shape constraints using pySHACL.

```
Usage: rosetta validate [OPTIONS] DATA_FILE SHAPES_DIR

Arguments:
  DATA_FILE                          RDF data file (JSON-LD)
  SHAPES_DIR                         Directory — recursively loads all *.ttl files

Options:
  -o, --output PATH                  Output file  (default: stdout)
  -c, --config PATH                  Path to rosetta.toml
```

**Example:**

```bash
# Load all shapes (generated + hand-authored overrides) from the policies dir
uv run rosetta validate \
  mapping.jsonld \
  rosetta/policies/shacl/ \
  -o validation.json
```

**Exit codes:** 0 if conforms, 1 if SHACL violations found.

---

### rosetta shacl-gen

Auto-generates SHACL shapes from a master LinkML schema. Defaults to closed-world shapes (`sh:closed true` + `sh:ignoredProperties` for PROV-O / dcterms / rdf:type / qudt:hasUnit) and emits per-class `sh:in` constraints on `qudt:hasUnit` for slots whose names map to QUDT IRIs via `detect_unit`.

```
Usage: rosetta shacl-gen [OPTIONS] SCHEMA_FILE

Arguments:
  SCHEMA_FILE          Master LinkML schema YAML

Options:
  -o, --output PATH    Output SHACL Turtle file (default: stdout)
  --open               Emit open-world shapes (skip sh:closed and sh:ignoredProperties)
  -c, --config PATH    Path to rosetta.toml
```

**Example:**

```bash
# Default closed-world shapes
uv run rosetta shacl-gen \
  rosetta/tests/fixtures/nations/master_cop.linkml.yaml \
  -o master.shacl.ttl

# Plug straight into rosetta validate
uv run rosetta validate \
  mapping.jsonld \
  rosetta/policies/shacl/ \
  -o validation.json

# Open-world shapes for intentionally extensible master schemas
uv run rosetta shacl-gen master.linkml.yaml --open -o master.open.shacl.ttl
```

**Exit codes:** 0 on success, 1 on generation error, 2 on Click usage error.

---

### rosetta compile

Compiles an approved SSSOM audit log plus source and master LinkML schemas into a YARRRML mapping file. Internally builds a linkml-map `TransformationSpecification` YAML, then compiles it to YARRRML via the forked `YarrrmlCompiler`.

```bash
# Compile to YARRRML (stdout)
uv run rosetta compile store/audit-log.sssom.tsv \
  --source-schema demo_out/nor_radar.linkml.yaml \
  --master-schema demo_out/master_cop.linkml.yaml

# Compile to file with coverage report and intermediate TransformSpec
uv run rosetta compile store/audit-log.sssom.tsv \
  --source-schema demo_out/nor_radar.linkml.yaml \
  --master-schema demo_out/master_cop.linkml.yaml \
  -o demo_out/nor_to_mc.yarrrml.yml \
  --coverage-report demo_out/nor_to_mc.coverage.json \
  --spec-output demo_out/nor_to_mc.transform.yaml
```

**Exit codes:** 0 on success, 1 on error (malformed input, unresolvable CURIEs, empty SSSOM, missing source format annotation), 2 on Click usage error.

**Coverage report:** When `--coverage-report` is provided, a JSON file with the `CoverageReport` model is written. Fields: row-stage counts, resolved/unresolved class + slot mappings, datatype mismatches, composite-group resolution status, and required master slots that remain unmapped.

**Source format resolution:** The source format is read from `annotations.rosetta_source_format` on the source schema (stamped by `rosetta ingest`). Exit 1 if missing.

---

### rosetta run

Materializes a YARRRML mapping against a concrete data file via [morph-kgc](https://morph-kgc.readthedocs.io/) and frames the resulting RDF as JSON-LD using a `@context` derived from the master LinkML schema.

```bash
# Basic materialization (JSON-LD to stdout)
uv run rosetta run demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml

# Write to file with inline SHACL validation
uv run rosetta run demo_out/nor_to_mc.yarrrml.yml demo_out/nor_radar.csv \
  --master-schema demo_out/master_cop.linkml.yaml \
  -o demo_out/nor_tracks.jsonld \
  --validate rosetta/policies/shacl/ \
  --validate-report report.json
```

**Exit codes:** 0 on success, 1 on runtime or SHACL validation error, 2 on Click usage error. Empty materialized graph (0 triples) is not an error — a warning prints to stderr.

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
uv run pytest                               # full suite (default)
uv run pytest -m "not slow"                 # fast feedback — skips slow and e2e
uv run pytest -m "not slow and not e2e"     # CI fast-gate equivalent
uv run pytest -m integration                # integration tests only
uv run pytest -m e2e                        # end-to-end pipelines only
uv run pytest -k test_lint                  # run a specific module
```

Markers:

- `integration` — multi-component in-process tests via `CliRunner`
- `e2e` — full pipeline tests (usually also `slow`)
- `slow` — wall-clock >1s; deselect for quick iteration

CI runs the full suite on every push; a parallel `fast-gate` job runs
`-m "not slow and not e2e"` for sub-minute PR feedback.
