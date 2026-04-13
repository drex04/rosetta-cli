"""rosetta-translate: Normalise non-English field labels to English via DeepL."""

import os
import sys
from pathlib import Path

import click

from rosetta.core.config import get_config_value, load_config
from rosetta.core.io import open_input, open_output
from rosetta.core.rdf_utils import ROSE_NS, load_graph, save_graph
from rosetta.core.translation import translate_labels


@click.command("rosetta-translate")
@click.option(
    "--input",
    "-i",
    "input_path",
    default="-",
    show_default=True,
    help="Turtle input file (default: stdin).",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    default="-",
    show_default=True,
    help="Turtle output file (default: stdout).",
)
@click.option(
    "--source-lang",
    default=None,
    help="Source language code (e.g. DE, NO) or 'auto'. 'EN'/'EN-US'/etc = passthrough.",
)
@click.option("--config", "-c", default=None, help="Path to rosetta.toml.")
def cli(
    input_path: str,
    output_path: str,
    source_lang: str | None,
    config: str | None,
) -> None:
    """Translate non-English field labels to English via DeepL.

    Reads a rosetta-ingest TTL and writes an English-normalised TTL.
    Use --source-lang EN (or any EN-* variant) to pass through without any API call.
    """
    cfg = load_config(Path(config) if config is not None else None)
    resolved_lang = (
        get_config_value(cfg, "translate", "source_lang", cli_value=source_lang) or "auto"
    )

    # NOTE: must use same predicate as translate_labels — both use startswith("EN")
    is_passthrough = resolved_lang.upper().startswith("EN")

    api_key = os.environ.get("DEEPL_API_KEY", "")
    if not is_passthrough and not api_key:
        click.echo(
            "Error: DEEPL_API_KEY environment variable is not set. "
            "Set it or pass --source-lang EN for passthrough.",
            err=True,
        )
        sys.exit(1)

    try:
        with open_input(input_path) as src:
            g = load_graph(src)

        # Idempotency guard: skip if any rose:originalLabel already exists
        if any(True for _ in g.subject_objects(ROSE_NS.originalLabel)):
            click.echo(
                "Warning: graph already contains rose:originalLabel triples"
                " — skipping translation.",
                err=True,
            )
            with open_output(output_path) as fh:
                save_graph(g, fh)
            return

        g = translate_labels(g, source_lang=resolved_lang, api_key=api_key)

        if output_path != "-":
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open_output(output_path) as fh:
            save_graph(g, fh)

    except Exception as e:
        click.echo(str(e), err=True)
        sys.exit(1)
