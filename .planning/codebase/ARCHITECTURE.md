# Architecture

**Analysis Date:** 2026-04-16 | **Phases:** 14 (audit-log SSSOM), 15 (SSSOM-only lint)

## Pattern Overview
**Overall:** Unix-composable pipeline of single-responsibility CLI tools.
- Each tool reads file/stdin, writes file/stdout — composable in shell pipelines.
- Strict layer separation: CLI (I/O + Click) → Core (pure logic) → Store (file persistence).
- Canonical formats: LinkML YAML (schemas), SSSOM TSV (mappings + audit log), JSON (embeddings).
- No shared in-process state — tools communicate via files on disk.

## Layers

**CLI Layer** (`rosetta/cli/`):
- Purpose: Click entrypoints, argument parsing, I/O orchestration, exit codes.
- Pattern: Parse config (precedence: CLI flag > env > rosetta.toml), load inputs, call core functions, serialize Pydantic models via `model.model_dump(mode="json")`, exit(0 or 1).
- Entry points in `pyproject.toml [project.scripts]`: 9 tools.

**Core Layer** (`rosetta/core/`):
- Purpose: Stateless functions + utility classes — normalization, embedding, similarity, RDF, audit log I/O.
- Key modules:
  - `normalize.py` — dispatch on format (7 supported); returns `SchemaDefinition`.
  - `embedding.py` — E5 model (E5 passage prefix logic); lexical vector encoding.
  - `features.py` — extract 5-element structural vectors (depth, child_count, slot_usage, cardinality, parent_depth).
  - `similarity.py` — cosine matrix; rank suggestions with lexical+structural blend (weight=0.2); audit-log boost/derank.
  - `accredit.py` — state-machine: load/append/parse SSSOM log; validate ingest rules; state queries.
  - `units.py` — QUDT graph loading; unit compatibility; FNML suggestions.
  - `unit_detect.py` — regex-based unit detection from field labels.
  - `models.py` — Pydantic v2 output types: SSSOMRow, LintReport, EmbeddingReport, SuggestionReport, ValidationReport, ProvenanceRecord, CoverageReport.
  - `rdf_utils.py`, `translation.py`, `provenance.py` — utilities.

**Policies Layer** (`rosetta/policies/`):
- Purpose: Static knowledge graphs (loaded via importlib.resources).
- Files: `qudt_units.ttl` (QUDT ontology), `fnml_registry.ttl` (FNML functions), `mapping.shacl.ttl` (SHACL constraints).

**Store Layer** (`store/`):
- Purpose: Runtime file persistence.
- Files: `audit-log.sssom.tsv` (9-column SSSOM: subject_id, predicate_id, object_id, mapping_justification, confidence, subject_label, object_label, mapping_date, record_id). Datatype columns are intentionally excluded from the audit log per Phase 15 design — they live only on the suggest-output TSV (11 columns).

## Data Flow

**rosetta-ingest:**
1. `rosetta/cli/ingest.py` — input schema file (CSV, TSV, JSON Schema, OpenAPI, RDFS, XSD, TTL) + format flag.
2. `normalize_schema()` dispatches to schema-automator (JSON Schema/OpenAPI/XSD), genson (CSV/TSV/JSON-sample), LinkML parsers (RDFS/TTL).
3. Output: `.linkml.yaml` (LinkML SchemaDefinition).

**rosetta-embed:**
1. `rosetta/cli/embed.py` — reads `.linkml.yaml`.
2. Extract labels from nodes; load E5 model (default: `intfloat/e5-large-v2`); apply passage prefix ("passage: " for E5, "" for others).
3. `extract_structural_features_linkml()` — 5-element vectors per node (normalized to [0,1]).
4. Output: JSON `{field_name → EmbeddingVectors{label, lexical: [1024], structural: [5], datatype?}}`.

**rosetta-suggest:**
1. `rosetta/cli/suggest.py` — reads source embeddings JSON + master embeddings JSON.
2. `cosine_matrix()` — pairwise cosine similarity on lexical vectors.
3. `rank_suggestions(A, B, A_struct?, B_struct?, structural_weight=0.2)` — blend: `score = lex * (1 - w) + struct * w`; top-k per source, filter by min_score.
4. `apply_sssom_feedback(suggestions, audit_log)` — for each (subject, object): if approved HC in log, boost +0.1; if owl:differentFrom, derank.
5. Output: `.sssom.tsv` from `rosetta-suggest` is 11 columns (adds `subject_datatype`, `object_datatype` to the 9 base columns).

**rosetta-lint:**
1. `rosetta/cli/lint.py` — reads SSSOM TSV; loads audit log if configured.
2. Checks: MaxOneMmcPerPair, NoHumanCurationReproposal, valid predicates, unit compatibility (QUDT), datatype mismatch (LinkML numeric set: {integer, int, float, double, decimal, long, short, nonNegativeInteger, positiveInteger}).
3. Output: LintReport JSON (findings array + block/warning/info counts).

