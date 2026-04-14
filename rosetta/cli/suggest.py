"""rosetta-suggest: Rank master ontology candidates for source schema fields."""

import json
import sys
from pathlib import Path

import click
import numpy as np

from rosetta.core.accredit import load_ledger
from rosetta.core.config import get_config_value, load_config
from rosetta.core.io import open_output
from rosetta.core.models import FieldSuggestions, Suggestion, SuggestionReport
from rosetta.core.similarity import apply_ledger_feedback, rank_suggestions


@click.command()
@click.option(
    "--source", required=True, type=click.Path(exists=True), help="Source embeddings JSON"
)
@click.option(
    "--master", required=True, type=click.Path(exists=True), help="Master embeddings JSON"
)
@click.option("--top-k", default=None, type=int, help="Max suggestions per field")
@click.option("--min-score", default=None, type=float, help="Minimum cosine score")
@click.option("--anomaly-threshold", default=None, type=float, help="Anomaly flag threshold")
@click.option("--output", default=None, type=click.Path(), help="Output file (default: stdout)")
@click.option("--ledger", default=None, type=click.Path(), help="Path to accreditation ledger.json")
@click.option("--config", default="rosetta.toml", show_default=True)
def cli(
    source: str,
    master: str,
    top_k: int | None,
    min_score: float | None,
    anomaly_threshold: float | None,
    output: str | None,
    ledger: str | None,
    config: str,
) -> None:
    """Rank master ontology candidates for source schema fields."""
    cfg = load_config(Path(config))
    resolved_top_k = int(get_config_value(cfg, "suggest", "top_k", cli_value=top_k) or 5)
    resolved_min_score = float(
        get_config_value(cfg, "suggest", "min_score", cli_value=min_score) or 0.0
    )
    resolved_anomaly_threshold = float(
        get_config_value(cfg, "suggest", "anomaly_threshold", cli_value=anomaly_threshold) or 0.3
    )

    try:
        src_emb = json.loads(Path(source).read_text())
        master_emb = json.loads(Path(master).read_text())

        if not src_emb:
            click.echo(f"No embeddings found in source file: {source}", err=True)
            sys.exit(1)
        if not master_emb:
            click.echo(f"No embeddings found in master file: {master}", err=True)
            sys.exit(1)

        for uri, val in src_emb.items():
            if "lexical" not in val:
                raise ValueError(f"Missing 'lexical' key for URI: {uri}")
        src_uris = list(src_emb)
        A = np.array([src_emb[u]["lexical"] for u in src_uris], dtype=np.float32)
        src_labels = {
            u: val.get("label") or u.split("/")[-1].replace("_", " ").title()
            for u, val in src_emb.items()
        }

        for uri, val in master_emb.items():
            if "lexical" not in val:
                raise ValueError(f"Missing 'lexical' key for URI: {uri}")
        master_uris = list(master_emb)
        B = np.array([master_emb[u]["lexical"] for u in master_uris], dtype=np.float32)
        master_labels = {
            u: val.get("label") or u.split("/")[-1].replace("_", " ").title()
            for u, val in master_emb.items()
        }

        result = rank_suggestions(
            src_uris,
            A,
            master_uris,
            B,
            resolved_top_k,
            resolved_min_score,
            resolved_anomaly_threshold,
        )

        if ledger is not None:
            led = load_ledger(Path(ledger))
            for src_uri, field_data in result.items():
                field_data["suggestions"] = apply_ledger_feedback(
                    src_uri, field_data["suggestions"], led
                )
                # Re-sort by new score descending; re-assign 1-based ranks
                field_data["suggestions"].sort(key=lambda s: s["score"], reverse=True)
                for rank_idx, sug in enumerate(field_data["suggestions"], 1):
                    sug["rank"] = rank_idx

        report = SuggestionReport(
            root={
                uri: FieldSuggestions(
                    label=src_labels[uri],
                    suggestions=[
                        Suggestion(
                            target_uri=s["uri"],
                            label=master_labels[s["uri"]],
                            score=s["score"],
                        )
                        for s in field["suggestions"]
                    ],
                    anomaly=field["anomaly"],
                )
                for uri, field in result.items()
            }
        )
        with open_output(output) as fh:
            fh.write(report.model_dump_json(indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
