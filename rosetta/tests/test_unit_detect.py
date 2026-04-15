"""Tests for rosetta/core/unit_detect.py — detect_unit()."""

from __future__ import annotations

import pytest

from rosetta.core.unit_detect import detect_unit

# ---------------------------------------------------------------------------
# Name-pattern tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        # km/h variants — must win over bare _km
        ("speed_kmh", "km_per_hour"),
        ("speed_km_h", "km_per_hour"),
        ("speed_km/h", "km_per_hour"),
        # meters / meter (end-anchored)
        ("altitude_meters", "meter"),
        ("altitude_meter", "meter"),
        ("distance_m", "meter"),
        # kilometre
        ("range_km", "kilometer"),
        # foot
        ("ceiling_ft", "foot"),
        # knot
        ("speed_kts", "knot"),
        # degree variants
        ("bearing_deg", "degree"),
        ("bearing_grad", "degree"),
        ("bearing_grader", "degree"),
        # dBm
        ("signal_dbm", "dBm"),
        ("signal_DBM", "dBm"),  # case-insensitive
    ],
)
def test_detect_unit_from_name(name: str, expected: str) -> None:
    assert detect_unit(name, "") == expected


def test_detect_unit_name_takes_priority_over_description() -> None:
    # name says km, description says foot — name wins
    assert detect_unit("range_km", "measured in feet") == "kilometer"


def test_detect_unit_no_false_positive_km_in_kmh() -> None:
    # km/h pattern must fire before bare km pattern
    assert detect_unit("speed_kmh", "") == "km_per_hour"


# ---------------------------------------------------------------------------
# Description-pattern tests (name gives no match)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "description,expected",
    [
        ("position in decimal degree", "degree"),
        ("position in decimal degrees", "degree"),
        ("speed in km/h", "km_per_hour"),
        ("range in kilometer", "kilometer"),
        ("range in kilometers", "kilometer"),
        ("ceiling in feet", "foot"),
        ("ceiling in foot", "foot"),
        ("wind speed in knots", "knot"),
        ("wind speed in knot", "knot"),
        ("altitude in metres", "meter"),
        ("altitude in metre", "meter"),
        ("bearing in degree", "degree"),
        ("signal level in dBm", "dBm"),
    ],
)
def test_detect_unit_from_description(description: str, expected: str) -> None:
    assert detect_unit("value", description) == expected


# ---------------------------------------------------------------------------
# No-match cases
# ---------------------------------------------------------------------------


def test_detect_unit_returns_none_when_no_match() -> None:
    assert detect_unit("field_name", "some unrelated description") is None


def test_detect_unit_empty_inputs() -> None:
    assert detect_unit("", "") is None


def test_detect_unit_partial_name_no_match() -> None:
    # "kilometer" in name but not end-anchored — should not match bare _km pattern
    assert detect_unit("kilometer_range", "") is None


def test_detect_unit_dbm_desc_case_sensitive() -> None:
    # _DESC_PATTERNS dBm pattern has no re.IGNORECASE — 'dbm' in desc is not matched
    assert detect_unit("field", "power in dbm") is None


def test_detect_unit_dBm_desc_exact_case() -> None:
    assert detect_unit("field", "power in dBm") == "dBm"
