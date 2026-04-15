---
phase: 13
plan: "02"
title: "structural feature extraction"
---

# Context: Phase 13-02

## Locked Decisions (from plan-work 2026-04-15)

- **Structural features stored in `.embed.json`**: `EmbeddingVectors.structural: list[float] = []` — backward-compatible default; old embed files load without error and cause suggest to fall back to lexical-only.
- **Always-on extraction**: `rosetta-embed` always populates `structural`; no CLI flag. Cost is negligible (no model inference — pure schema traversal).
- **5-float feature vector** (per node, in order):
  - `[0]` `is_class` — 1.0 if class, 0.0 if slot
  - `[1]` `hierarchy_depth_normalized` — depth in `is_a` chain, normalized by max depth in schema (0.0 if no hierarchy or depth 0)
  - `[2]` `is_required` — 1.0 if slot has `required=True`, else 0.0 (0.0 for classes)
  - `[3]` `is_multivalued` — 1.0 if slot has `multivalued=True`, else 0.0 (0.0 for classes)
  - `[4]` `slot_usage_count_normalized` — count of classes that declare this slot in their `slots` list, divided by total class count; 0.0 for class nodes
- **Linear blend in `rank_suggestions`**: `final = (1 - structural_weight) * lex_sim + structural_weight * struct_sim`. Skipped (lexical-only) when either `A_struct` or `B_struct` is `None` or all-zero rows.
- **`structural_weight = 0.2` default** — 80% lexical, 20% structural. Configured via `rosetta.toml [suggest] structural_weight`.
- **New module `rosetta/core/features.py`** — `extract_structural_features_linkml` lives here, not in `embedding.py` (separate concerns: text extraction vs. structural feature extraction).
- **Node ID format**: same as `extract_text_inputs_linkml` — `"{schema_name}/{node_name}"` — so features and embeddings key off the same URIs.

## Decisions

- [review] `schema.name or "schema"` fallback: `features.py` must use `schema_name = schema.name or "schema"` — same guard as `extract_text_inputs_linkml` — to prevent silent key mismatches when schema has no name field.
- [review] pyright annotations in `features.py`: use `cast("dict[str, Any]", schema.classes)` and `# pyright: ignore[reportUnknownMemberType]` at every `schema.classes`/`schema.slots` access — same pattern as `embedding.py`.
- [review] `A_struct`/`B_struct` pre-declaration: declare `A_struct: np.ndarray | None = None` and `B_struct: np.ndarray | None = None` before the `if struct_dim > 0` block in `suggest.py` for basedpyright compatibility.
- [review] `mapping_justification` conditionality: emit `"semapv:CompositeMatching"` when structural blending is active (both arrays non-zero); `"semapv:LexicalMatching"` when fallback. Decided: fix conditionally (not deferred).
- [review] Fallback stderr warning: emit `click.echo("Warning: ...", err=True)` in `suggest.py` CLI when src embed has structural arrays but master does not (or vice versa). Decided: add the warning.
- [review] Mixed-vintage test: add `test_rank_suggestions_structural_partial_zeros` to `test_suggest.py` to cover the scenario where src embed has structural arrays and master embed does not.

## Deferred Ideas

- **Richer feature set** (`has_range_type`, `slot_domain_count`, slot `range` class depth): reserved for a future plan if structural blending proves impactful.
- **Per-feature weight tuning** (separate weights for each of the 5 features): out of scope; single `structural_weight` scalar is sufficient for Phase 13.
- **`--structural-weight` CLI flag on suggest**: deferred; `rosetta.toml` config is sufficient for Phase 13.
