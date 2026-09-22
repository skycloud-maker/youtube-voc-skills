"""Immutable governance metadata contracts.

These models describe governance records without implying where or whether they
are persisted. They intentionally avoid database, dashboard, pipeline, and
sidecar integration.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from src.domain.canonical_ids import CanonicalIdPrefix, validate_canonical_id
from src.domain.digests import validate_sha256_digest
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


_METADATA_ID_PATTERN = re.compile(r"^[a-z]+_[0-9a-f]{32}$")


def new_metadata_id(prefix: str) -> str:
    """Create a storage-neutral opaque metadata identifier."""

    normalized = prefix.strip().lower()
    if not normalized or not normalized.endswith("_") or not normalized[:-1].isalpha():
        raise ValueError("Metadata ID prefix must be lowercase letters followed by '_'")
    return f"{normalized}{uuid4().hex}"


def validate_metadata_id(value: str) -> str:
    if not isinstance(value, str) or not _METADATA_ID_PATTERN.fullmatch(value):
        raise ValueError("Metadata ID must use a lowercase prefix and UUID4 hex payload")
    return value


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CORRECTION = "needs_correction"


class ShadowEventSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PromptInvocationMetadata(FrozenContractModel):
    prompt_metadata_id: str = Field(default_factory=lambda: new_metadata_id("pmeta_"))
    prompt_family: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt_hash: str
    prompt_source: str = Field(min_length=1)
    prompt_template_ref: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    _metadata_id = field_validator("prompt_metadata_id")(validate_metadata_id)
    _prompt_hash = field_validator("prompt_hash")(validate_sha256_digest)
    _created_at = field_validator("created_at")(_validate_timezone)


class ModelInvocationMetadata(FrozenContractModel):
    model_metadata_id: str = Field(default_factory=lambda: new_metadata_id("mmeta_"))
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_version: str | None = None
    temperature: float | None = Field(default=None, ge=0)
    top_p: float | None = Field(default=None, ge=0, le=1)
    reasoning_mode: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    _metadata_id = field_validator("model_metadata_id")(validate_metadata_id)
    _created_at = field_validator("created_at")(_validate_timezone)


class CostMetadata(FrozenContractModel):
    cost_metadata_id: str = Field(default_factory=lambda: new_metadata_id("cost_"))
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    request_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    _metadata_id = field_validator("cost_metadata_id")(validate_metadata_id)
    _created_at = field_validator("created_at")(_validate_timezone)

    @model_validator(mode="after")
    def _total_matches_parts(self) -> "CostMetadata":
        expected_total = self.input_tokens + self.output_tokens
        if self.total_tokens != expected_total:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        return self


class EvaluationMetadata(FrozenContractModel):
    evaluation_run_id: str = Field(default_factory=lambda: new_metadata_id("eval_"))
    evaluation_bundle_id: str = Field(min_length=1)
    golden_set_version: str = Field(min_length=1)
    evaluation_scope: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    _metadata_id = field_validator("evaluation_run_id")(validate_metadata_id)
    _created_at = field_validator("created_at")(_validate_timezone)


class RegressionMetadata(FrozenContractModel):
    regression_run_id: str = Field(default_factory=lambda: new_metadata_id("reg_"))
    regression_suite_version: str = Field(min_length=1)
    baseline_version: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

    _metadata_id = field_validator("regression_run_id")(validate_metadata_id)
    _created_at = field_validator("created_at")(_validate_timezone)


class ReviewMetadata(FrozenContractModel):
    review_metadata_id: str = Field(default_factory=lambda: new_metadata_id("review_"))
    reviewer_id: str = Field(min_length=1)
    review_timestamp: datetime = Field(default_factory=utc_now)
    review_reason: str = Field(min_length=1)
    review_status: ReviewStatus

    _metadata_id = field_validator("review_metadata_id")(validate_metadata_id)
    _review_timestamp = field_validator("review_timestamp")(_validate_timezone)


class CorrectionMetadata(FrozenContractModel):
    correction_id: str = Field(default_factory=lambda: new_metadata_id("corr_"))
    correction_timestamp: datetime = Field(default_factory=utc_now)
    correction_reason: str = Field(min_length=1)
    correction_source: str = Field(min_length=1)
    corrected_field_path: str = Field(min_length=1)

    _metadata_id = field_validator("correction_id")(validate_metadata_id)
    _correction_timestamp = field_validator("correction_timestamp")(_validate_timezone)


class ReanalysisMetadata(FrozenContractModel):
    reanalysis_metadata_id: str = Field(default_factory=lambda: new_metadata_id("reana_"))
    parent_analysis_run_id: str
    reanalysis_reason: str = Field(min_length=1)
    replay_prompt_version: str | None = None
    replay_model_version: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    _metadata_id = field_validator("reanalysis_metadata_id")(validate_metadata_id)
    _created_at = field_validator("created_at")(_validate_timezone)

    @field_validator("parent_analysis_run_id")
    @classmethod
    def _parent_analysis_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)


class ShadowEventMetadata(FrozenContractModel):
    shadow_event_id: str = Field(default_factory=lambda: new_metadata_id("shadow_"))
    event_type: str = Field(min_length=1)
    severity: ShadowEventSeverity
    source_component: str = Field(min_length=1)
    related_collection_run_id: str | None = None
    related_analysis_run_id: str | None = None
    message: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)

    _metadata_id = field_validator("shadow_event_id")(validate_metadata_id)
    _created_at = field_validator("created_at")(_validate_timezone)

    @field_validator("related_collection_run_id")
    @classmethod
    def _related_collection_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    @field_validator("related_analysis_run_id")
    @classmethod
    def _related_analysis_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)
