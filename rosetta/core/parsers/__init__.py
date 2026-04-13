from __future__ import annotations

from pathlib import Path
from typing import TextIO

from rosetta.core.parsers._types import FieldSchema, schema_slug

__all__ = ["FieldSchema", "schema_slug", "dispatch_parser"]


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
        raise ValueError(
            "Cannot auto-detect format from stdin; use --input-format {csv,json-schema,openapi}"
        )
    """
    fmt = input_format
    if fmt is None:
        if path is None:
            raise ValueError(
                "Cannot auto-detect format from stdin; "
                "use --input-format {csv,json-schema,openapi,xsd,json-sample}"
            )
        ext = path.suffix.lower()
        if ext == ".csv":
            fmt = "csv"
        elif ext == ".json":
            fmt = "json-schema"
        elif ext in (".yaml", ".yml"):
            fmt = "openapi"
        elif ext == ".xsd":
            fmt = "xsd"
        else:
            raise ValueError(
                f"Cannot auto-detect format from extension '{ext}';"
                " use --input-format {csv,json-schema,openapi,xsd,json-sample}"
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
    elif fmt == "xsd":
        from rosetta.core.parsers.xsd_parser import parse_xsd

        return parse_xsd(src, path, nation)
    elif fmt == "json-sample":
        from rosetta.core.parsers.json_sample_parser import parse_json_sample

        return parse_json_sample(src, path, nation, max_sample_rows)
    else:
        raise ValueError(
            f"Unknown input format: {fmt!r}. Use csv, json-schema, openapi, xsd, or json-sample."
        )
