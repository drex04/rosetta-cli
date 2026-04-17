---
plan: 16-03
title: morph-kgc runner + JSON-LD framing + E2E
date: 2026-04-17
---

# Plan 16-03 Design — morph-kgc Runner + JSON-LD Framing + E2E

## Goal

Close the Phase 16 pipeline by executing the YARRRML produced by the fork's `YarrrmlCompiler` against real source data via `morph-kgc`, framing the resulting N-Triples graph as JSON-LD using a context derived from the master schema, and proving it end-to-end with a slow integration test.

## Primary approach (locked)

Fully in-process orchestration. `rosetta-yarrrml-gen --run` composes:

```
SSSOM → build_spec() → YarrrmlCompiler.compile(spec)
      → rml_runner.run_materialize(yarrrml, data_file, work_dir) → rdflib.Graph
      → rml_runner.graph_to_jsonld(graph, master_schema) → bytes
      → stdout or --jsonld-output
```

## Rejected alternative

Subprocess pipeline (`linkml-tr compile yarrrml | morph-kgc`): rejected because `morph_kgc.materialize()` returns a live `rdflib.Graph` exactly matching the framing step's input. Serializing and re-parsing at a process boundary is waste, and the integration tests already import `YarrrmlCompiler` in-process.

## Locked gray-area decisions

| # | Decision |
|---|----------|
| GA-03-1 | Config as INI **string** built via `configparser` + `StringIO`; YARRRML written to `work_dir/mapping.yml` (real file — morph-kgc reads by path from the INI). |
| GA-03-2 | Data-file binding: fork's YARRRML emits `$(DATA_FILE)` placeholder; runner substitutes via string replace before writing. Single-source; multi-source deferred. |
| GA-03-3 | JSON-LD context generated in-process via `linkml.generators.jsonldcontextgen.ContextGenerator(master_schema).serialize()`. `--context-output` writes the generated context JSON for inspection. |
| GA-03-4 | `--run` stdout: JSON-LD to stdout when no `--jsonld-output`; to file when both. Without `--run`, CLI emits TransformSpec YAML (unchanged). Exit 1 on any morph-kgc error; no partial output. |
| GA-03-5 | E2E fixture: synthesize 3-row `nor_radar_sample.csv`; reuse existing `nor_radar.linkml.yaml` + `master_cop.linkml.yaml`. Slow test asserts JSON-LD parses, `@context` roots master default_prefix, ≥1 typed instance, one unit-converted field. |
| GA-03-6 | No new Pydantic output model — JSON-LD is standard. `CoverageReport` unchanged. Any internal dataclasses keep `extra="forbid"`. |
| GA-03-7 | Runner module split: two public fns (`run_materialize`, `graph_to_jsonld`) + private helpers (`_build_ini`, `_substitute_data_path`, `_generate_jsonld_context`). Keeps radon grade ≤ B per function. |
| GA-03-8 | `work_dir`: default to `tempfile.mkdtemp()` cleaned at exit; `--workdir PATH` overrides for debugging (artifacts retained). |
| GA-03-9 | YARRRML written to `.yml` on disk before morph-kgc invocation; morph-kgc detects YARRRML by extension. |

## API pre-flight (verified)

- `morph_kgc.materialize(config, python_source=None)` — accepts INI string **or** path; returns `rdflib.Graph`. **[verified live on 2.10]**
- morph-kgc accepts YARRRML directly: `mappings: /path/to/file.yml`. **[verified — readthedocs]**
- `linkml.generators.jsonldcontextgen.ContextGenerator(schema).serialize()` → context JSON string. **[verified live via import]**

## Must-haves

**Truths:**
1. `rosetta-yarrrml-gen --sssom A --source-schema S --master-schema M --data D --run` writes JSON-LD to stdout rooted at the master schema's `@context`.
2. JSON-LD contains ≥1 typed instance for every source class with a resolved `skos:exactMatch`/`skos:closeMatch` in the filtered audit log.
3. A linear unit-converted slot (e.g., m→ft) shows the converted numeric value in the JSON-LD output.
4. On any morph-kgc error, CLI exits 1 with error on stderr; no partial JSON-LD is written.
5. `--run` without `--data` exits 1 with a clear error before invoking morph-kgc.
6. The README's `rosetta-yarrrml-gen` section documents the `--run` pipeline with a worked example.
7. Without `--run`, CLI behavior is unchanged from 16-01/16-02.

**Artifacts:**
- `rosetta/core/rml_runner.py` — new module, provides `run_materialize` + `graph_to_jsonld`.
- `rosetta/cli/yarrrml_gen.py` — adds `--run`, `--data`, `--jsonld-output`, `--workdir`, `--context-output`.
- `rosetta/tests/test_rml_runner.py` — unit tests for runner helpers + small inline YARRRML.
- `rosetta/tests/test_yarrrml_run_e2e.py` (slow) — NOR-CSV → JSON-LD full pipeline.
- `rosetta/tests/fixtures/nor_radar_sample.csv` — 3-row E2E input.
- `pyproject.toml` — `morph-kgc>=2.10` pinned at resolved version.
- `README.md` — `rosetta-yarrrml-gen` section rewritten for the `--run` pipeline.

**Key links:**
- `yarrrml_gen.py` → imports `YarrrmlCompiler` (fork) + `rml_runner.run_materialize` + `rml_runner.graph_to_jsonld`.
- `rml_runner.py` → imports `morph_kgc`, `rdflib`, `linkml.generators.jsonldcontextgen.ContextGenerator`.
- E2E → invokes CLI via `click.testing.CliRunner`.

## Failure modes

| Mode | Detection | Recovery |
|------|-----------|----------|
| morph-kgc raises (bad YARRRML, unreadable CSV, FnML error) | try/except around `materialize()` | exit 1; stderr message; no stdout JSON-LD |
| `--data` file missing / unreadable | `click.Path(exists=True, dir_okay=False)` | Click-generated exit 2 |
| master schema JSON-LD context generation fails | try/except around `ContextGenerator.serialize()` | exit 1; stderr message |
| `$(DATA_FILE)` placeholder missing in YARRRML | detect pre-substitution; fail fast | exit 1; stderr "compiler produced YARRRML without $(DATA_FILE) placeholder" |
| `--run` without `--data` | validator before runner invocation | exit 1; stderr "--run requires --data" |
| `--workdir` exists but not writable | `Path.touch()` probe | exit 1; stderr message |

## Scope boundaries

**In scope:** single-source YARRRML execution, N-Triples → JSON-LD compaction via master-schema context, `--run` CLI orchestration, E2E test.

**Out of scope:**
- `--frame` (JSON-LD framing mode) — deferred per Phase 16 CONTEXT.
- Multi-source YARRRML (multiple data files) — deferred.
- Python-UDF unit conversion (non-linear) — GREL only per 16-02 decisions.
- Upstream PR to morph-kgc — n/a, no morph-kgc changes.
