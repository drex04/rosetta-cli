"""Translate class/slot titles and descriptions in a LinkML SchemaDefinition using DeepL."""

from __future__ import annotations

from typing import Any, cast

import deepl
import deepl.exceptions
from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]


def _collect_node_texts(
    nodes: Any,
    kind_prefix: str,
    texts: list[str],
    targets: list[tuple[str, str, str]],
) -> None:
    """Accumulate unique texts and (kind, node_name, text) targets for a nodes dict."""
    for node_name, node in nodes.items():  # pyright: ignore[reportUnknownMemberType,reportOptionalMemberAccess]
        label: str = node.title or str(node_name).replace("_", " ").title()  # pyright: ignore[reportAttributeAccessIssue]
        if label not in texts:
            texts.append(label)
        targets.append((f"{kind_prefix}_title", str(node_name), label))
        desc: str | None = node.description  # pyright: ignore[reportAttributeAccessIssue]
        if desc:
            if desc not in texts:
                texts.append(desc)
            targets.append((f"{kind_prefix}_desc", str(node_name), desc))


def _apply_translation_map(
    schema: SchemaDefinition,
    targets: list[tuple[str, str, str]],
    translation_map: dict[str, str],
) -> None:
    """Write translated strings back into the schema in-place."""
    for kind, node_name, original in targets:
        translated = translation_map.get(original, original)
        if kind == "class_title":
            cls_obj = schema.classes[node_name]  # pyright: ignore[reportAttributeAccessIssue,reportOptionalSubscript,reportCallIssue,reportArgumentType]
            if cls_obj.aliases is None:  # pyright: ignore[reportAttributeAccessIssue]
                cls_obj.aliases = []  # pyright: ignore[reportAttributeAccessIssue]
            aliases: list[str] = cast("list[str]", cls_obj.aliases)  # pyright: ignore[reportAttributeAccessIssue]
            if original not in aliases:
                aliases.insert(0, original)
            cls_obj.title = translated  # pyright: ignore[reportAttributeAccessIssue]
        elif kind == "class_desc":
            schema.classes[node_name].description = translated  # pyright: ignore[reportAttributeAccessIssue,reportOptionalSubscript,reportCallIssue,reportArgumentType]
        elif kind == "slot_title":
            slot_obj = schema.slots[node_name]  # pyright: ignore[reportAttributeAccessIssue,reportOptionalSubscript,reportCallIssue,reportArgumentType]
            if slot_obj.aliases is None:  # pyright: ignore[reportAttributeAccessIssue]
                slot_obj.aliases = []  # pyright: ignore[reportAttributeAccessIssue]
            saliases: list[str] = cast("list[str]", slot_obj.aliases)  # pyright: ignore[reportAttributeAccessIssue]
            if original not in saliases:
                saliases.insert(0, original)
            slot_obj.title = translated  # pyright: ignore[reportAttributeAccessIssue]
        elif kind == "slot_desc":
            schema.slots[node_name].description = translated  # pyright: ignore[reportAttributeAccessIssue,reportOptionalSubscript,reportCallIssue,reportArgumentType]


def translate_schema(
    schema: SchemaDefinition,
    source_lang: str,
    target_lang: str = "EN-US",
    deepl_key: str | None = None,
) -> SchemaDefinition:
    """Translate class and slot titles/descriptions to *target_lang* via DeepL.

    If source_lang starts with 'EN' (case-insensitive), return schema unchanged.
    Original non-English titles are prepended to aliases.
    """
    if source_lang.upper().startswith("EN"):
        return schema

    if not deepl_key:
        raise ValueError("DeepL API key required. Set DEEPL_API_KEY or pass --deepl-key.")

    translator = deepl.Translator(deepl_key)
    sl: str | None = source_lang if source_lang.lower() != "auto" else None

    texts_to_translate: list[str] = []
    targets: list[tuple[str, str, str]] = []
    _collect_node_texts(schema.classes, "class", texts_to_translate, targets)
    _collect_node_texts(schema.slots, "slot", texts_to_translate, targets)

    if not texts_to_translate:
        return schema

    try:
        results = translator.translate_text(
            texts_to_translate, target_lang=target_lang, source_lang=sl
        )
    except deepl.exceptions.AuthorizationException as exc:
        raise RuntimeError(
            f"DeepL authentication failed: {exc}. Check --deepl-key or DEEPL_API_KEY env var."
        ) from exc
    except deepl.exceptions.QuotaExceededException as exc:
        raise RuntimeError(f"DeepL quota exceeded: {exc}.") from exc
    except deepl.exceptions.DeepLException as exc:
        raise RuntimeError(f"DeepL API error: {exc}.") from exc

    results_list = cast("list[deepl.TextResult]", results)
    translation_map: dict[str, str] = {
        original: result.text
        for original, result in zip(texts_to_translate, results_list, strict=True)
    }
    _apply_translation_map(schema, targets, translation_map)
    return schema
