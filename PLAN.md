# Implementation Plan: Rosetta — Composable CLI Tools for Semantic Mapping

**Version:** 2.0  
**Approach:** Unix-philosophy CLI tools, composed via pipes and scripts  
**Audience:** Solo developer / coding agent  
**Date:** April 2026

---

## 1. Philosophy

Each component of the Rosetta architecture is implemented as a standalone CLI tool that:

- Does one thing well.
- Reads from files or stdin, writes to files or stdout.
- Uses RDF (Turtle/N-Triples) and JSON as interchange formats between tools.
- Can be tested independently with surrogate data before any UI exists.
- Can be composed into pipelines via shell scripts or a lightweight orchestrator later.

The UI is deferred entirely. The "user interface" for Phase 1 is the terminal.

---

## 2. Shared Conventions

**Language:** Python (for RDF ecosystem maturity — rdflib, pySHACL, sentence-transformers, PyTorch Geometric all have first-class Python support).

**Package structure:**

```
rosetta/
├── cli/                    # Entry points for each tool
│   ├── ingest.py
│   ├── embed.py
│   ├── suggest.py
│   ├── lint.py
│   ├── validate.py
│   ├── accredit.py
│   └── provenance.py
├── core/                   # Shared library code
│   ├── rdf_utils.py        # RDF I/O helpers (load/save Turtle, SPARQL helpers)
│   ├── embedding.py        # Embedding model wrappers
│   ├── similarity.py       # Cosine similarity, k-NN, anomaly detection
│   ├── units.py            # QUDT unit comparison logic
│   └── provenance.py       # PROV-O triple generation
├── policies/               # SHACL shapes and Rego policies
│   ├── shapes/
│   │   └── air_track.ttl
│   └── rego/
│       └── sovereignty.rego
├── store/                  # Local file-based "repository" (upgradeable to triple store later)
│   ├── master-ontology/
│   ├── national-schemas/
│   └── accredited-mappings/
├── tests/
│   ├── fixtures/           # Synthetic air defense test data
│   └── test_*.py
└── scripts/
    └── pipeline.sh         # Example end-to-end composition
```

**RDF serialisation:** Turtle (.ttl) for human-readable artifacts. N-Triples for machine interchange (one triple per line, grep-friendly, streamable).

**Configuration:** Each tool reads defaults from a shared `rosetta.toml` config file but all settings are overridable via CLI flags.

**Local-first storage:** Start with a file-based repository (directories of .ttl files). The same tools can later point at a Fuseki/GraphDB SPARQL endpoint by changing the config — the tool interfaces don't change.

---

## 3. The Tools

### Tool 1: `rosetta-ingest`

**Purpose:** Convert a national schema into an RDF graph.

**Input:** A schema file (XSD, JSON Schema, OpenAPI spec (YAML or JSON), SQL DDL, or CSV with headers) + optional sample data file.

**Output:** A Turtle file representing the schema as RDF, with one node per attribute annotated with label, data type, parent entity, detected unit (if any), and statistical summary (if sample data provided).

**Example usage:**

```bash
# Ingest a JSON Schema, output RDF
rosetta-ingest --format jsonschema --nation NOR \
  --schema nor_radar.json \
  --sample-data nor_radar_sample.csv \
  --output store/national-schemas/NOR/nor_radar.ttl

# Ingest an OpenAPI spec (extracts JSON Schema from components/schemas)
rosetta-ingest --format openapi --nation USA \
  --schema us_c2_api.yaml \
  --output store/national-schemas/USA/us_c2.ttl

# Ingest a CSV (headers become attributes, data becomes statistics)
rosetta-ingest --format csv --nation DEU \
  --schema patriot_export.csv \
  --output store/national-schemas/DEU/patriot.ttl
```

**Key implementation details:**

