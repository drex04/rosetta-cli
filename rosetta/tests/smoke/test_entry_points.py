"""Subprocess smoke tests — verify the `rosetta` CLI dispatches subcommands."""

from __future__ import annotations

import shutil
import subprocess

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.e2e]


def _skip_if_not_installed() -> None:
    if shutil.which("rosetta") is None:
        pytest.skip("rosetta not installed — run `uv sync` first")


_ALL_SUBCOMMANDS = [
    "ingest",
    "translate",
    "embed",
    "suggest",
    "lint",
    "validate",
    "compile",
    "run",
    "accredit",
    "shacl-gen",
]


@pytest.mark.parametrize("subcmd", _ALL_SUBCOMMANDS)
def test_subcommand_help(subcmd: str) -> None:
    _skip_if_not_installed()
    result = subprocess.run(
        ["rosetta", subcmd, "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, f"rosetta {subcmd} --help failed: {result.stderr}"
    assert "Usage:" in result.stdout


def test_rosetta_version() -> None:
    _skip_if_not_installed()
    result = subprocess.run(
        ["rosetta", "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0
    assert "rosetta" in result.stdout
