"""I/O helpers for Unix-composable stdin/stdout support."""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

import click


@contextmanager
def open_input(path: str | Path | None) -> Generator[TextIO, None, None]:
    """Open *path* for reading; yield stdin if path is None or '-'.

    The context manager does NOT close stdin when exiting.
    """
    if path is None or path == "-":
        yield sys.stdin
    else:
        fh = open(path, encoding="utf-8")
        try:
            yield fh
        finally:
            fh.close()


@contextmanager
def open_output(path: str | Path | None) -> Generator[TextIO, None, None]:
    """Open *path* for writing; yield stdout if path is None or '-'.

    The context manager does NOT close stdout when exiting.
    """
    if path is None or path == "-":
        yield sys.stdout
    else:
        fh = open(path, "w", encoding="utf-8")
        try:
            yield fh
        finally:
            fh.close()


def resolve_output_paths(
    schema_files: tuple[str, ...],
    output: Path | None,
) -> list[tuple[Path, Path | None]]:
    """Resolve (input_path, output_path | None) pairs for one or many schema files.

    Rules:
    - 1 input + no -o            → stdout  (output_path is None)
    - 1 input + -o file.yaml     → write to file
    - 1 input + -o dir/ or dir   → write to dir/{stem}.linkml.yaml
    - N inputs + no -o           → write each to ./{stem}.linkml.yaml
    - N inputs + -o dir          → write each to dir/{stem}.linkml.yaml; mkdir -p
    - N inputs + -o file.yaml    → UsageError
    - N inputs + -o -            → UsageError
    """
    if len(schema_files) == 1:
        return [_resolve_single(Path(schema_files[0]), output)]
    return _resolve_multi(schema_files, output)


def _resolve_single(input_path: Path, output: Path | None) -> tuple[Path, Path | None]:
    """Resolve output for a single input file."""
    if output is None or str(output) == "-":
        return (input_path, None)
    if _is_dir_target(output):
        output.mkdir(parents=True, exist_ok=True)
        return (input_path, output / f"{input_path.stem}.linkml.yaml")
    return (input_path, output)


def _resolve_multi(
    schema_files: tuple[str, ...], output: Path | None
) -> list[tuple[Path, Path | None]]:
    """Resolve outputs for multiple input files."""
    if output is not None and str(output) == "-":
        raise click.UsageError("Multiple inputs cannot write to stdout (-o -).")
    if output is not None and not _is_dir_target(output):
        raise click.UsageError(
            f"Multiple inputs require -o to be a directory, got a file path: {output}"
        )
    out_dir = output if output is not None else Path()
    if output is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    pairs = [(Path(sf), out_dir / f"{Path(sf).stem}.linkml.yaml") for sf in schema_files]
    seen: dict[Path, Path] = {}
    for src, dst in pairs:
        if dst in seen:
            raise click.UsageError(
                f"Duplicate output stem: {src} and {seen[dst]} both resolve to {dst.name}"
            )
        seen[dst] = src
    return pairs  # pyright: ignore[reportReturnType]


def _is_dir_target(path: Path) -> bool:
    """Return True if *path* should be treated as a directory target.

    A path is a directory target if it already exists as a directory,
    or if its string form ends with a path separator.
    """
    return path.is_dir() or str(path).endswith(("/", "\\"))
