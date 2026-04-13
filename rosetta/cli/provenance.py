"""rosetta-provenance: Record and query provenance metadata."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import click

from rosetta.core.models import ProvenanceRecord
from rosetta.core.provenance import query_provenance, stamp_artifact
from rosetta.core.rdf_utils import ROSE_NS, load_graph, save_graph


@click.group()
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
@click.pass_context
def cli(ctx: click.Context, config: str | None) -> None:
    """Record and query provenance metadata for mapping decisions."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


@cli.command()
@click.argument("input_path", metavar="INPUT")
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output path. Use '-' for stdout. Omit to overwrite INPUT in-place.",
)
@click.option(
    "--agent",
    default="http://rosetta.interop/ns/agent/rosetta-cli",
    help="Agent URI for this stamp event.",
)
@click.option("--label", "-l", default=None, help="Human-readable label for this stamp event.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Format for stamp summary printed to stderr.",
)
def stamp(
    input_path: str,
    output: str | None,
    agent: str,
    label: str | None,
    fmt: str,
) -> None:
    """Stamp PROV-O metadata onto INPUT.

    Artifact URI is derived as rose:<stem> from the input filename.
    Files with the same stem in different directories share an artifact URI.
    """
    try:
        g = load_graph(Path(input_path))
        artifact_uri = str(ROSE_NS[Path(input_path).stem])
        new_version = stamp_artifact(g, artifact_uri, agent, label)

        # Determine output destination
        if output == "-":
            save_graph(g, sys.stdout)
        elif output is not None:
            save_graph(g, Path(output))
        else:
            save_graph(g, Path(input_path))

        # Build stamp summary (report to stderr)
        now_str = datetime.now(UTC).isoformat()
        record = ProvenanceRecord(
            activity_uri=f"{ROSE_NS}activity/summary",
            agent_uri=agent,
            label=label,
            started_at=now_str,
            ended_at=now_str,
            version=new_version,
        )
        if fmt == "json":
            click.echo(json.dumps(record.model_dump(mode="json"), indent=2), err=True)
        else:
            click.echo(f"Stamped {artifact_uri} version {new_version}", err=True)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("input_path", metavar="INPUT")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def query(input_path: str, fmt: str) -> None:
    """Query provenance records stamped onto INPUT."""
    try:
        g = load_graph(Path(input_path))
        artifact_uri = str(ROSE_NS[Path(input_path).stem])
        records = query_provenance(g, artifact_uri)

        if not records:
            click.echo("No provenance records found.", err=True)
            sys.exit(0)

        if fmt == "json":
            print(json.dumps([r.model_dump(mode="json") for r in records], indent=2))
        else:
            for r in records:
                lbl = r.label or "(no label)"
                print(f"v{r.version}  {r.started_at}  {r.agent_uri}  {lbl}")
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
