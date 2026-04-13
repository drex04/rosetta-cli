from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, RootModel

# --- Lint ---


class FnmlSuggestion(BaseModel):
    fnml_function: str
    label: str | None = None
    multiplier: float | None = None
    offset: float | None = None

    def __getitem__(self, key: str) -> object:
        return self.model_dump()[key]

    def __contains__(self, key: object) -> bool:
        return key in self.model_dump()


class LintFinding(BaseModel):
    rule: str
    severity: Literal["BLOCK", "WARNING", "INFO"]
    source_uri: str
    target_uri: str | None = None
    message: str
    fnml_suggestion: FnmlSuggestion | None = None


class LintSummary(BaseModel):
    block: int
    warning: int
    info: int


class LintReport(BaseModel):
    findings: list[LintFinding]
    summary: LintSummary


# --- Suggestions ---


class Suggestion(BaseModel):
    target_uri: str
    score: float


class FieldSuggestions(BaseModel):
    suggestions: list[Suggestion]
    anomaly: bool


class SuggestionReport(RootModel[dict[str, FieldSuggestions]]):
    pass


# --- Embeddings ---


class EmbeddingVectors(BaseModel):
    lexical: list[float]


class EmbeddingReport(RootModel[dict[str, EmbeddingVectors]]):
    pass


# --- Provenance ---


class ProvenanceRecord(BaseModel):
    activity_uri: str
    agent_uri: str
    label: str | None = None
    started_at: str  # ISO 8601 datetime string
    ended_at: str  # ISO 8601 datetime string
    version: int  # current rose:version of the artifact at query time
