"""Immutable Atomic VoC contracts.

Atomic VoC is the unit-level bridge from source evidence to later intelligence
attachments. This module defines identity and revision contracts only; it does
not extract, classify, persist, or route records.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_atomic_voc_id,
    new_atomic_voc_revision_id,
    validate_canonical_id,
)
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


class AtomicVocStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class AtomicVocRevisionReason(StrEnum):
    INITIAL_EXTRACTION = "initial_extraction"
    REANALYSIS = "reanalysis"
    CORRECTION = "correction"
    TAXONOMY_UPDATE = "taxonomy_update"
    MODEL_UPGRADE = "model_upgrade"
    PROMPT_UPGRADE = "prompt_upgrade"


class AtomicVocSourceType(StrEnum):
    COMMENT = "comment"
    REPLY = "reply"
    VIDEO_TRANSCRIPT = "video_transcript"
    VIDEO_DESCRIPTION = "video_description"
    VIDEO_METADATA = "video_metadata"
    COMMUNITY_POST = "community_post"


class AtomicVocSpan(FrozenContractModel):
    source_field: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    quoted_text: str = Field(min_length=1)
    extraction_method: str = Field(min_length=1)

    @field_validator("source_field", "quoted_text", "extraction_method")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value

    @model_validator(mode="after")
    def _span_offsets_are_ordered(self) -> "AtomicVocSpan":
        if self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char")
        return self


class AtomicVoc(FrozenContractModel):
    atomic_voc_id: str = Field(default_factory=new_atomic_voc_id)
    source_comment_id: str = Field(min_length=1)
    source_video_id: str | None = None
    source_type: AtomicVocSourceType
    collection_run_id: str
    first_analysis_run_id: str
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()
    status: AtomicVocStatus = AtomicVocStatus.ACTIVE

    @field_validator("atomic_voc_id")
    @classmethod
    def _atomic_voc_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ATOMIC_VOC)

    @field_validator("collection_run_id")
    @classmethod
    def _collection_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    @field_validator("first_analysis_run_id")
    @classmethod
    def _first_analysis_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)

    @field_validator("source_comment_id")
    @classmethod
    def _source_comment_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_comment_id must not be blank")
        return value

    _created_at = field_validator("created_at")(_validate_timezone)


class AtomicVocRevision(FrozenContractModel):
    atomic_voc_revision_id: str = Field(default_factory=new_atomic_voc_revision_id)
    atomic_voc_id: str
    analysis_run_id: str
    revision_number: int = Field(ge=1)
    revision_reason: AtomicVocRevisionReason = AtomicVocRevisionReason.INITIAL_EXTRACTION
    text_excerpt: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    language: str = Field(min_length=1)
    country: str = Field(min_length=1)
    product_category: str | None = None
    product_family: str | None = None
    feature_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    spans: tuple[AtomicVocSpan, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("atomic_voc_revision_id")
    @classmethod
    def _atomic_voc_revision_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ATOMIC_VOC_REVISION)

    @field_validator("atomic_voc_id")
    @classmethod
    def _atomic_voc_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ATOMIC_VOC)

    @field_validator("analysis_run_id")
    @classmethod
    def _analysis_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.EVIDENCE_REF)
            for value in values
        )

    @field_validator(
        "text_excerpt",
        "normalized_text",
        "language",
        "country",
        "product_category",
        "product_family",
        mode="before",
    )
    @classmethod
    def _nonblank_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Text fields must not be blank")
        return value

    _created_at = field_validator("created_at")(_validate_timezone)
