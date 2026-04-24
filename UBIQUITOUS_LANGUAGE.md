# Ubiquitous Language

## Schemas and Ontologies

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Source Schema** | A partner-nation's data schema describing their sensor or C2 system, in any supported format (CSV, JSON Schema, OpenAPI, XSD, RDFS/OWL, JSON sample) | National schema, partner schema, input schema |
| **Master Ontology** | The authoritative shared RDF ontology that all source schemas are mapped to | Target ontology, reference ontology, canonical schema |
| **LinkML Schema** | The normalized intermediate representation that `ingest` produces from any source schema | YAML schema, intermediate schema |
| **Class** | A named entity type in a LinkML schema (e.g. `RadarTrack`, `WeaponSystem`) | Entity, type, object, node |
| **Slot** | A named property or field within a class in a LinkML schema | Field, attribute, property, column |

## Mapping Pipeline

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Ingest** | The act of parsing a source schema into a normalized LinkML schema, optionally translating labels and generating SHACL shapes | Import, parse, convert |
| **Candidate Mapping** | A machine-generated proposed correspondence between a source slot/class and a master ontology slot/class, ranked by cosine similarity | Suggestion, recommendation, match |
| **Embedding** | A dense vector representation of a schema element's label + description, produced by a sentence-transformer model (E5) for similarity comparison | Vector, encoding |
| **Cosine Similarity** | The similarity metric used to rank candidate mappings between source and master schema elements | Score, distance, similarity |

## Audit and Governance

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Audit Log** | The append-only SSSOM TSV file that records every mapping decision, keyed by (subject, object) pair | Log, decision log, history |
| **SSSOM** | Simple Standard for Sharing Ontological Mappings -- the TSV-based file format used for all mapping records | Mapping file, TSV |
| **Subject** | The source-schema element (left side) in a mapping row | Source, left, from |
| **Object** | The master-ontology element (right side) in a mapping row | Target, right, to |
| **Predicate** | The semantic relationship asserted between subject and object (e.g. `skos:exactMatch`, `skos:broadMatch`, `owl:differentFrom`) | Relation, link type |
| **ManualMappingCuration (MMC)** | An analyst's proposed mapping decision, written as a new SSSOM row with `mapping_justification: semapv:ManualMappingCuration` | Proposal, analyst decision |
| **HumanCuration (HC)** | An accreditor's review decision that confirms, narrows, or rejects a prior MMC row, with `mapping_justification: semapv:HumanCuration` | Review, approval, accreditor decision |
| **Lint Gate** | The automated quality check that runs before any `ledger append` -- blocks on unit mismatches, duplicate pairs, invalid predicates, and datatype conflicts | Validation, pre-commit check |

## Roles

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Analyst** | The person who reviews candidate mappings and proposes decisions (MMC rows) via `ledger append --role analyst` | Mapper, reviewer, user |
| **Accreditor** | The person who reviews analyst proposals and renders final decisions (HC rows) via `ledger append --role accreditor` | Approver, reviewer, auditor |

## Materialisation

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Compile** | The act of transforming approved audit-log mappings into a YARRRML specification | Generate, build, export |
| **YARRRML** | The declarative mapping language that `compile` produces, used as input to the materialisation engine | RML, mapping rules, mapping spec |
| **Transform** | The act of materialising source data into JSON-LD by applying a compiled YARRRML spec through morph-kgc | Materialise, execute, run |
| **SHACL Shapes** | RDF constraint graphs used to validate that materialised output conforms to the master ontology's structure | Constraints, validation rules, shapes |
| **FnML Suggestion** | A recommended RML function (from the QUDT policy graph) for converting between incompatible units during materialisation | Conversion function, unit function |

## Units and Quality

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **QUDT** | The Quantities, Units, Dimensions, and Types ontology used for unit compatibility checks and conversion lookups | Unit ontology |
| **Dimension Vector** | A QUDT string encoding the physical dimensions of a unit (length, mass, time, etc.), used to determine compatibility | Unit dimensions, physical quantity |
| **Unit Compatibility** | Two units are compatible if they share the same dimension vector (e.g. meters and feet are compatible; meters and kilograms are not) | Unit match, dimension match |
| **Datatype Compatibility** | Source and target slots have compatible XSD datatypes -- BLOCK on numeric-to-string, WARNING on narrowing casts (float to int) | Type check, type match |
| **Reachability** | A source slot's owning class has a corresponding class mapping in the audit log, so the slot mapping can actually be compiled | Connected, mapped class |

