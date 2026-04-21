# rosetta-cli

**Map partner-nation schemas to a shared ontology — systematically, transparently, and with auditable human review.**

Defense coalitions speak in many tongues. Norwegian radar tracks, German Patriot telemetry, US C2 feeds — each schema has its own language, units, field names, and structure. Making them interoperate is the difference between a commander seeing one coherent picture and juggling seven.

`rosetta-cli` is a composable Unix toolkit that takes heterogeneous partner schemas and produces a materialized, standards-compliant RDF knowledge graph aligned to a master ontology. Every step is a discrete tool you can script, pipe, inspect, and audit.

---

## What it does

- **Ingests** schemas in seven formats (CSV, TSV, JSON Schema, OpenAPI, XSD, RDFS/OWL, JSON samples) and normalises them to [LinkML](https://linkml.io/).
- **Translates** non-English titles and descriptions via DeepL so multilingual schemas embed in a common semantic space — with originals preserved as aliases.
- **Embeds** every class and slot with multilingual sentence transformers (default: `intfloat/e5-large-v2`), blending **lexical** and **structural** similarity so a field's cardinality, depth, and hierarchy informs the match alongside its name.
- **Suggests** candidate mappings ranked by cosine similarity, automatically boosted by prior approvals and deranked by prior rejections recorded in the audit log.
- **Lints** analyst proposals against physical-unit dimensionality, datatype compatibility, and audit-log conflicts — *before* a human reviewer ever sees them.
- **Records** every decision in an append-only [SSSOM](https://mapping-commons.github.io/sssom/) audit log that feeds straight back into the next `suggest` run.
- **Generates** a [YARRRML](https://rml.io/yarrrml/) mapping from the approved log, compiles it, and materializes it against real source data via [morph-kgc](https://morph-kgc.readthedocs.io/) — producing JSON-LD framed against your master ontology's `@context`.
- **Validates** the RDF against [SHACL](https://www.w3.org/TR/shacl/) shapes — exit `0` conformant, `1` violations — so the pipeline composes cleanly into CI gates.

---

## Why this way

### Standards, not reinvention

Every intermediate artifact uses an open W3C or OBO-community standard:

| Layer | Standard |
|-------|----------|
| Schema normalisation | LinkML |
| Mapping interchange | SSSOM |
| Mapping predicates | SKOS, OWL |
| Justification vocabulary | SEMAPV |
| Provenance | PROV-O |
| Validation | SHACL |
| Materialisation | RML / YARRRML |
| Serialisation | Turtle, N-Triples, JSON-LD |

Nothing locks you in. Every file is readable by third-party tools and survives `rosetta-cli` itself.

### Unix philosophy, strictly

Each command does one thing, reads from files or stdin, writes to files or stdout, and returns meaningful exit codes (`0` conformant, `1` violations). There is no orchestrator, no daemon, no state server — just nine binaries you pipe together. Wrap the pipeline in a shell script, drive it from CI, or step through it interactively.

### Human-in-the-loop, not human-out-of-the-loop

Automated similarity is a **candidate generator**, not a decider. `rosetta-cli` separates two roles:

- The **Analyst** proposes mappings from ranked candidates.
- The **Accreditor** approves or rejects proposals.

This split is enforced through a state machine backed by an append-only audit log. Every mapping in production traces back to a reviewer, a timestamp, a justification, and — where applicable — a composition expression describing how fields combine.

### Multilingual by construction

Coalition schemas are not monolingual. Norwegian `breddegrad` should match English `latitude` on first pass. `rosetta-cli` uses multilingual embeddings, plus an optional DeepL translation pass, so candidates surface across languages without hand-maintained alias tables.

### Auditable, always

The audit log is a 13-column SSSOM TSV. You can `git diff` it, grep it, or drop it into a ticketing system. Every event carries a UUID, a timestamp, a SEMAPV justification, and a confidence score at time of proposal. No decisions live in someone's email.

---

## Who it's for

- **Coalition data architects** aligning partner-nation schemas to a shared operational picture.
- **Ontology engineers** who need a repeatable, reviewable mapping pipeline — not a one-off Jupyter notebook.
- **Defense integrators** who must produce accreditable, provenance-stamped RDF for downstream C2, sensor-fusion, or intelligence systems.
- **Anyone** who has tried to reconcile a dozen CSVs to one schema by hand and sworn *never again*.

---

## Next steps

- [Getting started](getting-started.md) — install, run the bundled demo, and see the full pipeline produce JSON-LD in under ten minutes.
- [The pipeline](concepts/pipeline.md) — a visual tour of how each tool fits together.
- [Accreditation workflow](concepts/accreditation.md) — the Analyst/Accreditor state machine and why it exists.
- [CLI reference](cli/index.md) — per-tool options, arguments, exit codes (auto-rendered from the source).
