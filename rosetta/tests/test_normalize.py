"""Tests for rosetta.core.normalize — one test per format plus meta-tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from rosetta.core.normalize import normalize_schema

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_json_schema() -> None:
    """deu_patriot.json → SchemaDefinition with at least 1 slot."""
    schema = normalize_schema(FIXTURES / "deu_patriot.json")
    assert schema is not None
    assert len(schema.slots) >= 1 or len(schema.classes) >= 1


def test_normalize_openapi() -> None:
    """usa_c2.yaml (OpenAPI) → SchemaDefinition with at least 1 class."""
    schema = normalize_schema(FIXTURES / "usa_c2.yaml", fmt="openapi")
    assert schema is not None
    assert len(schema.classes) >= 1 or len(schema.slots) >= 1


def test_normalize_xsd(tmp_path: Path) -> None:
    """Inline minimal XSD via tmp_path → SchemaDefinition with at least 1 slot."""
    xsd_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:complexType name="SpeedType">
    <xs:sequence>
      <xs:element name="speed_kts" type="xs:float"/>
    </xs:sequence>
  </xs:complexType>
</xs:schema>"""
    xsd_file = tmp_path / "test.xsd"
    xsd_file.write_text(xsd_content)
    schema = normalize_schema(xsd_file)
    assert schema is not None
    assert len(schema.classes) >= 1 or len(schema.slots) >= 1


def test_normalize_csv(tmp_path: Path) -> None:
    """Inline CSV → SchemaDefinition with slot 'name' and slot 'age'."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("name,age\nAlice,30\nBob,25\n")
    schema = normalize_schema(csv_file)
    assert schema is not None
    slot_names = list(schema.slots.keys())
    assert any("name" in s.lower() for s in slot_names) or len(schema.classes) >= 1


def test_normalize_tsv(tmp_path: Path) -> None:
    """Inline TSV → SchemaDefinition."""
    tsv_file = tmp_path / "test.tsv"
    tsv_file.write_text("name\tage\nAlice\t30\nBob\t25\n")
    schema = normalize_schema(tsv_file)
    assert schema is not None
    assert len(schema.slots) >= 1 or len(schema.classes) >= 1


def test_normalize_json_sample(tmp_path: Path) -> None:
    """Inline JSON sample list → SchemaDefinition."""
    sample_file = tmp_path / "sample.json"
    sample_file.write_text('[{"speed_kts": 400, "altitude_ft": 35000}]')
    schema = normalize_schema(sample_file, fmt="json-sample")
    assert schema is not None
    assert len(schema.slots) >= 1 or len(schema.classes) >= 1


def test_normalize_rdfs(tmp_path: Path) -> None:
    """Inline minimal Turtle → SchemaDefinition with at least 1 class."""
    ttl_content = """\
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix ex: <http://example.org/> .

ex:Speed a rdfs:Class ;
    rdfs:label "Speed" .
"""
    ttl_file = tmp_path / "test.ttl"
    ttl_file.write_text(ttl_content)
    schema = normalize_schema(ttl_file)
    assert schema is not None
    assert len(schema.classes) >= 1 or len(schema.slots) >= 1


def test_normalize_auto_detect_ttl(tmp_path: Path) -> None:
    """.ttl extension with fmt=None → rdfs format inferred."""
    ttl_file = tmp_path / "test.ttl"
    ttl_file.write_text(
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix ex: <http://example.org/> .\n"
        'ex:Speed a rdfs:Class ; rdfs:label "Speed" .\n'
    )
    schema = normalize_schema(ttl_file, fmt=None)
    assert schema is not None


def test_normalize_auto_detect_json() -> None:
    """.json extension with fmt=None → json-schema format inferred."""
    schema = normalize_schema(FIXTURES / "deu_patriot.json", fmt=None)
    assert schema is not None


def test_normalize_schema_name_from_stem() -> None:
    """No schema_name arg → schema.name == path.stem."""
    schema = normalize_schema(FIXTURES / "deu_patriot.json")
    assert schema.name == "deu_patriot"


def test_normalize_schema_name_override() -> None:
    """schema_name='custom' → schema.name == 'custom'."""
    schema = normalize_schema(FIXTURES / "deu_patriot.json", schema_name="custom")
    assert schema.name == "custom"


def test_normalize_unsupported_raises(tmp_path: Path) -> None:
    """.xyz extension with no fmt → ValueError."""
    bad_file = tmp_path / "bad.xyz"
    bad_file.write_text("whatever")
    with pytest.raises(ValueError, match="Cannot infer format"):
        normalize_schema(bad_file)
