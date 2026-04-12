"""Tests for rosetta.core.io — open_input / open_output helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from rosetta.core.io import open_input, open_output


def test_open_input_file(tmp_path: Path) -> None:
    """open_input(path) reads a regular file correctly."""
    content = "Hello, Rosetta!\n"
    src = tmp_path / "input.txt"
    src.write_text(content, encoding="utf-8")

    with open_input(str(src)) as fh:
        result = fh.read()

    assert result == content


def test_open_input_stdin() -> None:
    """open_input('-') yields stdin without closing it afterward."""
    with open_input("-") as fh:
        assert fh is sys.stdin

    # stdin must still be open after the context manager exits
    assert not sys.stdin.closed


def test_open_output_stdout() -> None:
    """open_output('-') yields stdout without closing it afterward."""
    with open_output("-") as fh:
        assert fh is sys.stdout

    # stdout must still be open after the context manager exits
    assert not sys.stdout.closed
