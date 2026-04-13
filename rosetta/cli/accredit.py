"""rosetta-accredit: Manage mapping accreditation state."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from rosetta.core.accredit import (
    approve_mapping,
    load_ledger,
    revoke_mapping,
    save_ledger,
    submit_mapping,
)


@click.group()
@click.option(
    "--ledger",
    default="store/ledger.json",
    show_default=True,
    help="Path to ledger.json",
)
@click.option("--config", "-c", default=None, help="Path to rosetta.toml")
@click.pass_context
def cli(ctx: click.Context, ledger: str, config: str | None) -> None:
    """Manage mapping accreditation state."""
    ctx.ensure_object(dict)
    ctx.obj["ledger_path"] = Path(ledger)


@cli.command("submit")
@click.option("--source", required=True, help="Source field URI")
@click.option("--target", required=True, help="Target ontology URI")
@click.option("--actor", default="anonymous", show_default=True, help="Submitter identity")
@click.option("--notes", default="", help="Free-text notes")
@click.pass_context
def submit(ctx: click.Context, source: str, target: str, actor: str, notes: str) -> None:
    """Submit a mapping for review (pending state)."""
    ledger_path: Path = ctx.obj["ledger_path"]
    try:
        led = load_ledger(ledger_path)
        entry = submit_mapping(led, source, target, actor=actor, notes=notes)
        save_ledger(led, ledger_path)
        click.echo(json.dumps({"status": "ok", "entry": entry.model_dump(mode="json")}, indent=2))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("approve")
@click.option("--source", required=True)
@click.option("--target", required=True)
@click.pass_context
def approve(ctx: click.Context, source: str, target: str) -> None:
    """Approve a pending mapping."""
    ledger_path: Path = ctx.obj["ledger_path"]
    try:
        led = load_ledger(ledger_path)
        entry = approve_mapping(led, source, target)
        save_ledger(led, ledger_path)
        click.echo(json.dumps({"status": "ok", "entry": entry.model_dump(mode="json")}, indent=2))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("revoke")
@click.option("--source", required=True)
@click.option("--target", required=True)
@click.pass_context
def revoke(ctx: click.Context, source: str, target: str) -> None:
    """Revoke an accredited mapping."""
    ledger_path: Path = ctx.obj["ledger_path"]
    try:
        led = load_ledger(ledger_path)
        entry = revoke_mapping(led, source, target)
        save_ledger(led, ledger_path)
        click.echo(json.dumps({"status": "ok", "entry": entry.model_dump(mode="json")}, indent=2))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("status")
@click.option("--source", default=None, help="Filter by source URI")
@click.option("--target", default=None, help="Filter by target URI")
@click.pass_context
def status(ctx: click.Context, source: str | None, target: str | None) -> None:
    """Show accreditation status. Outputs JSON array of matching entries."""
    ledger_path: Path = ctx.obj["ledger_path"]
    try:
        led = load_ledger(ledger_path)
        entries = led.mappings
        if source is not None:
            entries = [e for e in entries if e.source_uri == source]
        if target is not None:
            entries = [e for e in entries if e.target_uri == target]
        click.echo(json.dumps([e.model_dump(mode="json") for e in entries], indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
