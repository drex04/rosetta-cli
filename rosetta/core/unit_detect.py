from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pint import UnitRegistry

# ---------------------------------------------------------------------------
# Regex tables — ordered most-specific first; all map to QUDT IRI strings.
# ---------------------------------------------------------------------------

_NAME_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    # Speed — compound before bare length/time tokens
    (re.compile(r"(?:_kmh|km[/_]h)", re.IGNORECASE), "unit:KiloM-PER-HR"),
    (re.compile(r"(?:^|_)mps$", re.IGNORECASE), "unit:M-PER-SEC"),
    (re.compile(r"(?:^|_)mph$", re.IGNORECASE), "unit:MI-PER-HR"),
    # Frequency — GHz/MHz/kHz before bare Hz
    (re.compile(r"(?:^|_)(?:ghz|gigahertz)$", re.IGNORECASE), "unit:GigaHZ"),
    (re.compile(r"(?:^|_)(?:mhz|megahertz)$", re.IGNORECASE), "unit:MegaHZ"),
    (re.compile(r"(?:^|_)(?:khz|kilohertz)$", re.IGNORECASE), "unit:KiloHZ"),
    (re.compile(r"(?:^|_)hz$", re.IGNORECASE), "unit:HZ"),
    # Length — km before bare m
    (re.compile(r"(?:^|_)meters?$", re.IGNORECASE), "unit:M"),
    (re.compile(r"(?:^|_)km$", re.IGNORECASE), "unit:KiloM"),
    (re.compile(r"(?:^|_)m$", re.IGNORECASE), "unit:M"),
    (re.compile(r"(?:^|_)ft$", re.IGNORECASE), "unit:FT"),
    (re.compile(r"(?:^|_)nmi$", re.IGNORECASE), "unit:NauticalMile"),
    (re.compile(r"(?:^|_)kts$", re.IGNORECASE), "unit:KN"),
    # Angle — mrad before rad, deg/grad separated from rad/radians
    (re.compile(r"(?:^|_)mrad$", re.IGNORECASE), "unit:MilliRAD"),
    (re.compile(r"(?:^|_)(?:deg|grad|grader)$", re.IGNORECASE), "unit:DEG"),
    (re.compile(r"(?:^|_)(?:rad|radians?)$", re.IGNORECASE), "unit:RAD"),
    # Power / signal — dBm has no QUDT IRI; short-circuit with None
    (re.compile(r"(?:^|_)dbm$", re.IGNORECASE), None),
    # Mass
    (re.compile(r"(?:^|_)kg$", re.IGNORECASE), "unit:KiloGM"),
    # Pressure — hPa before Pa
    (re.compile(r"(?:^|_)hpa$", re.IGNORECASE), "unit:HectoPa"),
    (re.compile(r"(?:^|_)pa$", re.IGNORECASE), "unit:PA"),
    # Time
    (re.compile(r"(?:^|_)(?:secs?|seconds?)$", re.IGNORECASE), "unit:SEC"),
    (re.compile(r"(?:^|_)(?:hrs?|hours?)$", re.IGNORECASE), "unit:HR"),
    # Temperature
    (re.compile(r"(?:^|_)(?:celsius|degc)$", re.IGNORECASE), "unit:degC"),
    (re.compile(r"(?:^|_)(?:fahrenheit|degf)$", re.IGNORECASE), "unit:DEG_F"),
    (re.compile(r"(?:^|_)kelvin$", re.IGNORECASE), "unit:K"),
]

_DESC_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    (re.compile(r"\bdecimal\s+degrees?\b", re.IGNORECASE), "unit:DEG"),
    (re.compile(r"\bkm/h\b", re.IGNORECASE), "unit:KiloM-PER-HR"),
    (re.compile(r"\bm/s\b", re.IGNORECASE), "unit:M-PER-SEC"),
    (re.compile(r"\bkilometers?\b", re.IGNORECASE), "unit:KiloM"),
    (re.compile(r"\bnautical\s+miles?\b", re.IGNORECASE), "unit:NauticalMile"),
    (re.compile(r"\b(?:feet|foot)\b", re.IGNORECASE), "unit:FT"),
    (re.compile(r"\bknots?\b", re.IGNORECASE), "unit:KN"),
    (re.compile(r"\bmetres?\b", re.IGNORECASE), "unit:M"),
    (re.compile(r"\bdegree\b", re.IGNORECASE), "unit:DEG"),
    (re.compile(r"\bmilliradians?\b|\bmrads?\b", re.IGNORECASE), "unit:MilliRAD"),
    (re.compile(r"\bradians?\b", re.IGNORECASE), "unit:RAD"),
    (re.compile(r"\bGHz\b"), "unit:GigaHZ"),
    (re.compile(r"\bMHz\b"), "unit:MegaHZ"),
    (re.compile(r"\bkHz\b"), "unit:KiloHZ"),
    (re.compile(r"\bhertz\b|\bHz\b", re.IGNORECASE), "unit:HZ"),
    (re.compile(r"\bkilograms?\b", re.IGNORECASE), "unit:KiloGM"),
    (re.compile(r"\bhectopascals?\b|\bhPa\b"), "unit:HectoPa"),
    (re.compile(r"\bpascals?\b", re.IGNORECASE), "unit:PA"),
    (re.compile(r"\bseconds?\b", re.IGNORECASE), "unit:SEC"),
    (re.compile(r"\bminutes?\b", re.IGNORECASE), "unit:MIN"),
    (re.compile(r"\bhours?\b", re.IGNORECASE), "unit:HR"),
    (re.compile(r"\bkelvin\b", re.IGNORECASE), "unit:K"),
    (re.compile(r"\bcelsius\b", re.IGNORECASE), "unit:degC"),
    (re.compile(r"\bfahrenheit\b", re.IGNORECASE), "unit:DEG_F"),
    (re.compile(r"\bdBm\b"), None),
]

