from __future__ import annotations

from pathlib import Path
from typing import TextIO

import yaml

from rosetta.core.parsers import FieldSchema, schema_slug
from rosetta.core.unit_detect import compute_stats, detect_unit


def _resolve_ref(ref: str, schemas: dict) -> dict:
    """Resolve an internal $ref like '#/components/schemas/X' to its schema dict."""
    if not ref.startswith("#"):
        raise ValueError(f"External $ref not supported: {ref}")
    # Expect format: #/components/schemas/<Name>
    parts = ref.lstrip("#/").split("/")
    # parts = ["components", "schemas", "Name"]
    if len(parts) == 3 and parts[0] == "components" and parts[1] == "schemas":
        name = parts[2]
        if name in schemas:
            return schemas[name]
    raise ValueError(f"Cannot resolve $ref: {ref}")


def parse_openapi(src: TextIO, path: Path | None, nation: str) -> tuple[list[FieldSchema], str]:
    """Parse an OpenAPI 3.x document and return (list[FieldSchema], slug).

    Walks components.schemas, resolves internal $refs, merges all properties
    into a flat list (last-schema-wins on duplicate names).
    """
    doc = yaml.safe_load(src)
    if not isinstance(doc, dict):
        raise ValueError("OpenAPI document must be a YAML mapping, got "
                         f"{type(doc).__name__}")

    # Derive slug: normalize path.stem through schema_slug to ensure lowercase/safe URIs;
    # fall back to schema_slug of info.title when no path is available.
    if path is not None:
        slug = schema_slug(path.stem)
    else:
        title = doc.get("info", {}).get("title", "unknown")
        slug = schema_slug(title)

    components = doc.get("components", {})
    schemas: dict = components.get("schemas", {})

    # Merged properties: name -> FieldSchema (last-schema-wins)
    merged: dict[str, FieldSchema] = {}

    for _schema_name, schema_obj in schemas.items():
        # Resolve $ref at top level if needed
        if "$ref" in schema_obj:
            schema_obj = _resolve_ref(schema_obj["$ref"], schemas)

        properties: dict = schema_obj.get("properties", {})
        required_fields: list = schema_obj.get("required", [])

        # Collect sample values from schema-level examples (list of dicts) only
        schema_examples: list[dict] = schema_obj.get("examples", [])

        for field_name, field_def in properties.items():
            # Resolve $ref in individual property if present
            if "$ref" in field_def:
                field_def = _resolve_ref(field_def["$ref"], schemas)

            data_type = field_def.get("type", "string")
            description = field_def.get("description", "")
            is_required = field_name in required_fields

            # Gather sample values from schema-level examples only (not per-property example)
            sample_values = []
            for example_obj in schema_examples:
                if isinstance(example_obj, dict) and field_name in example_obj:
                    sample_values.append(example_obj[field_name])

            detected_unit = detect_unit(field_name, description)
            numeric_stats, categorical_stats = compute_stats(sample_values)

            merged[field_name] = FieldSchema(
                name=field_name,
                data_type=data_type,
                description=description,
                required=is_required,
                detected_unit=detected_unit,
                sample_values=sample_values,
                numeric_stats=numeric_stats,
                categorical_stats=categorical_stats,
            )

    return list(merged.values()), slug
