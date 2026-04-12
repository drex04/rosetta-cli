# Plan 03-01 Summary: rosetta-embed

## Status: Complete

- **Commit:** 7f0dea1
- **Date:** 2026-04-12
- **Tests:** 40/40 passing (8 new, 1 slow skipped by default)

## What Was Built

| File | Description |
|------|-------------|
| `rosetta/core/embedding.py` | `extract_text_inputs(g)` + `EmbeddingModel` class |
| `rosetta/cli/embed.py` | Full `rosetta-embed` CLI (replaced stub) |
| `rosetta/tests/test_embed.py` | 8 tests (7 unit/CLI mocked, 1 slow real-model) |
| `pyproject.toml` | Added `sentence-transformers>=3.0`, `numpy>=1.26`, pytest markers |

## All Must-Haves Met

1. `rosetta-embed --input <ttl> --output <json>` exits 0, writes valid JSON with `"lexical"` vectors per field
2. Works for both national schemas (`rose:Field`) and master ontology (`rose:Attribute`)
3. Text template `"{parent} / {label} — {description}"` implemented correctly
4. 3-tier config precedence via `get_config_value` for model and mode
5. Output parent dirs auto-created
6. All unit tests pass without downloading LaBSE (mocked)
7. All exceptions → clean stderr + exit 1
8. None-guard on OPTIONAL SPARQL vars prevents literal `"None"` in text inputs
9. JSON keys are plain strings (URIRef → str before `json.dumps()`)

## Quality Warnings

None.

## Issues Encountered

None.