- Per-format parser modules (one per supported format). Start with CSV, JSON Schema, and OpenAPI — they cover most modern integration cases.
- **OpenAPI parsing:** Extract `components.schemas` from the OpenAPI spec (YAML or JSON). Each schema object becomes an entity; its properties become attributes. Supports `$ref` resolution for nested schemas. Descriptions and `format` fields (e.g., `format: double`) are preserved as RDF annotations.
- Unit detection: regex patterns for common unit annotations in field names and descriptions (e.g., `_m`, `_ft`, `_kmh`, `(meters)`, `[NM]`). Falls back to "unknown" if no unit is detected — the linter will catch this later.
- Statistical summary: min, max, mean, stddev, null_rate, cardinality, histogram (10 bins). Stored as RDF annotations on the attribute node using a custom `rosetta:stats` namespace.

**Build order:** First. Everything else depends on having RDF representations of schemas.

**Estimated effort:** 2–3 days.

---

### Tool 2: `rosetta-embed`

**Purpose:** Generate embedding vectors for all attributes in an RDF schema graph.

**Input:** A Turtle file (from `rosetta-ingest` or the Master Ontology).

**Output:** A JSON file mapping each attribute URI to its embedding vectors (lexical, structural, statistical).

**Example usage:**

```bash
# Embed the master ontology (do this once, then incrementally)
rosetta-embed --input store/master-ontology/master.ttl \
  --output store/embeddings/master.json

# Embed a national schema
rosetta-embed --input store/national-schemas/NOR/nor_radar.ttl \
  --output store/embeddings/NOR/nor_radar.json

# Embed with only lexical similarity (skip GNN, useful for early testing)
rosetta-embed --mode lexical-only \
  --input store/national-schemas/NOR/nor_radar.ttl \
  --output store/embeddings/NOR/nor_radar.json
```

**Key implementation details:**

- **Lexical:** Load LaBSE via `sentence-transformers`. Encode `"{parent_entity} / {attribute_label} — {description}"` as the input string to provide context.
- **Structural:** This is the most complex component. For the MVP, start with `--mode lexical-only` and add the GCN later. When implemented: build a PyTorch Geometric `Data` object from the RDF graph, train a 2-layer GCN with TransE objective on the Master Ontology, then use it to encode national schemas.
- **Statistical:** A small feedforward network (or even a simple normalised feature vector for the MVP) over the summary statistics from `rosetta-ingest`.
- **Output format:** `{ "uri": { "lexical": [0.1, 0.2, ...], "structural": [...], "statistical": [...] } }`
- The `--mode` flag allows incremental sophistication: `lexical-only` → `lexical+stats` → `full`. This lets you prove the pipeline works before investing in the GCN.

**Build order:** Second. Depends on Tool 1 output format.

**Estimated effort:** 3–5 days for lexical-only. Additional 1–2 weeks for the full GCN pipeline.

---

### Tool 3: `rosetta-suggest`

**Purpose:** Given a national schema's embeddings and the master ontology's embeddings, suggest mappings.

**Input:** Two embedding JSON files (national + master), plus optional existing accredited mappings for anomaly detection context.

**Output:** A JSON file of ranked suggestions per attribute, with confidence scores broken down by signal type.

**Example usage:**

```bash
# Basic suggestion
rosetta-suggest \
  --source store/embeddings/NOR/nor_radar.json \
  --target store/embeddings/master.json \
  --output suggestions/NOR/nor_radar_suggestions.json

# With anomaly detection against existing mappings
rosetta-suggest \
  --source store/embeddings/NOR/nor_radar.json \
  --target store/embeddings/master.json \
  --existing store/accredited-mappings/ \
  --output suggestions/NOR/nor_radar_suggestions.json

# Tune weights
rosetta-suggest \
  --source store/embeddings/NOR/nor_radar.json \
  --target store/embeddings/master.json \
  --weights 0.3,0.5,0.2 \
  --output suggestions/NOR/nor_radar_suggestions.json
```

**Output format:**

