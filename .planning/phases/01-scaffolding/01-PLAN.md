---
phase: 1
plan: 1
title: "Project skeleton, config loader, and RDF utilities"
scope: "pyproject.toml, package structure, rosetta.toml config, Click integration, rdf_utils, pytest harness, synthetic test fixtures"
requirements:
  - REQ-09
  - REQ-10
  - REQ-26
must_haves:
  truths:
    - "Running `uv run rosetta-ingest --help` prints a Click help message (entrypoint works)"
    - "All 8 CLI entrypoints (`rosetta-ingest`, `rosetta-embed`, `rosetta-suggest`, `rosetta-lint`, `rosetta-validate`, `rosetta-rml-gen`, `rosetta-provenance`, `rosetta-accredit`) respond to `--help`"
    - "`rosetta-ingest --help` output includes `--config`, `--input`, `--output`, and `--format` flags"
    - "Running `uv run pytest` discovers and passes at least one test"
    - "`rosetta/core/config.py` loads rosetta.toml from CWD and merges with CLI flags (config file -> env var -> CLI flag precedence)"
    - "`rosetta/core/rdf_utils.py` can round-trip a Graph: load Turtle from file, save as Turtle, reload, and the triples match"
    - "All rosetta-generated RDF uses the `rose:` prefix bound to `http://rosetta.interop/ns/`"
    - "[review] `open_input('-')` reads from stdin and `open_output('-')` writes to stdout without error"
    - "[review] Malformed TOML in rosetta.toml raises a clear error, not a raw traceback"
    - "[review] Invalid RDF in `load_graph` raises a clear error, not a raw rdflib parse exception"
  artifacts:
    - path: pyproject.toml
      provides: project metadata, dependencies, CLI entrypoints
      contains: "[project.scripts]"
    - path: rosetta/__init__.py
      provides: package root
      contains: "__version__"
    - path: rosetta/cli/__init__.py
      provides: CLI subpackage
      contains: ""
    - path: rosetta/cli/ingest.py
      provides: stub Click entrypoint for rosetta-ingest
      contains: "@click.command"
    - path: rosetta/core/__init__.py
      provides: core subpackage
      contains: ""
    - path: rosetta/core/config.py
      provides: TOML config loader with CLI merge
      contains: "load_config"
    - path: rosetta/core/rdf_utils.py
      provides: RDF I/O helpers, namespace bindings
      contains: "ROSE_NS"
    - path: rosetta/core/io.py
      provides: stdin/stdout open helpers
      contains: "open_input"
    - path: rosetta.toml
      provides: default config file
      contains: "[general]"
    - path: rosetta/tests/__init__.py
      provides: test package
      contains: ""
    - path: rosetta/tests/conftest.py
      provides: shared pytest fixtures
      contains: "tmp_graph"
    - path: rosetta/tests/test_rdf_utils.py
      provides: round-trip test for rdf_utils
      contains: "test_roundtrip"
    - path: rosetta/tests/test_io.py
      provides: stdin/stdout I/O helper tests
      contains: "test_open_input_file"
    - path: rosetta/tests/test_config.py
      provides: config loading tests
      contains: "test_load_config"
    - path: store/master-ontology/master.ttl
      provides: synthetic Master Air Defense Ontology (~20 concepts with QUDT units)
      contains: "AirTrack"
    - path: rosetta/tests/fixtures/nor_radar.csv
      provides: Norwegian radar CSV fixture (Norwegian labels, metric units)
      contains: "sporings_id"
    - path: rosetta/tests/fixtures/deu_patriot.json
      provides: German Patriot JSON Schema fixture (German labels, metric units)
      contains: "Ziel_ID"
    - path: rosetta/tests/fixtures/usa_c2.yaml
      provides: US C2 OpenAPI fixture (English labels, imperial/nautical units)
      contains: "track_number"
  key_links:
    - from: pyproject.toml
      to: rosetta/cli/ingest.py
      via: "[project.scripts] entrypoint"
    - from: rosetta/cli/ingest.py
      to: rosetta/core/config.py
      via: "import load_config"
    - from: rosetta/core/rdf_utils.py
      to: rosetta/core/config.py
      via: "namespace URI from config (optional)"
    - from: rosetta/tests/conftest.py
      to: rosetta/core/rdf_utils.py
      via: "import for fixture creation"
---

# Plan 01: Project Skeleton, Config Loader, and RDF Utilities

