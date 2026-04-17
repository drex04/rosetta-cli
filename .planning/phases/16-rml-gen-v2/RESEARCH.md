# Phase 16: rosetta-rml-gen v2 (SSSOM → YARRRML) — Research

**Researched:** 2026-04-16
**Domain:** RML / YARRRML mapping-language generation, driven by approved SSSOM rows + LinkML source/master schemas, with JSON/CSV/XML sources and a JSON-LD output target.
**Overall confidence:** HIGH on tooling and spec mechanics (Context7-equivalent official docs + current PyPI releases verified); MEDIUM on the canonical SSSOM→YARRRML algorithm (no published prior art — we must build it); LOW on some FnML-for-unit-conversion details (spec exists but real-world examples scarce).

---

## Executive Summary

The best-in-class Python-native stack for this phase is **morph-kgc ≥ 2.10** (PyPI, released 2026-01-20, MIT) as the RML/YARRRML execution engine, together with **yatter ≥ 1.2** (PyPI, Oct 2025) as an optional YARRRML-to-RML translator. Morph-kgc **accepts YARRRML directly** as input — no yatter conversion required — and supports JSON (JSONPath), CSV/TSV, and XML (XPath) sources natively, plus RML-FNML with Python user-defined functions for unit conversion. **[verified]** The critical caveat: **morph-kgc only emits N-Triples or N-Quads**. JSON-LD output must be produced by a second step — load N-Triples into rdflib, then `g.serialize(format="json-ld", context=…)` using a context derived from the master LinkML schema. **[verified]**

For YARRRML generation itself, LinkML already ships a **`gen-yarrrml` generator** that emits YARRRML from a LinkML schema, one mapping per class, honouring `class_uri`/`slot_uri`. That generator is insufficient standalone because it knows nothing about SSSOM (it assumes identity mapping — source slots map to themselves). But it establishes a canonical *shape* for the output our builder must emit, and we can reuse its prefix/URI-resolution conventions. No published tool converts SSSOM-to-YARRRML end-to-end — this phase is greenfield work, and the algorithm is the research deliverable's core contribution (Section 4).

**Primary recommendation:** Build a Python-native `yarrrml_builder.py` that (1) loads the source LinkML schema and master LinkML schema, (2) resolves every SSSOM `subject_id`/`object_id` CURIE via the `curies` library using a prefix map merged from `rosetta.toml`, the SSSOM header `curie_map`, and both schemas' `prefixes:` blocks, (3) groups SSSOM rows by source class (derived by walking `slot_usage` → owning class), (4) emits one YARRRML mapping block per source class with JSONPath/CSV/XPath iterator based on a `--source-format` flag, (5) inserts FnML function blocks only when source and object datatypes/units differ (deferred to Plan 16-02 for unit-aware lint rules already done in Phase 15), and (6) delegates execution to morph-kgc via `morph_kgc.materialize()` (Plan 16-03). Do **not** adopt `linkml-map` as a substitute — it is an orthogonal LinkML-to-LinkML transform system, not an RDF generator; its `TransformationSpecification` docs themselves note it is "not yet fully stable."

Five hard-to-reverse design decisions the planner needs to lock before coding: (a) does 16-01 ship with FnML unit-conversion or defer to 16-02 (recommend defer); (b) how are SubjectMap row IDs chosen when the source LinkML class has no obvious identifier slot (recommend `identifier: true` slot first, else synthetic `$(__row)` for CSV / `$(__index)` for JSON arrays); (c) do we expose raw YARRRML as the stable user-facing artifact or treat YARRRML as internal and ship RML Turtle (recommend YARRRML — human-readable, reviewable in PRs); (d) where is the prefix map canonicalised — rosetta.toml, the master schema, or merged (recommend merged, with master-schema precedence); (e) `--run` mode execution — in-process via `morph_kgc.materialize()` or subprocess (recommend in-process for small graphs, `materialize()` returns a rdflib `Graph` directly which is ideal for the JSON-LD framing step).

---

## Project Constraints (from CLAUDE.md)

Extracted directives the planner MUST honour:

