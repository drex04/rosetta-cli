# Phase 6 Plan 02 — FnML Integration + Pipeline Convenience

## Objective

Extend `rosetta-rml-gen` to wrap predicate-object maps in FnML `functionValue` blocks when a mapping decision includes a conversion function. Add a `--from-suggest` convenience mode that auto-builds decisions from `rosetta-suggest` + `rosetta-lint` output, closing the full pipeline.

## Context

- Builds on Plan 01. `rosetta/core/rml_builder.py` and `rosetta/cli/rml_gen.py` already exist.
- FnML parameter predicates use `http://rosetta.interop/fn/param/` namespace (D06-04).
- `--from-suggest` takes top-1 suggestion per source URI; enriches with lint `fnml_suggestion` when the (source_uri, target_uri) pair appears in lint findings (D06-05).
- No function descriptor TTL files required — RML execution only needs the function URI in the mapping.

## Additional Namespaces

```python
FNML    = Namespace("http://semweb.mmlab.be/ns/fnml#")
FNO     = Namespace("https://w3id.org/function/ontology#")
ROSE_FN = Namespace("http://rosetta.interop/fn/")
ROSE_P  = Namespace("http://rosetta.interop/fn/param/")
```

## Tasks

### Task 1 — Add FnML namespaces and `_add_function_value` to `rml_builder.py`

Add after existing imports and constants:

```python
FNML    = Namespace("http://semweb.mmlab.be/ns/fnml#")
FNO     = Namespace("https://w3id.org/function/ontology#")
ROSE_P  = Namespace("http://rosetta.interop/fn/param/")
```

Add to `build_rml_graph` namespace bindings:
```python
g.bind("fnml", FNML)
g.bind("fno",  FNO)
```

Add new private function:

```python
def _add_function_value(
    g: Graph,
    obj_map: BNode,
    decision: MappingDecision,
    source_format: str,
) -> None:
    """Wrap obj_map in FnML functionValue block."""
    fv = BNode()
    g.add((obj_map, FNML.functionValue, fv))

    # fno:executes → function URI
    fn_pom = BNode()
    g.add((fv, RR.predicateObjectMap, fn_pom))
    g.add((fn_pom, RR.predicate, FNO.executes))
    fn_obj = BNode()
    g.add((fn_pom, RR.objectMap, fn_obj))
    g.add((fn_obj, RR.constant, URIRef(decision.fnml_function)))  # type: ignore[arg-type]

    # value param → rml:reference on the source field
    val_pom = BNode()
    g.add((fv, RR.predicateObjectMap, val_pom))
    g.add((val_pom, RR.predicate, ROSE_P.value))
    val_obj = BNode()
    g.add((val_pom, RR.objectMap, val_obj))
    g.add((val_obj, RML.reference, Literal(_field_ref(decision, source_format))))

    # optional multiplier
    if decision.multiplier is not None:
        m_pom = BNode()
        g.add((fv, RR.predicateObjectMap, m_pom))
        g.add((m_pom, RR.predicate, ROSE_P.multiplier))
        m_obj = BNode()
        g.add((m_pom, RR.objectMap, m_obj))
        g.add((m_obj, RR.constant, Literal(decision.multiplier)))

    # optional offset
    if decision.offset is not None:
        o_pom = BNode()
        g.add((fv, RR.predicateObjectMap, o_pom))
        g.add((o_pom, RR.predicate, ROSE_P.offset))
        o_obj = BNode()
        g.add((o_pom, RR.objectMap, o_obj))
        g.add((o_obj, RR.constant, Literal(decision.offset)))
```

Modify `_add_predicate_object_map` to branch on `fnml_function`:

```python
def _add_predicate_object_map(
    g: Graph, map_node: BNode, decision: MappingDecision, source_format: str
) -> None:
    pom = BNode()
    g.add((map_node, RR.predicateObjectMap, pom))
    g.add((pom, RR.predicate, URIRef(decision.target_uri)))
    obj_map = BNode()
    g.add((pom, RR.objectMap, obj_map))
    if decision.fnml_function:
        _add_function_value(g, obj_map, decision, source_format)
    else:
        g.add((obj_map, RML.reference, Literal(_field_ref(decision, source_format))))
```

### Task 2 — Add `--from-suggest` mode to `rml_gen.py`

Add two new options to the `@click.command` decorator:
```python
@click.option("--from-suggest", default=None, type=click.Path(exists=True),
              help="Auto-build decisions from rosetta-suggest JSON (takes top-1 per field)")
@click.option("--lint", default=None, type=click.Path(exists=True),
              help="rosetta-lint JSON to enrich decisions with FnML suggestions")
```