## Task 1: pyproject.toml + package structure

Create the foundational project files.

**Do:**
- Create `pyproject.toml` with:
  - `[project]` metadata (name=rosetta-cli, version=0.1.0, python>=3.11)
  - Dependencies: rdflib, click, pyyaml (use `import tomllib` from stdlib — no third-party TOML dep needed for Python 3.11+)
  - Dev dependencies: pytest
  - `[project.scripts]`: `rosetta-ingest = "rosetta.cli.ingest:cli"` (plus stubs for other tools)
  - `[build-system]` with hatchling or setuptools
- Create directory structure with `__init__.py` files:
  - `rosetta/__init__.py` (with `__version__ = "0.1.0"`)
  - `rosetta/cli/__init__.py`
  - `rosetta/core/__init__.py`
  - `rosetta/policies/` (empty dir with `.gitkeep`)
  - `rosetta/store/` (empty dir with `.gitkeep`)
  - `rosetta/tests/__init__.py`
- Run `uv sync` to install

**Done when:**
- `uv run python -c "import rosetta; print(rosetta.__version__)"` prints `0.1.0`

---

## Task 2: rosetta.toml + config loader

Implement the config system (REQ-09).

**Do:**
- Create `rosetta.toml` with default config:
  ```toml
  [general]
  store_path = "store"
  default_format = "turtle"

  [namespaces]
  rose = "http://rosetta.interop/ns/"
  rose_stats = "http://rosetta.interop/ns/stats/"

  [embed]
  model = "sentence-transformers/LaBSE"
  mode = "lexical-only"
  ```
- Create `rosetta/core/config.py`:
  - `load_config(config_path: Path | None = None) -> dict` — loads from given path or CWD/rosetta.toml, returns empty dict if not found
  - `get_config_value(config: dict, section: str, key: str, cli_value=None, env_prefix="ROSETTA")` — implements 3-tier precedence: config file -> env var -> CLI flag (CLI wins). Env var name derived as `{env_prefix}_{SECTION.upper()}_{KEY.upper()}` (e.g., `ROSETTA_EMBED_MODEL`)
- Create `rosetta/tests/test_config.py`:
  - `test_load_config` — loads a tmp rosetta.toml
  - `test_cli_overrides_config` — verifies CLI value beats config file value
  - `test_env_overrides_config` — verifies env var beats config file value (e.g., `ROSETTA_EMBED_MODEL`)
  - `test_missing_config_returns_empty` — no file = empty dict
  - `test_load_config_malformed_toml` — malformed TOML raises a clear error, not a raw `tomllib.TOMLDecodeError` traceback

**Done when:**
- `uv run pytest rosetta/tests/test_config.py` passes all 3 tests

---

## Task 3: RDF utilities + namespace management

Implement the shared RDF I/O layer.

**Do:**
- Create `rosetta/core/rdf_utils.py`:
  - `ROSE_NS = Namespace("http://rosetta.interop/ns/")`
  - `ROSE_STATS_NS = Namespace("http://rosetta.interop/ns/stats/")`
  - `bind_namespaces(g: Graph) -> Graph` — binds `rose:`, `rose-stats:`, `qudt:`, `prov:`, `skos:` prefixes
  - `load_graph(path: Path | TextIO, fmt: str = "turtle") -> Graph` — loads RDF, binds namespaces
  - `save_graph(g: Graph, path: Path | TextIO, fmt: str = "turtle") -> None` — serializes with bound prefixes
  - `query_graph(g: Graph, sparql: str) -> list[dict]` — convenience SPARQL SELECT wrapper
- Create `rosetta/tests/test_rdf_utils.py`:
  - `test_roundtrip` — create graph with rose: triples, save to turtle, reload, assert triples match
  - `test_bind_namespaces` — verify all expected prefixes are bound
  - `test_query_graph` — insert triples, query them back
  - `test_load_graph_invalid_rdf` — invalid RDF input raises a clear error, not a raw rdflib parse exception

**Done when:**
- `uv run pytest rosetta/tests/test_rdf_utils.py` passes all 3 tests

---

## Task 4: I/O helpers + Click stub entrypoint

Wire up the CLI with stdin/stdout support (REQ-10).

