"""Immutable collection and analysis run contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_analysis_run_id,
    new_collection_run_id,
    validate_canonical_id,
)
from src.domain.digests import validate_sha256_digest


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_timezone(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("Timestamp must include timezone information")
    return value


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class AnalysisKind(StrEnum):
    INITIAL = "initial"
    REANALYSIS = "reanalysis"
    LIFECYCLE_REEVALUATION = "lifecycle_reevaluation"
    CORRECTION_REPLAY = "correction_replay"


class FrozenContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RunError(FrozenContractModel):
    code: str
    message: str
    stage: str | None = None
    source_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)

    _timezone = field_validator("occurred_at")(_validate_timezone)


class PromptVersion(FrozenContractModel):
    stage: str
    prompt_id: str
    prompt_version: str
    content_digest: str

    _digest = field_validator("content_digest")(validate_sha256_digest)


class ModelVersion(FrozenContractModel):
    stage: str
    provider: str
    model: str
    model_snapshot: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class CostSummary(FrozenContractModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    total_cost: float = Field(default=0.0, ge=0)
    provider_details: tuple[dict[str, Any], ...] = ()


class CollectionRun(FrozenContractModel):
    collection_run_id: str = Field(default_factory=new_collection_run_id)
    source_system: str
    scope: dict[str, Any] = Field(default_factory=dict)
    collector_version: str
    code_commit: str
    raw_snapshot_ids: tuple[str, ...] = ()
    dataset_fingerprint: str
    quota: dict[str, Any] = Field(default_factory=dict)
    errors: tuple[RunError, ...] = ()
    status: RunStatus = RunStatus.PENDING
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    legacy_ids: tuple[str, ...] = ()

    @field_validator("collection_run_id")
    @classmethod
    def _collection_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    @field_validator("raw_snapshot_ids")
    @classmethod
    def _raw_snapshot_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT)
            for value in values
        )

    _fingerprint = field_validator("dataset_fingerprint")(validate_sha256_digest)
    _started_at = field_validator("started_at")(_validate_timezone)
    _finished_at = field_validator("finished_at")(_validate_timezone)


class AnalysisRun(FrozenContractModel):
    analysis_run_id: str = Field(default_factory=new_analysis_run_id)
    collection_run_id: str
    parent_analysis_run_id: str | None = None
    analysis_kind: AnalysisKind = AnalysisKind.INITIAL
    pipeline_version: str
    schema_bundle_version: str
    code_commit: str
    prompt_versions: tuple[PromptVersion, ...] = ()
    model_versions: tuple[ModelVersion, ...] = ()
    correction_cutoff_at: datetime | None = None
    dataset_fingerprint: str
    cost_summary: CostSummary = Field(default_factory=CostSummary)
    artifact_ids: tuple[str, ...] = ()
    errors: tuple[RunError, ...] = ()
    status: RunStatus = RunStatus.PENDING
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    legacy_ids: tuple[str, ...] = ()

    @field_validator("analysis_run_id")
    @classmethod
    def _analysis_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)

    @field_validator("collection_run_id")
    @classmethod
    def _collection_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    @field_validator("parent_analysis_run_id")
    @classmethod
    def _parent_analysis_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)

    @field_validator("artifact_ids")
    @classmethod
    def _artifact_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ARTIFACT) for value in values)

    _fingerprint = field_validator("dataset_fingerprint")(validate_sha256_digest)
    _correction_cutoff_at = field_validator("correction_cutoff_at")(_validate_timezone)
    _started_at = field_validator("started_at")(_validate_timezone)
    _finished_at = field_validator("finished_at")(_validate_timezone)
