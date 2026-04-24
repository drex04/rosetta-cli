"""morph-kgc materialization + JSON-LD framing helpers.

This module wraps the morph-kgc library to execute YARRRML mappings (as produced
by the forked ``linkml_map.compiler.yarrrml_compiler.YarrrmlCompiler``) against
concrete data files and frame the resulting ``rdflib.Graph`` as JSON-LD using a
``@context`` derived from the master LinkML schema.

Public API:
    - ``run_materialize`` — context manager yielding an ``rdflib.Graph``.
    - ``graph_to_jsonld`` — serializes a graph to JSON-LD bytes with a master-schema context.

All functions use broad rdflib types at their boundaries and raise ``RuntimeError``
or ``ValueError`` instead of letting library exceptions leak unwrapped.
"""

from __future__ import annotations

import contextlib
import json
import logging
import shutil
import tempfile
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path
from typing import Any

import morph_kgc
import rdflib
from linkml.generators.jsonldcontextgen import ContextGenerator  # type: ignore[import-untyped]

_DATA_FILE_PLACEHOLDER: str = "$(DATA_FILE)"


def _write_udf_file(work_dir: Path) -> Path:
    """Copy the rosetta UDF Python module into ``work_dir`` and return its path.

    morph-kgc loads this file via the INI ``udfs=<path>`` option and
    registers each ``@udf``-decorated function under its ``fun_id`` IRI.
    """
    udf_path = work_dir / "rosetta_udfs.py"
    try:
        source = (
            files("rosetta.functions")
            .joinpath("unit_conversion_udfs.py")
            .read_text(encoding="utf-8")
        )
        udf_path.write_text(source, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to write UDF file to {udf_path}: {exc}") from exc
    return udf_path


def _substitute_data_path(yarrrml: str, data_path: Path) -> str:
    """Replace the ``$(DATA_FILE)`` placeholder in ``yarrrml`` with ``data_path``.

    Raises ``ValueError`` if the placeholder is not present in the input text.
    """
    if _DATA_FILE_PLACEHOLDER not in yarrrml:
        raise ValueError(f"YARRRML missing {_DATA_FILE_PLACEHOLDER} placeholder")
    return yarrrml.replace(_DATA_FILE_PLACEHOLDER, str(data_path))


def _build_ini(mapping_path: Path, udf_path: Path | None = None) -> str:
    """Return a morph-kgc INI config string for a single YARRRML mapping file.

    If ``udf_path`` is given, a ``udfs=<abs-path>`` line is emitted in the
    ``[CONFIGURATION]`` block so morph-kgc registers the rosetta UDFs.
    """
    absolute = str(mapping_path.resolve())
    udf_line = f"udfs={udf_path.resolve()}\n" if udf_path is not None else ""
    return (
        f"[CONFIGURATION]\noutput_format=N-TRIPLES\n{udf_line}"
        f"\n[DataSource1]\nmappings={absolute}\n"
    )


def _generate_jsonld_context(master_schema_path: Path) -> dict[str, Any]:
    """Generate a JSON-LD ``@context`` dict from a LinkML master schema.

    Returns the inner ``@context`` dict. Raises ``ValueError`` if the serialized
    JSON does not contain an ``@context`` key (no silent fallback). Raises
    ``RuntimeError`` if the underlying ``ContextGenerator`` call fails.
    """
    try:
        generator = ContextGenerator(str(master_schema_path))  # pyright: ignore[reportUnknownVariableType]
        serialized: str = generator.serialize()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    except Exception as exc:
        raise RuntimeError(
            f"Failed to generate JSON-LD context from master schema {master_schema_path}: {exc}"
        ) from exc

    parsed: Any = json.loads(serialized)
    if not isinstance(parsed, dict) or "@context" not in parsed:
        raise ValueError("ContextGenerator output missing @context key")
    inner: Any = parsed["@context"]
    if not isinstance(inner, dict):
        raise ValueError("ContextGenerator output missing @context key")
    return inner


@contextlib.contextmanager
def run_materialize(
    yarrrml_text: str,
    data_path: Path,
    work_dir: Path | None = None,
) -> Iterator[rdflib.Graph]:
    """Materialize ``yarrrml_text`` against ``data_path`` into an ``rdflib.Graph``.

    This is a context manager. If ``work_dir`` is None an internal temporary
    directory is created and cleaned up on exit; a caller-supplied ``work_dir``
    is never cleaned up (caller owns it).

    Raises ``ValueError`` if the YARRRML lacks the ``$(DATA_FILE)`` placeholder.
    Raises ``RuntimeError`` if the mapping file cannot be written. Any
    morph-kgc error propagates unchanged.
    """
    logging.getLogger("morph_kgc").setLevel(logging.WARNING)

    owns_workdir = work_dir is None
    effective_dir: Path = (
        Path(tempfile.mkdtemp(prefix="rosetta-yarrrml-")) if owns_workdir else work_dir
    )
    # Caller-supplied dirs may not yet exist; CLI already handles this, but make
    # the runner tolerant for direct callers (tests, notebooks).
    if not owns_workdir:
        try:
            effective_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(f"Failed to create work_dir {effective_dir}: {exc}") from exc

    try:
        substituted = _substitute_data_path(yarrrml_text, data_path)
        mapping_path = effective_dir / "mapping.yml"
        try:
            mapping_path.write_text(substituted, encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Failed to write mapping file to {mapping_path}: {exc}") from exc

        udf_path = _write_udf_file(effective_dir)
        ini_string = _build_ini(mapping_path, udf_path=udf_path)
        graph: rdflib.Graph = morph_kgc.materialize(ini_string)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        yield graph
    finally:
        if owns_workdir:
            shutil.rmtree(effective_dir, ignore_errors=True)


def graph_to_jsonld(
    graph: rdflib.Graph,
    master_schema_path: Path,
    context_output: Path | None = None,
) -> bytes:
    """Serialize ``graph`` to JSON-LD bytes using a context from the master schema.

    If ``context_output`` is supplied, also writes the context dict to that path
    (indent=2, utf-8). Raises ``RuntimeError`` if serialization fails.
    """
    context_dict = _generate_jsonld_context(master_schema_path)

    if context_output is not None:
        context_output.write_text(json.dumps(context_dict, indent=2), encoding="utf-8")

    try:
        serialized = graph.serialize(format="json-ld", context=context_dict, indent=2)
    except Exception as exc:
        raise RuntimeError(f"JSON-LD serialization failed: {exc}") from exc

    if isinstance(serialized, bytes):
        return serialized
    return serialized.encode("utf-8")
