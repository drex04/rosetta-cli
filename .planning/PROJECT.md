# Project: Rosetta CLI

## Vision

Composable CLI tools (Unix-philosophy) for semantic mapping between NATO nations' defense schemas and a shared master ontology — using RDF, ML embeddings, SHACL validation, and RML generation.

## Problem

NATO nations use different schemas, languages, and units for the same air defense concepts. Cross-nation data fusion (common operational picture) requires labor-intensive, error-prone manual mapping. Rosetta automates discovering, validating, and governing those cross-schema mappings.

## Target Users

NATO/defense integration engineers (and coding agents) who need to map national C2, radar, and air track schemas to a shared master ontology.

## Scope — v1 (Milestones 1–3)

**In:**
- 8 CLI tools: `rosetta-ingest`, `rosetta-embed`, `rosetta-suggest`, `rosetta-lint`, `rosetta-validate`, `rosetta-rml-gen`, `rosetta-provenance`, `rosetta-accredit`
- Local file-based RDF store (directories of `.ttl` files)
- Lexical embeddings (LaBSE via sentence-transformers)
- SHACL validation (pySHACL)
- RML/FnML mapping generation
- PROV-O provenance stamping
- Accreditation state machine (DRAFT → ACCREDITED → REVOKED)
- Feedback loop: approved mappings boost future suggestions; revoked mappings are purged

**Out (deferred):**
- Web UI or REST API
- Triple store (Fuseki/GraphDB)
- OPA/Rego policy enforcement
- Digital signatures (PKI)
- Vector database (Milvus/Pinecone)
- GCN structural embeddings (Milestone 4)
- Kill switch notifications

## Tech Stack

- **Language:** Python 3.11+
- **Package manager:** uv
- **CLI framework:** Click
- **RDF:** rdflib, pySHACL
- **Embeddings:** sentence-transformers (LaBSE), torch, scikit-learn, numpy
- **Config:** rosetta.toml (TOML)
- **Storage:** local file-based (directories of .ttl files)
- **No auth, no database, no web deployment**

## Constraints

- Solo developer / coding agent
- Local-first, no external services required
- Python chosen for RDF ecosystem maturity

## Success Criteria

- Full pipeline (`pipeline.sh`) runs against 3 synthetic air defense schemas (NOR CSV, DEU JSON Schema, USA OpenAPI)
- Correct cross-lingual mapping suggestions (e.g. "Høyde" → Altitude_MSL, "Geschwindigkeit" → Speed)
- Linter blocks unit mismatches (km → NM without conversion function)
- Accredit state machine enforced (can't approve without passing lint + validate)
- Feedback loop: approved mappings boost confidence; revoked mappings disappear from suggestions
