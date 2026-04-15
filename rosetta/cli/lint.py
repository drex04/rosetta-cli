"""rosetta-lint: Validate unit and datatype compatibility in field mappings."""

import json
import sys
from pathlib import Path
from typing import Any

import click
import rdflib
from rdflib.namespace import XSD
from rdflib.term import Node

from rosetta.core.accredit import load_log, parse_sssom_tsv
from rosetta.core.config import get_config_value, load_config
from rosetta.core.io import open_output
from rosetta.core.models import LintFinding, LintReport, LintSummary, SSSOMRow
from rosetta.core.units import (
    UNIT_STRING_TO_IRI,
    expand_unit_iri,
    load_qudt_graph,
    suggest_fnml,
    units_compatible,
)

ROSE = rdflib.Namespace("http://rosetta.interop/ns/")
QUDT = rdflib.Namespace("http://qudt.org/schema/qudt/")

# XSD numeric types — mismatch against xsd:string triggers datatype_mismatch WARNING
_NUMERIC_XSD = {
    str(XSD.integer),
    str(XSD.int),
    str(XSD.float),
    str(XSD.double),
    str(XSD.decimal),
    str(XSD.long),
    str(XSD.short),
}
_STRING_XSD = {str(XSD.string)}

_SRC_UNIT_QUERY = """
PREFIX rose: <http://rosetta.interop/ns/>
SELECT ?unit WHERE {
    ?subject rose:detectedUnit ?unit .
}
LIMIT 1
"""

_TGT_UNIT_QUERY = """
PREFIX qudt: <http://qudt.org/schema/qudt/>
SELECT ?unit WHERE {
    ?subject qudt:unit ?unit .
}
LIMIT 1
"""

_SRC_DTYPE_QUERY = """
PREFIX rose: <http://rosetta.interop/ns/>
SELECT ?dtype WHERE {
    ?subject rose:dataType ?dtype .
}
LIMIT 1
"""

