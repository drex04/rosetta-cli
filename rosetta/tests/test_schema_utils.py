"""Tests for rosetta.core.schema_utils — shared schema utilities."""

from __future__ import annotations

import textwrap

import pytest
from linkml_runtime.utils.schemaview import SchemaView

from rosetta.core.models import SSSOMRow
from rosetta.core.schema_utils import (
    ancestors,
    build_slot_owner_index,
    check_slot_class_reachability,
    local_name,
    nearest_mapped_ancestor,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_MASTER_YAML = textwrap.dedent("""\
    name: master
    id: https://example.org/master
    imports:
    - linkml:types
    prefixes:
      linkml:
        prefix_prefix: linkml
        prefix_reference: https://w3id.org/linkml/
    default_range: string
    slots:
      hasLongitude:
        name: hasLongitude
        range: double
      hasLatitude:
        name: hasLatitude
        range: double
      hasTrackNumber:
        name: hasTrackNumber
        range: string
      hasVerticalRate:
        name: hasVerticalRate
        range: double
    classes:
      Entity:
        name: Entity
        slots:
        - hasLongitude
        - hasLatitude
      Track:
        name: Track
        is_a: Entity
        slots:
        - hasTrackNumber
      AirTrack:
        name: AirTrack
        is_a: Track
        slots:
        - hasVerticalRate
      SensorReport:
        name: SensorReport
""")

_SOURCE_YAML = textwrap.dedent("""\
    name: source
    id: https://example.org/source
    imports:
    - linkml:types
    prefixes:
      linkml:
        prefix_prefix: linkml
        prefix_reference: https://w3id.org/linkml/
    default_range: string
    slots:
      longitude:
        name: longitude
        range: double
      latitude:
        name: latitude
        range: double
    classes:
      Observation:
        name: Observation
        slots:
        - longitude
        - latitude
""")


@pytest.fixture()
def master_view() -> SchemaView:
    return SchemaView(_MASTER_YAML)


@pytest.fixture()
def source_view() -> SchemaView:
    return SchemaView(_SOURCE_YAML)


# ---------------------------------------------------------------------------
# build_slot_owner_index
# ---------------------------------------------------------------------------


def test_build_slot_owner_index_returns_defining_class(master_view: SchemaView) -> None:
    index = build_slot_owner_index(master_view)
    assert index["hasLongitude"] == "Entity"
    assert index["hasLatitude"] == "Entity"
    assert index["hasTrackNumber"] == "Track"
    assert index["hasVerticalRate"] == "AirTrack"


# ---------------------------------------------------------------------------
# local_name
# ---------------------------------------------------------------------------


def test_local_name_strips_prefix() -> None:
    assert local_name("nor_radar:Observation") == "Observation"
    assert local_name("master:hasLongitude") == "hasLongitude"


def test_local_name_no_prefix_passthrough() -> None:
    assert local_name("Observation") == "Observation"


# ---------------------------------------------------------------------------
# ancestors
# ---------------------------------------------------------------------------


def test_ancestors_walks_is_a(master_view: SchemaView) -> None:
    result = ancestors("AirTrack", master_view)
    assert result == {"AirTrack", "Track", "Entity"}


def test_ancestors_root_class(master_view: SchemaView) -> None:
    result = ancestors("Entity", master_view)
    assert result == {"Entity"}


def test_ancestors_standalone_class(master_view: SchemaView) -> None:
    result = ancestors("SensorReport", master_view)
    assert result == {"SensorReport"}


# ---------------------------------------------------------------------------
# nearest_mapped_ancestor
# ---------------------------------------------------------------------------


def test_nearest_mapped_ancestor_direct_match(master_view: SchemaView) -> None:
    result = nearest_mapped_ancestor("Track", {"Track"}, master_view)
    assert result == "Track"


def test_nearest_mapped_ancestor_superclass_of_mapped(master_view: SchemaView) -> None:
    # Entity is a superclass of Track — so Entity resolves to Track
    result = nearest_mapped_ancestor("Entity", {"Track"}, master_view)
    assert result == "Track"


def test_nearest_mapped_ancestor_unreachable(master_view: SchemaView) -> None:
    # SensorReport has no relationship to Entity
    result = nearest_mapped_ancestor("Entity", {"SensorReport"}, master_view)
    assert result is None


def test_nearest_mapped_ancestor_walk_up(master_view: SchemaView) -> None:
    # AirTrack → Track → Entity; mapped={Entity}
    result = nearest_mapped_ancestor("AirTrack", {"Entity"}, master_view)
    assert result == "Entity"


# ---------------------------------------------------------------------------
# check_slot_class_reachability
# ---------------------------------------------------------------------------


def _make_row(
    subject_id: str,
    object_id: str,
    justification: str = "semapv:ManualMappingCuration",
) -> SSSOMRow:
    return SSSOMRow(
        subject_id=subject_id,
        predicate_id="skos:exactMatch",
        object_id=object_id,
        mapping_justification=justification,
        confidence=0.9,
        subject_label="",
        object_label="",
    )


def test_slot_class_unreachable(source_view: SchemaView, master_view: SchemaView) -> None:
    rows = [
        _make_row("source:Observation", "master:SensorReport"),  # class mapping
        _make_row("source:longitude", "master:hasLongitude"),  # slot mapping
    ]
    mismatches = check_slot_class_reachability(rows, source_view, master_view)
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.target_slot_name == "hasLongitude"
    assert m.target_owning_class == "Entity"
    assert m.mapped_target_classes == {"SensorReport"}
    assert m.target_class_subclasses == ["AirTrack", "Track"]


def test_slot_class_reachable(source_view: SchemaView, master_view: SchemaView) -> None:
    rows = [
        _make_row("source:Observation", "master:Track"),  # class mapping → Track extends Entity
        _make_row("source:longitude", "master:hasLongitude"),  # slot on Entity, reachable via Track
    ]
    mismatches = check_slot_class_reachability(rows, source_view, master_view)
    assert not mismatches


def test_slot_class_reachable_via_subclass(
    source_view: SchemaView, master_view: SchemaView
) -> None:
    rows = [
        _make_row("source:Observation", "master:AirTrack"),  # AirTrack → Track → Entity
        _make_row("source:longitude", "master:hasLongitude"),  # hasLongitude on Entity
    ]
    mismatches = check_slot_class_reachability(rows, source_view, master_view)
    assert not mismatches


def test_no_confirmed_rows_returns_empty(source_view: SchemaView, master_view: SchemaView) -> None:
    rows = [
        _make_row("source:Observation", "master:SensorReport", "semapv:CompositeMatching"),
    ]
    mismatches = check_slot_class_reachability(rows, source_view, master_view)
    assert not mismatches


def test_no_class_mappings_returns_empty(source_view: SchemaView, master_view: SchemaView) -> None:
    rows = [
        _make_row("source:longitude", "master:hasLongitude"),
    ]
    mismatches = check_slot_class_reachability(rows, source_view, master_view)
    assert not mismatches
