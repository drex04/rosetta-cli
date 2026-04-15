"""rosetta-embed — embed a LinkML schema using a sentence-transformer model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from rosetta.core.embedding import (
    EmbeddingModel,
    extract_text_inputs_linkml,
)
from rosetta.core.features import extract_structural_features_linkml
from rosetta.core.models import EmbeddingReport, EmbeddingVectors


@click.command()
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Input .linkml.yaml schema file.",
)
@click.option("--model", default=None, help="Sentence-transformer model name.")
@click.option(
    "--output",
    default=None,
    type=click.Path(path_type=Path),
    help="Output JSON path (default: stdout).",
)
@click.option(
    "--include-definitions",
    is_flag=True,
    default=False,
    help="Append description field to embedded text.",
)
@click.option(
    "--include-parents",
    is_flag=True,
    default=False,
    help="Append direct is_a parent title to embedded text.",
)
@click.option(
    "--include-ancestors",
    is_flag=True,
    default=False,
    help="Append all transitive is_a ancestor titles (supersedes --include-parents).",
)
@click.option(
    "--include-children",
    is_flag=True,
    default=False,
    help="Append direct is_a child class names to embedded text.",
)
def cli(
    input_path: Path,
    model: str | None,
    output: Path | None,
    include_definitions: bool,
    include_parents: bool,
    include_ancestors: bool,
    include_children: bool,
) -> None:
    """Embed a LinkML schema using a sentence-transformer model."""
    try:
        from typing import cast as _cast

        from linkml_runtime.linkml_model import SchemaDefinition
        from linkml_runtime.loaders import yaml_loader  # type: ignore[import-untyped]

        from rosetta.core.config import get_config_value, load_config

        config = load_config(None)
        model_name: str = (
            model or get_config_value(config, "embed", "model") or "intfloat/e5-large-v2"
        )

        schema = _cast(
            SchemaDefinition,
            yaml_loader.load(str(input_path), target_class=SchemaDefinition),  # pyright: ignore[reportUnknownMemberType]
        )
        pairs = extract_text_inputs_linkml(
            schema,
            include_definitions=include_definitions,
            include_parents=include_parents,
            include_ancestors=include_ancestors,
            include_children=include_children,
        )
        if not pairs:
            click.echo("Error: No embeddable nodes found in schema.", err=True)
            sys.exit(1)

        struct_map = extract_structural_features_linkml(schema)

        em = EmbeddingModel(model_name)
        texts = [text for _, _, text in pairs]
        vectors = em.encode(texts)

        report = EmbeddingReport(
            root={
                node_id: EmbeddingVectors(
                    label=label,
                    lexical=vec,
                    structural=struct_map.get(node_id, []),
                )
                for (node_id, label, _), vec in zip(pairs, vectors, strict=True)
            }
        )
        out_json = json.dumps(report.model_dump(mode="json"), indent=2)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(out_json)
        else:
            click.echo(out_json)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
