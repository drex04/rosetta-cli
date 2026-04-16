# Roadmap

## Phase 1: Project scaffolding and core setup
**Goal:** Working Python project with uv, package structure, shared config loading, RDF utilities, and test harness. Ready to build tools on top.

**Delivers:**
- `pyproject.toml` with uv + all dependencies declared
- Package structure: `rosetta/cli/`, `rosetta/core/`, `rosetta/policies/`, `rosetta/store/`, `rosetta/tests/`
- `rosetta/core/rdf_utils.py` — RDF I/O helpers (load/save Turtle, SPARQL helpers)
- `rosetta.toml` config loading with Click integration
- Pytest setup with fixtures directory
- Synthetic Master Air Defense Ontology (`store/master-ontology/master.ttl`)
- All 3 synthetic national schema test fixtures (NOR CSV, DEU JSON Schema, USA OpenAPI)

**Requirements:** REQ-09, REQ-10, REQ-26

---

## Phase 2: rosetta-ingest
**Goal:** Convert national schemas (CSV, JSON Schema, OpenAPI) into RDF Turtle.

**Delivers:**
- `rosetta/cli/ingest.py` with Click entrypoint
- Per-format parser modules: CSV, JSON Schema, OpenAPI (with `$ref` resolution)
- Unit detection via regex (field name + description patterns)
- Statistical summary computation from sample data
- Output: valid Turtle with `rosetta:stats` annotations

**Requirements:** REQ-01, REQ-02, REQ-03

---

## Phase 3: rosetta-embed + rosetta-suggest
**Goal:** Generate embeddings and get mapping suggestions.

**Delivers:**
- `rosetta/cli/embed.py` — LaBSE embeddings in `lexical-only` mode
- `rosetta/core/embedding.py` — model wrapper (sentence-transformers)
- `rosetta/cli/suggest.py` — cosine similarity + ranked suggestions
- `rosetta/core/similarity.py` — cosine sim, k-NN, anomaly detection
- Output formats defined: embedding JSON, suggestions JSON
- End-to-end: NOR CSV → embeddings → suggestions against master → correct cross-lingual matches

**Requirements:** REQ-04, REQ-05, REQ-06, REQ-07, REQ-08

---

## Phase 4: rosetta-lint
**Goal:** Catch unit mismatches, type issues, and suggest FnML conversions.

**Delivers:**
- `rosetta/cli/lint.py` with Click entrypoint
- `rosetta/core/units.py` — QUDT unit comparison
- FnML repository search (by source/target unit pair)
- BLOCK/WARNING/INFO lint report (JSON)
- Exit code 1 on BLOCKs
- `--strict` mode

**Requirements:** REQ-11, REQ-12, REQ-13, REQ-14, REQ-15

---

## Phase 5: Code quality infrastructure
**Goal:** Establish a robust, enforced code quality baseline — static type checking, consistent formatting/linting config, and Pydantic runtime validation for structured data — before building further tools on top.

**Delivers:**
- `basedpyright` configured in strict mode (pyproject.toml); clean check on all `rosetta/` source
- `ruff` fully configured (format + lint rules, target Python 3.11+)
- Full type annotations on all `rosetta/core/` and `rosetta/cli/` modules
- `pydantic>=2` added; Pydantic models for `LintFinding`, `LintReport`, `Suggestion`, `SuggestionReport`, `EmbeddingEntry`
- Bare `dict` returns replaced with typed models at core function boundaries
- Runtime validation at CLI output boundaries (models validated before JSON serialisation)

**Requirements:** REQ-QA-01, REQ-QA-02

---

## Phase 6: rosetta-rml-gen
**Goal:** Generate valid RML/FnML Turtle from approved decisions.

**Delivers:**
- `rosetta/cli/rml_gen.py` with Click entrypoint
- RML template engine (LogicalSource, SubjectMap, PredicateObjectMap)
- FnML `functionValue` wrapping when conversion function specified
- Output: valid RML executable by RMLMapper

**Requirements:** REQ-16, REQ-17

---

## Phase 7: rosetta-provenance
**Goal:** Stamp PROV-O metadata on mapping artifacts.

**Delivers:**
- `rosetta/cli/provenance.py` with Click entrypoint
- `rosetta/core/provenance.py` — PROV-O triple generation
- `--query` mode: human-readable provenance summary
- Version increment on each stamp

**Requirements:** REQ-18, REQ-19

---

## Phase 8: rosetta-validate
**Goal:** SHACL validation of mapping artifacts.

**Delivers:**
- `rosetta/cli/validate.py` with Click entrypoint
- pySHACL wrapper (single shape file or `--shapes-dir`)
- Structured JSON report
- Exit code 0/1

**Requirements:** REQ-20, REQ-21

---

## Phase 9: rosetta-accredit + feedback loop
**Goal:** Full governance layer. Accreditation state machine + suggestion feedback loop.

