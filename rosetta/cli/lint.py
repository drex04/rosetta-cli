"""rosetta-lint: Validate unit and datatype compatibility in field mappings."""

import sys
from pathlib import Path

import click
import rdflib

from rosetta.core.accredit import load_log, parse_sssom_tsv
from rosetta.core.config import get_config_value, load_config
from rosetta.core.io import open_output
from rosetta.core.models import LintFinding, LintReport, LintSummary, SSSOMRow
from rosetta.core.unit_detect import detect_unit, recognized_unit_without_iri
from rosetta.core.units import (
    load_qudt_graph,
    suggest_fnml,
    units_compatible,
)

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

# LinkML numeric types — mismatch triggers datatype_mismatch WARNING
_NUMERIC_LINKML = {
    "integer",
    "int",
    "float",
    "double",
    "decimal",
    "long",
    "short",
    "nonNegativeInteger",
    "positiveInteger",
}


def check_sssom_proposals(
    rows: list[SSSOMRow],
    log: list[SSSOMRow],
) -> list[LintFinding]:
    """Return list of LintFindings. Empty list = no errors."""
    findings: list[LintFinding] = []

    # 1. MaxOneMmcPerPair
    mmc_rows = [r for r in rows if r.mapping_justification == MMC]
    pair_counts: dict[tuple[str, str], int] = {}
    for r in mmc_rows:
        pair = (r.subject_id, r.object_id)
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
    for (subject_id, object_id), count in pair_counts.items():
        if count > 1:
            findings.append(
                LintFinding(
                    rule="max_one_mmc_per_pair",
                    severity="BLOCK",
                    source_uri=subject_id,
                    target_uri=object_id,
                    message=f"MaxOneMmcPerPair: {count} rows for {subject_id} → {object_id}",
                )
            )

    # 2. NoHumanCurationReproposal
    if log:
        approved_pairs: set[tuple[str, str]] = set()
        rejected_pairs: set[tuple[str, str]] = set()
        for r in log:
            if r.mapping_justification == HC:
                # Distinguish approved vs rejected by predicate
                if r.predicate_id == "owl:differentFrom":
                    rejected_pairs.add((r.subject_id, r.object_id))
                else:
                    approved_pairs.add((r.subject_id, r.object_id))

        for r in mmc_rows:
            pair = (r.subject_id, r.object_id)
            if pair in approved_pairs:
                findings.append(
                    LintFinding(
                        rule="reproposal_of_approved",
                        severity="BLOCK",
                        source_uri=r.subject_id,
                        target_uri=r.object_id,
                        message=f"Approved HumanCuration exists for {r.subject_id} → {r.object_id}",
                    )
                )
            elif pair in rejected_pairs:
                findings.append(
                    LintFinding(
                        rule="reproposal_of_rejected",
                        severity="BLOCK",
                        source_uri=r.subject_id,
                        target_uri=r.object_id,
                        message=f"Rejected HumanCuration exists for {r.subject_id} → {r.object_id}",
                    )
                )

    # 3. ValidPredicate
    for r in mmc_rows:
        if r.predicate_id not in _VALID_PREDICATES:
            findings.append(
                LintFinding(
                    rule="invalid_predicate",
                    severity="BLOCK",
                    source_uri=r.subject_id,
                    target_uri=r.object_id,
                    message=f"{r.subject_id} → {r.object_id}: invalid predicate '{r.predicate_id}'",
                )
            )

    return findings


def _unit_label(row_id: str, label: str) -> str:
    """Return the best available field name for unit detection."""
    if label:
        return label
    local = row_id.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return local


def _unit_not_detected(row_id: str, side: str, name: str, description: str) -> LintFinding:
    """Build an INFO finding distinguishing 'no unit' from 'recognized, no QUDT IRI'."""
    if recognized_unit_without_iri(name, description):
        message = f"Unit recognized in {side} field but has no QUDT IRI mapping"
    else:
        message = f"No detectable unit in {side} field name"
    return LintFinding(
        rule="unit_not_detected",
        severity="INFO",
        source_uri=row_id,
        message=message,
    )


