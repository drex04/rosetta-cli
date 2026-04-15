"""Tests for rosetta/core/units.py and rosetta/cli/lint.py."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.lint import cli
from rosetta.core.units import (
    UNIT_STRING_TO_IRI,
    dimension_vector,
    load_qudt_graph,
    suggest_fnml,
    units_compatible,
)

# ---------------------------------------------------------------------------
# Module-level fixture — load QUDT graph once for all unit tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qudt_graph():
    return load_qudt_graph()


# ---------------------------------------------------------------------------
# Section 1 — units.py unit tests
# ---------------------------------------------------------------------------


def test_unit_string_to_iri_meter():
    assert UNIT_STRING_TO_IRI["meter"] == "unit:M"


def test_unit_string_to_iri_foot():
    assert UNIT_STRING_TO_IRI["foot"] == "unit:FT"


def test_unit_string_to_iri_dbm():
    assert "dBm" in UNIT_STRING_TO_IRI
    assert UNIT_STRING_TO_IRI["dBm"] is None


def test_unit_string_to_iri_unknown():
    assert UNIT_STRING_TO_IRI.get("furlongs") is None


def test_load_qudt_graph_parses(qudt_graph):
    assert len(list(qudt_graph)) > 10


def test_dimension_vector_metre(qudt_graph):
    assert dimension_vector("unit:M", qudt_graph) == "A0E0L1I0M0H0T0D0"


def test_dimension_vector_kilogram(qudt_graph):
    assert dimension_vector("unit:KiloGM", qudt_graph) == "A0E0L0I0M1H0T0D0"


def test_dimension_vector_unknown(qudt_graph):
    assert dimension_vector("unit:FOOBAR", qudt_graph) is None


def test_units_compatible_same_unit(qudt_graph):
    assert units_compatible("unit:M", "unit:M", qudt_graph) is True


def test_units_compatible_same_dimension(qudt_graph):
    assert units_compatible("unit:FT", "unit:M", qudt_graph) is True


def test_units_compatible_different_dimension(qudt_graph):
    assert units_compatible("unit:FT", "unit:KiloGM", qudt_graph) is False


def test_units_compatible_unknown_unit(qudt_graph):
    assert units_compatible(None, "unit:M", qudt_graph) is None  # pyright: ignore[reportArgumentType]


def test_units_compatible_missing_vector(qudt_graph):
    assert units_compatible("unit:FOOBAR", "unit:BAZQUX", qudt_graph) is None


def test_dimension_vector_full_iri(qudt_graph):
    assert dimension_vector("http://qudt.org/vocab/unit/M", qudt_graph) == "A0E0L1I0M0H0T0D0"


def test_suggest_fnml_known_pair(qudt_graph):
    result = suggest_fnml("unit:FT", "unit:M", qudt_graph)
    assert result is not None
    assert "fnml_function" in result
    assert "multiplier" in result
    assert abs(result["multiplier"] - 0.3048) < 1e-6  # pyright: ignore[reportOperatorIssue]


def test_suggest_fnml_offset_pair(qudt_graph):
    result = suggest_fnml("unit:degC", "unit:K", qudt_graph)
    assert result is not None
    assert result["offset"] == pytest.approx(273.15)


def test_suggest_fnml_unknown_pair(qudt_graph):
    assert suggest_fnml("unit:FOOBAR", "unit:BAZQUX", qudt_graph) is None


# ---------------------------------------------------------------------------
# Section 2 — CLI integration tests
# ---------------------------------------------------------------------------


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return str(p)


_SRC_FOOT = """\
@prefix rose: <http://rosetta.interop/ns/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/field/alt>
    rose:detectedUnit "foot" ;
    rose:dataType xsd:float .
"""

_SRC_METER = """\
@prefix rose: <http://rosetta.interop/ns/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/field/alt>
    rose:detectedUnit "meter" ;
    rose:dataType xsd:float .
"""

_SRC_NO_UNIT = """\
@prefix rose: <http://rosetta.interop/ns/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/field/alt>
    rose:dataType xsd:float .
"""

_SRC_INT_DTYPE = """\
@prefix rose: <http://rosetta.interop/ns/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/field/alt>
    rose:detectedUnit "meter" ;
    rose:dataType xsd:integer .
"""

_MST_KILOGRAM = """\
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/master/altitude>
    qudt:unit unit:KiloGM ;
    rdfs:range xsd:float .
"""

_MST_METRE = """\
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/master/altitude>
    qudt:unit unit:M ;
    rdfs:range xsd:float .
