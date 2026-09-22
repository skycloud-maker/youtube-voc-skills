"""Immutable Improvement Candidate contracts.

ImprovementCandidate represents a governed improvement opportunity derived from
one or more IssueCluster records. It is not practitioner execution, ownership,
priority scoring, or presentation state. No candidate generation engine is
implemented here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_improvement_candidate_id,
    validate_canonical_id,
)
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


class CandidateStatus(StrEnum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class CandidateSource(StrEnum):
    LLM = "llm"
    RULE = "rule"
    HUMAN_REVIEW = "human_review"
    REANALYSIS = "reanalysis"


class ImprovementCandidate(FrozenContractModel):
    improvement_candidate_id: str = Field(default_factory=new_improvement_candidate_id)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    related_issue_cluster_ids: tuple[str, ...] = Field(min_length=1)
    supporting_evidence_refs: tuple[str, ...] = ()
    supporting_root_cause_ids: tuple[str, ...] = ()
    candidate_status: CandidateStatus = CandidateStatus.PROPOSED
    candidate_source: CandidateSource
    confidence: float = Field(ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()

    @field_validator("improvement_candidate_id")
    @classmethod
    def _improvement_candidate_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.IMPROVEMENT_CANDIDATE)

    @field_validator("title", "summary")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text fields must not be blank")
        return value

    @field_validator("related_issue_cluster_ids")
    @classmethod
    def _related_issue_cluster_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ISSUE_CLUSTER) for value in values
        )

    @field_validator("supporting_evidence_refs")
    @classmethod
    def _supporting_evidence_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.EVIDENCE_REF) for value in values
        )

    @field_validator("supporting_root_cause_ids")
    @classmethod
    def _supporting_root_cause_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ROOT_CAUSE_HYPOTHESIS)
            for value in values
        )

    @model_validator(mode="after")
    def _references_are_nonempty(self) -> "ImprovementCandidate":
        if not self.related_issue_cluster_ids:
            raise ValueError("ImprovementCandidate requires at least one IssueCluster ID")
        return self

    _created_at = field_validator("created_at")(_validate_timezone)
