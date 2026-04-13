# Codebase Concerns

**Analysis Date:** 2026-04-13

## Tech Debt

**Broad exception catching in CLI commands:**
- Issue: `embed.py` line 54 and `suggest.py` line 62 catch all exceptions generically, obscuring real error sources
- Files: `rosetta/cli/embed.py`, `rosetta/cli/suggest.py`
- Impact: User receives unhelpful error messages; silent failures in data pipelines
- Fix approach: Catch specific exceptions (ValueError, IOError, OSError) and re-raise with context

**Silent failure in unit detection:**
- Issue: `unit_detect.py` lines 84-85 catch parsing errors and continue silently with `pass`
- Files: `rosetta/core/unit_detect.py`
- Impact: Malformed numeric values silently fall through to categorical stats; no indication of parse failures
- Fix approach: Log warnings or track parse failures; distinguish between "not numeric" and "parse error"

**Model loading performance:**
- Issue: `EmbeddingModel` loads sentence-transformer on every instantiation; no singleton or caching
- Files: `rosetta/core/embedding.py` lines 83-86
- Impact: Each `rosetta-embed` invocation incurs multi-second model load overhead; blocks in pipes
- Fix approach: Implement lazy global model cache or singleton pattern; consider process-level caching

## Known Limitations

**Embedding mode hardcoded:**
- Symptoms: Only `lexical-only` mode works; other modes show warning but still use lexical
- File: `rosetta/cli/embed.py` lines 27-31
- Workaround: Ignore `--mode` flag, always use lexical embeddings; config.mode is vestigial

**URI path segment parsing fragile:**
- Symptoms: Master schema slug extracted via hardcoded split on `/` (second-to-last segment)
- File: `rosetta/core/embedding.py` line 60
- Workaround: Keep URI structure rigid with exactly 2 path segments before final slash

**Unit string not in UNIT_STRING_TO_IRI:**
- Symptoms: Lint silently skips unit checks if detected unit doesn't match key exactly
- File: `rosetta/cli/lint.py` line 153, `rosetta/core/units.py` lines 19-27
- Workaround: Ensure `detect_unit()` returns only keys from UNIT_STRING_TO_IRI mapping (memory: "metre" vs "meter")

## Security Considerations

**SPARQL injection via unvalidated unit strings:**
- Risk: Unit string detected from field metadata fed into SPARQL query without escaping
- Files: `rosetta/cli/lint.py` lines 150, 187 (initBindings with URIRef coercion)
- Current mitigation: rdflib URIRef coercion implicitly escapes; binding uses initBindings not string interp
- Recommendations: Add unit string validation against UNIT_STRING_TO_IRI before query; add type hints

**RDF parsing from untrusted sources:**
- Risk: `rdflib.Graph.parse()` can load remote RDF (XXE, denial of service)
- Files: `rosetta/core/rdf_utils.py` line 52, `rosetta/cli/lint.py` lines 96-100
- Current mitigation: Local file I/O only; no remote URL support in CLI
- Recommendations: Add security note in comments; reject `http://` URIs in file paths

## Performance Bottlenecks

**Cosine similarity matrix computed fully:**
- Problem: `rank_suggestions()` computes full (n_src × n_master) similarity matrix, then filters top_k
- File: `rosetta/core/similarity.py` lines 48, 58
- Cause: Uses np.argsort on full row; no early-exit or heap-based selection
- Improvement path: Use numpy.partition or heapq for top_k selection; scales O(n_master) instead of O(n_master log n_master)

**QUDT graph loaded on every lint invocation:**
- Problem: `load_qudt_graph()` parses large TTL files (qudt_units.ttl + fnml_registry.ttl) on each call
- File: `rosetta/cli/lint.py` line 107
- Cause: No module-level caching; importlib.resources read() every time
- Improvement path: Lazy-load at module scope; memoize or use functools.cache

## Fragile Areas

**JSON embedding format validation:**
- Why fragile: Checks for 'lexical' key only after reading all embeddings into memory
- Files: `rosetta/cli/suggest.py` lines 43-45, 49-51
- Safe modification: Validate format on first embedding before np.array allocation; fail fast
- Test coverage: No tests for missing 'lexical', empty embedding arrays, or dimension mismatches

**Configuration value type coercion:**
- Why fragile: `suggest.py` lines 26-30 call int()/float() on config values without validation
- Files: `rosetta/cli/suggest.py`
- Safe modification: Add try/except with human-readable error; validate in load_config before use
- Test coverage: No tests for non-numeric config values (e.g. ROSETTA_SUGGEST_TOP_K="abc")

**SPARQL query results assumed non-null:**
- Why fragile: `_sparql_one()` line 73 assumes `row[0]` exists without guarding `row is not None or len(row) > 0`
- Files: `rosetta/cli/lint.py`
- Safe modification: Check result count and field count before indexing; return None explicitly
- Test coverage: No tests for empty SPARQL results or malformed bindings

## Test Coverage Gaps

**Error path testing:**
- What's not tested: Malformed RDF, invalid JSON embeddings, missing config files, SPARQL errors
- Risk: Silent failures in data pipelines; users unaware of corrupt intermediate files
- Priority: High

**Unit detection edge cases:**
- What's not tested: Unicode field names, mixed-case variations, partial matches (e.g. "meter" in "speedometer")
- Risk: Inconsistent unit detection across real data
- Priority: Medium

**Config and environment variable precedence:**
- What's not tested: Env var override behavior, missing sections, type coercion edge cases
- Risk: Production configs behave differently than development
- Priority: Medium

---
*Concerns audit: 2026-04-13*
