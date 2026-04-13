"""XSD parser stub — full implementation in phase 11-01."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from rosetta.core.parsers._types import FieldSchema


def parse_xsd(
    src: TextIO,
    path: Path | None,
    nation: str,
) -> tuple[list[FieldSchema], str]:
    """Parse an XSD schema file into FieldSchema objects.

    Not yet implemented — placeholder for phase 11-01.
    """
    raise NotImplementedError("XSD parser is not yet implemented.")
