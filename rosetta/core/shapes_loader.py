"""Recursive, symlink-safe loader for SHACL shapes directories.

Used by ``rosetta validate`` and (after Plan 19-03) ``rosetta run --validate``.

Core-layer module: stays framework-agnostic. Raises stdlib ``ValueError`` on
user-visible input problems; CLI callers wrap these into ``click.UsageError``.
Non-fatal warnings are written straight to ``sys.stderr`` (no ``click`` import).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import rdflib
from rdflib.namespace import RDF

# SHACL namespace constant (private — single source of truth for sh:NodeShape /
# sh:PropertyShape detection inside this module).
_SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")


def _walk_ttl_files(shapes_dir: Path) -> list[Path]:
    """Return every ``*.ttl`` under ``shapes_dir``, sorted, symlink-loop-safe."""
    ttl_files: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(shapes_dir, followlinks=False):
        for fname in filenames:
            if fname.endswith(".ttl"):
                ttl_files.append(Path(dirpath) / fname)
    ttl_files.sort()
    return ttl_files


def _parse_single_shapes_file(path: Path) -> rdflib.Graph:
    """Parse one Turtle shapes file; re-raise parse errors with the file path."""
    g = rdflib.Graph()
    try:
        g.parse(str(path), format="turtle")
    except Exception as exc:
        raise ValueError(f"Failed to parse shapes file {path}: {exc}") from exc
    _warn_if_no_shapes(path, g)
    return g


def _warn_if_no_shapes(path: Path, g: rdflib.Graph) -> None:
    """Emit a stderr warning if ``g`` contains no sh:NodeShape/sh:PropertyShape."""
    n_node = sum(1 for _ in g.triples((None, RDF.type, _SH.NodeShape)))
    n_prop = sum(1 for _ in g.triples((None, RDF.type, _SH.PropertyShape)))
    if n_node + n_prop == 0:
        print(
            f"WARNING: {path} contains no SHACL shapes "
            f"(no sh:NodeShape or sh:PropertyShape triples) — "
            f"file will still be merged into the shapes graph",
            file=sys.stderr,
        )


def load_shapes_from_dir(shapes_dir: Path) -> rdflib.Graph:
    """Recursively load ``*.ttl`` shapes from ``shapes_dir`` into a single graph.

    - Walks with ``os.walk(followlinks=False)`` — symlink loops cannot hang.
    - Rejects non-directory / missing paths early with ``ValueError``.
    - Sorts file list (alphabetical by full path) for deterministic merge order.
    - For each file: parses as Turtle, counts ``sh:NodeShape`` + ``sh:PropertyShape``
      triples; if zero, emits a stderr warning but still merges (open-world
      principle — user explicitly put it in ``--shapes``).
    - Raises ``ValueError`` if no ``.ttl`` files are found at all, or if any
      ``.ttl`` file fails to parse (error message includes the offending path
      so users do not get an unattributed rdflib trace).
    """
    if not shapes_dir.is_dir():
        raise ValueError(f"--shapes {shapes_dir} is not a directory (or does not exist).")

    ttl_files = _walk_ttl_files(shapes_dir)
    if not ttl_files:
        raise ValueError(f"--shapes {shapes_dir} contained no .ttl files (recursive walk).")

    merged = rdflib.Graph()
    for f in ttl_files:
        merged += _parse_single_shapes_file(f)
    return merged


def load_shapes(shapes_path: Path) -> rdflib.Graph:
    """Load SHACL shapes from a file or directory.

    If ``shapes_path`` is a file, parse it directly as Turtle.
    If ``shapes_path`` is a directory, delegate to :func:`load_shapes_from_dir`.
    """
    if not shapes_path.exists():
        raise ValueError(f"--shapes {shapes_path} does not exist.")

    if shapes_path.is_file():
        return _parse_single_shapes_file(shapes_path)

    return load_shapes_from_dir(shapes_path)
