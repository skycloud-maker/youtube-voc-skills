"""Immutable CEJ attachment contracts.

CEJ assessments attach customer-journey interpretation to AtomicVocRevision
records. This module defines attachment contracts only; it does not execute
inference, migration, persistence, or rendering.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_cej_assessment_id,
    validate_canonical_id,
)
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


class CejStage(StrEnum):
    AWARENESS = "awareness"
    EXPLORATION = "exploration"
    DECISION = "decision"
    PURCHASE = "purchase"
    DELIVERY = "delivery"
    SETUP = "setup"
    USAGE = "usage"
    MANAGEMENT = "management"
    REPLACEMENT = "replacement"


class HsCejRollupStage(StrEnum):
    DISCOVER = "discover"
    COMPARE_DECIDE = "compare_decide"
    PURCHASE_DELIVERY = "purchase_delivery"
    SETUP_ONBOARDING = "setup_onboarding"
    USE_MANAGE = "use_manage"
    REPLACE_REPURCHASE = "replace_repurchase"


class CejGateReason(StrEnum):
    STRATEGIC_SCOPE = "strategic_scope"
    SUPPORTING_SCOPE = "supporting_scope"
    INQUIRY_SCOPE = "inquiry_scope"
    INFORMATIONAL_SCOPE = "informational_scope"
    TRASH_SCOPE = "trash_scope"
    MISSING_SOURCE_STAGE = "missing_source_stage"
    UNMAPPED_STAGE = "unmapped_stage"
    EXCLUDED_FROM_ANALYSIS = "excluded_from_analysis"
    HUMAN_CORRECTED = "human_corrected"
    REANALYSIS_UPDATED = "reanalysis_updated"


class CejAssessmentSource(StrEnum):
    LLM = "llm"
    RULE = "rule"
    LEGACY_COMMENT_TRUTH = "legacy_comment_truth"
    HUMAN_REVIEW = "human_review"
    REANALYSIS = "reanalysis"


class CejAssessment(FrozenContractModel):
    cej_assessment_id: str = Field(default_factory=new_cej_assessment_id)
    atomic_voc_revision_id: str
    analysis_run_id: str
    experience_stage: CejStage | None = None
    actionable_stage: CejStage | None = None
    pre_gate_stage: CejStage | None = None
    hs_rollup_stage: HsCejRollupStage | None = None
    gate_reason: CejGateReason
    confidence: float = Field(ge=0, le=1)
    source: CejAssessmentSource
    evidence_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()

    @field_validator("cej_assessment_id")
    @classmethod
    def _cej_assessment_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.CEJ_ASSESSMENT)

    @field_validator("atomic_voc_revision_id")
    @classmethod
    def _atomic_voc_revision_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ATOMIC_VOC_REVISION)

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

    @model_validator(mode="after")
    def _stage_or_gate_reason_is_explicit(self) -> "CejAssessment":
        if self.experience_stage is None and self.actionable_stage is None and self.pre_gate_stage is None:
            if self.gate_reason not in {
                CejGateReason.MISSING_SOURCE_STAGE,
                CejGateReason.UNMAPPED_STAGE,
                CejGateReason.EXCLUDED_FROM_ANALYSIS,
                CejGateReason.TRASH_SCOPE,
            }:
                raise ValueError("Stage absence requires an explicit non-stage gate reason")
        return self

    _created_at = field_validator("created_at")(_validate_timezone)
