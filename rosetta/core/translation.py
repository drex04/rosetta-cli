"""Translate class/slot titles and descriptions in a LinkML SchemaDefinition using DeepL."""

from __future__ import annotations

from typing import cast

import deepl
import deepl.exceptions
from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]


def translate_schema(
    schema: SchemaDefinition,
    source_lang: str,
    target_lang: str = "EN",
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

    # Collect all unique texts to translate in one batch
    texts_to_translate: list[str] = []
    # (kind, node_name, original_text) tuples telling us where to write back results
    targets: list[tuple[str, str, str]] = []

    for cls_name, cls in schema.classes.items():  # pyright: ignore[reportAttributeAccessIssue,reportOptionalMemberAccess]
        label: str = cls.title or str(cls_name).replace("_", " ").title()  # pyright: ignore[reportAttributeAccessIssue]
        if label not in texts_to_translate:
            texts_to_translate.append(label)
        targets.append(("class_title", str(cls_name), label))
        desc: str | None = cls.description  # pyright: ignore[reportAttributeAccessIssue]
        if desc:
            if desc not in texts_to_translate:
                texts_to_translate.append(desc)
            targets.append(("class_desc", str(cls_name), desc))

    for slot_name, slot in schema.slots.items():  # pyright: ignore[reportAttributeAccessIssue,reportOptionalMemberAccess]
        label = slot.title or str(slot_name).replace("_", " ").title()  # pyright: ignore[reportAttributeAccessIssue]
        if label not in texts_to_translate:
            texts_to_translate.append(label)
        targets.append(("slot_title", str(slot_name), label))
        sdesc: str | None = slot.description  # pyright: ignore[reportAttributeAccessIssue]
        if sdesc:
            if sdesc not in texts_to_translate:
                texts_to_translate.append(sdesc)
            targets.append(("slot_desc", str(slot_name), sdesc))

    if not texts_to_translate:
        return schema

    try:
        results = translator.translate_text(
            texts_to_translate,
            target_lang="EN-US",
            source_lang=sl,
        )
    except deepl.exceptions.AuthorizationException as exc:
        raise RuntimeError(
            f"DeepL authentication failed: {exc}. Check --deepl-key or DEEPL_API_KEY env var."
        ) from exc
    except deepl.exceptions.QuotaExceededException as exc:
        raise RuntimeError(f"DeepL quota exceeded: {exc}.") from exc
    except deepl.exceptions.DeepLException as exc:
        raise RuntimeError(f"DeepL API error: {exc}.") from exc

    # DeepL returns list when input is list; cast to narrow for zip
    results_list = cast("list[deepl.TextResult]", results)

    # Build translation map
    translation_map: dict[str, str] = {
        original: result.text
        for original, result in zip(texts_to_translate, results_list, strict=True)
    }

    # Apply translations — linkml_runtime containers are untyped, suppress attribute errors
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

    return schema