"""

_MST_STRING_DTYPE = """\
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/master/altitude>
    qudt:unit unit:M ;
    rdfs:range xsd:string .
"""

_MST_UNKNOWN_UNIT = """\
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/master/altitude>
    qudt:unit <http://qudt.org/vocab/unit/FOOBAR> ;
    rdfs:range xsd:float .
"""

_SUGGESTIONS = json.dumps(
    {
        "http://example.org/field/alt": {
            "suggestions": [{"target_uri": "http://example.org/master/altitude", "score": 0.95}]
        }
    }
)


def _invoke(tmp_path, src_ttl, mst_ttl, extra_args=None):
    src = _write(tmp_path, "src.ttl", src_ttl)
    mst = _write(tmp_path, "mst.ttl", mst_ttl)
    sug = _write(tmp_path, "sug.json", _SUGGESTIONS)
    args = ["--source", src, "--master", mst, "--suggestions", sug]
    if extra_args:
        args.extend(extra_args)
    return CliRunner().invoke(cli, args)


def test_lint_cli_block_on_dimension_mismatch(tmp_path):
    result = _invoke(tmp_path, _SRC_FOOT, _MST_KILOGRAM)
    assert result.exit_code == 1
    data = json.loads(result.output)
    blocks = [f for f in data["findings"] if f["severity"] == "BLOCK"]
    assert any(f["rule"] == "unit_dimension_mismatch" for f in blocks)


def test_lint_cli_warning_unit_conversion(tmp_path):
    result = _invoke(tmp_path, _SRC_FOOT, _MST_METRE)
    assert result.exit_code == 0
    data = json.loads(result.output)
    warnings = [f for f in data["findings"] if f["severity"] == "WARNING"]
    assert any(f["rule"] == "unit_conversion_required" for f in warnings)
    conversion = next(f for f in warnings if f["rule"] == "unit_conversion_required")
    assert conversion["fnml_suggestion"] is not None


def test_lint_cli_info_no_unit(tmp_path):
    result = _invoke(tmp_path, _SRC_NO_UNIT, _MST_METRE)
    assert result.exit_code == 0
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["severity"] == "INFO"]
    assert any(f["rule"] == "unit_not_detected" for f in infos)


def test_lint_cli_strict_warning_becomes_block(tmp_path):
    result = _invoke(tmp_path, _SRC_FOOT, _MST_METRE, extra_args=["--strict"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    blocks = [f for f in data["findings"] if f["severity"] == "BLOCK"]
    assert any(f["rule"] == "unit_conversion_required" for f in blocks)


def test_lint_cli_output_file(tmp_path):
    out_path = str(tmp_path / "out.json")
    src = _write(tmp_path, "src.ttl", _SRC_FOOT)
    mst = _write(tmp_path, "mst.ttl", _MST_METRE)
    sug = _write(tmp_path, "sug.json", _SUGGESTIONS)
    CliRunner().invoke(
        cli,
        [
            "--source",
            src,
            "--master",
            mst,
            "--suggestions",
            sug,
            "--output",
            out_path,
        ],
    )
    assert (tmp_path / "out.json").exists()
    with open(out_path) as fh:
        data = json.load(fh)
    assert "findings" in data


def test_lint_cli_stdout(tmp_path):
    result = _invoke(tmp_path, _SRC_FOOT, _MST_METRE)
    assert '"findings"' in result.output
    data = json.loads(result.output)
    assert "findings" in data


def test_lint_cli_summary_counts(tmp_path):
    result = _invoke(tmp_path, _SRC_FOOT, _MST_METRE)
    data = json.loads(result.output)
    assert "summary" in data
    summary = data["summary"]
    assert "block" in summary
    assert "warning" in summary
    assert "info" in summary


def test_lint_cli_datatype_mismatch(tmp_path):
    result = _invoke(tmp_path, _SRC_INT_DTYPE, _MST_STRING_DTYPE)
    data = json.loads(result.output)
    rules = [f["rule"] for f in data["findings"]]
    assert "datatype_mismatch" in rules
    mismatch = next(f for f in data["findings"] if f["rule"] == "datatype_mismatch")
    assert mismatch["severity"] == "WARNING"


def test_lint_cli_unit_vector_missing(tmp_path):
    # Source has "meter" -> unit:M (known), master has FOOBAR (no dimension vector)
    # units_compatible("unit:M", "http://qudt.org/vocab/unit/FOOBAR", g) -> None
    result = _invoke(tmp_path, _SRC_METER, _MST_UNKNOWN_UNIT)
    data = json.loads(result.output)
    rules = [f["rule"] for f in data["findings"]]
    assert "unit_vector_missing" in rules
    vec_missing = next(f for f in data["findings"] if f["rule"] == "unit_vector_missing")
    assert vec_missing["severity"] == "INFO"


def test_lint_cli_strict_summary_warning_zero(tmp_path):
    result = _invoke(tmp_path, _SRC_FOOT, _MST_METRE, extra_args=["--strict"])
    data = json.loads(result.output)
    summary = data["summary"]
    assert summary["warning"] == 0
    assert summary["block"] > 0


# New fixtures for gap coverage

_SRC_DBM = """\
@prefix rose: <http://rosetta.interop/ns/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/field/alt>
    rose:detectedUnit "dBm" ;
    rose:dataType xsd:float .
