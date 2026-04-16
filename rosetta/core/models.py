from __future__ import annotations

from datetime import datetime
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


# --- Embeddings ---


class EmbeddingVectors(BaseModel):
    label: str = ""
    lexical: list[float]
    structural: list[float] = []
    datatype: str | None = None


class EmbeddingReport(RootModel[dict[str, EmbeddingVectors]]):
    pass


# --- Suggest ---


class Suggestion(BaseModel):
    target_uri: str
    label: str = ""
    score: float


class FieldSuggestions(BaseModel):
    label: str = ""
    suggestions: list[Suggestion]
    anomaly: bool = False


class SuggestionReport(RootModel[dict[str, FieldSuggestions]]):
    pass


# --- SSSOM ---


class SSSOMRow(BaseModel):
    subject_id: str
    predicate_id: str
    object_id: str
    mapping_justification: str
    confidence: float
    subject_label: str = ""
    object_label: str = ""
    mapping_date: datetime | None = None  # stamped by accredit ingest
    record_id: str | None = None  # UUID4 stamped by accredit ingest
    subject_datatype: str | None = None
    object_datatype: str | None = None
    subject_type: str | None = None
    object_type: str | None = None
    mapping_group_id: str | None = None
    composition_expr: str | None = None


# --- Provenance ---


class ProvenanceRecord(BaseModel):
    activity_uri: str
    agent_uri: str
    label: str | None = None
    started_at: str  # ISO 8601 datetime string
    ended_at: str  # ISO 8601 datetime string
    version: int  # current rose:version of the artifact at query time


# --- Validate ---


class ValidationFinding(BaseModel):
    focus_node: str
    severity: Literal["Violation", "Warning", "Info"]
    constraint: str
    source_shape: str | None = None
    message: str | None = None  # sh:resultMessage is optional per SHACL spec


class ValidationSummary(BaseModel):
    violation: int
    warning: int
    info: int
    conforms: bool


class ValidationReport(BaseModel):
    findings: list[ValidationFinding]
    summary: ValidationSummary


# --- Accreditation ---


class StatusEntry(BaseModel):
    subject_id: str
    object_id: str
    state: Literal["pending", "approved", "rejected"]
    predicate_id: str
    mapping_date: str | None


# --- RML Generation ---


class MappingDecision(BaseModel):
    source_uri: str
    target_uri: str
    field_ref: str | None = None  # rml:reference value; defaults to URI last segment
    fnml_function: str | None = None  # set in Plan 02
    multiplier: float | None = None
    offset: float | None = None
