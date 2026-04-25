"""Integration tests for the custom FnO function mechanism (Phase 23-05).

Covers:
- FunctionLibrary.add_declarations() with a custom TTL
- _write_udf_file() concatenation of builtin + custom UDFs
- load_function_config() path validation
- Malformed TTL raises clean ValueError
- CLI-level tests for compile, transform, and ledger with custom functions
"""

from __future__ import annotations

import contextlib
import csv
from collections.abc import Iterator
from pathlib import Path

import pytest
import rdflib
from click.testing import CliRunner

from rosetta.core.config import load_function_config
from rosetta.core.function_library import FunctionLibrary
from rosetta.core.models import SSSOM_COLUMNS
from rosetta.core.rml_runner import _write_udf_file

_CUSTOM_FNO_TTL = """\
@prefix fno: <https://w3id.org/function/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex:  <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

ex:myCustomFunc
    a fno:Function ;
    fno:name "myCustom" ;
    fno:expects ( [ a fno:Parameter ; fno:predicate ex:input ; fno:type xsd:string ] ) ;
    fno:returns ( [ a fno:Output ; fno:predicate ex:output ; fno:type xsd:string ] ) .
"""

_CUSTOM_UDF_PY = """\
def my_custom_transform(value):
    return value.upper()
"""


@pytest.mark.integration
def test_custom_fno_declaration_loads_into_library(tmp_path: Path) -> None:
    """Custom FnO TTL adds function to library; builtins still present."""
    custom_path = tmp_path / "custom.fno.ttl"
    custom_path.write_text(_CUSTOM_FNO_TTL, encoding="utf-8")

    library = FunctionLibrary.load_builtins()
    library.add_declarations(custom_path)

    assert library.has_function("http://example.org/myCustomFunc"), (
        "Custom function should be present after add_declarations()"
    )
    assert library.has_function("grel:math_round"), (
        "Builtin grel:math_round should still be present"
    )


@pytest.mark.integration
def test_custom_udf_concatenated_in_write_udf_file(tmp_path: Path) -> None:
    """_write_udf_file concatenates builtin and custom UDF source."""
    custom_path = tmp_path / "custom_udf.py"
    custom_path.write_text(_CUSTOM_UDF_PY, encoding="utf-8")

    content = _write_udf_file(tmp_path, extra_udf_paths=[custom_path]).read_text(encoding="utf-8")

    assert "meter_to_foot" in content, "Builtin UDF content should be present"
    assert "my_custom_transform" in content, "Custom UDF content should be present"


@pytest.mark.integration
def test_load_function_config_missing_declaration_raises() -> None:
    """load_function_config raises ValueError when a declaration file is absent."""
    with pytest.raises(ValueError, match="not found"):
        load_function_config({"functions": {"declarations": ["nonexistent.ttl"]}})


@pytest.mark.integration
def test_load_function_config_missing_udf_raises() -> None:
    """load_function_config raises ValueError when a UDF file is absent."""
    with pytest.raises(ValueError, match="not found"):
        load_function_config({"functions": {"udfs": ["nonexistent_udf.py"]}})


@pytest.mark.integration
def test_load_function_config_empty_returns_empty_lists() -> None:
    """load_function_config({}) returns empty declaration and UDF lists."""
    result: dict[str, list[Path]] = load_function_config({})
    assert result == {"declarations": [], "udfs": []}


@pytest.mark.integration
def test_malformed_ttl_raises_clean_error(tmp_path: Path) -> None:
    """add_declarations() with invalid Turtle raises ValueError containing 'Failed to parse'."""
    bad_path = tmp_path / "bad.fno.ttl"
    bad_path.write_text("this is not valid turtle @@@", encoding="utf-8")

    library = FunctionLibrary.load_builtins()
    with pytest.raises(ValueError, match="Failed to parse"):
        library.add_declarations(bad_path)


@pytest.mark.integration
def test_build_function_library_loads_custom_declarations(tmp_path: Path) -> None:
    """build_function_library returns a library that includes custom declarations."""
    from rosetta.core.config import build_function_library

    custom_path = tmp_path / "custom.fno.ttl"
    custom_path.write_text(_CUSTOM_FNO_TTL, encoding="utf-8")
    config = {"functions": {"declarations": [str(custom_path)]}}

    library, fn_config = build_function_library(config)

    assert library.has_function("http://example.org/myCustomFunc")
    assert library.has_function("grel:math_round")
    assert fn_config["declarations"] == [custom_path]


# ---------------------------------------------------------------------------
# CLI-level tests (Truth #1, #2, #3)
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures" / "nations"
_NOR_SCHEMA = _FIXTURES / "nor_radar.linkml.yaml"
_MC_SCHEMA = _FIXTURES / "master_cop.linkml.yaml"
_NOR_SSSOM = _FIXTURES / "sssom_nor_approved.sssom.tsv"

_ROSETTA_TOML_DECL = """\
[functions]
declarations = ["{path}"]
"""

_ROSETTA_TOML_UDF = """\
[functions]
udfs = ["{path}"]
"""


def _fixed_graph() -> rdflib.Graph:
    g = rdflib.Graph()
    g.add(
        (
            rdflib.URIRef("http://example.org/s"),
            rdflib.URIRef("http://example.org/p"),
            rdflib.Literal("test"),
        )
    )
    return g