```json
{
  "nor:TRACK_DATA/ALT": {
    "suggestions": [
      {
        "target": "master:Altitude_MSL",
        "score": 0.94,
        "breakdown": { "lexical": 0.97, "structural": 0.92, "statistical": 0.91 },
        "precedent_count": 14,
        "anomaly_flag": null
      },
      {
        "target": "master:Altitude_AGL",
        "score": 0.87,
        "breakdown": { "lexical": 0.95, "structural": 0.84, "statistical": 0.78 },
        "precedent_count": 3,
        "anomaly_flag": null
      }
    ]
  }
}
```

**Key implementation details:**

- Cosine similarity computation across all source×target pairs.
- Weighted composite score with configurable weights.
- **Trust-weighted scoring:** If `--existing` is provided, the tool reads the mapping ledger (`store/accredited-mappings/ledger.json`) maintained by `rosetta-accredit`. ACCREDITED mappings boost the confidence score for their target concept. REVOKED mappings are excluded entirely — they never appear as suggestions and do not count toward precedent. DEPRECATED mappings contribute with reduced weight.
- Anomaly detection: if `--existing` is provided, compute cluster centroids for each master concept and flag suggestions where the proposed vector is > k·σ from the centroid.
- `precedent_count`: how many existing **accredited** (not draft, not revoked) mappings map to the same target concept with similar source attributes.

**Build order:** Third. Depends on Tool 2 output format.

**Estimated effort:** 2–3 days.

---

### Tool 4: `rosetta-lint`

**Purpose:** Check a proposed mapping for unit mismatches, data type issues, and missing conversion functions. Suggest FnML functions from the repository.

**Input:** A mapping decision file (JSON — the suggestions file after the user has marked their selections) + the source schema RDF + the master ontology RDF.

**Output:** A lint report (JSON) with BLOCK/WARNING/INFO findings. If a unit mismatch is found and a known FnML function exists in the repository, include it as a suggestion.

**Example usage:**

```bash
# Lint a set of mapping decisions
rosetta-lint \
  --decisions mappings/NOR/nor_radar_decisions.json \
  --source-schema store/national-schemas/NOR/nor_radar.ttl \
  --master store/master-ontology/master.ttl \
  --fnml-repo store/accredited-mappings/fnml/ \
  --output reports/NOR/nor_radar_lint.json

# Strict mode: treat WARNINGs as BLOCKs
rosetta-lint --strict \
  --decisions mappings/NOR/nor_radar_decisions.json \
  --source-schema store/national-schemas/NOR/nor_radar.ttl \
  --master store/master-ontology/master.ttl \
  --output reports/NOR/nor_radar_lint.json
```

**Decision file format** (input — the user edits this after reviewing suggestions):

```json
{
  "nor:TRACK_DATA/ALT": {
    "target": "master:Altitude_MSL",
    "accepted": true,
    "fnml_function": null
  },
  "nor:TRACK_DATA/RNG": {
    "target": "master:Distance",
    "accepted": true,
    "fnml_function": null
  }
}
```

**Lint report format** (output):

```json
{
  "status": "BLOCKED",
  "findings": [
    {
      "attribute": "nor:TRACK_DATA/RNG",
      "severity": "BLOCK",
      "code": "UNIT_MISMATCH",
      "message": "Source unit is KiloM, target requires NM. No FnML function provided.",
      "suggested_fnml": {
        "uri": "fnml:km_to_nm_v1",
        "source_integration": "DEU_PATRIOT_2024",
        "accredited_by": "NATO_AA",
        "accredited_date": "2024-11-20"
      }
    },
    {
      "attribute": "nor:TRACK_DATA/ALT",
      "severity": "INFO",
      "code": "UNITS_COMPATIBLE",
      "message": "Source and target both use unit:M. No conversion needed."
    }
  ]
}
```

**Key implementation details:**

- Load QUDT unit definitions to compare source vs. target units.
- Search `--fnml-repo` directory for existing conversion functions matching the unit pair.
- Also check: data type compatibility, CRS mismatches (if coordinate attributes), timestamp format compatibility.
- Exit code: 0 if no BLOCKs, 1 if any BLOCK findings. This makes it composable in shell scripts (`rosetta-lint ... && rosetta-validate ...`).

