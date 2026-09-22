"""Immutable Practitioner Action contracts.

PractitionerAction represents a recommended or governed human action derived
from one or more ImprovementCandidate records. It is not a candidate,
initiative, responsible organization, project-management object, or execution
tracker. No execution engine is implemented here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_practitioner_action_id,
    validate_canonical_id,
)
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


class PractitionerActionStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PractitionerActionSource(StrEnum):
    LLM = "llm"
    RULE = "rule"
    HUMAN_REVIEW = "human_review"
    REANALYSIS = "reanalysis"


class PractitionerAction(FrozenContractModel):
    practitioner_action_id: str = Field(default_factory=new_practitioner_action_id)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    related_candidate_ids: tuple[str, ...] = Field(min_length=1)
    supporting_issue_cluster_ids: tuple[str, ...] = ()
    action_status: PractitionerActionStatus = PractitionerActionStatus.PROPOSED
    action_source: PractitionerActionSource
    confidence: float = Field(ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()

    @field_validator("practitioner_action_id")
    @classmethod
    def _practitioner_action_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.PRACTITIONER_ACTION)

    @field_validator("title", "summary")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text fields must not be blank")
        return value

    @field_validator("related_candidate_ids")
    @classmethod
    def _related_candidate_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.IMPROVEMENT_CANDIDATE)
            for value in values
        )

    @field_validator("supporting_issue_cluster_ids")
    @classmethod
    def _supporting_issue_cluster_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ISSUE_CLUSTER) for value in values
        )

    @model_validator(mode="after")
    def _references_are_nonempty(self) -> "PractitionerAction":
        if not self.related_candidate_ids:
            raise ValueError("PractitionerAction requires at least one ImprovementCandidate ID")
        return self

    _created_at = field_validator("created_at")(_validate_timezone)
