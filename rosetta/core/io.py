"""I/O helpers for Unix-composable stdin/stdout support."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, TextIO


@contextmanager
def open_input(path: str | Path | None) -> Generator[TextIO, None, None]:
    """Open *path* for reading; yield stdin if path is None or '-'.

    The context manager does NOT close stdin when exiting.
    """
    if path is None or path == "-":
        yield sys.stdin
    else:
        fh = open(path, "r", encoding="utf-8")
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