**Delivers:**
- `rosetta/cli/accredit.py` with Click entrypoints (submit/approve/revoke/status)
- `ledger.json` maintenance (accredited, revoked, deprecated mappings)
- `rosetta-suggest` reads ledger: boosts accredited precedents, excludes revoked
- `scripts/pipeline.sh` — end-to-end composition demo
- Full Milestone 3 test: approve NOR mapping → German suggestions improve; revoke → disappears

**Requirements:** REQ-22, REQ-23, REQ-24, REQ-25

---

## Phase 10: rosetta-translate
**Goal:** Normalise non-English field labels to English via DeepL before embedding,
enabling English-to-English vector comparisons with a higher-quality English-specialized
model (intfloat/e5-large-v2). The tool is a clean passthrough for English-source schemas.

**Delivers:**
- `rosetta/cli/translate.py` — new `rosetta-translate` CLI tool
- `rosetta/core/translation.py` — DeepL wrapper + passthrough logic
- Dual-label audit trail: `rdfs:label` updated to English, `rose:originalLabel` preserves original
- `--source-lang EN` passthrough: no API call, output TTL identical to input
- `rosetta.toml` updated: `[translate]` section + `[embed].model = intfloat/e5-large-v2`

**Requirements:** REQ-TRANSLATE-01

---

## Phase 11: rosetta-ingest extensions
**Goal:** Extend `rosetta-ingest` with two new input modes: XSD schema parsing and
JSON sample-data deduction.

**Delivers:**
- `rosetta/core/parsers/xsd_parser.py` — full XSD vocabulary support (complexType, sequence,
  choice, extension, restriction, attributes); `.xsd` auto-detected from extension
- `rosetta/core/parsers/json_sample_parser.py` — infer JSON Schema from instance data via
  `genson`, pipe through existing `parse_json_schema`; `--input-format json-sample` required
- Updated `dispatch_parser` wiring for both new formats
- Tests, fixtures, README updates for both formats

**Requirements:** REQ-INGEST-XSD-01, REQ-INGEST-SAMPLE-01

---

## Milestone: v2.0 — LinkML + SSSOM migration

---

## Phase 12: Schema Normalization
**Goal:** Replace all custom schema parsers with schema-automator importers. Adopt LinkML
`SchemaDefinition` as the single internal schema representation. Update `rosetta-translate`
to operate on LinkML YAML instead of RDF Turtle. Lay the dependency foundation (sssom)
for Phase 13.

**Delivers:**
- `rosetta/core/normalize.py` — `normalize_schema()` dispatching to 7 format importers
- `rosetta/cli/ingest.py` rewritten — outputs `.linkml.yaml`; adds `--schema-name`; drops `--nation`
- `rosetta/core/translation.py` + `rosetta/cli/translate.py` updated — LinkML YAML I/O;
  translates class + slot titles and descriptions; preserves originals in `aliases`
- `rosetta/core/parsers/` deleted entirely (all custom parsers and `FieldSchema`)
- `schema-automator >= 0.5.5` and `sssom >= 0.4.15` added to dependencies

**Requirements:** REQ-V2-INGEST-01

---

## Phase 13: Semantic Matching
**Goal:** Update `rosetta-embed` and `rosetta-suggest` to work with LinkML SchemaDefinition.
Add structural feature extraction. Output SSSOM candidates with confidence scores.

**Delivers:**
- `rosetta-embed` updated — consumes `.linkml.yaml`; computes embeddings from slot/class titles + descriptions
- Structural feature extraction — class hierarchy, slot co-occurrence, cardinality
- `rosetta-suggest` updated — outputs `.sssom.tsv` candidates; confidence field carries similarity scores
- Accredited SSSOM store integrated into suggestion boost logic

**Requirements:** REQ-V2-SUGGEST-01

---

## Phase 14: User Review
**Goal:** User approves/rejects SSSOM candidate mappings. Produce an approved SSSOM mapping set
ready for formal accreditation.

**Delivers:**
- `rosetta-review` (new tool or extended `rosetta-suggest`) — user approve/reject workflow
- Output: `mappings-user-approved.sssom.tsv` with `mapping_justification: semapv:ManualMappingCuration`
- Updated `rosetta-accredit` — reads/writes SSSOM instead of `ledger.json`; accredited
  mappings feed back into suggestion boost (Phase 13 loop)

**Requirements:** REQ-V2-REVIEW-01

---

