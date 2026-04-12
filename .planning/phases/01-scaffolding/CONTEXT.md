# Phase 1 Context: Project Scaffolding and Core Setup

## Locked Decisions

### GA-1: Config file discovery
**Decision:** CWD default + `--config` flag override.
`rosetta.toml` is loaded from the current working directory by default. A `--config PATH` flag on every CLI tool overrides this. No XDG search.
**Rationale:** Simple and predictable for a CLI tool. Users run commands from the project root.

### GA-2: RDF namespace base URI
**Decision:** `http://rosetta.interop/ns/` with `rose:` prefix.
All rosetta-generated RDF uses this namespace for custom predicates and classes. Statistical annotations use `http://rosetta.interop/ns/stats/` with `rose-stats:` prefix.
**Rationale:** User preference. Plausible interoperability-focused namespace.

### GA-3: rdflib Graph interface
**Decision:** Raw rdflib `Graph` objects + helper functions. No wrapper class.
`rdf_utils.py` exposes functions like `load_graph(path)`, `save_graph(graph, path, fmt)`, `bind_namespaces(graph)`.
**Rationale:** Keeps things simple and idiomatic for rdflib users. No unnecessary abstraction layer.

### [review] GA-4: Env var key derivation
**Decision:** Env vars follow the pattern `{ROSETTA}_{SECTION}_{KEY}` in uppercase (e.g., `ROSETTA_EMBED_MODEL`).
**Rationale:** Unambiguous convention prevents collisions across the 8 tools and sections.

### [review] GA-5: Error contracts for foundation modules
**Decision:** `config.py` wraps `tomllib.TOMLDecodeError` in a clear message. `rdf_utils.py` wraps rdflib parse errors. No raw tracebacks escape to CLI users.
**Rationale:** Foundation code must define clean error boundaries — downstream tools compose on top of it.

## Decisions

- [review] REQ-26 added to Phase 1 scope — synthetic fixtures (master.ttl + 3 national schemas) are load-bearing for all downstream phases
- [review] `tomli` removed from dependencies — use `tomllib` (stdlib) per Python 3.11+ target
- [review] All 8 CLI stubs must accept `--config` and `--help` from Phase 1 onward
- [review] I/O helpers (`open_input`/`open_output`) require dedicated test coverage (`test_io.py`)
- [review] Acceptance truths strengthened: all 8 entrypoints verified, stdin/stdout composability tested, error cases covered

## Deferred Ideas

- Pre-commit hooks / linting config — considered, not needed for solo developer phase
- Makefile/justfile — considered, `uv run` commands are sufficient for now
- CI config — deferred until code exists to test

## Design Approach

- Click CLI framework with `[project.scripts]` entrypoints
- Config: `tomllib` (stdlib) for TOML parsing, 3-tier precedence: rosetta.toml defaults -> env vars -> CLI flags
- stdin/stdout: `--input`/`--output` flags defaulting to `-`, shared `open_input()`/`open_output()` helpers
- Pytest with conftest.py fixtures for shared test setup
