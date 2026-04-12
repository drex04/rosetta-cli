---
phase: 3
plan: 2
title: rosetta-suggest — cosine similarity ranked mapping suggestions
status: complete
commit: 5acccf0
tests_passing: 63
tests_new: 19
completed: 2026-04-12
test_metrics:
  total: 63
  new: 19
  deselected: 1
  spec_tests_count: 19
---

# Plan 03-02 Summary

## What Was Built

- `rosetta/core/similarity.py` — `cosine_matrix()` (pure numpy, zero-norm safe, dimension guard) + `rank_suggestions()` (pre-filter anomaly, 1-based rank, scores to 6dp)
- `rosetta/cli/suggest.py` — Full `rosetta-suggest` CLI (source/master JSON, 3-tier config, clean error handling)
- `rosetta/tests/test_suggest.py` — 19 tests: 5 unit (cosine math) + 7 unit (rank logic) + 7 CLI tests
- `rosetta.toml` — `[suggest]` section added (`top_k=5`, `min_score=0.0`, `anomaly_threshold=0.3`)

## Verification

- `uv run pytest -m "not slow" -q`: **63 passed, 1 deselected**
- `uv run rosetta-suggest --help`: all 7 options displayed, exit 0

## Deviations

- `CliRunner(mix_stderr=False)` not supported in installed Click version — error-path CLI tests use default `CliRunner()` and check `result.output` (combined stdout+stderr). All error assertions still pass correctly.
- `rosetta-suggest` entrypoint was already present in `pyproject.toml` from Phase 3 Plan 01 scaffolding — Task 4 only needed to add `rosetta.toml [suggest]` section.

## Issues Encountered

None.

## Quality Warnings

None.