## Relationships

- A **Source Schema** is ingested into exactly one **LinkML Schema**
- The **Master Ontology** is also ingested into a **LinkML Schema** (with `--master` to generate **SHACL Shapes**)
- **Candidate Mappings** are generated by comparing **Embeddings** of a source **LinkML Schema** against a master **LinkML Schema**
- An **Analyst** reviews **Candidate Mappings** and writes **MMC** rows to the **Audit Log** (via the **Lint Gate**)
- An **Accreditor** reviews pending **MMC** rows and writes **HC** rows to the **Audit Log** (via the **Lint Gate**)
- **Compile** reads approved **HC** rows from the **Audit Log** and produces a **YARRRML** spec
- **Transform** applies the **YARRRML** spec to source data and validates the output against **SHACL Shapes**
- A **Lint Gate** checks **Unit Compatibility**, **Datatype Compatibility**, **Reachability**, duplicate pairs, and predicate validity before any **Audit Log** write
- An **FnML Suggestion** is produced when a **Lint Gate** detects incompatible but dimensionally-related units

## Example dialogue

> **Dev:** "A partner sent us a Norwegian radar CSV. How does it get into the system?"

> **Domain expert:** "You **ingest** it -- that parses the CSV into a **LinkML Schema**. If the labels are in Norwegian, pass `--translate --lang NB` so they come out in English. You also ingest the **Master Ontology** with `--master` to get the **SHACL Shapes**."

> **Dev:** "Then what produces the candidate mappings?"

> **Domain expert:** "`suggest` does that. It generates **Embeddings** for both **LinkML Schemas** and ranks **Candidate Mappings** by **Cosine Similarity**. It also filters out any **Subject** that already has a decision in the **Audit Log**."

> **Dev:** "And the analyst just edits the TSV and appends?"

> **Domain expert:** "Right. The **Analyst** marks each row with a **Predicate** -- `skos:exactMatch`, `skos:broadMatch`, or `owl:differentFrom` to reject. Then `ledger append --role analyst` writes **MMC** rows. The **Lint Gate** runs automatically: it will BLOCK if there's a **Unit Compatibility** problem or a duplicate pair."

> **Dev:** "What if the lint gate finds incompatible units that are actually convertible, like meters and feet?"

> **Domain expert:** "It still warns, but it also attaches an **FnML Suggestion** -- a QUDT-derived conversion function. That gets compiled into the **YARRRML** spec so **Transform** applies it automatically."

> **Dev:** "And the accreditor?"

> **Domain expert:** "The **Accreditor** runs `ledger review` to see pending **MMC** rows, then appends **HC** rows. Once approved, `compile` reads the **Audit Log**, filters for accepted **HC** rows, and emits **YARRRML**. Then `transform` materialises JSON-LD and validates it against the **SHACL Shapes**."

## Flagged ambiguities

- **"mapping"** is used to mean three different things: a single SSSOM row (a mapping decision), the YARRRML spec (a mapping document), and the overall process (mapping schemas). Use **Candidate Mapping** for proposals, **SSSOM Row** or **Audit Log entry** for recorded decisions, and **YARRRML spec** for the compiled output.
- **"schema"** can refer to the raw source format (CSV, JSON Schema), the normalized **LinkML Schema**, or the **Master Ontology**. Always qualify: **Source Schema**, **LinkML Schema**, or **Master Ontology**.
- **"validate"/"validation"** appears in two contexts: the **Lint Gate** validates SSSOM proposals before writing, while **SHACL validation** checks materialised RDF output. Prefer **Lint Gate** for pre-append checks and **SHACL validation** for post-transform checks.
- **"reviewer"** is ambiguous between **Analyst** and **Accreditor** -- these are distinct roles with different permissions and lifecycle stages. Always use the specific role name.
- **"suggestion"** can mean either a **Candidate Mapping** (from `suggest`) or an **FnML Suggestion** (from the lint gate). Qualify which.