**Do:**
- Create `rosetta/core/io.py`:
  - `open_input(path: str | None) -> ContextManager[TextIO]` — returns stdin if path is None or `-`, else opens file for reading
  - `open_output(path: str | None) -> ContextManager[TextIO]` — returns stdout if path is None or `-`, else opens file for writing
- Create `rosetta/cli/ingest.py`:
  - A Click command stub with `--input`, `--output`, `--format`, `--nation`, `--config` options
  - Loads config via `load_config`, prints "Not yet implemented" for the actual logic
  - The `--config` option uses `load_config(path)` to load from a custom path
- Create stubs for all other CLI entrypoints (single-line Click commands that print "Not yet implemented"):
  - `rosetta/cli/embed.py` → `rosetta-embed`
  - `rosetta/cli/suggest.py` → `rosetta-suggest`
  - `rosetta/cli/lint.py` → `rosetta-lint`
  - `rosetta/cli/validate.py` → `rosetta-validate`
  - `rosetta/cli/rml_gen.py` → `rosetta-rml-gen` (underscore in filename, hyphen in script name)
  - `rosetta/cli/provenance.py` → `rosetta-provenance`
  - `rosetta/cli/accredit.py` → `rosetta-accredit`
  - Each stub must accept `--config` and `--help` flags at minimum
- Create `rosetta/tests/conftest.py`:
  - `tmp_graph` fixture — returns a fresh Graph with namespaces bound
  - `sample_ttl` fixture — writes a small TTL file to tmp_path and returns the path
  - `config_dir` fixture — writes a rosetta.toml to tmp_path and returns the directory
- Create `rosetta/tests/test_io.py`:
  - `test_open_input_file` — reads from a tmp file
  - `test_open_input_stdin` — `open_input('-')` returns stdin without error
  - `test_open_output_stdout` — `open_output('-')` writes to stdout without error

**Done when:**
- All 8 entrypoints respond to `uv run rosetta-<tool> --help`
- `uv run pytest` discovers and passes all tests (config + rdf_utils + io)

---

## Task 5: Verify end-to-end + clean up

Final integration check.

**Do:**
- Run `uv run pytest` — all tests pass
- Run `uv run rosetta-ingest --help` — confirm entrypoint works
- Run `uv run rosetta-embed --help` — confirm stub works
- Verify `rosetta.toml` is loadable from CWD
- Check that the `rose:` namespace appears in any saved TTL output
- Fix any issues found

**Done when:**
- All tests pass, all 8 entrypoints respond to `--help`, config loads from CWD

---

## Task 6: Synthetic test fixtures (REQ-26)

Create the static test data that all downstream phases depend on.

**Do:**
- Create `store/master-ontology/master.ttl`:
  - ~20 concepts from the PLAN.md Test Data section: AirTrack (Altitude_MSL, Altitude_AGL, Heading, Speed, Range, Bearing, Latitude, Longitude, Timestamp, Track_ID, Classification), RadarReturn (Signal_Strength, Cross_Section, Doppler_Shift), EngagementZone (Min_Range, Max_Range, Min_Altitude, Max_Altitude)
  - Each attribute annotated with QUDT unit, rdfs:label, rdfs:comment
  - Uses `rose:` namespace per GA-2
- Create `rosetta/tests/fixtures/nor_radar.csv`:
  - Headers: `sporings_id, breddegrad, lengdegrad, hoyde_m, kurs_grader, hastighet_kmh, avstand_km, peiling_grader, tidsstempel, klassifisering, signalstyrke_dbm`
  - 5-10 rows of synthetic data with realistic values
- Create `rosetta/tests/fixtures/deu_patriot.json`:
  - JSON Schema with German field names per PLAN.md: Ziel_ID, Breite, Laenge, Hoehe_Meter, Kurs, Geschwindigkeit_ms, Entfernung_km, Zeitstempel, Bedrohungsstufe
- Create `rosetta/tests/fixtures/usa_c2.yaml`:
  - OpenAPI spec with English labels per PLAN.md: track_number, lat_dd, lon_dd, altitude_ft, course_deg, speed_kts, range_nm, timestamp_z, id_status
- Create `store/national-schemas/` directory with `.gitkeep`
- Create `store/accredited-mappings/` directory with `.gitkeep`

**Done when:**
- `master.ttl` loads with rdflib without errors and contains >= 20 attribute nodes
- All 3 national schema fixtures are valid in their respective formats (CSV parseable, JSON valid, YAML valid)
- `store/` directory structure is in place for downstream phases