Make `--decisions` no longer `required=True` — validate in function body instead:

```python
# Mutually exclusive resolution
if from_suggest and decisions:
    click.echo("Error: use --decisions or --from-suggest, not both.", err=True)
    sys.exit(1)
if not from_suggest and not decisions:
    click.echo("Error: one of --decisions or --from-suggest is required.", err=True)
    sys.exit(1)
```

Add a helper function `_decisions_from_suggest` (top of module, before `cli`):

```python
def _decisions_from_suggest(
    suggest_path: str, lint_path: str | None
) -> dict[str, dict[str, object]]:
    """Build decisions dict from suggest JSON, optionally enriched by lint JSON."""
    suggest: dict[str, dict[str, object]] = json.loads(Path(suggest_path).read_text())
    lint_index: dict[tuple[str, str], dict[str, object]] = {}

    if lint_path:
        lint_data: dict[str, object] = json.loads(Path(lint_path).read_text())
        for finding in lint_data.get("findings", []):  # type: ignore[union-attr]
            fnml = finding.get("fnml_suggestion")
            if fnml and finding.get("source_uri") and finding.get("target_uri"):
                key = (str(finding["source_uri"]), str(finding["target_uri"]))
                lint_index[key] = dict(fnml)  # type: ignore[arg-type]

    result: dict[str, dict[str, object]] = {}
    for src_uri, field_data in suggest.items():
        suggestions = field_data.get("suggestions", [])
        if not suggestions:
            continue
        # top-1 by score (already sorted descending by rosetta-suggest)
        top = suggestions[0]  # type: ignore[index]
        target_uri = str(top["target_uri"])  # type: ignore[index]
        decision: dict[str, object] = {"target_uri": target_uri}

        # enrich from lint
        fnml_props = lint_index.get((src_uri, target_uri))
        if fnml_props:
            decision.update(fnml_props)

        result[src_uri] = decision
    return result
```

In `cli`, after the mutual-exclusion guard:

```python
if from_suggest:
    try:
        raw = _decisions_from_suggest(from_suggest, lint)
    except Exception as e:
        click.echo(f"Error building decisions from suggest: {e}", err=True)
        sys.exit(1)
```

(The existing `--decisions` path is unchanged below.)

### Task 3 — Write FnML tests, extending `test_rml_gen.py`

Add to the existing test file:

1. **`test_fnml_multiply_wraps_function_value`** — `MappingDecision` with `fnml_function="http://rosetta.interop/fn/MultiplyByFactor"`, `multiplier=0.3048` → graph contains `fnml:functionValue` triple, `fno:executes` triple pointing to the function URI, `rr:constant` literal `0.3048`; does NOT contain plain `rml:reference` on that objectMap

2. **`test_fnml_no_multiplier_no_offset`** — `fnml_function` set, `multiplier=None`, `offset=None` → graph contains `fno:executes` but no multiplier/offset predicates

3. **`test_fnml_with_offset`** — `offset=32.0` set → graph contains `rose_p:offset` with constant `32.0`

4. **`test_from_suggest_top1_selected`** — write tmp suggest JSON with two suggestions per field (scores 0.9 and 0.5), invoke `_decisions_from_suggest`, assert only the 0.9 suggestion is picked

5. **`test_from_suggest_enriched_by_lint`** — write suggest JSON + lint JSON where source/target pair has `fnml_suggestion`; assert `_decisions_from_suggest` result includes `fnml_function` key

6. **`test_cli_from_suggest_flag_exits_0`** — write suggest JSON to tmp, invoke CLI with `--from-suggest` and `--source-file data.json`, assert exit code 0 and stdout is parseable Turtle

7. **`test_cli_both_flags_exits_1`** — pass both `--decisions` and `--from-suggest` → exit code 1

### Task 4 — Update `rosetta.toml` with rml-gen defaults

Add section to `rosetta.toml`:

```toml
[rml-gen]
source_format = "json"
base_uri = "http://rosetta.interop/record"
```

Wire config lookup in `cli` following the same `get_config_value` pattern used in `suggest.py`.

## Quality gate

Before marking complete:
```bash
uv run ruff format rosetta/core/rml_builder.py rosetta/cli/rml_gen.py rosetta/tests/test_rml_gen.py
uv run ruff check rosetta/core/rml_builder.py rosetta/cli/rml_gen.py
uv run basedpyright rosetta/core/rml_builder.py rosetta/cli/rml_gen.py
uv run pytest rosetta/tests/test_rml_gen.py -v
uv run pytest -m "not slow"   # full regression
```

All 14 tests pass (7 from Plan 01 + 7 new), ruff clean, basedpyright clean, no regressions.