"""

_MST_NO_UNIT = """\
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/master/altitude>
    rdfs:range xsd:float .
"""

_MST_KILOMETRE = """\
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/master/altitude>
    qudt:unit unit:KiloM ;
    rdfs:range xsd:float .
"""

_SRC_MULTI = """\
@prefix rose: <http://rosetta.interop/ns/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/field/alt>
    rose:detectedUnit "foot" ;
    rose:dataType xsd:float .

<http://example.org/field/lat>
    rose:detectedUnit "meter" ;
    rose:dataType xsd:float .
"""

_MST_MULTI = """\
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://example.org/master/altitude>
    qudt:unit unit:KiloGM ;
    rdfs:range xsd:float .

<http://example.org/master/latitude>
    qudt:unit unit:M ;
    rdfs:range xsd:float .
"""

_SUGGESTIONS_MULTI = json.dumps(
    {
        "http://example.org/field/alt": {
            "suggestions": [{"target_uri": "http://example.org/master/altitude", "score": 0.95}]
        },
        "http://example.org/field/lat": {
            "suggestions": [{"target_uri": "http://example.org/master/latitude", "score": 0.90}]
        },
    }
)


def test_lint_cli_master_unit_missing(tmp_path):
    """Source has a valid unit; master field has no qudt:unit → master_unit_missing INFO."""
    result = _invoke(tmp_path, _SRC_METER, _MST_NO_UNIT)
    assert result.exit_code == 0
    data = json.loads(result.output)
    rules = [f["rule"] for f in data["findings"]]
    assert "master_unit_missing" in rules
    finding = next(f for f in data["findings"] if f["rule"] == "master_unit_missing")
    assert finding["severity"] == "INFO"


def test_lint_cli_dbm_no_iri_mapping(tmp_path):
    """dBm maps to None in UNIT_STRING_TO_IRI → unit_not_detected with IRI-mapping message."""
    result = _invoke(tmp_path, _SRC_DBM, _MST_METRE)
    assert result.exit_code == 0
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["rule"] == "unit_not_detected"]
    assert infos, "Expected unit_not_detected finding for dBm"
    assert "no QUDT IRI mapping" in infos[0]["message"]


def test_lint_cli_strict_info_stays_info(tmp_path):
    """--strict only upgrades WARNINGs; INFO findings must remain INFO."""
    result = _invoke(tmp_path, _SRC_NO_UNIT, _MST_METRE, extra_args=["--strict"])
    data = json.loads(result.output)
    infos = [f for f in data["findings"] if f["severity"] == "INFO"]
    assert infos, "Expected at least one INFO finding (unit_not_detected)"
    assert all(f["rule"] == "unit_not_detected" for f in infos)


def test_lint_cli_unit_conversion_null_fnml(tmp_path):
    """Compatible units with no registered FnML conversion → fnml_suggestion is None.
    foot→kilometre: both length (compatible), but no direct FT→KiloM entry in fnml_registry.
    """
    result = _invoke(tmp_path, _SRC_FOOT, _MST_KILOMETRE)
    assert result.exit_code == 0
    data = json.loads(result.output)
    conversions = [f for f in data["findings"] if f["rule"] == "unit_conversion_required"]
    assert conversions, "Expected unit_conversion_required for foot→kilometre"
    assert conversions[0]["fnml_suggestion"] is None


def test_lint_cli_multi_mapping_summary(tmp_path):
    """Two pairs in one suggestions file — summary block/warning/info counts aggregate correctly."""
    sug = _write(tmp_path, "sug.json", _SUGGESTIONS_MULTI)
    src = _write(tmp_path, "src.ttl", _SRC_MULTI)
    mst = _write(tmp_path, "mst.ttl", _MST_MULTI)
    result = CliRunner().invoke(cli, ["--source", src, "--master", mst, "--suggestions", sug])
    data = json.loads(result.output)
    summary = data["summary"]
    # foot→KiloGM is BLOCK; meter→M is same unit (no unit finding); totals must reflect multi-pair
    assert summary["block"] >= 1
    assert len(data["findings"]) >= 1


def test_lint_cli_numeric_to_numeric_no_datatype_mismatch(tmp_path):
    """xsd:integer (source) vs xsd:float (master) — both numeric, no datatype_mismatch."""
    # _SRC_INT_DTYPE has rose:dataType xsd:integer, _MST_METRE has rdfs:range xsd:float
    # Both are numeric — should produce no datatype_mismatch finding
    result = _invoke(tmp_path, _SRC_INT_DTYPE, _MST_METRE)
    data = json.loads(result.output)
    rules = [f["rule"] for f in data["findings"]]
    assert "datatype_mismatch" not in rules


# ---------------------------------------------------------------------------
# SSSOM proposals lint tests
# ---------------------------------------------------------------------------

_MMC = "semapv:ManualMappingCuration"
_HC = "semapv:HumanCuration"
_SSSOM_HEADER = "# sssom_version: https://w3id.org/sssom/spec/0.15\n# mapping_set_id: test\n"
_SSSOM_COLS = [
    "subject_id",
    "predicate_id",
    "object_id",
    "mapping_justification",
    "confidence",
    "subject_label",
    "object_label",
    "mapping_date",
    "record_id",
]


def _write_sssom(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w") as f:
        f.write(_SSSOM_HEADER)
        writer = csv.DictWriter(f, fieldnames=_SSSOM_COLS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in _SSSOM_COLS})


def _no_accredit_toml(tmp_path: Path) -> Path:
    config = tmp_path / "rosetta.toml"
    config.write_text("[suggest]\ntop_k = 5\n")
    return config


def test_lint_sssom_passes_clean_file(tmp_path: Path) -> None:
    sssom = tmp_path / "clean.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0, result.output


def test_lint_sssom_max_one_mmc_per_pair_fails(tmp_path: Path) -> None:
    sssom = tmp_path / "dup.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
            {
                "subject_id": "a",
                "predicate_id": "skos:relatedMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.8",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 1


def test_lint_sssom_no_reproposal_of_approved_fails(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id="a",
                object_id="b",
                predicate_id="skos:exactMatch",
                mapping_justification=MMC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )
    append_log(
        [
            SSSOMRow(
                subject_id="a",
                object_id="b",
                predicate_id="skos:exactMatch",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )

    sssom = tmp_path / "reproposal.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(tmp_rosetta_toml)])
    assert result.exit_code == 1


def test_lint_sssom_no_reproposal_of_rejected_fails(tmp_path: Path, tmp_rosetta_toml: Path) -> None:
    from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION, append_log
    from rosetta.core.models import SSSOMRow

    log_path = tmp_path / "audit-log.sssom.tsv"
    append_log(
        [
            SSSOMRow(
                subject_id="c",
                object_id="d",
                predicate_id="skos:exactMatch",
                mapping_justification=MMC_JUSTIFICATION,
                confidence=0.9,
            )
        ],
        log_path,
    )
    append_log(
        [
            SSSOMRow(
                subject_id="c",
                object_id="d",
                predicate_id="owl:differentFrom",
                mapping_justification=HC_JUSTIFICATION,
                confidence=0.0,
            )
        ],
        log_path,
    )

    sssom = tmp_path / "reproposal_rejected.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "c",
                "predicate_id": "skos:exactMatch",
                "object_id": "d",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(tmp_rosetta_toml)])
    assert result.exit_code == 1


def test_lint_sssom_invalid_predicate_fails(tmp_path: Path) -> None:
    sssom = tmp_path / "bad_pred.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "bad:predicate",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 1


def test_lint_sssom_no_log_configured_skips_reproposal_check(tmp_path: Path) -> None:
    """Config without [accredit] section → reproposal check skipped."""
    sssom = tmp_path / "no_log.sssom.tsv"
    _write_sssom(
        sssom,
        [
            {
                "subject_id": "a",
                "predicate_id": "skos:exactMatch",
                "object_id": "b",
                "mapping_justification": _MMC,
                "confidence": "0.9",
            },
        ],
    )
    config = _no_accredit_toml(tmp_path)
    result = CliRunner().invoke(cli, ["--sssom", str(sssom), "--config", str(config)])
    assert result.exit_code == 0
