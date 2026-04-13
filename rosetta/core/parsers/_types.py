"""Shared types for rosetta parsers — split out to avoid circular imports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldSchema:
    name: str  # original field name from source
    data_type: str  # "string" | "number" | "integer" | "boolean"
    description: str = ""
    required: bool = False
    detected_unit: str | None = None
    sample_values: list[str | float | int | bool | None] = field(default_factory=list)
    numeric_stats: dict[str, Any] | None = None  # populated by compute_stats()
    categorical_stats: dict[str, Any] | None = None  # populated by compute_stats()


def schema_slug(title: str) -> str:
    """Convert a schema title or $id segment to a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    if not slug:
        raise ValueError(
            f"Schema title {title!r} produced an empty slug after normalisation. "
            "Use a title containing at least one ASCII letter or digit."
        )
    return slug
