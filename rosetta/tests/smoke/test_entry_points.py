"""Subprocess smoke tests — verify installed console scripts resolve."""

from __future__ import annotations

import shutil
import subprocess

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.e2e]


def _skip_if_not_installed(name: str) -> None:
    if shutil.which(name) is None:
        pytest.skip(f"{name} not installed — run `uv sync` first")


def test_rosetta_ingest_entry_point() -> None:
    _skip_if_not_installed("rosetta-ingest")
    result = subprocess.run(
        ["rosetta-ingest", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Normalise a schema file" in result.stdout
    assert "--format" in result.stdout


def test_rosetta_yarrrml_gen_entry_point() -> None:
    _skip_if_not_installed("rosetta-yarrrml-gen")
    result = subprocess.run(
        ["rosetta-yarrrml-gen", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0
    assert "--sssom" in result.stdout
    assert "--run" in result.stdout
