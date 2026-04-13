# Phase 6 Plan 01 — Core RML Engine

## Objective

Build the basic `rosetta-rml-gen` CLI: reads a decisions JSON file, outputs valid RML Turtle with `rml:logicalSource`, `rr:subjectMap`, and `rr:predicateObjectMap` (no FnML). Output must be parseable by rdflib and structurally valid for RMLMapper.

## Context

- **Input decisions format:** `{ "http://rosetta.interop/field/nor/schema/hoyde_m": { "target_uri": "http://master.ontology/AltitudeMSL", "field_ref": "hoyde_m" } }`
- **field_ref** defaults to the last path segment of the source URI when absent.
- Generation uses `rdflib.Graph` with blank nodes — no f-string templates (see D06-02).
- Source format `json` → `ql:JSONPath` references use `$.fieldname`; `csv` → `ql:CSV` uses bare column name (D06-03).
- New `MappingDecision` Pydantic model is added to `rosetta/core/models.py`.

## Namespaces

```python
RML  = Namespace("http://semweb.mmlab.be/ns/rml#")
RR   = Namespace("http://www.w3.org/ns/r2rml#")
QL   = Namespace("http://semweb.mmlab.be/ns/ql#")
ROSE = Namespace("http://rosetta.interop/ns/")
```

## Tasks

### Task 1 — Add `MappingDecision` model to `rosetta/core/models.py`

Append after the `EmbeddingReport` class:

```python
class MappingDecision(BaseModel):
    source_uri: str
    target_uri: str
    field_ref: str | None = None          # rml:reference value; defaults to URI last segment
    fnml_function: str | None = None      # set in Plan 02
    multiplier: float | None = None
    offset: float | None = None
```

No other changes to the file.

### Task 2 — Create `rosetta/core/rml_builder.py`

New file. Full implementation:

```python
"""RML/FnML Turtle generation from approved mapping decisions."""
from __future__ import annotations

import rdflib
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from rosetta.core.models import MappingDecision

RML  = Namespace("http://semweb.mmlab.be/ns/rml#")
RR   = Namespace("http://www.w3.org/ns/r2rml#")
QL   = Namespace("http://semweb.mmlab.be/ns/ql#")

_FORMAT_MAP: dict[str, URIRef] = {
    "json": QL.JSONPath,
    "csv":  QL.CSV,
}

def _field_ref(decision: MappingDecision, source_format: str) -> str:
    """Return rml:reference string for the decision."""
    name = decision.field_ref or decision.source_uri.rstrip("/").rsplit("/", 1)[-1]
    return f"$.{name}" if source_format == "json" else name


def _add_logical_source(g: Graph, map_node: BNode, source_file: str, source_format: str) -> None:
    ls = BNode()
    g.add((map_node, RML.logicalSource, ls))
    g.add((ls, RML.source, Literal(source_file)))
    g.add((ls, RML.referenceFormulation, _FORMAT_MAP[source_format]))


def _add_subject_map(g: Graph, map_node: BNode, base_uri: str) -> None:
    sm = BNode()
    g.add((map_node, RR.subjectMap, sm))
    g.add((sm, RR.template, Literal(f"{base_uri.rstrip('/')}/{{id}}")))


def _add_predicate_object_map(
    g: Graph, map_node: BNode, decision: MappingDecision, source_format: str
) -> None:
    pom = BNode()
    g.add((map_node, RR.predicateObjectMap, pom))
    g.add((pom, RR.predicate, URIRef(decision.target_uri)))
    obj_map = BNode()
    g.add((pom, RR.objectMap, obj_map))
    # FnML branch handled in Plan 02; plain reference here
    g.add((obj_map, RML.reference, Literal(_field_ref(decision, source_format))))


def build_rml_graph(
    decisions: list[MappingDecision],
    source_file: str,
    source_format: str,
    base_uri: str,
) -> Graph:
    """Build an rdflib Graph containing a single TriplesMap for all decisions."""
    if source_format not in _FORMAT_MAP:
        raise ValueError(f"Unsupported source_format: {source_format!r}. Use 'json' or 'csv'.")

    g = Graph()
    g.bind("rml", RML)
    g.bind("rr",  RR)
    g.bind("ql",  QL)

    map_node = BNode()
    g.add((map_node, RDF.type, RR.TriplesMap))
    _add_logical_source(g, map_node, source_file, source_format)
    _add_subject_map(g, map_node, base_uri)
    for decision in decisions:
        _add_predicate_object_map(g, map_node, decision, source_format)
    return g
```

