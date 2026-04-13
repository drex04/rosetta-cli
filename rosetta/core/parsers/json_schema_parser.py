from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import TextIO

from rosetta.core.parsers._types import FieldSchema, schema_slug
from rosetta.core.unit_detect import compute_stats, detect_unit


def parse_json_schema(src: TextIO, path: Path | None, nation: str) -> tuple[list[FieldSchema], str]:
    """Parse a JSON Schema document and return (fields, slug)."""
    try:
        schema = json.load(src)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON{f' in {path!r}' if path else ''}: {exc}") from exc

    if "properties" not in schema:
        raise ValueError(f"JSON Schema missing 'properties' key in {path!r}")

    # Derive slug: prefer $id last path segment (stripping version suffixes) over title.
    # Rationale: $id encodes the canonical identifier for the schema (e.g. "deu_patriot"),
    # while title is often a human-readable string that produces unwieldy slugs.
    if "$id" in schema:
        parts = [p for p in schema["$id"].rstrip("/").split("/") if p]
        # skip trailing version-like segments (e.g. "v1", "v2.3")
        while parts and re.match(r"^v\d", parts[-1], re.IGNORECASE):
            parts.pop()
        id_segment = parts[-1] if parts else ""
        if id_segment:
            slug = schema_slug(id_segment)
        elif "title" in schema:
            slug = schema_slug(schema["title"])
        else:
            fallback = path.stem if path is not None else "unknown"
            slug = schema_slug(fallback)
            warnings.warn(
                "No title or $id in JSON Schema; using filename as slug",
                stacklevel=2,
            )
    elif "title" in schema:
        slug = schema_slug(schema["title"])
    else:
        fallback = path.stem if path is not None else "unknown"
        slug = schema_slug(fallback)
        warnings.warn(
            "No title or $id in JSON Schema; using filename as slug",
            stacklevel=2,
        )

    # Collect top-level examples (list of dicts only)
    top_examples = schema.get("examples", [])
    if not isinstance(top_examples, list):
        top_examples = []

    required_fields = set(schema.get("required", []))

    fields: list[FieldSchema] = []
    for name, prop in schema["properties"].items():
        if "$ref" in prop:
            raise ValueError(
                f"Property {name!r} uses $ref which is not supported in JSON Schema properties; "
                "inline the type or resolve refs before ingestion."
            )
        raw_type = prop.get("type", "string")
        data_type = raw_type[0] if isinstance(raw_type, list) else raw_type
        description = prop.get("description", "")
        is_required = name in required_fields

        # Collect sample values from top-level examples only
        sample_values = [ex[name] for ex in top_examples if isinstance(ex, dict) and name in ex]

        detected_unit = detect_unit(name, description)
        numeric_stats, categorical_stats = compute_stats(sample_values)

        fields.append(
            FieldSchema(
                name=name,
                data_type=data_type,
                description=description,
                required=is_required,
                detected_unit=detected_unit,
                sample_values=sample_values,
                numeric_stats=numeric_stats,
                categorical_stats=categorical_stats,
            )
        )

    return fields, slug
