# Plan Review — Phase 18 (all three plans)

**Date:** 2026-04-18
**Reviewer:** Claude Code (fh:plan-review skill, 2 parallel fh:code-reviewer agents)
**Plans reviewed:** 18-01, 18-02, 18-03
**Mode selected:** HOLD SCOPE

## Completion summary

```
+====================================================================+
|            PLAN REVIEW — COMPLETION SUMMARY                        |
+====================================================================+
| Mode selected        | HOLD SCOPE                                  |
| System Audit         | 3 plans, ~22 tasks, ~36 tests, 0 prod code  |
| Step 0               | HOLD — scope already well-calibrated        |
| Section 1  (Scope)   | 1 WARNING, 2 OK                             |
| Section 2  (Stories) | 3 WARNINGs (two blockers)                   |
| Section 3  (UX)      | 2 WARNINGs, 2 OK                            |
| Section 4  (Risk)    | 1 CRITICAL GAP (LaBSE mock), 1 WARN, 1 OK   |
| Section 5  (Deps)    | 1 CRITICAL GAP (rule codes), 1 WARN, 1 OK   |
| Section 6  (Correct) | 1 CRITICAL GAP (summary.errors), 3 WARN     |
+--------------------------------------------------------------------+
| Section 7  (Arch)    | 2 WARNINGs, 2 OK                            |
| Section 8  (Tests)   | 2 CRITICAL GAPS, 7 WARNs — most actionable  |
| Section 9  (Perf)    | 2 WARNINGs, 2 OK                            |
| Section 10 (Sec/Err) | 4 WARNINGs, 2 OK                            |
+--------------------------------------------------------------------+
| PLAN.md updates      | 10 [review] truths added across 3 plans     |
| CONTEXT.md updates   | 6 [review] decisions locked (D-18-09..14)   |
| Deferred items       | 5 (rdfs/tsv/query-json/skip-mask/live-API)  |
| Delight opportunities| N/A (HOLD mode, not EXPANSION)              |
| Unresolved decisions | 0 — 2 asked, both answered "Recommended"    |
+====================================================================+
```

## Critical gaps caught (5)

| # | Issue | Location | Fix class |
|---|-------|----------|-----------|
| C1 | `LintReport.summary.errors` — field doesn't exist | 18-02 Truth 6, Task 4 | Mechanical (→ `summary.block`) |
| C2 | Lint rule `unit_incompatible` — actual code is `unit_dimension_mismatch` | 18-02 Task 3 item 3 | Mechanical |
| C3 | Lint rule `missing_required` — no such code in `rosetta/core/lint.py` | 18-03 Task 3 item 2 | Test removed; coverage redirected to `test_validate_pipeline.py` |
| C4 | `rosetta-accredit` zero positive-path integration tests | 18-02 artifact table | New test file added (`test_accredit_pipeline.py`, 3 tests) |
| C5 | LaBSE model-mock strategy unresolved | 18-02 Task 3 / risk section | Precondition added: grep `test_embed.py`, replicate mock |

## What already exists (partial solutions the plan leverages)

- **`click.testing.CliRunner`** — the repo uses this extensively. Pattern is proven.
- **`monkeypatch.setattr("deepl.Translator.translate_text", ...)`** — existing `test_translate.py` already mocks DeepL successfully. Plan generalizes this into a reusable `fake_deepl` fixture; no new technique required.
- **Pydantic models for CLI outputs** — `LintReport`, `SuggestionReport`, `EmbeddingReport` already exist. Plan reuses them for structured assertions.
- **`@pytest.mark.slow`** — marker already declared. Phase 18 only adds two new markers (`integration`, `e2e`).
- **`test_yarrrml_run_e2e.py`** — already a 219-line e2e template. New tests follow its shape (CliRunner, tmp_path, patch-then-invoke).
- **9 existing fixtures** — NOR CSV/LinkML, DEU JSON, USA OpenAPI, master CoP, SSSOM audit log. Migrated into `fixtures/nations/` without content changes.

## Dream state delta (HOLD mode — no expansion taken)

Relative to a 12-month ideal:

- ✅ Full per-tool integration coverage
- ✅ Adversarial coverage per category (6 categories × multiple tests)
- ✅ Layered marker scheme for selective execution
- ✅ Zero-cost DeepL mocking
- ✅ Subprocess smoke for packaging
- ⏸️ Property-based fuzzing (Hypothesis) — deferred
- ⏸️ Mutation testing — deferred
- ⏸️ Coverage ratcheting gates — deferred
- ⏸️ `rdfs`/`tsv` ingest-format coverage — deferred (documented gap)
- ⏸️ `provenance query --format json` coverage — deferred (documented gap)

The plan lands the fat part of the value curve. Deferred items are explicitly flagged in `CONTEXT.md` "Deferred during review" so a future phase can pick them up with context.

## Test coverage diagram (from Section 8)