**Build order:** Fourth. Can be developed in parallel with Tool 3 once the schema RDF format (Tool 1) is stable.

**Estimated effort:** 3–4 days.

---

### Tool 5: `rosetta-validate`

**Purpose:** Run SHACL validation on a complete mapping package to ensure it meets structural requirements.

**Input:** A mapping artifact (Turtle — the RML file) + SHACL shapes.

**Output:** A SHACL validation report (Turtle or JSON).

**Example usage:**

```bash
# Validate against air track shape
rosetta-validate \
  --mapping mappings/NOR/nor_radar.rml.ttl \
  --shapes policies/shapes/air_track.ttl \
  --output reports/NOR/nor_radar_shacl.json

# Validate against all shapes in the policies directory
rosetta-validate \
  --mapping mappings/NOR/nor_radar.rml.ttl \
  --shapes-dir policies/shapes/ \
  --output reports/NOR/nor_radar_shacl.json
```

**Key implementation details:**

- Wraps `pySHACL` (the Python SHACL validator).
- Loads the SHACL shapes from `--shapes` or `--shapes-dir`.
- Produces a structured report: which shapes passed, which failed, and why.
- Exit code: 0 if conformant, 1 if not.

**Build order:** Fifth. Independent of Tools 2–4; only depends on the RML output format being defined.

**Estimated effort:** 1–2 days (pySHACL does the heavy lifting; most work is writing good shapes).

---

### Tool 6: `rosetta-rml-gen`

**Purpose:** Generate an RML mapping file from a user's mapping decisions plus any FnML functions.

**Input:** The lint-approved decisions file + source schema RDF + FnML functions.

**Output:** A complete RML/FnML Turtle file ready for validation and accreditation.

**Example usage:**

```bash
# Generate RML from approved decisions
rosetta-rml-gen \
  --decisions mappings/NOR/nor_radar_decisions.json \
  --source-schema store/national-schemas/NOR/nor_radar.ttl \
  --master store/master-ontology/master.ttl \
  --output mappings/NOR/nor_radar.rml.ttl
```

**Key implementation details:**

- Templates for RML `LogicalSource`, `SubjectMap`, and `PredicateObjectMap`.
- If a decision includes an `fnml_function`, the generator wraps the object map in an `fnml:functionValue` block.
- The output is valid RML that can be executed by RMLMapper against real source data.

**Build order:** Sixth. Depends on the decisions format from Tools 3/4.

**Estimated effort:** 2–3 days.

---

### Tool 7: `rosetta-provenance`

**Purpose:** Stamp a mapping artifact with PROV-O metadata.

**Input:** A mapping artifact (Turtle) + agent identity + activity type.

**Output:** The same artifact enriched with PROV-O triples, or a separate provenance sidecar file.

**Example usage:**

```bash
# Stamp creation provenance
rosetta-provenance \
  --artifact mappings/NOR/nor_radar.rml.ttl \
  --agent "NOR_Engineer_42" \
  --activity "creation" \
  --output mappings/NOR/nor_radar.rml.ttl

# Stamp accreditation
rosetta-provenance \
  --artifact mappings/NOR/nor_radar.rml.ttl \
  --agent "NATO_AA_Board" \
  --activity "accreditation" \
  --output mappings/NOR/nor_radar.rml.ttl

# Query provenance (who touched this artifact?)
rosetta-provenance --query \
  --artifact mappings/NOR/nor_radar.rml.ttl
```

**Key implementation details:**

- Appends PROV-O triples (`prov:wasGeneratedBy`, `prov:wasAssociatedWith`, `prov:used`, timestamps) to the artifact.
- Each activity gets a unique URI and timestamp.
- `--query` mode reads the existing PROV-O triples and prints a human-readable summary.
- Version tracking: each provenance stamp increments a version annotation on the artifact.

**Build order:** Seventh. Straightforward RDF generation; independent of the ML components.

