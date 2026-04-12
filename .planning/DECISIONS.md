# Decisions

## 2026-04-12: Python + uv as package manager

**Decision:** Use Python with uv (not pip/poetry) as the package manager.
**Why:** uv is fast, modern, handles Python version management, and has excellent lockfile support. Preferred by user.
**Impact:** All install/run commands use `uv run`, `uv add`, `uv sync`.

## 2026-04-12: Local-first file-based storage (no triple store)

**Decision:** Use directories of `.ttl` files as the RDF store for MVP.
**Why:** Sufficient for the scale of Milestones 1–3; same RDF format means migration to Fuseki/GraphDB is trivial by changing config — tool interfaces don't change.
**Impact:** No SPARQL endpoint required for MVP.

## 2026-04-12: Lexical-only embeddings for MVP

**Decision:** Start with LaBSE lexical embeddings; defer GCN structural embeddings to Milestone 4.
**Why:** Proves the pipeline works before investing in GCN complexity. `--mode lexical-only` flag makes this explicit.
**Impact:** rosetta-embed supports `--mode` flag; `full` mode deferred.

## 2026-04-12: Defer UI entirely

**Decision:** No web UI or REST API in v1.
**Why:** Not needed to prove core logic works. "User interface" for Phase 1 is the terminal.
**Impact:** All tools are CLI-only; composable via shell pipes and scripts.
