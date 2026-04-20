"""Shared schema utilities for slot ownership, class hierarchy, and structural validation."""

from __future__ import annotations

from dataclasses import dataclass

from linkml_runtime.utils.schemaview import SchemaView

from rosetta.core.accredit import HC_JUSTIFICATION, MMC_JUSTIFICATION
from rosetta.core.models import SSSOMRow


def build_slot_owner_index(view: SchemaView) -> dict[str, str]:
    """Build a slot_name -> owning_class index once per SchemaView.

    Uses the class's *direct* slot declarations (cls.slots) so that inherited
    slots are attributed to the class that defines them, not subclasses.
    Falls back to induced slots for any slot not covered by direct declarations
    (e.g. schemas that only use slot_usage without direct class-level slots).
    """
    index: dict[str, str] = {}
    for class_name in view.all_classes():  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
        cls = view.get_class(class_name)  # pyright: ignore[reportUnknownMemberType]
        for slot_name in list(getattr(cls, "slots", []) or []):
            index.setdefault(str(slot_name), str(class_name))
    for class_name in view.all_classes():  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
        for slot in view.class_induced_slots(class_name):  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
            slot_key = str(slot.name)  # pyright: ignore[reportUnknownMemberType]
            index.setdefault(slot_key, str(class_name))
    return index


def local_name(curie: str) -> str:
    """Strip the prefix from a CURIE, returning the local name.

    SchemaView.get_class / get_slot match on the element *name*, not on the
    CURIE — so "nor_radar:Observation" must be resolved to "Observation" before
    the lookup.  Falls back to the full string if no ':' is present.
    """
    return curie.split(":", 1)[-1] if ":" in curie else curie


def ancestors(class_name: str, view: SchemaView) -> set[str]:
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


def nearest_mapped_ancestor(
    class_name: str,
    mapped_classes: set[str],
    view: SchemaView,
) -> str | None:
    """Find the best mapped class for a slot owner.

    Three cases:
    1. class_name is in mapped_classes — return it directly.
    2. class_name is an *ancestor* of one or more mapped classes (i.e., the slot
       is defined on a superclass but the mapping targets a subclass) — return
       the first mapped class whose ancestor set includes class_name.
    3. Walk up is_a from class_name to find a mapped ancestor.
    Returns None if no relationship is found.
    """
    if class_name in mapped_classes:
        return class_name
    for mc in mapped_classes:
        if class_name in ancestors(mc, view):
            return mc
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


@dataclass
class SlotClassMismatch:
    """A slot mapping whose target owning class is unreachable from any class mapping."""

    row: SSSOMRow
    target_slot_name: str
    target_owning_class: str
    mapped_target_classes: set[str]


def _classify_row_for_reachability(
    row: SSSOMRow,
    source_view: SchemaView,
    master_view: SchemaView,
    master_slot_owners: dict[str, str],
    mapped_classes: set[str],
    slot_rows: list[tuple[SSSOMRow, str, str]],
) -> None:
    """Classify a single row as class-level or slot-level for reachability checking."""
    subj_name = local_name(row.subject_id)
    obj_name = local_name(row.object_id)

    src_class = source_view.get_class(subj_name, strict=False)  # pyright: ignore[reportUnknownMemberType]
    mst_class = master_view.get_class(obj_name, strict=False)  # pyright: ignore[reportUnknownMemberType]

    if src_class and mst_class:
        mapped_classes.add(str(mst_class.name))  # pyright: ignore[reportUnknownMemberType]
        return

    src_slot = source_view.get_slot(subj_name, strict=False)  # pyright: ignore[reportUnknownMemberType]
    mst_slot = master_view.get_slot(obj_name, strict=False)  # pyright: ignore[reportUnknownMemberType]
    if src_slot and mst_slot:
        slot_name = str(mst_slot.name)  # pyright: ignore[reportUnknownMemberType]
        owner = master_slot_owners.get(slot_name)
        if owner is not None:
            slot_rows.append((row, slot_name, owner))


def check_slot_class_reachability(
    rows: list[SSSOMRow],
    source_view: SchemaView,
    master_view: SchemaView,
) -> list[SlotClassMismatch]:
    """Check that every slot mapping's owning class is reachable from a class mapping.

    Only inspects confirmed rows (ManualMappingCuration or HumanCuration).
    Returns a list of mismatches — empty means all slot mappings are structurally valid.
    """
    confirmed = [
        r for r in rows if r.mapping_justification in {MMC_JUSTIFICATION, HC_JUSTIFICATION}
    ]
    if not confirmed:
        return []

    master_slot_owners = build_slot_owner_index(master_view)
    mapped_classes: set[str] = set()
    slot_rows: list[tuple[SSSOMRow, str, str]] = []

    for row in confirmed:
        _classify_row_for_reachability(
            row, source_view, master_view, master_slot_owners, mapped_classes, slot_rows
        )

    if not mapped_classes or not slot_rows:
        return []

    return [
        SlotClassMismatch(
            row=row,
            target_slot_name=slot_name,
            target_owning_class=owner,
            mapped_target_classes=mapped_classes.copy(),
        )
        for row, slot_name, owner in slot_rows
        if nearest_mapped_ancestor(owner, mapped_classes, master_view) is None
    ]
