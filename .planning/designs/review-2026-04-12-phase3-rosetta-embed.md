# Plan Review — Phase 3 Plan 01: rosetta-embed
**Date:** 2026-04-12  
**Mode:** HOLD SCOPE  
**Gate:** PASS (with fixes applied)

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | 3 CRITICAL bugs found pre-implementation     |
| Step 0               | HOLD SCOPE — plan scope accepted            |
| Section 1  (Scope)   | OK — all 6 truths deliverable               |
| Section 2  (Errors)  | 3 error paths unmapped → CRITICAL GAPS      |
| Section 3  (UX)      | 1 WARNING — open_output inconsistency       |
| Section 4  (Risk)    | 1 WARNING — path-segment comment wrong      |
| Section 5  (Deps)    | OK — sentence-transformers>=3.0 correct     |
| Section 6  (Correct) | 2 CRITICAL bugs — None coercion + URIRef    |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 1 CRITICAL (open_output bypass fixed)       |
| Section 8  (Code Ql) | 1 CRITICAL — URIRef JSON serialization      |
| Section 9  (Tests)   | Diagram produced; 3 CRITICAL gaps patched   |
| Section 10 (Perf)    | OK — batch encoding + model download noted  |
+--------------------------------------------------------------------+
| PLAN.md updated      | 3 truths added, CLI outline patched (5 edits)|
| CONTEXT.md updated   | 5 decisions locked, 2 items deferred        |
| Error/rescue registry| 3 methods, 3 CRITICAL GAPS → PLAN.md        |
| Failure modes        | 6 total, 3 CRITICAL GAPS → PLAN.md          |
| Delight opportunities| N/A (HOLD SCOPE)                            |
| Diagrams produced    | Test coverage diagram (below)               |
| Unresolved decisions | 0                                           |
+====================================================================+
```

---

## Critical Bugs Fixed in PLAN.md

### Bug 1: No try/except in CLI outline
**Problem:** Plan said "exit 1 on any exception" in prose but showed no `try/except` in the code outline. Implementers follow the outline, not the prose.  
**Fix:** Added explicit `try/except Exception as e: click.echo(str(e), err=True); sys.exit(1)` wrapping the entire CLI body. Mirrors `ingest.py:31-40`.

### Bug 2: OPTIONAL SPARQL → `"None"` string in embeddings
**Problem:** `query_graph` returns Python `None` for unbound OPTIONAL vars (`conceptLabel`, `comment`). Python f-strings render `None` as the literal string `"None"`. Text inputs like `"None / AttrLabel — None"` silently corrupt embedding quality and cause `test_extract_master_no_concept` to fail.  
**Fix:** Added explicit None-guard in Task 2 spec:
```python
concept_label = str(row["conceptLabel"]) if row.get("conceptLabel") is not None else ""
comment       = str(row["comment"])       if row.get("comment")       is not None else ""
```

### Bug 3: URIRef keys → json.dumps() TypeError
**Problem:** `query_graph` returns `URIRef` objects for `?attr`/`?field`. Building `{uri: ...}` with `URIRef` keys then calling `json.dumps()` raises `TypeError: Object of type URIRef is not JSON serializable`.  
**Fix:** Changed result dict to `{str(uri): {"lexical": vec} for uri, vec in zip(uris, vectors)}`.

---

## Additional Fixes

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 4 | IMPORTANT | `Path.write_text` + `click.echo` diverges from `open_output` pattern | Use `mkdir` guard + `open_output()` for both branches |
| 5 | WARNING | "4th path segment" comment wrong — would mislead to nation code | Corrected to "3rd segment (index -2)" with explicit example |
| 6 | WARNING | `MASTER_TTL` in slow test breaks inside `isolated_filesystem()` | Added `Path(__file__).resolve().parent.parent.parent / ...` |

---

## Test Coverage Diagram

```
extract_text_inputs()
  ├── master path (rose:Attribute present)
  │   ├── with concept + comment         → test_extract_master_attributes ✓
  │   ├── no concept (None → "")         → test_extract_master_no_concept ✓
  │   └── no comment (concept present)   → WARNING: not explicitly tested
  └── national path (rose:Field)
      ├── normal fields                  → test_extract_national_fields ✓
      └── field with no label            → edge case, acceptable skip

EmbeddingModel
  ├── encode() shape                     → test_embedding_model_encode_shape ✓
  └── import/encode exceptions           → covered by CLI try/except test

CLI (embed.py)
  ├── national TTL → JSON file (mocked)  → test_embed_cli_national ✓
  ├── empty graph → exit 1              → test_embed_cli_empty_graph ✓
  ├── output dir auto-create            → test_embed_cli_output_creates_dirs ✓
  ├── stdout output                     → test_embed_cli_stdout ✓
  ├── master TTL → CLI (fast)           → DEFERRED (slow test covers it) ⚠
  ├── invalid Turtle → exit 1           → covered by try/except (no dedicated test) ⚠
  └── real model + master.ttl           → test_embed_cli_real_model_master_ttl [slow] ✓
```

---

## Data Flow (Happy + Shadow Paths)

```
INPUT (.ttl file or stdin)
  │
  ▼
open_input(input_path)
  ├── shadow: file not found    → load_graph raises ValueError → try/except → exit 1
  └── shadow: bad Turtle        → load_graph raises ValueError → try/except → exit 1
  │
  ▼
load_graph(src) → rdflib.Graph
  │
  ▼
extract_text_inputs(g) → list[tuple[str, str]]
  ├── shadow: no rose:Field or rose:Attribute → returns [] → "No embeddable..." → exit 1
  ├── master path: SPARQL OPTIONAL → None coercion → "" (not "None")
  └── national path: uri.split("/")[-2] → schema slug
  │
  ▼
EmbeddingModel(model_name).encode(texts) → list[list[float]]
  ├── shadow: package not installed → ImportError in __init__ → try/except → exit 1
  └── shadow: OOM / bad model     → Exception → try/except → exit 1
  │
  ▼
{str(uri): {"lexical": vec} for ...}  ← URIRef coerced to str
  │
  ▼
open_output(output_path)
  ├── file path: mkdir(parents=True) first, then write
  └── stdout: "-" → open_output yields sys.stdout
  │
  ▼
json.dumps(result, indent=2) → fh.write()
  └── shadow: PermissionError / disk full → try/except → exit 1
```

---

## What Already Exists

- `rosetta/core/rdf_utils.py` — `query_graph`, `load_graph`, `bind_namespaces` — all needed by `extract_text_inputs`
- `rosetta/core/io.py` — `open_input`, `open_output` — embed uses both
- `rosetta/core/config.py` — `get_config_value` with 3-tier precedence — matches plan spec exactly
- `store/master-ontology/master.ttl` — real fixture for slow test
- `rosetta/cli/embed.py` — stub with `--config` option — will be replaced

## Dream State Delta

After Phase 3 Plan 01, rosetta-embed will produce single-mode (lexical-only) embedding JSON. Future plans (Plan 02+) extend to:
- `lexical+stats` mode (combine embedding with Phase 2 computed stats)
- `rosetta-suggest` similarity matching
- Batch encoding with progress bar for large ontologies
