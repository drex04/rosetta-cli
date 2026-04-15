---
phase: 13
plan: "02"
title: "structural feature extraction"
status: complete
commit: cbdd2dd
tests: "177/177"
completed: "2026-04-15"
---

# Summary: Plan 13-02 — Structural Feature Extraction

## What Was Built

Implemented structural feature extraction for LinkML schemas and blended lexical+structural cosine similarity in `rosetta-suggest`.

### New: `rosetta/core/features.py`
- `extract_structural_features_linkml(schema: SchemaDefinition) -> dict[str, list[float]]`
- Returns 5-float vector per class and slot: `[is_class, hierarchy_depth_normalized, is_required, is_multivalued, slot_usage_count_normalized]`
- Iterative (non-recursive) `is_a` chain walking for deep-schema safety
- Node IDs match `extract_text_inputs_linkml` format (`schema_name/node_name`)

### Updated: `rosetta/core/models.py`
- `EmbeddingVectors` gained `structural: list[float] = []` — backward-compatible with old embed files

### Updated: `rosetta/cli/embed.py`
- Calls `extract_structural_features_linkml` after lexical embedding, merges into `EmbeddingReport`
- No CLI flags added — always-on extraction

### Updated: `rosetta/core/similarity.py`
- `rank_suggestions` gained keyword-only `A_struct`, `B_struct`, `structural_weight=0.2`
- Linear blend: `final = (1 - w) * lex_sim + w * struct_sim`; silent fallback to lexical-only when either array is None or all-zero

### Updated: `rosetta/cli/suggest.py`
- Reads `structural_weight` from `rosetta.toml [suggest]` via `get_config_value`
- Builds `A_struct`/`B_struct` numpy arrays from `EmbeddingReport.root[u].structural`
- Mixed-vintage warning on stderr when one file has structural arrays but not the other
- Emits `semapv:CompositeMatching` when blending active, `semapv:LexicalMatching` otherwise

### Updated: `rosetta.toml`
- Added `structural_weight = 0.2` to `[suggest]`

### New: `rosetta/tests/test_features.py` (6 tests)
All 6 structural feature unit tests pass.

### Updated: `rosetta/tests/test_suggest.py` (+5 tests)
- `test_rank_suggestions_structural_blend` — blended score differs from lexical-only
- `test_rank_suggestions_structural_fallback` — None arrays → lexical-only identical
- `test_rank_suggestions_structural_weight_zero` — w=0.0 → pure lexical
- `test_rank_suggestions_structural_partial_zeros` — all-zero master rows → lexical fallback
- `test_suggest_cli_structural_weight_config` — different weights → different confidence values

### Updated: `rosetta/tests/test_embed.py`
- `test_embed_linkml_cli` now asserts `"structural"` key present with length 5

### Updated: `README.md`
- Documented `structural` array in embed output
- Documented `structural_weight`, auto-blending, fallback, and `mapping_justification` values

## Test Metrics

- Before: 166 tests
- After: 177 tests (+11)
- All 177 passing

## Issues Encountered

None — all 4 waves completed cleanly.

## Next Action

Phase 13 complete. Run `/fh:build` to execute Phase 14 (User Review — approve/reject → approved SSSOM).