@pytest.mark.integration
def test_compile_cli_with_custom_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rosetta compile loads custom FnO declarations from rosetta.toml (Truth #1)."""
    from rosetta.cli.compile import cli

    custom_ttl = tmp_path / "custom.fno.ttl"
    custom_ttl.write_text(_CUSTOM_FNO_TTL, encoding="utf-8")
    toml = tmp_path / "rosetta.toml"
    toml.write_text(_ROSETTA_TOML_DECL.format(path=str(custom_ttl)), encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(_NOR_SSSOM),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
        ],
    )
    assert result.exit_code == 0, result.stderr


@pytest.mark.integration
def test_compile_cli_bad_declaration_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rosetta compile exits 1 with clean error when custom declaration is missing."""
    from rosetta.cli.compile import cli

    toml = tmp_path / "rosetta.toml"
    toml.write_text(_ROSETTA_TOML_DECL.format(path="nonexistent.fno.ttl"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(_NOR_SSSOM),
            "--source-schema",
            str(_NOR_SCHEMA),
            "--master-schema",
            str(_MC_SCHEMA),
        ],
    )
    assert result.exit_code == 1
    assert "not found" in result.stderr


@pytest.mark.integration
def test_transform_cli_passes_custom_udf_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rosetta transform passes custom UDF paths to run_materialize (Truth #2)."""
    from rosetta.cli.transform import cli

    custom_udf = tmp_path / "custom_udf.py"
    custom_udf.write_text(_CUSTOM_UDF_PY, encoding="utf-8")
    toml = tmp_path / "rosetta.toml"
    toml.write_text(_ROSETTA_TOML_UDF.format(path=str(custom_udf)), encoding="utf-8")

    dummy_yarrrml = tmp_path / "mapping.yml"
    dummy_yarrrml.write_text("mappings:\n  test: {}", encoding="utf-8")
    dummy_data = tmp_path / "data.json"
    dummy_data.write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    @contextlib.contextmanager
    def _capture(*args: object, **kwargs: object) -> Iterator[rdflib.Graph]:
        captured["extra_udf_paths"] = kwargs.get("extra_udf_paths")
        yield _fixed_graph()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("rosetta.cli.transform.run_materialize", _capture)
    monkeypatch.setattr(
        "rosetta.cli.transform.graph_to_jsonld",
        lambda *a, **kw: b'{"@context": {}, "@graph": []}',
    )

    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            str(dummy_yarrrml),
            str(dummy_data),
            "--master-schema",
            str(_MC_SCHEMA),
            "--no-validate",
        ],
    )
    assert result.exit_code == 0, result.stderr
    udf_paths = captured["extra_udf_paths"]
    assert isinstance(udf_paths, list)
    assert len(udf_paths) == 1
    assert udf_paths[0] == custom_udf


_MINIMAL_SCHEMA = """\
id: https://example.org/{name}
name: {name}
prefixes:
  linkml: https://w3id.org/linkml/
  test: https://example.org/test/
default_prefix: test
imports:
  - linkml:types
classes:
  TestClass:
    attributes:
      test_field:
        range: string
"""


def _make_sssom_tsv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "input.sssom.tsv"
    header = "# sssom_version: https://w3id.org/sssom/spec/0.15\n# mapping_set_id: test\n"
    with path.open("w") as f:
        f.write(header)
        writer = csv.DictWriter(f, fieldnames=SSSOM_COLUMNS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in SSSOM_COLUMNS})
    return path


@pytest.mark.integration
def test_ledger_dry_run_with_custom_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rosetta ledger --dry-run validates custom CURIEs via custom declarations (Truth #3)."""
    from rosetta.cli.ledger import cli

    custom_ttl = tmp_path / "custom.fno.ttl"
    custom_ttl.write_text(_CUSTOM_FNO_TTL, encoding="utf-8")
    toml = tmp_path / "rosetta.toml"
    toml.write_text(_ROSETTA_TOML_DECL.format(path=str(custom_ttl)), encoding="utf-8")

    src = tmp_path / "source.yaml"
    src.write_text(_MINIMAL_SCHEMA.format(name="source_schema"), encoding="utf-8")
    master = tmp_path / "master.yaml"
    master.write_text(_MINIMAL_SCHEMA.format(name="master_schema"), encoding="utf-8")

    sssom = _make_sssom_tsv(
        tmp_path,
        [
            {
                "subject_id": "test:test_field",
                "predicate_id": "skos:exactMatch",
                "object_id": "test:test_field",
                "mapping_justification": "semapv:ManualMappingCuration",
                "confidence": "0.9",
                "conversion_function": "http://example.org/myCustomFunc",
            }
        ],
    )

    log_path = tmp_path / "audit.tsv"
    monkeypatch.chdir(tmp_path)

    result = CliRunner(mix_stderr=False).invoke(
        cli,
        [
            "--audit-log",
            str(log_path),
            "append",
            "--role",
            "analyst",
            "--dry-run",
            str(sssom),
            "--source-schema",
            str(src),
            "--master-schema",
            str(master),
        ],
    )
    # dry-run exits 0 when no BLOCKs — custom CURIE is resolved via custom declaration
    # If custom declarations weren't loaded, the undeclared_function lint would BLOCK
    assert result.exit_code == 0, f"Unexpected BLOCKs:\n{result.output}"