**rosetta-accredit:**
1. `ingest <sssom.tsv>` — `check_ingest_row()` validates state-machine (no duplicate MMC in-file, no HC reproposal if prior HC rejection in log); `append_log()` stamps mapping_date (ISO 8601 UTC), record_id (UUID4); appends to `store/audit-log.sssom.tsv`.
2. `review [field_id] [decision]` — query pending via `query_pending()` (HC awaiting manual decision).
3. `status` — query `current_state_for_pair()` (latest record per pair).
4. `dump` — output all non-deleted audit records.

**rosetta-yarrrml-gen:**
1. Reads approved SSSOM audit log + source and master LinkML schemas.
2. Outputs a linkml-map `TransformationSpecification` YAML (first half of the SSSOM → YARRRML pipeline).

**rosetta-translate:**
1. Translates LinkML YAML field labels via DeepL (source_lang: "auto" or "EN").

**rosetta-validate:**
1. Runs pySHACL against `mapping.shacl.ttl`; exit 0 (valid) or 1 (violations).

**rosetta-provenance:**
1. Extracts provenance metadata from ingest + accredit records.

## Key Abstractions

**`normalize_schema(path, fmt=None, schema_name=None) → SchemaDefinition`:**
- Single dispatch for 7 formats → LinkML SchemaDefinition.
- Auto-detects from file extension; raises ValueError for unsupported.

**`EmbeddingModel` (embedding.py):**
- Property `prefix` — "passage: " for E5 models, "" for others.
- Default: `intfloat/e5-large-v2` from config `[embed].model`.
- Loads via sentence-transformers; encodes text to float vectors (1024-dim).

**`extract_structural_features_linkml(schema) → dict[str, list[float]]`:**
- Returns [depth, child_count, slot_usage, cardinality, parent_depth] per node (all ∈ [0,1]).

**`rank_suggestions(src_uris, A, master_uris, B, top_k=5, min_score=0.0, A_struct=None, B_struct=None, structural_weight=0.2) → dict`:**
- Cosine similarity (A @ B.T / norms); blends structural if provided.
- Returns top_k per source URI, filtered by min_score, ranked descending.

**`apply_sssom_feedback(suggestions: dict, audit_log: list[SSSOMRow]) → dict`:**
- Boosts approved (HC) pairs: +0.1 confidence.
- Deranks rejected (owl:differentFrom) pairs: removes from suggestions.

**Accredit state-machine (accredit.py):**
- `load_log(path) → list[SSSOMRow]` — parse 9-column audit-log SSSOM; tolerates 11-column suggest TSV via `.get()` defaults; coerce datetime to UTC.
- `append_log(path, rows)` — atom-lock; stamp missing mapping_date/record_id; append to file with headers if new.
- `parse_sssom_tsv(path) → list[SSSOMRow]` — parse TSV rows; coerce types.
- `current_state_for_pair(log, subject_id, object_id) → SSSOMRow | None` — latest record for pair.
- `query_pending(log) → list[SSSOMRow]` — HC rows awaiting manual decision.
- `check_ingest_row(row, log) → bool` — validate: no duplicate MMC in-file; no HC reproposal if prior HC rejection.

**`SSSOMRow` (models.py):**
- Fields: subject_id, predicate_id, object_id, mapping_justification, confidence, subject_label, object_label, mapping_date (datetime | None), record_id (UUID4 | None), subject_datatype, object_datatype.
- Stamped by accredit ingest; serialized to JSON via `model_dump(mode="json")`.

**Pydantic output models (models.py):**
- All user-facing structured output typed — LintReport, EmbeddingReport (RootModel), SuggestionReport (RootModel), ValidationReport, ProvenanceRecord, CoverageReport.
- Construct in CLI; serialize with `model.model_dump(mode="json")` before `json.dumps()`.

**Config precedence (config.py):**
- CLI flag > env var (`ROSETTA_SECTION_KEY`) > `rosetta.toml` > hardcoded default.

## Entry Points

All 9 tools in `pyproject.toml [project.scripts]`:
- `rosetta-ingest` → `rosetta/cli/ingest.py:cli`
- `rosetta-embed` → `rosetta/cli/embed.py:cli`
- `rosetta-suggest` → `rosetta/cli/suggest.py:cli`
- `rosetta-lint` → `rosetta/cli/lint.py:cli`
- `rosetta-validate` → `rosetta/cli/validate.py:cli`
- `rosetta-yarrrml-gen` → `rosetta/cli/yarrrml_gen.py:cli`
- `rosetta-provenance` → `rosetta/cli/provenance.py:cli`
- `rosetta-accredit` → `rosetta/cli/accredit.py:cli`
- `rosetta-translate` → `rosetta/cli/translate.py:cli`

## Error Handling
- Exit 0 = success/conformant; Exit 1 = errors/violations.
- Core raises `ValueError` with human-readable message.
- CLI catches `ValueError`, prints to stderr, calls `sys.exit(1)`.
- No internal recovery — fail fast.
