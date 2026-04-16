# Codebase Concerns

**Analysis Date:** 2026-04-16  
**Phase:** Post-15 (HEAD c16d82c)

---

## Tech Debt

**rdflib SPARQL row attribute access untyped:**
- Issue: SPARQL query results use dynamic attribute access (`row.subject_id`) that static type checkers cannot verify. Pervasive `# pyright: ignore[reportAttributeAccessIssue]` suppressions.
- Files: `rosetta/core/units.py` (4 suppressions), `rosetta/core/translation.py` (10), `rosetta/core/provenance.py` (7)
- Impact: Silent failures if query column names drift; no IDE autocomplete on result rows
- Fix approach: Wrap rdflib SPARQL results in a typed dataclass at query boundaries

**PROV namespace untyped:**
- Issue: `from rdflib.namespace import PROV` is untyped; all attribute accesses (`PROV.wasGeneratedBy`, etc.) trigger `# type: ignore[attr-defined]`
- Files: `rosetta/core/provenance.py` (8 suppressions), `rosetta/tests/test_provenance.py` (related)
- Impact: No IDE hints; brittle to typos in namespace attribute names
- Fix approach: Create a typed Namespace alias or cast at import; reuse across source and tests

**linkml-runtime fully untyped:**
- Issue: All imports from `linkml_runtime` flagged `# type: ignore[import-untyped]`. ~20 unsuppressed `SchemaDefinition` attr accesses across embedding, translation, features, ingest, translate
- Files: `rosetta/core/embedding.py`, `rosetta/core/translate.py`, `rosetta/core/features.py`, `rosetta/cli/ingest.py`, `rosetta/cli/translate.py`
- Impact: No type safety on schema introspection; CI passes but runtime errors possible on API changes
- Fix approach: Create stub types (`.pyi`) for critical linkml_runtime exports, or add defensive `hasattr` checks

**pyparsing global state mutation without finally:**
- Issue: `normalize_schema()` saves `pyparsing.ParserElement.DEFAULT_WHITE_CHARS` before calling importers (line 193), restores after (line 195), but **NOT in try/finally**. Schema import exception leaves global state corrupted, breaking subsequent rdflib SPARQL in same process.
- Files: `rosetta/core/normalize.py:190–195`
- Impact: First schema import error silently breaks all subsequent embedding/suggest/lint in CLI session
- Fix approach: Wrap dispatch in try/finally; restore whitespace in finally block

**RdfsImportEngine format hardcoded to turtle:**
- Issue: `normalize.py` passes `format="turtle"` unconditionally to all importers, but `.owl`/`.rdf` XML files fail to parse
- Files: `rosetta/core/normalize.py:_dispatch_import()` (line 197 approx.)
- Impact: Non-turtle RDF files silently fail or produce parse errors without helpful diagnostics
- Fix approach: Detect format by file extension; pass `format="xml"` for `.owl`/`.rdf`, `format="turtle"` for `.ttl`

**refurb pre-commit hook false positives:**
- Issue: refurb modernization linter added to CI; may flag legacy/generated code patterns as errors
- Files: `pyproject.toml` (check tool.refurb)
- Impact: Legitimate code patterns may fail CI; watch for over-aggressive suggestions
- Fix approach: Whitelist false positives via `# noqa: E225` etc.; keep baseline of exceptions

---

## Known Limitations

**Audit log file locking missing:**
- Issue: `append_log()` in `rosetta/core/accredit.py:101` has no file lock. Concurrent `rosetta-accredit ingest` calls can race on `path.stat().st_size == 0` header check (TOCTOU). Header duplication possible.
- Symptom: First two concurrent calls both write header if path is empty
- Workaround: Serialize accredit calls via external lock (shell `flock`, systemd socket activation, etc.)

**Embedding model download uncontrolled:**
- Issue: LaBSE embedding model downloads ~1GB at first use; no offline mode or cached-path config flag
- Symptom: First `rosetta-embed` call hangs silently on slow networks; no progress indicator
- Workaround: Pre-download model via `huggingface-hub`, set `HF_HOME` env var

**Unit detection mismatch silent failure:**
- Issue: `detect_unit()` output must match `UNIT_STRING_TO_IRI` key names exactly. Mismatches (e.g., "metre" vs "meter", "dBm" → None) silently skip lint checks without warning
- Symptom: Unit mappings appear valid but don't lint; no error or hint in output
- Workaround: Check `detect_unit()` output manually; cross-reference against QUDT keys in `rosetta/core/units.py`

**SSSOM feedback resorting not automatic:**
- Issue: `apply_sssom_feedback()` in `rosetta/core/similarity.py` adjusts scores but doesn't re-sort output
- Symptom: Top-1 suggestion may not be highest-confidence after feedback applied
- Workaround: Callers must re-sort by confidence column after feedback

---

## Performance Bottlenecks

**QUDT graph reloaded on every lint invocation:**
- Issue: `load_qudt_graph()` in `rosetta/core/units.py` re-parses TTL file on every call; no memoization
- Problem: `rosetta-lint` re-imports QUDT (>1MB) for each field in schema, O(n) file parses
- Cause: No `functools.lru_cache` decorator
- Improvement path: Add `@functools.lru_cache(maxsize=1)` decorator to `load_qudt_graph()`

**Full matrix materialization before top-k ranking:**
- Issue: `rank_suggestions()` in `rosetta/core/similarity.py` builds full (n_source × n_master) cosine-similarity matrix in memory before selecting top-k
- Problem: For 10k source fields × 100k master entries, materializes ~1B floats (~4GB memory)
- Cause: Uses `np.argsort` over full array instead of `np.argpartition` for partial sort
- Improvement path: Use `numpy.argpartition()` for partial sort; avoid full materialization

