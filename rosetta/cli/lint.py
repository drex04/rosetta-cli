"""rosetta-lint: Validate unit and datatype compatibility in field mappings."""
import json
import sys
from pathlib import Path

import click
import rdflib

from rosetta.core.config import load_config
from rosetta.core.io import open_output
from rosetta.core.units import (
    UNIT_STRING_TO_IRI,
    load_qudt_graph,
    units_compatible,
    suggest_fnml,
)

ROSE = rdflib.Namespace("http://rosetta.interop/ns/")
QUDT = rdflib.Namespace("http://qudt.org/schema/qudt/")
XSD  = rdflib.namespace.XSD
RDFS = rdflib.namespace.RDFS

# XSD numeric types — mismatch against xsd:string triggers datatype_mismatch WARNING
_NUMERIC_XSD = {
    str(XSD.integer), str(XSD.int), str(XSD.float), str(XSD.double),
    str(XSD.decimal), str(XSD.long), str(XSD.short),
}
_STRING_XSD = {str(XSD.string)}

_SRC_UNIT_QUERY = """
PREFIX rose: <http://rosetta.interop/ns/>
SELECT ?unit WHERE {
    <%s> rose:detectedUnit ?unit .
}
LIMIT 1
"""

_TGT_UNIT_QUERY = """
PREFIX qudt: <http://qudt.org/schema/qudt/>
SELECT ?unit WHERE {
    <%s> qudt:unit ?unit .
}
LIMIT 1
"""

_SRC_DTYPE_QUERY = """
PREFIX rose: <http://rosetta.interop/ns/>
SELECT ?dtype WHERE {
    <%s> rose:dataType ?dtype .
}
LIMIT 1
"""

