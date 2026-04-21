from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, RootModel

# review-2: ConfigDict(extra="forbid") on every user-facing model — the same
# gotcha that bit SSSOMRow in 16-00. Catches field-name typos at construction
# time (e.g. README/JSON doc drift against model field names).
_STRICT: ConfigDict = ConfigDict(extra="forbid")


# --- Lint ---


class FnmlSuggestion(BaseModel):
    model_config = _STRICT

    fnml_function: str
    label: str | None = None
    multiplier: float | None = None
    offset: float | None = None

    def __getitem__(self, key: str) -> object:
        return self.model_dump()[key]

    def __contains__(self, key: object) -> bool:
        return key in self.model_dump()


class LintFinding(BaseModel):
    model_config = _STRICT

    rule: str
    severity: Literal["BLOCK", "WARNING", "INFO"]
    source_uri: str
    target_uri: str | None = None
    message: str
    fnml_suggestion: FnmlSuggestion | None = None


class LintSummary(BaseModel):
    model_config = _STRICT

    block: int
    warning: int
    info: int


class LintReport(BaseModel):
    model_config = _STRICT

    findings: list[LintFinding]
    summary: LintSummary


# --- Embeddings ---


class EmbeddingVectors(BaseModel):
    model_config = _STRICT

    label: str = ""
    lexical: list[float]
    structural: list[float] = []
    datatype: str | None = None


class EmbeddingReport(RootModel[dict[str, EmbeddingVectors]]):
    pass


# --- Suggest ---


class Suggestion(BaseModel):
    model_config = _STRICT

    target_uri: str
    label: str = ""
    score: float


class FieldSuggestions(BaseModel):
    model_config = _STRICT

    label: str = ""
    suggestions: list[Suggestion]
    anomaly: bool = False


class SuggestionReport(RootModel[dict[str, FieldSuggestions]]):
    pass


# --- SSSOM ---


class SSSOMRow(BaseModel):
    model_config = _STRICT

    subject_id: str
    predicate_id: str
    object_id: str
    mapping_justification: str
    confidence: float
    subject_label: str = ""
    object_label: str = ""
    mapping_date: datetime | None = None  # stamped by accredit append
    record_id: str | None = None  # UUID4 stamped by accredit append
    subject_datatype: str | None = None
    object_datatype: str | None = None
    subject_type: str | None = None
    object_type: str | None = None
    mapping_group_id: str | None = None
    composition_expr: str | None = None


# --- Validate ---


class ValidationFinding(BaseModel):
    model_config = _STRICT

    focus_node: str
    severity: Literal["Violation", "Warning", "Info"]
    constraint: str
    source_shape: str | None = None
    message: str | None = None  # sh:resultMessage is optional per SHACL spec


class ValidationSummary(BaseModel):
    model_config = _STRICT

    violation: int
    warning: int
    info: int
    conforms: bool


class ValidationReport(BaseModel):
    model_config = _STRICT

    findings: list[ValidationFinding]
    summary: ValidationSummary


# --- YARRRML Generation (coverage) ---


class CoverageReport(BaseModel):
    model_config = _STRICT

    source_schema_prefix: str
    master_schema_prefix: str
    rows_total: int
    rows_after_prefix_filter: int
    rows_after_predicate_filter: int
    rows_after_justification_filter: int
    resolved_class_mappings: list[str] = []
    resolved_slot_mappings: list[str] = []
    unresolved_subjects: list[dict[str, str]] = []  # {"curie", "reason"}
    unresolved_objects: list[dict[str, str]] = []
    skipped_non_exact_predicates: list[dict[str, str]] = []  # {"row_id", "predicate_id"}
    composite_groups: list[
        dict[str, object]
    ] = []  # {"group_id", "member_row_ids": [...], "target_slot"}  # noqa: E501
    datatype_warnings: list[dict[str, str]] = []
    unmapped_required_master_slots: list[str] = []
