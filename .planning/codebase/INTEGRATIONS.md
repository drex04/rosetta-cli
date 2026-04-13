# External Integrations

**Analysis Date:** 2026-04-13

## APIs & External Services
**Model Hosting:**
- Hugging Face Model Hub — provides pre-trained LaBSE embedding model via sentence-transformers
  - SDK: sentence-transformers >=3.0
  - Auth: None (models downloaded to local cache on first use; no API key required)
  - Used by: `rosetta-embed` (`rosetta/core/embedding.py`), `rosetta-suggest` (`rosetta/core/similarity.py`)
  - Config: model name set in `rosetta.toml` `[embed] model = "sentence-transformers/LaBSE"`

## Data Storage
**Databases:** None.

**File Storage:**
- Local file-based RDF repository at path set by `rosetta.toml` `[general] store_path = "store"`
- Override via CLI flag or env var `ROSETTA_GENERAL_STORE_PATH`
- Input formats accepted: Turtle (.ttl), N-Triples (.nt), JSON-LD, RDF/XML (all via rdflib)
- Output formats: Turtle for human artifacts, N-Triples for machine interchange, JSON for embeddings/suggestions

## Authentication & Identity
**Auth Provider:** None.

## Monitoring & Observability
**Error Tracking:** None — errors written to stderr via Click; exit code 1 on failure.
**Logs:** stdout/stderr only; no external log aggregation.

## Environment Configuration
**Development:** No required env vars. All settings override via CLI flags or `rosetta.toml`.
- `ROSETTA_EMBED_MODEL` — optional override for embedding model name
- `ROSETTA_GENERAL_STORE_PATH` — optional override for RDF store location
- No secrets or credentials managed anywhere in the codebase.

**Production:** Same as development; no external service credentials required.

---
*Integration audit: 2026-04-13*
