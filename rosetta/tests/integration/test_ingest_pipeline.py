"""Integration tests for rosetta-ingest on stress fixtures (Phase 18-02)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import CliRunner
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.loaders import yaml_loader

from rosetta.cli.ingest import cli as ingest_cli

pytestmark = [pytest.mark.integration]


def _load_linkml(out: Path) -> SchemaDefinition:
    return cast(
        SchemaDefinition,
        yaml_loader.load(str(out), target_class=SchemaDefinition),
    )


def _classes_dict(schema: SchemaDefinition) -> dict[str, Any]:
    """Return schema.classes as a dict, working around linkml-runtime's union type."""
    return cast(dict[str, Any], schema.classes or {})


def _slots_dict(schema: SchemaDefinition) -> dict[str, Any]:
    """Return schema.slots as a dict, working around linkml-runtime's union type."""
    return cast(dict[str, Any], schema.slots or {})


def test_ingest_nested_json_schema(tmp_path: Path, stress_dir: Path) -> None:
    """Deeply nested JSON Schema ingests cleanly and preserves the `kind` slot."""
    out = tmp_path / "nested.linkml.yaml"
    result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [
            str(stress_dir / "nested_json_schema.json"),
            "--schema-format",
            "json-schema",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"ingest failed: {result.stderr}"

    schema = _load_linkml(out)

    # NOTE: schema-automator flattens JSON Schema oneOf — the `kind` slot exists
    # but without a TrackKind enum range. See plan 18-02 Risks.
    classes = _classes_dict(schema)
    slots = _slots_dict(schema)

    total_slot_names: set[str] = set(slots.keys())
    total_attr_names: set[str] = set()
    for cls in classes.values():
        attrs = getattr(cls, "attributes", None) or {}
        total_attr_names.update(attrs.keys())

    assert len(classes) >= 3, f"expected >=3 classes, got {len(classes)}"
    total_fields = len(total_slot_names) + len(total_attr_names)
    assert total_fields >= 12, f"expected >=12 slots+attributes total, got {total_fields}"

    # Behavioural invariant: a `kind`-like field is preserved somewhere.
    all_names = total_slot_names | total_attr_names
    assert any(n == "kind" or n.endswith("_kind") or "kind" in n for n in all_names), (
        f"expected a 'kind'-like slot/attribute, got names: {sorted(all_names)[:20]}..."
    )


def test_ingest_complex_xsd(tmp_path: Path, stress_dir: Path) -> None:
    """Complex XSD with inheritance preserves TrackBase→RadarTrack is_a and attributes."""
    out = tmp_path / "xsd.linkml.yaml"
    result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [
            str(stress_dir / "complex_types.xsd"),
            "--schema-format",
            "xsd",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"ingest failed: {result.stderr}"

    schema = _load_linkml(out)
    classes = _classes_dict(schema)

    # NOTE: XSD attributes land under classes[*].attributes, not top-level slots.
    # See plan 18-02 Risks.
    class_names = set(classes.keys())
    assert "TrackBase" in class_names, f"expected TrackBase in classes, got {class_names}"
    assert "RadarTrack" in class_names, f"expected RadarTrack in classes, got {class_names}"

    radar_track = classes["RadarTrack"]
    assert radar_track.is_a == "TrackBase", (
        f"expected RadarTrack.is_a == TrackBase, got {radar_track.is_a}"
    )

    total_attrs = sum(len(getattr(cls, "attributes", None) or {}) for cls in classes.values())
    assert total_attrs >= 3, f"expected >=3 attributes across classes, got {total_attrs}"


def test_ingest_csv_edge_cases(tmp_path: Path, stress_dir: Path) -> None:
    """CSV with BOM, embedded quotes/newlines, and header-space normalises to 5 slots.

    The UTF-8 BOM is stripped by ``_strip_bom_if_present`` before the file
    reaches schema-automator, so slot names are clean. Header-space
    normalisation is schema-automator's concern and is NOT overridden; the
    ``radar type`` column lands with its literal space preserved.
    """
    out = tmp_path / "csv_edge.linkml.yaml"
    result = CliRunner(mix_stderr=False).invoke(
        ingest_cli,
        [
            str(stress_dir / "csv_edge_cases.csv"),
            "--schema-format",
            "csv",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, f"ingest failed: {result.stderr}"

    schema = _load_linkml(out)

    slots = _slots_dict(schema)
    classes = _classes_dict(schema)

    all_field_names: set[str] = set(slots.keys())
    for cls in classes.values():
        attrs = getattr(cls, "attributes", None) or {}
        all_field_names.update(attrs.keys())

    assert len(all_field_names) == 5, (
        f"expected exactly 5 slots/attributes (one per CSV column), got "
        f"{len(all_field_names)}: {sorted(all_field_names)}"
    )

    # Behavioural invariant: BOM is stripped from slot names.
    for name in all_field_names:
        assert not name.startswith("\ufeff"), f"BOM must be stripped from slot names; got {name!r}"
    # Every source column is represented (exact match on BOM-stripped names;
    # schema-automator preserves the literal space in `radar type`).
    for expected in ("track_id", "location", "note", "reading_mhz", "radar type"):
        assert expected in all_field_names, (
            f"expected {expected!r} in slots, got: {sorted(all_field_names)}"
        )
