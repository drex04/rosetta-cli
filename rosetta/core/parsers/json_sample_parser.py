"""JSON sample parser — walk sample JSON data and deduce field schemas with stats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TextIO

from rosetta.core.parsers._types import FieldSchema, schema_slug
from rosetta.core.unit_detect import compute_stats, detect_unit


def _infer_data_type(values: list[Any]) -> str:
    """Infer FieldSchema data_type from a list of sample values (ignoring None)."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return "string"
    if all(isinstance(v, bool) for v in non_null):
        return "boolean"
    if all(isinstance(v, dict) for v in non_null):
        return "object"
    if all(isinstance(v, list) and any(isinstance(i, dict) for i in v) for v in non_null):
        return "object"  # list-of-dicts: each list key is a nested object collection
    if all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
        return "integer"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
        return "number"
    return "string"


def _build_fields(
    objects: list[dict[str, Any]],
    *,
    depth: int = 0,
    max_depth: int = 10,
) -> list[FieldSchema]:
    """Recursively build FieldSchema list from a list of sample objects."""
    all_keys = {k for obj in objects for k in obj}
    fields: list[FieldSchema] = []
    for key in sorted(all_keys):  # sorted for deterministic output
        values = [obj[key] for obj in objects if key in obj]
        data_type = _infer_data_type(values)
        required = all(key in obj for obj in objects)

        children: list[FieldSchema] = []
        sample_values: list[str | float | int | bool | None] = []

        if data_type == "object" and depth < max_depth:
            if all(isinstance(v, dict) for v in values if v is not None):
                # plain dict values (normal nested object)
                nested = [v for v in values if isinstance(v, dict)]
            else:
                # list-of-dicts values: flatten all items
                nested = [
                    item
                    for v in values
                    if isinstance(v, list)
                    for item in v
                    if isinstance(item, dict)
                ]
            children = _build_fields(nested, depth=depth + 1, max_depth=max_depth)
        else:
            sample_values = [v for v in values if not isinstance(v, (dict, list))]

        detected_unit = detect_unit(key, "")
        numeric_stats, categorical_stats = compute_stats(sample_values)

        fields.append(
            FieldSchema(
                name=key,
                data_type=data_type,
                required=required,
                detected_unit=detected_unit,
                sample_values=sample_values,
                numeric_stats=numeric_stats,
                categorical_stats=categorical_stats,
                children=children,
            )
        )
    return fields


def parse_json_sample(
    src: TextIO,
    path: Path | None,
    nation: str,
    max_sample_rows: int = 1000,
) -> tuple[list[FieldSchema], str]:
    """Walk sample JSON data recursively, returning (fields, slug) with nested FieldSchema."""
    try:
        data = json.load(src)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON: {exc}") from exc
    except RecursionError:
        raise ValueError("JSON is too deeply nested to parse safely.") from None

    if isinstance(data, list):
        objects = [o for o in data if isinstance(o, dict)]
    elif isinstance(data, dict):
        # Envelope pattern: single key whose value is a non-empty list of objects
        list_values = [
            v for v in data.values() if isinstance(v, list) and any(isinstance(i, dict) for i in v)
        ]
        objects = (
            [o for o in list_values[0] if isinstance(o, dict)] if len(list_values) == 1 else [data]
        )
    else:
        raise ValueError("Sample JSON must be a JSON object or array of objects.")

    if not objects:
        raise ValueError(
            "Sample JSON produced no fields — input must be a non-empty object or array of objects"
        )

    slug = schema_slug(path.stem) if path is not None else "sample"
    fields = _build_fields(objects[:max_sample_rows])
    if not fields:
        raise ValueError(
            "Sample JSON produced no fields — input must be a non-empty object or array of objects"
        )
    return fields, slug
