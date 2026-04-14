"""Normalise any supported schema format to a LinkML SchemaDefinition.

NOTE: linkml package has a version incompatibility where linkml.__init__ references
Format.JSON which no longer exists in linkml_runtime.  The monkey-patch below must
run before any schema_automator importer is loaded.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pyparsing as _pp  # type: ignore[import-untyped]

# ---- Monkey-patch linkml Format enum before schema_automator is imported ----
# linkml.__init__ calls Format.JSON but linkml_runtime only exposes Format.JSONLD.
# Patch once at module load time so all subsequent imports succeed.
try:
    from linkml_runtime.linkml_model.linkml_files import (
        Format as _Format,  # type: ignore[import-untyped]
    )

    if not hasattr(_Format, "JSON"):
        _Format.JSON = _Format.JSONLD  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]
except Exception:  # pragma: no cover — only fails if linkml_runtime not installed
    pass
# -------------------------------------------------------------------------

from linkml_runtime.linkml_model import SchemaDefinition  # type: ignore[import-untyped]


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

    # --- Format detection ---
    if fmt is None:
        ext = input_path.suffix.lower()
        match ext:
            case ".json":
                fmt = "json-schema"
            case ".xsd":
                fmt = "xsd"
            case ".csv":
                fmt = "csv"
            case ".tsv":
                fmt = "tsv"
            case ".ttl" | ".owl" | ".rdf":
                fmt = "rdfs"
            case ".yaml" | ".yml":
                content = input_path.read_text(encoding="utf-8", errors="replace")[:512]
                fmt = "openapi" if "openapi:" in content else None
            case _:
                fmt = None
        if fmt is None:
            _fmts = "json-schema,openapi,xsd,csv,tsv,json-sample,rdfs"
            raise ValueError(
                f"Cannot infer format from extension {input_path.suffix!r}."
                f" Use --format {{{_fmts}}}."
            )

    # --- Importer dispatch ---
    # schema_automator/pydbml mutate pyparsing.ParserElement.DEFAULT_WHITE_CHARS
    # (strips '\n'), breaking rdflib's SPARQL parser in the same process.
    # Save and restore around every importer call.
    _saved_whitespace: str = _pp.ParserElement.DEFAULT_WHITE_CHARS
    schema: SchemaDefinition
    match fmt:
        case "json-schema":
            from schema_automator.importers.jsonschema_import_engine import (  # type: ignore[import-untyped]
                JsonSchemaImportEngine,
            )

            schema = JsonSchemaImportEngine().convert(str(input_path), name=name)

        case "openapi":
            # json_schema_from_open_api takes a parsed dict, not a file path.
            import yaml as _yaml
            from schema_automator.importers.jsonschema_import_engine import (  # type: ignore[import-untyped]
                JsonSchemaImportEngine,
                json_schema_from_open_api,
            )

            raw: dict[str, object] = _yaml.safe_load(
                input_path.read_text(encoding="utf-8", errors="replace")
            )
            js = json_schema_from_open_api(raw)
            tmp_path_str: str | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as tmp:
                    json.dump(js, tmp)
                    tmp_path_str = tmp.name
                schema = JsonSchemaImportEngine().convert(tmp_path_str, name=name)
            finally:
                if tmp_path_str and os.path.exists(tmp_path_str):
                    os.unlink(tmp_path_str)

        case "xsd":
            from schema_automator.importers.xsd_import_engine import (  # type: ignore[import-untyped]
                XsdImportEngine,
            )

            schema = XsdImportEngine().convert(str(input_path))

        case "csv":
            from schema_automator.generalizers.csv_data_generalizer import (  # type: ignore[import-untyped]
                CsvDataGeneralizer,
            )

            # schema_name is forwarded via **kwargs → convert_dicts(schema_name=)
            schema = CsvDataGeneralizer(column_separator=",").convert(
                str(input_path), schema_name=name
            )

        case "tsv":
            from schema_automator.generalizers.csv_data_generalizer import (  # type: ignore[import-untyped]
                CsvDataGeneralizer,
            )

            schema = CsvDataGeneralizer(column_separator="\t").convert(
                str(input_path), schema_name=name
            )

        case "json-sample":
            from genson import SchemaBuilder  # type: ignore[import-untyped]
            from schema_automator.importers.jsonschema_import_engine import (  # type: ignore[import-untyped]
                JsonSchemaImportEngine,
            )

            data = json.loads(input_path.read_text(encoding="utf-8"))
            builder = SchemaBuilder()
            if isinstance(data, list):
                for item in data:
                    builder.add_object(item)
            else:
                builder.add_object(data)
            inferred = builder.to_schema()
            tmp_path_str2: str | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as tmp:
                    json.dump(inferred, tmp)
                    tmp_path_str2 = tmp.name
                schema = JsonSchemaImportEngine().convert(tmp_path_str2, name=name)
            finally:
                if tmp_path_str2 and os.path.exists(tmp_path_str2):
                    os.unlink(tmp_path_str2)

        case "rdfs":
            from schema_automator.importers.rdfs_import_engine import (  # type: ignore[import-untyped]
                RdfsImportEngine,
            )

            # RdfsImportEngine.convert accepts format= kwarg (default "turtle")
            schema = RdfsImportEngine().convert(str(input_path), format="turtle")

        case _:
            _supported = "json-schema, openapi, xsd, csv, tsv, json-sample, rdfs"
            raise ValueError(f"Unsupported format {fmt!r}. Supported: {_supported}.")

    # Restore pyparsing whitespace mutated by schema_automator/pydbml imports
    _pp.ParserElement.set_default_whitespace_chars(_saved_whitespace)

    # Post-assign schema name uniformly (XsdImportEngine lacks a name param)
    if name:
        schema.name = name
    return schema