```
Tool                    | Positive (18-02) | Adversarial (18-03) | Smoke (18-02 T5)
------------------------|-----------------|---------------------|------------------
rosetta-ingest          |                 |                     |
  json-schema           | nested ✓        | malformed JSON ✓    | entry-point ✓
  xsd                   | complex XSD ✓   | truncated XSD ✓     | -
  csv                   | edge-case CSV ✓ | wrong-enc CSV ✓     | -
  rdfs                  | DEFERRED        | DEFERRED            | -
  tsv                   | DEFERRED        | DEFERRED            | -
rosetta-embed           | nested JSON ✓   | MISSING (accepted)  | -
rosetta-suggest         | inheritance ✓   | type-divergence ✓   | -
rosetta-lint            | suggest→lint ✓  | datatype_mismatch ✓ | -
rosetta-validate        | SHACL shape ✓   | MISSING (accepted)  | -
rosetta-provenance      |                 |                     |
  stamp                 | stamp+query ✓   | MISSING (accepted)  | -
  query --format json   | DEFERRED        | -                   | -
rosetta-accredit        |                 |                     |
  ingest                | ✓ [review]      | dup/colcount/derank | -
  approve               | ✓ [review]      | -                   | -
  revoke                | ✓ [review]      | -                   | -
  status                | ✓ [review]      | -                   | -
rosetta-translate       | DE/FR/batch/mix | auth/quota/transient| -
rosetta-yarrrml-gen     | XSD→JSON-LD ✓   | dateTime typo,      | entry-point ✓
                        |                 | no --data, etc.     |
```

## Failure modes registry (from Section 10)

| Codepath | Failure Mode | Rescued? | Test? | User Sees | Logged? |
|----------|--------------|----------|-------|-----------|---------|
| `ingest` JSON parse | `JSONDecodeError` | exit 1 | 18-03 Task 2 | stderr phrase | stderr |
| `ingest` XSD parse | `xml.etree.ParseError` / `lxml.XMLSyntaxError` | exit 1 | 18-03 Task 2 | stderr phrase | stderr |
| `ingest` CSV encoding | `UnicodeDecodeError` | exit 1 (precondition-gated) | 18-03 Task 2 | stderr phrase | stderr |
| `ingest` missing file | Click `UsageError` → exit 2 | exit 2 | 18-03 Task 5 | "does not exist" | stderr |
| `accredit ingest` dup MMC | `ValueError` from `check_ingest_row` → errors list | exit 1 (precondition-gated) | 18-03 Task 4 | stderr phrase | stderr |
| `accredit ingest` phantom derank | `check_ingest_row` or other path (precondition) | exit 1 (precondition-gated) | 18-03 Task 4 | "cannot derank" | stderr |
| `translate` auth fail | `AuthorizationException` | exit 1 | 18-03 Task 8 | "authentication..." | stderr |
| `translate` quota | `QuotaExceededException` | exit 1 | 18-03 Task 8 | "quota..." | stderr |
| `translate` transient | `DeepLException` | exit 1 | 18-03 Task 8 | "DeepL API error" | stderr |
| `translate` missing key, non-EN | pre-translator guard | exit 1 | 18-03 Task 8 | "API key required" | stderr |
| `yarrrml-gen --run` no `--data` | manual guard | exit 1 | 18-03 Task 5 | "--run requires --data" | stderr |
| `yarrrml-gen` `dateTime` typo | schema-automator / ContextGenerator | exit 1 | 18-03 Task 7 | "dateTime" phrase | stderr |

All rows have RESCUED=Y, TEST=Y, USER-SEES=visible. No silent-failure gaps remain.

## Exception enumeration

Named explicitly in plans after review: `JSONDecodeError`, `xml.etree.ParseError`/`lxml.XMLSyntaxError`, `UnicodeDecodeError`, `deepl.exceptions.AuthorizationException`/`QuotaExceededException`/`DeepLException`, `ValueError` (check_ingest_row), Click `UsageError` (exit 2 context).

Preconditions added to gate the following before test authoring: exact translate stderr phrases, `owl:differentFrom` handling location, current lint rule-code table, `accredit ingest` exit-code path for errors-list non-empty.

## Final gate recommendations

- **18-01: PASS** ✅ — Infrastructure plan is concrete and now carries an explicit atomic-commit rule for Tasks 2–5 plus the `fake_deepl` signature cleanup.
- **18-02: PASS** ✅ — C1 mechanical fixes applied; C4 closed (test_accredit_pipeline.py added); C5 precondition added. Three new `[review]` truths lock the fixes.
- **18-03: PASS** ✅ — C3 removed (missing_required test gone); BOM test pinned; preconditions added for translate stderr, `owl:differentFrom`, accredit exit-code path. Five new `[review]` truths lock the fixes.

## Next step

`/fh:build 18-01` — plans are ready for execution. Build in order: 18-01 → 18-02 → 18-03.
