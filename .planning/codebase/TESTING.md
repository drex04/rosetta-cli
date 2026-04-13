# Testing Patterns

**Analysis Date:** 2026-04-13

## Test Framework
**Runner:** pytest 9.0.3+ (from `pyproject.toml` dev dependencies)
**Config:** `.pytest.ini_options` in `pyproject.toml` (line 39); marker for `slow` tests available
**Run Commands:**
```bash
uv run pytest               # all tests
uv run pytest -k name      # filter by name
uv run pytest -m "not slow"  # exclude slow tests
```

## Test File Organization
**Location:** `rosetta/tests/` — one test file per core module
**Naming:** `test_<module>.py` (e.g., `test_lint.py`, `test_ingest.py`, `test_embed.py`)
**Fixtures:** Stored in `rosetta/tests/fixtures/` (CSV, JSON, YAML test data files)

## Test Structure
**Patterns:** Pure pytest with descriptive test names starting with `test_`; no BDD frameworks
**Fixtures:** `@pytest.fixture` for shared setup — module-scoped fixtures (e.g., `qudt_graph`) load once per file
**Parametrize:** Use `@pytest.mark.parametrize()` for multiple test cases (e.g., unit detection patterns in `test_ingest.py` line 84)

## Mocking
**Framework:** `unittest.mock` (standard library); `monkeypatch` (pytest built-in)
**Pattern:** Use `monkeypatch.setattr()` for module-level replacements (e.g., mocking `SentenceTransformer` in `test_embed.py` line 26)

## Fixtures and Factories
**Location:** `rosetta/tests/fixtures/` contains:
- `nor_radar.csv` — 11 fields with unit metadata
- `deu_patriot.json` — JSON schema with 9 fields
- `usa_c2.yaml` — OpenAPI spec with 9 fields

**Test data creation:** Inline TOML/TTL strings in test functions (see `test_lint.py` lines 117–201 for RDF test data)
**Temporary files:** Use `tmp_path` fixture for CLI tests that write output

## Coverage
**Requirements:** No coverage enforcement; `pytest-cov>=4.1` available but not enforced

## Test Types
**Unit:** Core logic tests (e.g., unit detection, QUDT dimension vectors) — see `test_lint.py` lines 32–105
**Integration:** CLI tests using `CliRunner` from click.testing; invoke CLI with temp files and assert exit codes + output (see `test_lint.py` lines 204–443)
**CLI tests:** Pattern: create temp fixtures, invoke with `runner.invoke(cli, args)`, parse JSON/Turtle output, assert exit code (0 for success, 1 for errors/blocks)

---
*Testing analysis: 2026-04-13*
