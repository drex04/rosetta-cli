---
phase: 1
plan: 1
title: "Project skeleton, config loader, and RDF utilities"
status: completed
commit: c5ea044
wave_start_sha: 2d7c55fd8ac0208314c8bf10b30c37dc1b7debf1
test_metrics:
  total: 12
  passed: 12
  failed: 0
  spec_tests_count: 0
---

# Plan 01 Summary: Project Skeleton, Config Loader, and RDF Utilities

## What Was Built

Phase 1 establishes the full project scaffold for rosetta-cli — a composable CLI toolkit for semantic mapping between NATO defense schemas.

### Task 1: pyproject.toml + package structure
- `pyproject.toml` with all 8 `[project.scripts]` entrypoints, rdflib/click/pyyaml deps, hatchling build
- Package directories: `rosetta/cli/`, `rosetta/core/`, `rosetta/policies/`, `rosetta/store/`, `rosetta/tests/`
- `rosetta/__init__.py` with `__version__ = "0.1.0"`
- All 8 CLI stub files created

### Task 2: rosetta.toml + config loader
- `rosetta.toml` with `[general]`, `[namespaces]`, `[embed]` sections
- `rosetta/core/config.py`: `load_config()` + `get_config_value()` with 3-tier precedence (file → env var → CLI)
- Error wrapping: `tomllib.TOMLDecodeError` → `ValueError` with human-readable message

### Task 3: RDF utilities + namespace management
- `rosetta/core/rdf_utils.py`: `ROSE_NS`, `ROSE_STATS_NS`, `bind_namespaces()`, `load_graph()`, `save_graph()`, `query_graph()`
- Bound prefixes: `rose:`, `rose-stats:`, `qudt:`, `prov:`, `skos:`
- Error wrapping: rdflib parse exceptions → clear `ValueError`

### Task 4: I/O helpers + Click entrypoints
- `rosetta/core/io.py`: `open_input()` + `open_output()` context managers (stdin/stdout safe)
- `rosetta/cli/ingest.py`: full Click command with `--input/-i`, `--output/-o`, `--format/-f`, `--nation/-n`, `--config/-c`
- All 7 other CLI stubs updated with `--config/-c` short option
- `rosetta/tests/conftest.py`: `tmp_graph`, `sample_ttl`, `config_dir` fixtures

### Task 5: Integration verification
- All 8 entrypoints respond to `--help` ✓
- `rosetta.toml` loads from CWD ✓
- `rose:` prefix appears in serialized Turtle output ✓
- All 12 tests passing ✓

### Task 6: Synthetic test fixtures (REQ-26)
- `store/master-ontology/master.ttl`: 3 concepts (AirTrack, RadarReturn, EngagementZone), 20 `rose:Attribute` instances with QUDT units
- `rosetta/tests/fixtures/nor_radar.csv`: 7 rows Norwegian radar data
- `rosetta/tests/fixtures/deu_patriot.json`: German Patriot JSON Schema (draft-07)
- `rosetta/tests/fixtures/usa_c2.yaml`: US C2 OpenAPI 3.0.3 fragment
- `store/national-schemas/` and `store/accredited-mappings/` directory scaffolding

## Test Results

```
12 passed in 0.18s
- test_config.py: 5/5 (load, CLI override, env override, missing, malformed TOML)
- test_io.py: 3/3 (file input, stdin passthrough, stdout passthrough)
- test_rdf_utils.py: 4/4 (round-trip, bind_namespaces, query_graph, invalid RDF error)
```

## Must-Have Acceptance Criteria

| Truth | Status |
|-------|--------|
| `uv run rosetta-ingest --help` prints Click help | ✓ |
| All 8 entrypoints respond to `--help` | ✓ |
| `rosetta-ingest --help` includes `--config`, `--input`, `--output`, `--format` | ✓ |
| `uv run pytest` discovers and passes at least one test | ✓ (12 tests) |
| `rosetta/core/config.py` loads rosetta.toml with 3-tier precedence | ✓ |
| `rosetta/core/rdf_utils.py` round-trips a Graph | ✓ |
| All rosetta-generated RDF uses `rose:` prefix | ✓ |
| `open_input('-')` reads from stdin without error | ✓ |
| Malformed TOML raises clear error | ✓ |
| Invalid RDF raises clear error | ✓ |

## Issues Encountered

None. All tasks completed cleanly on first attempt.

## Deferred Items

- Pre-commit hooks / linting config (already deferred in CONTEXT.md)
- CI config (deferred until code exists to test)
- QUDT unit URI `unit:M2` and `unit:HZ` in master.ttl — should confirm against live QUDT vocabulary when strict URI validation is added in a later phase
