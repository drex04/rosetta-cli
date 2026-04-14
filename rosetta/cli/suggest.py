"""rosetta-suggest: Rank master ontology candidates for source schema fields (SSSOM TSV output)."""

import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

import click
import numpy as np

from rosetta.core.config import get_config_value, load_config
from rosetta.core.io import open_output
from rosetta.core.models import (
    EmbeddingReport,
    SSSOMRow,
)
from rosetta.core.similarity import apply_sssom_feedback, rank_suggestions

_SSSOM_HEADER_LINES = [
    "# mapping_set_id: https://rosetta-cli/mappings",
    "# mapping_tool: rosetta-suggest",
    "# license: https://creativecommons.org/licenses/by/4.0/",
    "# curie_map:",
    "#   skos: http://www.w3.org/2004/02/skos/core#",
    "#   semapv: https://w3id.org/semapv/vocab/",
]

_SSSOM_COLUMNS = [
    "subject_id",
    "predicate_id",
    "object_id",
    "mapping_justification",
    "confidence",
    "subject_label",
    "object_label",
]


def _parse_sssom_tsv(path: Path) -> list[SSSOMRow]:
    """Parse an SSSOM TSV file and return a list of SSSOMRow objects.

    Skips comment lines (starting with '#') and rows with missing required fields.
    """
    rows: list[SSSOMRow] = []
    with path.open(encoding="utf-8") as fh:
        non_comment_lines: list[str] = []
        for line in fh:
            if not line.startswith("#"):
                non_comment_lines.append(line)

    if not non_comment_lines:
        return rows

    reader = csv.DictReader(non_comment_lines, delimiter="\t")
    for row in reader:
        subject_id = (row.get("subject_id") or "").strip()
        predicate_id = (row.get("predicate_id") or "").strip()
        object_id = (row.get("object_id") or "").strip()
        mapping_justification = (row.get("mapping_justification") or "").strip()
        if not (subject_id and predicate_id and object_id and mapping_justification):
            continue
        confidence_raw = (row.get("confidence") or "").strip()
        confidence = float(confidence_raw) if confidence_raw else 0.0
        rows.append(
            SSSOMRow(
                subject_id=subject_id,
                predicate_id=predicate_id,
                object_id=object_id,
                mapping_justification=mapping_justification,
                confidence=confidence,
            )
        )
    return rows


@click.command()
@click.argument("source", type=click.Path(exists=True))
@click.argument("master", type=click.Path(exists=True))
@click.option("--top-k", default=None, type=int, help="Max suggestions per field")
@click.option("--min-score", default=None, type=float, help="Minimum cosine score")
@click.option(
    "--approved-mappings",
    default=None,
    type=click.Path(),
    help="Path to an approved mappings .sssom.tsv file",
)
@click.option("--output", default=None, type=click.Path(), help="Output file (default: stdout)")
@click.option("--config", default="rosetta.toml", show_default=True)
def cli(
    source: str,
    master: str,
    top_k: int | None,
    min_score: float | None,
    approved_mappings: str | None,
    output: str | None,
    config: str,
) -> None:
    """Rank master ontology candidates for source schema fields (SSSOM TSV output)."""
    cfg = load_config(Path(config))
    resolved_top_k = int(get_config_value(cfg, "suggest", "top_k", cli_value=top_k) or 5)
    resolved_min_score = float(
        get_config_value(cfg, "suggest", "min_score", cli_value=min_score) or 0.0
    )

    # Validate --approved-mappings path up front (before heavy processing)
    approved_path: Path | None = None
    if approved_mappings is not None:
        approved_path = Path(approved_mappings)
        if not approved_path.exists():
            click.echo(f"Approved mappings file not found: {approved_mappings}", err=True)
            sys.exit(1)

    try:
        src_raw = json.loads(Path(source).read_text())
        master_raw = json.loads(Path(master).read_text())

        if not src_raw:
            click.echo(f"No embeddings found in source file: {source}")
            sys.exit(1)
        if not master_raw:
            click.echo(f"No embeddings found in master file: {master}")
            sys.exit(1)

        # Validate and build numpy arrays
        for uri, val in src_raw.items():
            if "lexical" not in val:
                raise ValueError(f"Missing 'lexical' key for URI: {uri}")
        for uri, val in master_raw.items():
            if "lexical" not in val:
                raise ValueError(f"Missing 'lexical' key for URI: {uri}")

        # Parse via EmbeddingReport for typed access
        src_report = EmbeddingReport.model_validate(src_raw)
        master_report = EmbeddingReport.model_validate(master_raw)

        src_uris = list(src_report.root.keys())
        master_uris = list(master_report.root.keys())

        A = np.array([src_report.root[u].lexical for u in src_uris], dtype=np.float32)
        B = np.array([master_report.root[u].lexical for u in master_uris], dtype=np.float32)

        # Load approved mappings if provided
        approved_rows: list[SSSOMRow] = []
        if approved_path is not None:
            approved_rows = _parse_sssom_tsv(approved_path)

        # Compute ranked suggestions
        result = rank_suggestions(src_uris, A, master_uris, B, resolved_top_k, resolved_min_score)

        # --- SSSOM TSV output ---
        sssom_rows: list[SSSOMRow] = []
        for src_uri, field_data in result.items():
            candidates_tsv: list[dict[str, Any]] = field_data["suggestions"]  # pyright: ignore[reportAny]

            # Apply SSSOM feedback if approved mappings present
            if approved_rows:
                candidates_tsv = apply_sssom_feedback(src_uri, candidates_tsv, approved_rows)

            src_label = src_report.root[src_uri].label

            for cand in candidates_tsv:
                obj_uri: str = cand["uri"]  # pyright: ignore[reportAny]
                score: float = cand["score"]  # pyright: ignore[reportAny]
                obj_label = (
                    master_report.root[obj_uri].label if obj_uri in master_report.root else ""
                )

                sssom_rows.append(
                    SSSOMRow(
                        subject_id=src_uri,
                        predicate_id="skos:relatedMatch",
                        object_id=obj_uri,
                        mapping_justification="semapv:LexicalMatching",
                        confidence=score,
                        subject_label=src_label,
                        object_label=obj_label,
                    )
                )

        # Write SSSOM TSV
        with open_output(output) as fh:
            for line in _SSSOM_HEADER_LINES:
                fh.write(line + "\n")

            buf = io.StringIO()
            writer = csv.writer(buf, delimiter="\t", lineterminator="\n")
            writer.writerow(_SSSOM_COLUMNS)
            for row in sssom_rows:
                writer.writerow(
                    [
                        row.subject_id,
                        row.predicate_id,
                        row.object_id,
                        row.mapping_justification,
                        row.confidence,
                        row.subject_label,
                        row.object_label,
                    ]
                )
            fh.write(buf.getvalue())

    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)
