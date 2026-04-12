from __future__ import annotations

import csv
import itertools
from pathlib import Path
from typing import TextIO

from rosetta.core.parsers import FieldSchema
from rosetta.core.unit_detect import compute_stats, detect_unit


def parse_csv(
    src: TextIO,
    path: Path | None,
    nation: str,
    max_sample_rows: int = 1000,
) -> tuple[list[FieldSchema], str]:
    """Parse a CSV file and return (list[FieldSchema], slug).

    Reads up to max_sample_rows rows. Infers data_type per column,
    detects units, and computes stats.
    """
    reader = csv.DictReader(src)
    rows = list(itertools.islice(reader, max_sample_rows))

    slug = path.stem if path is not None else "unknown"

    if not rows:
        return ([], slug)

    field_names = list(rows[0].keys())
    fields: list[FieldSchema] = []

    for name in field_names:
        # Collect all raw values for this column across sampled rows
        all_values = [row[name] for row in rows]
        non_empty = [v for v in all_values if v != ""]

        # Infer data_type
        if not non_empty:
            data_type = "string"
        else:
            numeric_vals: list[float] = []
            all_numeric = True
            for v in non_empty:
                try:
                    numeric_vals.append(float(v))
                except (ValueError, TypeError):
                    all_numeric = False
                    break

            if all_numeric:
                # "integer" only if raw strings contain no decimal point
                if all("." not in v for v in non_empty):
                    data_type = "integer"
                else:
                    data_type = "number"
            else:
                data_type = "string"

        # Detect unit from field name
        detected_unit = detect_unit(name, "")

        # Compute stats
        numeric_stats, categorical_stats = compute_stats(all_values)

        fields.append(
            FieldSchema(
                name=name,
                data_type=data_type,
                detected_unit=detected_unit,
                sample_values=all_values,
                numeric_stats=numeric_stats,
                categorical_stats=categorical_stats,
            )
        )

    return (fields, slug)
