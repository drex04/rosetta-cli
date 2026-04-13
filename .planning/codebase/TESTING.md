# Testing Patterns

**Analysis Date:** 2026-04-13

## Test Framework
**Runner:** pytest 9.0.3+ (dev dependency in `pyproject.toml`)
**Run Commands:**
```bash
uv run pytest                # all tests
uv run pytest -m "not slow"  # fast tests (CI regression guard)
uv run pytest -k test_name   # filter by name
```

## Test File Organization
**Location:** `rosetta/tests/` — one file per tool/module
**Naming:** `test_<module>.py` (e.g., `test_lint.py`, `test_accredit.py`, `test_ingest.py`)
**Stub tests:** Put `test_<tool>_stub_exits_1` in the tool's own test file — not in an unrelated file.

## Test Structure
**Pattern:** Plain pytest functions with descriptive names — `test_submit_creates_pending`, `test_approve_wrong_state_raises`
**Return types:** All test functions annotated `-> None`
**Assertions:** Direct `assert` statements; use `pytest.raises(ValueError, match="pattern")` for error paths
**Sections:** Group related tests with comment banners (`# --- Section 1 ---`)

## Fixtures
**Shared fixtures:** `rosetta/tests/conftest.py` — `tmp_graph`, `sample_ttl`, `config_dir`
**Local fixtures:** Defined in test file when module-scoped (e.g., `qudt_graph` in `test_lint.py` loads QUDT once per module via `scope="module"`)
**tmp_path:** Use pytest's built-in `tmp_path: Path` for CLI tests that write output files

## Mocking
**Framework:** `monkeypatch` (pytest built-in) for module-level replacements
**Pattern:** `monkeypatch.setattr("rosetta.core.embedding.SentenceTransformer", MockTransformer)`

## CLI Testing
**Pattern:** `from click.testing import CliRunner` — invoke CLI in-process
```python
runner = CliRunner()
result = runner.invoke(cli, ["--input", str(path), "--nation", "NOR"])
assert result.exit_code == 0, result.output
```
**JSON output:** Parse with `json.loads(result.output)` then assert fields
**RDF output:** Parse with `Graph().parse(data=result.output, format="turtle")` then query

## Fixtures and Test Data
**Location:** `rosetta/tests/fixtures/`
**Contents:**
- `nor_radar.csv` — 11 fields with unit metadata (CSV format)
- `deu_patriot.json` — 9-field JSON schema
- `usa_c2.yaml` — OpenAPI spec with 9 fields
**Inline data:** Turtle/TOML strings constructed inline for lint/validate tests; use `tmp_path` to write them

## Coverage
**Requirements:** No enforced threshold. `pytest-cov>=4.1` available but not required in CI.
**Markers:** `@pytest.mark.slow` for expensive tests (model loading); deselect with `-m "not slow"`.

## Type Annotations in Tests
**Policy:** Annotate fixture return types and non-obvious variables (basic pyright mode).
**Suppression:** Use `# pyright: ignore[reportArgumentType]` — not `# type: ignore[arg-type]`.
**rdflib SPARQL:** `# pyright: ignore[reportAttributeAccessIssue]` at every row attribute access.

---
*Testing analysis: 2026-04-13*
