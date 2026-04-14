# Phase 12: Library API Research — schema-automator, linkml, sssom-py, SchemaView

**Researched:** 2026-04-14
**Domain:** Python library APIs for schema import, OWL parsing, SSSOM writing, LinkML introspection
**Confidence:** MEDIUM (web docs + source search; could not execute live installs)

---

## 1. `schema-automator` — JSON Schema Importer

### Install name

```
uv add schema-automator
```

PyPI name is `schema-automator` (NOT `linkml-schema-automator`). Latest PyPI version is **0.2.11** (Jan 2023). The GitHub `main` branch is more recent but the PyPI release is stale — pin carefully or install from git.

### Python import path

```python
from schema_automator.importers.jsonschema_import_engine import JsonSchemaImportEngine
```

### Method signature

```python
engine = JsonSchemaImportEngine()
schema: SchemaDefinition = engine.convert(
    input: str,          # file path to .json or .yaml JSON Schema file
    name: str = None,    # schema name — REQUIRED in practice (becomes schema id)
    format: str = "json" # "json" or "yaml"
)
```

- `input` is a **file path string**, not a parsed dict.
- Returns a `linkml_runtime.linkml_model.meta.SchemaDefinition` object.
- The `name` argument is optional per the signature but functionally required: without it the output schema has no `id`, which breaks downstream LinkML tools. Always pass `name`.

### OpenAPI / OAS support

YES. There is a helper function `json_schema_from_open_api` inside the same module that extracts `components.schemas` from an OpenAPI document and converts it to a plain JSON Schema dict before passing to the same import engine. Callers can do:

```python
from schema_automator.importers.jsonschema_import_engine import (
    JsonSchemaImportEngine,
    json_schema_from_open_api,
)
import json, pathlib

oas_dict = json.loads(pathlib.Path("openapi.json").read_text())
json_schema_dict = json_schema_from_open_api(oas_dict)  # extracts components.schemas
# write to tmp file or pass dict path -- the engine wants a file path, not a dict
```

Gotcha: the engine's `convert()` wants a file path, not an in-memory dict. For OpenAPI, the helper extracts the dict, but you must serialize it to a temp file or adapt the internal `loads()` path.

### Known gotchas

- **Stale PyPI release** (0.2.11, Jan 2023): If you need recent fixes, install from git: `uv add git+https://github.com/linkml/schema-automator`.
- **`$ref` resolution**: JSON Schema `$ref` is handled but complex nested `$ref` chains may produce flat class structures or be silently dropped. Verify output against source.
- **Name is not optional**: Omitting `name` causes the output `SchemaDefinition.id` to be `None`, which breaks `SchemaView` and YAML serializers.
- **Output is in-memory only**: `convert()` returns the object; it does not write files. Call `linkml.utils.schema_builder.dump_yaml(schema)` or use `linkml.generators.yamlgen.YAMLGenerator` to serialize.

---

## 2. LinkML OWL Importer

### Which library?

There are two distinct packages — do NOT confuse them:

| Package | PyPI name | Purpose |
|---------|-----------|---------|
| `schema-automator` | `schema-automator` | **OWL → LinkML** (import direction) |
| `linkml-owl` | `linkml-owl` | **LinkML → OWL** (export direction) |

For importing OWL into a `SchemaDefinition`, use `schema-automator`'s `OwlImportEngine`, not `linkml-owl`.

### Python import path

```python
from schema_automator.importers.owl_import_engine import OwlImportEngine
```

### Method signature

```python
engine = OwlImportEngine()
schema: SchemaDefinition = engine.convert(
    file: str,           # file path to OWL file
    name: str = None,    # schema name
    model_uri: str = None,
    identifier: str = None,
    **kwargs
)
```

### Critical limitation: functional syntax only

The `OwlImportEngine` uses the `funowl` library internally, which **requires OWL Functional Syntax** as input. It does NOT natively parse Turtle (`.ttl`) or RDF/XML directly.

