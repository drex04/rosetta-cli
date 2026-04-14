# Codebase Concerns

**Analysis Date:** 2026-04-14

## Tech Debt

**rdflib SPARQL row access — pervasive pyright suppression:**
- Issue: Every `.attribute` access on SPARQL result rows requires `# pyright: ignore[reportAttributeAccessIssue]` because rdflib rows are untyped.
- Files: `rosetta/core/units.py` (lines 142-147), `rosetta/cli/lint.py` (line 80), `rosetta/core/rdf_utils.py` (line 96)
- Impact: Attribute name typos go undetected; type errors silenced wholesale.
- Fix approach: Wrap `query_graph()` return in a typed helper that unpacks rows by variable name into a typed dict.

**prov namespace — 8 `type: ignore` suppressions in one module:**
- Issue: Every PROV triple addition requires `# type: ignore[attr-defined]` because the PROV namespace is untyped.
- Files: `rosetta/core/provenance.py` (lines 89-98), `rosetta/tests/test_provenance.py` (lines 68-90)
- Impact: Masks namespace bugs; duplicates suppression across source and tests.
- Fix approach: Define `PROV = Namespace("http://www.w3.org/ns/prov#")` as a typed local, or cast once at module level.

**linkml-runtime fully untyped — pervasive suppression in v2 additions:**
- Issue: All `linkml_runtime` imports carry `# type: ignore[import-untyped]`; every `SchemaDefinition` attribute access requires `# pyright: ignore[reportAttributeAccessIssue]`.
- Files: `rosetta/core/embedding.py`, `rosetta/core/translation.py`, `rosetta/cli/embed.py`, `rosetta/cli/ingest.py`, `rosetta/cli/translate.py`
- Impact: Silent breakage if linkml-runtime changes field names; ~20 unsuppressed call sites.
- Fix approach: Add a `linkml_runtime.pyi` stub or runtime attribute checks via `hasattr`.

**pyparsing whitespace restore not in `try/finally`:**
- Issue: `normalize_schema` saves/restores `pyparsing.ParserElement.DEFAULT_WHITE_CHARS` around importer calls, but the restore is not in a `finally` block.
- File: `rosetta/core/normalize.py` (lines 109, 204)
- Impact: An importer exception leaves the process pyparsing state broken, corrupting subsequent SPARQL queries in the same process.
- Fix approach: Wrap the restore in `try/finally`.

**RdfsImportEngine hardcoded to `format="turtle"`:**
- Issue: `.owl` and `.rdf` extensions route to the `rdfs` importer but it is always called with `format="turtle"`.
- File: `rosetta/core/normalize.py` (line 197)
- Impact: OWL/RDF XML files produce a parse error with no helpful message.
- Fix approach: Detect RDF/XML by extension and pass `format="xml"`.

## Known Limitations

**Accreditation ledger has no concurrency protection:**
- Symptoms: Simultaneous `rosetta-accredit submit` calls on the same `ledger.json` can lose updates (read-modify-write without a lock).
- File: `rosetta/core/accredit.py` (`load_ledger` / `save_ledger`)
- Workaround: Use only in single-writer pipelines; avoid parallel CI jobs writing the same ledger.

**Embedding model downloads at first use (~1 GB):**
- Symptoms: First `rosetta-embed` run downloads LaBSE from HuggingFace with no offline/cached-path config option.
- File: `rosetta/core/embedding.py` (line 95)
- Workaround: Pre-seed `~/.cache/huggingface` or set `HF_HUB_OFFLINE=1` after seeding.

**`UNIT_STRING_TO_IRI` key contract is implicit:**
- Symptoms: Lint silently skips unit checks if `detect_unit()` output doesn't exactly match a key (e.g., `"metre"` vs `"meter"`).
- Files: `rosetta/core/units.py`, `rosetta/core/unit_detect.py`
- Workaround: Keep `detect_unit()` output and map keys synchronized manually.

**SSSOM feedback does not re-sort after score adjustment:**
- Symptoms: `apply_sssom_feedback()` adjusts scores but does not re-sort; boosted candidates may rank below unboosted ones in TSV output.
- File: `rosetta/core/similarity.py` (lines 111-159), `rosetta/cli/suggest.py` (line 159)
- Workaround: Consumers should re-sort by `confidence` column after loading the TSV.

## Performance Bottlenecks

**QUDT graph loaded fresh on every lint invocation:**
- Problem: `load_qudt_graph()` parses large TTL files on every call with no module-level cache.
- File: `rosetta/cli/lint.py` (line 126), `rosetta/core/units.py` (line 38)
- Cause: No memoization; `importlib.resources` read on every invocation.
- Improvement path: Apply `functools.lru_cache(maxsize=1)` to `load_qudt_graph()`.

**Full similarity matrix computed before top-k filter:**
- Problem: `rank_suggestions()` materialises an (n_src × n_master) float32 matrix before filtering to top_k.
- File: `rosetta/core/similarity.py` (line 49)
- Cause: `np.argsort` over full rows; O(n log n) when O(n) via `np.argpartition` is sufficient.
- Improvement path: Replace `np.argsort` with `np.argpartition` for top_k selection; for >10k master nodes consider `faiss` ANN.

## Fragile Areas

**pyshacl return-type cast silences shape changes:**
- Why fragile: `pyshacl.validate()` result is force-cast via `# pyright: ignore[reportAssignmentType]`; if pyshacl changes return shape, the cast silently misassigns.
- File: `rosetta/cli/validate.py` (line 96)
- Safe modification: Add `assert len(pyshacl_result) == 3` after the call.
- Test coverage: Happy-path only; no tests for unexpected return shapes.

**`apply_sssom_feedback` soft breadth penalty always fires:**
- Why fragile: Any `owl:differentFrom` row for a subject causes ALL other candidates to receive `penalty * 0.25` derank, changing every score for that subject.
- File: `rosetta/core/similarity.py` (lines 144-146)
- Safe modification: Gate breadth penalty behind a config flag; document the semantic explicitly.
- Test coverage: Non-collinear vector case covered; interaction with `apply_ledger_feedback` is untested.

## Test Coverage Gaps

**`normalize_schema` exception paths:**
- What's not tested: Importer exceptions (malformed input); pyparsing global state after an import failure.
- Risk: Broken pyparsing state corrupts subsequent SPARQL calls in the same process silently.
- Priority: High

**Real embedding model gated behind `@pytest.mark.slow`:**
- What's not tested: SentenceTransformer model path skipped in `pytest -m "not slow"` runs.
- File: `rosetta/tests/test_embed.py`
- Risk: Embedding dimension changes or model API breaks go undetected in normal CI.
- Priority: Medium

**No stdin/stdout pipe integration tests:**
- What's not tested: Unix composability — piping one tool's output into another (e.g., `ingest | embed`, `suggest | lint`).
- Risk: Exit-code contracts or serialization format changes silently break shell pipelines.
- Priority: Medium

---
*Concerns audit: 2026-04-14*
