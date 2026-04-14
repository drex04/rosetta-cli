# Testing Patterns

**Analysis Date:** 2026-04-14

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
**Naming:** `test_<module>.py` (e.g., `test_lint.py`, `test_suggest.py`, `test_embed.py`)
**Stub tests:** Put `test_<tool>_stub_exits_1` in the tool's own test file — not in an unrelated file.

## Test Structure
**Pattern:** Plain pytest functions with descriptive names — `test_submit_creates_pending`, `test_cosine_matrix_orthogonal`
**Return types:** All test functions annotated `-> None`
**Assertions:** Direct `assert` statements; use `pytest.raises(ValueError, match="pattern")` for error paths
**Sections:** Group related tests with comment banners (`# --- Section ---`)

## Fixtures
**Shared fixtures:** `rosetta/tests/conftest.py` — `tmp_graph` (rdflib Graph), `sample_ttl` (Turtle file Path), `config_dir` (tmp dir with rosetta.toml)
**Local fixtures:** Defined in test file when module-scoped (e.g., `scope="module"` for expensive QUDT graph loads)
**tmp_path:** Use pytest's built-in `tmp_path: Path` for CLI tests that write output files
**Embedding fixtures:** Module-level dicts (`SOURCE_EMB`, `MASTER_EMB`) written to `tmp_path` via `@pytest.fixture`

## Mocking
**Framework:** `monkeypatch` (pytest built-in) for module-level replacements
**SentenceTransformer pattern:**
```python
class _FakeModel:
    def encode(self, texts): return np.zeros((len(texts), 4), dtype=np.float32)

monkeypatch.setattr(sentence_transformers, "SentenceTransformer", lambda name: _FakeModel())
```

## CLI Testing
**Pattern:** `from click.testing import CliRunner` — invoke CLI in-process
```python
runner = CliRunner()
result = runner.invoke(cli, ["--input", str(path)])
assert result.exit_code == 0, result.output
```
**Error detail:** `err_detail = result.output + (str(result.exception) if result.exception else "")` — use as assert message
**JSON output:** Parse with `json.loads(result.output)` then assert fields
**RDF output:** Parse with `Graph().parse(data=result.output, format="turtle")` then query
**SSSOM TSV output:** Assert `"subject_id" in result.output`, `"\t" in result.output`, `result.output.lstrip().startswith("#")`; parse data rows by filtering out lines starting with `#` or `subject_id`
**File output:** Pass `--output str(tmp_path / "out.sssom.tsv")`; assert `out_file.exists()` and `"subject_id" in out_file.read_text()`

## LinkML Test Fixtures
**Builder pattern:** Use a `_make_schema()` helper that returns `SchemaDefinition`:
```python
def _make_schema(classes=None, slots=None, name="test_schema") -> SchemaDefinition:
    schema = SchemaDefinition(id=f"https://example.org/{name}", name=name)
    # populate schema.classes / schema.slots via ClassDefinition / SlotDefinition
    return schema
```
**SSSOM fixture:** Write `.sssom.tsv` to `tmp_path` with `curie_map` comment block + header + tab-delimited rows.

## Slow Tests
**Marker:** `@pytest.mark.slow` for model loading
**Deselect:** `uv run pytest -m "not slow"`

## Test Data Files
**Location:** `rosetta/tests/fixtures/`
**Contents:** `nor_radar.csv`, `deu_patriot.json`, `usa_c2.yaml` — synthetic field schemas
**Inline data:** Turtle/TOML/SSSOM strings constructed inline; use `tmp_path` to write them

## Coverage
**Requirements:** No enforced threshold. `pytest-cov>=4.1` available but not required in CI.

## Type Annotations in Tests
**Policy:** Annotate fixture return types and non-obvious variables (basic pyright mode).
**Suppression:** Use `# pyright: ignore[reportArgumentType]` — not `# type: ignore[arg-type]`.
**rdflib SPARQL:** `# pyright: ignore[reportAttributeAccessIssue]` at every row attribute access.

---
*Testing analysis: 2026-04-14*
