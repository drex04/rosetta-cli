"""rosetta-embed: Embed RDF schema attributes using LaBSE."""

import json
import sys
from pathlib import Path

import click

from rosetta.core.config import load_config, get_config_value
from rosetta.core.io import open_input, open_output
from rosetta.core.rdf_utils import load_graph
from rosetta.core.embedding import extract_text_inputs, EmbeddingModel


@click.command()
@click.option("--input", "-i", "input_path", default="-", show_default=True, help="Turtle input file (default: stdin).")
@click.option("--output", "-o", "output_path", default="-", show_default=True, help="JSON output file (default: stdout).")
@click.option("--mode", default=None, help="Embedding mode (default: lexical-only).")
@click.option("--model", default=None, help="Model name (default: sentence-transformers/LaBSE).")
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(input_path, output_path, mode, model, config):
    """Embed RDF schema attributes using LaBSE."""
    cfg = load_config(config)
    resolved_model = get_config_value(cfg, "embed", "model", cli_value=model) or "sentence-transformers/LaBSE"
    resolved_mode  = get_config_value(cfg, "embed", "mode",  cli_value=mode)  or "lexical-only"

    try:
        with open_input(input_path) as src:
            g = load_graph(src)

        pairs = extract_text_inputs(g)
        if not pairs:
            click.echo("No embeddable attributes found in input.", err=True)
            sys.exit(1)

        em = EmbeddingModel(resolved_model)
        uris, texts = zip(*pairs)
        vectors = em.encode(list(texts))

        # URIRef → str so json.dumps() doesn't raise TypeError
        result = {str(uri): {"lexical": vec} for uri, vec in zip(uris, vectors)}

        # Auto-create output parent directory, then write
        if output_path != "-":
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open_output(output_path) as fh:
            fh.write(json.dumps(result, indent=2))
    except Exception as e:
        click.echo(str(e), err=True)
        sys.exit(1)
