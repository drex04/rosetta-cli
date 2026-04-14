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


def extract_text_inputs_linkml(
    schema: SchemaDefinition,
    *,
    include_definitions: bool = False,
    include_parents: bool = False,
    include_ancestors: bool = False,
    include_children: bool = False,
) -> list[tuple[str, str, str]]:
    """Return (node_id, label, text) triples for each class and slot in a LinkML SchemaDefinition.

    node_id format: "{schema.name}/{node_name}"
    label: human-readable title (used as the base text and stored in embeddings for display)
    text: label + optional definition, parents/ancestors, children — joined with ". "
    --include-ancestors supersedes --include-parents (ancestors is a strict superset).
    """
    schema_name: str = schema.name or "schema"  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    need_view = include_parents or include_ancestors or include_children
    view = SchemaView(schema) if need_view else None
    results: list[tuple[str, str]] = []

    classes: dict[str, Any] = cast("dict[str, Any]", schema.classes)  # pyright: ignore[reportUnknownMemberType]
    slots: dict[str, Any] = cast("dict[str, Any]", schema.slots)  # pyright: ignore[reportUnknownMemberType]
    all_nodes: dict[str, Any] = {**classes, **slots}

    for node_name, node in all_nodes.items():
        label: str = node.title or node_name.replace("_", " ").title()
        parts: list[str] = [label]

        if include_definitions and node.description:
            parts.append(node.description)

        if include_ancestors and view is not None:
            try:
                ancs: list[str] = [str(a) for a in view.class_ancestors(node_name)[1:]]  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType,reportUnknownArgumentType]
            except Exception:  # noqa: BLE001
                ancs = []
            for anc in ancs:
                anc_node: Any = classes.get(anc) or slots.get(anc)
                anc_label: str = (anc_node.title if anc_node else None) or anc.replace(
                    "_", " "
                ).title()
                parts.append(anc_label)
        elif include_parents:
            parent: str | None = getattr(node, "is_a", None)
            if parent:
                parent_node: Any = classes.get(parent) or slots.get(parent)
                parent_label: str = (parent_node.title if parent_node else None) or parent.replace(
                    "_", " "
                ).title()
                parts.append(parent_label)

        if include_children:
            children = [n for n, c in classes.items() if getattr(c, "is_a", None) == node_name]
            parts.extend(ch.replace("_", " ").title() for ch in children)

        results.append((f"{schema_name}/{node_name}", label, ". ".join(parts)))

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