def _check_units(
    findings: list[LintFinding],
    row: SSSOMRow,
    qudt_graph: rdflib.Graph,
) -> None:
    """Append unit-related findings for a single SSSOM row."""
    src_name = _unit_label(row.subject_id, row.subject_label)
    tgt_name = _unit_label(row.object_id, row.object_label)
    src_iri = detect_unit(src_name, row.subject_label)
    tgt_iri = detect_unit(tgt_name, row.object_label)

    if src_iri is None or tgt_iri is None:
        if src_iri is None:
            findings.append(
                _unit_not_detected(row.subject_id, "subject", src_name, row.subject_label)
            )
        if tgt_iri is None:
            findings.append(_unit_not_detected(row.object_id, "object", tgt_name, row.object_label))
        return

    compat = units_compatible(src_iri, tgt_iri, qudt_graph)
    src_label = src_iri.removeprefix("unit:")
    tgt_label = tgt_iri.removeprefix("unit:")

    if compat is False:
        findings.append(
            LintFinding(
                rule="unit_dimension_mismatch",
                severity="BLOCK",
                source_uri=row.subject_id,
                target_uri=row.object_id,
                message=f"Incompatible unit dimensions: {src_label} vs {tgt_label}",
            )
        )
    elif compat is True:
        if src_iri != tgt_iri:
            findings.append(
                LintFinding(
                    rule="unit_conversion_required",
                    severity="WARNING",
                    source_uri=row.subject_id,
                    target_uri=row.object_id,
                    message=f"Same dimension, different units: {src_label} vs {tgt_label}",
                    fnml_suggestion=suggest_fnml(src_iri, tgt_iri, qudt_graph),
                )
            )
        # else: identical units — no finding
    else:
        # compat is None → dimension vector missing
        findings.append(
            LintFinding(
                rule="unit_vector_missing",
                severity="INFO",
                source_uri=row.subject_id,
                message="Unit dimension vector missing",
            )
        )


def _check_datatype(findings: list[LintFinding], row: SSSOMRow) -> None:
    """Append a datatype_mismatch WARNING if numeric vs non-numeric mismatch detected."""
    if row.subject_datatype is None or row.object_datatype is None:
        return
    src_numeric = row.subject_datatype in _NUMERIC_LINKML
    tgt_numeric = row.object_datatype in _NUMERIC_LINKML
    if src_numeric != tgt_numeric:
        findings.append(
            LintFinding(
                rule="datatype_mismatch",
                severity="WARNING",
                source_uri=row.subject_id,
                target_uri=row.object_id,
                message=f"Datatype mismatch: {row.subject_datatype} vs {row.object_datatype}",
            )
        )


@click.command()
@click.option(
    "--sssom",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="SSSOM TSV file to lint.",
)
@click.option("--output", "-o", default=None, help="Output JSON file (default: stdout).")
@click.option("--strict", is_flag=True, default=False, help="Upgrade all WARNINGs to BLOCKs.")
@click.option("--config", default=None, help="Path to rosetta.toml config file.")
def cli(sssom: str | None, output: str | None, strict: bool, config: str | None) -> None:
    """Lint a SSSOM proposal TSV for unit/datatype compatibility and structural rules."""
    if sssom is None:
        click.echo("Error: --sssom is required.", err=True)
        sys.exit(1)

    rows = parse_sssom_tsv(Path(sssom))
    cfg = load_config(Path(config)) if config else load_config()
    log_path_str = get_config_value(cfg, "accredit", "log")
    log = load_log(Path(log_path_str)) if log_path_str and Path(log_path_str).exists() else []

    findings: list[LintFinding] = []

    # 1. Proposal checks
    findings.extend(check_sssom_proposals(rows, log))

    # 2. Per-row unit + datatype checks
    try:
        qudt_graph = load_qudt_graph()
        for row in rows:
            try:
                _check_units(findings, row, qudt_graph)
                _check_datatype(findings, row)
            except Exception as exc:  # noqa: BLE001
                findings.append(
                    LintFinding(
                        rule="parse_error", severity="INFO", source_uri="", message=str(exc)
                    )
                )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            LintFinding(rule="parse_error", severity="WARNING", source_uri="", message=str(exc))
        )

    # 3. --strict: upgrade WARNINGs → BLOCKs
    if strict:
        findings = [
            f.model_copy(update={"severity": "BLOCK"}) if f.severity == "WARNING" else f
            for f in findings
        ]

    # 4. Build report and write
    summary = LintSummary(
        block=sum(1 for f in findings if f.severity == "BLOCK"),
        warning=sum(1 for f in findings if f.severity == "WARNING"),
        info=sum(1 for f in findings if f.severity == "INFO"),
    )
    report = LintReport(findings=findings, summary=summary)
    with open_output(output) as fh:
        fh.write(report.model_dump_json(indent=2))

    sys.exit(1 if any(f.severity == "BLOCK" for f in findings) else 0)
