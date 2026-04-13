# External Integrations

**Analysis Date:** 2026-04-13

## APIs & External Services
**Model Hosting:**
- Hugging Face Model Hub — provides pre-trained embedding models (LaBSE, E5) via sentence-transformers
  - SDK: sentence-transformers 3.0+
  - Auth: None (models downloaded to local cache on first use)
  - Used by: `rosetta-embed` (`rosetta/core/embedding.py`), `rosetta-suggest` (`rosetta/core/similarity.py`)

## Data Storage
**Databases:** None (no database integrations)

**File Storage:** 
- **Local file-based RDF repository** — `rosetta/store/` (configurable path via `ROSETTA_GENERAL_STORE_PATH`)
- **Input formats:** Turtle (.ttl), N-Triples (.nt), JSON-LD, RDF/XML (rdflib-supported)
- **Output formats:** Turtle (human-readable), N-Triples (machine interchange), JSON (embeddings, suggestions)
- **Configuration:** managed in `rosetta.toml` and CLI flags (e.g., `--input`, `--output` default to stdin/stdout)

## Authentication & Identity
**Auth Provider:** None (no OAuth, API keys, or identity services)

## Monitoring & Observability
**Error Tracking:** None (errors logged to stderr via Click error handling)
**Logs:** stdout/stderr only (Unix-composable; no external log aggregation)

## Environment Configuration
**Development:** No required env vars; all settings override via CLI flags or `rosetta.toml`
- Optional: `ROSETTA_EMBED_MODEL` to override embedding model
- Optional: `ROSETTA_GENERAL_STORE_PATH` to override RDF store location
- Secrets: None (no credentials managed)

**Production:** Same as development; no external service credentials required

---
*Integration audit: 2026-04-13*
