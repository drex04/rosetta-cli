# Testing Patterns

**Updated:** 2026-04-16 (phases 14–15)

## Test Framework

**Runner:** pytest 9.0+ (see `pyproject.toml` [dependency-groups.dev])

```bash
uv run pytest                           # all tests
uv run pytest -m "not slow"             # fast tests (CI regression guard)
uv run pytest -k test_name              # filter by name
```

**Marker:** `@pytest.mark.slow` for expensive tests (model loading, LLM embedding); deselect with `-m "not slow"`.

## File Organization

- **Location:** `rosetta/tests/test_<module>.py` — one file per tool/module.
- **Stub tests:** place `test_<tool>_stub_exits_1` in target tool's test file (updates in place when impl lands).

Test data: `rosetta/tests/fixtures/` (nor_radar.csv, deu_patriot.json, usa_c2.yaml).

## Test Structure

- Plain pytest functions, `-> None` annotation.
- Descriptive names: `test_<function>_<scenario>`.
- Comment banners for sections: `# --- Section ---`.

```python
def test_units_compatible_same_unit(qudt_graph) -> None:
    assert units_compatible("unit:M", "unit:M", qudt_graph) is True
```

Error testing:
```python
with pytest.raises(ValueError, match="Failed to parse RDF"):
    load_graph(bad_ttl)
```

## Fixtures

**Shared (`conftest.py`):**
- `tmp_graph() -> Graph` — fresh Graph with Rosetta namespaces
- `sample_ttl(tmp_path: Path) -> Path` — minimal .ttl file
- `tmp_rosetta_toml(tmp_path: Path) -> Path` — temp rosetta.toml with [accredit].log
- `config_dir(tmp_path: Path) -> Path` — temp dir with rosetta.toml

**Module-scoped** for expensive loads:
```python
@pytest.fixture(scope="module")
def qudt_graph():
    return load_qudt_graph()
```

**Built-in:** `tmp_path: Path` (tmp dir per test).

## CLI Testing

```python
from click.testing import CliRunner

runner = CliRunner()
result = runner.invoke(cli, ["--input", str(input_file), "--output", str(output_file)])
assert result.exit_code == 0, f"CLI failed: {result.output}"
assert output_file.exists()
```

**JSON output:** `json.loads(result.output)` to parse.
**SSSOM TSV:** assert `"subject_id" in result.output`, `"\t" in result.output`, comment-block prefix.

## Mocking

- **Module replacement:** pytest `monkeypatch` fixture.
- **SentenceTransformer:** `_FakeModel` pattern returning fixed-shape embeddings.

```python
class _FakeModel:
    def encode(self, texts):
        return np.zeros((len(texts), 4), dtype=np.float32)

monkeypatch.setattr("sentence_transformers.SentenceTransformer", lambda *a, **k: _FakeModel())
```

## LinkML Fixtures

Builder pattern:
```python
def _make_schema() -> SchemaDefinition:
    schema = SchemaDefinition(name="test_schema")
    schema.classes = {"Speed": ClassDefinition(name="Speed")}
    return schema
```

## SSSOM Fixtures

Write `.sssom.tsv` to `tmp_path` with **11-column header** + tab-delimited rows:

```python
def _make_sssom_tsv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "input.sssom.tsv"
    header = "# sssom_version: https://w3id.org/sssom/spec/0.15\n# mapping_set_id: test\n"
    cols = [
        "subject_id", "predicate_id", "object_id", "mapping_justification", "confidence",
        "subject_label", "object_label", "mapping_date", "record_id",
        "subject_datatype", "object_datatype"
    ]
    with path.open("w") as f:
        f.write(header)
        writer = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in cols})
    return path
```

## Type Annotations in Tests

- Annotate fixture return types: `def tmp_graph() -> Graph:`
- Annotate non-obvious variables: `rows: list[SSSOMRow] = load_log(path)`
- Use `# pyright: ignore[reportArgumentType]` (NOT `# type: ignore[arg-type]` — basedpyright ignores latter in tests).
- SPARQL row attr access: `# pyright: ignore[reportAttributeAccessIssue]` at every `.attribute`.

## Coverage

pytest-cov available; no enforced threshold. Run with `pytest --cov=rosetta`.

## Example: Test Accredit Integration

See `rosetta/tests/test_accredit_integration.py` — end-to-end audit-log pipeline with:
- SSSOM fixture write
- CLI invoke
- Log append + load
- Assertion on record_id, mapping_date stamps