_TGT_DTYPE_QUERY = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?dtype WHERE {
    ?subject rdfs:range ?dtype .
}
LIMIT 1
"""


_VALID_PREDICATES = {
    "skos:exactMatch",
    "skos:closeMatch",
    "skos:narrowMatch",
    "skos:broadMatch",
    "skos:relatedMatch",
    "owl:differentFrom",
}

MMC = "semapv:ManualMappingCuration"
HC = "semapv:HumanCuration"


def check_sssom_proposals(
    rows: list[SSSOMRow],
    log: list[SSSOMRow],
) -> list[str]:
    """Return list of error strings. Empty list = no errors."""
    errors: list[str] = []

    # 1. MaxOneMmcPerPair
    mmc_rows = [r for r in rows if r.mapping_justification == MMC]
    pair_counts: dict[tuple[str, str], int] = {}
    for r in mmc_rows:
        pair = (r.subject_id, r.object_id)
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
    for (subject_id, object_id), count in pair_counts.items():
        if count > 1:
            errors.append(
                f"ERROR [MaxOneMmcPerPair] {subject_id} → {object_id}: "
                f"{count} ManualMappingCuration rows (max 1)"
            )

    # 2. NoHumanCurationReproposal
    if log:
        hc_pairs: set[tuple[str, str]] = {
            (r.subject_id, r.object_id) for r in log if r.mapping_justification == HC
        }
        for r in mmc_rows:
            pair = (r.subject_id, r.object_id)
            if pair in hc_pairs:
                errors.append(
                    f"ERROR [NoHumanCurationReproposal] {r.subject_id} → {r.object_id}: "
                    f"pair already has a HumanCuration decision in the audit log"
                )

    # 3. ValidPredicate
    for r in mmc_rows:
        if r.predicate_id not in _VALID_PREDICATES:
            errors.append(
                f"ERROR [ValidPredicate] {r.subject_id} → {r.object_id}: "
                f"invalid predicate '{r.predicate_id}'"
            )

    return errors


def _sparql_one(
    graph: rdflib.Graph,
    query: str,
    bindings: dict[str, Any] | None = None,
) -> Node | None:
    """Run a SPARQL SELECT returning one row/one var; return that value or None."""
    results = list(graph.query(query, initBindings=bindings or {}))
    if not results:
        return None
    row = results[0]
    val = row[0]  # pyright: ignore[reportIndexIssue]
    return val if val is not None else None


@click.command()
@click.option(
    "--source", default=None, type=click.Path(exists=True), help="National schema RDF (Turtle)."
)
@click.option(
    "--master", default=None, type=click.Path(exists=True), help="Master ontology RDF (Turtle)."
)
@click.option(
    "--suggestions",
    default=None,
    type=click.Path(exists=True),
    help="Suggestions JSON from rosetta-suggest.",
)
@click.option("--output", default=None, type=click.Path(), help="Output file (default: stdout).")
@click.option("--strict", is_flag=True, default=False, help="Treat WARNINGs as BLOCKs.")
@click.option("--config", default="rosetta.toml", show_default=True, help="Path to rosetta.toml.")
@click.option(
    "--sssom",
    default=None,
    type=click.Path(exists=True),
    help="Validate a SSSOM TSV file (proposals mode).",
)
def cli(  # noqa: E501
    source: str | None,
    master: str | None,
    suggestions: str | None,
    output: str | None,
    strict: bool,
    config: str,
    sssom: str | None,
) -> None:
    """Lint mapping files against SHACL shapes and policy rules."""
    # ----------------------------------------------------------------
    # SSSOM proposals mode
    # ----------------------------------------------------------------
    sssom_errors: list[str] = []
    if sssom is not None:
        rows = parse_sssom_tsv(Path(sssom))
        cfg = load_config(Path(config)) if config else load_config()
        log_path_str = get_config_value(cfg, "accredit", "log")
        if log_path_str and Path(log_path_str).exists():
            log = load_log(Path(log_path_str))
        else:
            log = []
        sssom_errors = check_sssom_proposals(rows, log)
        for err in sssom_errors:
            click.echo(err, err=True)

    # If --sssom was the only mode requested, exit now.
    if sssom is not None and source is None and master is None and suggestions is None:
        sys.exit(1 if sssom_errors else 0)

    # If schema lint mode was requested, require all three options.
    if source is None or master is None or suggestions is None:
        if source is not None or master is not None or suggestions is not None:
            click.echo(
                "Error: --source, --master, and --suggestions are all required"
                " for schema lint mode.",
                err=True,
            )
            sys.exit(1)
        # Nothing to do if no options provided at all.
        sys.exit(1 if sssom_errors else 0)

    # initialised here so exit-code line after except can see it
    findings: list[LintFinding] = []

    try:
        # 1. Load source TTL
        src_graph = rdflib.Graph()
        src_graph.parse(source, format="turtle")

        # 2. Load master TTL
        mst_graph = rdflib.Graph()
        mst_graph.parse(master, format="turtle")

        # 3. Load suggestions JSON
        with open(suggestions, encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)

        # 4. Load QUDT + FnML policy graph
        qudt_graph = load_qudt_graph()

        # 5. Iterate source fields
        for src_uri, entry in data.items():
            # Issue 1: guard against malformed suggestion entries
            if not isinstance(entry, dict):
                findings.append(
                    LintFinding(
                        rule="parse_error",
                        severity="INFO",
                        source_uri=src_uri,
                        target_uri=None,
                        message=f"Suggestions entry for '{src_uri}' is not a dict; skipping.",
                        fnml_suggestion=None,
                    )
                )
                continue

            sug_list = entry.get("suggestions", [])
            if not isinstance(sug_list, list) or not sug_list:
                continue  # no suggestions → nothing to lint

            top = sug_list[0]
            if not isinstance(top, dict):
                findings.append(
                    LintFinding(
                        rule="parse_error",
                        severity="INFO",
                        source_uri=src_uri,
                        target_uri=None,
                        message=f"First suggestion entry for '{src_uri}' is not a dict; skipping.",  # noqa: E501
                        fnml_suggestion=None,
                    )
                )
                continue

            tgt_uri = top.get("target_uri", "")
            if not tgt_uri:
                continue

            # ----------------------------------------------------------------
            # c. Unit check — source side
            # ----------------------------------------------------------------
            unit_node = _sparql_one(src_graph, _SRC_UNIT_QUERY, {"subject": rdflib.URIRef(src_uri)})
            unit_str = str(unit_node) if unit_node is not None else None

            if unit_str is None or unit_str not in UNIT_STRING_TO_IRI:
                findings.append(
                    LintFinding(
                        rule="unit_not_detected",
                        severity="INFO",
                        source_uri=src_uri,
                        target_uri=tgt_uri,
                        message=f"No detectable unit on source field '{src_uri}'.",
                        fnml_suggestion=None,
                    )
                )
                # Still run datatype check below — fall through after continue-skip
                _run_datatype_check(findings, src_graph, mst_graph, src_uri, tgt_uri)
                continue

            src_iri = UNIT_STRING_TO_IRI[unit_str]
            if src_iri is None:
                # Known unmappable unit (e.g. dBm)
                findings.append(
                    LintFinding(
                        rule="unit_not_detected",
                        severity="INFO",
                        source_uri=src_uri,
                        target_uri=tgt_uri,
                        message=f"Unit '{unit_str}' has no QUDT IRI mapping.",
                        fnml_suggestion=None,
                    )
                )
                _run_datatype_check(findings, src_graph, mst_graph, src_uri, tgt_uri)
                continue

            # ----------------------------------------------------------------
            # d. Unit check — master side
            # ----------------------------------------------------------------
            tgt_unit_node = _sparql_one(
                mst_graph, _TGT_UNIT_QUERY, {"subject": rdflib.URIRef(tgt_uri)}
            )
            if tgt_unit_node is None:
                findings.append(
                    LintFinding(
                        rule="master_unit_missing",
                        severity="INFO",
                        source_uri=src_uri,
                        target_uri=tgt_uri,
                        message=f"No qudt:unit on master field '{tgt_uri}'.",
                        fnml_suggestion=None,
                    )
                )
                _run_datatype_check(findings, src_graph, mst_graph, src_uri, tgt_uri)
                continue

            tgt_iri = str(tgt_unit_node)

            # ----------------------------------------------------------------
            # e. Compatibility check
            # ----------------------------------------------------------------
            compat = units_compatible(src_iri, tgt_iri, qudt_graph)

            if compat is False:
                findings.append(
                    LintFinding(
                        rule="unit_dimension_mismatch",
                        severity="BLOCK",
                        source_uri=src_uri,
                        target_uri=tgt_uri,
                        message="Incompatible unit dimensions.",
                        fnml_suggestion=None,
                    )
                )
            elif compat is True:
                # Normalise both to full IRI for equality check
                if expand_unit_iri(src_iri) != expand_unit_iri(tgt_iri):
                    fnml = suggest_fnml(src_iri, tgt_iri, qudt_graph)
                    findings.append(
                        LintFinding(
                            rule="unit_conversion_required",
                            severity="WARNING",
                            source_uri=src_uri,
                            target_uri=tgt_uri,
                            message="Units are compatible but differ; conversion needed.",
                            fnml_suggestion=fnml,
                        )
                    )
                # else: identical units — no finding
            else:
                # compat is None → dimension vector missing
                findings.append(
                    LintFinding(
                        rule="unit_vector_missing",
                        severity="INFO",
                        source_uri=src_uri,
                        target_uri=tgt_uri,
                        message="Dimension vector missing for one or both units.",
                        fnml_suggestion=None,
                    )
                )

            # ----------------------------------------------------------------
            # f. Datatype check (always runs unless we already continued above)
            # ----------------------------------------------------------------
            _run_datatype_check(findings, src_graph, mst_graph, src_uri, tgt_uri)

        # --------------------------------------------------------------------
        # 7. --strict: re-classify WARNINGs → BLOCKs
        # --------------------------------------------------------------------
        if strict:
            upgraded: list[LintFinding] = []
            for f in findings:
                if f.severity == "WARNING":
                    upgraded.append(f.model_copy(update={"severity": "BLOCK"}))
                else:
                    upgraded.append(f)
            findings = upgraded

        # 8. Build summary and report
        summary = LintSummary(
            block=sum(1 for f in findings if f.severity == "BLOCK"),
            warning=sum(1 for f in findings if f.severity == "WARNING"),
            info=sum(1 for f in findings if f.severity == "INFO"),
        )
        report = LintReport(findings=findings, summary=summary)

        # 9. Write output
        with open_output(output) as fh:
            fh.write(report.model_dump_json(indent=2))

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # 10. Exit code AFTER writing output
    has_block = any(f.severity == "BLOCK" for f in findings)
    sys.exit(1 if (has_block or sssom_errors) else 0)


def _run_datatype_check(
    findings: list[LintFinding],
    src_graph: rdflib.Graph,
    mst_graph: rdflib.Graph,
    src_uri: str,
    tgt_uri: str,
) -> None:
    """Append a datatype_mismatch WARNING if numeric vs string mismatch detected."""
    src_dt_node = _sparql_one(src_graph, _SRC_DTYPE_QUERY, {"subject": rdflib.URIRef(src_uri)})
    tgt_dt_node = _sparql_one(mst_graph, _TGT_DTYPE_QUERY, {"subject": rdflib.URIRef(tgt_uri)})

    # None-guard before any string coercion
    if src_dt_node is None or tgt_dt_node is None:
        return

    src_dt = str(src_dt_node)
    tgt_dt = str(tgt_dt_node)

    src_numeric = src_dt in _NUMERIC_XSD
    src_string = src_dt in _STRING_XSD
    tgt_numeric = tgt_dt in _NUMERIC_XSD
    tgt_string = tgt_dt in _STRING_XSD

    mismatch = (src_numeric and tgt_string) or (src_string and tgt_numeric)
    if mismatch:
        findings.append(
            LintFinding(
                rule="datatype_mismatch",
                severity="WARNING",
                source_uri=src_uri,
                target_uri=tgt_uri,
                message=f"Datatype mismatch: source '{src_dt}' vs master '{tgt_dt}'.",
                fnml_suggestion=None,
            )
        )
