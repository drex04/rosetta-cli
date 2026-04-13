# Codebase Concerns

**Analysis Date:** 2026-04-13

## Tech Debt

**rdflib SPARQL row access — pervasive pyright suppression:**
- Issue: Every `.attribute` access on SPARQL result rows requires `# pyright: ignore[reportAttributeAccessIssue]` because rdflib rows are untyped.
- Files: `rosetta/core/units.py` (lines 142-147), `rosetta/cli/lint.py` (line 80), `rosetta/core/rdf_utils.py` (line 96)
- Impact: Attribute name typos go undetected; type errors silenced wholesale.
- Fix approach: Wrap `query_graph()` return in a typed helper that unpacks rows by variable name into a typed dict.

**`datetime.utcnow()` deprecated in Python 3.12+:**
- Issue: Uses `datetime.utcnow()` which is deprecated since Python 3.12 and emits `DeprecationWarning`.
- Files: `rosetta/core/accredit.py` (line 52)
- Impact: Warnings in logs; will raise in a future Python release.
- Fix approach: Replace with `datetime.now(tz=timezone.utc)`; update Pydantic model to store aware datetimes.

**prov namespace — 8 `type: ignore` suppressions in one module:**
- Issue: Every PROV triple addition requires `# type: ignore[attr-defined]` because the PROV namespace is untyped.
- Files: `rosetta/core/provenance.py` (lines 89-98), `rosetta/tests/test_provenance.py` (lines 68-90)
- Impact: Masks namespace bugs; duplicates suppression across source and tests.
- Fix approach: Define `PROV = Namespace("http://www.w3.org/ns/prov#")` as a typed local, or cast once at module level.

## Known Limitations

**Accreditation ledger has no concurrency protection:**
- Symptoms: Simultaneous `rosetta-accredit submit` calls on the same `ledger.json` can lose updates (read-modify-write without a lock).
- File: `rosetta/core/accredit.py` (`load_ledger` / `save_ledger`)
- Workaround: Use only in single-writer pipelines; avoid parallel CI jobs writing the same ledger.

**Embedding model downloads at first use (~1 GB):**
- Symptoms: First `rosetta-embed` run downloads LaBSE from HuggingFace with no offline/cached-path config option.
- File: `rosetta/core/embedding.py` (line 91)
- Workaround: Pre-seed `~/.cache/huggingface` or set `HF_HUB_OFFLINE=1` after seeding.

**`UNIT_STRING_TO_IRI` key contract is implicit:**
- Symptoms: Lint silently skips unit checks if `detect_unit()` output doesn't exactly match a key (e.g., `"metre"` vs `"meter"`).
- Files: `rosetta/core/units.py`, `rosetta/core/unit_detect.py`
- Workaround: Keep `detect_unit()` output and map keys synchronized manually.

## Performance Bottlenecks

**QUDT graph loaded fresh on every lint invocation:**
- Problem: `load_qudt_graph()` parses large TTL files each call with no module-level cache.
- File: `rosetta/cli/lint.py` (line 107)
- Cause: No memoization; `importlib.resources` read on every invocation.
- Improvement path: Use `functools.cache` or a lazy module-level singleton.

**Full similarity matrix computed before top-k filter:**
- Problem: `rank_suggestions()` sorts the entire (n_src × n_master) matrix before filtering to top_k.
- File: `rosetta/core/similarity.py`
- Cause: `np.argsort` over full rows; O(n log n) when O(n) via `np.partition` is sufficient.
- Improvement path: Replace `np.argsort` with `np.argpartition` for top_k selection.

## Fragile Areas

**pyshacl return-type cast silences shape changes:**
- Why fragile: `pyshacl.validate()` result is force-cast via `# pyright: ignore[reportAssignmentType]`; if pyshacl changes return shape, the cast silently misassigns.
- File: `rosetta/cli/validate.py` (line 96)
- Safe modification: Add a runtime assertion `assert isinstance(...) and len(...) == 3` after the call.
- Test coverage: Happy-path only; no tests for pyshacl returning unexpected shapes.

**JSON embedding format validated late:**
- Why fragile: `suggest.py` reads all embeddings into memory before checking for the `'lexical'` key.
- File: `rosetta/cli/suggest.py`
- Safe modification: Validate format on first entry before `np.array` allocation; fail fast with a clear message.
- Test coverage: No tests for missing keys, empty arrays, or dimension mismatches.

## Test Coverage Gaps

**Real embedding model gated behind `@pytest.mark.slow`:**
- What's not tested: SentenceTransformer model path skipped in `pytest -m "not slow"` runs.
- File: `rosetta/tests/test_embed.py` (line 268+)
- Risk: Embedding dimension changes or model API breaks go undetected in normal CI.
- Priority: Medium — add a mock-model smoke test that runs in standard mode.

**No stdin/stdout pipe integration tests:**
- What's not tested: Unix composability — piping one tool's output into another (e.g., `ingest | embed`, `suggest | lint`).
- Risk: Exit-code contracts or serialization format changes silently break shell pipelines.
- Priority: Medium.

---
*Concerns audit: 2026-04-13*