_TGT_DTYPE_QUERY = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?dtype WHERE {
    <%s> rdfs:range ?dtype .
}
LIMIT 1
"""


def _sparql_one(graph: rdflib.Graph, query: str) -> rdflib.term.Node | None:
    """Run a SPARQL SELECT returning one row/one var; return that value or None."""
    results = list(graph.query(query))
    if not results:
        return None
    row = results[0]
    return row[0] if row[0] is not None else None


@click.command()
@click.option("--source", required=True, type=click.Path(exists=True),
              help="National schema RDF (Turtle).")
@click.option("--master", required=True, type=click.Path(exists=True),
              help="Master ontology RDF (Turtle).")
@click.option("--suggestions", required=True, type=click.Path(exists=True),
              help="Suggestions JSON from rosetta-suggest.")
@click.option("--output", default=None, type=click.Path(),
              help="Output file (default: stdout).")
@click.option("--strict", is_flag=True, default=False,
              help="Treat WARNINGs as BLOCKs.")
@click.option("--config", default="rosetta.toml", show_default=True,
              help="Path to rosetta.toml.")
def cli(source, master, suggestions, output, strict, config):
    """Lint mapping files against SHACL shapes and policy rules."""
    cfg = load_config(config)  # noqa: F841 — available for future use

    try:
        # 1. Load source TTL
        src_graph = rdflib.Graph()
        src_graph.parse(source, format="turtle")

        # 2. Load master TTL
        mst_graph = rdflib.Graph()
        mst_graph.parse(master, format="turtle")

        # 3. Load suggestions JSON
        with open(suggestions, "r", encoding="utf-8") as fh:
            data: dict = json.load(fh)

        # 4. Load QUDT + FnML policy graph
        qudt_graph = load_qudt_graph()

        findings: list[dict] = []

        # 5. Iterate source fields
        for src_uri, entry in data.items():
            sug_list = entry.get("suggestions", [])
            if not sug_list:
                continue  # no suggestions → nothing to lint

            top = sug_list[0]
            tgt_uri = top.get("uri", "")
            if not tgt_uri:
                continue

            # ----------------------------------------------------------------
            # c. Unit check — source side
            # ----------------------------------------------------------------
            unit_node = _sparql_one(src_graph, _SRC_UNIT_QUERY % src_uri)
            unit_str = str(unit_node) if unit_node is not None else None

            if unit_str is None or unit_str not in UNIT_STRING_TO_IRI:
                findings.append({
                    "severity": "INFO",
                    "rule": "unit_not_detected",
                    "source_field": src_uri,
                    "target_field": tgt_uri,
                    "source_unit": unit_str,
                    "target_unit": None,
                    "message": f"No detectable unit on source field '{src_uri}'.",
                    "fnml_suggestion": None,
                })
                # Still run datatype check below — fall through after continue-skip
                _run_datatype_check(findings, src_graph, mst_graph, src_uri, tgt_uri)
                continue

            src_iri = UNIT_STRING_TO_IRI[unit_str]
            if src_iri is None:
                # Known unmappable unit (e.g. dBm)
                findings.append({
                    "severity": "INFO",
                    "rule": "unit_not_detected",
                    "source_field": src_uri,
                    "target_field": tgt_uri,
                    "source_unit": unit_str,
                    "target_unit": None,
                    "message": f"Unit '{unit_str}' has no QUDT IRI mapping.",
                    "fnml_suggestion": None,
                })
                _run_datatype_check(findings, src_graph, mst_graph, src_uri, tgt_uri)
                continue

            # ----------------------------------------------------------------
            # d. Unit check — master side
            # ----------------------------------------------------------------
            tgt_unit_node = _sparql_one(mst_graph, _TGT_UNIT_QUERY % tgt_uri)
            if tgt_unit_node is None:
                findings.append({
                    "severity": "INFO",
                    "rule": "master_unit_missing",
                    "source_field": src_uri,
                    "target_field": tgt_uri,
                    "source_unit": src_iri,
                    "target_unit": None,
                    "message": f"No qudt:unit on master field '{tgt_uri}'.",
                    "fnml_suggestion": None,
                })
                _run_datatype_check(findings, src_graph, mst_graph, src_uri, tgt_uri)
                continue

            tgt_iri = str(tgt_unit_node)

            # ----------------------------------------------------------------
            # e. Compatibility check
            # ----------------------------------------------------------------
            compat = units_compatible(src_iri, tgt_iri, qudt_graph)

            if compat is False:
                findings.append({
                    "severity": "BLOCK",
                    "rule": "unit_dimension_mismatch",
                    "source_field": src_uri,
                    "target_field": tgt_uri,
                    "source_unit": src_iri,
                    "target_unit": tgt_iri,
                    "message": "Incompatible unit dimensions.",
                    "fnml_suggestion": None,
                })
            elif compat is True:
                # Normalise both to full IRI for equality check
                def _to_full(iri: str) -> str:
                    return "http://qudt.org/vocab/unit/" + iri[5:] if iri.startswith("unit:") else iri

                if _to_full(src_iri) != _to_full(tgt_iri):
                    fnml = suggest_fnml(src_iri, tgt_iri, qudt_graph)
                    findings.append({
                        "severity": "WARNING",
                        "rule": "unit_conversion_required",
                        "source_field": src_uri,
                        "target_field": tgt_uri,
                        "source_unit": src_iri,
                        "target_unit": tgt_iri,
                        "message": "Units are compatible but differ; conversion needed.",
                        "fnml_suggestion": fnml,
                    })
                # else: identical units — no finding
            else:
                # compat is None → dimension vector missing
                findings.append({
                    "severity": "INFO",
                    "rule": "unit_vector_missing",
                    "source_field": src_uri,
                    "target_field": tgt_uri,
                    "source_unit": src_iri,
                    "target_unit": tgt_iri,
                    "message": "Dimension vector missing for one or both units.",
                    "fnml_suggestion": None,
                })

            # ----------------------------------------------------------------
            # f. Datatype check (always runs unless we already continued above)
            # ----------------------------------------------------------------
            _run_datatype_check(findings, src_graph, mst_graph, src_uri, tgt_uri)

        # --------------------------------------------------------------------
        # 7. --strict: re-classify WARNINGs → BLOCKs
        # --------------------------------------------------------------------
        if strict:
            for f in findings:
                if f["severity"] == "WARNING":
                    f["severity"] = "BLOCK"

        # 8. Recount summary using final severities
        summary = {"block": 0, "warning": 0, "info": 0}
        for f in findings:
            sev = f["severity"].lower()
            if sev in summary:
                summary[sev] += 1

        result = {"findings": findings, "summary": summary}

        # 9. Write output
        with open_output(output) as fh:
            json.dump(result, fh, indent=2)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # 10. Exit code AFTER writing output
    has_block = any(f["severity"] == "BLOCK" for f in findings)
    sys.exit(1 if has_block else 0)


def _run_datatype_check(
    findings: list[dict],
    src_graph: rdflib.Graph,
    mst_graph: rdflib.Graph,
    src_uri: str,
    tgt_uri: str,
) -> None:
    """Append a datatype_mismatch WARNING if numeric vs string mismatch detected."""
    src_dt_node = _sparql_one(src_graph, _SRC_DTYPE_QUERY % src_uri)
    tgt_dt_node = _sparql_one(mst_graph, _TGT_DTYPE_QUERY % tgt_uri)

    # None-guard before any string coercion
    if src_dt_node is None or tgt_dt_node is None:
        return

    src_dt = str(src_dt_node)
    tgt_dt = str(tgt_dt_node)

    src_numeric = src_dt in _NUMERIC_XSD
    src_string  = src_dt in _STRING_XSD
    tgt_numeric = tgt_dt in _NUMERIC_XSD
    tgt_string  = tgt_dt in _STRING_XSD

    mismatch = (src_numeric and tgt_string) or (src_string and tgt_numeric)
    if mismatch:
        findings.append({
            "severity": "WARNING",
            "rule": "datatype_mismatch",
            "source_field": src_uri,
            "target_field": tgt_uri,
            "source_unit": None,
            "target_unit": None,
            "message": f"Datatype mismatch: source '{src_dt}' vs master '{tgt_dt}'.",
            "fnml_suggestion": None,
        })
