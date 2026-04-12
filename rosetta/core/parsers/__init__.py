from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import TextIOBase
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO


@dataclass
class FieldSchema:
    name: str                          # original field name from source
    data_type: str                     # "string" | "number" | "integer" | "boolean"
    description: str = ""
    required: bool = False
    detected_unit: str | None = None
    sample_values: list[str | float | int | bool | None] = field(default_factory=list)
    numeric_stats: dict | None = None      # populated by compute_stats()
    categorical_stats: dict | None = None  # populated by compute_stats()


def schema_slug(title: str) -> str:
    """Convert a schema title or $id segment to a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug


def dispatch_parser(
    src: TextIO,
    path: Path | None,
    input_format: str | None,
    nation: str,
    max_sample_rows: int = 1000,
) -> tuple[list[FieldSchema], str]:
    """Detect format, call the right parser, return (fields, slug).

    Imports are lazy (inside function body) to avoid circular imports.
    If path extension is unrecognised and input_format is None:
        raise ValueError("Cannot auto-detect format from stdin; use --input-format {csv,json-schema,openapi}")
    """
    fmt = input_format
    if fmt is None:
        if path is None:
            raise ValueError(
                "Cannot auto-detect format from stdin; use --input-format {csv,json-schema,openapi}"
            )
        ext = path.suffix.lower()
        if ext == ".csv":
            fmt = "csv"
        elif ext == ".json":
            fmt = "json-schema"
        elif ext in (".yaml", ".yml"):
            fmt = "openapi"
        else:
            raise ValueError(
                f"Cannot auto-detect format from extension '{ext}'; use --input-format {{csv,json-schema,openapi}}"
            )

    if fmt == "csv":
        from rosetta.core.parsers.csv_parser import parse_csv
        return parse_csv(src, path, nation, max_sample_rows)
    elif fmt == "json-schema":
        from rosetta.core.parsers.json_schema_parser import parse_json_schema
        return parse_json_schema(src, path, nation)
    elif fmt == "openapi":
        from rosetta.core.parsers.openapi_parser import parse_openapi
        return parse_openapi(src, path, nation)
    else:
        raise ValueError(f"Unknown input format: {fmt!r}. Use csv, json-schema, or openapi.")
