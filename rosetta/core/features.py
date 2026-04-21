"""Structural feature extraction for the Rosetta CLI toolkit."""

from __future__ import annotations

from typing import Any, cast

from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]


def _compute_depths(all_nodes: dict[str, Any]) -> dict[str, int]:
    """Return iterative is_a chain depths for every node (cycle-safe)."""
    depths: dict[str, int] = {}
    for node_name in all_nodes:
        if node_name in depths:
            continue
        chain: list[str] = []
        visited: set[str] = set()
        current: str = node_name
        while True:
            if current in visited:
                break
            visited.add(current)
            chain.append(current)
            node: Any = all_nodes.get(current)
            if node is None:
                break
            parent: str | None = getattr(node, "is_a", None)
            if not parent or parent not in all_nodes:
                break
            current = parent
        root_depth: int = depths.get(chain[-1], 0)
        for i, name in enumerate(reversed(chain)):
            if name not in depths:
                depths[name] = root_depth + i
    return depths


def _compute_slot_usage(classes: dict[str, Any]) -> dict[str, int]:
    """Return count of classes that reference each slot name in their .slots list."""
    slot_usage: dict[str, int] = {}
    for cls_node in classes.values():
        for slot_name in getattr(cls_node, "slots", None) or []:
            slot_usage[slot_name] = slot_usage.get(slot_name, 0) + 1
    return slot_usage


def extract_structural_features_linkml(
    schema: SchemaDefinition,
) -> dict[str, list[float]]:
    """Return structural feature vectors for each class and slot in a LinkML SchemaDefinition.

    Returns a dict mapping node_id -> [f0, f1, f2, f3, f4] where:
      f0: is_class (1.0 if class, 0.0 if slot)
      f1: hierarchy_depth_normalized (depth in is_a chain, normalized by max depth)
      f2: is_required (1.0 if slot required=True, else 0.0)
      f3: is_multivalued (1.0 if slot multivalued=True, else 0.0)
      f4: slot_usage_count_normalized (for slots: count of classes whose .slots list
          includes this slot name, divided by max(1, total_class_count))

    node_id format: "{schema_name}:{node_name}"
    All feature values are in [0.0, 1.0].
    """
    schema_name: str = schema.name or "schema"  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    classes: dict[str, Any] = cast("dict[str, Any]", schema.classes)  # pyright: ignore[reportUnknownMemberType]
    slots: dict[str, Any] = cast("dict[str, Any]", schema.slots)  # pyright: ignore[reportUnknownMemberType]

    depths = _compute_depths(classes | slots)
    slot_usage = _compute_slot_usage(classes)
    max_depth: int = max(depths.values(), default=0)
    total_class_count: int = len(classes)
    result: dict[str, list[float]] = {}

    for node_name in classes:
        depth_norm: float = depths.get(node_name, 0) / max_depth if max_depth > 0 else 0.0
        result[f"{schema_name}:{node_name}"] = [1.0, depth_norm, 0.0, 0.0, 0.0]

    for node_name in slots:
        node = slots[node_name]
        depth_norm = depths.get(node_name, 0) / max_depth if max_depth > 0 else 0.0
        is_required: float = 1.0 if getattr(node, "required", False) else 0.0
        is_multivalued: float = 1.0 if getattr(node, "multivalued", False) else 0.0
        usage_norm: float = slot_usage.get(node_name, 0) / max(1, total_class_count)
        result[f"{schema_name}:{node_name}"] = [
            0.0,
            depth_norm,
            is_required,
            is_multivalued,
            usage_norm,
        ]

    return result
