# The pipeline

`rosetta-cli` is a set of composable commands. This page shows how they compose into one continuous flow from raw partner schemas to a validated RDF graph.

## Overview

```
┌────────────────┐    ┌───────────────┐    ┌──────────────┐
│  Partner       │───▶│  LinkML YAML  │───▶│  Embeddings  │
│  schema        │    │  (normalised) │    │  (per slot)  │
└────────────────┘    └───────────────┘    └──────┬───────┘
   rosetta-ingest        rosetta-translate        │  rosetta-embed
                                                  ▼
┌──────────────────────────────────────────────────────────────┐
│  rosetta-suggest  →  candidates.sssom.tsv                    │
│     (cosine similarity, boosted/deranked by audit log)       │
└──────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────┐
│  Analyst edits → rosetta-lint → rosetta-accredit append      │
│  Accreditor reviews → rosetta-accredit append                │
│                           │                                  │
│                           ▼                                  │
│                  audit-log.sssom.tsv  (append-only)          │
└──────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────┐
│  rosetta-yarrrml-gen --run                                   │
│     TransformSpec YAML → YARRRML → morph-kgc → JSON-LD       │
└──────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────┐
│  rosetta-validate (SHACL)                                    │
│     Conformant, validated RDF artifact                       │
└──────────────────────────────────────────────────────────────┘
```

## Stages

### 1. Ingest — schemas to LinkML

[`rosetta-ingest`](../cli/ingest.md) auto-detects the input format and produces a LinkML schema YAML. Every generated schema is stamped with `annotations.rosetta_source_format` and per-slot path annotations (CSV column, JSONPath, or XPath) so downstream tools can generate format-aware RML mappings.

### 2. Translate — optional, multilingual normalisation

[`rosetta-translate`](../cli/translate.md) runs non-English titles and descriptions through DeepL so embeddings can compare across languages. Originals are preserved in `aliases`. For English-source schemas, pass `--source-lang EN` and the step is a no-op.

### 3. Embed — semantic vectors per slot

[`rosetta-embed`](../cli/embed.md) produces a JSON map of slot URI → embedding vector. Each entry carries a `label`, a `lexical` vector (from the sentence transformer), and a 5-dimensional `structural` vector encoding is-class, hierarchy depth, is-required, is-multivalued, and slot-usage count — all normalised to `[0, 1]`.

### 4. Suggest — rank candidates

[`rosetta-suggest`](../cli/suggest.md) blends lexical and structural cosine similarity, ranks the top-K candidates per source slot, and emits SSSOM TSV. When an audit log is configured, previously approved pairs are boosted and previously rejected pairs are deranked automatically.

### 5. Lint — catch problems before humans see them

[`rosetta-lint`](../cli/lint.md) flags physical-unit dimension mismatches, datatype incompatibilities, duplicate proposals, and conflicts with prior accreditation decisions. In `--strict` mode, warnings become blocks — use it as a CI gate on the mapping repo.

### 6. Accredit — the two-role state machine

[`rosetta-accredit`](../cli/accredit.md) manages the Analyst-proposes / Accreditor-approves workflow through an append-only audit log. See [Accreditation workflow](accreditation.md) for the full state machine.

### 7. Generate — compile approved mappings into RML

[`rosetta compile`](../cli/compile.md) reads the audit log and produces a YARRRML mapping file. [`rosetta run`](../cli/run.md) materialises the YARRRML against concrete source data via morph-kgc and frames the result as JSON-LD using a `@context` derived from the master LinkML schema.

### 8. Validate — SHACL conformance

[`rosetta-validate`](../cli/validate.md) runs the materialised RDF against SHACL shapes. Exit `0` conformant, `1` violations — compose it into CI.

## Composability

Because every step is a plain Unix command with stdin/stdout support and meaningful exit codes, you can:

- Pipe intermediate stages (`ingest` → `embed` via stdout/stdin).
- Wrap the whole pipeline in a shell script (see `scripts/pipeline-demo.sh`).
- Run any prefix of it — e.g., stop at `suggest` if you only want ranked candidates.
- Re-run from any point after editing an intermediate artifact.
- Drive the pipeline from CI, treating `lint --strict` and `validate` as gates.

Nothing is hidden. Nothing is implicit. Every artifact is a file on disk in an open format.
