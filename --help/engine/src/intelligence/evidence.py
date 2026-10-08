"""Immutable evidence reference contracts.

EvidenceRef links intelligence records back to source evidence and canonical run
lineage. It is a contract only: no extraction, persistence, scoring engine, or
presentation integration is implemented here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_evidence_ref_id,
    validate_canonical_id,
)
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


class EvidenceKind(StrEnum):
    DIRECT = "direct"
    CONTEXT = "context"
    CONTRADICTORY = "contradictory"
    TRANSLATION = "translation"
    SUMMARY = "summary"


class EvidenceStrength(StrEnum):
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class EvidenceSourceType(StrEnum):
    COMMENT = "comment"
    REPLY = "reply"
    VIDEO_TITLE = "video_title"
    VIDEO_DESCRIPTION = "video_description"
    TRANSCRIPT = "transcript"
    COMMUNITY_POST = "community_post"
    EXTERNAL_METADATA = "external_metadata"


class EvidenceSpan(FrozenContractModel):
    source_field: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    quoted_text: str = Field(min_length=1)

    @field_validator("source_field", "quoted_text")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value

    @model_validator(mode="after")
    def _span_offsets_are_ordered(self) -> "EvidenceSpan":
        if self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char")
        return self


class EvidenceRef(FrozenContractModel):
    evidence_ref_id: str = Field(default_factory=new_evidence_ref_id)
    atomic_voc_id: str
    atomic_voc_revision_id: str
    raw_source_snapshot_id: str
    collection_run_id: str
    analysis_run_id: str
    source_type: EvidenceSourceType
    source_id: str = Field(min_length=1)
    source_field: str = Field(min_length=1)
    span: EvidenceSpan
    quoted_text: str = Field(min_length=1)
    normalized_quote: str = Field(min_length=1)
    evidence_kind: EvidenceKind
    evidence_strength: EvidenceStrength
    language: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()

    @field_validator("evidence_ref_id")
    @classmethod
    def _evidence_ref_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.EVIDENCE_REF)

    @field_validator("atomic_voc_id")
    @classmethod
    def _atomic_voc_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ATOMIC_VOC)

    @field_validator("atomic_voc_revision_id")
    @classmethod
    def _atomic_voc_revision_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ATOMIC_VOC_REVISION)

    @field_validator("raw_source_snapshot_id")
    @classmethod
    def _raw_source_snapshot_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT)

    @field_validator("collection_run_id")
    @classmethod
    def _collection_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    @field_validator("analysis_run_id")
    @classmethod
    def _analysis_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)

    @field_validator(
        "source_id",
        "source_field",
        "quoted_text",
        "normalized_quote",
        "language",
    )
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value

    _created_at = field_validator("created_at")(_validate_timezone)