**Estimated effort:** 1–2 days.

---

### Tool 8: `rosetta-accredit`

**Purpose:** Manage the lifecycle state of mapping artifacts (DRAFT → ACCREDITED → REVOKED). In the CLI-only phase, this is a simple state-machine tool. Digital signatures (PKI) are deferred to later phases.

**Input:** A mapping artifact + desired state transition.

**Output:** The artifact with updated status metadata + provenance stamp.

**Example usage:**

```bash
# Submit for accreditation (runs lint + validate as prerequisites)
rosetta-accredit submit \
  --artifact mappings/NOR/nor_radar.rml.ttl \
  --agent "NOR_Engineer_42"

# Approve (accredit)
rosetta-accredit approve \
  --artifact mappings/NOR/nor_radar.rml.ttl \
  --agent "NATO_AA_Board"

# Revoke (kill switch)
rosetta-accredit revoke \
  --artifact mappings/NOR/nor_radar.rml.ttl \
  --agent "NATO_AA_Board" \
  --reason "Incorrect conversion constant in fnml:m_to_ft_v2"

# List all artifacts and their current status
rosetta-accredit status --repo store/accredited-mappings/
```

**Key implementation details:**

- `submit` calls `rosetta-lint` and `rosetta-validate` internally. If either fails, submission is blocked.
- `approve` updates the status annotation, calls `rosetta-provenance` to stamp the accreditation, copies the artifact to `store/accredited-mappings/`, and **updates the suggestion index** (see below).
- `revoke` updates status to REVOKED, stamps provenance with reason, **removes the mapping from the suggestion index**, and (in future phases) triggers downstream notifications.
- `status` scans the repository and lists artifacts with their current lifecycle state.

**Feedback loop — how accreditation improves suggestions:**

The `approve` and `revoke` commands maintain a **mapping ledger** (`store/accredited-mappings/ledger.json`) that `rosetta-suggest` reads at query time. This ledger records every accredited source→target mapping pair with its trust weight.

- When a mapping is **ACCREDITED**, it is added to the ledger with a high trust weight. `rosetta-suggest` uses this to boost the confidence score of the same target concept when a structurally similar source attribute appears in a future integration. The `precedent_count` in suggestion output reflects only accredited mappings.
- When a mapping is **REVOKED**, it is marked as excluded in the ledger. `rosetta-suggest` filters it out entirely — revoked mappings never appear as suggestions or count toward precedent. If a revoked mapping was the *only* precedent for a particular source→target pair, the system falls back to pure embedding similarity without historical boosting.
- When a mapping is **DEPRECATED** (superseded by a newer version), its trust weight is reduced but it is not excluded. It contributes weaker historical signal.

This means the suggestion engine gets better with every approval cycle, and bad mappings are actively purged from its recommendations.

**Build order:** Eighth. Orchestrates the other tools.

**Estimated effort:** 2–3 days.

---

## 4. The Pipeline

Once all tools are built, an end-to-end integration looks like this:

