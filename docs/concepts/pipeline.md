# The pipeline

`rosetta-cli` is a set of composable commands. This page shows how they compose into one continuous flow from raw partner schemas to a validated RDF graph.

## Overview

```
┌────────────────┐    ┌─────────────────────────────────────────┐
│  Partner       │───▶│  rosetta ingest                         │
│  schema        │    │  • auto-detect format → LinkML YAML      │
└────────────────┘    │  • optional: --translate (DeepL)         │
                      │  • optional: --emit-master / --shapes    │
                      └──────────────────┬──────────────────────┘
                                         │
                                         ▼
                      ┌─────────────────────────────────────────┐
                      │  rosetta suggest                         │
                      │  • embed slots (LaBSE, structural)       │
                      │  • cosine similarity ranking             │
                      │  • audit-log boost/derank                │
                      │  → candidates.sssom.tsv                  │
                      └──────────────────┬──────────────────────┘
                                         │
                                         ▼
                      ┌─────────────────────────────────────────┐
                      │  rosetta ledger                          │
                      │  • append (analyst proposals, lint gate) │
                      │  • append (accreditor decisions)         │
                      │  → audit-log.sssom.tsv  (append-only)    │
                      └──────────────────┬──────────────────────┘
                                         │
                                         ▼
                      ┌─────────────────────────────────────────┐
                      │  rosetta compile                         │
                      │  • approved mappings → YARRRML           │
                      └──────────────────┬──────────────────────┘
                                         │
                                         ▼
                      ┌─────────────────────────────────────────┐
                      │  rosetta transform                       │
                      │  • YARRRML → morph-kgc → JSON-LD         │
                      │  • SHACL validation by default           │
                      │  → Conformant, validated RDF artifact    │
                      └─────────────────────────────────────────┘
```

## Stages

### 1. Ingest — schemas to LinkML

[`rosetta ingest`](../cli/ingest.md) auto-detects the input format and produces a LinkML schema YAML. Every generated schema is stamped with `annotations.rosetta_source_format` and per-slot path annotations (CSV column, JSONPath, or XPath) so downstream tools can generate format-aware RML mappings.

Pass `--translate` to run non-English titles and descriptions through DeepL so embeddings can compare across languages (originals preserved in `aliases`). Pass `--emit-master` or `--shapes` to produce a master OWL/SHACL artifact alongside the LinkML output.

### 2. Suggest — embed slots and rank candidates

[`rosetta suggest`](../cli/suggest.md) embeds slots internally (LaBSE lexical vectors + 5-dimensional structural vectors), blends cosine similarity scores, ranks the top-K candidates per source slot, and emits SSSOM TSV. When an audit log is configured, previously approved pairs are boosted and previously rejected pairs are deranked automatically.

Pass one or more schema files directly — `suggest` handles embedding internally; no separate embed step is required.

### 3. Accredit — the two-role state machine with lint gate

[`rosetta ledger`](../cli/ledger.md) manages the Analyst-proposes / Accreditor-approves workflow through an append-only audit log. When appending analyst proposals, a lint gate checks for physical-unit dimension mismatches, datatype incompatibilities, duplicate proposals, and conflicts with prior decisions. Pass `--strict` to treat warnings as blocks. See [Accreditation workflow](accreditation.md) for the full state machine.

### 4. Compile — approved mappings to YARRRML

[`rosetta compile`](../cli/compile.md) reads the audit log and produces a YARRRML mapping file ready for materialisation.

### 5. Transform — materialise to JSON-LD

[`rosetta transform`](../cli/transform.md) materialises the YARRRML against concrete source data via morph-kgc and frames the result as JSON-LD using a `@context` derived from the master LinkML schema. SHACL validation runs by default (pass `--no-validate` to skip).

## Composability

Because every step is a plain Unix command with stdin/stdout support and meaningful exit codes, you can:

- Pipe intermediate stages (`ingest` → `suggest` via stdout/stdin).
- Wrap the whole pipeline in a shell script (see `scripts/pipeline-demo.sh`).
- Run any prefix of it — e.g., stop at `suggest` if you only want ranked candidates.
- Re-run from any point after editing an intermediate artifact.
- Drive the pipeline from CI, treating `ledger append --strict` and `transform` as gates.

Nothing is hidden. Nothing is implicit. Every artifact is a file on disk in an open format.
