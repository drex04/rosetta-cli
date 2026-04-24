"""Tests for FunctionLibrary — FnO type signature registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from rosetta.core.function_library import FunctionLibrary


def test_load_builtins_has_all_eleven() -> None:
    lib = FunctionLibrary.load_builtins()
    builtins = [
        "grel:math_round",
        "grel:math_floor",
        "grel:math_ceil",
        "grel:string_toNumber",
        "grel:string_toString",
        "rfns:meterToFoot",
        "rfns:footToMeter",
        "rfns:kgToPound",
        "rfns:poundToKg",
        "rfns:celsiusToFahrenheit",
        "rfns:kelvinToCelsius",
    ]
    for fn in builtins:
        assert lib.has_function(fn), f"Missing: {fn}"


def test_has_function_unknown_returns_false() -> None:
    lib = FunctionLibrary.load_builtins()
    assert not lib.has_function("grel:nonExistent")


def test_get_input_type_round() -> None:
    lib = FunctionLibrary.load_builtins()
    assert lib.get_input_type("grel:math_round") == "xsd:decimal"


def test_get_output_type_round() -> None:
    lib = FunctionLibrary.load_builtins()
    assert lib.get_output_type("grel:math_round") == "xsd:integer"


def test_get_output_type_toNumber() -> None:
    lib = FunctionLibrary.load_builtins()
    assert lib.get_output_type("grel:string_toNumber") == "xsd:double"


def test_get_parameter_predicate_round() -> None:
    lib = FunctionLibrary.load_builtins()
    assert lib.get_parameter_predicate("grel:math_round") == "grel:p_dec_n"


def test_get_input_type_unit_conversion() -> None:
    lib = FunctionLibrary.load_builtins()
    assert lib.get_input_type("rfns:meterToFoot") == "xsd:decimal"


def test_add_custom_declarations(tmp_path: Path) -> None:
    custom_ttl = tmp_path / "custom.fno.ttl"
    custom_ttl.write_text("""
    @prefix fno: <https://w3id.org/function/ontology#> .
    @prefix myfn: <https://example.org/functions#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    myfn:customFn a fno:Function ;
        fno:expects ( [ a fno:Parameter ;
                         fno:predicate myfn:value ;
                         fno:type xsd:date ] ) ;
        fno:returns ( [ a fno:Output ;
                         fno:predicate myfn:result ;
                         fno:type xsd:dateTime ] ) .
    """)
    lib = FunctionLibrary.load_builtins()
    lib.add_declarations(custom_ttl)  # type: ignore[arg-type]
    assert lib.has_function("myfn:customFn") or lib.has_function(
        "https://example.org/functions#customFn"
    )


def test_sparql_returns_all_eleven() -> None:
    lib = FunctionLibrary.load_builtins()
    assert len(lib._functions) == 11


def test_get_input_type_unknown_returns_none() -> None:
    lib = FunctionLibrary.load_builtins()
    assert lib.get_input_type("grel:nonExistent") is None


def test_get_parameter_predicate_unknown_raises() -> None:
    lib = FunctionLibrary.load_builtins()
    with pytest.raises(KeyError):
        lib.get_parameter_predicate("grel:nonExistent")


def test_empty_library_has_no_functions() -> None:
    lib = FunctionLibrary()
    assert not lib._functions
    assert not lib.has_function("grel:math_round")


# --- load_conversion_policies tests ---

from rosetta.core.config import load_conversion_policies  # noqa: E402


def test_load_conversion_policies_empty() -> None:
    assert not load_conversion_policies({})


def test_load_conversion_policies_type_pairs() -> None:
    config = {"conversions": {"float:integer": "grel:math_round"}}
    result = load_conversion_policies(config)
    assert result == {"float:integer": "grel:math_round"}


def test_load_conversion_policies_unit_pairs() -> None:
    config = {"conversions": {"units": {"unit:M:unit:FT": "rfns:meterToFoot"}}}
    result = load_conversion_policies(config)
    assert result == {"unit:M:unit:FT": "rfns:meterToFoot"}


def test_load_conversion_policies_merged() -> None:
    config = {
        "conversions": {
            "float:integer": "grel:math_round",
            "units": {"unit:M:unit:FT": "rfns:meterToFoot"},
        }
    }
    result = load_conversion_policies(config)
    assert result == {
        "float:integer": "grel:math_round",
        "unit:M:unit:FT": "rfns:meterToFoot",
    }


def test_load_conversion_policies_skips_non_string() -> None:
    """Nested sub-tables are not treated as policy values."""
    config = {"conversions": {"units": {"a:b": "fn:x"}, "float:int": "fn:y"}}
    result = load_conversion_policies(config)
    assert "float:int" in result
    assert "units" not in result
