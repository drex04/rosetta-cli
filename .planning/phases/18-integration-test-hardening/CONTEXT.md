# Phase 18: Integration & E2E Test Hardening — Context

## Locked Decisions

### D-18-01: Fixture directory layout
**Decision:** Three subdirectories under `rosetta/tests/fixtures/`:
- `nations/` — existing NOR/DEU/USA fixtures (migrated in 18-01)
- `stress/` — new complex positive-path fixtures (deeply nested JSON Schema, complex XSD, CSV edge cases, LinkML inheritance)
- `adversarial/` — committed malformed fixtures for rich negative cases

Separately, **test files** (not fixtures) live under `rosetta/tests/{integration, adversarial, smoke}/`. The `adversarial/` subdir appears in BOTH `fixtures/` (malformed inputs) and `tests/` (negative-path tests). This is intentional — fixtures and their consumers are clustered by the same semantic tag.

**Why:** Flat `fixtures/` is 9 files today; adding 15+ more would make the directory unreadable. Subdirs cluster by intent so a reviewer can find "the bad inputs" or "the stress inputs" at a glance.

**How to apply:** All integration/adversarial tests reference fixtures via pytest fixtures exposed from `conftest.py` (e.g. `nor_csv_path`, `nested_json_schema_path`). Call sites never hardcode `rosetta/tests/fixtures/...` paths.

### D-18-02: Adversarial fixture strategy — hybrid
**Decision:** Two styles, chosen per case:
- **Inline** (`tmp_path.write_text(...)`) — for simple mutations: truncation, wrong column count, missing required field, bad JSON bracket.
- **Committed file** (under `fixtures/adversarial/`) — for rich complex examples: deeply nested JSON Schema with `$ref` + `oneOf` breakage, complex XSD with broken `<xs:choice>` nesting.

**Why:** Inline keeps simple tests self-documenting — the bad bytes live in the test. Committed files are needed when the fixture is too large to inline-read but should be greppable and reproducible.

**How to apply:** If the malformed input fits in ≤10 lines of source, build it inline with `tmp_path`. Otherwise commit under `fixtures/adversarial/<case>.{ext}` and expose via `conftest.py`.

### D-18-03: Marker semantics (composable)
**Decision:** Three markers, composable:
- `integration` — multi-component in-process test via `CliRunner`; asserts behavior across ≥2 tools or one tool + its core helpers.
- `e2e` — full pipeline, typically includes materialization (morph-kgc, RDF generation) or subprocess invocation. Usually also `@slow`.
- `slow` — wall-clock >1s (existing meaning preserved).

Tests compose markers freely (e.g. `@pytest.mark.integration @pytest.mark.slow @pytest.mark.e2e`).

**Why:** Layered semantics let developers pick subsets by intent ("I'm iterating on the CLI layer — run integration + not e2e") without the tag explosion of per-feature markers.

**How to apply:** Declare all three in `[tool.pytest.ini_options].markers` in `pyproject.toml`. Retag the existing 3 integration tests. README documents selection examples.

### D-18-04: CI runs full suite including slow + e2e
**Decision:** The default CI job drops `-m "not slow"` and runs everything. A second fast-gate job runs `-m "not slow and not e2e"` for PR feedback speed (<1 min target).

**Why:** User's explicit preference — "run all tests in CI including slow and e2e" — because integration/e2e drift undetected is the primary risk this phase addresses. A fast-gate job preserves PR iteration speed without sacrificing coverage.

**How to apply:** Update `.github/workflows/ci.yml` — keep the existing `pytest` step unmodified but remove the `-m "not slow"` selector (or change it to unrestricted `pytest`). Add a second job `fast-gate` that runs the constrained selector.

### D-18-05: `rosetta-translate` coverage via DeepL mocks (10 tests, $0 in credits)
**Decision:** Use `monkeypatch.setattr("deepl.Translator.translate_text", fake)` — the pattern already proven in `test_translate.py`. Add a reusable `fake_deepl` pytest fixture in `conftest.py` that accepts either a `{original: translated}` dict or an exception to raise.

**Why:** DeepL credits cost money; live calls are flaky in CI. The existing unit tests already mock successfully, so the machinery exists — we're just generalizing it into a fixture.

**How to apply:**
- 4 positive-path tests in 18-02 (DE→EN, FR→EN, batch-size, mixed-language)
- 6 error-path tests in 18-03 (auth fail, quota, transient, missing key + non-EN, EN passthrough without key, empty schema)

### D-18-06: Subprocess smoke tests (included)
**Decision:** Two subprocess smoke tests under `rosetta/tests/smoke/test_entry_points.py`, both marked `@pytest.mark.slow @pytest.mark.e2e`:
- `subprocess.run(["rosetta-ingest", "--help"])` → exit 0, stdout contains "Normalise a schema file"
- `subprocess.run(["rosetta-yarrrml-gen", "--help"])` → exit 0, stdout mentions `--sssom` and `--run`

**Why:** User's explicit preference. Catches packaging regressions (entry-point renames, console-script breakage in `pyproject.toml`) that `CliRunner` cannot.

**How to apply:** Use `shutil.which("rosetta-ingest")` first to detect the installed script; skip with `pytest.skip` if not installed (dev-only installs via `uv sync` will have it). `check=False`; assert `returncode == 0`.

### D-18-07: Default invocation is `CliRunner`, not subprocess
**Decision:** All integration tests invoke via `click.testing.CliRunner` unless testing entry-point installation (the two smoke tests) or a subprocess-only behavior.

**Why:** CliRunner is 10-20× faster, gives real tracebacks, and is easier to debug. Subprocess is reserved for cases where entry-point resolution or OS-level behavior is the subject under test.

