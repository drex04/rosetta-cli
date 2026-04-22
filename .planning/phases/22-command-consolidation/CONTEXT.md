# Phase 22: Command Consolidation — Locked Decisions

## D-22-01: `translate` folded into `ingest`
**Decision:** `rosetta translate` is removed. Translation is triggered via `--translate --lang <code>` flags on `rosetta ingest`. DeepL key resolved via `--deepl-key` flag or `DEEPL_API_KEY` env var.
**Rationale:** Translation always follows ingestion; separate command adds no value.

## D-22-02: Multi-schema positional args on `ingest`
**Decision:** `rosetta ingest` accepts one or more source schema files as positional args. Each produces `{stem}.linkml.yaml`. With multiple inputs, `-o` is a directory; stdout only works for a single input.
**Rationale:** Batch ingestion is the common case; eliminates repeated invocations.

## D-22-03: `ingest --master` for ontology + shapes
**Decision:** `--master <ontology.ttl>` normalizes the master ontology to LinkML YAML and generates SHACL shapes alongside it as `{stem}.shacl.ttl`. First `--master` run scaffolds `rosetta.toml` if absent.
**Rationale:** Master ontology is a project-level input; shapes are a maintained artifact the user edits. Separate `init` command rejected — `--master` flag on an existing command avoids a new concept.

## D-22-04: `embed` folded into `suggest`
**Decision:** `rosetta suggest` accepts LinkML YAML schemas directly (source + master) and embeds internally. No pre-computed embedding files required. Standalone `rosetta embed` is removed.
**Rationale:** Embed was never consumed independently; requiring two separate embed runs was the biggest UX pain point.

## D-22-05: `lint` folded into `ledger append` as a gate
**Decision:** `rosetta lint` is removed as a standalone command. All lint checks run automatically inside `ledger append` before rows are written. Lint failure rejects the append. `--source-schema` and `--master-schema` are required flags on `ledger append`.
**Rationale:** Lint without append is a dry-run; lint after append is too late. Gate position is correct.

## D-22-06: `ledger append --dry-run`
**Decision:** `--dry-run` runs lint and reports findings but does not append to the audit log. Replaces the standalone `rosetta lint` use case.
**Rationale:** Users need to preview lint results before committing to an append.

## D-22-07: `ledger append --role` (required)
**Decision:** `--role analyst` or `--role accreditor` is required on every `ledger append` invocation. Role determines lint rules and row filtering:
- `--role analyst`: lint BLOCKs any HumanCuration rows; only ManualMappingCuration rows are appended.
- `--role accreditor`: only HumanCuration rows are appended.
No default role — explicit is better than implicit.
**Rationale:** The role determines the state machine transition; implicit role detection from file content is fragile.

## D-22-08: `transform` validates by default
**Decision:** `rosetta transform` runs SHACL validation by default. `--no-validate` flag opts out. `--validate <shapes-dir>` remains for specifying custom shapes. Default shapes location read from config or convention.
**Rationale:** Validation is the safe default; skipping is the exception.

## D-22-09: Standalone commands removed
**Decision:** `translate`, `embed`, `shapes`, `validate`, `lint` are removed as top-level subcommands. No backward-compat aliases.
**Rationale:** Internal tool, no external users. Functionality is consolidated into `ingest`, `suggest`, `ledger append`, and `transform`.

## D-22-10: Keep `ingest` name
**Decision:** The command is `rosetta ingest`, not `rosetta init`. `--master` flag handles the one-time project setup concern.
**Rationale:** "Init" implies one-time use; `ingest` works for both first-time setup and adding sources on day 30.

## D-22-11: Shapes output location
**Decision:** `ingest --master ontology.ttl` writes shapes alongside the normalized ontology as `{stem}.shacl.ttl`.
**Rationale:** Simple, predictable, no extra flags needed.

---

## Dependencies

- **Phase 21 (HC Filtering) must be complete before Phase 22.** Phase 21 modifies `lint.py`, `suggest.py`, and `similarity.py`. Phase 22 rewrites or removes these files. Building 22 on pre-21 code would cause merge conflicts and rework.