**Workaround for Turtle input:** Convert Turtle to OWL Functional Syntax first using a tool like `robot` or `owltools`, or use `rdflib` + `funowl` manually. Alternatively, use `rdflib` to load the Turtle graph and map `owl:Class`, `rdfs:label`, etc. by hand — this may be simpler for the rosetta-cli use case than fighting the `funowl` constraint.

### OWL constructs handled

From documentation: `owl:Class`, `owl:ObjectProperty`, `owl:DatatypeProperty`, `rdfs:label`, `rdfs:subClassOf`. Complex axioms (OWL restrictions, cardinality) are not fully represented in LinkML and will be dropped.

### Risk assessment

**HIGH RISK**: If rosetta-cli ingests Turtle (`.ttl`) OWL files, `OwlImportEngine` cannot consume them directly. The Turtle → functional syntax conversion step adds significant complexity. Consider whether a hand-rolled `rdflib`-based OWL walker is simpler for this project's specific OWL constructs.

---

## 3. `sssom-py` — Programmatic MappingSet and Write Path

### Install name

```
uv add sssom
```

PyPI package is `sssom` (not `sssom-utils` — that name does not exist on PyPI). Latest: **v0.4.15** (December 2024). Actively maintained.

### Data model import

The `Mapping` and `MappingSet` classes are **LinkML-generated Python dataclasses** (not Pydantic). They live in the `sssom.datamodel` module (generated from the LinkML schema YAML at build time):

```python
from sssom.datamodel import Mapping, MappingSet
```

Note: the module may also appear as `sssom_schema.datamodel` in some older versions — check the installed package's `src/` layout if the import fails.

### Key fields on `Mapping`

All IDs are **CURIE strings**, not URIs:

```python
m = Mapping(
    subject_id="HP:0001250",            # required
    predicate_id="skos:exactMatch",     # required
    object_id="MONDO:0005027",          # required
    mapping_justification="semapv:ManualMappingCuration",  # required, CURIE
    subject_label="Seizure",            # optional
    object_label="Epilepsy",            # optional
    confidence=0.9,                     # optional, float 0.0-1.0
    comment="...",                      # optional
    # many more optional fields per the spec
)
```

**Field name:** `mapping_justification` (not `justification`, not `predicate_justification`).

**semapv URI prefix:** `https://w3id.org/semapv/vocab/` — i.e. `semapv:ManualMappingCuration` expands to `https://w3id.org/semapv/vocab/ManualMappingCuration`. Use the CURIE form in the field value; sssom-py resolves prefixes via a built-in prefix map.

Valid `mapping_justification` CURIEs (from spec):
- `semapv:ManualMappingCuration`
- `semapv:LexicalMatching`
- `semapv:SemanticSimilarityThresholdMatching`
- `semapv:LexicalSimilarityThresholdMatching`
- `semapv:LogicalReasoning`
- `semapv:MappingReview`
- `semapv:UnspecifiedMatching`

### Constructing a `MappingSet`

```python
from sssom.datamodel import Mapping, MappingSet

ms = MappingSet(
    mapping_set_id="https://example.org/my-mappings",
    license="https://creativecommons.org/publicdomain/zero/1.0/",
    mappings=[m1, m2, m3],
)
```

### Converting to `MappingSetDataFrame` and writing TSV

`write_table` operates on a `MappingSetDataFrame` (a wrapper around a pandas DataFrame + metadata), not directly on `MappingSet`. Conversion path:

```python
from sssom.util import MappingSetDataFrame
from sssom.writers import write_table

# from_sssom_dataframe is the blessed constructor:
from sssom.parsers import from_sssom_dataframe
import pandas as pd

# Option A: Build DataFrame manually from Mapping objects
rows = [
    {"subject_id": m.subject_id, "predicate_id": m.predicate_id,
     "object_id": m.object_id, "mapping_justification": m.mapping_justification,
     "confidence": m.confidence}
    for m in mappings
]
df = pd.DataFrame(rows)
msdf = MappingSetDataFrame(df=df, metadata=ms)

# Option B: parse from existing TSV
# msdf = parse_sssom_table("existing.sssom.tsv")

with open("output.sssom.tsv", "w") as fh:
    write_table(msdf, fh)
```

