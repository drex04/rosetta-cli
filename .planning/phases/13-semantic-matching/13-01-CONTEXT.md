---
phase: 13
plan: "01"
title: "linkml upgrade + SSSOM output"
---

# Context: Phase 13-01

## Locked Decisions (from plan-work)

- SSSOM TSV only output (no JSON fallback) — clean v2 break
- `predicate_id: skos:relatedMatch` + `mapping_justification: semapv:LexicalMatching` for all auto-generated candidates
- `anomaly` field dropped — not a SSSOM concept
- `--ledger` renamed to `--approved-mappings`; reads `.sssom.tsv`
- Boost logic: additive `+0.1`, cap 1.0

## Decisions (from plan-review 2026-04-14)

- [review] **Revocation model:** `apply_sssom_feedback` uses a dual-intent SSSOM file. Rows with `predicate_id == owl:differentFrom` → subtract penalty (floor 0.0), row NOT removed from SSSOM table. Any other predicate hit → additive boost. Soft subject-breadth deranking (penalty × 0.25) applied to all other candidates when any differentFrom row exists for the subject_id. Why: SSSOM has no native revoke concept; this keeps the rejected mapping visible to downstream consumers while discouraging re-selection.

- [review] **Anomaly removal scope:** `rank_suggestions()` `anomaly_threshold` parameter and `"anomaly"` return key are removed (not just the CLI flag). Three unit tests (`test_rank_suggestions_anomaly_true/false/pre_filter`) are deleted. Why: Phase 14 human review supersedes the heuristic threshold; keeping a dead parameter in a core public function is confusing.

- [review] **Label source:** `rosetta-embed` derives `label` from the last URI fragment (after `#` or `/`) and writes it to `EmbeddingVectors.label`. `rosetta-suggest` reads this for `subject_label`/`object_label` SSSOM columns. Why: label must survive into Phase 14 human review for readability; URI fragment parsing is simple and sufficient; avoids a separate lookup step.

- [review] **`EmbeddingVectors.label` is backward-compatible:** field defaults to `""` so existing `.embed.json` files without the key still load without error.

- [review] **`Suggestion`/`FieldSuggestions`/`SuggestionReport` removal is safe:** only `suggest.py` (being rewritten) imports these; `units.py` only imports `FnmlSuggestion` — confirmed by audit.

- [review] **SSSOM header curie_map is required:** both sssom-library and hand-rolled TSV paths must emit `# curie_map: {skos: ..., semapv: ...}` block so downstream SSSOM validators accept the file.

- [review] **`object_id` in approved SSSOM must be a full URI:** must match the embedding JSON key exactly (e.g. `http://example.org/ont#HeightAGL`). CURIEs in approved files will produce zero matches silently. Document in README.

## Deferred Ideas

- **`--excluded-mappings` as separate flag:** considered and rejected; dual-intent single file (`owl:differentFrom`) is simpler and more SSSOM-native.
- **Add label to embed input schema:** considered; URI fragment parsing is sufficient for Phase 14 readability without touching the ingest pipeline.
- **Narrow `except Exception` in suggest.py:** worthwhile but not in scope for this plan; tracked as tech debt.
