"""Recursive, symlink-safe loader for SHACL shapes directories.

Used by ``rosetta-validate`` and (after Plan 19-03) ``rosetta-yarrrml-gen --validate``.
"""

from __future__ import annotations

import os
from pathlib import Path

import click
import rdflib
from rdflib.namespace import RDF

# SHACL namespace constant (private — single source of truth for sh:NodeShape /
# sh:PropertyShape detection inside this module).
_SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")


def load_shapes_from_dir(shapes_dir: Path) -> rdflib.Graph:
    """Recursively load ``*.ttl`` shapes from ``shapes_dir`` into a single graph.

    - Walks with ``os.walk(followlinks=False)`` — symlink loops cannot hang.
    - Sorts file list (alphabetical by full path) for deterministic merge order.
    - For each file: parses as Turtle, counts ``sh:NodeShape`` + ``sh:PropertyShape``
      triples; if zero, emits a ``click.echo`` stderr warning but still merges
      (open-world principle — user explicitly put it in ``--shapes-dir``).
    - Raises ``click.UsageError`` if no ``.ttl`` files are found at all.
    """
    ttl_files: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(shapes_dir, followlinks=False):
        for fname in filenames:
            if fname.endswith(".ttl"):
                ttl_files.append(Path(dirpath) / fname)

    ttl_files.sort()

    if not ttl_files:
        raise click.UsageError(
            f"--shapes-dir {shapes_dir} contained no .ttl files (recursive walk)."
        )

    merged = rdflib.Graph()
    for f in ttl_files:
        g = rdflib.Graph()
        g.parse(str(f), format="turtle")
        n_node = sum(1 for _ in g.triples((None, RDF.type, _SH.NodeShape)))
        n_prop = sum(1 for _ in g.triples((None, RDF.type, _SH.PropertyShape)))
        if n_node + n_prop == 0:
            click.echo(
                f"WARNING: {f} contains no SHACL shapes "
                f"(no sh:NodeShape or sh:PropertyShape triples) — "
                f"file will still be merged into the shapes graph",
                err=True,
            )
        merged += g

    return merged
