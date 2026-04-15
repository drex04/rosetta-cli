from __future__ import annotations

import re

# Each entry: (pattern, unit_string, apply_to_name, apply_to_description)
# Order matters — more specific patterns must come before less specific ones.
_NAME_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # km/h variants — MUST come before _km to avoid false match
    (re.compile(r"(?:_kmh|km[/_]h)", re.IGNORECASE), "km_per_hour"),
    # individual unit suffixes — all end-anchored
    (re.compile(r"(?:^|_)meters?$", re.IGNORECASE), "meter"),
    (re.compile(r"(?:^|_)m$", re.IGNORECASE), "meter"),
    (re.compile(r"(?:^|_)km$", re.IGNORECASE), "kilometer"),
    (re.compile(r"(?:^|_)ft$", re.IGNORECASE), "foot"),
    (re.compile(r"(?:^|_)kts$", re.IGNORECASE), "knot"),
    (re.compile(r"(?:^|_)(?:deg|grad|grader)$", re.IGNORECASE), "degree"),
    (re.compile(r"(?:^|_)dbm$", re.IGNORECASE), "dBm"),
]

_DESC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bdecimal\s+degrees?\b", re.IGNORECASE), "degree"),
    (re.compile(r"\bkm/h\b", re.IGNORECASE), "km_per_hour"),
    (re.compile(r"\bkilometers?\b", re.IGNORECASE), "kilometer"),
    (re.compile(r"\b(?:feet|foot)\b", re.IGNORECASE), "foot"),
    (re.compile(r"\bknots?\b", re.IGNORECASE), "knot"),
    (re.compile(r"\bmetres?\b", re.IGNORECASE), "meter"),
    (re.compile(r"\bdegree\b", re.IGNORECASE), "degree"),
    (re.compile(r"\bdBm\b"), "dBm"),
]


def detect_unit(name: str, description: str) -> str | None:
    """Detect the physical unit for a field from its name and description.

    Apply end-anchored regex patterns to the field name first, then the
    description. Return the first match, or None if no unit is detected.
    """
    for pattern, unit in _NAME_PATTERNS:
        if pattern.search(name):
            return unit

    for pattern, unit in _DESC_PATTERNS:
        if pattern.search(description):
            return unit

    return None