### Task 3 — Create `rosetta/cli/rml_gen.py`

New file. Full implementation:

```python
"""rosetta-rml-gen: Generate RML/FnML Turtle from approved mapping decisions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from rosetta.core.io import open_output
from rosetta.core.models import MappingDecision
from rosetta.core.rml_builder import build_rml_graph


@click.command()
@click.option("--decisions", required=True, type=click.Path(exists=True),
              help="Approved decisions JSON (source_uri → {target_uri, ...})")
@click.option("--source-file", required=True,
              help="Data file path to embed in rml:logicalSource (not read, just referenced)")
@click.option("--source-format", default="json", show_default=True,
              type=click.Choice(["json", "csv"]),
              help="RML reference formulation (json=JSONPath, csv=CSV)")
@click.option("--base-uri", default="http://rosetta.interop/record",
              show_default=True, help="Subject template base URI")
@click.option("--output", default=None, type=click.Path(), help="Output file (default: stdout)")
def cli(
    decisions: str,
    source_file: str,
    source_format: str,
    base_uri: str,
    output: str | None,
) -> None:
    """Generate RML/FnML Turtle from approved mapping decisions."""
    try:
        raw: dict[str, dict[str, object]] = json.loads(Path(decisions).read_text())
    except Exception as e:
        click.echo(f"Error reading decisions: {e}", err=True)
        sys.exit(1)

    if not raw:
        click.echo("Error: decisions file is empty.", err=True)
        sys.exit(1)

    parsed: list[MappingDecision] = []
    for src_uri, props in raw.items():
        if "target_uri" not in props:
            click.echo(f"Error: missing 'target_uri' for {src_uri}", err=True)
            sys.exit(1)
        parsed.append(MappingDecision(source_uri=src_uri, **props))  # type: ignore[arg-type]

    try:
        g = build_rml_graph(parsed, source_file, source_format, base_uri)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    with open_output(output) as fh:
        fh.write(g.serialize(format="turtle"))
```

### Task 4 — Register entrypoint in `pyproject.toml`

In `pyproject.toml`, find the `[project.scripts]` section and add:
```
rosetta-rml-gen = "rosetta.cli.rml_gen:cli"
```

Run `uv sync` after editing.

### Task 5 — Write tests in `rosetta/tests/test_rml_gen.py`

New file. Cover:

1. **`test_basic_rml_two_decisions`** — call `build_rml_graph` with two `MappingDecision` instances, assert:
   - `g.serialize(format="turtle")` does not raise
   - Graph contains exactly one `rr:TriplesMap`
   - Graph contains `rml:logicalSource`
   - Graph contains two `rr:predicateObjectMap` triples
   - Each `rml:reference` value matches expected field ref

2. **`test_field_ref_from_uri`** — `MappingDecision(source_uri="http://example.org/field/nor/alt", target_uri="...", field_ref=None)` with source_format="json" → `rml:reference` literal is `"$.alt"`

3. **`test_csv_format_bare_ref`** — source_format="csv" → `rml:reference` is `"alt"` (no `$.` prefix)

4. **`test_unsupported_format_raises`** — `build_rml_graph(..., source_format="xml", ...)` raises `ValueError`

5. **`test_cli_empty_decisions_exits_1`** — write `{}` to tmp JSON, invoke CLI via `CliRunner`, assert exit code 1

6. **`test_cli_missing_target_uri_exits_1`** — decisions JSON missing `target_uri` → exit code 1

7. **`test_cli_writes_turtle_to_stdout`** — valid decisions JSON → exit code 0, stdout contains `rml:logicalSource`

## Quality gate

Before marking complete:
```bash
uv run ruff format rosetta/core/rml_builder.py rosetta/cli/rml_gen.py rosetta/tests/test_rml_gen.py
uv run ruff check rosetta/core/rml_builder.py rosetta/cli/rml_gen.py
uv run basedpyright rosetta/core/rml_builder.py rosetta/cli/rml_gen.py
uv run pytest rosetta/tests/test_rml_gen.py -v
```

All 7 tests pass, ruff clean, basedpyright clean.
