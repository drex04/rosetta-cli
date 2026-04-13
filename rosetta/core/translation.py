from __future__ import annotations

import deepl
from rdflib import RDF, RDFS, Graph, Literal

from rosetta.core.rdf_utils import ROSE_NS, bind_namespaces


def translate_labels(
    g: Graph,
    source_lang: str,
    api_key: str,
) -> Graph:
    """Translate all rose:Field rdfs:label values to English.

    When source_lang starts with 'EN' (case-insensitive), returns *g* unchanged.
    Covers EN, EN-US, EN-GB, en, etc. — no API call for any English variant.
    Otherwise calls DeepL, replaces rdfs:label with the English translation,
    and adds rose:originalLabel preserving the original text.
    """
    if source_lang.upper().startswith("EN"):
        return g

    # Collect (field_node, label_literal) for all rose:Field nodes
    field_labels: list[tuple[object, Literal]] = []
    for field_node in g.subjects(RDF.type, ROSE_NS.Field):
        for label in g.objects(field_node, RDFS.label):  # pyright: ignore[reportArgumentType]
            if isinstance(label, Literal):
                field_labels.append((field_node, label))

    if not field_labels:
        return g

    # Deduplicate
    unique_texts = list(dict.fromkeys(str(lbl) for _, lbl in field_labels))

    translator = deepl.Translator(api_key)
    sl = None if source_lang.lower() == "auto" else source_lang.upper()
    results = translator.translate_text(unique_texts, target_lang="EN-US", source_lang=sl)
    assert isinstance(
        results, list
    )  # DeepL returns list when input is list; narrows for basedpyright
    if len(results) != len(unique_texts):
        raise ValueError(
            f"DeepL returned {len(results)} results for {len(unique_texts)} unique labels; "
            "aborting to prevent silent label loss."
        )
    translation_map = {orig: res.text for orig, res in zip(unique_texts, results)}

    for field_node, orig_label in field_labels:
        orig_text = str(orig_label)
        eng_text = translation_map.get(orig_text, orig_text)
        g.remove((field_node, RDFS.label, orig_label))  # pyright: ignore[reportArgumentType]
        g.add((field_node, RDFS.label, Literal(eng_text)))  # pyright: ignore[reportArgumentType]
        g.add((field_node, ROSE_NS.originalLabel, Literal(orig_text)))  # pyright: ignore[reportArgumentType]

    bind_namespaces(g)
    return g
