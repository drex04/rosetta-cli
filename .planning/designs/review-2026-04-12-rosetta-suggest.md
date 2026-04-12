# Plan Review — rosetta-suggest (03-02)
**Date:** 2026-04-12 | **Mode:** HOLD SCOPE

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | Clean — no DB, no external APIs, numpy      |
|                      | already a dep, no new packages needed        |
| Step 0               | HOLD SCOPE confirmed by user                |
| Section 1  (Scope)   | OK — maps cleanly to ROADMAP REQ-04–08     |
| Section 2  (Accept.) | 4 issues — 2 CRITICAL, 2 WARNING; resolved |
| Section 3  (UX)      | 1 WARNING (no short aliases) — deferred    |
| Section 4  (Risk)    | 1 WARNING (dim mismatch) — now CRITICAL,   |
|                      | guarded in cosine_matrix                    |
| Section 5  (Integr.) | 1 CRITICAL (lexical key) — guarded in CLI  |
| Section 6  (Correct.)| 1 CRITICAL (top_k>master) — documented     |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 1 CRITICAL (API design) — resolved; pure   |
|                      | math signature for rank_suggestions         |
| Section 8  (Code Ql) | 1 WARNING (open_input vs read_text)        |
|                      | — dismissed (file-only is locked decision)  |
| Section 9  (Tests)   | 6 missing tests added (19 total)           |
| Section 10 (Perf)    | OK — 100×500 matrix = 200 KB, <10 ms      |
+--------------------------------------------------------------------+
| PLAN.md updated      | 4 truths added ([review] 7-10)              |
|                      | 6 new tests added to Task 3 (19 total)      |
| CONTEXT.md updated   | 6 review decisions locked (21-26)           |
|                      | 3 items deferred                            |
| Error/rescue registry| 9 paths mapped, 2 CRITICAL GAPS → fixed    |
| Failure modes        | dim mismatch, missing lexical key, top_k>N |
|                      | — all rescued and tested                    |
| Diagrams produced    | Test coverage diagram (below)              |
| Unresolved decisions | None                                        |
+====================================================================+
```

## Test Coverage Diagram

```
cosine_matrix(A, B)
  ├── shape (n,m) correctness              [test_cosine_matrix_shape] ✓
  ├── identical vectors → 1.0             [test_cosine_matrix_identical] ✓
  ├── orthogonal vectors → 0.0            [test_cosine_matrix_orthogonal] ✓
  ├── zero-norm row (div-by-zero guard)   [test_cosine_matrix_zero_vector] ✓
  └── mismatched dims → ValueError        [test_cosine_matrix_dim_mismatch] ✓

rank_suggestions(src_uris, A, master_uris, B, ...)
  ├── output sorted descending, rank 1   [test_rank_suggestions_order] ✓
  ├── top_k truncation                   [test_rank_suggestions_top_k] ✓
  ├── top_k > master → return all        [test_rank_suggestions_top_k_exceeds_master] ✓
  ├── min_score filter                   [test_rank_suggestions_min_score] ✓
  ├── anomaly=true (max < threshold)     [test_rank_suggestions_anomaly_true] ✓
  ├── anomaly=false (max >= threshold)   [test_rank_suggestions_anomaly_false] ✓
  └── anomaly pre-filter (good match     [test_rank_suggestions_anomaly_pre_filter] ✓
      filtered by min_score → not anom.)

CLI suggest.py
  ├── file → file, exit 0, valid JSON    [test_suggest_cli_basic] ✓
  ├── stdout (no --output)               [test_suggest_cli_stdout] ✓
  ├── empty source dict → exit 1 + path [test_suggest_cli_empty_source] ✓
  ├── empty master dict → exit 1 + path [test_suggest_cli_empty_master] ✓
  ├── missing "lexical" key → exit 1    [test_suggest_cli_missing_lexical_key] ✓
  ├── --top-k 1 → 1 result per field    [test_suggest_cli_top_k] ✓
  └── --top-k overrides rosetta.toml    [test_suggest_cli_config_precedence] ✓
```

## Error/Rescue Registry

```
CODEPATH                       | FAILURE MODE               | RESCUED? | TEST? | USER SEES?                  | LOGGED?
-------------------------------|----------------------------|----------|-------|-----------------------------|--------
json.loads(source)             | malformed JSON             | Y (try)  | N     | str(e) on stderr            | N
json.loads(master)             | malformed JSON             | Y (try)  | N     | str(e) on stderr            | N
empty source dict check        | src == {}                  | Y        | Y     | "No embeddings in source"   | N
empty master dict check        | master == {}               | Y        | Y     | "No embeddings in master"   | N
"lexical" key loop guard       | KeyError on entry          | Y        | Y     | "Missing 'lexical' for URI" | N
np.array(list[float])          | non-numeric in vector      | Y (try)  | N     | str(e) on stderr            | N
cosine_matrix dim check        | A.shape[1] != B.shape[1]   | Y        | Y     | descriptive ValueError      | N
rank_suggestions top_k > N     | slice beyond master count  | Y        | Y     | truncated to master size    | N
open_output dir missing        | FileNotFoundError          | Y (try)  | N     | str(e) on stderr            | N
```

## Key Decisions Made

| # | Decision | Why |
|---|----------|-----|
| 21 | rank_suggestions takes arrays + URI lists | Keeps similarity.py as pure math; CLI owns parsing |
| 22 | Anomaly computed from raw pre-filter scores | Semantically correct: anomaly = no good match exists, not "filtered out" |
| 23 | Dimension mismatch guard in cosine_matrix | Prevents cryptic numpy traceback; gives actionable error |
| 24 | "lexical" key guard in CLI loop | Descriptive error per offending URI before array construction |
| 25 | Separate empty-file messages | User needs to know which file is the problem |
| 26 | top_k > master → return all | Documented natural behaviour; tested |

## What Already Exists

- `open_output(path)` in `rosetta/core/io.py` — handles file + stdout uniformly
- `get_config_value(cfg, section, key)` 3-tier precedence — same pattern as embed.py
- `load_config(path)` with tolerated missing file — same pattern
- Mock pattern for SentenceTransformer in `test_embed.py` — not needed here (no model)
- numpy already in `[project.dependencies]` — no new packages

## Dream State Delta

After this plan: source fields → cosine similarity → ranked suggestions with anomaly flags.
Remaining for Phase 3: none (both embed + suggest complete).
Next: Phase 4 (rosetta-lint) — unit mismatch detection, QUDT comparison, FnML repo search.