**`write_table` signature:**
```python
write_table(
    msdf: MappingSetDataFrame,
    file,                        # file-like object (open for writing)
    embedded_mode: bool = True,  # include metadata header lines
    serialisation: str = "tsv",
    sort: bool = False,
)
```

### Known gotcha: curie_map not propagated

Issue #573: when building `MappingSetDataFrame` programmatically, `write_table()` may ignore the `curie_map` in `msdf.metadata`, so the output TSV header may lack prefix declarations. Workaround: pass `curie_map` explicitly or use `from_sssom_dataframe()` (which handles it correctly) rather than the bare `MappingSetDataFrame()` constructor.

```python
# Safer constructor:
from sssom.parsers import from_sssom_dataframe
msdf = from_sssom_dataframe(df, prefix_map={"semapv": "https://w3id.org/semapv/vocab/"}, meta=ms)
```

---

## 4. LinkML `SchemaView` — Key Iteration APIs

### Install

`SchemaView` is in **`linkml-runtime`**, not `linkml` itself:

```
uv add linkml-runtime
```

(`linkml` depends on `linkml-runtime`, so it is transitively installed if `linkml` is already a dep.)

### Import

```python
from linkml_runtime.utils.schemaview import SchemaView
```

### Constructor

```python
sv = SchemaView("path/to/schema.yaml")
# or from a SchemaDefinition object:
sv = SchemaView(schema)  # schema: SchemaDefinition
```

### Iterating all classes

```python
# Returns dict[ClassDefinitionName, ClassDefinition]
all_classes: dict = sv.all_classes(imports=True)
for class_name, class_def in all_classes.items():
    print(class_name, class_def.description)
```

### Iterating slots of a class (with inheritance resolved)

```python
# Returns list[SlotDefinition] — includes inherited + local slots
induced_slots: list = sv.class_induced_slots(class_name="MyClass", imports=True)
for slot in induced_slots:
    print(slot.name, slot.range, slot.required, slot.description)
```

### Getting a single induced slot

```python
slot_def: SlotDefinition = sv.induced_slot(
    slot_name="my_slot",
    class_name="MyClass",   # required for inheritance resolution
    imports=True,
)
print(slot_def.range)        # str: name of target type or class
print(slot_def.required)     # bool | None
print(slot_def.description)  # str | None
print(slot_def.multivalued)  # bool | None
print(slot_def.identifier)   # bool — is this an identifier slot?
```

### Key properties on `SlotDefinition`

| Property | Type | Meaning |
|----------|------|---------|
| `range` | `str \| None` | Target type name (e.g. `"string"`, `"integer"`, or a class name) |
| `required` | `bool \| None` | Must have a value |
| `multivalued` | `bool \| None` | Can hold a list |
| `description` | `str \| None` | Human-readable docs |
| `identifier` | `bool \| None` | Is the primary key |
| `inlined` | `bool \| None` | Embedded vs. referenced |

### Getting all classes in topological order

```python
sv.all_classes(ordered_by=OrderedBy.LEXICAL)   # alphabetical
sv.all_classes(ordered_by=OrderedBy.PRESERVE)  # schema file order (default)
```

---

## 5. Open Questions / Risks

