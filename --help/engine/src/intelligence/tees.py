"""Immutable TEE/S attachment contracts.

TEE/S assessments attach experience-friction signals to AtomicVocRevision
records. Time means time inside the customer experience, not chronological
trend analysis.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_tees_assessment_id,
    validate_canonical_id,
)
from src.domain.runs import FrozenContractModel, _validate_timezone, utc_now


class TeesAxis(StrEnum):
    TIME = "time"
    EFFORT = "effort"
    EMOTION = "emotion"
    SUCCESS = "success"


class TeesSignalPolarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class TeesIntensity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class TeesAssessmentSource(StrEnum):
    LLM = "llm"
    RULE = "rule"
    LEGACY_COMMENT_TRUTH = "legacy_comment_truth"
    HUMAN_REVIEW = "human_review"
    REANALYSIS = "reanalysis"


_ALLOWED_SIGNAL_TYPES: dict[TeesAxis, frozenset[str]] = {
    TeesAxis.TIME: frozenset(
        {
            "delay",
            "waiting",
            "repeated_attempts",
            "early_failure",
            "recurrence",
            "duration_burden",
        }
    ),
    TeesAxis.EFFORT: frozenset(
        {
            "setup_difficulty",
            "usage_difficulty",
            "maintenance_burden",
            "troubleshooting_effort",
            "information_search_effort",
            "service_contact_effort",
        }
    ),
    TeesAxis.EMOTION: frozenset(
        {
            "frustration",
            "anxiety",
            "satisfaction",
            "trust",
            "disappointment",
            "relief",
            "curiosity",
        }
    ),
    TeesAxis.SUCCESS: frozenset(
        {
            "goal_achieved",
            "goal_failed",
            "partial_success",
            "expectation_gap",
            "repurchase_intent",
            "recommendation_intent",
        }
    ),
}


class TeesAxisSignal(FrozenContractModel):
    axis: TeesAxis
    signal_type: str = Field(min_length=1)
    polarity: TeesSignalPolarity
    intensity: TeesIntensity
    quoted_summary: str | None = None
    evidence_refs: tuple[str, ...] = ()

    @field_validator("signal_type")
    @classmethod
    def _signal_type_is_allowed(cls, value: str, info) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("signal_type must not be blank")
        axis = info.data.get("axis")
        if isinstance(axis, TeesAxis) and normalized not in _ALLOWED_SIGNAL_TYPES[axis]:
            raise ValueError(f"Unsupported TEE/S signal_type for axis {axis.value}: {normalized}")
        return normalized

    @field_validator("quoted_summary")
    @classmethod
    def _quoted_summary_nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("quoted_summary must not be blank")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_refs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.EVIDENCE_REF)
            for value in values
        )


class TeesAssessment(FrozenContractModel):
    tees_assessment_id: str = Field(default_factory=new_tees_assessment_id)
    atomic_voc_revision_id: str
    analysis_run_id: str
    time_signals: tuple[TeesAxisSignal, ...] = ()
    effort_signals: tuple[TeesAxisSignal, ...] = ()
    emotion_signals: tuple[TeesAxisSignal, ...] = ()
    success_signals: tuple[TeesAxisSignal, ...] = ()
    confidence: float = Field(ge=0, le=1)
    source: TeesAssessmentSource
    evidence_refs: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    legacy_refs: tuple[str, ...] = ()

    @field_validator("tees_assessment_id")
    @classmethod
    def _tees_assessment_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.TEES_ASSESSMENT)

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

    @field_validator("time_signals")
    @classmethod
    def _time_signals_use_time_axis(cls, values: tuple[TeesAxisSignal, ...]) -> tuple[TeesAxisSignal, ...]:
        return _validate_axis_bucket(values, TeesAxis.TIME, "time_signals")

    @field_validator("effort_signals")
    @classmethod
    def _effort_signals_use_effort_axis(cls, values: tuple[TeesAxisSignal, ...]) -> tuple[TeesAxisSignal, ...]:
        return _validate_axis_bucket(values, TeesAxis.EFFORT, "effort_signals")

    @field_validator("emotion_signals")
    @classmethod
    def _emotion_signals_use_emotion_axis(cls, values: tuple[TeesAxisSignal, ...]) -> tuple[TeesAxisSignal, ...]:
        return _validate_axis_bucket(values, TeesAxis.EMOTION, "emotion_signals")

    @field_validator("success_signals")
    @classmethod
    def _success_signals_use_success_axis(cls, values: tuple[TeesAxisSignal, ...]) -> tuple[TeesAxisSignal, ...]:
        return _validate_axis_bucket(values, TeesAxis.SUCCESS, "success_signals")

    _created_at = field_validator("created_at")(_validate_timezone)


def _validate_axis_bucket(
    values: tuple[TeesAxisSignal, ...],
    expected_axis: TeesAxis,
    field_name: str,
) -> tuple[TeesAxisSignal, ...]:
    for signal in values:
        if signal.axis != expected_axis:
            raise ValueError(f"{field_name} only accepts {expected_axis.value} signals")
    return values
