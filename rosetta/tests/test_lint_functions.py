"""Tests for function-aware lint validation and populate_conversion_functions."""

import pytest
import rdflib

from rosetta.core.function_library import FunctionLibrary
from rosetta.core.lint import (
    check_datatype,
    check_units,
    populate_conversion_functions,
)
from rosetta.core.models import LintFinding, SSSOMRow
from rosetta.core.units import load_qudt_graph


@pytest.fixture()
def library() -> FunctionLibrary:
    return FunctionLibrary.load_builtins()


@pytest.fixture()
def qudt_graph() -> rdflib.Graph:
    return load_qudt_graph()


def _make_row(**overrides: object) -> SSSOMRow:
    defaults: dict[str, object] = dict(
        subject_id="src:field",
        predicate_id="skos:exactMatch",
        object_id="tgt:field",
        mapping_justification="semapv:ManualMappingCuration",
        confidence=0.9,
    )
    defaults.update(overrides)
    return SSSOMRow(**defaults)  # pyright: ignore[reportArgumentType]


# ---------------------------------------------------------------------------
# check_datatype tests
# ---------------------------------------------------------------------------


def test_check_datatype_covered_by_function(library: FunctionLibrary) -> None:
    """integer→string with grel:string_toString → INFO datatype_covered_by_function."""
    row = _make_row(
        subject_datatype="integer",
        object_datatype="string",
        conversion_function="grel:string_toString",
    )
    findings: list[LintFinding] = []
    check_datatype(findings, row, library=library)
    assert len(findings) == 1
    assert findings[0].rule == "datatype_covered_by_function"
    assert findings[0].severity == "INFO"


def test_check_datatype_undeclared_function(library: FunctionLibrary) -> None:
    """Undeclared conversion_function → BLOCK undeclared_function."""
    row = _make_row(
        subject_datatype="integer",
        object_datatype="string",
        conversion_function="rfns:nonexistent",
    )
    findings: list[LintFinding] = []
    check_datatype(findings, row, library=library)
    assert len(findings) == 1
    assert findings[0].rule == "undeclared_function"
    assert findings[0].severity == "BLOCK"


def test_check_datatype_no_function_still_blocks() -> None:
    """No conversion_function → BLOCK datatype_mismatch as before."""
    row = _make_row(subject_datatype="integer", object_datatype="string")
    findings: list[LintFinding] = []
    check_datatype(findings, row)
    assert len(findings) == 1
    assert findings[0].rule == "datatype_mismatch"
    assert findings[0].severity == "BLOCK"


def test_check_datatype_function_output_doesnt_cover(library: FunctionLibrary) -> None:
    """float→string with grel:math_round (output xsd:integer) → still BLOCK datatype_mismatch.

    grel:math_round returns xsd:integer which does NOT cover target "string",
    so the original BLOCK must still fire.
    """
    row = _make_row(
        subject_datatype="float",
        object_datatype="string",
        conversion_function="grel:math_round",
    )
    findings: list[LintFinding] = []
    check_datatype(findings, row, library=library)
    assert len(findings) == 1
    assert findings[0].rule == "datatype_mismatch"
    assert findings[0].severity == "BLOCK"


def test_check_datatype_no_library_with_function_blocks() -> None:
    """library=None + conversion_function set → original BLOCK still fires."""
    row = _make_row(
        subject_datatype="integer",
        object_datatype="string",
        conversion_function="grel:string_toString",
    )
    findings: list[LintFinding] = []
    check_datatype(findings, row, library=None)
    assert len(findings) == 1
    assert findings[0].rule == "datatype_mismatch"
    assert findings[0].severity == "BLOCK"


def test_check_datatype_narrowing_covered_by_function(library: FunctionLibrary) -> None:
    """float→integer narrowing with grel:math_round → INFO datatype_covered_by_function."""
    row = _make_row(
        subject_datatype="float",
        object_datatype="integer",
        conversion_function="grel:math_round",
    )
    findings: list[LintFinding] = []
    check_datatype(findings, row, library=library)
    assert len(findings) == 1
    assert findings[0].rule == "datatype_covered_by_function"
    assert findings[0].severity == "INFO"


# ---------------------------------------------------------------------------
# check_units tests
# ---------------------------------------------------------------------------