```bash
#!/bin/bash
# pipeline.sh — Full mapping workflow for a Norwegian radar

set -euo pipefail
NATION="NOR"
SYSTEM="nor_radar"

echo "=== Step 1: Ingest schema ==="
rosetta-ingest --format csv --nation $NATION \
  --schema data/$SYSTEM.csv \
  --output store/national-schemas/$NATION/$SYSTEM.ttl

echo "=== Step 2: Generate embeddings ==="
rosetta-embed --mode lexical-only \
  --input store/national-schemas/$NATION/$SYSTEM.ttl \
  --output store/embeddings/$NATION/$SYSTEM.json

echo "=== Step 3: Get mapping suggestions ==="
rosetta-suggest \
  --source store/embeddings/$NATION/$SYSTEM.json \
  --target store/embeddings/master.json \
  --existing store/accredited-mappings/ \
  --output suggestions/$NATION/${SYSTEM}_suggestions.json

echo "=== Suggestions generated. Review and edit: ==="
echo "  suggestions/$NATION/${SYSTEM}_suggestions.json"
echo "  Mark 'accepted: true' for each mapping you approve."
echo "  Press Enter when done."
read

echo "=== Step 4: Lint mapping decisions ==="
rosetta-lint \
  --decisions suggestions/$NATION/${SYSTEM}_suggestions.json \
  --source-schema store/national-schemas/$NATION/$SYSTEM.ttl \
  --master store/master-ontology/master.ttl \
  --fnml-repo store/accredited-mappings/fnml/ \
  --output reports/$NATION/${SYSTEM}_lint.json

echo "=== Step 5: Generate RML ==="
rosetta-rml-gen \
  --decisions suggestions/$NATION/${SYSTEM}_suggestions.json \
  --source-schema store/national-schemas/$NATION/$SYSTEM.ttl \
  --master store/master-ontology/master.ttl \
  --output mappings/$NATION/$SYSTEM.rml.ttl

echo "=== Step 6: Validate against SHACL shapes ==="
rosetta-validate \
  --mapping mappings/$NATION/$SYSTEM.rml.ttl \
  --shapes-dir policies/shapes/ \
  --output reports/$NATION/${SYSTEM}_shacl.json

echo "=== Step 7: Stamp provenance and submit ==="
rosetta-provenance \
  --artifact mappings/$NATION/$SYSTEM.rml.ttl \
  --agent "${NATION}_Engineer" \
  --activity "creation"

rosetta-accredit submit \
  --artifact mappings/$NATION/$SYSTEM.rml.ttl \
  --agent "${NATION}_Engineer"

echo "=== Pipeline complete. Artifact is SUBMITTED. ==="
echo "  AA can approve with: rosetta-accredit approve --artifact mappings/$NATION/$SYSTEM.rml.ttl --agent NATO_AA"
```

---

## 5. Dependency Graph and Parallel Development

The tools have the following dependency structure. Tools on the same row can be developed in parallel.

```
                    ┌──────────────┐
                    │   rosetta-   │
         ┌─────────│   ingest     │──────────┐
         │         └──────────────┘           │
         │           Defines the              │
         │           RDF schema format        │
         │           all tools consume        │
         ▼                                    ▼
┌──────────────┐                    ┌──────────────┐
│   rosetta-   │                    │   rosetta-   │
│   embed      │                    │   validate   │
└──────┬───────┘                    └──────┬───────┘
       │                                   │
       ▼                                   │
┌──────────────┐   ┌──────────────┐        │
│   rosetta-   │   │   rosetta-   │        │
│   suggest    │   │   lint       │        │
└──────┬───────┘   └──────┬───────┘        │
       │                  │                │
       └────────┬─────────┘                │
                ▼                          │
       ┌──────────────┐                    │
       │   rosetta-   │                    │
       │   rml-gen    │                    │
       └──────┬───────┘                    │
              │                            │
              └──────────┬─────────────────┘
                         ▼
              ┌──────────────────┐
              │   rosetta-       │
              │   provenance     │
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │   rosetta-       │
              │   accredit       │
              │   (orchestrates  │
              │    lint+validate │
              │    +provenance)  │
              └──────────────────┘
```

**What can be built in parallel:**

| Phase | Tools | Notes |
|---|---|---|
| Phase A | `rosetta-ingest` | Foundation — must come first. Defines the RDF format. |
| Phase B (parallel) | `rosetta-embed` + `rosetta-validate` + `rosetta-provenance` | All three depend only on the RDF format from Phase A. They don't depend on each other. `rosetta-lint` can also start here if you define the decisions JSON format upfront. |
| Phase C (parallel) | `rosetta-suggest` + `rosetta-lint` | `suggest` needs embeddings. `lint` needs the decisions format and QUDT. These two are independent of each other. |
| Phase D | `rosetta-rml-gen` | Needs the decisions format from suggest/lint. |
| Phase E | `rosetta-accredit` | Orchestrator — wires everything together. Build last. |

