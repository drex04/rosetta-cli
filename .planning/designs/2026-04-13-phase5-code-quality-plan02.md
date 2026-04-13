# Design: Phase 5 Plan 02 — Pydantic Runtime Validation

## Approved Design

Pydantic v2 models defined in `rosetta/core/models.py`. Core functions that produce user-facing JSON return model instances instead of bare dicts. CLIs serialise via `model.model_dump(mode="json")`. Three output families: lint, suggestions, embeddings.

## Decisions Locked

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Models in `rosetta/core/models.py` (single file) | Three families, all small — one file avoids over-engineering |
| 2 | Core functions return Pydantic models, not dicts | Types flow through call stack; not just a boundary shim |
| 3 | Serialise with `model.model_dump(mode="json")` | Handles None, nested models, enums; avoids manual field listing |
| 4 | `FnmlSuggestion` is a nested Pydantic model | Currently `dict \| None` from `suggest_fnml`; give it a schema |
| 5 | Ingest parser internals out of scope | `ParsedField` etc. are internal, transformed to RDF immediately |
| 6 | `SeverityEnum` as `Literal["BLOCK", "WARNING", "INFO"]` | Validates severity values at construction; readable in JSON |

## Model Families

### Lint
- `FnmlSuggestion(function_iri: str, label: str | None)`
- `LintFinding(type: str, severity: Literal["BLOCK","WARNING","INFO"], source_uri: str, target_uri: str, message: str, fnml_suggestion: FnmlSuggestion | None)`
- `LintSummary(block: int, warning: int, info: int)`
- `LintReport(findings: list[LintFinding], summary: LintSummary)`

### Suggestions
- `Suggestion(target_uri: str, score: float, anomaly: bool)`
- `SuggestionReport(root: dict[str, list[Suggestion]])` — uses `RootModel`

### Embeddings
- `EmbeddingVectors(lexical: list[float])`
- `EmbeddingReport(root: dict[str, EmbeddingVectors])` — uses `RootModel`
