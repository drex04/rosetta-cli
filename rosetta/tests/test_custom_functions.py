"""Integration tests for the custom FnO function mechanism (Phase 23-05, Task 4).

Covers:
- FunctionLibrary.add_declarations() with a custom TTL
- _write_udf_file() concatenation of builtin + custom UDFs
- load_function_config() path validation
- Malformed TTL raises clean ValueError
- run_materialize() signature accepts extra_udf_paths
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from rosetta.core.config import load_function_config
from rosetta.core.function_library import FunctionLibrary
from rosetta.core.rml_runner import _write_udf_file, run_materialize

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
def test_run_materialize_accepts_extra_udf_paths_param() -> None:
    """run_materialize signature must declare extra_udf_paths parameter."""
    sig = inspect.signature(run_materialize)
    assert "extra_udf_paths" in sig.parameters, (
        "run_materialize must accept extra_udf_paths keyword argument"
    )
    param = sig.parameters["extra_udf_paths"]
    assert param.default is None, "extra_udf_paths should default to None"