- **Public API surface changes update README.md** — new/renamed CLI options (`--sssom`, `--source-schema`, `--master-schema`, `--source-format`, `--base-iri`, `--run`, `--coverage-report`, `--output`), output format (YARRRML YAML, optional JSON-LD), and exit-code semantics must all be documented in the rosetta-rml-gen README section before the phase is done.
- **All tools: read files or stdin, write files or stdout** — YARRRML YAML must be stdout-composable; when `--run` mode emits JSON-LD, same rule applies.
- **Exit 0 success / exit 1 error-or-unresolved-mapping** — coverage failures (SSSOM CURIE that doesn't resolve to any schema slot) must be exit 1 unless `--force`.
- **Conventional commits** — `feat(16-01):`, `feat(16-02):`, `feat(16-03):` prefixes.
- **basedpyright strict on sources** — all new functions annotated; `rdflib.term.Node | None`/`rdflib.Graph` at function boundaries, no narrowing to `URIRef`/`Literal`.
- **Pydantic models for user-facing JSON outputs** — define `YarrrmlDocument`, `YarrrmlMapping`, `CoverageReport` in `rosetta/core/models.py` BEFORE finalizing return shapes (per CLAUDE.md: "redesigning mid-phase is costly"). Consider using `extra="forbid"` (Phase 15 lesson — silent-extra-field bug).
- **Complexity gates** — `rosetta/core/yarrrml_builder.py` must pass `radon cc -n C` (no grade C+ functions). Likely means splitting the build into small helpers (one per YARRRML section: sources, prefixes, mappings, po-list).
- **Dead code / security gates** — `vulture --min-confidence 80` and `bandit -ll` both pass; YAML loading must use `yaml.safe_load`, never `yaml.load`.
- **Stub tests in the tool's own test file** — `test_rml_gen.py` should host stubs for 16-01/16-02/16-03 rather than scattering across modules.
- **Mandatory pre-commit:** `ruff format`, `ruff check`, `basedpyright`, `pytest -m "not slow"`, `radon`, `vulture`, `bandit`, `refurb`.

Known gotchas that bite this phase specifically:
- **Pydantic silent extra-field** — if YARRRML dict fields differ from Pydantic field names, data vanishes silently unless `extra="forbid"`. Cross-check YARRRML spec key names (`sources`, `mappings`, `subjects`, `predicateobjects`, `po`) against our model fields.
- **rdflib broad types** — N-Triples→JSON-LD framing touches rdflib; use `rdflib.term.Node` not `URIRef`.
- **UNIT_STRING_TO_IRI key contract** — if we reuse unit detection from Phase 4/15 for FnML function selection, keys must match `detect_unit()` exactly.
- **LinkML SchemaDefinition access** — `cast + # pyright: ignore[reportAttributeAccessIssue]` needed on `schema.classes` / `schema.slots` (from learnings).

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REQ-V2-RMLGEN-01 | SSSOM-driven YARRRML generator that, when executed by an RML engine, transforms source data (JSON/CSV/XML) into JSON-LD conforming to the master ontology. Includes schema coverage checks against source and master LinkML schemas. | Sections 2 (YARRRML spec), 3 (morph-kgc 2.10), 4 (algorithm), 5 (JSON-LD framing), 6 (integration plan). |

---

## 1. SSSOM — CURIE resolution, class vs property, prior art

### 1.1 CURIE-to-IRI resolution in SSSOM

SSSOM mapping files carry a `curie_map:` block in the YAML/TSV header (the existing audit log already emits this — see `rosetta/core/accredit.py::SSSOM_HEADER`). **[verified]** sssom-py resolves CURIEs using a `curies.Converter` object; if none is supplied, it falls back to a Bioregistry-derived default prefix map. **[verified — sssom-py docs]**

**Canonical passing convention:**

```python
from curies import Converter
import sssom.parsers as sp

msdf = sp.parse_sssom_table("audit-log.sssom.tsv")
converter: Converter = msdf.converter          # reads curie_map block
subject_iri = converter.expand(row.subject_id) # "src:speedMps" -> full IRI
```

For rosetta-cli we should **merge three sources** of prefix information (precedence low → high):

1. Bioregistry defaults (via `curies.get_bioregistry_converter()`) — optional, LOW priority, only if we opt in.
2. `rosetta.toml [namespaces]` (already holds `rose = …`).
3. LinkML source-schema `prefixes:` block.
4. LinkML master-schema `prefixes:` block.
5. SSSOM header `curie_map:` (highest priority — it's what the mapping was authored with).

LinkML and SSSOM both use CURIE/URI prefixes natively; the `curies` library (PyPI, biopragmatics) is the common denominator. **[verified]**

### 1.2 Class vs property mappings in SSSOM

SSSOM `predicate_id` is orthogonal to the "thing type" of subject/object. Official guidance: **[verified — mapping-commons.github.io/sssom]**

| predicate_id | Meaning | Applies to |
|--------------|---------|------------|
| `skos:exactMatch` | Interchangeable with high confidence | Both classes and properties (common default) |
| `skos:closeMatch` | Similar enough for some IR uses | Both |
| `skos:broadMatch` / `narrowMatch` / `relatedMatch` | Hierarchical or related | Both |
| `owl:equivalentClass` | Both sides are OWL classes, equivalent | Classes only |
| `owl:equivalentProperty` | Both sides are OWL properties, equivalent | Properties only |
| `semapv:crossSpeciesExactMatch` | Domain-specific | Classes usually |

**Key inference for Phase 16:** `predicate_id: skos:exactMatch` does **not** tell us whether the row is class-level or slot-level. The generator must disambiguate by **schema introspection** — looking up `subject_id` in the source LinkML schema: is it a `class.name`/`class.class_uri` or a `slot.name`/`slot.slot_uri`? Same for `object_id` against the master schema. A row where both resolve to classes produces a SubjectMap type assertion (`rdf:type`); a row where both resolve to slots produces a PredicateObjectMap. A row where subject resolves to a slot but object to a class is a **malformed mapping** — lint error, exit 1. **[inferred from SSSOM + LinkML semantics]**

### 1.3 Prior art: SSSOM → RML/YARRRML

**No published, maintained tool converts SSSOM to RML or YARRRML end-to-end** as of April 2026 (thorough WebSearch + GitHub search). **[verified absence — multiple queries]**

Adjacent prior art:
- **`linkml gen-yarrrml`** (official LinkML generator) — emits YARRRML from a LinkML schema alone, no mapping input. It emits identity-like mappings (source slot → its own `slot_uri`). **[verified — linkml.io/linkml/generators/yarrrml.html]** Relevant PR: [linkml/linkml#3131](https://github.com/linkml/linkml/pull/3131) improves IRI handling for object links.
- **`OWL2YARRRML`** — generates YARRRML *templates* from an OWL ontology. Different problem (no mapping input). **[verified]**
- **`linkml-map`** (formerly linkml-transformer) — declarative LinkML-to-LinkML transform. *Does not execute against JSON/CSV/XML*; it's instance-level data transform between LinkML models. States "not yet fully stable" in its own docs. **Not a substitute.** **[verified]**
- **Monarch Initiative / OBO** — SSSOM is heavily used by OBO but primarily for ontology-to-ontology alignment, not for data-to-RDF mapping-language generation. No SSSOM-to-RML tool found in the Monarch or mapping-commons GitHub orgs.

**Implication:** The core SSSOM-to-YARRRML algorithm in Section 4 is novel work. The research deliverable flags this as a risk factor the planner should weight.

**Sources:**
- [SSSOM predicate_id reference](https://mapping-commons.github.io/sssom/predicate_id/)
- [SSSOM mapping predicates guide](https://mapping-commons.github.io/sssom/mapping-predicates/)
- [curies · PyPI](https://pypi.org/project/curies/)
- [sssom-py context module](https://mapping-commons.github.io/sssom-py/_modules/sssom/context.html)

---

## 2. RML and YARRRML essentials

### 2.1 RML spec core constructs **[verified — rml.io/specs/rml/]**

| Construct | Role |
|-----------|------|
| `rml:LogicalSource` | Data source + reference formulation + iterator |
| `rml:source` | Path/URL to the data file |
| `rml:referenceFormulation` | Language: `ql:JSONPath`, `ql:CSV`, `ql:XPath` |
| `rml:iterator` | Path to iterate records (JSON/XML; absent for CSV) |
| `rr:TriplesMap` | One mapping block; a subject + many PO maps |
| `rr:subjectMap` | Template for row IRI + `rr:class` assertion |
| `rr:template` | `"http://ex/{id}"` — interpolates fields |
| `rr:predicateObjectMap` | Predicate + ObjectMap pair |
| `rml:reference` | Field path (JSONPath for JSON, column for CSV, XPath for XML) |
| `rr:datatype` / `rr:language` | Literal typing on ObjectMap |
| `rr:parentTriplesMap` | Joins between TriplesMaps (nested objects) |

### 2.2 Reference formulations and iterators **[verified]**

| Source format | Reference formulation | Iterator example | Reference example |
|---------------|----------------------|------------------|-------------------|
| JSON | `ql:JSONPath` | `$.tracks[*]` (iterate array) | `$.name` or `name` |
| CSV/TSV | `ql:CSV` | *(none — implicit per-row)* | `column_name` |
| XML | `ql:XPath` | `//track` or `/root/track` | `./@id` or `./name/text()` |
| JSON-LD | `ql:JSONPath` | `$['@graph'][*]` | etc. |

**Pitfalls (see Section 7):** omitting `[*]` from a JSONPath array iterator is the single most common mistake — `$.tracks` returns the array itself rather than each element. **[verified — rml.io docs, yarrrml-parser issues]**

### 2.3 YARRRML top-level structure **[verified — rml.io/yarrrml/spec/]**

```yaml
prefixes:
  ex: http://example.org/
  xsd: http://www.w3.org/2001/XMLSchema#
  rose: http://rosetta.interop/ns/
  master: http://rosetta.interop/master/

sources:
  tracks_src:
    access: data.json
    referenceFormulation: jsonpath
    iterator: "$.tracks[*]"

mappings:
  track:
    sources: [tracks_src]
    subjects: ex:track/$(id)
    predicateobjects:
      - [a, master:Track]                                 # rdf:type
      - [master:name, $(name)]                            # plain literal
      - [master:airSpeed, $(speed_mps), xsd:double]       # typed literal
      - [master:homepage, $(url)~iri]                     # IRI object
```

**Canonical examples for each source format:**

**JSON** (file `tracks.json`):
```yaml
prefixes: { ex: http://example.org/, master: http://master.example/ }
sources:
  src: { access: tracks.json, referenceFormulation: jsonpath, iterator: "$.tracks[*]" }
mappings:
  trk:
    sources: [src]
    subjects: ex:track/$(id)
    po:
      - [a, master:Track]
      - [master:name, $(name)]
      - [master:speed, $(speed_mps), xsd:double]
```

**CSV** (file `tracks.csv`):
```yaml
prefixes: { ex: http://example.org/, master: http://master.example/ }
sources:
  src: { access: tracks.csv, referenceFormulation: csv }
mappings:
  trk:
    sources: [src]
    subjects: ex:track/$(id)
    po:
      - [a, master:Track]
      - [master:name, $(name)]
      - [master:speed, $(speed_mps), xsd:double]
```

**XML** (file `tracks.xml`):
```yaml
prefixes: { ex: http://example.org/, master: http://master.example/ }
sources:
  src: { access: tracks.xml, referenceFormulation: xpath, iterator: "//track" }
mappings:
  trk:
    sources: [src]
    subjects: ex:track/$(./@id)
    po:
      - [a, master:Track]
      - [master:name, $(./name)]
      - [master:speed, $(./speed_mps), xsd:double]
```

### 2.4 Object-type and datatype annotations **[verified]**

YARRRML object shorthand list syntax `[predicate, value, datatype_or_languagetag]`:

| Form | Meaning |
|------|---------|
| `[p, $(field)]` | Plain literal (xsd:string by default) |
| `[p, $(field), xsd:double]` | Typed literal |
| `[p, $(field), en~lang]` | Language-tagged literal |
| `[p, $(field)~iri]` | Object is an IRI (field value expanded as URI) |
| `[p, ex:Type, ~iri]` | Static IRI object |

For richer cases YARRRML also supports `objects:` (or `o:`) with explicit `type:` / `datatype:` / `language:` / `value:` keys — needed when the value is itself generated by a function (see 2.5).

### 2.5 FnO / FnML in YARRRML **[verified — rml.io spec; morph-kgc RML-FNML docs]**

YARRRML expresses functions with a `function:` + `parameters:` block, typically inside an `objects:` entry. Example (concatenation):

```yaml
mappings:
  person:
    sources: [src]
    subjects: ex:person/$(id)
    po:
      - p: ex:fullName
        o:
          function: grel:string_concat
          parameters:
            - [grel:p_string_sep, $(first)]
            - [grel:p_string_sep, " "]
            - [grel:p_string_sep, $(last)]
```

**Unit conversion in morph-kgc (via Python UDF)** — preferred path for rosetta-cli **[verified — Softx paper 2024 + morph-kgc RML-FNML docs]**:

1. Write a Python file with decorated functions:

```python
# file: rosetta_udfs.py
from morph_kgc.udfs import udf
@udf(fun_id="http://rosetta/udf/m_to_ft", return_type="http://www.w3.org/2001/XMLSchema#double")
def m_to_ft(value: str) -> float:
    return float(value) * 3.28084
```

2. Reference it in the morph-kgc INI config: `udfs = rosetta_udfs.py`.
3. In YARRRML:

```yaml
po:
  - p: master:altitudeFt
    o:
      function: <http://rosetta/udf/m_to_ft>
      parameters:
        - [grel:valueParameter, $(altitude_m)]
      datatype: xsd:double
```

This path is clean but adds another file to manage. **An alternative** for simple linear conversions (multiplier + offset, which is what `FnmlSuggestion` already carries from Phase 15 lint): generate the math inline using a pre-registered GREL function `grel:array_sum` + `grel:multiply` — avoids user-defined-function registration entirely, at the cost of expressiveness.

**Recommendation:** Defer unit-conversion FnML to Plan 16-02. Plan 16-01 should generate YARRRML with datatype-only coercion (e.g., `xsd:double`, `xsd:dateTime`). The Phase 15 lint system already emits `FnmlSuggestion` with multiplier/offset — Plan 16-02 reads those and emits FnML blocks only where lint flagged a unit mismatch.

### 2.6 JSON-LD output — RML engines emit N-Triples, we frame **[verified]**

morph-kgc **only supports N-Triples and N-Quads** as output formats (INI `output_format = N-TRIPLES | N-QUADS`). **[verified — morph-kgc readthedocs]** No direct JSON-LD. The pipeline for JSON-LD is two-step:

```python
import morph_kgc
import rdflib

# Step 1: materialize into rdflib.Graph directly
g: rdflib.Graph = morph_kgc.materialize(config_ini_string)

# Step 2: serialize with a JSON-LD context
context_dict = json.loads(Path("master.context.jsonld").read_text())["@context"]
jsonld_bytes = g.serialize(format="json-ld", context=context_dict, indent=2)
```

The context comes from `linkml generate jsonld-context master.linkml.yaml > master.context.jsonld` (see Section 5).

**Sources:**
- [YARRRML spec](https://rml.io/yarrrml/spec/)
- [YARRRML tutorial](https://rml.io/yarrrml/tutorial/getting-started/)
- [YARRRML spec fork (OEG)](https://oeg-dataintegration.github.io/yarrrml-spec/)
- [RML-FNML spec](https://kg-construct.github.io/rml-fnml/spec/docs/)
- [RML-FNML in Morph-KGC (SoftwareX 2024)](https://www.sciencedirect.com/science/article/pii/S2352711024000803)
- [Morph-KGC docs — output format](https://morph-kgc.readthedocs.io/en/latest/documentation/)

---

## 3. Python tooling evaluation

### 3.1 morph-kgc — RECOMMENDED

| Attribute | Value |
|-----------|-------|
| Latest version | **2.10.0** (2026-01-20) **[verified PyPI]** |
| Install | `uv add morph-kgc` |
| License | Apache-2.0 |
| Input | RML (Turtle), YARRRML (YAML), **accepts both directly** |
| Source data | JSON, CSV, TSV, XML, Excel, Parquet, Feather, ORC, Stata, SAS, SPSS, ODS, MySQL, PostgreSQL, Oracle, MSSQL, MariaDB, SQLite |
| Output | N-Triples, N-Quads (RDF + RDF-star). **No direct JSON-LD.** |
| Python API | `morph_kgc.materialize(config)` → rdflib.Graph; `materialize_set(config)` → set of triples; `materialize_oxigraph(config)` → oxigraph Store |
| FnO / FnML | Full RML-FNML support + Python UDFs via `udfs` INI parameter |
| Maintenance | Active — Jan 2026 release, Elsevier SoftwareX publication |
| Python | ≥ 3.9 |

**Known limitations:**
- Config is an INI string, not YAML or TOML — minor friction but acceptable.
- JSON-LD not a native output; requires rdflib post-processing.
- Large graphs (> memory) should use `output_dir` partitioning rather than in-process materialize.

### 3.2 yatter — OPTIONAL (only if we want to inspect RML Turtle)

| Attribute | Value |
|-----------|-------|
| Latest version | ≥ 1.2 (Oct 2025) **[verified PyPI]** |
| Install | `uv add yatter` |
| Purpose | Pure YARRRML↔RML translator (Python port of yarrrml-parser) |
| Python API | `yatter.translate(yarrrml_dict) -> rml_turtle_string` |
| Use case in Phase 16 | Optional debug output: emit both YARRRML and translated RML Turtle for user inspection. Not required for execution (morph-kgc handles YARRRML natively). |

**Recommendation:** Not a mandatory dependency for 16-01. Consider adding in 16-03 if user-facing "show me the RML this produces" is a useful feature.

### 3.3 yarrrml-parser — NOT RECOMMENDED

Node.js only; would require a `subprocess.run(["node", ...])` call or Docker. Morph-kgc native YARRRML support removes the need.

### 3.4 RMLMapper (Java) — FALLBACK ONLY

JAR-based; requires Java 11+ in the environment. Slower; batch only. Rosetta-cli is a Python project — adding a Java dependency is unjustifiable when morph-kgc is feature-complete for our needs. Reserve as a compatibility-check-only tool in CI if ever needed.

### 3.5 pyrml / pyRML — DEAD

PyPI `pyrml` last updated 2022, no RML-FNML support, minimal maintenance. **[verified]** Do not use.

### 3.6 linkml generators relevant to this phase

| Generator | Purpose | Use in Phase 16 |
|-----------|---------|-----------------|
| `gen-yarrrml` | LinkML schema → YARRRML template | Reference implementation. Read its source for prefix/URI conventions. Do NOT use as-is (it emits identity mappings, no SSSOM). |
| `gen-jsonld-context` | LinkML schema → JSON-LD `@context` | **Direct use in 16-03** for framing morph-kgc N-Triples output into JSON-LD. |
| `gen-jsonld` | LinkML schema → full JSON-LD document | Not needed for our pipeline. |

**Source links:**
- [morph-kgc GitHub](https://github.com/morph-kgc/morph-kgc) — [PyPI](https://pypi.org/project/morph-kgc/)
- [yatter GitHub (oeg-upm)](https://github.com/oeg-upm/yatter) — [PyPI](https://pypi.org/project/yatter/)
- [LinkML YARRRML generator](https://linkml.io/linkml/generators/yarrrml.html)
- [LinkML JSON-LD context generator](https://linkml.io/linkml/generators/jsonld-context.html)

---

## 4. The SSSOM + source-schema → YARRRML algorithm

This is the core of the phase and the portion with no published prior art.

### 4.1 Inputs

1. `sssom_rows: list[SSSOMRow]` — approved/curated rows (Phase 14 audit log).
2. `source_schema: linkml_runtime.SchemaDefinition` — LinkML YAML from `rosetta-ingest`.
3. `master_schema: linkml_runtime.SchemaDefinition` — LinkML YAML of the master ontology.
4. `source_file: str` — path the RML engine will read (not opened by the builder).
5. `source_format: Literal["json", "csv", "xml"]` — reference formulation.
6. `base_iri: str` — SubjectMap template base (e.g., `http://rosetta.interop/instances/`).
7. `prefix_converter: curies.Converter` — merged from `.toml`, schema prefixes, SSSOM `curie_map`.

### 4.2 Row classification

Each SSSOMRow is classified by schema lookups:

```
for row in sssom_rows:
    s_iri = converter.expand(row.subject_id)
    o_iri = converter.expand(row.object_id)

    s_kind = classify(s_iri, source_schema)   # "class" | "slot" | "unknown"
    o_kind = classify(o_iri, master_schema)   # "class" | "slot" | "unknown"

    match (s_kind, o_kind):
        case ("class", "class"):    class_mappings.append(row)          # defines rdf:type
        case ("slot", "slot"):      slot_mappings.append(row)           # defines PredicateObjectMap
        case ("slot", "class"):     # malformed — slot → class makes no sense
        case ("class", "slot"):     # malformed — class → slot makes no sense
        case (_, "unknown"):        coverage.unresolved_master.append(row)
        case ("unknown", _):        coverage.unresolved_source.append(row)
```

`classify()` walks `schema.classes[*].class_uri`, `schema.slots[*].slot_uri`, and `schema.slot_usage` to find the IRI. Use `linkml_runtime.utils.schemaview.SchemaView` — it already provides `.get_class(uri)` and `.get_slot(uri)` helpers with CURIE expansion. **[verified from LinkML docs]**

### 4.3 Grouping slots into TriplesMaps

YARRRML emits one `mappings:` block per source class. For each slot mapping we need to find its **owning source class**. LinkML slot ownership is recorded via:

1. `class.slots` list on each class, **or**
2. `class.slot_usage` dict (class-specific overrides), **or**
3. A slot's `domain` attribute (declarative).

Use `SchemaView.get_classes_by_slot(slot_name)` to find owning classes. **[verified]** If a slot is owned by multiple classes, we emit the PO entry in each class's TriplesMap.

### 4.4 SubjectMap identifier selection

For each source class, pick the identifier slot in priority order:
1. Slot with `identifier: true`.
2. Slot named `id` (case-insensitive).
3. Slot with a `unique_keys` single-column entry.
4. **Synthetic**: `$(__index)` for JSON arrays, `$(__rownum)` for CSV, `$(./@rml:rowNumber)` / generated UUID for XML. *Note: morph-kgc supports `$(__rownum)` as a virtual CSV column.*

Emit a warning in the coverage report when (4) is used (phase 16-02 deliverable).

### 4.5 One row → one `po` entry (slot case)

Given `row = (src:speedMps, skos:exactMatch, master:airSpeed, confidence=0.95, subject_datatype=xsd:double, object_datatype=xsd:double)`:

1. Resolve `subject_id` CURIE to a SlotDefinition in source schema — note its `name` (e.g., `speedMps`), this becomes the `rml:reference`.
2. Resolve `object_id` CURIE to a SlotDefinition in master schema — note its `slot_uri` (full IRI), this becomes the `predicate`.
3. Pick datatype: prefer `row.object_datatype` (the target's datatype); fall back to `row.subject_datatype`; fall back to `xsd:string`.
4. Reference-field expression depends on source format:
   - JSON: `$(speedMps)` (leading `$` is YARRRML syntax, not JSONPath — YARRRML prefixes it with the iterator automatically)
   - CSV: `$(speedMps)` (column name)
   - XML: `$(./speedMps)` or `$(./speedMps/text())`
5. If source and object datatypes differ AND Phase 15 lint has an `fnml_suggestion` for this row: emit FnML block (Plan 16-02).
6. Otherwise emit shorthand: `[<predicate_iri>, $(<reference>), <datatype>]`.

### 4.6 `mapping_justification` usage

| Justification | How RML-gen treats it |
|---------------|----------------------|
| `semapv:ManualMappingCuration` (MMC) | Pending — **skip** (not yet approved). |
| `semapv:HumanCuration` (HC) | **Approved** — include in generation. |
| `semapv:LexicalMatching`, `semapv:CompositeMatching` | Unaccredited suggestions — **skip**. |
| `semapv:UnspecifiedMatching` | Skip. |

Phase 14 ensures the input is already the approved subset — but the builder should defensively filter to `HumanCuration` only (exit 1 with a message if no HC rows are present, unless `--include-manual` is passed). **[inferred from Phase 14 state machine in `accredit.py`]**

### 4.7 Coverage computation

Three coverage dimensions the report carries:

| Metric | Count |
|--------|-------|
| `source_slots_mapped` | Unique source slots referenced by any HC SSSOM row |
| `source_slots_total` | All slots in source schema |
| `source_slots_unmapped` | `total - mapped` |
| `master_slots_mapped` | Unique master slots referenced |
| `rows_unresolved_source` | SSSOM rows whose subject_id doesn't resolve |
| `rows_unresolved_master` | SSSOM rows whose object_id doesn't resolve |

**Exit code**: 1 if `rows_unresolved_*` > 0 unless `--force`; 1 if `source_slots_mapped == 0`; 0 otherwise. Coverage goes to stderr by default, or to `--coverage-report <file>` as JSON.

### 4.8 Source-format heuristics

Phase 11 rewrote `rosetta-ingest` to use schema-automator, which **does not preserve the original file's format** in the output LinkML YAML in a machine-readable way (the filename stem is kept via `--schema-name` but format is lost). **[verified by reading `rosetta/cli/ingest.py`]**

**Recommendation:** Require `--source-format` explicitly in Plan 16-01. In Plan 16-02, add optional auto-detection from the source-data file extension (`.json`, `.csv`, `.xml`), with the explicit flag overriding.

---

## 5. JSON-LD output framing

### 5.1 Generate `@context` from the master LinkML schema

```bash
linkml generate jsonld-context store/master-ontology/master.linkml.yaml \
  --useuris \
  > store/master-ontology/master.context.jsonld
```

The `--useuris` flag forces slot/class URIs over default model URIs — essential when slots have explicit `slot_uri`. **[verified — linkml.io/linkml/generators/jsonld-context.html]** The output is a `{ "@context": { prefix: uri, slotname: {...} } }` object.

**Caveat [verified gh issue #97]:** If the master schema sets a `default_prefix:` that has an underscore suffix, gen-jsonld-context can omit entries. Our master schema uses `master:` as default — should be safe, but plan a test.

### 5.2 Pipeline

```python
from pathlib import Path
import json
import morph_kgc
import rdflib

config = f"""
[DataSource1]
mappings: {yarrrml_path}
file_path: {source_data_path}

[CONFIGURATION]
output_format: N-TRIPLES
"""

g: rdflib.Graph = morph_kgc.materialize(config)

ctx_doc = json.loads(Path("master.context.jsonld").read_text())
jsonld_bytes: bytes = g.serialize(
    format="json-ld",
    context=ctx_doc["@context"],
    indent=2,
    auto_compact=True,
)
```

`rdflib.Graph.serialize(format="json-ld", context=..., auto_compact=True)` handles the compaction step — equivalent to `jsonld.compact(expanded, context)`. **[verified — rdflib docs]**

### 5.3 Framing vs compaction

Our output is a flat set of typed RDF instances. **Compaction** (via `@context`) is enough for 16-03; full **framing** (via `@context` + `@type` filter) would produce a nested tree and would need a separate `master.frame.jsonld` document. Recommend compaction-only for MVP; framing deferred unless user requests.

---

## 6. Integration with existing toolchain

### 6.1 To DELETE

| File | Reason |
|------|--------|
| `rosetta/core/rml_builder.py` | Replaced by `yarrrml_builder.py` |
| `rosetta/core/models.py::MappingDecision` | No remaining users after CLI rewrite (only 5 refs, all within rml-gen scope — verified via grep) |
| `rosetta/tests/test_rml_gen.py` (existing tests) | New test file replaces; keep stub convention per CLAUDE.md |

### 6.2 To ADD

| File | Purpose |
|------|---------|
| `rosetta/core/yarrrml_builder.py` | Build YARRRML dict from SSSOM + LinkML schemas |
| `rosetta/core/schema_coverage.py` | Coverage analysis + CURIE resolution (or inline in builder) |
| `rosetta/core/rml_runner.py` | Morph-KGC invocation + JSON-LD framing (16-03) |
| `rosetta/core/models.py::YarrrmlMapping`, `CoverageReport`, `RmlGenReport` | Pydantic models for structured output |
| `rosetta/tests/fixtures/master.linkml.yaml` | LinkML form of master ontology (currently only Turtle) |
| `rosetta/tests/fixtures/approved.sssom.tsv` | Small SSSOM fixture with HC-justified rows |

### 6.3 CLI surface (new)

```
rosetta-rml-gen \
  --sssom         <path>     # (required) approved SSSOM TSV
  --source-schema <path>     # (required) source LinkML YAML
  --master-schema <path>     # (required) master LinkML YAML
  --source-format json|csv|xml  # (required in 16-01; auto in 16-02)
  --source-data   <path>     # (required with --run) data file to transform
  --output        <path>     # YARRRML out (default stdout)
  --base-iri      <uri>      # SubjectMap base (default rose:instances/)
  --run                      # one-shot generate + execute (16-03)
  --coverage-report <path>   # write coverage JSON (default: stderr summary)
  --force                    # continue on unresolved mappings (exit 0)
  --config        rosetta.toml
```

Justification per option:
- `--sssom`, `--source-schema`, `--master-schema`: three-way inputs demanded by the phase goal (SSSOM + two schemas).
- `--source-format`: explicit in 16-01 (ingest loses format metadata).
- `--source-data`: only meaningful with `--run`; Click conditional-require pattern.
- `--output`: Unix-composable; stdout default aligns with CLAUDE.md convention.
- `--base-iri`: configurable per deployment; rosetta.toml default.
- `--run`: defaults to dry-generate mode, consistent with other rosetta tools (suggest dry-outputs; accredit is explicit).
- `--coverage-report`: separate file avoids polluting YARRRML output; stderr summary is always on.
- `--force`: policy escape hatch for coverage failures.

### 6.4 `rosetta.toml` additions

```toml
[rml_gen]
base_iri = "http://rosetta.interop/instances/"
udfs_path = "store/udfs.py"        # optional, for FnML (Plan 16-02)
default_source_format = "json"     # fallback when not inferrable
frame_output = false               # Plan 16-03: use @context only, not @frame
```

### 6.5 Wave-0 test infrastructure (Nyquist validation)

| Behavior | Test type | Command |
|----------|-----------|---------|
| REQ-V2-RMLGEN-01: SSSOM row → `po:` entry shape | unit | `uv run pytest rosetta/tests/test_rml_gen.py::test_po_shape -x` |
| CURIE resolution precedence merged correctly | unit | `...::test_curie_precedence -x` |
| JSONPath iterator generation | unit | `...::test_json_iterator` |
| CSV iterator absence | unit | `...::test_csv_no_iterator` |
| XML XPath iterator | unit | `...::test_xml_iterator` |
| Unresolved subject_id exits 1 | integration | `...::test_unresolved_exits_1` |
| End-to-end NOR CSV → JSON-LD | smoke (slow) | `uv run pytest -m slow ...::test_e2e_nor_csv` |
| morph-kgc materialization returns rdflib.Graph | integration | `...::test_morph_kgc_returns_graph` |

Wave-0 gaps:
- [ ] `rosetta/tests/fixtures/master.linkml.yaml` — master ontology in LinkML form
- [ ] `rosetta/tests/fixtures/approved.sssom.tsv` — 5-row fixture (HC only, one class + slots)
- [ ] `rosetta/tests/fixtures/source.linkml.yaml` — minimal source schema
- [ ] `rosetta/tests/fixtures/source_tracks.json` + `.csv` + `.xml` — three-format fixtures

---

## 7. Prior art and pitfalls

### 7.1 YARRRML authoring pitfalls **[verified — rml.io + gh issues]**

1. **Missing `[*]` in JSONPath iterator** — `$.tracks` yields the array, not elements. Always use `[*]`.
2. **Leading dot on inner references** — writing `.creator.id` instead of `creator.id` in non-iterator positions.
3. **Quoting inconsistency** — iterator is often quoted (`iterator: "$.tracks[*]"`) while reference-values inside `$(...)` are not. Standardize in our builder.
4. **XML namespaces in subject templates** — `s: ex:track/$(./ns:id)` can produce incorrect RML output. Workaround: prefix declaration in the source block.
5. **Function + predicate interaction** — known parser bug: `p: <fn-call>, o: …` crashes yarrrml-parser; morph-kgc handles this via `po` block with full `p`/`o` keys.
6. **Named blank-node subjects** — not supported; subjects must be IRIs. Not an issue for us (we always emit IRIs).
7. **Silent predicate drop** — object type `iri` is discarded after the first source in multi-source mappings (yarrrml-parser gh#137). Not an issue for us — one source per mapping.

### 7.2 LinkML-specific pitfalls (from memory & research)

- **`schema.classes` / `schema.slots` attribute access** — use `SchemaView` helpers; direct attribute access triggers pyright errors needing `# pyright: ignore[reportAttributeAccessIssue]`.
- **`schema.name` vs `"schema"` fallback** for `default_prefix`.
- **`class_uri` / `slot_uri` verbatim** — LinkML emits these literally; full IRIs work, CURIEs get expanded via prefixes block.

### 7.3 Morph-KGC pitfalls

- **INI config only** — no YAML/JSON config. Our `rml_runner.py` must construct INI strings. Small friction.
- **Large data** — in-process `materialize()` is memory-bound. For rosetta's synthetic test fixtures (tens-of-rows), fine; production-scale would use `output_dir` partitioning.
- **UDF function IRIs** — must be full IRIs in YARRRML (`<http://…>`), not CURIEs. Mixing up will silently produce a `grel:undefinedFunction` error.

### 7.4 SSSOM pitfalls (from project memory)

- **9-column SSSOM** — project standard from Phase 14; `subject_datatype` and `object_datatype` are columns 10-11. `parse_sssom_tsv` handles both 9-col legacy and 11-col current.
- **curie_map block required in header** — `parse_sssom_tsv` expects `# curie_map:` in the YAML front-matter; our builder must do the same for consistency.
- **MMC vs HC** — only HC rows go into YARRRML. Phase 16 code must filter defensively.

### 7.5 LinkML-map is NOT a substitute

From project planning: the instinct might be "we have LinkML everywhere, use linkml-map." But linkml-map performs **LinkML-instance to LinkML-instance** transforms — both sides must already be in LinkML/JSON form. It does not consume CSV/XML/arbitrary JSON and does not produce RDF. Use it only if we later want to transform *already-materialized* master RDF into downstream LinkML views. It's adjacent, not competitive.

**Sources:**
- [yarrrml-parser issues#67 — nested objects pitfalls](https://github.com/RMLio/yarrrml-parser/issues/67)
- [yarrrml-parser issues#95 — flat array values](https://github.com/RMLio/yarrrml-parser/issues/95)
- [yarrrml-parser issues#137 — object type discarded](https://github.com/RMLio/yarrrml-parser/issues/137)
- [yarrrml-parser issues#158 — XML namespace](https://github.com/RMLio/yarrrml-parser/issues/158)
- [Path-based and triplification approaches (SWJ 2024)](https://content.iospress.com/articles/semantic-web/sw243585) — user-behaviour study of RML/YARRRML mistakes
- [LinkML-Map](https://linkml.io/linkml-map/) — confirming scope mismatch

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11+ | All | ✓ | 3.11+ | — |
| uv | Build | ✓ | current | — |
| rdflib | Pipeline step 2 | ✓ | already in pyproject | — |
| morph-kgc | RML execution (16-03) | ✗ (need `uv add`) | 2.10.0 | yatter + RMLMapper.jar (Java — reject) |
| linkml + linkml-runtime | Schema introspection, jsonld-context | ✓ | already in pyproject | — |
| sssom + sssom-py | SSSOM parsing | ✓ | already in pyproject (≥0.4.15) | Re-use `rosetta/core/accredit.py::parse_sssom_tsv` |
| curies | CURIE expansion | ✗ (transitively via sssom-py usually) | latest | Hand-rolled CURIE resolver (reject — curies is maintained) |
| yatter (optional) | Debug RML output | ✗ | 1.2+ | skip |
| Java | RMLMapper fallback | not required | — | — |
| Node.js | yarrrml-parser fallback | not required | — | — |

**Missing dependencies to add in Plan 16-01:**
- `morph-kgc>=2.10` (deferred to 16-03, but add early for CI)
- `curies>=0.7` (add now — needed for CURIE resolution in 16-01)

**Missing but not blocking:** `yatter` — optional diagnostic feature.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥ 8 (already configured in pyproject.toml) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run | `uv run pytest rosetta/tests/test_rml_gen.py -x -m "not slow"` |
| Full suite | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| REQ-V2-RMLGEN-01 | Parses SSSOM TSV, resolves CURIEs, emits valid YARRRML for JSON source | unit | `pytest test_rml_gen.py::test_json_yarrrml_shape -x` | ❌ Wave 0 |
| REQ-V2-RMLGEN-01 | Exits 1 on unresolved subject_id; exits 0 with `--force` | unit | `pytest test_rml_gen.py::test_unresolved_exits -x` | ❌ Wave 0 |
| REQ-V2-RMLGEN-01 | Covers 100% of HC-approved SSSOM rows in output | unit | `pytest test_rml_gen.py::test_coverage_report -x` | ❌ Wave 0 |
| REQ-V2-RMLGEN-01 | CSV format: no iterator, column references | unit | `pytest test_rml_gen.py::test_csv_yarrrml -x` | ❌ Wave 0 |
| REQ-V2-RMLGEN-01 | XML format: XPath iterator | unit | `pytest test_rml_gen.py::test_xml_yarrrml -x` | ❌ Wave 0 |
| REQ-V2-RMLGEN-01 | E2E: SSSOM + source + schemas → morph-kgc → JSON-LD | smoke (slow) | `pytest -m slow test_rml_gen.py::test_e2e_jsonld` | ❌ Wave 0 |
| REQ-V2-RMLGEN-01 | MMC-only SSSOM file exits 1 unless `--include-manual` | unit | `pytest test_rml_gen.py::test_hc_filter -x` | ❌ Wave 0 |
| REQ-V2-RMLGEN-01 | Prefix precedence (SSSOM > master > source > toml) | unit | `pytest test_rml_gen.py::test_prefix_precedence -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest rosetta/tests/test_rml_gen.py -x` (seconds)
- **Per wave merge:** `uv run pytest -m "not slow"` (regression guard)
- **Phase gate:** `uv run pytest` (full suite, including `-m slow` E2E) green before `verify-work`.

### Wave 0 Gaps

- [ ] `rosetta/tests/test_rml_gen.py` — full rewrite (delete current `MappingDecision`-era tests)
- [ ] `rosetta/tests/fixtures/master.linkml.yaml` — master in LinkML form
- [ ] `rosetta/tests/fixtures/source_tracks.linkml.yaml` — minimal tracks schema
- [ ] `rosetta/tests/fixtures/approved.sssom.tsv` — 5 HC rows
- [ ] `rosetta/tests/fixtures/source_tracks.json`, `.csv`, `.xml` — three-format source data
- [ ] `rosetta/tests/fixtures/master.context.jsonld` — framed context (or regenerate on the fly in test)
- [ ] Framework dependency: `uv add morph-kgc curies` (needed for unit tests, not just 16-03)

---

## Recommendations and open questions for the designer

### Locked-in recommendations (HIGH confidence)

1. **Stack:** morph-kgc 2.10 + rdflib + LinkML + curies. Drop yarrrml-parser/RMLMapper/pyrml.
2. **Output format:** YARRRML YAML as the primary artifact; JSON-LD as the `--run` mode output only.
3. **Execution model:** in-process `morph_kgc.materialize()` → rdflib.Graph → `serialize(format="json-ld", context=…)`.
4. **CURIE resolution:** `curies.Converter` merged from 4 sources with SSSOM-header precedence highest.
5. **SubjectMap identifier:** schema-declared `identifier: true` slot first, then `id`, then synthetic row index with warning.
6. **Filter to HumanCuration rows** by default; gate on `--include-manual`.
7. **Exit 1 on unresolved mappings** unless `--force`.
8. **Plan split:** 16-01 JSON + core algorithm + coverage; 16-02 CSV+XML + FnML unit-conversion + schema-comparison report; 16-03 morph-kgc runner + JSON-LD + E2E.

### Open questions for the designer

1. **Class-level mappings vs slot-level mappings in one run:** should class-level SSSOM rows (subject_id resolves to a class URI) auto-generate the `rr:class` on the TriplesMap, or does the user supply class mappings separately? *Recommendation:* infer automatically — if SSSOM has a row `(src:Track, skos:exactMatch, master:Track)`, use `master:Track` as the `subjects:` class. If there's no such row, exit 1 with "add a class-level mapping for source class `src:Track`".

2. **Multi-class schemas:** a source schema can have multiple top-level classes (e.g., `Track`, `Threat`, `Sensor`). Do we emit one YARRRML file with all mappings or one file per class? *Recommendation:* one file with multiple `mappings:` blocks; morph-kgc handles it natively.

3. **FnML for unit conversion — UDF or GREL:** defer entirely to 16-02 decision point. Research shows Python UDF is cleaner but adds a file; GREL inline math handles multiplier/offset only (which is what our `FnmlSuggestion` model carries). *Recommendation:* start with GREL inline for the 95% case (linear conversions); escape to UDF for nonlinear.

4. **Frame vs context-only for JSON-LD:** compaction is simpler and enough for Milestone 3 demo. Framing produces prettier nested output but adds a `@frame` document to maintain. *Recommendation:* context-only for MVP; add frame support behind a `--frame` flag in a post-16 enhancement.

5. **Tests fixture: master schema in LinkML.** Currently `master_cop_ontology.ttl` exists but no `.linkml.yaml` form. Do we (a) hand-author the LinkML form, (b) back-convert from TTL, or (c) treat LinkML as the canonical form going forward and regenerate the TTL from it via `linkml generate owl`? *Recommendation:* (c) — LinkML is already canonical in the v2.0 migration goal; the TTL is a derived artifact.

6. **Audit-log → approved-mapping decoupling:** the audit log mixes MMC and HC. Should `--sssom` point at the full audit log (builder filters) or at a pre-filtered "approved" set produced by a new `rosetta-accredit export-approved` subcommand? *Recommendation:* accept audit log directly (less tooling surface); builder filters for `semapv:HumanCuration`. Matches how `rosetta-suggest` consumes the log today.

7. **Empty SSSOM handling:** a well-formed SSSOM file with zero HC rows — exit 1 (nothing to generate) or exit 0 with an empty YARRRML document? *Recommendation:* exit 1 with a clear message; empty YARRRML is a user confusion trap.

### Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| morph-kgc YARRRML support has edge-case gaps (vs yarrrml-parser reference) | LOW | MEDIUM | Parallel CI run that also pipes YARRRML through yatter and diffs RML; catch divergence early. |
| LinkML `gen-jsonld-context` omits slots due to default_prefix bug | LOW | MEDIUM | Test with real master schema; fall back to hand-authored context if triggered. |
| `curies` merged-prefix precedence semantics differ from expectation | LOW | MEDIUM | Unit test the precedence explicitly (`test_prefix_precedence`). |
| LinkML schema introspection patterns add pyright friction | MEDIUM | LOW | Pre-cast + ignore comments (documented project pattern). |
| UDF registration in morph-kgc INI not testable in pytest without temp-file dance | MEDIUM | LOW | Defer UDF path to 16-02; 16-01 emits datatype-only coercion. |
| SSSOM row mapping `subject_id` is a slot in source but `object_id` is a class in master (mixed-kind) | LOW | LOW | Explicit lint error at classify() time; documented as invalid. |

---

## Sources

### Primary (HIGH confidence — official specs / PyPI / docs)

- [YARRRML spec (rml.io)](https://rml.io/yarrrml/spec/)
- [RML spec](https://rml.io/specs/rml/)
- [YARRRML tutorial](https://rml.io/yarrrml/tutorial/getting-started/)
- [Morph-KGC docs](https://morph-kgc.readthedocs.io/en/latest/documentation/)
- [Morph-KGC GitHub](https://github.com/morph-kgc/morph-kgc)
- [Morph-KGC PyPI (v2.10.0, 2026-01-20)](https://pypi.org/project/morph-kgc/)
- [RML-FNML spec](https://kg-construct.github.io/rml-fnml/spec/docs/)
- [RML-FNML in Morph-KGC (SoftwareX 2024)](https://www.sciencedirect.com/science/article/pii/S2352711024000803)
- [LinkML YARRRML generator](https://linkml.io/linkml/generators/yarrrml.html)
- [LinkML JSON-LD context generator](https://linkml.io/linkml/generators/jsonld-context.html)
- [LinkML generators index](https://linkml.io/linkml/generators/index.html)
- [SSSOM mapping predicates](https://mapping-commons.github.io/sssom/mapping-predicates/)
- [SSSOM predicate_id](https://mapping-commons.github.io/sssom/predicate_id/)
- [sssom-py context module](https://mapping-commons.github.io/sssom-py/_modules/sssom/context.html)
- [curies PyPI / GitHub](https://github.com/biopragmatics/curies)
- [yatter PyPI](https://pypi.org/project/yatter/) / [GitHub](https://github.com/oeg-upm/yatter)
- [rdflib JSON-LD serialization example](https://rdflib.readthedocs.io/en/stable/apidocs/examples.jsonld_serialization/)

### Secondary (MEDIUM — community/issue tracker)

- [yarrrml-parser issues index](https://github.com/RMLio/yarrrml-parser/issues) (pitfalls: #67, #95, #137, #158, #199)
- [LinkML#3131 — improved YARRRML IRI handling](https://github.com/linkml/linkml/pull/3131)
- [LinkML#97 — gen-jsonld-context prefix bug](https://github.com/linkml/linkml/issues/97)
- [LinkML-Map](https://linkml.io/linkml-map/) (for scope-exclusion confirmation)
- [awesome-kgc-tools](https://kg-construct.github.io/awesome-kgc-tools/)
- [Path-based & triplification approaches (SWJ 2024 — user pitfalls study)](https://content.iospress.com/articles/semantic-web/sw243585)

### Tertiary (LOW — used only for sanity checks)

- [kglab morph-kgc example](https://derwen.ai/docs/kgl/ex2_1/)
- [Snyk morph-kgc health](https://snyk.io/advisor/python/morph-kgc)

---

## Metadata

**Confidence breakdown:**
- Stack selection (morph-kgc + rdflib + linkml + curies): **HIGH** — verified against current PyPI and official docs.
- YARRRML spec mechanics: **HIGH** — official rml.io spec + LinkML's own generator as cross-check.
- SSSOM→YARRRML algorithm (Section 4): **MEDIUM** — synthesized from spec semantics; no published prior art; subject to shakeout during Plan 16-01 implementation.
- Unit-conversion FnML via Python UDF: **MEDIUM** — documented in 2024 SoftwareX paper and morph-kgc docs, but real-world YARRRML-with-UDF examples are thin.
- JSON-LD framing via rdflib: **HIGH** — standard rdflib flow.
- Environment availability: **HIGH** — Python ecosystem, no OS/SDK dependencies.

**Research date:** 2026-04-16
**Valid until:** 2026-07-16 (stable specs; 90-day window). If morph-kgc 3.x releases before implementation, reverify JSON-LD output support (a 3.x upgrade might add it natively).
