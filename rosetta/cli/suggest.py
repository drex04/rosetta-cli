"""rosetta suggest: Rank master ontology candidates for source schema fields (SSSOM TSV output)."""

import csv
import io
import sys
from pathlib import Path
from typing import Any, cast

import click
import numpy as np
from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]
from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]

from rosetta.core.config import load_config, load_conversion_policies
from rosetta.core.embedding import EmbeddingModel, extract_text_inputs_linkml
from rosetta.core.features import extract_structural_features_linkml
from rosetta.core.function_library import FunctionLibrary
from rosetta.core.io import open_output
from rosetta.core.ledger import DATETIME_MIN, load_log
from rosetta.core.lint import populate_conversion_functions
from rosetta.core.models import SSSOM_COLUMNS, SSSOMRow
from rosetta.core.similarity import filter_decided_suggestions, rank_suggestions

_SSSOM_HEADER_LINES = [
    "# mapping_set_id: https://rosetta-cli/mappings",
    "# mapping_tool: rosetta suggest",
    "# license: https://creativecommons.org/licenses/by/4.0/",
    "# curie_map:",
    "#   skos: http://www.w3.org/2004/02/skos/core#",
    "#   semapv: https://w3id.org/semapv/vocab/",
]


@click.command(
    epilog="""Examples:

  rosetta suggest source.yaml master.yaml \\
      --audit-log audit-log.sssom.tsv -o proposals.sssom.tsv

  rosetta -v suggest source.yaml master.yaml \\
      --audit-log audit-log.sssom.tsv --top-k 10 --model intfloat/e5-large-v2"""
)
@click.argument("source_schema", type=click.Path(exists=True))
@click.argument("master_schema", type=click.Path(exists=True))
@click.option("--top-k", default=5, show_default=True, type=int, help="Max suggestions per field")
@click.option(
    "--min-score",
    default=0.0,
    show_default=True,
    type=float,
    help="Minimum cosine score",
)
@click.option(
    "-o", "--output", default=None, type=click.Path(), help="Output file (default: stdout)"
)
@click.option(
    "--structural-weight",
    default=0.2,
    show_default=True,
    type=float,
    help="Weight for structural features when blending (0.0 = lexical-only).",
)
@click.option(
    "--audit-log",
    required=True,
    type=click.Path(),
    help="Path to SSSOM audit log.",
)
@click.option(
    "--model",
    default="intfloat/e5-large-v2",
    show_default=True,
    help="Sentence-transformer model for embeddings.",
)
def cli(
    source_schema: str,
    master_schema: str,
    top_k: int,
    min_score: float,
    output: str | None,
    structural_weight: float,
    audit_log: str,
    model: str,
) -> None:
    """Rank master ontology candidates for source schema fields (SSSOM TSV output).

    SOURCE_SCHEMA and MASTER_SCHEMA are LinkML YAML schema files. Embeddings are
    computed on-the-fly using the specified sentence-transformer model.
    """
    log: list[SSSOMRow] = []
    lp = Path(audit_log)
    if lp.exists():
        log = load_log(lp)

    try:
        # Load LinkML schemas
        source_def: SchemaDefinition = cast(
            "SchemaDefinition",
            yaml_loader.load(  # pyright: ignore[reportUnknownMemberType]
                source_schema, target_class=SchemaDefinition
            ),
        )
        master_def: SchemaDefinition = cast(
            "SchemaDefinition",
            yaml_loader.load(  # pyright: ignore[reportUnknownMemberType]
                master_schema, target_class=SchemaDefinition
            ),
        )

        # Extract (node_id, label, text) triples
        src_inputs = extract_text_inputs_linkml(source_def)
        master_inputs = extract_text_inputs_linkml(master_def)

        if not src_inputs:
            click.echo(f"No nodes found in source schema: {source_schema}", err=True)
            sys.exit(1)
        if not master_inputs:
            click.echo(f"No nodes found in master schema: {master_schema}", err=True)
            sys.exit(1)

        # Build URI lists and lookup dicts
        src_uris = [uid for uid, _, _ in src_inputs]
        master_uris = [uid for uid, _, _ in master_inputs]
        src_labels = {uid: label for uid, label, _ in src_inputs}
        master_labels = {uid: label for uid, label, _ in master_inputs}
        src_texts = [text for _, _, text in src_inputs]
        master_texts = [text for _, _, text in master_inputs]

        # Build datatype lookups from schema slots
        src_schema_name: str = source_def.name or "schema"  # pyright: ignore[reportUnknownMemberType]
        src_datatypes: dict[str, str | None] = {}
        for slot_name, slot_obj in cast("dict[str, Any]", source_def.slots).items():  # pyright: ignore[reportUnknownMemberType]
            src_datatypes[f"{src_schema_name}:{slot_name}"] = getattr(slot_obj, "range", None)

        master_schema_name: str = master_def.name or "schema"  # pyright: ignore[reportUnknownMemberType]
        master_datatypes: dict[str, str | None] = {}
        for slot_name, slot_obj in cast("dict[str, Any]", master_def.slots).items():  # pyright: ignore[reportUnknownMemberType]
            master_datatypes[f"{master_schema_name}:{slot_name}"] = getattr(slot_obj, "range", None)

        # Load embedding model and encode
        click.echo("Loading embedding model...", err=True)
        try:
            embedding_model = EmbeddingModel(model)
        except OSError as exc:
            raise click.ClickException(f"Failed to load embedding model: {exc}") from exc

        src_vectors = np.array(embedding_model.encode_query(src_texts), dtype=np.float32)
        master_vectors = np.array(embedding_model.encode(master_texts), dtype=np.float32)

        # Extract structural features
        src_struct_dict = extract_structural_features_linkml(source_def)
        master_struct_dict = extract_structural_features_linkml(master_def)

        src_structs = [src_struct_dict.get(uri, []) for uri in src_uris]
        master_structs = [master_struct_dict.get(uri, []) for uri in master_uris]

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
                "Warning: structural arrays present in one schema but not the other"
                " — falling back to lexical-only",
                err=True,
            )

        blending_active = (
            A_struct is not None
            and B_struct is not None
            and np.any(A_struct != 0)
            and np.any(B_struct != 0)
            and structural_weight > 0.0
        )
        mapping_justification = (
            "semapv:CompositeMatching" if blending_active else "semapv:LexicalMatching"
        )

        # Compute ranked suggestions
        result = rank_suggestions(
            src_uris,
            src_vectors,
            master_uris,
            master_vectors,
            top_k,
            min_score,
            A_struct=A_struct,
            B_struct=B_struct,
            structural_weight=structural_weight,
        )

        result = filter_decided_suggestions(result, log)

        # Build index: (subject_id, object_id) -> latest non-CompositeMatching log row.
        # Exclude HC rejections — those pairs are already filtered from result.
        log_index: dict[tuple[str, str], SSSOMRow] = {}
        for row in log:
            if row.mapping_justification != "semapv:CompositeMatching" and not (
                row.mapping_justification == "semapv:HumanCuration"
                and row.predicate_id == "owl:differentFrom"
            ):
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

            src_label = src_labels.get(src_uri, "")

            for cand in candidates_tsv:
                obj_uri: str = cand["uri"]  # pyright: ignore[reportAny]
                score: float = cand["score"]  # pyright: ignore[reportAny]
                obj_label = master_labels.get(obj_uri, "")

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
                        mapping_date=cand.get("mapping_date") or None,
                        record_id=cand.get("record_id") or None,
                        subject_datatype=src_datatypes.get(src_uri),
                        object_datatype=master_datatypes.get(obj_uri),
                    )
                )

        config = load_config()
        library = FunctionLibrary.load_builtins()
        policies = load_conversion_policies(config)
        populate_conversion_functions(sssom_rows, policies, library)

        # Write SSSOM TSV
        with open_output(output) as fh:
            for line in _SSSOM_HEADER_LINES:
                _ = fh.write(line + "\n")

            buf = io.StringIO()
            writer = csv.writer(buf, delimiter="\t", lineterminator="\n")
            _ = writer.writerow(SSSOM_COLUMNS)
            for row in sssom_rows:
                _ = writer.writerow(
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
                        row.conversion_function or "",
                    ]
                )
            _ = fh.write(buf.getvalue())

    except SystemExit:
        raise
    except click.ClickException:
        raise
    except Exception as e:  # noqa: BLE001
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