For a solo developer, the practical build order follows the milestones below (you can't parallelise across yourself). But if you bring on a second developer or hand tools to a coding agent, Phases B and C each contain tools that can be built simultaneously.

---

## 6. Milestones

### Milestone 1: "Can we ingest and compare?" (Week 1–2)

Build: `rosetta-ingest` + `rosetta-embed` (lexical-only mode) + `rosetta-suggest`

Test with: Synthetic air defense data — a small Master Air Defense Ontology in Turtle (~20 concepts: AirTrack, Altitude_MSL, Heading, Speed, Range, Classification, etc.) and three synthetic national schemas: a Norwegian radar CSV (column names in Norwegian, units in metric), a German Patriot JSON Schema (field names in German, units in metric), and a US C2 OpenAPI spec (English labels, units in imperial/nautical). Verify that the system suggests correct cross-lingual mappings (e.g., "Høyde" → Altitude_MSL, "Geschwindigkeit" → Speed).

**You have a working suggestion engine.**

### Milestone 2: "Can we catch mistakes?" (Week 3–4)

Build: `rosetta-lint` + `rosetta-rml-gen`

Test with: Using the same synthetic schemas, intentionally map the Norwegian radar's range (kilometers) to the master's Range (nautical miles) without a conversion function. Verify the linter blocks it. Add an FnML function (`fnml:km_to_nm`) to the repository, re-run, verify the linter suggests it. Also test: mapping altitude (meters) to altitude (feet) without conversion — verify BLOCK. Mapping a heading (degrees) to a heading (degrees) — verify PASS.

**You have a safety-critical validation layer.**

### Milestone 3: "Can we track who did what?" (Week 5–6)

Build: `rosetta-provenance` + `rosetta-accredit` + `rosetta-validate`

Test with: Run the full pipeline.sh against the Norwegian radar schema. Verify the resulting artifact has complete PROV-O metadata. Verify SHACL validation catches a missing required field (e.g., remove the timestamp mapping from the AirTrack and confirm rejection). Verify the accredit tool enforces the state machine (can't approve without passing lint + validate). **Test the feedback loop:** approve the Norwegian mapping, then run `rosetta-suggest` against the German schema — verify that the approved Norwegian mappings boost suggestion confidence and appear in `precedent_count`. Then revoke one mapping and verify it disappears from suggestions entirely.

**You have the governance layer and feedback loop. The core system is complete.**

### Milestone 4: "Can we learn from history?" (Week 7–10)

Enhance: Add structural (GCN) and statistical embeddings to `rosetta-embed`. Test against real-world logistics data (GS1 EPCIS ontology as master, real CSV/API schemas from public logistics datasets). Verify that suggestion quality improves with the richer embedding modes.

**You have institutional memory.**

### Milestone 5: "Can someone else use this?" (Week 11+)

Build: A lightweight web UI or TUI (terminal UI) that wraps the CLI tools. Or expose the tools as a REST API and build a frontend later. The CLI tools don't change — the UI is just a shell over them.

---

## 7. Test Data Plan

### Milestones 1–3: Synthetic Air Defense Data (generated by the developer)

The developer creates a small but realistic synthetic dataset that exercises all system capabilities without requiring classified data.

**Master Ontology (~20 concepts):**

A Turtle file defining a simplified Air Defense ontology with QUDT unit annotations:

- `AirTrack` (entity) with attributes: `Altitude_MSL` (unit: M), `Altitude_AGL` (unit: M), `Heading` (unit: DEG), `Speed` (unit: KN), `Range` (unit: NM), `Bearing` (unit: DEG), `Latitude` (unit: DEG), `Longitude` (unit: DEG), `Timestamp` (format: ISO8601), `Track_ID` (string), `Classification` (enum: FRIEND/HOSTILE/UNKNOWN)
- `RadarReturn` (entity) with attributes: `Signal_Strength` (unit: dBm), `Cross_Section` (unit: M2), `Doppler_Shift` (unit: HZ)
- `EngagementZone` (entity) with attributes: `Min_Range` (unit: NM), `Max_Range` (unit: NM), `Min_Altitude` (unit: M), `Max_Altitude` (unit: M)

**Norwegian Radar Schema (CSV with Norwegian labels, metric units):**

```
sporings_id, breddegrad, lengdegrad, hoyde_m, kurs_grader, hastighet_kmh, avstand_km, peiling_grader, tidsstempel, klassifisering, signalstyrke_dbm
```

**German Patriot Schema (JSON Schema with German labels, metric units):**

```json
{ "Ziel_ID": "string", "Breite": "number", "Laenge": "number",
  "Hoehe_Meter": "integer", "Kurs": "number", "Geschwindigkeit_ms": "number",
  "Entfernung_km": "number", "Zeitstempel": "string", "Bedrohungsstufe": "string" }
```

**US C2 System Schema (OpenAPI spec, English labels, imperial/nautical units):**

```yaml
components:
  schemas:
    Track:
      properties:
        track_number: { type: string }
        lat_dd: { type: number, description: "Latitude in decimal degrees" }
        lon_dd: { type: number, description: "Longitude in decimal degrees" }
        altitude_ft: { type: integer, description: "Altitude in feet MSL" }
        course_deg: { type: number }
        speed_kts: { type: number, description: "Speed in knots" }
        range_nm: { type: number, description: "Range in nautical miles" }
        timestamp_z: { type: string, format: date-time }
        id_status: { type: string, enum: [FRIENDLY, HOSTILE, UNKNOWN, PENDING] }
```

This gives you three schemas with overlapping concepts, different languages, different units (metric vs. imperial vs. nautical), and different formats — exactly the conditions the system is designed to handle.

### Milestone 4: Real Logistics Data (provided by the developer)

The developer will source real-world logistics ontologies and datasets for scale testing:

- **Master:** GS1 EPCIS vocabulary, SOSA/SSN, or Logistics Core Ontology
- **National schemas:** Public supply chain APIs, AIS vessel data, freight/transport open data
- **Goal:** Validate that GCN structural embeddings improve suggestion quality at scale (~50+ concepts, multiple real schemas)

---

## 8. Dependencies

```
# Core
rdflib              # RDF parsing and serialisation
pyshacl             # SHACL validation
pyyaml              # OpenAPI spec parsing (YAML)

# Embeddings (can defer GCN deps to Milestone 4)
sentence-transformers  # LaBSE
torch                  # PyTorch (for LaBSE and GCN)
torch-geometric        # GCN/GAT (Milestone 4)
numpy
scikit-learn           # k-NN, cosine similarity

# CLI
click                  # CLI framework
toml                   # Config file parsing

# Optional / Later
rmlmapper-py           # RML execution against live data
milvus-lite            # Vector store (or just use numpy for MVP)
```

For the MVP (Milestones 1–3), you do not need a vector database. Numpy cosine similarity over a few hundred embeddings is instant. Milvus or Pinecone becomes relevant when the repository grows to thousands of attributes.

---

## 9. What This Defers

The following items from the Architecture document are explicitly deferred to post-MVP:

| Deferred Item | Reason | When to Add |
|---|---|---|
| Web UI | Not needed to prove the core logic works | After Milestone 3 |
| Triple store (Fuseki/GraphDB) | File-based storage is sufficient for MVP; same RDF format means migration is trivial | When query complexity or multi-user concurrency demands it |
| OPA/Rego policies | National sovereignty enforcement requires multi-user infrastructure | When deploying as a shared service |
| Digital signatures (PKI) | `rosetta-accredit` tracks status via metadata for now | When deploying to operational network |
| Vector database (Milvus/Pinecone) | Numpy is fast enough for MVP scale | When embedding count exceeds ~10K attributes |
| GCN structural embeddings | Lexical + statistical is a strong baseline; GCN adds complexity | Milestone 4, after baseline is proven |
| Kill switch notifications | Requires integration with C2 infrastructure | Operational deployment phase |