def test_check_units_covered_by_function(
    library: FunctionLibrary, qudt_graph: rdflib.Graph
) -> None:
    """unit:M → unit:FT with rfns:meterToFoot → INFO unit_conversion_covered."""
    row = _make_row(
        subject_id="src:altitude_m",
        object_id="tgt:altitude_ft",
        subject_label="altitude_m",
        object_label="altitude_ft",
        conversion_function="rfns:meterToFoot",
    )
    findings: list[LintFinding] = []
    check_units(findings, row, qudt_graph, library=library)
    unit_findings = [f for f in findings if f.rule == "unit_conversion_covered"]
    assert len(unit_findings) == 1
    assert unit_findings[0].severity == "INFO"


def test_check_units_undeclared_function(
    library: FunctionLibrary, qudt_graph: rdflib.Graph
) -> None:
    """Undeclared conversion_function on unit-mismatch row → BLOCK undeclared_function."""
    row = _make_row(
        subject_id="src:altitude_m",
        object_id="tgt:altitude_ft",
        subject_label="altitude_m",
        object_label="altitude_ft",
        conversion_function="rfns:bogus",
    )
    findings: list[LintFinding] = []
    check_units(findings, row, qudt_graph, library=library)
    block_findings = [f for f in findings if f.rule == "undeclared_function"]
    assert len(block_findings) == 1
    assert block_findings[0].severity == "BLOCK"


def test_check_units_no_function_still_warns(qudt_graph: rdflib.Graph) -> None:
    """No conversion_function on unit-mismatch row → WARNING unit_conversion_required."""
    row = _make_row(
        subject_id="src:altitude_m",
        object_id="tgt:altitude_ft",
        subject_label="altitude_m",
        object_label="altitude_ft",
    )
    findings: list[LintFinding] = []
    check_units(findings, row, qudt_graph)
    warn_findings = [f for f in findings if f.rule == "unit_conversion_required"]
    assert len(warn_findings) == 1
    assert warn_findings[0].severity == "WARNING"


def test_check_units_no_library_with_function_warns(qudt_graph: rdflib.Graph) -> None:
    """library=None + conversion_function set → WARNING (no silent pass-through)."""
    row = _make_row(
        subject_id="src:altitude_m",
        object_id="tgt:altitude_ft",
        subject_label="altitude_m",
        object_label="altitude_ft",
        conversion_function="rfns:meterToFoot",
    )
    findings: list[LintFinding] = []
    check_units(findings, row, qudt_graph, library=None)
    warn_findings = [f for f in findings if f.rule == "unit_conversion_required"]
    assert len(warn_findings) == 1
    assert warn_findings[0].severity == "WARNING"


def test_populate_empty_policies(library: FunctionLibrary) -> None:
    """Empty policies dict → conversion_function stays None."""
    row = _make_row(subject_datatype="float", object_datatype="integer")
    populate_conversion_functions([row], {}, library)
    assert row.conversion_function is None


# ---------------------------------------------------------------------------
# populate_conversion_functions tests
# ---------------------------------------------------------------------------


def test_populate_type_pair_match(library: FunctionLibrary) -> None:
    """Policy float:integer → grel:math_round sets conversion_function."""
    row = _make_row(subject_datatype="float", object_datatype="integer")
    populate_conversion_functions([row], {"float:integer": "grel:math_round"}, library)
    assert row.conversion_function == "grel:math_round"


def test_populate_unit_pair_match(library: FunctionLibrary) -> None:
    """Policy unit:M:unit:FT → rfns:meterToFoot sets conversion_function."""
    row = _make_row(
        subject_id="src:altitude_m",
        object_id="tgt:altitude_ft",
        subject_label="altitude_m",
        object_label="altitude_ft",
    )
    populate_conversion_functions([row], {"unit:M:unit:FT": "rfns:meterToFoot"}, library)
    assert row.conversion_function == "rfns:meterToFoot"


def test_populate_no_match(library: FunctionLibrary) -> None:
    """No matching policy → conversion_function stays None."""
    row = _make_row(subject_datatype="float", object_datatype="integer")
    populate_conversion_functions([row], {"string:integer": "grel:string_toNumber"}, library)
    assert row.conversion_function is None


def test_populate_already_set(library: FunctionLibrary) -> None:
    """Pre-existing conversion_function is not overwritten."""
    row = _make_row(
        subject_datatype="float",
        object_datatype="integer",
        conversion_function="grel:math_floor",
    )
    populate_conversion_functions([row], {"float:integer": "grel:math_round"}, library)
    assert row.conversion_function == "grel:math_floor"


def test_populate_undeclared_in_library_skipped(library: FunctionLibrary) -> None:
    """Policy function not in library → NOT set on row."""
    row = _make_row(subject_datatype="float", object_datatype="integer")
    populate_conversion_functions([row], {"float:integer": "rfns:nonexistent"}, library)
    assert row.conversion_function is None
