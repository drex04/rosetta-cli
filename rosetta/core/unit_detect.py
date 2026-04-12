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
    (re.compile(r"(?:^|_)(?:deg|grader)$", re.IGNORECASE), "degree"),
    (re.compile(r"(?:^|_)dbm$", re.IGNORECASE), "dBm"),
]

_DESC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bdecimal\s+degree\b", re.IGNORECASE), "degree"),
    (re.compile(r"\bkm/h\b", re.IGNORECASE), "km_per_hour"),
    (re.compile(r"\bkilometer\b", re.IGNORECASE), "kilometer"),
    (re.compile(r"\b(?:feet|foot)\b", re.IGNORECASE), "foot"),
    (re.compile(r"\bknot\b", re.IGNORECASE), "knot"),
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


def compute_stats(
    sample_values: list,
) -> tuple[dict | None, dict | None]:
    """Compute numeric or categorical statistics for a list of sample values.

    Returns:
        (numeric_stats, categorical_stats) where exactly one is populated
        (or both None if the input is empty / all-null).

    numeric_stats keys:  count, min, max, mean  (all float)
    categorical_stats keys: count, distinct_count
    """
    if not sample_values:
        return (None, None)

    # Filter out None and empty strings
    filtered = [v for v in sample_values if v is not None and v != ""]

    if not filtered:
        return (None, None)

    # Try to parse each value as float
    numeric: list[float] = []
    for v in filtered:
        try:
            numeric.append(float(v))
        except (ValueError, TypeError):
            pass

    total = len(filtered)

    if len(numeric) / total >= 0.5:
        # Treat as numeric
        stats: dict = {
            "count": float(total),
            "min": float(min(numeric)),
            "max": float(max(numeric)),
            "mean": float(sum(numeric) / len(numeric)),
        }
        return (stats, None)
    else:
        # Treat as categorical
        cat_stats: dict = {
            "count": total,
            "distinct_count": len(set(str(v) for v in filtered)),
        }
        return (None, cat_stats)
