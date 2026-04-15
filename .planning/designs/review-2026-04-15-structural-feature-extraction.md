# Plan Review — Phase 13-02: Structural Feature Extraction
Date: 2026-04-15

## Mode Selected
HOLD SCOPE — plan is tight and purposeful; deferred ideas section is correct.

## System Audit
- ARCHITECTURE.md, STRUCTURE.md present (no FLOWS.md/ERD.md)
- `EmbeddingVectors` currently has `label` + `lexical` only (no `structural`)
- `rank_suggestions` currently has no structural params
- `rosetta.toml [suggest]` currently empty

## Prior Context (claude-mem)
- SSSOM boost tests require non-collinear structural vectors (confirmed in test plan)
- `EmbeddingVectors.label` precedent from Plan 13-01 validates the `structural` field addition pattern

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | existing code confirmed; no drift           |
| Step 0               | HOLD — scope accepted                       |
| Section 1  (Scope)   | 0 issues — requirements complete           |
| Section 2  (Stories) | 1 issue: mapping_justification gap (fixed)  |
| Section 3  (UX)      | 1 issue: fallback warning (added)           |
| Section 4  (Risk)    | 1 issue: schema.name mismatch (CRITICAL)    |
| Section 5  (Deps)    | 0 issues — all deps already in pyproject    |
| Section 6  (Correct) | 1 issue: partial zeros scenario             |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 1 CRITICAL, 2 WARNING                       |
| Section 8  (Tests)   | 2 WARNING (underspec + missing test)        |
| Section 9  (Perf)    | 0 issues                                    |
| Section 10 (Security)| 1 WARNING (silent fallback → fixed)         |
+--------------------------------------------------------------------+
| PLAN.md updated      | 7 truths added, 1 test added to Task 5      |
| CONTEXT.md updated   | 6 decisions locked                          |
| Error/rescue registry| see below                                   |
| Failure modes        | see below                                   |
| Delight opportunities| N/A (HOLD mode)                             |
| Diagrams produced    | data flow (below)                           |
| Unresolved decisions | 0                                           |
+====================================================================+
```

## Error & Rescue Registry

| CODEPATH | FAILURE | RESCUED? | TEST? | USER SEES | LOGGED? |
|----------|---------|----------|-------|-----------|---------|
| `features.py`: schema.name=None | key mismatch → empty structural arrays | Y (via plan truth) | N (add to test_features.py) | silent empty struct | N |
| `suggest.py`: master embed has no structural | all-zero B_struct → fallback | Y (fallback logic) | Y (test_rank_suggestions_structural_partial_zeros) | stderr warning | N |
| `suggest.py`: both embed files missing structural | A_struct=None, B_struct=None | Y (lexical-only) | Y (test_rank_suggestions_structural_fallback) | no output change | N |
| `features.py`: empty schema (no classes/slots) | empty dict returned | Y (graceful) | Y (test_structural_features_empty_schema) | no structural in embed | N |

## Failure Modes Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES | LOGGED? |
|----------|-------------|----------|-------|-----------|---------|
| `embed.py` + `features.py` | schema.name=None → key mismatch | Y (plan truth added) | N | silent zero-struct | N |
| `suggest.py` blending | mixed-vintage master embed | Y (all-zero fallback) | Y (new test) | stderr warning | N |
| `rank_suggestions` | A_struct/B_struct dim mismatch | Y (cosine_matrix guard) | implicit | ValueError | N |
| `mapping_justification` | wrong value when structural active | Y (conditional logic) | partial | CompositeMatching | N |

## Data Flow Diagram

```
rosetta-embed
  schema.linkml.yaml
        │
        ▼
  extract_text_inputs_linkml(schema)
        │  → [(node_id, label, text), ...]
        │
  extract_structural_features_linkml(schema)
        │  → {node_id: [f0,f1,f2,f3,f4]}
        │
  EmbeddingModel.encode(texts)
        │  → [[float×1024], ...]
        │
  EmbeddingReport{node_id: EmbeddingVectors(label, lexical, structural)}
        │
        ▼
  .embed.json

rosetta-suggest
  src.embed.json + master.embed.json
        │
  EmbeddingReport.model_validate(...)
        │  → src_report, master_report
        │
  Build A (lexical n×1024), B (lexical m×1024)
  Build A_struct (n×5), B_struct (m×5) — or None if struct_dim=0
        │
  [WARN if one has structural, other doesn't]
        │
  rank_suggestions(src_uris, A, master_uris, B,
                   A_struct=A_struct, B_struct=B_struct,
                   structural_weight=w)
        │
  blend: final = (1-w)*cosine(A,B) + w*cosine(A_struct,B_struct)
  fallback: final = cosine(A,B) if either is None/all-zero
        │
  apply_sssom_feedback(...)  [if --approved-mappings]
        │
  SSSOMRow(mapping_justification = CompositeMatching|LexicalMatching)
        │
        ▼
  SSSOM TSV output
```

## What Already Exists
- `cosine_matrix` in `similarity.py` — reused for both lexical and structural similarity
- `EmbeddingVectors` Pydantic model — `structural: list[float] = []` field is a one-line addition
- `apply_sssom_feedback` already operates on candidate scores — unchanged by this plan
- `extract_text_inputs_linkml` pattern (cast + pyright ignores) — template for `features.py`

## Dream State Delta
After 13-02: structural blending is live and configurable, but `structural_weight=0.2` is a guess. Phase 14 (user review) will produce labelled approved/rejected mappings that could be used to tune `structural_weight` empirically.