## Phase 15: rosetta-lint SSSOM enrichment
**Goal:** Remove the legacy RDF lint path entirely. Enrich the SSSOM lint path with
unit-compatibility and datatype-compatibility checks drawn from QUDT and the LinkML schema.
Produce a machine-readable JSON `LintReport` from the SSSOM path (matching the old RDF
path's output contract).

**Delivers:**
- `rosetta/core/models.py` — `EmbeddingVectors.datatype` field; `SSSOMRow.subject_datatype` + `object_datatype`
- `rosetta/cli/embed.py` — populate `datatype` from `slot.range` in embedding report
- `rosetta/cli/suggest.py` — propagate `subject_datatype`/`object_datatype` into SSSOM TSV (2 new columns)
- `rosetta/core/accredit.py` — `_parse_sssom_row` reads new optional columns
- `rosetta/cli/lint.py` — RDF path deleted; SSSOM path outputs JSON `LintReport`; unit + datatype checks added
- `rosetta/tests/test_lint.py` — RDF tests removed; SSSOM unit/datatype tests added
- `README.md` — rosetta-lint section updated

**Requirements:** REQ-V2-LINT-01

---

## Phase 16: rosetta-rml-gen v2 (SSSOM → linkml-map TransformSpec → YARRRML → JSON-LD)
**Goal:** Replace the legacy decisions-JSON-driven RML Turtle generator with a pipeline
built on linkml-map's `TransformationSpecification` as the canonical IR, compiled to YARRRML
via a new `YarrrmlCompiler` contributed to a fork of linkml-map. Read approved SSSOM mappings,
build a TransformSpec, compile to YARRRML, execute via morph-kgc, and frame the output as
JSON-LD conforming to the master ontology.

Design doc: `.planning/designs/2026-04-16-phase16-rml-gen-v2.md`

**Delivers (split across 4 plans):**

### 16-00: SSSOM audit-log schema extension (prerequisite)
- Extend `SSSOMRow` with `subject_type`, `object_type`, `mapping_group_id`, `composition_expr`
- Audit log: 9 → 13 columns; suggest TSV: 11 → 15 columns
- Supports the SSSOM composite-entity pattern for 1:N and N:1 mappings

### 16-01: SSSOM → linkml-map TransformSpec (rosetta-cli)
- New `rosetta/core/transform_builder.py`
- Reads SSSOM + source LinkML + master LinkML; emits `mapping.transform.yaml`
- Groups rows by `mapping_group_id` for composite mappings; flows `composition_expr` to `SlotDerivation.expr`
- Schema coverage check; CURIE resolution via `curies.Converter`
- `rosetta-yarrrml-gen` CLI entrypoint (no YARRRML yet — TransformSpec only)

### 16-02: YarrrmlCompiler (forked linkml-map)
- Fork `linkml/linkml-map`; add `compiler/yarrrml_compiler.py` + Jinja2 template
- Handles `class_derivations`, `slot_derivations`, `unit_conversion` → FnML GREL, source-format references (JSON/CSV/XML)
- Registered as `linkml-tr compile yarrrml`
- `rosetta-cli` pins the fork via git SHA in `pyproject.toml`

### 16-03: morph-kgc runner + JSON-LD framing + E2E
- `rosetta/core/rml_runner.py` wraps `morph_kgc.materialize()`
- JSON-LD output via `linkml gen-jsonld-context` + rdflib framing
- `rosetta-yarrrml-gen --run` one-shot mode
- README rewrite; E2E test: NOR CSV → SSSOM → TransformSpec → YARRRML → JSON-LD

**Requirements:** REQ-V2-RMLGEN-01

---

## Phase 17: QUDT-native multi-library unit detection
**Goal:** Make `detect_unit()` return QUDT IRIs directly, eliminating the `UNIT_STRING_TO_IRI`
lookup table and the sync-mismatch gotcha it created. Add two new detection layers: expanded regex
(name + description) and quantulum3 NLP extraction validated by pint. Expand from 7 to ~25
NATO-relevant units. False positives gated by pint — unmappable results return `None`.

**Delivers:**
- `rosetta/core/unit_detect.py` — expanded regex patterns + quantulum3+pint cascade; returns QUDT IRIs;
  `_PINT_TO_QUDT_IRI` internal mapping table; lazy imports
- `rosetta/core/units.py` — `UNIT_STRING_TO_IRI` deleted; all other helpers unchanged
- `rosetta/cli/lint.py` — uses `detect_unit()` output as IRI directly; no lookup table
- `rosetta/policies/qudt_units.ttl` — new unit triples: HZ, KiloHZ, MegaHZ, GigaHZ, MilliRAD,
  HectoPa, DEG_F, MI-PER-HR
- `rosetta/tests/test_unit_detect.py` — IRI-based assertions; quantulum3-path tests
- `rosetta/tests/test_lint.py` — UNIT_STRING_TO_IRI tests replaced with detect_unit() equivalents
- `pyproject.toml` / `uv.lock` — quantulum3 and pint declared

**Note:** Phase 17 is independent of Phase 16 (rml-gen v2). Can be built in any order.

**Requirements:** REQ-UNIT-DETECT-01


