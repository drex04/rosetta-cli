"""Normalise any supported schema format to a LinkML SchemaDefinition."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import pyparsing as _pp  # type: ignore[import-untyped]
import yaml as _yaml
from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]


def _hoist_nested_objects(schema: dict[str, Any]) -> dict[str, Any]:
    """Hoist inline nested ``type: object`` schemas into ``$defs``.

    ``JsonSchemaImportEngine`` cannot translate inline nested objects; it
    expects either primitive types or ``$ref`` pointers into ``$defs``.
    This pre-processing step lifts every nested object (at any depth) into
    a named definition and replaces the inline schema with a ``$ref``.
    """
    defs: dict[str, Any] = {}

    def _title(name: str) -> str:
        return "".join(w.capitalize() for w in re.split(r"[_\-\s]+", name))

    def _unique(base: str) -> str:
        name = _title(base)
        counter = 1
        while name in defs:
            name = f"{_title(base)}{counter}"
            counter += 1
        return name

    def _process(node: Any, hint: str, is_root: bool = False) -> Any:
        if not isinstance(node, dict):
            return node
        node = dict(node)
        if "properties" in node:
            node["properties"] = {k: _process(v, k) for k, v in node["properties"].items()}
        if "items" in node:
            node["items"] = _process(node["items"], hint + "Item")
        if not is_root and node.get("type") == "object" and "properties" in node:
            def_name = _unique(hint)
            defs[def_name] = node
            return {"$ref": f"#/$defs/{def_name}"}
        return node

    result = _process(schema, "", is_root=True)
    if defs:
        existing: dict[str, Any] = result.get("$defs", {})
        existing.update(defs)
        result["$defs"] = existing
    return result


def _detect_format(input_path: Path) -> str:
    """Infer schema format from file extension.  Raises ValueError if unrecognised."""
    ext = input_path.suffix.lower()
    match ext:
        case ".json":
            return "json-schema"
        case ".xsd":
            return "xsd"
        case ".csv":
            return "csv"
        case ".tsv":
            return "tsv"
        case ".ttl" | ".owl" | ".rdf":
            return "rdfs"
        case ".yaml" | ".yml":
            content = input_path.read_text(encoding="utf-8", errors="replace")[:512]
            if "openapi:" in content:
                return "openapi"
    _fmts = "json-schema,openapi,xsd,csv,tsv,json-sample,rdfs"
    raise ValueError(
        f"Cannot infer format from extension {input_path.suffix!r}. Use --format {{{_fmts}}}."
    )


def _import_with_json_tempfile(data: dict[str, Any], name: str) -> SchemaDefinition:
    """Dump *data* to a temp JSON file, convert via JsonSchemaImportEngine, clean up."""
    from schema_automator.importers.jsonschema_import_engine import (  # type: ignore[import-untyped]
        JsonSchemaImportEngine,
    )

    tmp_path_str: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as tmp:
            json.dump(data, tmp)
            tmp_path_str = tmp.name
        return JsonSchemaImportEngine().convert(tmp_path_str, name=name)  # type: ignore[no-any-return]
    finally:
        if tmp_path_str and Path(tmp_path_str).exists():
            Path(tmp_path_str).unlink()


_UTF8_BOM = b"\xef\xbb\xbf"


def _strip_bom_if_present(input_path: Path) -> Path:
    """Return *input_path* unchanged when no UTF-8 BOM is present; otherwise
    write a BOM-stripped copy to a tempfile and return that path.

    ``schema-automator.CsvDataGeneralizer`` reads the file with a default
    encoding that does not strip the BOM, which leaves ``\\ufeff`` embedded
    in the first column header. Pre-stripping keeps the generated slot names
    clean without requiring a dependency change.
    """
    with input_path.open("rb") as fh:
        prefix = fh.read(len(_UTF8_BOM))
    if prefix != _UTF8_BOM:
        return input_path

    fd, tmp = tempfile.mkstemp(suffix=input_path.suffix, prefix="rosetta_nobom_")
    tmp_path = Path(tmp)
    try:
        with input_path.open("rb") as src, tmp_path.open("wb") as dst:
            src.read(len(_UTF8_BOM))  # skip BOM
            dst.write(src.read())
    finally:
        os.close(fd)
    return tmp_path


def _import_tabular(input_path: Path, name: str, *, separator: str) -> SchemaDefinition:
    """Run CsvDataGeneralizer with BOM-stripped input; clean up any tempfile."""
    from schema_automator.generalizers.csv_data_generalizer import (  # type: ignore[import-untyped]
        CsvDataGeneralizer,
    )

    resolved = _strip_bom_if_present(input_path)
    try:
        return CsvDataGeneralizer(column_separator=separator).convert(  # type: ignore[no-any-return]
            str(resolved), schema_name=name
        )
    finally:
        if resolved is not input_path:
            resolved.unlink(missing_ok=True)


def _dispatch_import(fmt: str, input_path: Path, name: str) -> SchemaDefinition:
    """Run the appropriate schema-automator importer for *fmt*."""
    match fmt:
        case "json-schema":
            from schema_automator.importers.jsonschema_import_engine import (  # type: ignore[import-untyped]
                JsonSchemaImportEngine,
            )

            return JsonSchemaImportEngine().convert(str(input_path), name=name)  # type: ignore[no-any-return]

        case "openapi":
            import yaml as _yaml
            from schema_automator.importers.jsonschema_import_engine import (  # type: ignore[import-untyped]
                json_schema_from_open_api,
            )

            raw: dict[str, object] = _yaml.safe_load(
                input_path.read_text(encoding="utf-8", errors="replace")
            )
            return _import_with_json_tempfile(json_schema_from_open_api(raw), name)

        case "xsd":
            from schema_automator.importers.xsd_import_engine import (  # type: ignore[import-untyped]
                XsdImportEngine,
            )

            return XsdImportEngine().convert(str(input_path))  # type: ignore[no-any-return]

        case "csv":
            return _import_tabular(input_path, name, separator=",")

        case "tsv":
            return _import_tabular(input_path, name, separator="\t")

        case "json-sample":
            from genson import SchemaBuilder  # type: ignore[import-untyped]

            data = json.loads(input_path.read_text(encoding="utf-8"))
            builder = SchemaBuilder()
            if isinstance(data, list):
                for item in data:
                    builder.add_object(item)
            else:
                builder.add_object(data)
            return _import_with_json_tempfile(_hoist_nested_objects(builder.to_schema()), name)

        case "rdfs":
            from schema_automator.importers.rdfs_import_engine import (  # type: ignore[import-untyped]
                RdfsImportEngine,
            )

            return RdfsImportEngine().convert(str(input_path), format="turtle")  # type: ignore[no-any-return]

        case _:
            _supported = "json-schema, openapi, xsd, csv, tsv, json-sample, rdfs"
            raise ValueError(f"Unsupported format {fmt!r}. Supported: {_supported}.")


def check_prefix_collision(output_path: Path, schema_def: SchemaDefinition) -> None:
    """Error if any sibling *.linkml.yaml in output_path.parent has the same
    default_prefix or id as schema_def.

    Raises ValueError (caught at CLI layer, exits 1).
    """
    parent = output_path.parent
    if not parent.is_dir():
        return
    new_prefix = schema_def.default_prefix
    new_id = str(schema_def.id)
    for sibling in parent.glob("*.linkml.yaml"):
        if sibling.resolve() == output_path.resolve():
            continue
        try:
            data = _yaml.safe_load(sibling.read_text(encoding="utf-8"))
        except (OSError, _yaml.YAMLError) as exc:
            print(
                f"WARNING: prefix-collision check could not read {sibling}: {exc}",
                file=sys.stderr,
            )
            continue
        if not isinstance(data, dict):
            continue
        if new_prefix and data.get("default_prefix") == new_prefix:
            raise ValueError(
                f"default_prefix {new_prefix!r} already used by {sibling}. "
                "Choose a unique --schema-name."
            )
        if new_id and str(data.get("id", "")) == new_id:
            raise ValueError(
                f"id {new_id!r} already used by {sibling}. Choose a unique --schema-name."
            )


def _stamp_source_format(schema_def: SchemaDefinition, fmt: str) -> None:
    """Set ``annotations.rosetta_source_format`` on the LinkML schema.

    ``fmt`` is the normalised CLI ``--format`` value mapped to the downstream
    domain: json|csv|xml. Unknown formats (rdfs) are not stamped.
    """
    domain_fmt: str | None = {
        "json": "json",
        "json-sample": "json",
        "json-schema": "json",
        "openapi": "json",
        "csv": "csv",
        "tsv": "csv",
        "xml": "xml",
        "xsd": "xml",
        "rdfs": None,
    }.get(fmt)
    if domain_fmt is None:
        return
    existing: dict[str, Any] = getattr(schema_def, "annotations", None) or {}
    existing["rosetta_source_format"] = domain_fmt
    schema_def.annotations = existing  # pyright: ignore[reportAttributeAccessIssue]


def _stamp_slot_paths(schema_def: SchemaDefinition, fmt: str) -> None:
    """For every slot, attach the format-specific path hint annotation consumed by 16-02."""
    annotation_key: str | None = {
        "json": "rosetta_jsonpath",
        "json-sample": "rosetta_jsonpath",
        "json-schema": "rosetta_jsonpath",
        "openapi": "rosetta_jsonpath",
        "csv": "rosetta_csv_column",
        "tsv": "rosetta_csv_column",
        "xml": "rosetta_xpath",
        "xsd": "rosetta_xpath",
    }.get(fmt)
    if annotation_key is None:
        return
    slots: dict[str, Any] = getattr(schema_def, "slots", None) or {}
    for slot_name, slot in slots.items():
        annotations: dict[str, Any] = getattr(slot, "annotations", None) or {}
        if annotation_key == "rosetta_csv_column":
            annotations[annotation_key] = slot_name
        elif annotation_key == "rosetta_jsonpath":
            annotations[annotation_key] = f"$.{slot_name}"
        elif annotation_key == "rosetta_xpath":
            annotations[annotation_key] = f"./{slot_name}"
        slot.annotations = annotations  # pyright: ignore[reportAttributeAccessIssue]


def normalize_schema(
    input_path: Path,
    fmt: str | None = None,
    schema_name: str | None = None,
) -> SchemaDefinition:
    """Normalise any supported schema format to a LinkML SchemaDefinition.

    Args:
        input_path: Path to the input file.
        fmt: Explicit format override.  If None, inferred from file extension.
        schema_name: Schema identifier.  Defaults to ``input_path.stem``.

    Returns:
        A ``SchemaDefinition`` populated by the appropriate schema-automator importer.

    Raises:
        ValueError: If the format cannot be inferred or is not supported.
    """
    name = schema_name or input_path.stem
    resolved_fmt = fmt if fmt is not None else _detect_format(input_path)

    # schema_automator/pydbml mutate pyparsing.ParserElement.DEFAULT_WHITE_CHARS
    # (strips '\n'), breaking rdflib's SPARQL parser in the same process.
    # Save and restore around every importer call.
    _saved_whitespace: str = _pp.ParserElement.DEFAULT_WHITE_CHARS
    schema: SchemaDefinition = _dispatch_import(resolved_fmt, input_path, name)
    _pp.ParserElement.set_default_whitespace_chars(_saved_whitespace)

    # Post-assign schema name uniformly (XsdImportEngine lacks a name param)
    if name:
        schema.name = name
    return schema
