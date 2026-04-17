"""SSSOM + LinkML schemas → linkml-map TransformationSpecification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast  # noqa: F401

from linkml_map.datamodel.transformer_model import (
    ClassDerivation,
    KeyVal,
    SlotDerivation,
    TransformationSpecification,
    UnitConversionConfiguration,
)
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rosetta.core.models import CoverageReport, SSSOMRow

# ---------------------------------------------------------------------------
# 4b — Row filtering
# ---------------------------------------------------------------------------

_EXCLUDED_PREDICATE_OWL_DIFFERENT_FROM = "owl:differentFrom"
_ACCEPTED_PREDICATES = frozenset({"skos:exactMatch", "skos:closeMatch"})
_HC = "semapv:HumanCuration"
_MMC = "semapv:ManualMappingCuration"


def filter_rows(
    rows: list[SSSOMRow],
    source_prefix: str,
    include_manual: bool,
) -> tuple[list[SSSOMRow], dict[str, list[SSSOMRow]]]:
    """Return (accepted, excluded_by_stage) where excluded_by_stage has keys:
    'prefix', 'predicate', 'justification'. owl:differentFrom rows are silently dropped.
    """
    accepted_justifications: set[str] = {_HC}
    if include_manual:
        accepted_justifications.add(_MMC)

    excluded: dict[str, list[SSSOMRow]] = {"prefix": [], "predicate": [], "justification": []}
    remaining: list[SSSOMRow] = []
    prefix_marker = f"{source_prefix}:"

    for row in rows:
        if row.predicate_id == _EXCLUDED_PREDICATE_OWL_DIFFERENT_FROM:
            continue  # silent drop (derank marker)
        if not row.subject_id.startswith(prefix_marker):
            excluded["prefix"].append(row)
            continue
        if row.predicate_id not in _ACCEPTED_PREDICATES:
            excluded["predicate"].append(row)
            continue
        if row.mapping_justification not in accepted_justifications:
            excluded["justification"].append(row)
            continue
        remaining.append(row)
    return remaining, excluded


# ---------------------------------------------------------------------------
# 4c — Row classification
# ---------------------------------------------------------------------------


@dataclass
class _ClassMapping:
    source_class_name: str
    target_class_name: str
    row: SSSOMRow


@dataclass
class _SlotMapping:
    source_slot_name: str
    source_owning_class: str
    target_slot_name: str
    target_owning_class: str
    row: SSSOMRow


@dataclass
class _Unresolved:
    row: SSSOMRow
    side: str  # "subject" or "object" or "mixed"
    reason: str


_Classification = _ClassMapping | _SlotMapping | _Unresolved


@dataclass
class _ClassifyContext:
    src_view: SchemaView
    master_view: SchemaView
    src_slot_owners: dict[str, str]
    mst_slot_owners: dict[str, str]


def _build_slot_owner_index(view: SchemaView) -> dict[str, str]:
    """Build a slot_name → owning_class index once per SchemaView.

    Uses the class's *direct* slot declarations (cls.slots) so that inherited
    slots are attributed to the class that defines them, not subclasses.
    Falls back to induced slots for any slot not covered by direct declarations
    (e.g. schemas that only use slot_usage without direct class-level slots).
    """
    index: dict[str, str] = {}
    # Pass 1: direct slot declarations — "defining class" wins
    for class_name in view.all_classes():  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
        cls = view.get_class(class_name)  # pyright: ignore[reportUnknownMemberType]
        for slot_name in list(getattr(cls, "slots", []) or []):
            index.setdefault(str(slot_name), str(class_name))
    # Pass 2: induced slots fill any gaps (slot_usage-only patterns)
    for class_name in view.all_classes():  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
        for slot in view.class_induced_slots(class_name):  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
            slot_key = str(slot.name)  # pyright: ignore[reportUnknownMemberType]
            index.setdefault(slot_key, str(class_name))
    return index


def _owning_class(index: dict[str, str], slot_name: str, schema_name: str) -> str:
    """Lookup in the pre-built index; raise if missing."""
    owner = index.get(slot_name)
    if owner is None:
        raise ValueError(f"slot {slot_name!r} has no owning class in schema {schema_name!r}")
    return owner


def _local_name(curie: str) -> str:
    """Strip the prefix from a CURIE, returning the local name.

    SchemaView.get_class / get_slot match on the element *name*, not on the
    CURIE — so "nor_radar:Observation" must be resolved to "Observation" before
    the lookup.  Falls back to the full string if no ':' is present.
    """
    return curie.split(":", 1)[-1] if ":" in curie else curie


def classify_row(row: SSSOMRow, ctx: _ClassifyContext) -> _Classification:
    """Resolve subject in source schema, object in master schema.
    Mixed-kind (slot↔class) is signalled via _Unresolved(side="mixed"); caller raises.
    """
    subj_name = _local_name(row.subject_id)
    obj_name = _local_name(row.object_id)
    src_class = ctx.src_view.get_class(subj_name, strict=False)  # pyright: ignore[reportUnknownMemberType]
    src_slot = ctx.src_view.get_slot(subj_name, strict=False)  # pyright: ignore[reportUnknownMemberType]
    mst_class = ctx.master_view.get_class(obj_name, strict=False)  # pyright: ignore[reportUnknownMemberType]
    mst_slot = ctx.master_view.get_slot(obj_name, strict=False)  # pyright: ignore[reportUnknownMemberType]

    if src_class and mst_class:
        return _ClassMapping(
            source_class_name=str(src_class.name),  # pyright: ignore[reportUnknownMemberType]
            target_class_name=str(mst_class.name),  # pyright: ignore[reportUnknownMemberType]
            row=row,
        )
    if src_slot and mst_slot:
        owner_src = _owning_class(
            ctx.src_slot_owners,
            str(src_slot.name),
            "source",  # pyright: ignore[reportUnknownMemberType]
        )
        owner_mst = _owning_class(
            ctx.mst_slot_owners,
            str(mst_slot.name),
            "master",  # pyright: ignore[reportUnknownMemberType]
        )
        return _SlotMapping(
            source_slot_name=str(src_slot.name),
            source_owning_class=owner_src,
            target_slot_name=str(mst_slot.name),
            target_owning_class=owner_mst,
            row=row,
        )
    if not src_class and not src_slot:
        return _Unresolved(row=row, side="subject", reason="no matching class_uri or slot_uri")
    if not mst_class and not mst_slot:
        return _Unresolved(row=row, side="object", reason="no matching class_uri or slot_uri")
    # mixed kinds — caller raises
    return _Unresolved(
        row=row, side="mixed", reason="subject and object are different kinds (class vs slot)"
    )


# ---------------------------------------------------------------------------
# 4d — Composite grouping
# ---------------------------------------------------------------------------


def group_composites(
    rows: list[SSSOMRow],
) -> tuple[dict[str, list[SSSOMRow]], list[SSSOMRow]]:
    """Return (groups_by_id, singletons). A row with mapping_group_id joins a group;
    rows without one are singletons.
    """
    groups: dict[str, list[SSSOMRow]] = {}
    singletons: list[SSSOMRow] = []
    for row in rows:
        if row.mapping_group_id:
            groups.setdefault(row.mapping_group_id, []).append(row)
        else:
            singletons.append(row)
    return groups, singletons


# ---------------------------------------------------------------------------
# 4e — Derivation builders
# ---------------------------------------------------------------------------


def build_class_derivation(
    target_class: str,
    source_class: str,
    slot_derivations: list[SlotDerivation],
) -> ClassDerivation:
    """Group SlotDerivations under a target class. upstream ClassDerivation.slot_derivations
    is Optional[dict[str, SlotDerivation]] keyed by target slot name — see container-asymmetry
    note in Plan 16-01 Context.
    """
    return ClassDerivation(
        name=target_class,
        populated_from=source_class,
        slot_derivations={sd.name: sd for sd in slot_derivations},
    )


def build_slot_derivation(m: _SlotMapping) -> SlotDerivation:
    """Build a SlotDerivation from a _SlotMapping classification.

    GA3: if subject_datatype and object_datatype both present and differ,
    set range=object_datatype (target datatype).
    Unit conversion is deferred to 16-02's YarrrmlCompiler.
    """
    unit_conv: UnitConversionConfiguration | None = None
    dtype_range: str | None = None
    if m.row.subject_datatype and m.row.object_datatype:
        if m.row.subject_datatype != m.row.object_datatype:
            dtype_range = m.row.object_datatype
    return SlotDerivation(
        name=m.target_slot_name,
        populated_from=m.source_slot_name,
        range=dtype_range,
        unit_conversion=unit_conv,
    )


def build_composite_slot_derivation(group_id: str, members: list[SSSOMRow]) -> SlotDerivation:
    """Build a composite SlotDerivation from a group of rows sharing mapping_group_id.

    Fatal if composition_expr is inconsistent across members OR if members target
    multiple different slots. Row IDs are surfaced in the error for diagnosability.

    The returned SlotDerivation.name is the target object_id CURIE; the caller
    (Wave 7 _resolve_composite_groups) resolves it to a schema slot name.
    """
    exprs = {r.composition_expr for r in members if r.composition_expr}
    if not exprs:
        row_ids = [r.record_id for r in members]
        raise ValueError(
            f"mapping_group_id={group_id!r} has no composition_expr on any member. "
            f"Composite mappings require composition_expr. Row IDs: {row_ids}"
        )
    if len(exprs) != 1:
        raise ValueError(
            f"mapping_group_id={group_id!r} has inconsistent composition_expr "
            f"across rows: {sorted(exprs)!r}. Row IDs: {[r.record_id for r in members]}"
        )
    target_slots = {r.object_id for r in members}
    if len(target_slots) != 1:
        raise ValueError(
            f"mapping_group_id={group_id!r} spans multiple target slots: {sorted(target_slots)!r}"
        )
    expr = next(iter(exprs))
    target = next(iter(target_slots))
    return SlotDerivation(name=target, expr=expr)


# ---------------------------------------------------------------------------
# Wave 7 — build_spec orchestrator + helpers
# ---------------------------------------------------------------------------


def _classify_singletons(
    singletons: list[SSSOMRow],
    ctx: _ClassifyContext,
    coverage: CoverageReport,
    force: bool,
) -> tuple[list[_ClassMapping], list[_SlotMapping]]:
    """Classify non-composite rows.

    Populates coverage.unresolved_subjects / coverage.unresolved_objects.
    Mixed-kind (subject is a class but object is a slot, or vice versa) is ALWAYS fatal —
    --force does not bypass it. Unresolvable CURIEs raise unless --force is set.
    """
    class_mappings: list[_ClassMapping] = []
    slot_mappings: list[_SlotMapping] = []
    for row in singletons:
        c = classify_row(row, ctx)
        if isinstance(c, _ClassMapping):
            class_mappings.append(c)
        elif isinstance(c, _SlotMapping):
            slot_mappings.append(c)
        else:
            if c.side == "mixed":
                raise ValueError(
                    f"mixed-kind mapping in row record_id={row.record_id!r}: "
                    f"subject={row.subject_id}, object={row.object_id} "
                    "(data-integrity error; --force does NOT bypass this)"
                )
            target_list = (
                coverage.unresolved_subjects if c.side == "subject" else coverage.unresolved_objects
            )
            target_list.append(
                {
                    "curie": row.subject_id if c.side == "subject" else row.object_id,
                    "reason": c.reason,
                }
            )
    if (coverage.unresolved_subjects or coverage.unresolved_objects) and not force:
        raise ValueError(
            f"Unresolvable CURIEs: {len(coverage.unresolved_subjects)} subject(s), "
            f"{len(coverage.unresolved_objects)} object(s). "
            "Pass --force to proceed with a best-effort spec."
        )
    return class_mappings, slot_mappings


def _resolve_composite_groups(
    groups: dict[str, list[SSSOMRow]],
    master_view: SchemaView,
    mst_slot_owners: dict[str, str],
    coverage: CoverageReport,
) -> list[tuple[str, SlotDerivation]]:
    """Resolve composite groups to (owner_class_name, SlotDerivation) pairs.

    Always fatal on internal inconsistency (delegated to build_composite_slot_derivation).
    Records resolved/unresolved status in coverage.composite_groups.
    """
    out: list[tuple[str, SlotDerivation]] = []
    for gid, members in groups.items():
        sd_tentative = build_composite_slot_derivation(gid, members)  # raises on inconsistency
        target_slot_obj = master_view.get_slot(_local_name(sd_tentative.name), strict=False)
        if not target_slot_obj:
            coverage.composite_groups.append(
                {
                    "group_id": gid,
                    "member_row_ids": [m.record_id or "" for m in members],
                    "target_slot": sd_tentative.name,
                    "resolved": False,
                }
            )
            continue
        resolved_name = str(target_slot_obj.name)
        sd = SlotDerivation(name=resolved_name, expr=sd_tentative.expr)
        owner = _owning_class(mst_slot_owners, resolved_name, "master")
        out.append((owner, sd))
        coverage.composite_groups.append(
            {
                "group_id": gid,
                "member_row_ids": [m.record_id or "" for m in members],
                "target_slot": resolved_name,
                "resolved": True,
            }
        )
    return out


def _collect_mappings(
    class_mappings: list[_ClassMapping],
    slot_mappings: list[_SlotMapping],
    composite_derivations: list[tuple[str, SlotDerivation]],
    coverage: CoverageReport,
) -> tuple[dict[str, list[SlotDerivation]], dict[str, str]]:
    """Build slots_by_target_class and source_for_target from all mapping kinds.

    Side-effects: populates coverage.resolved_class_mappings, resolved_slot_mappings,
    and datatype_warnings.
    """
    slots_by_target_class: dict[str, list[SlotDerivation]] = {}
    source_for_target: dict[str, str] = {}

    for cm in class_mappings:
        source_for_target[cm.target_class_name] = cm.source_class_name
        if cm.target_class_name not in slots_by_target_class:
            slots_by_target_class[cm.target_class_name] = []
        coverage.resolved_class_mappings.append(f"{cm.row.subject_id} → {cm.row.object_id}")

    for sm in slot_mappings:
        slots_by_target_class.setdefault(sm.target_owning_class, []).append(
            build_slot_derivation(sm)
        )
        # NOTE: source_for_target is NOT populated here — only explicit class-level
        # mapping rows may register a class. The F7 guard below catches any slot
        # whose owning class has no explicit class mapping.
        coverage.resolved_slot_mappings.append(f"{sm.row.subject_id} → {sm.row.object_id}")
        if (
            sm.row.subject_datatype
            and sm.row.object_datatype
            and sm.row.subject_datatype != sm.row.object_datatype
        ):
            coverage.datatype_warnings.append(
                {
                    "subject_id": sm.row.subject_id,
                    "subject_datatype": sm.row.subject_datatype,
                    "object_id": sm.row.object_id,
                    "object_datatype": sm.row.object_datatype,
                }
            )

    for owner_class, sd in composite_derivations:
        slots_by_target_class.setdefault(owner_class, []).append(sd)

    return slots_by_target_class, source_for_target


def _populate_required_slot_coverage(
    source_for_target: dict[str, str],
    slots_by_target_class: dict[str, list[SlotDerivation]],
    master_view: SchemaView,
    coverage: CoverageReport,
) -> None:
    """Populate coverage.unmapped_required_master_slots for each resolved target class."""
    for target_class in source_for_target:
        master_cls = master_view.get_class(target_class, strict=False)
        if master_cls is None:
            continue
        induced = master_view.class_induced_slots(target_class)  # pyright: ignore[reportUnknownVariableType]
        required_slot_names = {
            str(s.name)  # pyright: ignore[reportUnknownMemberType]
            for s in induced
            if bool(getattr(s, "required", False))
        }
        resolved_slot_names = {sd.name for sd in slots_by_target_class.get(target_class, [])}
        for missing in sorted(required_slot_names - resolved_slot_names):
            coverage.unmapped_required_master_slots.append(f"{target_class}.{missing}")


def _ancestors(class_name: str, view: SchemaView) -> set[str]:
    """Return the set of all ancestors (is_a chain) of class_name, including itself."""
    result: set[str] = set()
    current: str | None = class_name
    while current is not None:
        result.add(current)
        cls = view.get_class(current, strict=False)  # pyright: ignore[reportUnknownMemberType]
        if cls is None:
            break
        parent = getattr(cls, "is_a", None)
        current = str(parent) if parent else None
    return result


def _nearest_mapped_ancestor(
    class_name: str,
    mapped_classes: set[str],
    view: SchemaView,
) -> str | None:
    """Find the best mapped class for a slot owner.

    Two cases:
    1. class_name is in mapped_classes — return it directly.
    2. class_name is an *ancestor* of one or more mapped classes (i.e., the slot
       is defined on a superclass but the mapping targets a subclass) — return
       the first mapped class whose ancestor set includes class_name.
    3. Walk up is_a from class_name to find a mapped ancestor.
    Returns None if no relationship is found.
    """
    # Case 1: direct match
    if class_name in mapped_classes:
        return class_name
    # Case 2: class_name is a superclass of some mapped class
    for mc in mapped_classes:
        if class_name in _ancestors(mc, view):
            return mc
    # Case 3: walk up from class_name
    current: str | None = class_name
    while current is not None:
        if current in mapped_classes:
            return current
        cls = view.get_class(current, strict=False)  # pyright: ignore[reportUnknownMemberType]
        if cls is None:
            break
        parent = getattr(cls, "is_a", None)
        current = str(parent) if parent else None
    return None


def _remap_to_mapped_classes(
    slot_mappings: list[_SlotMapping],
    composite_derivations: list[tuple[str, SlotDerivation]],
    mapped_classes: set[str],
    master_view: SchemaView,
) -> tuple[list[_SlotMapping], list[tuple[str, SlotDerivation]]]:
    """Remap owning classes to the nearest mapped ancestor.

    Slots declared on a superclass (e.g. Entity.hasLatitude) but whose SSSOM
    class mapping targets a subclass (e.g. Track) are re-attributed to that
    subclass via is_a chain traversal.  This lets F7 pass without requiring the
    author to explicitly list every intermediate ancestor.
    """
    remapped_slots: list[_SlotMapping] = []
    for sm in slot_mappings:
        nearest = _nearest_mapped_ancestor(sm.target_owning_class, mapped_classes, master_view)
        if nearest is not None and nearest != sm.target_owning_class:
            sm = _SlotMapping(
                source_slot_name=sm.source_slot_name,
                source_owning_class=sm.source_owning_class,
                target_slot_name=sm.target_slot_name,
                target_owning_class=nearest,
                row=sm.row,
            )
        remapped_slots.append(sm)

    remapped_composites: list[tuple[str, SlotDerivation]] = []
    for owner, sd in composite_derivations:
        nearest = _nearest_mapped_ancestor(owner, mapped_classes, master_view)
        remapped_composites.append((nearest if nearest is not None else owner, sd))

    return remapped_slots, remapped_composites


def _assemble_class_derivations(
    class_mappings: list[_ClassMapping],
    slot_mappings: list[_SlotMapping],
    composite_derivations: list[tuple[str, SlotDerivation]],
    coverage: CoverageReport,
    master_view: SchemaView,
) -> list[ClassDerivation]:
    """Group slot derivations under their owning ClassDerivation.

    Fatal if any class referenced by slots lacks a class-level mapping (F7).
    Slots inherited from superclasses are re-attributed to the nearest mapped
    ancestor via is_a traversal before the F7 check.
    Populates coverage.unmapped_required_master_slots (review requirement).
    """
    mapped_classes = {cm.target_class_name for cm in class_mappings}

    # Remap inherited slot owners to the nearest mapped ancestor
    slot_mappings, composite_derivations = _remap_to_mapped_classes(
        slot_mappings, composite_derivations, mapped_classes, master_view
    )

    slots_by_target_class, source_for_target = _collect_mappings(
        class_mappings, slot_mappings, composite_derivations, coverage
    )

    # F7: every target class referenced by any slot must have a class-level mapping.
    # source_for_target only contains classes from explicit class-level mapping rows.
    for target_class in slots_by_target_class:
        if target_class not in source_for_target:
            raise ValueError(
                f"slots mapped to target class {target_class!r} but no class-level mapping "
                f"for it. Add a SSSOM row mapping the source class to {target_class!r}. "
                f"(--force does NOT bypass this — class resolution is required for a valid spec.)"
            )
    # Composite derivations whose owner still isn't mapped are fatal.
    for tc, _sd in composite_derivations:
        if tc not in source_for_target:
            raise ValueError(
                f"composite slot mapped to target class {tc!r} but no class-level mapping "
                f"for it. Add a SSSOM row mapping the source class to {tc!r}. "
                f"(--force does NOT bypass this — class resolution is required for a valid spec.)"
            )

    _populate_required_slot_coverage(
        source_for_target, slots_by_target_class, master_view, coverage
    )

    return [
        build_class_derivation(
            target_class=tc,
            source_class=source_for_target[tc],
            slot_derivations=slots,
        )
        for tc, slots in slots_by_target_class.items()
    ]


ROSETTA_GLOBAL_PREFIXES: dict[str, str] = {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "semapv": "https://w3id.org/semapv/vocab/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "qudt": "http://qudt.org/schema/qudt/",
}


def _build_prefix_map(
    source: SchemaDefinition,
    master: SchemaDefinition,
) -> dict[str, KeyVal]:
    """Merge prefix maps from rosetta globals, master, and source (source wins on collision).

    Returns a dict[str, KeyVal] suitable for TransformationSpecification.prefixes.
    """
    merged: dict[str, str] = ROSETTA_GLOBAL_PREFIXES.copy()

    def _add_schema_prefixes(schema: SchemaDefinition, dest: dict[str, str]) -> None:
        raw: object = schema.prefixes or {}
        if isinstance(raw, dict):
            items = raw.items()  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
        elif isinstance(raw, list):
            # Some linkml versions serialize prefixes as a list of Prefix objects
            items = ((getattr(p, "prefix_prefix", None) or str(p), p) for p in raw)  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType]
        else:
            return
        for k, v in items:  # pyright: ignore[reportUnknownVariableType]
            uri = getattr(v, "prefix_reference", None) or str(v)
            dest[str(k)] = str(uri)

    _add_schema_prefixes(master, merged)
    _add_schema_prefixes(source, merged)

    return {k: KeyVal(key=k, value=iri) for k, iri in merged.items()}


def _resolve_schema_path(raw: str | Path, label: str) -> str:
    """Validate *raw* is a non-empty path to an existing file; return its absolute str form.

    Raises ValueError with *label* in the message on any failure.
    """
    path_str = str(raw)
    if not path_str or not Path(path_str).is_file():
        raise ValueError(f"build_spec: {label} is required and must exist as a file; got {raw!r}")
    return str(Path(path_str).resolve())


def build_spec(
    sssom_rows: list[SSSOMRow],
    source: SchemaDefinition,
    master: SchemaDefinition,
    *,
    source_schema_path: str | Path,
    target_schema_path: str | Path,
    include_manual: bool = False,
    force: bool = False,
    prefiltered: tuple[list[SSSOMRow], dict[str, list[SSSOMRow]]] | None = None,
) -> tuple[TransformationSpecification, CoverageReport]:
    """Top-level orchestrator. Pure-function style; all I/O is caller's job.

    --force bypasses unresolvable-CURIE errors only. Mixed-kind mappings,
    missing class-level mappings, and inconsistent composite expressions are
    ALWAYS fatal — data-integrity errors, not coverage issues.

    prefiltered: optional pre-computed result of filter_rows(sssom_rows, src_prefix,
    include_manual). When supplied, the internal filter_rows call is skipped and the
    provided (remaining, excluded) tuple is used directly. Library callers that do
    not pass prefiltered continue to work without change (defaults to None).
    """
    # Validate and resolve schema paths (fail-fast; never write empty string to spec)
    _resolved_src = _resolve_schema_path(source_schema_path, "source_schema_path")
    _resolved_tgt = _resolve_schema_path(target_schema_path, "target_schema_path")

    src_prefix = str(source.default_prefix or "")
    if not src_prefix:
        raise ValueError("source schema lacks default_prefix")
    mst_prefix = str(master.default_prefix or "")

    if prefiltered is not None:
        remaining, excluded = prefiltered
    else:
        remaining, excluded = filter_rows(sssom_rows, src_prefix, include_manual)

    src_view = SchemaView(source)
    master_view = SchemaView(master)
    ctx = _ClassifyContext(
        src_view=src_view,
        master_view=master_view,
        src_slot_owners=_build_slot_owner_index(src_view),
        mst_slot_owners=_build_slot_owner_index(master_view),
    )

    coverage = CoverageReport(
        source_schema_prefix=src_prefix,
        master_schema_prefix=mst_prefix,
        rows_total=len(sssom_rows),
        rows_after_prefix_filter=len(sssom_rows) - len(excluded["prefix"]),
        rows_after_predicate_filter=(
            len(sssom_rows) - len(excluded["prefix"]) - len(excluded["predicate"])
        ),
        rows_after_justification_filter=len(remaining),
    )
    coverage.skipped_non_exact_predicates = [
        {"row_id": r.record_id or "", "predicate_id": r.predicate_id} for r in excluded["predicate"]
    ]

    groups, singletons = group_composites(remaining)
    class_mappings, slot_mappings = _classify_singletons(singletons, ctx, coverage, force)
    composite_derivations = _resolve_composite_groups(
        groups, master_view, ctx.mst_slot_owners, coverage
    )
    class_derivations = _assemble_class_derivations(
        class_mappings, slot_mappings, composite_derivations, coverage, master_view
    )

    spec = TransformationSpecification(
        id=f"https://rosetta.interop/transform/{src_prefix}-to-{mst_prefix}",
        title=f"Transform {src_prefix} → {mst_prefix}",
        class_derivations=class_derivations,
        source_schema=_resolved_src,
        target_schema=_resolved_tgt,
        prefixes=_build_prefix_map(source, master),
    )

    return spec, coverage
