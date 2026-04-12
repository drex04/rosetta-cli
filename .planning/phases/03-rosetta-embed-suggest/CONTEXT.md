# Phase 3 Context: rosetta-embed + rosetta-suggest

Locked decisions for this phase. Do not re-debate these.

## Plan 01 Decisions (rosetta-embed)

1. **Single unified extractor** — `extract_text_inputs(g)` handles both `rose:Field` (national schemas) and `rose:Attribute` (master ontology) in one function. Detects graph type by checking if any `rose:Attribute` triples exist.

2. **Text string template** — `"{parent} / {label} — {description}"` per PLAN.md spec.
   - For `rose:Field`: parent derived from URI path segment 4 (e.g. `nor_radar` from `http://rosetta.interop/field/NOR/nor_radar/hoyde_m`)
   - For `rose:Attribute`: parent from `?concept rose:hasAttribute ?attr` SPARQL query, using concept `rdfs:label`
   - Fallback: if no parent found, use label alone. If no comment, use empty string.

3. **Test strategy** — Mock `SentenceTransformer` in unit tests (zero CI latency, no download). Add one `@pytest.mark.slow` CLI integration test using a real small model (`all-MiniLM-L6-v2`). Slow tests skipped by default unless `-m slow` passed.

4. **Output parent dirs** — `embed` CLI auto-creates output parent directories (`Path.mkdir(parents=True, exist_ok=True)`) before writing JSON.

5. **Model loading** — `EmbeddingModel` class wraps `SentenceTransformer`; loaded once per CLI invocation, not per attribute. `encode()` takes a list of strings, returns a list of Python floats (via `.tolist()`).

6. **Output JSON format** — `{ "uri": { "lexical": [float, ...] } }` for `lexical-only` mode. Designed to extend to `lexical+stats` and `full` in future plans.

7. **Config integration** — model and mode read via `get_config_value(config, "embed", "model")` and `get_config_value(config, "embed", "mode")` with 3-tier precedence (CLI > env > rosetta.toml).

8. **Dependencies** — `sentence-transformers` and `numpy` added to `[project.dependencies]` in pyproject.toml (not optional, as embed is a core tool).

## Plan 01 Review Decisions

9. **[review] None-guard on OPTIONAL SPARQL vars** — `query_graph` returns Python `None` for unbound OPTIONAL variables. All OPTIONAL fields (`conceptLabel`, `comment`) must be coerced to `""` before f-string formatting. Omitting this guard silently produces the string `"None"` in text inputs, corrupting embeddings.

10. **[review] URIRef must be coerced to str** — `query_graph` returns `URIRef` objects for subject variables. The result dict key must use `str(uri)` to avoid `TypeError` from `json.dumps()`.

11. **[review] try/except wraps full CLI body** — All exceptions from graph loading, model loading, encoding, and I/O are caught and emitted as clean stderr messages with `sys.exit(1)`. Mirrors `ingest.py` pattern exactly.

12. **[review] `open_output()` for both file and stdout** — `mkdir` guard runs first for file paths, then `open_output(output_path)` handles both branches uniformly. This maintains architectural consistency with `ingest.py`.

13. **[review] URI path segment is index -2 (3rd segment after domain)** — The plan's prose said "4th" which was wrong. `nor_radar` is the 3rd path segment; `uri.split("/")[-2]` is correct. Implementers must not use index 4 (yields nation code).

### Deferred Ideas

- Fast mocked CLI test for master-ontology path (`test_embed_cli_master`) — deferred to avoid scope creep; slow test provides real coverage.
- `sentence-transformers` model download progress note (tqdm output to stderr is acceptable by default).

## Plan 02 Decisions (rosetta-suggest)

14. **Named flags, not positional args** — CLI uses `--source` and `--master` (not positional). Mirrors embed/ingest style; explicit in shell pipelines.

15. **File-only inputs** — `--source` and `--master` are file paths only; no stdin support. Two simultaneous stdin streams are not practical for this tool.

16. **Configurable anomaly threshold** — `rosetta.toml [suggest] anomaly_threshold = 0.3` + `--anomaly-threshold` CLI flag. Follows 3-tier precedence (`get_config_value`). Any source field whose max cosine similarity across all master attributes is below this value gets `"anomaly": true` in output.

17. **Numpy-only cosine similarity** — `cosine_matrix(A, B)` implemented as `(A @ B.T) / (‖A‖ · ‖B‖ᵀ)` using numpy alone. No scipy dependency.

18. **Output JSON schema** — keyed by source URI string:
    ```json
    {
      "<source_uri>": {
        "suggestions": [
          {"uri": "<master_uri>", "score": 0.92, "rank": 1},
          ...
        ],
        "anomaly": false
      }
    }
    ```
    Scores rounded to 6 decimal places. Rank is 1-based, ascending.

19. **top-k and min-score defaults** — `--top-k 5`, `--min-score 0.0`. Both configurable via `rosetta.toml [suggest]` section.

20. **Test strategy** — Unit tests for `similarity.py` use synthetic numpy arrays (no model). CLI tests use pre-baked embedding JSON fixtures (no model invocation). No slow/integration tests needed for suggest (embed already covers the model path).

## Plan 02 Review Decisions

21. **[review] rank_suggestions is pure math** — Signature: `rank_suggestions(src_uris, A, master_uris, B, ...)` where A/B are `np.ndarray`. The CLI owns JSON-to-ndarray conversion. Keeps similarity.py free of I/O and dict-parsing logic.

22. **[review] Anomaly computed pre-filter** — `anomaly = float(sim_row.max()) < anomaly_threshold` before `min_score` is applied. A field with a real match at score 0.8 filtered by `min_score=0.9` is NOT anomalous.

23. **[review] Dimension mismatch guard** — `cosine_matrix` raises `ValueError(f"Embedding dimension mismatch: source={A.shape[1]}, master={B.shape[1]}")` before any matmul. Prevents cryptic numpy tracebacks.

24. **[review] "lexical" key guard in CLI** — Before `np.array()` construction, loop over all URIs and raise `ValueError(f"Missing 'lexical' key for URI: {uri}")` if absent. Caught by top-level try/except.

25. **[review] Separate empty-file messages** — `"No embeddings found in source file: {path}"` vs `"No embeddings found in master file: {path}"` — not a combined message.

26. **[review] top_k > master returns all** — `min(top_k, len(master_uris))` slice; documented behaviour, tested in `test_rank_suggestions_top_k_exceeds_master`.

### Deferred Ideas

- Short-form CLI aliases `-s`/`-m` for `--source`/`--master` — omitted for now; add when other tools adopt consistent short aliases
- `--format table` human-readable output — deferred to a later UX pass
- Config precedence integration test for `--min-score` and `--anomaly-threshold` (only `--top-k` is tested; pattern is symmetric)