| # | Question | Risk | Recommendation |
|---|----------|------|----------------|
| 1 | Does `OwlImportEngine` handle Turtle at all, or is functional syntax truly required? | HIGH — blocks Phase 12 OWL path | Verify by attempting `engine.convert("sample.ttl")`. If it fails, use rdflib-native OWL walk instead. |
| 2 | Is `schema-automator` 0.2.11 (Jan 2023) compatible with current `linkml-runtime`? | MEDIUM — dependency conflicts possible | Run `uv add schema-automator` and check for version conflicts before planning tasks. |
| 3 | Exact `sssom.datamodel` module path — is it `sssom.datamodel` or `sssom_schema.datamodel`? | LOW — easy to grep installed package | Run `python -c "import sssom; print(sssom.__file__)"` then inspect `datamodel.py` presence. |
| 4 | `json_schema_from_open_api` — does it handle `$ref` inside `components.schemas`? | MEDIUM — rosetta-cli OAS schemas may use internal `$ref` | Test with actual OAS fixture file. |
| 5 | `write_table` curie_map bug (issue #573) — fixed in v0.4.15? | LOW — use `from_sssom_dataframe()` as workaround | Check issue status; use `from_sssom_dataframe()` by default. |

---

## Sources

- [schema-automator jsonschema_import_engine docs](https://linkml.io/schema-automator/_modules/schema_automator/importers/jsonschema_import_engine.html) — MEDIUM confidence (rendered source)
- [schema-automator owl_import_engine docs](https://linkml.io/schema-automator/_modules/schema_automator/importers/owl_import_engine.html) — MEDIUM confidence
- [schema-automator importers overview](https://linkml.io/schema-automator/packages/importers.html) — HIGH confidence (official docs)
- [schema-automator PyPI (Libraries.io)](https://libraries.io/pypi/schema-automator) — HIGH confidence (version 0.2.11, Jan 2023)
- [linkml SchemaView docs](https://linkml.io/linkml/developers/schemaview.html) — HIGH confidence (official)
- [linkml_runtime schemaview source](https://linkml.io/linkml/_modules/linkml_runtime/utils/schemaview.html) — HIGH confidence
- [sssom-py GitHub](https://github.com/mapping-commons/sssom-py) — HIGH confidence
- [sssom PyPI](https://pypi.org/project/sssom/) — HIGH confidence (v0.4.15, Dec 2024)
- [SSSOM Mapping class spec](https://mapping-commons.github.io/sssom/Mapping/) — HIGH confidence (official spec)
- [sssom.writers module docs](https://mapping-commons.github.io/sssom-py/_modules/sssom/writers.html) — MEDIUM confidence
- [sssom write_table curie_map issue #573](https://github.com/mapping-commons/sssom-py/issues/573) — HIGH confidence (known bug)
- [sssom-py SSSOM toolkit guide](https://mapping-commons.github.io/sssom/toolkit/) — HIGH confidence

---

## Follow-up: RDFS + XSD importers

**Researched:** 2026-04-14
**Source:** Raw GitHub source — `main` branch, confirmed via `api.github.com` tree listing
**Confidence:** HIGH (read actual source files, not docs)

### Install command (corrected)

```
uv add schema-automator
```

PyPI package name is `schema-automator` (NOT `linkml-schema-automator`). Confirmed via `pypi.org/pypi/schema-automator/json`. Latest PyPI version is **0.5.5** (not 0.2.11 as previously noted — the earlier research used an outdated source).

### Q1: Does an RDFS importer exist?

YES. `rdfs_import_engine.py` exists in `schema_automator/importers/` alongside a matching test file `tests/test_importers/test_rdfs_importer.py`. This is a real, tested importer — not a stub.

### Python import path

```python
from schema_automator.importers.rdfs_import_engine import RdfsImportEngine
```

### `RdfsImportEngine` class definition

```python
@dataclass
class RdfsImportEngine(ImportEngine):
    mappings: Dict[str, URIRef] = field(default_factory=dict)
    initial_metamodel_mappings: Dict[str, Union[URIRef, List[URIRef]]] = field(default_factory=dict)
    metamodel_mappings: Dict[str, List[URIRef]] = field(default_factory=lambda: defaultdict(list))
    reverse_metamodel_mappings: Dict[URIRef, List[str]] = field(default_factory=lambda: defaultdict(list))
    classdef_slots: set[str] = field(init=False)
    slotdef_slots: set[str] = field(init=False)
    seen_prefixes: set[str] = field(default_factory=set)
    prefix_counts: Counter[str] = field(default_factory=Counter)
```

### `convert()` method signature

```python
def convert(
    self,
    file: Union[str, Path, TextIO],  # file path, Path, or open file handle
    name: Optional[str] = None,
    format: Optional[str] = "turtle",  # default is "turtle" — Turtle is natively supported
    default_prefix: Optional[str] = None,
    model_uri: Optional[str] = None,
    identifier: Optional[str] = None,
    **kwargs: Any,
) -> SchemaDefinition:
```

Returns `linkml_runtime.linkml_model.SchemaDefinition`.

### Q2: Does it accept Turtle format directly?

YES. The default `format` parameter is `"turtle"`. Internally it calls `rdflib.Graph().parse(file, format=format)` — so it accepts any rdflib-supported format. For Turtle `.ttl` files, no conversion step is needed; simply call `engine.convert("my_ontology.ttl")` or `engine.convert("my_ontology.ttl", format="turtle")`.

This is the critical difference from `OwlImportEngine` (which requires OWL Functional Syntax via `funowl`). `RdfsImportEngine` is the correct engine for Turtle-serialized OWL/RDFS files.

### OWL/RDFS constructs handled

The `DEFAULT_METAMODEL_MAPPINGS` dict (defined at module level) reveals exactly which RDF terms are recognized:

```python
DEFAULT_METAMODEL_MAPPINGS: Dict[str, List[URIRef]] = {
    "description": [RDFS.comment],                          # rdfs:comment -> description
    "is_a":        [RDFS.subClassOf, SKOS.broader],         # rdfs:subClassOf -> is_a
    "domain_of":   [HTTP_SDO.domainIncludes, SDO.domainIncludes, RDFS.domain],
    "range":       [HTTP_SDO.rangeIncludes, SDO.rangeIncludes, RDFS.range],
    "exact_mappings": [OWL.sameAs, HTTP_SDO.sameAs],
    # Class metaclasses:
    ClassDefinition.__name__: [RDFS.Class, OWL.Class, SKOS.Concept],
    # Slot metaclasses:
    SlotDefinition.__name__: [
        RDF.Property,
        OWL.ObjectProperty,       # owl:ObjectProperty -> SlotDefinition
        OWL.DatatypeProperty,     # owl:DatatypeProperty -> SlotDefinition
        OWL.AnnotationProperty,
    ],
}
```

Checklist against the user's question:
- `rdfs:Class` — YES, maps to `ClassDefinition`
- `rdfs:subClassOf` — YES, maps to `is_a`
- `rdfs:label` — YES, handled via metamodel slot mapping (LinkML `name`)
- `rdfs:comment` — YES, maps to `description`
- `owl:DatatypeProperty` — YES, maps to `SlotDefinition`
- `owl:ObjectProperty` — YES, maps to `SlotDefinition`

Note: `rdfs:label` is handled through the metamodel introspection path (`sv.class_induced_slots`), not the explicit `DEFAULT_METAMODEL_MAPPINGS` dict. The engine walks all slots of `ClassDefinition` and `SlotDefinition` from the LinkML metamodel and resolves their `uri_mapping` annotations, so `rdfs:label` binds to the LinkML `name` field automatically.

### Internal pipeline (brief)

1. `g.parse(file, format=format)` — loads RDF graph with rdflib
2. `generate_rdfs_properties(g, cls_slots)` — finds all `RDF.Property`, `OWL.ObjectProperty`, `OWL.DatatypeProperty`, `OWL.AnnotationProperty` subjects; yields `SlotDefinition` objects
3. `process_rdfs_classes(g, cls_slots)` — finds all `RDFS.Class`, `OWL.Class`, `SKOS.Concept` subjects (including implicit classes from `rdfs:subClassOf` triples); yields `ClassDefinition` objects
4. Assembles into `SchemaDefinition` via `linkml.utils.schema_builder.SchemaBuilder`

### Q3: Does an XSD importer exist?

YES. `xsd_import_engine.py` exists and has a matching test `tests/test_importers/test_xsd_importer.py`.

### Python import path

```python
from schema_automator.importers.xsd_import_engine import XsdImportEngine
```

### `XsdImportEngine` class definition

```python
@dataclass
class XsdImportEngine(ImportEngine):
    sb: SchemaBuilder = field(default_factory=lambda: SchemaBuilder())
    target_ns: str | None = None
```

### `convert()` method signature

```python
def convert(self, file: str, **kwargs: Any) -> SchemaDefinition:
```

Internally: `etree.parse(file, parser)` — uses `lxml.etree`, so `file` must be a file path string (not a file handle). Parses XSD XML directly; no rdflib involvement.

The XSD engine maps `<xsd:complexType>` → `ClassDefinition`, `<xsd:element>` / `<xsd:attribute>` → `SlotDefinition`, and maps XSD primitive types (string, integer, boolean, decimal, dateTime, etc.) to LinkML built-in types via an internal `xsd_to_linkml_type()` function.

### Q4: Install command summary

| Scenario | Command |
|----------|---------|
| Latest PyPI release (0.5.5) | `uv add schema-automator` |
| Latest GitHub main (ahead of PyPI) | `uv add git+https://github.com/linkml/schema-automator` |

The PyPI name `schema-automator` (with hyphen) is correct. `linkml-schema-automator` does NOT exist on PyPI.

### Revised risk assessment for Phase 12 OWL path

**LOW RISK** (revised from HIGH). `RdfsImportEngine` accepts Turtle natively, handles all six OWL/RDFS constructs the project needs, and is backed by rdflib (already a rosetta-cli dependency). The `OwlImportEngine` (funowl / functional syntax only) is the wrong engine for `.ttl` files — use `RdfsImportEngine` instead.

### Sources (follow-up section)

- [rdfs_import_engine.py raw source](https://raw.githubusercontent.com/linkml/schema-automator/main/schema_automator/importers/rdfs_import_engine.py) — HIGH confidence (actual source)
- [xsd_import_engine.py raw source](https://raw.githubusercontent.com/linkml/schema-automator/main/schema_automator/importers/xsd_import_engine.py) — HIGH confidence (actual source)
- [schema-automator PyPI JSON API](https://pypi.org/pypi/schema-automator/json) — HIGH confidence (version 0.5.5)

---

## Follow-up: TSV/spreadsheet importer

**Researched:** 2026-04-14
**Source:** Raw GitHub source — `main` branch, `schema_automator/importers/tabular_import_engine.py`
**Confidence:** HIGH (read actual source)

### File found

`schema_automator/importers/tabular_import_engine.py` — the only tabular/tsv/csv/spreadsheet importer in the directory.

### Python import path and class name

```python
from schema_automator.importers.tabular_import_engine import TableImportEngine
```

Class: `TableImportEngine` (a `@dataclass` subclassing `ImportEngine`).

### `convert()` method signature

```python
@dataclass
class TableImportEngine(ImportEngine):
    element_type: str = None   # LinkML element type ("class", "slot", etc.)
    parent: str = None         # parent class name to attach elements to
    columns: List[str] = None  # REQUIRED — column header mapping (see below)

def convert(self, file: str) -> SchemaDefinition:
    # reads file with pd.read_csv(file, sep='\t')
    # delegates to self.import_from_dataframe(df)
```

Internally `convert()` calls `import_from_dataframe()`, which writes a temp TSV and delegates to **`schemasheets.SchemaMaker`**. Note: `convert()` returns the result of `import_from_dataframe()`, which returns `sm.create_schema([tf.name])` — a `SchemaDefinition`.

### Q3: Instance data or schema-defined-in-spreadsheet?

**Schema defined in a spreadsheet format** — NOT instance data inference.

`TableImportEngine` is a thin adapter over [schemasheets](https://github.com/linkml/schemasheets), which reads spreadsheets that **define a schema** (columns describe slot names, ranges, cardinality, etc.). It does not infer a schema by examining rows of domain data values.

### Requirements on TSV structure

The TSV must conform to the **schemasheets** format:

1. `self.columns` must be set before calling `convert()` — it is `None` by default and raises `ValueError` if unset. Each entry is a schemasheets column specifier (e.g. `"slot"`, `"range"`, `"description"`, `"required"`).
2. The engine inserts a header row at position 1 containing the `columns` list, mapping them to the TSV's actual column names.
3. If `self.parent` is set, the engine prepends a `parent` column with value `>{element_type}` on the first row and `{parent}` on all data rows — this is the schemasheets syntax for attaching slots to a class.
4. The underlying `schemasheets.SchemaMaker.create_schema()` then parses the annotated TSV per the [schemasheets spec](https://linkml.io/schemasheets/).

In short: **the TSV rows describe schema elements** (classes, slots, enums), not data records. Each row is a schema element definition with columns for name, range, description, required, etc.

### Minimal call example

```python
from schema_automator.importers.tabular_import_engine import TableImportEngine

engine = TableImportEngine(
    element_type="class",
    parent="MyClass",
    columns=["slot", "range", "description", "required"],
)
schema = engine.convert("my_schema.tsv")  # TSV must have matching columns
```

### Key dependency

Requires `schemasheets` to be installed (it is NOT bundled with `schema-automator` core — add separately if needed):

```
uv add schemasheets
```

### Source

- [tabular_import_engine.py raw source](https://raw.githubusercontent.com/linkml/schema-automator/main/schema_automator/importers/tabular_import_engine.py) — HIGH confidence (actual source)

---

## Follow-up: generalize-tsv Python API

**Researched:** 2026-04-14
**Source:** Raw GitHub source — `main` branch, `schema_automator/generalizers/csv_data_generalizer.py` and `schema_automator/cli.py`
**Confidence:** HIGH (read actual source files)

The `schemauto generalize-tsv` CLI is backed by `CsvDataGeneralizer` in `schema_automator.generalizers.csv_data_generalizer`. Import path: `from schema_automator.generalizers.csv_data_generalizer import CsvDataGeneralizer`. The class is a `@dataclass` with a `column_separator: str = "\t"` field (default tab), meaning it handles **plain CSV too** — just pass `column_separator=","` at construction time; the CLI exposes this as `--column-separator`. There are three entry-point methods: (1) `convert(file: str, **kwargs) -> SchemaDefinition` — accepts a file-path string, opens the file itself using `csv.DictReader` with `self.column_separator`, and returns a `linkml_runtime.linkml_model.SchemaDefinition`; (2) `convert_from_dataframe(df: pd.DataFrame, **kwargs) -> SchemaDefinition` — accepts a pandas DataFrame directly and delegates to `convert_dicts(df.to_dict("records"), ...)`; (3) `convert_multiple(files: List[str], **kwargs) -> SchemaDefinition` — multi-file variant that merges one class per file into a single schema (used by `schemauto generalize-tsvs`). The `schema_name` parameter (default `"example"`) is set on the dataclass instance at construction, not passed to `convert()` — but `convert_dicts()` accepts `schema_name` and `class_name` as keyword args that flow through `**kwargs`. Minimal usage:

```python
from schema_automator.generalizers.csv_data_generalizer import CsvDataGeneralizer
from linkml_runtime.linkml_model import SchemaDefinition

gen = CsvDataGeneralizer(schema_name="my_schema", column_separator="\t")
schema: SchemaDefinition = gen.convert("data.tsv")

# or from a DataFrame:
import pandas as pd
df = pd.read_csv("data.tsv", sep="\t")
schema = gen.convert_from_dataframe(df)
```

No required positional parameters beyond the file path / DataFrame — `schema_name` defaults to `"example"` if not set on the instance.
