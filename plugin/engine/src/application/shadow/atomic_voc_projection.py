"""Default-disabled shadow projection from legacy analysis rows to AtomicVocRevision.

This module intentionally does not persist, publish, or replace legacy outputs.
It only turns already-completed legacy analysis rows into in-memory canonical
contract objects when explicitly enabled.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from src.application.shadow.contracts import ShadowSidecarFailureLog
from src.domain.canonical_ids import (
    CanonicalIdPrefix,
)
from src.domain.digests import canonical_json_digest
from src.domain.runs import FrozenContractModel
from src.intelligence.atomic_voc import (
    AtomicVocRevision,
    AtomicVocRevisionReason,
    AtomicVocSpan,
)
from src.intelligence.cej import (
    CejAssessment,
    CejAssessmentSource,
    CejGateReason,
    CejStage,
    HsCejRollupStage,
)
from src.intelligence.evidence import (
    EvidenceKind,
    EvidenceRef,
    EvidenceSourceType,
    EvidenceSpan,
    EvidenceStrength,
)
from src.intelligence.improvement_candidate import (
    CandidateSource,
    CandidateStatus,
    ImprovementCandidate,
)
from src.intelligence.issue_cluster import (
    IssueCluster,
    IssueClusterSource,
    IssueClusterStatus,
)
from src.intelligence.practitioner_action import (
    PractitionerAction,
    PractitionerActionSource,
    PractitionerActionStatus,
)
from src.intelligence.root_cause import (
    RootCauseCategory,
    RootCauseHypothesis,
    RootCauseMaturity,
    RootCauseSource,
)
from src.intelligence.tees import (
    TeesAssessment,
    TeesAssessmentSource,
    TeesAxis,
    TeesAxisSignal,
    TeesIntensity,
    TeesSignalPolarity,
)

SHADOW_PROJECTION_CREATED_AT = datetime(1970, 1, 1, tzinfo=timezone.utc)

_TEES_EXPLICIT_FIELDS: dict[TeesAxis, tuple[str, ...]] = {
    TeesAxis.TIME: ("time_signals", "tees_time_signals", "tee_time", "time_signal", "time_friction"),
    TeesAxis.EFFORT: (
        "effort_signals",
        "tees_effort_signals",
        "tee_effort",
        "effort_signal",
        "effort_friction",
    ),
    TeesAxis.EMOTION: (
        "emotion_signals",
        "tees_emotion_signals",
        "tee_emotion",
        "emotion_signal",
        "emotion_friction",
    ),
    TeesAxis.SUCCESS: (
        "success_signals",
        "tees_success_signals",
        "tee_success",
        "success_signal",
        "success_outcome",
    ),
}

_TEES_ALLOWED_SIGNALS: dict[TeesAxis, tuple[str, ...]] = {
    TeesAxis.TIME: ("delay", "waiting", "repeated_attempts", "early_failure", "recurrence", "duration_burden"),
    TeesAxis.EFFORT: (
        "setup_difficulty",
        "usage_difficulty",
        "maintenance_burden",
        "troubleshooting_effort",
        "information_search_effort",
        "service_contact_effort",
    ),
    TeesAxis.EMOTION: (
        "frustration",
        "anxiety",
        "satisfaction",
        "trust",
        "disappointment",
        "relief",
        "curiosity",
    ),
    TeesAxis.SUCCESS: (
        "goal_achieved",
        "goal_failed",
        "partial_success",
        "expectation_gap",
        "repurchase_intent",
        "recommendation_intent",
    ),
}

_TEES_SIGNAL_ALIASES: dict[str, str] = {
    "repeat": "repeated_attempts",
    "retry": "repeated_attempts",
    "retries": "repeated_attempts",
    "early_failure": "early_failure",
    "early_fail": "early_failure",
    "takes_too_long": "duration_burden",
    "long_time": "duration_burden",
    "install": "setup_difficulty",
    "installation": "setup_difficulty",
    "hard_to_use": "usage_difficulty",
    "confusing": "usage_difficulty",
    "cleaning": "maintenance_burden",
    "maintenance": "maintenance_burden",
    "troubleshooting": "troubleshooting_effort",
    "repair": "troubleshooting_effort",
    "manual": "information_search_effort",
    "guide": "information_search_effort",
    "service": "service_contact_effort",
    "support": "service_contact_effort",
    "annoyance": "frustration",
    "annoyed": "frustration",
    "worry": "anxiety",
    "worried": "anxiety",
    "happy": "satisfaction",
    "satisfied": "satisfaction",
    "reliable": "trust",
    "disappointed": "disappointment",
    "reassured": "relief",
    "question": "curiosity",
    "works": "goal_achieved",
    "worked": "goal_achieved",
    "solved": "goal_achieved",
    "failed": "goal_failed",
    "failure": "goal_failed",
    "not_working": "goal_failed",
    "sometimes": "partial_success",
    "partial": "partial_success",
    "expectation": "expectation_gap",
    "repurchase": "repurchase_intent",
    "recommend": "recommendation_intent",
}

_TEES_KEYWORD_SIGNALS: dict[TeesAxis, tuple[tuple[str, tuple[str, ...]], ...]] = {
    TeesAxis.TIME: (
        ("delay", ("delay", "delayed", "late")),
        ("waiting", ("wait", "waiting")),
        ("repeated_attempts", ("repeat", "repeated", "retry", "again")),
        ("early_failure", ("early failure", "broke soon", "failed soon")),
        ("recurrence", ("recurring", "recurrence", "again and again")),
        ("duration_burden", ("takes too long", "long time", "too long")),
    ),
    TeesAxis.EFFORT: (
        ("setup_difficulty", ("install", "installation", "setup difficulty", "difficult setup")),
        ("usage_difficulty", ("hard to use", "confusing", "difficult to use")),
        ("maintenance_burden", ("cleaning", "maintenance", "maintain")),
        ("troubleshooting_effort", ("troubleshoot", "error", "repair", "fix")),
        ("information_search_effort", ("manual", "guide", "instruction")),
        ("service_contact_effort", ("service center", "customer service", "contact support")),
    ),
    TeesAxis.EMOTION: (
        ("frustration", ("frustrated", "annoying", "annoyed")),
        ("anxiety", ("worried", "anxious", "worry")),
        ("satisfaction", ("satisfied", "love", "good")),
        ("trust", ("trust", "reliable")),
        ("disappointment", ("disappointed", "disappointing")),
        ("relief", ("relief", "relieved")),
        ("curiosity", ("curious", "question", "wonder")),
    ),
    TeesAxis.SUCCESS: (
        ("goal_achieved", ("works well", "worked", "solved", "success")),
        ("goal_failed", ("does not work", "not working", "fail", "failed")),
        ("partial_success", ("partially", "sometimes")),
        ("expectation_gap", ("expected", "expectation", "not as expected")),
        ("repurchase_intent", ("repurchase", "buy again")),
        ("recommendation_intent", ("recommend", "recommendation")),
    ),
}

_TEES_KO_PRODUCT_EMOTION_KEYWORD_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("frustration", ("불만", "불편", "짜증", "답답", "안 보", "안보", "안 보여", "별로", "비추", "문제", "안됨", "안 됨")),
    ("anxiety", ("걱정", "불안", "찝찝", "무섭", "위험", "안전", "유해")),
    (
        "satisfaction",
        ("만족", "좋아보", "좋아 보", "좋더", "편하", "잘되", "잘 되", "깨끗", "광택", "추천", "최고", "사고 싶", "사고싶"),
    ),
    ("disappointment", ("아쉽", "실망")),
)

_PRODUCT_EXPERIENCE_CONTEXT_KEYWORDS = (
    "제품",
    "식세기",
    "식기세척",
    "건조기",
    "세탁기",
    "워시타워",
    "드럼",
    "통돌이",
    "세척",
    "건조",
    "버튼",
    "세제",
    "젖병",
    "필터",
    "냄새",
    "소음",
    "설치",
    "수리",
    "a/s",
    "as",
    "성능",
    "기능",
    "가격",
    "구매",
    "사용",
    "관리",
    "청소",
    "고장",
    "불량",
    "애벌",
    "광택",
)

_CONTENT_ONLY_CONTEXT_KEYWORDS = ("영상", "유튜버", "채널", "목소리", "설명", "편집")
_CONTENT_ONLY_AFFECT_KEYWORDS = ("감사", "잘 봤", "잘봤", "좋은 영상", "설명 좋", "목소리 좋")
_OTHER_PERSON_USAGE_BLAME_KEYWORDS = ("사람", "사람들", "남들", "왜")
_OTHER_PERSON_USAGE_ACTION_KEYWORDS = ("안 씻", "안씻", "안 닦", "안닦", "안 헹", "안헹", "흐르는", "더럽", "드럽", "기본")

_CEJ_COMPOSITE_STAGE_BUCKETS: dict[str, tuple[CejStage, ...]] = {
    "관리교체": (CejStage.MANAGEMENT, CejStage.REPLACEMENT),
}

_TEES_KO_PRODUCT_EMOTION_KEYWORD_EXTENSIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Narrow product/CEJ emotion markers approved after Golden120 review.
    # Keep generic question marks and curiosity-only wording out of runtime Emotion.
    ("anxiety", ("후회", "위생안좋", "위생 안좋", "전기세 겁나")),
    ("frustration", ("왜 안썼", "왜 안 써", "된것도아니고", "된 것도 아니고")),
)

_TEES_POSITIVE_SIGNALS = frozenset(
    {
        "satisfaction",
        "trust",
        "relief",
        "goal_achieved",
        "repurchase_intent",
        "recommendation_intent",
    }
)
_TEES_MIXED_SIGNALS = frozenset({"partial_success"})

_ROOT_CAUSE_TEXT_FIELDS = (
    "root_cause_hypothesis",
    "root_cause_text",
    "cause_hypothesis",
    "cause_reason",
    "reasoning",
)
_ROOT_CAUSE_CATEGORY_FIELDS = ("root_cause_category", "cause_category", "cause_type")
_ROOT_CAUSE_MATURITY_FIELDS = ("root_cause_maturity", "cause_maturity", "maturity")

_ROOT_CAUSE_CATEGORY_ALIASES: dict[str, RootCauseCategory] = {
    "product_design": RootCauseCategory.PRODUCT_DESIGN,
    "design": RootCauseCategory.PRODUCT_DESIGN,
    "usability": RootCauseCategory.USABILITY,
    "usage": RootCauseCategory.USABILITY,
    "installation_setup": RootCauseCategory.INSTALLATION_SETUP,
    "installation": RootCauseCategory.INSTALLATION_SETUP,
    "setup": RootCauseCategory.INSTALLATION_SETUP,
    "documentation_guidance": RootCauseCategory.DOCUMENTATION_GUIDANCE,
    "documentation": RootCauseCategory.DOCUMENTATION_GUIDANCE,
    "guidance": RootCauseCategory.DOCUMENTATION_GUIDANCE,
    "manual": RootCauseCategory.DOCUMENTATION_GUIDANCE,
    "service_support": RootCauseCategory.SERVICE_SUPPORT,
    "service": RootCauseCategory.SERVICE_SUPPORT,
    "support": RootCauseCategory.SERVICE_SUPPORT,
    "expectation_gap": RootCauseCategory.EXPECTATION_GAP,
    "expectation": RootCauseCategory.EXPECTATION_GAP,
    "compatibility_environment": RootCauseCategory.COMPATIBILITY_ENVIRONMENT,
    "compatibility": RootCauseCategory.COMPATIBILITY_ENVIRONMENT,
    "environment": RootCauseCategory.COMPATIBILITY_ENVIRONMENT,
    "durability_reliability": RootCauseCategory.DURABILITY_RELIABILITY,
    "durability": RootCauseCategory.DURABILITY_RELIABILITY,
    "reliability": RootCauseCategory.DURABILITY_RELIABILITY,
    "pricing_value": RootCauseCategory.PRICING_VALUE,
    "pricing": RootCauseCategory.PRICING_VALUE,
    "value": RootCauseCategory.PRICING_VALUE,
    "unclear": RootCauseCategory.UNCLEAR,
    "unknown": RootCauseCategory.UNCLEAR,
}

_ROOT_CAUSE_CATEGORY_KEYWORDS: tuple[tuple[RootCauseCategory, tuple[str, ...]], ...] = (
    (RootCauseCategory.INSTALLATION_SETUP, ("install", "installation", "setup difficulty", "difficult setup")),
    (RootCauseCategory.DOCUMENTATION_GUIDANCE, ("manual", "guide", "instruction", "unclear guide")),
    (RootCauseCategory.SERVICE_SUPPORT, ("service center", "customer service", "contact support", "repair")),
    (RootCauseCategory.DURABILITY_RELIABILITY, ("early failure", "broke soon", "failed soon", "not working")),
    (RootCauseCategory.USABILITY, ("hard to use", "confusing", "difficult to use")),
    (RootCauseCategory.EXPECTATION_GAP, ("expected", "expectation", "not as expected")),
    (RootCauseCategory.PRICING_VALUE, ("price", "expensive", "value")),
    (RootCauseCategory.COMPATIBILITY_ENVIRONMENT, ("compatible", "compatibility", "environment")),
    (RootCauseCategory.PRODUCT_DESIGN, ("design", "noise", "too loud")),
)

_ISSUE_GROUP_FIELDS = (
    "issue_label",
    "normalized_issue_label",
    "topic_label",
    "topic",
    "topic_name",
    "feature",
    "feature_name",
    "feature_id",
)


class AtomicVocShadowProjectionSettings(FrozenContractModel):
    enabled: bool = False


class AtomicVocShadowProjectionResult(FrozenContractModel):
    enabled: bool = False
    revisions: tuple[AtomicVocRevision, ...] = ()
    evidence_refs: tuple[EvidenceRef, ...] = ()
    cej_assessments: tuple[CejAssessment, ...] = ()
    tees_assessments: tuple[TeesAssessment, ...] = ()
    root_cause_hypotheses: tuple[RootCauseHypothesis, ...] = ()
    issue_clusters: tuple[IssueCluster, ...] = ()
    improvement_candidates: tuple[ImprovementCandidate, ...] = ()
    practitioner_actions: tuple[PractitionerAction, ...] = ()
    warnings: tuple[ShadowSidecarFailureLog, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


def project_legacy_analysis_to_atomic_voc_revisions(
    *,
    legacy_rows: object,
    analysis_run_id: str,
    collection_run_id: str | None = None,
    raw_source_snapshot_id: str | None = None,
    settings: AtomicVocShadowProjectionSettings | None = None,
) -> AtomicVocShadowProjectionResult:
    """Project completed legacy analysis rows into in-memory AtomicVocRevision objects."""

    effective_settings = settings or AtomicVocShadowProjectionSettings()
    if not effective_settings.enabled:
        return AtomicVocShadowProjectionResult(enabled=False)

    records = _records_from_legacy_output(legacy_rows)
    lineage_payload = {"analysis_run_id": analysis_run_id, "records": records}
    effective_collection_run_id = collection_run_id or _deterministic_canonical_id(
        CanonicalIdPrefix.COLLECTION_RUN,
        {**lineage_payload, "lineage": "collection"},
    )
    effective_raw_snapshot_id = raw_source_snapshot_id or _deterministic_canonical_id(
        CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT,
        {**lineage_payload, "lineage": "raw_snapshot"},
    )
    projections = tuple(
        _projection_from_record(
            record,
            row_index=index,
            analysis_run_id=analysis_run_id,
            collection_run_id=effective_collection_run_id,
            raw_source_snapshot_id=effective_raw_snapshot_id,
        )
        for index, record in enumerate(records)
    )
    revisions = tuple(projection[0] for projection in projections)
    evidence_refs = tuple(projection[1] for projection in projections)
    cej_assessments = tuple(projection[2] for projection in projections)
    tees_assessments = tuple(projection[3] for projection in projections)
    root_cause_hypotheses = tuple(projection[4] for projection in projections)
    cej_bridge_diagnostics = tuple(
        _cej_bridge_diagnostic(record, cej_assessment, row_index=index)
        for index, (record, cej_assessment) in enumerate(zip(records, cej_assessments, strict=True))
    )
    cej_bridge_diagnostic_counts: dict[str, int] = {}
    for diagnostic in cej_bridge_diagnostics:
        status = str(diagnostic["status"])
        cej_bridge_diagnostic_counts[status] = cej_bridge_diagnostic_counts.get(status, 0) + 1
    tees_emotion_policy_diagnostics = tuple(
        _tees_emotion_policy_diagnostic(record, tees_assessment, row_index=index)
        for index, (record, tees_assessment) in enumerate(zip(records, tees_assessments, strict=True))
    )
    tees_emotion_policy_counts: dict[str, int] = {}
    for diagnostic in tees_emotion_policy_diagnostics:
        status = str(diagnostic["status"])
        tees_emotion_policy_counts[status] = tees_emotion_policy_counts.get(status, 0) + 1
    issue_clusters = _issue_clusters_from_projections(
        records=records,
        revisions=revisions,
        evidence_refs=evidence_refs,
        cej_assessments=cej_assessments,
        root_cause_hypotheses=root_cause_hypotheses,
        analysis_run_id=analysis_run_id,
    )
    improvement_candidates = _improvement_candidates_from_issue_clusters(
        issue_clusters=issue_clusters,
        analysis_run_id=analysis_run_id,
    )
    practitioner_actions = _practitioner_actions_from_candidates(
        improvement_candidates=improvement_candidates,
        analysis_run_id=analysis_run_id,
    )
    return AtomicVocShadowProjectionResult(
        enabled=True,
        revisions=revisions,
        evidence_refs=evidence_refs,
        cej_assessments=cej_assessments,
        tees_assessments=tees_assessments,
        root_cause_hypotheses=root_cause_hypotheses,
        issue_clusters=issue_clusters,
        improvement_candidates=improvement_candidates,
        practitioner_actions=practitioner_actions,
        metadata={
            "legacy_row_count": len(records),
            "projected_revision_count": len(revisions),
            "projected_evidence_ref_count": len(evidence_refs),
            "projected_cej_assessment_count": len(cej_assessments),
            "projected_tees_assessment_count": len(tees_assessments),
            "projected_root_cause_hypothesis_count": len(root_cause_hypotheses),
            "projected_issue_cluster_count": len(issue_clusters),
            "projected_improvement_candidate_count": len(improvement_candidates),
            "projected_practitioner_action_count": len(practitioner_actions),
            "cej_bridge_diagnostic_counts": dict(sorted(cej_bridge_diagnostic_counts.items())),
            "cej_bridge_diagnostics": cej_bridge_diagnostics,
            "tees_emotion_policy_counts": dict(sorted(tees_emotion_policy_counts.items())),
            "tees_emotion_policy_diagnostics": tees_emotion_policy_diagnostics,
        },
    )


def project_legacy_analysis_safely(
    *,
    legacy_rows: object,
    analysis_run_id: str,
    logger: logging.Logger,
    collection_run_id: str | None = None,
    raw_source_snapshot_id: str | None = None,
    settings: AtomicVocShadowProjectionSettings | None = None,
    legacy_run_id: str | None = None,
) -> AtomicVocShadowProjectionResult:
    """Project shadow revisions without interrupting authoritative legacy execution."""

    effective_settings = settings or AtomicVocShadowProjectionSettings()
    try:
        return project_legacy_analysis_to_atomic_voc_revisions(
            legacy_rows=legacy_rows,
            analysis_run_id=analysis_run_id,
            collection_run_id=collection_run_id,
            raw_source_snapshot_id=raw_source_snapshot_id,
            settings=effective_settings,
        )
    except Exception as exc:
        failure = ShadowSidecarFailureLog.from_exception(
            operation="atomic_voc_shadow_projection",
            error=exc,
            legacy_run_id=legacy_run_id,
            details={
                "analysis_run_id": analysis_run_id,
                "collection_run_id": collection_run_id,
                "raw_source_snapshot_id": raw_source_snapshot_id,
            },
        )
        logger.warning(
            "AtomicVoc shadow projection failed",
            extra={"shadow_failure": failure.model_dump(mode="json")},
        )
        return AtomicVocShadowProjectionResult(enabled=effective_settings.enabled, warnings=(failure,))


def _records_from_legacy_output(legacy_rows: object) -> tuple[Mapping[str, Any], ...]:
    if legacy_rows is None:
        return ()
    if hasattr(legacy_rows, "to_dict"):
        records = legacy_rows.to_dict("records")  # pandas-compatible without importing pandas
    elif isinstance(legacy_rows, Mapping):
        records = (legacy_rows,)
    else:
        records = tuple(legacy_rows) if isinstance(legacy_rows, Iterable) else ()

    normalized: list[Mapping[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("Legacy analysis rows must be mapping-like records")
        normalized.append(record)
    return tuple(normalized)


def _projection_from_record(
    record: Mapping[str, Any],
    *,
    row_index: int,
    analysis_run_id: str,
    collection_run_id: str,
    raw_source_snapshot_id: str,
) -> tuple[AtomicVocRevision, EvidenceRef, CejAssessment, TeesAssessment, RootCauseHypothesis]:
    text_field, text_excerpt = _first_nonblank_field(
        record,
        (
            "text_excerpt",
            "opinion_text",
            "atomic_text",
            "comment_text",
            "text_display",
            "cleaned_text",
            "normalized_text",
        ),
    )
    normalized_text = _first_nonblank_value(record, ("normalized_text", "cleaned_text", text_field)) or text_excerpt
    language = _first_nonblank_value(record, ("language", "language_detected")) or "ko"
    country = _first_nonblank_value(record, ("country", "region")) or "KR"
    product_category = _first_nonblank_value(record, ("product_category", "product"))
    product_family = _first_nonblank_value(record, ("product_family",))
    source_id = _source_id(record, row_index=row_index)
    legacy_refs = _legacy_refs(record)
    identity_payload = {
        "analysis_run_id": analysis_run_id,
        "raw_source_snapshot_id": raw_source_snapshot_id,
        "row_index": row_index,
        "source_id": source_id,
        "source_field": text_field,
        "text_excerpt": text_excerpt,
    }
    atomic_voc_id = _deterministic_canonical_id(CanonicalIdPrefix.ATOMIC_VOC, identity_payload)
    atomic_voc_revision_id = _deterministic_canonical_id(
        CanonicalIdPrefix.ATOMIC_VOC_REVISION,
        {**identity_payload, "revision_number": 1},
    )
    evidence_ref_id = _deterministic_canonical_id(
        CanonicalIdPrefix.EVIDENCE_REF,
        {**identity_payload, "evidence_kind": EvidenceKind.DIRECT.value},
    )
    cej_assessment_id = _deterministic_canonical_id(
        CanonicalIdPrefix.CEJ_ASSESSMENT,
        {**identity_payload, "attachment": "cej"},
    )
    tees_assessment_id = _deterministic_canonical_id(
        CanonicalIdPrefix.TEES_ASSESSMENT,
        {**identity_payload, "attachment": "tees"},
    )
    root_cause_hypothesis_id = _deterministic_canonical_id(
        CanonicalIdPrefix.ROOT_CAUSE_HYPOTHESIS,
        {**identity_payload, "attachment": "root_cause"},
    )
    atomic_span = AtomicVocSpan(
        source_field=text_field,
        start_char=0,
        end_char=len(text_excerpt),
        quoted_text=text_excerpt,
        extraction_method="legacy_analysis_shadow_projection",
    )
    evidence_span = EvidenceSpan(
        source_field=text_field,
        start_char=0,
        end_char=len(text_excerpt),
        quoted_text=text_excerpt,
    )
    revision = AtomicVocRevision(
        atomic_voc_revision_id=atomic_voc_revision_id,
        atomic_voc_id=atomic_voc_id,
        analysis_run_id=analysis_run_id,
        revision_number=1,
        revision_reason=AtomicVocRevisionReason.INITIAL_EXTRACTION,
        text_excerpt=text_excerpt,
        normalized_text=normalized_text,
        language=language,
        country=country,
        product_category=product_category,
        product_family=product_family,
        feature_refs=_string_tuple(record.get("feature_refs")),
        evidence_refs=(evidence_ref_id,),
        spans=(atomic_span,),
        created_at=SHADOW_PROJECTION_CREATED_AT,
        legacy_refs=legacy_refs,
        metadata={"shadow_projection": "atomic_voc_revision_v1"},
    )
    evidence_ref = EvidenceRef(
        evidence_ref_id=evidence_ref_id,
        atomic_voc_id=atomic_voc_id,
        atomic_voc_revision_id=atomic_voc_revision_id,
        raw_source_snapshot_id=raw_source_snapshot_id,
        collection_run_id=collection_run_id,
        analysis_run_id=analysis_run_id,
        source_type=_evidence_source_type(record),
        source_id=source_id,
        source_field=text_field,
        span=evidence_span,
        quoted_text=text_excerpt,
        normalized_quote=normalized_text,
        evidence_kind=EvidenceKind.DIRECT,
        evidence_strength=EvidenceStrength.STRONG,
        language=language,
        created_at=SHADOW_PROJECTION_CREATED_AT,
        legacy_refs=legacy_refs,
    )
    cej_assessment = _cej_assessment_from_record(
        record,
        cej_assessment_id=cej_assessment_id,
        atomic_voc_revision_id=atomic_voc_revision_id,
        analysis_run_id=analysis_run_id,
        evidence_ref_id=evidence_ref_id,
        legacy_refs=legacy_refs,
    )
    tees_assessment = _tees_assessment_from_record(
        record,
        tees_assessment_id=tees_assessment_id,
        atomic_voc_revision_id=atomic_voc_revision_id,
        analysis_run_id=analysis_run_id,
        evidence_ref_id=evidence_ref_id,
        text_excerpt=text_excerpt,
        legacy_refs=legacy_refs,
    )
    root_cause_hypothesis = _root_cause_hypothesis_from_record(
        record,
        root_cause_hypothesis_id=root_cause_hypothesis_id,
        atomic_voc_revision_id=atomic_voc_revision_id,
        analysis_run_id=analysis_run_id,
        evidence_ref_id=evidence_ref_id,
        text_excerpt=text_excerpt,
        legacy_refs=legacy_refs,
    )
    return revision, evidence_ref, cej_assessment, tees_assessment, root_cause_hypothesis


def _first_nonblank_field(record: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[str, str]:
    for field in fields:
        value = _string_or_none(record.get(field))
        if value:
            return field, value
    raise ValueError("Legacy analysis row does not contain projectable text")


def _first_nonblank_value(record: Mapping[str, Any], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        value = _string_or_none(record.get(field))
        if value:
            return value
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split("|") if part.strip())
    if isinstance(value, Iterable):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _source_id(record: Mapping[str, Any], *, row_index: int) -> str:
    return (
        _first_nonblank_value(record, ("source_content_id", "comment_id", "opinion_id", "video_id"))
        or f"legacy-row-{row_index}"
    )


def _evidence_source_type(record: Mapping[str, Any]) -> EvidenceSourceType:
    is_reply = _string_or_none(record.get("is_reply"))
    if is_reply and is_reply.lower() in {"true", "1", "yes"}:
        return EvidenceSourceType.REPLY
    return EvidenceSourceType.COMMENT


def _cej_assessment_from_record(
    record: Mapping[str, Any],
    *,
    cej_assessment_id: str,
    atomic_voc_revision_id: str,
    analysis_run_id: str,
    evidence_ref_id: str,
    legacy_refs: tuple[str, ...],
) -> CejAssessment:
    experience_stage = _stage_from_fields(
        record,
        (
            "journey_stage_experience",
            "journey_stage_pre_gate",
            "customer_journey_stage",
            "cej_scene_code",
            "journey_stage",
        ),
    )
    actionable_stage = _stage_from_fields(record, ("journey_stage_actionable",))
    pre_gate_stage = _stage_from_fields(
        record,
        (
            "journey_stage_pre_gate",
            "journey_stage_experience",
            "customer_journey_stage",
            "cej_scene_code",
        ),
    )
    gate_reason = _gate_reason_from_record(
        record,
        experience_stage=experience_stage,
        actionable_stage=actionable_stage,
        pre_gate_stage=pre_gate_stage,
    )
    return CejAssessment(
        cej_assessment_id=cej_assessment_id,
        atomic_voc_revision_id=atomic_voc_revision_id,
        analysis_run_id=analysis_run_id,
        experience_stage=experience_stage,
        actionable_stage=actionable_stage,
        pre_gate_stage=pre_gate_stage,
        hs_rollup_stage=_hs_rollup_stage(experience_stage or actionable_stage or pre_gate_stage),
        gate_reason=gate_reason,
        confidence=_confidence(record),
        source=CejAssessmentSource.LEGACY_COMMENT_TRUTH,
        evidence_refs=(evidence_ref_id,),
        created_at=SHADOW_PROJECTION_CREATED_AT,
        legacy_refs=legacy_refs + _cej_legacy_refs(record),
    )


def _tees_assessment_from_record(
    record: Mapping[str, Any],
    *,
    tees_assessment_id: str,
    atomic_voc_revision_id: str,
    analysis_run_id: str,
    evidence_ref_id: str,
    text_excerpt: str,
    legacy_refs: tuple[str, ...],
) -> TeesAssessment:
    time_signals = _tees_axis_signals(record, TeesAxis.TIME, evidence_ref_id, text_excerpt)
    effort_signals = _tees_axis_signals(record, TeesAxis.EFFORT, evidence_ref_id, text_excerpt)
    emotion_signals = _tees_axis_signals(record, TeesAxis.EMOTION, evidence_ref_id, text_excerpt)
    success_signals = _tees_axis_signals(record, TeesAxis.SUCCESS, evidence_ref_id, text_excerpt)
    has_signals = any((time_signals, effort_signals, emotion_signals, success_signals))
    return TeesAssessment(
        tees_assessment_id=tees_assessment_id,
        atomic_voc_revision_id=atomic_voc_revision_id,
        analysis_run_id=analysis_run_id,
        time_signals=time_signals,
        effort_signals=effort_signals,
        emotion_signals=emotion_signals,
        success_signals=success_signals,
        confidence=_confidence(record),
        source=TeesAssessmentSource.LEGACY_COMMENT_TRUTH,
        evidence_refs=(evidence_ref_id,) if has_signals else (),
        created_at=SHADOW_PROJECTION_CREATED_AT,
        legacy_refs=legacy_refs + _tees_legacy_refs(record),
    )


def _tees_axis_signals(
    record: Mapping[str, Any],
    axis: TeesAxis,
    evidence_ref_id: str,
    text_excerpt: str,
) -> tuple[TeesAxisSignal, ...]:
    explicit_signal_types = _explicit_tees_signal_types(record, axis)
    signal_types = explicit_signal_types
    if not _has_explicit_tees_value(record, axis):
        signal_types = _keyword_tees_signal_types(record, axis)
    return tuple(
        TeesAxisSignal(
            axis=axis,
            signal_type=signal_type,
            polarity=_tees_signal_polarity(signal_type),
            intensity=_tees_signal_intensity(record),
            quoted_summary=text_excerpt,
            evidence_refs=(evidence_ref_id,),
        )
        for signal_type in signal_types
    )


def _explicit_tees_signal_types(record: Mapping[str, Any], axis: TeesAxis) -> tuple[str, ...]:
    signal_types: list[str] = []
    for field in _TEES_EXPLICIT_FIELDS[axis]:
        for token in _tees_tokens(record.get(field)):
            normalized = _normalize_tees_signal(token, axis)
            if normalized is not None and normalized not in signal_types:
                signal_types.append(normalized)
    return tuple(signal_types)


def _keyword_tees_signal_types(record: Mapping[str, Any], axis: TeesAxis) -> tuple[str, ...]:
    text = " ".join(
        value
        for value in (
            _first_nonblank_value(record, ("opinion_text", "text_excerpt", "comment_text", "text_display")),
            _first_nonblank_value(record, ("cleaned_text", "normalized_text", "atomic_text")),
        )
        if value
    ).lower()
    if not text:
        return ()
    signal_types: list[str] = []
    for signal_type, keywords in _TEES_KEYWORD_SIGNALS[axis]:
        if any(keyword in text for keyword in keywords) and signal_type not in signal_types:
            signal_types.append(signal_type)
    if axis == TeesAxis.EMOTION:
        for signal_type in _ko_product_experience_emotion_signal_types(record, text):
            if signal_type not in signal_types:
                signal_types.append(signal_type)
    return tuple(signal_types)


def _ko_product_experience_emotion_signal_types(record: Mapping[str, Any], text: str) -> tuple[str, ...]:
    if not _has_product_experience_emotion_context(record, text):
        return ()
    if _is_other_person_usage_habit_blame(text):
        return ()
    signal_types: list[str] = []
    for signal_type, keywords in (
        _TEES_KO_PRODUCT_EMOTION_KEYWORD_SIGNALS
        + _TEES_KO_PRODUCT_EMOTION_KEYWORD_EXTENSIONS
    ):
        if any(keyword in text for keyword in keywords) and signal_type not in signal_types:
            signal_types.append(signal_type)
    return tuple(signal_types)


def _has_product_experience_emotion_context(record: Mapping[str, Any], text: str) -> bool:
    if _is_content_only_reaction(text):
        return False
    has_product_field = any(
        _string_or_none(record.get(field))
        for field in ("product", "product_category", "product_family", "artifact_product_value")
    )
    return has_product_field or any(keyword in text for keyword in _PRODUCT_EXPERIENCE_CONTEXT_KEYWORDS)


def _is_content_only_reaction(text: str) -> bool:
    has_content_context = any(keyword in text for keyword in _CONTENT_ONLY_CONTEXT_KEYWORDS)
    has_content_affect = any(keyword in text for keyword in _CONTENT_ONLY_AFFECT_KEYWORDS)
    has_product_context = any(keyword in text for keyword in _PRODUCT_EXPERIENCE_CONTEXT_KEYWORDS)
    return has_content_context and has_content_affect and not has_product_context


def _is_other_person_usage_habit_blame(text: str) -> bool:
    has_other_person = any(keyword in text for keyword in _OTHER_PERSON_USAGE_BLAME_KEYWORDS)
    has_usage_action = any(keyword in text for keyword in _OTHER_PERSON_USAGE_ACTION_KEYWORDS)
    has_product_issue = any(keyword in text for keyword in ("버튼", "고장", "불량", "냄새", "소음", "성능", "안 보", "안보"))
    return has_other_person and has_usage_action and not has_product_issue


def _tees_emotion_policy_diagnostic(
    record: Mapping[str, Any],
    assessment: TeesAssessment,
    *,
    row_index: int,
) -> dict[str, Any]:
    text = " ".join(
        value
        for value in (
            _first_nonblank_value(record, ("opinion_text", "text_excerpt", "comment_text", "text_display")),
            _first_nonblank_value(record, ("cleaned_text", "normalized_text", "atomic_text")),
        )
        if value
    ).lower()
    actual_signals = tuple(signal.signal_type for signal in assessment.emotion_signals)
    explicit = _has_explicit_tees_value(record, TeesAxis.EMOTION)
    exclusion_reason = None
    if text and _is_content_only_reaction(text):
        exclusion_reason = "content_only_reaction"
    elif text and _is_other_person_usage_habit_blame(text):
        exclusion_reason = "other_person_usage_habit_blame"
    if actual_signals:
        status = "explicit_emotion_preserved" if explicit else "product_experience_keyword_applied"
    elif exclusion_reason:
        status = f"diagnostic_excluded_{exclusion_reason}"
    elif text and _has_product_experience_emotion_context(record, text):
        status = "product_context_no_emotion_signal"
    else:
        status = "no_product_emotion_context"
    return {
        "row_index": row_index,
        "source_id": _source_id(record, row_index=row_index),
        "status": status,
        "emotion_signals": actual_signals,
        "explicit_emotion_source": explicit,
        "exclusion_reason": exclusion_reason,
        "policy_scope": "contract_supported_product_experience_emotion_only",
    }


def _has_explicit_tees_value(record: Mapping[str, Any], axis: TeesAxis) -> bool:
    return any(_tees_tokens(record.get(field)) for field in _TEES_EXPLICIT_FIELDS[axis])


def _tees_tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        normalized = value.replace("|", ",").replace(";", ",").replace("/", ",")
        return tuple(part.strip() for part in normalized.split(",") if part.strip())
    if isinstance(value, Iterable):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _normalize_tees_signal(value: Any, axis: TeesAxis) -> str | None:
    text = _string_or_none(value)
    if text is None:
        return None
    normalized = text.lower().replace("-", "_").replace(" ", "_").strip("_")
    aliased = _TEES_SIGNAL_ALIASES.get(normalized, normalized)
    if aliased in _TEES_ALLOWED_SIGNALS[axis]:
        return aliased
    return None


def _tees_signal_polarity(signal_type: str) -> TeesSignalPolarity:
    if signal_type in _TEES_POSITIVE_SIGNALS:
        return TeesSignalPolarity.POSITIVE
    if signal_type in _TEES_MIXED_SIGNALS:
        return TeesSignalPolarity.MIXED
    return TeesSignalPolarity.NEGATIVE


def _tees_signal_intensity(record: Mapping[str, Any]) -> TeesIntensity:
    explicit = _first_nonblank_value(record, ("tees_intensity", "signal_intensity", "intensity"))
    if explicit:
        try:
            return TeesIntensity(explicit.lower())
        except ValueError:
            pass
    return TeesIntensity.MEDIUM


def _root_cause_hypothesis_from_record(
    record: Mapping[str, Any],
    *,
    root_cause_hypothesis_id: str,
    atomic_voc_revision_id: str,
    analysis_run_id: str,
    evidence_ref_id: str,
    text_excerpt: str,
    legacy_refs: tuple[str, ...],
) -> RootCauseHypothesis:
    explicit_text = _first_nonblank_value(record, _ROOT_CAUSE_TEXT_FIELDS)
    category = _root_cause_category(record, text_excerpt)
    maturity = _root_cause_maturity(record, has_explicit_text=explicit_text is not None, category=category)
    has_hypothesis_signal = explicit_text is not None or category != RootCauseCategory.UNCLEAR
    hypothesis_text = explicit_text or _root_cause_default_text(category)
    return RootCauseHypothesis(
        root_cause_hypothesis_id=root_cause_hypothesis_id,
        atomic_voc_revision_id=atomic_voc_revision_id,
        analysis_run_id=analysis_run_id,
        hypothesis_text=hypothesis_text,
        cause_category=category,
        maturity=maturity,
        confidence=_root_cause_confidence(record, maturity),
        evidence_refs=(evidence_ref_id,) if has_hypothesis_signal else (),
        counter_evidence_refs=(),
        source=RootCauseSource.RULE,
        created_at=SHADOW_PROJECTION_CREATED_AT,
        legacy_refs=legacy_refs + _root_cause_legacy_refs(record),
    )


def _root_cause_category(record: Mapping[str, Any], text_excerpt: str) -> RootCauseCategory:
    for field in _ROOT_CAUSE_CATEGORY_FIELDS:
        category = _normalize_root_cause_category(record.get(field))
        if category is not None:
            return category
    text = " ".join(
        value
        for value in (
            text_excerpt,
            _first_nonblank_value(record, ("cleaned_text", "normalized_text", "atomic_text")),
        )
        if value
    ).lower()
    for category, keywords in _ROOT_CAUSE_CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return RootCauseCategory.UNCLEAR


def _normalize_root_cause_category(value: Any) -> RootCauseCategory | None:
    text = _string_or_none(value)
    if text is None:
        return None
    normalized = text.lower().replace("-", "_").replace(" ", "_").replace("/", "_").strip("_")
    return _ROOT_CAUSE_CATEGORY_ALIASES.get(normalized)


def _root_cause_maturity(
    record: Mapping[str, Any],
    *,
    has_explicit_text: bool,
    category: RootCauseCategory,
) -> RootCauseMaturity:
    for field in _ROOT_CAUSE_MATURITY_FIELDS:
        value = _string_or_none(record.get(field))
        if value:
            normalized = value.lower().strip()
            if normalized == RootCauseMaturity.LIKELY.value:
                return RootCauseMaturity.LIKELY
            if normalized == RootCauseMaturity.POSSIBLE.value:
                return RootCauseMaturity.POSSIBLE
            if normalized == RootCauseMaturity.UNKNOWN.value:
                return RootCauseMaturity.UNKNOWN
            return RootCauseMaturity.UNKNOWN
    if has_explicit_text:
        return RootCauseMaturity.POSSIBLE
    if category != RootCauseCategory.UNCLEAR:
        return RootCauseMaturity.POSSIBLE
    return RootCauseMaturity.UNKNOWN


def _root_cause_default_text(category: RootCauseCategory) -> str:
    if category == RootCauseCategory.UNCLEAR:
        return "Root cause is unclear from legacy analysis output."
    label = category.value.replace("_", " ")
    return f"Legacy analysis suggests a possible {label} driver."


def _root_cause_confidence(record: Mapping[str, Any], maturity: RootCauseMaturity) -> float:
    explicit = _confidence(record)
    if maturity == RootCauseMaturity.UNKNOWN:
        return min(explicit, 0.5)
    if maturity == RootCauseMaturity.POSSIBLE:
        return min(explicit, 0.65)
    return min(explicit, 0.8)


def _issue_clusters_from_projections(
    *,
    records: tuple[Mapping[str, Any], ...],
    revisions: tuple[AtomicVocRevision, ...],
    evidence_refs: tuple[EvidenceRef, ...],
    cej_assessments: tuple[CejAssessment, ...],
    root_cause_hypotheses: tuple[RootCauseHypothesis, ...],
    analysis_run_id: str,
) -> tuple[IssueCluster, ...]:
    grouped_indexes: dict[tuple[str, ...], list[int]] = {}
    for index, record in enumerate(records):
        key = _issue_cluster_key(
            record=record,
            revision=revisions[index],
            cej_assessment=cej_assessments[index],
            root_cause_hypothesis=root_cause_hypotheses[index],
            row_index=index,
        )
        grouped_indexes.setdefault(key, []).append(index)

    clusters: list[IssueCluster] = []
    for key in sorted(grouped_indexes):
        indexes = grouped_indexes[key]
        cluster_revisions = tuple(revisions[index] for index in indexes)
        cluster_evidence_refs = tuple(evidence_refs[index].evidence_ref_id for index in indexes)
        cluster_root_cause_ids = tuple(
            root_cause_hypotheses[index].root_cause_hypothesis_id
            for index in indexes
            if root_cause_hypotheses[index].cause_category != RootCauseCategory.UNCLEAR
        )
        issue_cluster_id = _deterministic_canonical_id(
            CanonicalIdPrefix.ISSUE_CLUSTER,
            {
                "analysis_run_id": analysis_run_id,
                "grouping_key": key,
                "atomic_voc_revision_ids": tuple(revision.atomic_voc_revision_id for revision in cluster_revisions),
            },
        )
        clusters.append(
            IssueCluster(
                issue_cluster_id=issue_cluster_id,
                analysis_run_id=analysis_run_id,
                title=_issue_cluster_title(key, cluster_revisions),
                summary=_issue_cluster_summary(key, cluster_revisions),
                atomic_voc_revision_ids=tuple(revision.atomic_voc_revision_id for revision in cluster_revisions),
                evidence_refs=cluster_evidence_refs,
                root_cause_hypothesis_ids=cluster_root_cause_ids,
                cluster_status=IssueClusterStatus.ACTIVE,
                cluster_source=IssueClusterSource.RULE,
                confidence=_issue_cluster_confidence(indexes, root_cause_hypotheses),
                created_at=SHADOW_PROJECTION_CREATED_AT,
                legacy_refs=_issue_cluster_legacy_refs(key, records, indexes),
            )
        )
    return tuple(clusters)


def _issue_cluster_key(
    *,
    record: Mapping[str, Any],
    revision: AtomicVocRevision,
    cej_assessment: CejAssessment,
    root_cause_hypothesis: RootCauseHypothesis,
    row_index: int,
) -> tuple[str, ...]:
    product = _string_or_none(revision.product_category) or "product:unknown"
    issue_label = _first_nonblank_value(record, _ISSUE_GROUP_FIELDS)
    feature_ref = revision.feature_refs[0] if revision.feature_refs else None
    root_category = (
        root_cause_hypothesis.cause_category.value
        if root_cause_hypothesis.cause_category != RootCauseCategory.UNCLEAR
        else None
    )
    cej_stage = None
    if cej_assessment.actionable_stage is not None:
        cej_stage = cej_assessment.actionable_stage.value
    elif cej_assessment.experience_stage is not None:
        cej_stage = cej_assessment.experience_stage.value

    semantic_parts = tuple(
        f"{name}:{value}"
        for name, value in (
            ("issue", issue_label),
            ("feature", feature_ref),
            ("root", root_category),
            ("cej", cej_stage),
        )
        if value
    )
    if not semantic_parts:
        return ("singleton", f"row:{row_index}", f"revision:{revision.atomic_voc_revision_id}")
    return (f"product:{product}",) + semantic_parts


def _issue_cluster_title(key: tuple[str, ...], revisions: tuple[AtomicVocRevision, ...]) -> str:
    if key[0] == "singleton":
        return "Singleton legacy issue"
    label = key[1].split(":", 1)[1].replace("_", " ")
    product = key[0].split(":", 1)[1]
    return f"{product} {label} issue group"


def _issue_cluster_summary(key: tuple[str, ...], revisions: tuple[AtomicVocRevision, ...]) -> str:
    count = len(revisions)
    if key[0] == "singleton":
        return "No safe grouping key was available, so this AtomicVocRevision remains a singleton cluster."
    return f"Rule-based shadow grouping of {count} AtomicVocRevision record(s) using deterministic legacy fields."


def _issue_cluster_confidence(
    indexes: list[int],
    root_cause_hypotheses: tuple[RootCauseHypothesis, ...],
) -> float:
    if not indexes:
        return 0.0
    values = [root_cause_hypotheses[index].confidence for index in indexes]
    return min(sum(values) / len(values), 0.7)


def _issue_cluster_legacy_refs(
    key: tuple[str, ...],
    records: tuple[Mapping[str, Any], ...],
    indexes: list[int],
) -> tuple[str, ...]:
    refs = [f"grouping_key:{'|'.join(key)}"]
    for index in indexes:
        refs.extend(_legacy_refs(records[index]))
    return tuple(dict.fromkeys(refs))


def _improvement_candidates_from_issue_clusters(
    *,
    issue_clusters: tuple[IssueCluster, ...],
    analysis_run_id: str,
) -> tuple[ImprovementCandidate, ...]:
    candidates: list[ImprovementCandidate] = []
    for cluster in issue_clusters:
        if not _issue_cluster_has_candidate_support(cluster):
            continue
        improvement_candidate_id = _deterministic_canonical_id(
            CanonicalIdPrefix.IMPROVEMENT_CANDIDATE,
            {
                "analysis_run_id": analysis_run_id,
                "issue_cluster_id": cluster.issue_cluster_id,
                "atomic_voc_revision_ids": cluster.atomic_voc_revision_ids,
            },
        )
        candidates.append(
            ImprovementCandidate(
                improvement_candidate_id=improvement_candidate_id,
                title=_candidate_title(cluster),
                summary=_candidate_summary(cluster),
                related_issue_cluster_ids=(cluster.issue_cluster_id,),
                supporting_evidence_refs=cluster.evidence_refs,
                supporting_root_cause_ids=cluster.root_cause_hypothesis_ids,
                candidate_status=CandidateStatus.PROPOSED,
                candidate_source=CandidateSource.RULE,
                confidence=_candidate_confidence(cluster),
                created_at=SHADOW_PROJECTION_CREATED_AT,
                legacy_refs=("shadow_candidate_source:issue_cluster",) + cluster.legacy_refs,
            )
        )
    return tuple(candidates)


def _issue_cluster_has_candidate_support(cluster: IssueCluster) -> bool:
    has_multiple_revisions = len(cluster.atomic_voc_revision_ids) > 1
    has_supported_cause = bool(cluster.evidence_refs and cluster.root_cause_hypothesis_ids)
    has_clear_grouping_key = any(
        ref.startswith("grouping_key:") and ("|issue:" in ref or "|feature:" in ref)
        for ref in cluster.legacy_refs
    )
    return has_multiple_revisions or has_supported_cause or has_clear_grouping_key


def _candidate_title(cluster: IssueCluster) -> str:
    return f"Consider improvement for {cluster.title}"


def _candidate_summary(cluster: IssueCluster) -> str:
    return (
        "Rule-based shadow candidate derived from an IssueCluster with sufficient semantic support. "
        f"Cluster summary: {cluster.summary}"
    )


def _candidate_confidence(cluster: IssueCluster) -> float:
    if len(cluster.atomic_voc_revision_ids) > 1 and cluster.root_cause_hypothesis_ids:
        return min(cluster.confidence + 0.05, 0.75)
    return min(cluster.confidence, 0.65)


def _practitioner_actions_from_candidates(
    *,
    improvement_candidates: tuple[ImprovementCandidate, ...],
    analysis_run_id: str,
) -> tuple[PractitionerAction, ...]:
    actions: list[PractitionerAction] = []
    for candidate in improvement_candidates:
        if not _candidate_has_action_support(candidate):
            continue
        practitioner_action_id = _deterministic_canonical_id(
            CanonicalIdPrefix.PRACTITIONER_ACTION,
            {
                "analysis_run_id": analysis_run_id,
                "improvement_candidate_id": candidate.improvement_candidate_id,
                "issue_cluster_ids": candidate.related_issue_cluster_ids,
            },
        )
        actions.append(
            PractitionerAction(
                practitioner_action_id=practitioner_action_id,
                title=_action_title(candidate),
                summary=_action_summary(candidate),
                related_candidate_ids=(candidate.improvement_candidate_id,),
                supporting_issue_cluster_ids=candidate.related_issue_cluster_ids,
                action_status=PractitionerActionStatus.PROPOSED,
                action_source=PractitionerActionSource.RULE,
                confidence=_action_confidence(candidate),
                created_at=SHADOW_PROJECTION_CREATED_AT,
                legacy_refs=("shadow_action_source:improvement_candidate",) + candidate.legacy_refs,
            )
        )
    return tuple(actions)


def _candidate_has_action_support(candidate: ImprovementCandidate) -> bool:
    has_cluster = bool(candidate.related_issue_cluster_ids)
    has_evidence_or_cause = bool(candidate.supporting_evidence_refs or candidate.supporting_root_cause_ids)
    return has_cluster and has_evidence_or_cause


def _action_title(candidate: ImprovementCandidate) -> str:
    return f"Review proposed action for {candidate.title}"


def _action_summary(candidate: ImprovementCandidate) -> str:
    return (
        "Rule-based shadow action derived from a supported ImprovementCandidate. "
        f"Candidate summary: {candidate.summary}"
    )


def _action_confidence(candidate: ImprovementCandidate) -> float:
    return min(candidate.confidence, 0.7)


def _stage_from_fields(record: Mapping[str, Any], fields: tuple[str, ...]) -> CejStage | None:
    for field in fields:
        stage = _normalize_cej_stage(record.get(field))
        if stage is not None:
            return stage
    return None


def _normalize_free_text_key(value: Any) -> str:
    text = _string_or_none(value)
    if text is None:
        return ""
    normalized = (
        text.lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace("쨌", " ")
        .strip()
    )
    return " ".join(normalized.split())


def _normalize_cej_stage(value: Any) -> CejStage | None:
    text = _string_or_none(value)
    if text is None:
        return None
    normalized = (
        text.lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace("·", " ")
        .strip()
    )
    normalized = " ".join(normalized.split())
    aliases = {
        "s1 awareness": CejStage.AWARENESS,
        "s1 aware": CejStage.AWARENESS,
        "awareness": CejStage.AWARENESS,
        "인지": CejStage.AWARENESS,
        "s2 explore": CejStage.EXPLORATION,
        "s2 exploration": CejStage.EXPLORATION,
        "explore": CejStage.EXPLORATION,
        "exploration": CejStage.EXPLORATION,
        "탐색": CejStage.EXPLORATION,
        "s3 decision": CejStage.DECISION,
        "decision": CejStage.DECISION,
        "결정": CejStage.DECISION,
        "s4 purchase": CejStage.PURCHASE,
        "purchase": CejStage.PURCHASE,
        "구매": CejStage.PURCHASE,
        "s5 delivery": CejStage.DELIVERY,
        "delivery": CejStage.DELIVERY,
        "배송": CejStage.DELIVERY,
        "s6 on board": CejStage.SETUP,
        "s6 onboard": CejStage.SETUP,
        "s6 onboarding": CejStage.SETUP,
        "s6 setup": CejStage.SETUP,
        "setup": CejStage.SETUP,
        "onboarding": CejStage.SETUP,
        "사용준비": CejStage.SETUP,
        "설치": CejStage.SETUP,
        "s7 use": CejStage.USAGE,
        "use": CejStage.USAGE,
        "usage": CejStage.USAGE,
        "사용": CejStage.USAGE,
        "s8 maintain": CejStage.MANAGEMENT,
        "s8 maintenance": CejStage.MANAGEMENT,
        "maintain": CejStage.MANAGEMENT,
        "maintenance": CejStage.MANAGEMENT,
        "management": CejStage.MANAGEMENT,
        "관리": CejStage.MANAGEMENT,
        "s9 replace": CejStage.REPLACEMENT,
        "replacement": CejStage.REPLACEMENT,
        "replace": CejStage.REPLACEMENT,
        "교체": CejStage.REPLACEMENT,
    }
    return aliases.get(normalized)


def _gate_reason_from_record(
    record: Mapping[str, Any],
    *,
    experience_stage: CejStage | None,
    actionable_stage: CejStage | None,
    pre_gate_stage: CejStage | None,
) -> CejGateReason:
    explicit = _string_or_none(record.get("journey_stage_gate_reason"))
    if explicit:
        try:
            return CejGateReason(explicit.lower())
        except ValueError:
            pass
    hygiene_class = (_string_or_none(record.get("hygiene_class")) or "").lower()
    if hygiene_class == "trash":
        return CejGateReason.TRASH_SCOPE
    if _truthy(record.get("analysis_included")) is False:
        return CejGateReason.EXCLUDED_FROM_ANALYSIS
    if actionable_stage is not None:
        return CejGateReason.STRATEGIC_SCOPE
    if pre_gate_stage is not None or experience_stage is not None:
        if _truthy(record.get("inquiry_flag")) is True or hygiene_class == "inquiry":
            return CejGateReason.INQUIRY_SCOPE
        if hygiene_class == "informational":
            return CejGateReason.INFORMATIONAL_SCOPE
        return CejGateReason.SUPPORTING_SCOPE
    if _has_raw_cej_value(record):
        return CejGateReason.UNMAPPED_STAGE
    return CejGateReason.MISSING_SOURCE_STAGE


def _cej_bridge_diagnostic(
    record: Mapping[str, Any],
    assessment: CejAssessment,
    *,
    row_index: int,
) -> dict[str, Any]:
    raw_fields = _raw_cej_fields(record)
    composite_candidates = _composite_cej_stage_candidates(raw_fields)
    mapped = any(
        stage is not None
        for stage in (assessment.experience_stage, assessment.actionable_stage, assessment.pre_gate_stage)
    )
    if not raw_fields:
        status = "missing_raw_stage"
    elif mapped:
        status = "mapped_explicit_stage"
    elif composite_candidates:
        status = "composite_stage_bucket_unmapped"
    else:
        status = "unmapped_raw_stage"
    return {
        "row_index": row_index,
        "source_id": _source_id(record, row_index=row_index),
        "status": status,
        "raw_cej_fields": raw_fields,
        "experience_stage": assessment.experience_stage.value if assessment.experience_stage else None,
        "actionable_stage": assessment.actionable_stage.value if assessment.actionable_stage else None,
        "pre_gate_stage": assessment.pre_gate_stage.value if assessment.pre_gate_stage else None,
        "gate_reason": assessment.gate_reason.value,
        "bridge_scope": "explicit_field_preservation_only",
        "composite_stage_candidates": composite_candidates,
    }


def _hs_rollup_stage(stage: CejStage | None) -> HsCejRollupStage | None:
    if stage in {CejStage.AWARENESS, CejStage.EXPLORATION}:
        return HsCejRollupStage.DISCOVER
    if stage == CejStage.DECISION:
        return HsCejRollupStage.COMPARE_DECIDE
    if stage in {CejStage.PURCHASE, CejStage.DELIVERY}:
        return HsCejRollupStage.PURCHASE_DELIVERY
    if stage == CejStage.SETUP:
        return HsCejRollupStage.SETUP_ONBOARDING
    if stage in {CejStage.USAGE, CejStage.MANAGEMENT}:
        return HsCejRollupStage.USE_MANAGE
    if stage == CejStage.REPLACEMENT:
        return HsCejRollupStage.REPLACE_REPURCHASE
    return None


def _confidence(record: Mapping[str, Any]) -> float:
    for field in ("cej_confidence", "journey_stage_confidence", "confidence"):
        value = record.get(field)
        try:
            if value is not None:
                confidence = float(value)
                if 0 <= confidence <= 1:
                    return confidence
        except (TypeError, ValueError):
            continue
    return 0.5


def _truthy(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _has_raw_cej_value(record: Mapping[str, Any]) -> bool:
    return bool(_raw_cej_fields(record))


def _raw_cej_fields(record: Mapping[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for field in (
        "journey_stage_experience",
        "journey_stage_pre_gate",
        "journey_stage_actionable",
        "journey_stage_gate_reason",
        "customer_journey_stage",
        "cej_scene_code",
        "journey_stage",
    ):
        value = _string_or_none(record.get(field))
        if value:
            fields[field] = value
    return fields


def _composite_cej_stage_candidates(raw_fields: Mapping[str, str]) -> tuple[str, ...]:
    candidates: list[str] = []
    for value in raw_fields.values():
        normalized = _normalize_free_text_key(value)
        for stage in _CEJ_COMPOSITE_STAGE_BUCKETS.get(normalized, ()):
            if stage.value not in candidates:
                candidates.append(stage.value)
    return tuple(candidates)


def _cej_legacy_refs(record: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for field in (
        "journey_stage_experience",
        "journey_stage_actionable",
        "journey_stage_pre_gate",
        "journey_stage_gate_reason",
        "customer_journey_stage",
        "cej_scene_code",
    ):
        value = _string_or_none(record.get(field))
        if value:
            refs.append(f"{field}:{value}")
    return tuple(refs)


def _tees_legacy_refs(record: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for fields in _TEES_EXPLICIT_FIELDS.values():
        for field in fields:
            value = _string_or_none(record.get(field))
            if value:
                refs.append(f"{field}:{value}")
    return tuple(refs)


def _root_cause_legacy_refs(record: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for field in _ROOT_CAUSE_TEXT_FIELDS + _ROOT_CAUSE_CATEGORY_FIELDS + _ROOT_CAUSE_MATURITY_FIELDS:
        value = _string_or_none(record.get(field))
        if value:
            refs.append(f"{field}:{value}")
    return tuple(refs)


def _legacy_refs(record: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for field in ("opinion_id", "comment_id", "source_content_id", "video_id", "legacy_run_id"):
        value = _string_or_none(record.get(field))
        if value:
            refs.append(f"{field}:{value}")
    return tuple(refs)


def _deterministic_canonical_id(prefix: CanonicalIdPrefix, payload: Mapping[str, Any]) -> str:
    digest = canonical_json_digest(payload).removeprefix("sha256:")
    return f"{prefix.value}{digest[:32]}"