# ---------------------------------------------------------------------------
# NLP fallback — quantulum3 extracts unit candidates; pint canonicalises them.
# Keys are the exact str() of pint's parse_expression().units output.
# ---------------------------------------------------------------------------

_PINT_TO_QUDT_IRI: dict[str, str | None] = {
    "meter": "unit:M",
    "kilometer": "unit:KiloM",
    "kilometer / hour": "unit:KiloM-PER-HR",
    "foot": "unit:FT",
    "knot": "unit:KN",
    "degree": "unit:DEG",
    "nautical_mile": "unit:NauticalMile",
    "meter / second": "unit:M-PER-SEC",
    "mile / hour": "unit:MI-PER-HR",
    "radian": "unit:RAD",
    "milliradian": "unit:MilliRAD",
    "kilogram": "unit:KiloGM",
    "gram": "unit:GM",
    "second": "unit:SEC",
    "minute": "unit:MIN",
    "hour": "unit:HR",
    "pascal": "unit:PA",
    "hectopascal": "unit:HectoPa",
    "kelvin": "unit:K",
    "degree_Celsius": "unit:degC",
    "degree_Fahrenheit": "unit:DEG_F",
    "hertz": "unit:HZ",
    "kilohertz": "unit:KiloHZ",
    "megahertz": "unit:MegaHZ",
    "gigahertz": "unit:GigaHZ",
}

_ureg: UnitRegistry | None = None  # pyright: ignore[reportMissingTypeArgument]


_CAMEL_BOUNDARY: re.Pattern[str] = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _snake_case(name: str) -> str:
    """Insert underscores at lowercase/digit→uppercase CamelCase boundaries.

    ``hasAltitudeFt`` → ``has_Altitude_Ft`` and ``alt123Ft`` → ``alt123_Ft``
    so a trailing-unit regex like ``(?:^|_)ft$`` matches across CamelCase
    without growing every pattern with a CamelCase alternative.
    """
    return _CAMEL_BOUNDARY.sub("_", name)


def detect_unit(name: str, description: str) -> str | None:
    """Return the QUDT unit IRI for a field, or None if not detected.

    Cascade: name regex → description regex → quantulum3+pint NLP on
    description. Returns None both when no unit is detected and when the
    detected unit has no QUDT IRI (e.g. dBm).
    """
    normalized = _snake_case(name)
    for pattern, iri in _NAME_PATTERNS:
        if pattern.search(normalized):
            return iri

    for pattern, iri in _DESC_PATTERNS:
        if pattern.search(description):
            return iri

    return _detect_from_nlp(description)


def recognized_unit_without_iri(name: str, description: str) -> bool:
    """Return True if name/description matched a unit pattern that maps to None.

    Lets callers distinguish "known unit with no QUDT IRI" (e.g. dBm) from
    "no unit detected at all" — both cases make detect_unit() return None.
    """
    normalized = _snake_case(name)
    for pattern, iri in _NAME_PATTERNS:
        if pattern.search(normalized):
            return iri is None
    for pattern, iri in _DESC_PATTERNS:
        if pattern.search(description):
            return iri is None
    return False


def _detect_from_nlp(description: str) -> str | None:
    """quantulum3 + pint layer — lazy imports, single UnitRegistry per process."""
    global _ureg  # noqa: PLW0603
    try:
        from pint import UnitRegistry  # noqa: PLC0415
        from quantulum3 import parser as q3  # noqa: PLC0415
    except ImportError:
        return None

    if _ureg is None:
        _ureg = UnitRegistry()

    try:
        candidates: list[Any] = list(q3.parse(description))
    except Exception as exc:  # noqa: BLE001
        _log.debug("quantulum3 parse failed: %s", exc)
        return None

    for qty in candidates:
        try:
            parsed = _ureg.parse_expression(qty.unit.name)
            key = str(parsed.units)
            if key in _PINT_TO_QUDT_IRI:
                return _PINT_TO_QUDT_IRI[key]
        except Exception:  # noqa: BLE001
            continue
    return None
