# External Integrations

**Last Updated:** 2026-04-16 (Phases 14-15)

## APIs & External Services

### HuggingFace Model Hub

- **Service:** Sentence Transformers (remote model hosting)
- **Auth:** None — models downloaded anonymously on first run
- **Default model:** `intfloat/e5-large-v2` (set in `rosetta.toml [embed] model`)
- **Location:** Initialized in `rosetta/core/embedding.py:EmbeddingModel.__init__()`, used by `rosetta-embed` and `rosetta-suggest`
- **Cache:** Models auto-cached in `~/.cache/huggingface/` (HF transformers library default)
- **Fallback:** None — if fetch fails, embedding generation fails

### DeepL Translation API

- **Service:** DeepL machine translation
- **Auth:** Required — `DEEPL_API_KEY` env var or `--deepl-key` CLI flag (flag takes precedence)
- **Integration:** `rosetta/cli/translate.py`, `rosetta/core/translation.py`
- **Free tier:** Supported via `deepl>=1.18,<2` client
- **Failure mode:** Exit code 1 if key missing; API errors propagate to stderr
- **Config:** Source language set in `rosetta.toml [translate] source_lang` (default: "auto" for server-side detection)

## File-Based Storage

**Root path:** `store/` (configurable in `rosetta.toml [general] store_path`)

| Path                        | Format           | Purpose                          |
|-----------------------------|------------------|----------------------------------|
| `store/audit-log.sssom.tsv` | SSSOM TSV (11 cols) | Append-only accreditation log (Phase 14) |
| `store/accredited-mappings/` | Turtle/JSON      | Exported validated mappings      |
| `store/national-schemas/`   | LinkML YAML      | Imported NATO schemas            |
| `store/master-ontology/`    | Turtle           | Master ontology (read-only)      |

**Access patterns:**
- **Read:** `rosetta/core/io.py` for file I/O; `rosetta/core/rdf_utils.py` for RDF parsing
- **Write:** Append-only via `rosetta/core/accredit.py:append_log()` (Phase 14); full rewrites for exports
- **Concurrency:** None — single-writer assumed; concurrent writes to audit-log will corrupt

## No External Dependencies

- **No databases** (Postgres, MongoDB, DynamoDB, etc.)
- **No authentication** (no OAuth, JWT, LDAP; CLI tools are file-based)
- **No message queues** (Kafka, RabbitMQ, SQS)
- **No monitoring/observability** (no Datadog, New Relic, Sentry)
- **No email/Slack** (no SMTP, webhook notifications)
- **No CI integrations** (GitHub Actions is self-contained; `.github/workflows/ci.yml` has no webhook triggers)

## Environment Variables

| Variable         | Source              | Required | Used by              |
|------------------|---------------------|----------|----------------------|
| `DEEPL_API_KEY`  | Shell or flag only  | For translate | `rosetta/cli/translate.py`, `rosetta/core/translation.py` |

**Note:** Do not commit `.env` files; secrets are shell-only or passed via `--deepl-key`.

## Data Serialization (Internal)

- **RDF:** rdflib's Turtle/N-Triples parsers (no remote RDF endpoint)
- **SSSOM:** `sssom>=0.4.15` library for TSV parsing and 11-column validation (Phase 15)
- **YAML:** pyyaml for `rosetta.toml` and LinkML `.linkml.yaml`
- **JSON:** Standard library + Pydantic `model_dump(mode="json")` (no bare dicts)
