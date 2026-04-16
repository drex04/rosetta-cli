"""rosetta-suggest: Rank master ontology candidates for source schema fields (SSSOM TSV output)."""

import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

import click
import numpy as np

from rosetta.core.accredit import DATETIME_MIN, load_log
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
    "mapping_date",
    "record_id",
    "subject_datatype",
    "object_datatype",
    "subject_type",
    "object_type",
    "mapping_group_id",
    "composition_expr",
]


@click.command()
@click.argument("source", type=click.Path(exists=True))
@click.argument("master", type=click.Path(exists=True))
@click.option("--top-k", default=None, type=int, help="Max suggestions per field")
@click.option("--min-score", default=None, type=float, help="Minimum cosine score")
@click.option("--output", default=None, type=click.Path(), help="Output file (default: stdout)")
@click.option("--config", default="rosetta.toml", show_default=True)
def cli(
    source: str,
    master: str,
    top_k: int | None,
    min_score: float | None,
    output: str | None,
    config: str,
) -> None:
    """Rank master ontology candidates for source schema fields (SSSOM TSV output)."""
    cfg = load_config(Path(config))
    resolved_top_k = int(get_config_value(cfg, "suggest", "top_k", cli_value=top_k) or 5)
    resolved_min_score = float(
        get_config_value(cfg, "suggest", "min_score", cli_value=min_score) or 0.0
    )

    # Load audit log if configured
    log_path_str: str | None = get_config_value(cfg, "accredit", "log", cli_value=None)
    log: list[SSSOMRow] = []
    if log_path_str:
        lp = Path(log_path_str)
        if lp.exists():
            log = load_log(lp)

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

        _raw_structural_weight = get_config_value(
            cfg, "suggest", "structural_weight", cli_value=None
        )
        resolved_structural_weight: float = (
            float(_raw_structural_weight) if _raw_structural_weight is not None else 0.2
        )

        # Build structural numpy arrays (empty structural → zero-row matrix → fallback triggers)
        src_structs = [src_report.root[u].structural for u in src_uris]
        master_structs = [master_report.root[u].structural for u in master_uris]

        struct_dim = max((len(v) for v in src_structs + master_structs), default=0)
        A_struct: np.ndarray | None = None
        B_struct: np.ndarray | None = None
        if struct_dim > 0:
            A_struct = np.array([v or [0.0] * struct_dim for v in src_structs], dtype=np.float32)
            B_struct = np.array([v or [0.0] * struct_dim for v in master_structs], dtype=np.float32)

        src_has_struct = any(len(v) > 0 for v in src_structs)
        master_has_struct = any(len(v) > 0 for v in master_structs)
        if src_has_struct != master_has_struct:
            click.echo(
                "Warning: structural arrays present in one embed file but not the other"
                " — falling back to lexical-only",
                err=True,
            )

        blending_active = (
            A_struct is not None
            and B_struct is not None
            and np.any(A_struct != 0)
            and np.any(B_struct != 0)  # pyright: ignore[reportOperatorIssue]
            and resolved_structural_weight > 0.0
        )
        mapping_justification = (
            "semapv:CompositeMatching" if blending_active else "semapv:LexicalMatching"
        )

        # Compute ranked suggestions
        result = rank_suggestions(
            src_uris,
            A,
            master_uris,
            B,
            resolved_top_k,
            resolved_min_score,
            A_struct=A_struct,
            B_struct=B_struct,
            structural_weight=resolved_structural_weight,
        )

        # Apply per-field boost/derank from HumanCuration log rows
        hc_rows = [r for r in log if r.mapping_justification == "semapv:HumanCuration"]
        if hc_rows:
            for src_uri, entry in result.items():
                entry["suggestions"] = apply_sssom_feedback(src_uri, entry["suggestions"], hc_rows)

        # Build index: (subject_id, object_id) -> latest non-CompositeMatching log row
        log_index: dict[tuple[str, str], SSSOMRow] = {}
        for row in log:
            if row.mapping_justification != "semapv:CompositeMatching":
                key = (row.subject_id, row.object_id)
                existing = log_index.get(key)
                if existing is None or (row.mapping_date or DATETIME_MIN) >= (
                    existing.mapping_date or DATETIME_MIN
                ):
                    log_index[key] = row

        # For each candidate in result: if pair is in log_index, refresh justification/predicate
        for src_uri, entry in result.items():
            for cand in entry["suggestions"]:
                key = (src_uri, cand["uri"])
                if key in log_index:
                    log_row = log_index[key]
                    cand["mapping_justification"] = log_row.mapping_justification
                    cand["predicate_id"] = log_row.predicate_id

        # --- SSSOM TSV output ---
        sssom_rows: list[SSSOMRow] = []
        for src_uri, field_data in result.items():
            candidates_tsv: list[dict[str, Any]] = field_data["suggestions"]  # pyright: ignore[reportAny]

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
                        predicate_id=cand.get("predicate_id") or "skos:relatedMatch",
                        object_id=obj_uri,
                        mapping_justification=(
                            cand.get("mapping_justification") or mapping_justification
                        ),
                        confidence=score,
                        subject_label=src_label,
                        object_label=obj_label,
                        mapping_date=cand.get("mapping_date") or None,  # pyright: ignore[reportAny]
                        record_id=cand.get("record_id") or None,  # pyright: ignore[reportAny]
                        subject_datatype=src_report.root[src_uri].datatype,
                        object_datatype=(
                            master_report.root[obj_uri].datatype
                            if obj_uri in master_report.root
                            else None
                        ),
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
                        row.mapping_date.isoformat() if row.mapping_date else "",
                        row.record_id or "",
                        row.subject_datatype or "",
                        row.object_datatype or "",
                        row.subject_type or "",
                        row.object_type or "",
                        row.mapping_group_id or "",
                        row.composition_expr or "",
                    ]
                )
            fh.write(buf.getvalue())

    except (ValueError, OSError, json.JSONDecodeError, KeyError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
