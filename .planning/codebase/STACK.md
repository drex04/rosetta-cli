# Technology Stack

**Last Updated:** 2026-04-16 (Phases 14-15)

## Languages & Runtime

- **Python:** 3.11+ (enforced in `pyproject.toml` requires-python)
- **Package Manager:** uv with lockfile (`uv.lock`); install via `uv sync`, add deps with `uv add <pkg>`
- **Build System:** hatchling (wheel backend, packages `rosetta/`)

## Frameworks & Core Dependencies

| Package                | Purpose                                      | Version      |
|------------------------|----------------------------------------------|--------------|
| **click**              | CLI command/option routing                   | >=8.1        |
| **rdflib**             | RDF graph model (Turtle, N-Triples, SPARQL) | >=6.3        |
| **pySHACL**            | SHACL shape validation (shapes in `rosetta/policies/`) | >=0.20 |
| **sentence-transformers** | Semantic similarity (LaBSE/e5-large-v2 HF model) | >=3.0 |
| **pydantic**           | JSON schema + Pydantic v2 models (`rosetta/core/models.py`) | >=2.13.0 |
| **linkml**             | Schema definition (`.linkml.yaml` format)   | >=1.10.0     |
| **schema-automator**   | JSON Schema↔OpenAPI↔RDF inference           | >=0.5.5      |
| **sssom**              | SSSOM TSV I/O (11 columns with datatypes, Phase 15) | >=0.4.15 |
| **deepl**              | Machine translation API client               | >=1.18,<2    |
| **pyyaml**             | Config/schema parsing                        | >=6.0        |
| **numpy**              | Vector similarity math                       | >=1.26       |
| **genson**             | JSON Schema generation                       | >=1.2        |

## CLI Tools

Nine entrypoints (all in `pyproject.toml`):

- `rosetta-ingest` → `rosetta/cli/ingest.py` — import schemas + mappings
- `rosetta-embed` → `rosetta/cli/embed.py` — compute embedding vectors
- `rosetta-suggest` → `rosetta/cli/suggest.py` — generate mapping suggestions via similarity
- `rosetta-translate` → `rosetta/cli/translate.py` — machine translate labels (DeepL API)
- `rosetta-lint` → `rosetta/cli/lint.py` — validate SSSOM unit + datatype compatibility (RDF mode removed Phase 15)
- `rosetta-validate` → `rosetta/cli/validate.py` — SHACL shape checking
- `rosetta-yarrrml-gen` → `rosetta/cli/yarrrml_gen.py` — generate linkml-map TransformSpec YAML
- `rosetta-provenance` → `rosetta/cli/provenance.py` — document mapping origin
- `rosetta-accredit` → `rosetta/cli/accredit.py` — manage audit-log (ingest/review/status/dump, Phase 14)

## Configuration

- **Primary config file:** `rosetta.toml` — store path, namespaces, embed model, translate lang, suggest thresholds, lint strictness, accredit log path
- **Overridable via CLI:** All settings have corresponding flags (e.g., `--model`, `--deepl-key`, `--log`)
- **Format:** TOML with sections: `[general]`, `[embed]`, `[translate]`, `[suggest]`, `[lint]`, `[accredit]`

## Quality Assurance (CI + Pre-commit)

All eight checks run via `uv run`:

| Check | Command | Target | Notes |
|-------|---------|--------|-------|
| Format | `ruff format .` | All | 100 char line length, Python 3.11 target |
| Lint | `ruff check .` | All | Rules E, W, F, I, UP |
| Type | `basedpyright` | Strict: core + cli; Basic: tests | Mypy follow_imports=skip (skip dependencies) |
| Regression | `pytest -m "not slow"` | `rosetta/tests/` | Excludes slow marks |
| Complexity | `radon cc rosetta/core/ -n C -s` | Core only | CLI excluded (inherently high CC via Click) |
| Dead Code | `vulture rosetta/ --exclude rosetta/tests --min-confidence 80` | All except tests | Confidence 80 to skip Pydantic/Click decorators |
| Security | `bandit -r rosetta/ -x rosetta/tests -ll` | All except tests | Low-severity filter (-ll) |
| Modernization | `refurb rosetta/ rosetta/tests/` | All | Python idiom upgrades |

**CI:** `.github/workflows/ci.yml` enforces all eight on every push/PR; dedicated `analysis` job for radon/vulture/bandit.

## Type Annotations

- **Mandatory in `rosetta/core/` and `rosetta/cli/`:** explicit parameter and return types
- **Broad RDF types:** Use `rdflib.term.Node | None`, `rdflib.Graph` (never narrow to URIRef/Literal at function boundaries)
- **User-facing JSON:** Pydantic models only in `rosetta/core/models.py` (v2, serialized with `model_dump(mode="json")`)
- **Tests:** Basic mode — annotate fixture returns and non-obvious vars; use `# pyright: ignore[reportArgumentType]` for stub suppression

## Data Formats

- **Turtle (.ttl)** — human RDF artifacts
- **N-Triples (.nt)** — machine RDF interchange
- **LinkML YAML (.linkml.yaml)** — schema definitions
- **SSSOM TSV (.sssom.tsv)** — 11 columns (Phase 15): subject_id, predicate_id, object_id, mapping_justification, confidence, subject_label, object_label, subject_datatype, object_datatype, mapping_date, record_id
- **JSON** — structured output via Pydantic models (no bare dicts to stdout)
