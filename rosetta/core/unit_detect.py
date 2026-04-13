from __future__ import annotations

import json
import re
import statistics as _statistics
from typing import Any

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


def compute_stats(
    sample_values: list[Any],
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Compute numeric or categorical statistics for a list of sample values.

    Returns:
        (numeric_stats, categorical_stats) where exactly one is populated
        (or both None if the input is empty / all-null).

    numeric_stats keys:  count (int), min, max, mean, stddev, null_rate,
                         cardinality, histogram (JSON-encoded list of 10 bin counts),
                         histogram_edges (JSON-encoded list of 11 bin edges)
    categorical_stats keys: count (int), distinct_count, null_rate
    """
    total_raw = len(sample_values)
    if total_raw == 0:
        return (None, None)

    # Filter out None and empty strings
    filtered = [v for v in sample_values if v is not None and v != ""]

    if not filtered:
        return (None, None)

    null_rate = (total_raw - len(filtered)) / total_raw

    # Try to parse each value as float
    numeric: list[float] = []
    for v in filtered:
        try:
            numeric.append(float(v))
        except (ValueError, TypeError):
            pass

    total = len(filtered)

    if len(numeric) / total >= 0.5:
        min_val = min(numeric)
        max_val = max(numeric)
        mean_val = sum(numeric) / len(numeric)
        stddev_val = _statistics.stdev(numeric) if len(numeric) >= 2 else 0.0

        # 10-bin equal-width histogram
        if len(numeric) >= 2 and min_val != max_val:
            bin_width = (max_val - min_val) / 10
            edges = [min_val + i * bin_width for i in range(11)]
            counts = [0] * 10
            for v in numeric:
                idx = min(int((v - min_val) / bin_width), 9)
                counts[idx] += 1
        else:
            edges = [min_val] * 11
            counts = [len(numeric)] + [0] * 9

        stats: dict[str, object] = {
            "count": total,
            "min": float(min_val),
            "max": float(max_val),
            "mean": float(mean_val),
            "stddev": float(stddev_val),
            "null_rate": float(null_rate),
            "cardinality": len(set(numeric)),
            "histogram": json.dumps(counts),
            "histogram_edges": json.dumps([round(e, 9) for e in edges]),
        }
        return (stats, None)
    else:
        # Treat as categorical
        cat_stats: dict[str, object] = {
            "count": total,
            "distinct_count": len(set(str(v) for v in filtered)),
            "null_rate": float(null_rate),
        }
        return (None, cat_stats)
