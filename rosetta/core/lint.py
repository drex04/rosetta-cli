"""rosetta core lint: Lint logic for SSSOM proposal validation."""

from pathlib import Path

import rdflib
from linkml_runtime.utils.schemaview import SchemaView

from rosetta.core.models import LintFinding, LintReport, LintSummary, SSSOMRow
from rosetta.core.schema_utils import check_slot_class_reachability
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


def _check_duplicate_mmc_pairs(findings: list[LintFinding], mmc_rows: list[SSSOMRow]) -> None:
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


def _check_duplicate_mmc_subjects(findings: list[LintFinding], mmc_rows: list[SSSOMRow]) -> None:
    subject_counts: dict[str, list[str]] = {}
    for r in mmc_rows:
        subject_counts.setdefault(r.subject_id, []).append(r.object_id)
    for subject_id, objects in subject_counts.items():
        if len(objects) > 1:
            findings.append(
                LintFinding(
                    rule="max_one_mmc_per_subject",
                    severity="BLOCK",
                    source_uri=subject_id,
                    target_uri=objects[0],
                    message=(
                        f"MaxOneMmcPerSubject: {subject_id} has {len(objects)} confirmed "
                        f"mappings ({', '.join(objects)}); only one is allowed"
                    ),
                )
            )


def _check_no_reproposal(
    findings: list[LintFinding], mmc_rows: list[SSSOMRow], log: list[SSSOMRow]
) -> None:
    if not log:
        return
    approved_pairs: set[tuple[str, str]] = set()
    rejected_pairs: set[tuple[str, str]] = set()
    for r in log:
        if r.mapping_justification == HC:
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


def _check_valid_predicates(findings: list[LintFinding], mmc_rows: list[SSSOMRow]) -> None:
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


def check_sssom_proposals(
    rows: list[SSSOMRow],
    log: list[SSSOMRow],
) -> list[LintFinding]:
    """Return list of LintFindings. Empty list = no errors."""
    findings: list[LintFinding] = [
        LintFinding(
            rule="hc_in_candidates",
            severity="BLOCK",
            source_uri=r.subject_id,
            target_uri=r.object_id,
            message="HumanCuration row found in candidates — HC belongs only in the audit log",
        )
        for r in rows
        if r.mapping_justification == HC
    ]

    mmc_rows = [r for r in rows if r.mapping_justification == MMC]
    _check_duplicate_mmc_pairs(findings, mmc_rows)
    _check_duplicate_mmc_subjects(findings, mmc_rows)
    _check_no_reproposal(findings, mmc_rows, log)
    _check_valid_predicates(findings, mmc_rows)

    return findings


def unit_label(row_id: str, label: str) -> str:
    """Return the best available field name for unit detection."""
    if label:
        return label
    local = row_id.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return local


def unit_not_detected(row_id: str, side: str, name: str, description: str) -> LintFinding:
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


def check_units(
    findings: list[LintFinding],
    row: SSSOMRow,
    qudt_graph: rdflib.Graph,
) -> None:
    """Append unit-related findings for a single SSSOM row."""
    src_name = unit_label(row.subject_id, row.subject_label)
    tgt_name = unit_label(row.object_id, row.object_label)
    src_iri = detect_unit(src_name, row.subject_label)
    tgt_iri = detect_unit(tgt_name, row.object_label)

    if src_iri is None or tgt_iri is None:
        if src_iri is None:
            findings.append(
                unit_not_detected(row.subject_id, "subject", src_name, row.subject_label)
            )
        if tgt_iri is None:
            findings.append(unit_not_detected(row.object_id, "object", tgt_name, row.object_label))
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


def check_datatype(findings: list[LintFinding], row: SSSOMRow) -> None:
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


def _check_reachability(
    findings: list[LintFinding],
    confirmed_rows: list[SSSOMRow],
    source_schema: str | Path,
    master_schema: str | Path,
) -> None:
    try:
        source_view = SchemaView(str(source_schema))
        master_view = SchemaView(str(master_schema))
    except Exception as exc:  # noqa: BLE001
        findings.append(
            LintFinding(
                rule="schema_parse_error",
                severity="BLOCK",
                source_uri="",
                message=f"Cannot load schema for reachability check: {exc}",
            )
        )
        return
    for mismatch in check_slot_class_reachability(confirmed_rows, source_view, master_view):
        findings.append(
            LintFinding(
                rule="slot_class_unreachable",
                severity="BLOCK",
                source_uri=mismatch.row.subject_id,
                target_uri=mismatch.row.object_id,
                message=(
                    f"Slot '{mismatch.target_slot_name}' belongs to class "
                    f"'{mismatch.target_owning_class}' which is not reachable from any "
                    f"mapped class ({', '.join(sorted(mismatch.mapped_target_classes))}). "
                    f"Map the source class to '{mismatch.target_owning_class}' or one of "
                    f"its subclasses."
                ),
            )
        )


def _check_units_and_datatypes(findings: list[LintFinding], confirmed_rows: list[SSSOMRow]) -> None:
    try:
        qudt_graph = load_qudt_graph()
        for row in confirmed_rows:
            try:
                check_units(findings, row, qudt_graph)
                check_datatype(findings, row)
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


def _build_report(findings: list[LintFinding], *, strict: bool) -> LintReport:
    if strict:
        findings = [
            f.model_copy(update={"severity": "BLOCK"}) if f.severity == "WARNING" else f
            for f in findings
        ]
    summary = LintSummary(
        block=sum(1 for f in findings if f.severity == "BLOCK"),
        warning=sum(1 for f in findings if f.severity == "WARNING"),
        info=sum(1 for f in findings if f.severity == "INFO"),
    )
    return LintReport(findings=findings, summary=summary)


def run_lint(
    rows: list[SSSOMRow],
    log: list[SSSOMRow],
    source_schema: str | Path,
    master_schema: str | Path,
    *,
    strict: bool = False,
) -> LintReport:
    """Run the full lint pipeline and return a LintReport."""
    findings: list[LintFinding] = []
    findings.extend(check_sssom_proposals(rows, log))

    confirmed_rows = [r for r in rows if r.mapping_justification in {MMC, HC}]
    _check_reachability(findings, confirmed_rows, source_schema, master_schema)
    _check_units_and_datatypes(findings, confirmed_rows)

    return _build_report(findings, strict=strict)
