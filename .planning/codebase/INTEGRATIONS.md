# External Integrations

**Analysis Date:** 2026-04-14

## APIs & External Services
**Model Hosting:**
- Hugging Face Model Hub — provides pre-trained embedding model via sentence-transformers
  - SDK: sentence-transformers >=3.0
  - Auth: None (models downloaded to local cache on first use; no API key required)
  - Default model: `intfloat/e5-large-v2` (set in `rosetta.toml [embed] model`)
  - Used by: `rosetta-embed` (`rosetta/core/embedding.py`), `rosetta-suggest` (`rosetta/core/similarity.py`)

**Translation API:**
- DeepL — machine translation for `rosetta-translate`
  - SDK: deepl >=1.18,<2
  - Auth: `DEEPL_API_KEY` env var (required for translation; source lang configured via `rosetta.toml [translate] source_lang`)

## Data Storage
**Databases:** None.

**File Storage:**
- Local file-based RDF repository at path set by `rosetta.toml` `[general] store_path = "store"`
- **Input formats accepted:** Turtle (.ttl), N-Triples (.nt), JSON-LD, RDF/XML (via rdflib); LinkML YAML (`.linkml.yaml`) via linkml/schema-automator
- **Output formats:**
  - Turtle — human-authored RDF artifacts
  - N-Triples — machine interchange
  - LinkML YAML (`.linkml.yaml`) — primary schema format; output of `rosetta-ingest`, input of `rosetta-embed` and `rosetta-suggest`
  - SSSOM TSV (`.sssom.tsv`) — mapping output from `rosetta-suggest` (replaces JSON)
  - JSON — embedding vectors from `rosetta-embed`

## Authentication & Identity
**Auth Provider:** None.
**Only credential in use:** `DEEPL_API_KEY` for `rosetta-translate`.

## Monitoring & Observability
**Error Tracking:** None — errors written to stderr via Click; exit code 1 on failure.
**Logs:** stdout/stderr only; no external log aggregation.

## Environment Configuration
**Development:**
- `DEEPL_API_KEY` — required only for `rosetta-translate`; all other tools need no env vars
- All other settings override via CLI flags or `rosetta.toml`

**Production:** Same as development; only `DEEPL_API_KEY` is an external credential.

---
*Integration audit: 2026-04-14*