**How to apply:** Import `from click.testing import CliRunner` and the CLI's `cli` object; call `CliRunner(mix_stderr=False).invoke(cli, [...])`. Assert on `result.exit_code`, `result.stdout`, `result.stderr`.

### D-18-08: Every integration test asserts three things
**Decision:** Every new integration test asserts at minimum:
1. **Exit code** (0 for happy path, 1 for error path)
2. **Structured output shape** — parse stdout/output file through the appropriate Pydantic model (`LintReport`, `SuggestionReport`, etc.) when applicable; or `rdflib.Graph` parse for RDF outputs
3. **One behavioral invariant** — a concrete assertion about what the output should contain (e.g., "≥ 1 row has `mapping_justification=semapv:ManualMappingCuration`")

**Why:** Tests that only check "didn't crash" are low-value. Three-level assertion forces the test to encode *what the tool is supposed to do*, not just that it ran.

**How to apply:** Plan-check step 6 will fail any integration test that lacks all three assertions.

## Bounded Context (files touched by Phase 18)

**Added:**
- `rosetta/tests/integration/` (new directory with ~10 files)
- `rosetta/tests/adversarial/` (new directory with ~8 files)
- `rosetta/tests/smoke/test_entry_points.py` (new)
- `rosetta/tests/fixtures/nations/` (reorg of existing fixtures)
- `rosetta/tests/fixtures/stress/` (4 new complex fixtures)
- `rosetta/tests/fixtures/adversarial/` (3-5 committed malformed fixtures)

**Modified:**
- `pyproject.toml` (markers declaration)
- `rosetta/tests/conftest.py` (fixture-path fixtures + `fake_deepl`)
- `rosetta/tests/test_accredit_integration.py` (marker retag + fixture-path migration)
- `rosetta/tests/test_yarrrml_compile_integration.py` (marker retag + fixture-path migration)
- `rosetta/tests/test_yarrrml_run_e2e.py` (marker retag + fixture-path migration)
- `.github/workflows/ci.yml` (CI job changes)
- `README.md` ("Running tests" section)

**Unchanged:** All production code under `rosetta/core/` and `rosetta/cli/`. Phase 18 is additive; zero runtime behavioral change.

## Dependencies

- Phase 17 complete ✓ (unit-detect is the last production phase; Phase 18 tests exercise it)
- No new Python dependencies required (pytest, rdflib, click already present)
- No new fork pins required

## Out of scope (explicitly deferred)

- Property-based testing (Hypothesis) — could be a future Phase 19
- Performance benchmarks / `pytest-benchmark` — out of scope
- Mutation testing — out of scope
- Coverage ratcheting gates — out of scope; existing `pytest-cov` stays advisory
- Live DeepL integration test behind an opt-in marker — deferred; mocks are sufficient

## Review decisions (plan-review 2026-04-18)

- **[review] D-18-09: LaBSE model is mocked in integration tests.** Tests 1 (`test_embed_on_nested_json`) and 7 (`test_full_chain_json_to_lint`) in 18-02 follow the mock pattern already established in `rosetta/tests/test_embed.py`. CI does not download the 1.2 GB model. Precondition check: grep `test_embed.py` for the mock pattern before writing the integration tests; escalate if the unit-test file doesn't mock.
- **[review] D-18-10: `rosetta-accredit` positive-path coverage added.** A new `test_accredit_pipeline.py` is included in 18-02 (decided in review — initial plan only covered adversarial accredit paths). Three tests: `ingest → approve → status`, `ingest → approve → revoke` lifecycle, `status` on empty log. Closes the zero-positive-coverage gap flagged by engineering review.
- **[review] D-18-11: Lint rule codes validated against current code.** Only `datatype_mismatch` (cli/lint.py:212) and `unit_dimension_mismatch` (cli/lint.py:171) are asserted. `unit_incompatible` and `missing_required` were in the original plan — both removed; they don't exist. LinkML `required` constraint is a `rosetta-validate` concern, not `rosetta-lint`; covered in 18-02's `test_validate_pipeline.py`.
- **[review] D-18-12: `LintReport.summary.block` is the correct severity field.** `summary.errors` was referenced in the original plan and does not exist on `LintSummary`. All severity assertions now use `block`/`warning`/`info`.
- **[review] D-18-13: Preconditions added for brittle assertions.** Each task block that depends on currently-uncertain stderr strings, rule codes, or exception-routing paths (translate errors, accredit duplicate/derank, lint rule codes) includes an explicit "grep first, assert second" precondition. Writing a test that fails these preconditions is a hard stop requiring the planner's attention.
- **[review] D-18-14: Atomic-commit requirement for 18-01 Tasks 2–5.** The `git mv` fixture relocation, `conftest.py` additions, and integration-test retags form one transition and must be staged together as a single PR. Committing Task 2 alone leaves CI in a transiently broken state.

## Deferred during review (not adopted)

- `rosetta-ingest --format rdfs` and `--format tsv` coverage — accepted as known gap; deferred to a future phase because the scope commitment was HOLD (not EXPANSION).
- `rosetta-provenance query --format json` subcommand coverage — same reasoning.
- Subprocess smoke-test "skip masks packaging regressions" — session-fixture proposal deferred; the current `pytest.skip(f"{name} not installed")` behavior is accepted for developer laptops, and CI uses `uv sync` which always installs the scripts.
- Live-API translate test behind opt-in marker — mocks are sufficient for the scope of Phase 18.
- Session-scoped CI assertion that all console scripts resolve — would catch the skip-masking case but is a tooling change, not a test. Deferred.
