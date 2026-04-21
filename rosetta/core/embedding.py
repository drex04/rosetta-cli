"""Embedding utilities for the Rosetta CLI toolkit."""

from __future__ import annotations

from typing import Any, cast

from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]
from linkml_runtime.utils.schemaview import SchemaView  # type: ignore[import-untyped]


def _e5_passage_prefix(model_name: str) -> str:
    """Return the passage prefix required by E5 models, empty string otherwise.

    E5 models (e.g. intfloat/multilingual-e5-*) require all indexed texts to be
    prefixed with ``"passage: "`` and query texts with ``"query: "``.  Other models
    (LaBSE, NB-BERT, …) do not use prefixes.
    """
    low = model_name.lower()
    if "e5" in low and "e5se" not in low:  # exclude unrelated models with 'e5' in name
        return "passage: "
    return ""


def _label_for(name: str, node: Any) -> str:
    """Return the human-readable label for a schema node (title or titlecased name)."""
    return (node.title if node is not None else None) or name.replace("_", " ").title()


def _ancestor_labels(
    node_name: str, view: Any, classes: dict[str, Any], slots: dict[str, Any]
) -> list[str]:
    try:
        ancs: list[str] = [str(a) for a in view.class_ancestors(node_name)[1:]]  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType,reportUnknownArgumentType]
    except Exception:  # noqa: BLE001
        return []
    return [_label_for(anc, classes.get(anc) or slots.get(anc)) for anc in ancs]


def _parent_label(node: Any, classes: dict[str, Any], slots: dict[str, Any]) -> str | None:
    parent: str | None = getattr(node, "is_a", None)
    if not parent:
        return None
    return _label_for(parent, classes.get(parent) or slots.get(parent))


def _child_labels(node_name: str, classes: dict[str, Any]) -> list[str]:
    return [
        n.replace("_", " ").title()
        for n, c in classes.items()
        if getattr(c, "is_a", None) == node_name
    ]


def _node_text_parts(
    node_name: str,
    node: Any,
    classes: dict[str, Any],
    slots: dict[str, Any],
    view: Any,
    *,
    include_definitions: bool,
    include_parents: bool,
    include_ancestors: bool,
    include_children: bool,
) -> list[str]:
    """Build the text parts list for a single schema node."""
    parts: list[str] = [_label_for(node_name, node)]

    if include_definitions and node.description:
        parts.append(node.description)

    if include_ancestors and view is not None:
        parts.extend(_ancestor_labels(node_name, view, classes, slots))
    elif include_parents:
        parent_label = _parent_label(node, classes, slots)
        if parent_label:
            parts.append(parent_label)

    if include_children:
        parts.extend(_child_labels(node_name, classes))

    return parts


def extract_text_inputs_linkml(
    schema: SchemaDefinition,
    *,
    include_definitions: bool = False,
    include_parents: bool = False,
    include_ancestors: bool = False,
    include_children: bool = False,
) -> list[tuple[str, str, str]]:
    """Return (node_id, label, text) triples for each class and slot in a LinkML SchemaDefinition.

    node_id format: "{schema.name}:{node_name}"
    label: human-readable title (used as the base text and stored in embeddings for display)
    text: label + optional definition, parents/ancestors, children — joined with ". "
    --include-ancestors supersedes --include-parents (ancestors is a strict superset).
    """
    schema_name: str = schema.name or "schema"  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    need_view = include_parents or include_ancestors or include_children
    view = SchemaView(schema) if need_view else None

    classes: dict[str, Any] = cast("dict[str, Any]", schema.classes)  # pyright: ignore[reportUnknownMemberType]
    slots: dict[str, Any] = cast("dict[str, Any]", schema.slots)  # pyright: ignore[reportUnknownMemberType]

    results: list[tuple[str, str, str]] = []
    for node_name, node in (classes | slots).items():
        parts = _node_text_parts(
            node_name,
            node,
            classes,
            slots,
            view,
            include_definitions=include_definitions,
            include_parents=include_parents,
            include_ancestors=include_ancestors,
            include_children=include_children,
        )
        results.append((f"{schema_name}:{node_name}", parts[0], ". ".join(parts)))

    return results


class EmbeddingModel:
    """Thin wrapper around a SentenceTransformer model."""

    model_name: str
    _passage_prefix: str
    _query_prefix: str

    def __init__(self, model_name: str = "intfloat/e5-large-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model: SentenceTransformer = SentenceTransformer(model_name)
        self._passage_prefix = _e5_passage_prefix(model_name)
        self._query_prefix = "query: " if self._passage_prefix else ""

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode passage texts; return as list of Python float lists (JSON-serializable).

        For E5 models the required ``"passage: "`` prefix is applied automatically.
        """
        if self._passage_prefix:
            texts = [self._passage_prefix + t for t in texts]
        vectors = self._model.encode(texts)  # numpy array shape (n, dim)
        return [v.tolist() for v in vectors]

    def encode_query(self, texts: list[str]) -> list[list[float]]:
        """Encode query texts (used at retrieval time, not indexing).

        For E5 models applies ``"query: "`` prefix; for all others identical to
        :meth:`encode`.
        """
        if self._query_prefix:
            texts = [self._query_prefix + t for t in texts]
        vectors = self._model.encode(texts)
        return [v.tolist() for v in vectors]
