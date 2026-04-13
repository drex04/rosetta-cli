---
phase: 10
name: rosetta-translate
plan: 10-01
status: planning
locked: true
---

# Phase 10 Context: rosetta-translate

## Locked Decisions

### D1: Standalone tool (Approach B)
`rosetta-translate` is a new CLI tool, not a flag on `rosetta-embed`. Translation is an
auditable pre-processing step that produces an output TTL before embedding. The pipeline is:

```
rosetta-ingest → rosetta-translate → rosetta-embed → rosetta-suggest
```

For English source schemas, `rosetta-translate` is still always in the pipeline but is a
clean passthrough — no API call, output TTL is identical in label content.

### D2: Source language via explicit flag
`--source-lang` flag, default `auto`. When `--source-lang EN` (case-insensitive), the tool
skips DeepL entirely and writes the input graph to output unchanged.
Auto-detect mode (`auto`) omits `source_lang` on the DeepL call so DeepL detects it
server-side.

### D3: Dual-label audit trail
When translation occurs, both the original and English label are preserved in the output TTL:
- `rdfs:label` is replaced with the English translation
- `rose:originalLabel` triple is added to each translated field node, preserving the original

No `rose:originalLabel` triples are written in passthrough mode.

### D4: Default embed model → intfloat/e5-large-v2
`rosetta.toml` `[embed].model` updated from `sentence-transformers/LaBSE` to
`intfloat/e5-large-v2`. Rationale: once input is normalized to English via translation,
an English-specialized model outperforms LaBSE which spreads capacity across 109 languages.
The existing `_e5_passage_prefix` support in `embedding.py` handles E5 query/passage prefixes
automatically — no changes to embedding.py needed.

### D5: API key via environment variable only
`DEEPL_API_KEY` env var. Not stored in rosetta.toml (no secrets in config files).
CLI exits 1 with a clear message if the var is unset and `--source-lang` is not `EN`.

### D6: In-memory label deduplication
Unique label strings are collected before the DeepL call. If multiple fields share the same
label text, it is translated once and the result is reused — minimises API character usage
within a single run. No persistent cache between runs.

## Decisions (added in review)

- [review] **EN-passthrough normalised to startswith('EN')**: `source_lang.upper().startswith('EN')`
  catches EN, EN-US, EN-GB, en, etc. without calling DeepL. Exact `== "EN"` match was fragile.

- [review] **zip truncation rescued with assert**: After `translate_text`, assert
  `len(results) == len(unique_texts)` and raise `ValueError` with context if mismatched.
  Prevents silent label loss on partial API results.

- [review] **Idempotency guard**: If any `rose:originalLabel` triple exists in the input graph,
  emit a warning to stderr and exit 0 without re-translating. Prevents audit trail corruption
  on accidental double-run.

- [review] **embedding.py code-level default updated**: `EmbeddingModel.__init__` default
  changed from `"sentence-transformers/LaBSE"` to `"intfloat/e5-large-v2"` alongside
  `rosetta.toml` update. Keeps code and config in sync.

- [review] **scripts updated**: `scripts/full-pipeline.sh` and `scripts/quickstart.sh` added
  to artifact list; both will include the `rosetta-translate` step in their pipeline demos.

- [review] **deepl version pinned to `<2`**: v2 SDK renames `Translator` and `DeepLException`; upper bound prevents silent breakage.

- [review] **CLI uses `--input/-i` / `--output/-o` options**: Changed from positional args to named options to match `embed.py`, `ingest.py`, and all other rosetta tools. Maintains `-i file | tool` composability idiom.

- [review] **embed.py CLI layer patched in Task 6**: The `or "sentence-transformers/LaBSE"` fallback in `embed.py:cli()` is distinct from the `EmbeddingModel` class default. Without patching `embed.py`, absent `rosetta.toml` + no `--model` flag silently produces LaBSE embeddings regardless of `embedding.py` or `rosetta.toml` defaults.

- [review] **Test count raised from 6 to 10**: Added `test_translate_passthrough_source_lang_en_us`, `test_translate_auto_lang_passes_none_to_deepl`, `test_translate_api_error_exits_1`, `test_translate_already_translated_skips`. The 6-test "Done when" criterion was the executor's acceptance gate and would have left idempotency, EN-US passthrough, and API error paths untested.

## Deferred Ideas

- Language tag preservation on `rose:originalLabel` (e.g. `"Zielreichweite"@de` vs plain
  `"Zielreichweite"`): deferred — D3 only requires preserving the text, not the lang tag.
  Revisit if round-trip fidelity becomes a requirement.
- `--format` output option for non-Turtle serialisation: deferred — out of scope for phase 10,
  consistent omission with other tools that don't need it (translate always outputs Turtle).