---

## Fragile Areas

**pyshacl return type cast unvalidated:**
- Issue: `rosetta/cli/validate.py` casts pyshacl return to tuple via `# pyright: ignore[reportAssignmentType]` without runtime assertion
- Risk: If pyshacl API changes, validation silently produces wrong results or exceptions at wrong boundary
- Safe modification: Add `assert len(result) == 3` after cast to validate shape
- Test coverage: Happy-path only; no tests for unexpected return shapes

**Soft breadth penalty fires on every revocation:**
- Issue: `apply_sssom_feedback()` in `rosetta/core/similarity.py` applies 0.25 dampening to all candidates when **any** `owl:differentFrom` row is processed
- Risk: Feedback loop: user rejects candidate → all competitors penalized 0.25 → original rejection re-emerges as top-1
- Safe modification: Gate behind config flag (`--skip-breadth-penalty`); document semantic clearly; default off for Phase 16
- Test coverage: Non-collinear vector case tested; interaction with structural blending untested

**Flat schema structural features near-zero:**
- Issue: `extract_structural_features_linkml()` in `rosetta/core/features.py` returns near-zero vectors for schemas with no `is_a` inheritance (common in flat domains)
- Risk: Cosine similarity becomes noisy when structural component is zero-ish; random matches scored equally
- Safe modification: Detect flat schema (max_depth=0); either skip structural blending or warn and zero-out structural component
- Test coverage: No test of embedding/similarity with zero-inheritance schemas

---

## Phase 14/15 Specific Findings

**Audit log column count frozen at 9:**
- Current: AUDIT_LOG_COLUMNS in `rosetta/core/accredit.py:20–30` defines 9 columns: subject_id, predicate_id, object_id, mapping_justification, confidence, subject_label, object_label, mapping_date, record_id
- Design: Datatype columns (subject_datatype, object_datatype) explicitly EXCLUDED per Phase 15 design decision
- Risk: Phase 16-00 will extend to 13 columns; `_parse_sssom_row()` uses `.get()` defaults for backward compat. Upgrade path not yet defined.
- Files: `rosetta/core/accredit.py:20–30, 42–60`

**Audit log path resolution edge case:**
- Issue: `rosetta/cli/accredit.py` and callers use `is_file()`/`is_dir()` to resolve log path, but no guarantee old and new log paths don't collide
- Risk: Two stores in same directory with overlapping audit log names lead to silent mixing
- Files: `rosetta/cli/accredit.py`
- Fix: Phase 16-00 will namespace audit logs by store ID

**DEFAULT_PREFIX uniqueness not enforced:**
- Issue: LinkML schemas in same store can share DEFAULT_PREFIX; today, second ingest with `--schema-name X` clobbers first
- Risk: Silent data loss; mapping history split across two schemas with same prefix, causing linkml type conflicts
- Priority: **High** — add lint check in Phase 16-00
- Files: `rosetta/core/ingest.py`, `rosetta/cli/ingest.py`

**rdflib import kept after RDF deletion:**
- Issue: Phase 15 deleted RDF mode from `rosetta-lint` but line 7 still imports rdflib. Verify it's not dead code.
- Files: `rosetta/cli/lint.py:7`
- Risk: If unused, unnecessary dependency; if used elsewhere, import may be load-bearing (check for graph/namespace refs)
- Status: Verify via grep for `rdflib.` usage in lint.py; Grep found 0 hits, likely dead code

---

## Test Coverage Gaps

**pyparsing state corruption untested — HIGH PRIORITY:**
- What's missing: No test that verifies `DEFAULT_WHITE_CHARS` restoration on import exception; no test of SPARQL after failed import in same process
- Risk: Importer crash followed by broken SPARQL goes undetected in CI
- Coverage: Add `test_normalize_exception_restores_pyparsing_state()` in `rosetta/tests/test_normalize.py`; follow with SPARQL query

**Real embedding model hidden behind `@pytest.mark.slow` — MEDIUM:**
- What's missing: Fast CI skips embedding API calls via `pytest -m "not slow"`; embedding-model downloader breaks silently
- Risk: Embedding pipeline works locally, fails in production after model or dependency update
- Coverage: Move one embed test to main suite; cache model in CI environment

**Pipe integration across tool boundaries — MEDIUM:**
- What's missing: No tests of e.g. `rosetta-ingest | rosetta-embed | rosetta-suggest` shell chains
- Risk: Tool output format drift (TSV columns, JSON keys) breaks Unix composability without detection
- Coverage: Add `test_pipe_ingest_to_embed()` etc. in integration test suite; validate exit codes and TSV headers

**Flat schema structural features untested — MEDIUM:**
- What's missing: No test of embedding/similarity with zero-inheritance schemas (no `is_a` relationships)
- Risk: Structural blending breaks silently on flat domains; cosine similarity degrades to noise
- Coverage: Add fixture with flat schema; verify structural component is zero or blending is skipped

**Concurrent audit log writers untested — MEDIUM:**
- What's missing: No test of `append_log()` called from two processes simultaneously
- Risk: Race condition undetected until production; header duplication or row interleaving possible
- Coverage: Add `test_accredit_concurrent_append()` with `multiprocessing.Process` or `threading`; verify no duplicates

---

*Concerns audit: 2026-04-16 (GSD codebase mapper)*
