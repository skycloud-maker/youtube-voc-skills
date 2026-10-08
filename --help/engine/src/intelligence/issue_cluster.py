"""Immutable Issue Cluster contracts.

IssueCluster groups semantically related AtomicVocRevision records. It is not a
root cause, candidate, practitioner action, priority score, or implementation
recommendation. No grouping engine is implemented here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_issue_cluster_id,
    validate_canonical_id,
)
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


class IssueClusterStatus(StrEnum):
    ACTIVE = "active"
    MERGED = "merged"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class IssueClusterSource(StrEnum):
    LLM = "llm"
    RULE = "rule"
    HUMAN_REVIEW = "human_review"
    REANALYSIS = "reanalysis"


class IssueCluster(FrozenContractModel):
    issue_cluster_id: str = Field(default_factory=new_issue_cluster_id)
    analysis_run_id: str
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    atomic_voc_revision_ids: tuple[str, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
    root_cause_hypothesis_ids: tuple[str, ...] = ()
    cluster_status: IssueClusterStatus = IssueClusterStatus.ACTIVE
    cluster_source: IssueClusterSource
    confidence: float = Field(ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()

    @field_validator("issue_cluster_id")
    @classmethod
    def _issue_cluster_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ISSUE_CLUSTER)

    @field_validator("analysis_run_id")
    @classmethod
    def _analysis_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)

    @field_validator("title", "summary")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text fields must not be blank")
        return value

    @field_validator("atomic_voc_revision_ids")
    @classmethod
    def _atomic_voc_revision_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ATOMIC_VOC_REVISION)
            for value in values
        )

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.EVIDENCE_REF)
            for value in values
        )

    @field_validator("root_cause_hypothesis_ids")
    @classmethod
    def _root_cause_hypothesis_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ROOT_CAUSE_HYPOTHESIS)
            for value in values
        )

    @model_validator(mode="after")
    def _references_are_nonempty(self) -> "IssueCluster":
        if not self.atomic_voc_revision_ids:
            raise ValueError("IssueCluster requires at least one AtomicVocRevision ID")
        return self

    _created_at = field_validator("created_at")(_validate_timezone)
