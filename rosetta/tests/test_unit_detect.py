"""Tests for rosetta/core/unit_detect.py — detect_unit() returns QUDT IRIs."""

from __future__ import annotations

import pytest

from rosetta.core.unit_detect import detect_unit

# ---------------------------------------------------------------------------
# Name-pattern tests — expected values are QUDT IRI strings (or None)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        # Speed
        ("speed_kmh", "unit:KiloM-PER-HR"),
        ("speed_km_h", "unit:KiloM-PER-HR"),
        ("speed_km/h", "unit:KiloM-PER-HR"),
        ("speed_mps", "unit:M-PER-SEC"),
        ("speed_mph", "unit:MI-PER-HR"),
        # Length
        ("altitude_meters", "unit:M"),
        ("altitude_meter", "unit:M"),
        ("distance_m", "unit:M"),
        ("range_km", "unit:KiloM"),
        ("ceiling_ft", "unit:FT"),
        ("dist_nmi", "unit:NauticalMile"),
        ("speed_kts", "unit:KN"),
        # Frequency — most-specific first
        ("freq_ghz", "unit:GigaHZ"),
        ("freq_mhz", "unit:MegaHZ"),
        ("freq_khz", "unit:KiloHZ"),
        ("carrier_hz", "unit:HZ"),
        # Angle
        ("bearing_deg", "unit:DEG"),
        ("bearing_grad", "unit:DEG"),
        ("bearing_grader", "unit:DEG"),
        ("bearing_rad", "unit:RAD"),
        ("bearing_radians", "unit:RAD"),
        ("bearing_mrad", "unit:MilliRAD"),
        # Mass
        ("weight_kg", "unit:KiloGM"),
        # Pressure
        ("baro_hpa", "unit:HectoPa"),
        ("pressure_pa", "unit:PA"),
        # Time
        ("elapsed_sec", "unit:SEC"),
        ("elapsed_seconds", "unit:SEC"),
        ("elapsed_hr", "unit:HR"),
        ("elapsed_hours", "unit:HR"),
        # Temperature
        ("temp_celsius", "unit:degC"),
        ("temp_degc", "unit:degC"),
        ("temp_fahrenheit", "unit:DEG_F"),
        ("temp_degf", "unit:DEG_F"),
        ("temp_kelvin", "unit:K"),
        # dBm — no QUDT IRI, returns None
        ("signal_dbm", None),
        ("signal_DBM", None),
    ],
)
def test_detect_unit_from_name(name: str, expected: str | None) -> None:
    assert detect_unit(name, "") == expected


def test_detect_unit_name_takes_priority_over_description() -> None:
    # name says km, description says foot — name wins
    assert detect_unit("range_km", "measured in feet") == "unit:KiloM"


def test_detect_unit_no_false_positive_km_in_kmh() -> None:
    # km/h pattern must fire before bare km pattern
    assert detect_unit("speed_kmh", "") == "unit:KiloM-PER-HR"


# ---------------------------------------------------------------------------
# Description-pattern tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "description,expected",
    [
        ("position in decimal degree", "unit:DEG"),
        ("position in decimal degrees", "unit:DEG"),
        ("speed in km/h", "unit:KiloM-PER-HR"),
        ("Speed in m/s", "unit:M-PER-SEC"),
        ("range in kilometer", "unit:KiloM"),
        ("range in kilometers", "unit:KiloM"),
        ("Distance in nautical miles", "unit:NauticalMile"),
        ("ceiling in feet", "unit:FT"),
        ("ceiling in foot", "unit:FT"),
        ("wind speed in knots", "unit:KN"),
        ("wind speed in knot", "unit:KN"),
        ("altitude in metres", "unit:M"),
        ("altitude in metre", "unit:M"),
        ("bearing in degree", "unit:DEG"),
        ("Bearing in radians", "unit:RAD"),
        ("Angle in milliradians", "unit:MilliRAD"),
        ("Frequency in GHz", "unit:GigaHZ"),
        ("Frequency in MHz", "unit:MegaHZ"),
        ("Signal frequency in kHz", "unit:KiloHZ"),
        ("Frequency in hertz", "unit:HZ"),
        ("Mass in kilograms", "unit:KiloGM"),
        ("Pressure in hectopascals", "unit:HectoPa"),
        ("Pressure in pascals", "unit:PA"),
        ("Duration in seconds", "unit:SEC"),
        ("Duration in minutes", "unit:MIN"),
        ("Duration in hours", "unit:HR"),
        ("Temperature in kelvin", "unit:K"),
        ("Temperature in celsius", "unit:degC"),
        ("Temperature in fahrenheit", "unit:DEG_F"),
        ("signal level in dBm", None),
    ],
)
def test_detect_unit_from_description(description: str, expected: str | None) -> None:
    assert detect_unit("value", description) == expected


# ---------------------------------------------------------------------------
# NLP-path tests — quantulum3 + pint when regex misses
# ---------------------------------------------------------------------------


def test_detect_unit_quantulum3_megahertz() -> None:
    """quantulum3 fires when regex patterns miss; pint canonicalises and maps."""
    # Avoid 'megahertz' keyword in desc — force NLP path via numeric + unit token
    result = detect_unit("carrier_wave", "operating at 100 MHz carrier")
    assert result == "unit:MegaHZ"


def test_detect_unit_quantulum3_no_false_positive() -> None:
    """Description with no detectable unit returns None through NLP."""
    assert detect_unit("callsign", "this field represents a unique identifier") is None


def test_detect_unit_name_takes_priority_over_quantulum3() -> None:
    """Name regex wins before the NLP path is reached."""
    assert detect_unit("range_km", "speed in metres per second") == "unit:KiloM"


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
    # and there's no NLP-pint mapping for dBm either → None
    assert detect_unit("field", "power in dbm") is None


def test_detect_unit_dBm_desc_exact_case() -> None:
    # dBm has no QUDT IRI — desc-pattern returns None, short-circuiting NLP
    assert detect_unit("field", "power in dBm") is None
