"""Immutable weak-inference Root Cause hypothesis contracts.

Root Cause hypotheses explain what may be driving a customer experience issue.
They are not evidence, not facts, and not candidate priorities. Maturity governs
intervention confidence, not customer problem importance.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_root_cause_hypothesis_id,
    validate_canonical_id,
)
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


class RootCauseMaturity(StrEnum):
    UNKNOWN = "unknown"
    POSSIBLE = "possible"
    LIKELY = "likely"
    SUPPORTED = "supported"
    REJECTED = "rejected"


class RootCauseSource(StrEnum):
    LLM = "llm"
    RULE = "rule"
    HUMAN_REVIEW = "human_review"
    REANALYSIS = "reanalysis"
    CORRECTION = "correction"


class RootCauseCategory(StrEnum):
    PRODUCT_DESIGN = "product_design"
    USABILITY = "usability"
    INSTALLATION_SETUP = "installation_setup"
    DOCUMENTATION_GUIDANCE = "documentation_guidance"
    SERVICE_SUPPORT = "service_support"
    EXPECTATION_GAP = "expectation_gap"
    COMPATIBILITY_ENVIRONMENT = "compatibility_environment"
    DURABILITY_RELIABILITY = "durability_reliability"
    PRICING_VALUE = "pricing_value"
    UNCLEAR = "unclear"


class RootCauseHypothesis(FrozenContractModel):
    root_cause_hypothesis_id: str = Field(default_factory=new_root_cause_hypothesis_id)
    atomic_voc_revision_id: str
    analysis_run_id: str
    hypothesis_text: str = Field(min_length=1)
    cause_category: RootCauseCategory
    maturity: RootCauseMaturity = RootCauseMaturity.UNKNOWN
    confidence: float = Field(ge=0, le=1)
    evidence_refs: tuple[str, ...] = ()
    counter_evidence_refs: tuple[str, ...] = ()
    source: RootCauseSource
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()

    @field_validator("root_cause_hypothesis_id")
    @classmethod
    def _root_cause_hypothesis_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ROOT_CAUSE_HYPOTHESIS)

    @field_validator("atomic_voc_revision_id")
    @classmethod
    def _atomic_voc_revision_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ATOMIC_VOC_REVISION)

    @field_validator("analysis_run_id")
    @classmethod
    def _analysis_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)

    @field_validator("hypothesis_text")
    @classmethod
    def _hypothesis_text_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("hypothesis_text must not be blank")
        return value

    @field_validator("evidence_refs", "counter_evidence_refs")
    @classmethod
    def _evidence_ref_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.EVIDENCE_REF)
            for value in values
        )

    @model_validator(mode="after")
    def _governed_maturity_source(self) -> "RootCauseHypothesis":
        governed_sources = {RootCauseSource.HUMAN_REVIEW, RootCauseSource.CORRECTION}
        governed_maturities = {RootCauseMaturity.SUPPORTED, RootCauseMaturity.REJECTED}
        if self.maturity in governed_maturities and self.source not in governed_sources:
            raise ValueError("supported/rejected Root Cause maturity requires human_review or correction source")
        return self

    _created_at = field_validator("created_at")(_validate_timezone)
