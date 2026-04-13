# Plan Review — Phase 10 rosetta-translate
**Date:** 2026-04-13
**Plan:** `.planning/phases/10-translate/10-01-PLAN.md`
**Mode:** HOLD (scope accepted, focus on bulletproofing)
**Gate:** PASS (after fixes applied directly to plan)

---

## Completion Summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD                                        |
| Research files       | None found                                  |
| Step 0               | HOLD confirmed; 5 CRITICAL, 6 WARNING found |
| Section 1  (Scope)   | 3 issues — embed.py fallback gap, EN== bug  |
| Section 2  (AC)      | 1 CRITICAL — test count 6 vs 10             |
| Section 3  (UX)      | 1 WARNING — positional args break convention|
| Section 4  (Risk)    | 1 WARNING — deepl v2; batch size note       |
| Section 5  (Deps)    | 1 WARNING — deepl>=1.18 needed <2 bound     |
| Section 6  (Correct) | 2 CRITICAL — import E401, == not startswith |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 5 issues — passthrough divergence, annots   |
| Section 8  (Code Ql) | 3 lint issues fixed in plan code blocks     |
| Section 9  (Tests)   | 1 CRITICAL — 4 missing tests, wrong gate    |
| Section 10 (Perf)    | OK — single-run, in-memory, acceptable      |
+--------------------------------------------------------------------+
| PLAN.md updated      | 8 truths added, 2 artifacts added, Task 6   |
| CONTEXT.md updated   | 4 decisions added                           |
| Error/rescue registry| 4 methods mapped, 0 CRITICAL GAPS remaining |
| Failure modes        | 5 total, 0 CRITICAL GAPS remaining          |
| Diagrams produced    | 1 (data flow)                               |
| Unresolved decisions | 0                                           |
+====================================================================+
```

---

## Critical Findings (all fixed in plan)

| # | Severity | Finding | Fix Applied |
|---|----------|---------|-------------|
| 1 | CRITICAL | `== "EN"` in both code blocks contradicts `startswith('EN')` truth — EN-US/EN-GB call DeepL and fail key check | Both blocks updated to `.upper().startswith("EN")` |
| 2 | CRITICAL | `import os, sys` on one line — ruff E401 kills CI on first commit | Split to separate lines |
| 3 | CRITICAL | `import os` + empty `TYPE_CHECKING` block unused — ruff F401 | Removed from translation.py block |
| 4 | CRITICAL | `cli()` has no type annotations — basedpyright strict fails | Full annotations added |
| 5 | CRITICAL | Task 4 "Done when" says 6 tests; truths require 10 — executor stops at 6 | Task 4 expanded to 10 named tests |

## Warning Findings (all fixed in plan)

| # | Severity | Finding | Fix Applied |
|---|----------|---------|-------------|
| 6 | WARNING | `embed.py:cli()` has `or "LaBSE"` fallback not covered by any task | Task 6 added |
| 7 | WARNING | `embed.py` docstring + `--model` help text still say LaBSE | Task 6 covers both |
| 8 | WARNING | Positional args break `--input/-i --output/-o` convention | Switched to named options |
| 9 | WARNING | `deepl>=1.18` no upper bound — v2 renames Translator + DeepLException | Changed to `deepl>=1.18,<2` |
| 10 | WARNING | `assert isinstance(results, list)` missing before zip — basedpyright strict | Added with ValueError guard |
| 11 | WARNING | No EN-US/EN-GB passthrough test — startswith not locked by any test | `test_translate_passthrough_source_lang_en_us` added |

---

## Error & Rescue Map

| CODEPATH | ERROR TYPE | RESCUED? | TEST? | USER SEES | LOGGED? |
|----------|------------|----------|-------|-----------|---------|
| translate_labels — translate_text | deepl.DeepLException | Y (CLI except) | Y (test_translate_api_error_exits_1) | stderr + exit 1 | stderr |
| translate_labels — result count mismatch | ValueError | Y (CLI except) | partial | stderr + exit 1 | stderr |
| translate CLI — DEEPL_API_KEY missing | early exit(1) | Y | Y (test_translate_missing_api_key_exits_1) | "DEEPL_API_KEY" message | stderr |
| translate CLI — idempotency guard | warning + exit 0 | Y | Y (test_translate_already_translated_skips) | warning on stderr | stderr |

---

## Data Flow Diagram

```
                    ┌─────────────────────────────────┐
                    │        rosetta-translate         │
                    └─────────────────────────────────┘
                                    │
              ┌────────────────────────────────────────┐
              │          CLI (translate.py)             │
              │  --input/-i  --output/-o  --source-lang │
              └────────────┬───────────────────────────┘
                           │
              ┌────────────▼───────────────────────────┐
              │      load_graph(src) → rdflib.Graph     │
              └────────────┬───────────────────────────┘
                           │
              ┌────────────▼───────────────────────────┐
              │       translate_labels(g, lang, key)    │
              ├────────────────────────────────────────┤
              │  HAPPY: lang.upper().startswith("EN")  │──► g unchanged (passthrough)
              │  HAPPY: lang == "auto" or "DE"/"NO"/…  │
              │    ├─ idempotency check (rose:originalLabel exists?) ──► warn + exit 0
              │    ├─ collect (field_node, label_lit)   │
              │    ├─ deduplicate → unique_texts list   │
              │    ├─ deepl.Translator(api_key)         │
              │    ├─ translate_text(unique_texts, …)   │
              │    ├─ assert isinstance(results, list)  │
              │    ├─ assert len(results)==len(unique)  │──► ValueError → exit 1
              │    ├─ build translation_map             │
              │    └─ remove/add rdfs:label triples     │
              │       add rose:originalLabel triples    │
              │  SHADOW 1: no rose:Field nodes → early return
              │  SHADOW 2: rose:originalLabel exists → warn + exit 0
              │  SHADOW 3: DeepLException → CLI except → exit 1
              └────────────┬───────────────────────────┘
                           │
              ┌────────────▼───────────────────────────┐
              │   save_graph(g, fh) → Turtle output     │
              └─────────────────────────────────────────┘
```

---

## What Already Exists

- `open_input`/`open_output` in `rosetta/core/io.py` — full stdin/file abstraction
- `load_graph`/`save_graph` in `rosetta/core/rdf_utils.py` — Turtle round-trip
- `get_config_value`/`load_config` in `rosetta/core/config.py` — 3-tier config precedence
- `bind_namespaces` + `ROSE_NS` in `rosetta/core/rdf_utils.py`
- `_e5_passage_prefix` logic already in `embedding.py` — E5 prefixes handled automatically

## Dream State Delta

After this phase: pipeline uniform across all national schemas. E5-large-v2 replaces LaBSE in config, code, CLI, and README. Translation audit trail in `rose:originalLabel`. All major failure modes observable.

Remaining gaps (explicitly deferred): no persistent translation cache (D6); no `--format` option.
