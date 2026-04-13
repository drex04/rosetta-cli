"""Unit tests for accreditation state machine and CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from rosetta.cli.accredit import cli
from rosetta.core.accredit import (
    approve_mapping,
    load_ledger,
    revoke_mapping,
    save_ledger,
    submit_mapping,
)
from rosetta.core.models import Ledger

SRC = "http://example.org/NOR#field1"
TGT = "http://nato.int/master#Concept1"


def test_submit_creates_pending() -> None:
    ledger = Ledger()
    entry = submit_mapping(ledger, SRC, TGT, actor="alice")
    assert entry.status == "pending"
    assert entry.source_uri == SRC
    assert entry.target_uri == TGT
    assert len(ledger.mappings) == 1


def test_submit_duplicate_raises() -> None:
    ledger = Ledger()
    submit_mapping(ledger, SRC, TGT, actor="alice")
    with pytest.raises(ValueError, match="already exists"):
        submit_mapping(ledger, SRC, TGT, actor="bob")


def test_approve_pending_succeeds() -> None:
    ledger = Ledger()
    submit_mapping(ledger, SRC, TGT, actor="alice")
    entry = approve_mapping(ledger, SRC, TGT)
    assert entry.status == "accredited"


def test_approve_wrong_state_raises() -> None:
    ledger = Ledger()
    submit_mapping(ledger, SRC, TGT, actor="alice")
    approve_mapping(ledger, SRC, TGT)
    with pytest.raises(ValueError, match="Cannot approve"):
        approve_mapping(ledger, SRC, TGT)


def test_revoke_accredited_succeeds() -> None:
    ledger = Ledger()
    submit_mapping(ledger, SRC, TGT, actor="alice")
    approve_mapping(ledger, SRC, TGT)
    entry = revoke_mapping(ledger, SRC, TGT)
    assert entry.status == "revoked"


def test_revoke_wrong_state_raises() -> None:
    ledger = Ledger()
    submit_mapping(ledger, SRC, TGT, actor="alice")
    with pytest.raises(ValueError, match="Cannot revoke"):
        revoke_mapping(ledger, SRC, TGT)


def test_load_save_roundtrip(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger = Ledger()
    submit_mapping(ledger, SRC, TGT, actor="alice")
    approve_mapping(ledger, SRC, TGT)
    save_ledger(ledger, ledger_path)

    loaded = load_ledger(ledger_path)
    assert len(loaded.mappings) == 1
    assert loaded.mappings[0].status == "accredited"
    assert loaded.mappings[0].source_uri == SRC


def test_status_cli_json_output(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    runner = CliRunner()
    # Submit first
    result = runner.invoke(
        cli, ["--ledger", str(ledger_path), "submit", "--source", SRC, "--target", TGT]
    )
    assert result.exit_code == 0

    # Check status
    result = runner.invoke(cli, ["--ledger", str(ledger_path), "status"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["status"] == "pending"


def test_submit_cli_exit_0(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    runner = CliRunner()
    result = runner.invoke(
        cli, ["--ledger", str(ledger_path), "submit", "--source", SRC, "--target", TGT]
    )
    assert result.exit_code == 0
    assert ledger_path.exists()


def test_approve_cli_error_on_nonexistent(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.json"
    runner = CliRunner()
    result = runner.invoke(
        cli, ["--ledger", str(ledger_path), "approve", "--source", SRC, "--target", TGT]
    )
    assert result.exit_code == 1
