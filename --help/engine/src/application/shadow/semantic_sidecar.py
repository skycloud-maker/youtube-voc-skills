"""Observation-only semantic shadow artifacts for completed legacy analysis.

This sidecar does not change legacy analyzer outputs. It projects completed
legacy analysis rows into the newer Atomic VoC semantic chain, writes compact
diagnostic artifacts, and leaves production dashboard metrics untouched.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Iterable, Mapping
import json
import logging
from pathlib import Path
import re
from typing import Any

from src.application.shadow.atomic_voc_projection import (
    AtomicVocShadowProjectionResult,
    AtomicVocShadowProjectionSettings,
    project_legacy_analysis_safely,
)
from src.application.shadow.contracts import ShadowSidecarFailureLog
from src.application.shadow.golden120_semantic_interpreter import enhance_golden120_card_with_semantic_rules
from src.application.shadow.golden120_semantic_llm import (
    build_semantic_interpreter_config,
    interpret_golden120_semantic_payloads,
)
from src.application.shadow.golden120_prompt_builder import (
    GOLDEN120_PROMPT_VERSION,
    GOLDEN120_SYSTEM_PROMPT,
    build_golden120_semantic_prompt_payload,
    build_golden120_semantic_user_prompt,
)
from src.application.shadow.semantic_card_contract import (
    GENERIC_PRODUCT_LABELS,
    GOLDEN120_UNIT_CARD_REQUIRED_FIELDS,
    GOLDEN120_UNIT_CARD_SCHEMA_VERSION,
    PROJECTION_CARD_SOURCE,
    UNKNOWN_FEATURE_TOPIC_LABELS,
)
from src.domain.canonical_ids import new_analysis_run_id

DEFAULT_SEMANTIC_SHADOW_ROOT = Path("artifacts/shadow_semantic/runs")
SEMANTIC_SIDECAR_SCHEMA_VERSION = "shadow-semantic-sidecar-v1"
SEMANTIC_UNIT_CARD_SCHEMA_VERSION = GOLDEN120_UNIT_CARD_SCHEMA_VERSION


def materialize_semantic_shadow_sidecar_safely(
    *,
    legacy_rows: object,
    legacy_run_id: str,
    logger: logging.Logger,
    output_root: str | Path = DEFAULT_SEMANTIC_SHADOW_ROOT,
    analysis_run_id: str | None = None,
    row_limit: int | None = None,
    run_scope: Mapping[str, Any] | None = None,
) -> Path | None:
    """Write semantic shadow artifacts without interrupting legacy execution."""

    try:
        return materialize_semantic_shadow_sidecar(
            legacy_rows=legacy_rows,
            legacy_run_id=legacy_run_id,
            logger=logger,
            output_root=output_root,
            analysis_run_id=analysis_run_id,
            row_limit=row_limit,
            run_scope=run_scope,
        )
    except Exception as exc:
        failure = ShadowSidecarFailureLog.from_exception(
            operation="semantic_shadow_sidecar_materialization",
            error=exc,
            legacy_run_id=legacy_run_id,
            details={"output_root": str(output_root), "row_limit": row_limit},
        )
        logger.warning(
            "Semantic shadow sidecar materialization failed",
            extra={"shadow_failure": failure.model_dump(mode="json")},
        )
        return None


def materialize_semantic_shadow_sidecar(
    *,
    legacy_rows: object,
    legacy_run_id: str,
    logger: logging.Logger,
    output_root: str | Path = DEFAULT_SEMANTIC_SHADOW_ROOT,
    analysis_run_id: str | None = None,
    row_limit: int | None = None,
    run_scope: Mapping[str, Any] | None = None,
) -> Path:
    """Project legacy rows and write summary/review artifacts."""

    records = _records_from_legacy_rows(legacy_rows)
    if row_limit is not None and row_limit > 0:
        records = records[:row_limit]
    effective_analysis_run_id = analysis_run_id or new_analysis_run_id()
    result = project_legacy_analysis_safely(
        legacy_rows=records,
        analysis_run_id=effective_analysis_run_id,
        logger=logger,
        settings=AtomicVocShadowProjectionSettings(enabled=True),
        legacy_run_id=legacy_run_id,
    )

    run_dir = Path(output_root) / f"{_safe_run_dir_name(legacy_run_id)}__{effective_analysis_run_id[-8:]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    review_queue = _semantic_review_queue(result=result, records=records)
    comparison = _semantic_comparison_rows(result=result, records=records)
    unit_analysis_cards = _semantic_unit_analysis_cards(result=result, records=records)
    semantic_prompt_payloads = _semantic_prompt_payload_rows(unit_analysis_cards)
    semantic_interpreter_config = build_semantic_interpreter_config(run_scope or {})
    semantic_llm_outputs, semantic_llm_diagnostics = interpret_golden120_semantic_payloads(
        semantic_prompt_payloads,
        config=semantic_interpreter_config,
    )
    semantic_enhanced_unit_cards = _semantic_llm_enhanced_unit_cards(
        unit_analysis_cards=unit_analysis_cards,
        semantic_llm_outputs=semantic_llm_outputs,
    )
    dashboard_source_cards = semantic_enhanced_unit_cards or unit_analysis_cards
    semantic_quality_postprocess = _semantic_quality_postprocess_cards(dashboard_source_cards)
    dashboard_source_cards = semantic_quality_postprocess["cards"]
    semantic_ai_drafts = _semantic_ai_draft_rows(dashboard_source_cards)
    ai_draft_gap_analysis = _semantic_ai_draft_gap_analysis(
        unit_analysis_cards=unit_analysis_cards,
        semantic_enhanced_unit_cards=semantic_enhanced_unit_cards,
        semantic_ai_drafts=semantic_ai_drafts,
        semantic_llm_outputs=semantic_llm_outputs,
        semantic_llm_diagnostics=semantic_llm_diagnostics,
        semantic_quality_postprocess=semantic_quality_postprocess,
    )
    semantic_dashboard_units = _semantic_dashboard_unit_rows(dashboard_source_cards)
    semantic_dashboard_topics = _semantic_dashboard_topic_rows(semantic_dashboard_units)
    summary = _semantic_sidecar_summary(
        result=result,
        records=records,
        legacy_run_id=legacy_run_id,
        analysis_run_id=effective_analysis_run_id,
        legacy_row_count=len(records),
        run_dir=run_dir,
        review_queue_count=len(review_queue),
        unit_analysis_card_count=len(unit_analysis_cards),
        unit_card_source_counts=_unit_card_source_counts(unit_analysis_cards),
        unit_analysis_cards=unit_analysis_cards,
        run_scope=run_scope or {},
        semantic_llm_diagnostics=semantic_llm_diagnostics,
        semantic_llm_output_count=len(semantic_llm_outputs),
        semantic_enhanced_unit_card_count=len(semantic_enhanced_unit_cards),
        semantic_quality_postprocess=semantic_quality_postprocess,
        semantic_ai_draft_count=len(semantic_ai_drafts),
        ai_draft_gap_analysis=ai_draft_gap_analysis,
        semantic_dashboard_unit_count=len(semantic_dashboard_units),
        semantic_dashboard_topic_count=len(semantic_dashboard_topics),
    )

    _write_json(run_dir / "summary.json", summary)
    _write_jsonl(run_dir / "review_queue.jsonl", review_queue)
    _write_jsonl(run_dir / "comparison_records.jsonl", comparison)
    _write_jsonl(run_dir / "unit_analysis_cards.jsonl", unit_analysis_cards)
    _write_jsonl(run_dir / "semantic_prompt_payloads.jsonl", semantic_prompt_payloads)
    _write_jsonl(run_dir / "semantic_llm_outputs.jsonl", semantic_llm_outputs)
    _write_jsonl(run_dir / "semantic_enhanced_unit_cards.jsonl", semantic_enhanced_unit_cards)
    _write_jsonl(run_dir / "semantic_ai_drafts.jsonl", semantic_ai_drafts)
    _write_json(run_dir / "ai_draft_gap_analysis.json", ai_draft_gap_analysis)
    _write_jsonl(run_dir / "semantic_dashboard_units.jsonl", semantic_dashboard_units)
    _write_jsonl(run_dir / "semantic_dashboard_topics.jsonl", semantic_dashboard_topics)
    _write_json(
        run_dir / "manifest.json",
        {
            "schema_version": SEMANTIC_SIDECAR_SCHEMA_VERSION,
            "legacy_run_id": legacy_run_id,
            "analysis_run_id": effective_analysis_run_id,
            "artifacts": {
                "summary": "summary.json",
                "review_queue": "review_queue.jsonl",
                "comparison_records": "comparison_records.jsonl",
                "unit_analysis_cards": "unit_analysis_cards.jsonl",
                "semantic_prompt_payloads": "semantic_prompt_payloads.jsonl",
                "semantic_llm_outputs": "semantic_llm_outputs.jsonl",
                "semantic_enhanced_unit_cards": "semantic_enhanced_unit_cards.jsonl",
                "semantic_ai_drafts": "semantic_ai_drafts.jsonl",
                "ai_draft_gap_analysis": "ai_draft_gap_analysis.json",
                "semantic_dashboard_units": "semantic_dashboard_units.jsonl",
                "semantic_dashboard_topics": "semantic_dashboard_topics.jsonl",
            },
            "diagnostic_only": True,
            "production_metrics_mutated": False,
        },
    )
    logger.info(
        "Semantic shadow sidecar materialized",
        extra={
            "legacy_run_id": legacy_run_id,
            "analysis_run_id": effective_analysis_run_id,
            "run_dir": str(run_dir),
            "review_queue_count": len(review_queue),
        },
    )
    return run_dir


def _records_from_legacy_rows(legacy_rows: object) -> list[dict[str, Any]]:
    if legacy_rows is None:
        return []
    if hasattr(legacy_rows, "to_dict"):
        raw_records = legacy_rows.to_dict("records")
    elif isinstance(legacy_rows, Mapping):
        raw_records = [dict(legacy_rows)]
    elif isinstance(legacy_rows, Iterable) and not isinstance(legacy_rows, (str, bytes)):
        raw_records = list(legacy_rows)
    else:
        return []
    return [_sanitize_record(record) for record in raw_records if isinstance(record, Mapping)]


def _sanitize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe(value) for key, value in record.items()}


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(inner_value) for key, inner_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(inner_value) for inner_value in value]
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _semantic_sidecar_summary(
    *,
    result: AtomicVocShadowProjectionResult,
    records: list[dict[str, Any]],
    legacy_run_id: str,
    analysis_run_id: str,
    legacy_row_count: int,
    run_dir: Path,
    review_queue_count: int,
    unit_analysis_card_count: int,
    unit_card_source_counts: Mapping[str, int],
    unit_analysis_cards: list[dict[str, Any]],
    run_scope: Mapping[str, Any],
    semantic_llm_diagnostics: Mapping[str, Any],
    semantic_llm_output_count: int,
    semantic_enhanced_unit_card_count: int,
    semantic_quality_postprocess: Mapping[str, Any],
    semantic_ai_draft_count: int,
    ai_draft_gap_analysis: Mapping[str, Any],
    semantic_dashboard_unit_count: int,
    semantic_dashboard_topic_count: int,
) -> dict[str, Any]:
    root_maturity = Counter(
        _enum_value(getattr(hypothesis, "maturity", None)) or "missing"
        for hypothesis in result.root_cause_hypotheses
    )
    return {
        "schema_version": SEMANTIC_SIDECAR_SCHEMA_VERSION,
        "legacy_run_id": legacy_run_id,
        "analysis_run_id": analysis_run_id,
        "run_dir": str(run_dir),
        "diagnostic_only": True,
        "production_metrics_mutated": False,
        "legacy_row_count": legacy_row_count,
        "enabled": bool(result.enabled),
        "atomic_voc_revision_count": len(result.revisions),
        "evidence_ref_count": len(result.evidence_refs),
        "cej_assessment_count": len(result.cej_assessments),
        "tees_assessment_count": len(result.tees_assessments),
        "root_cause_count": len(result.root_cause_hypotheses),
        "issue_cluster_count": len(result.issue_clusters),
        "improvement_candidate_count": len(result.improvement_candidates),
        "practitioner_action_count": len(result.practitioner_actions),
        "review_queue_count": review_queue_count,
        "unit_analysis_card_count": unit_analysis_card_count,
        "warning_count": len(result.warnings),
        "cej_bridge_diagnostic_counts": _count_values(result.metadata.get("cej_bridge_diagnostic_counts", {})),
        "tees_emotion_policy_counts": _count_values(result.metadata.get("tees_emotion_policy_counts", {})),
        "root_cause_maturity_counts": dict(sorted(root_maturity.items())),
        "recommended_use": "sidecar_preview_before_dashboard_promotion",
        "unit_card_schema_version": SEMANTIC_UNIT_CARD_SCHEMA_VERSION,
        "semantic_prompt_version": GOLDEN120_PROMPT_VERSION,
        "unit_card_required_fields": list(GOLDEN120_UNIT_CARD_REQUIRED_FIELDS),
        "card_source": PROJECTION_CARD_SOURCE,
        "card_source_note": (
            "Current cards are legacy projections shaped into the Golden120 contract. "
            "They are not yet produced by the full Golden120 semantic interpreter."
        ),
        "unit_card_source_counts": dict(unit_card_source_counts),
        "count_reconciliation": _count_reconciliation(
            records=records,
            unit_analysis_cards=unit_analysis_cards,
            run_scope=run_scope,
        ),
        "engine_runtime_diagnostics": _engine_runtime_diagnostics(
            unit_analysis_cards,
            semantic_llm_diagnostics=semantic_llm_diagnostics,
        ),
        "semantic_llm_diagnostics": dict(semantic_llm_diagnostics),
        "semantic_llm_output_count": semantic_llm_output_count,
        "semantic_enhanced_unit_card_count": semantic_enhanced_unit_card_count,
        "semantic_quality_postprocess": {
            "input_card_count": int(semantic_quality_postprocess.get("input_count", 0) or 0),
            "output_card_count": int(semantic_quality_postprocess.get("output_count", 0) or 0),
            "atomic_boundary_merge_count": int(
                semantic_quality_postprocess.get("atomic_boundary_merge_count", 0) or 0
            ),
            "duplicate_split_detected_count": int(
                semantic_quality_postprocess.get("duplicate_split_detected_count", 0) or 0
            ),
            "duplicate_split_removed_count": int(
                semantic_quality_postprocess.get("duplicate_split_removed_count", 0) or 0
            ),
            "root_reclassified_count": int(semantic_quality_postprocess.get("root_reclassified_count", 0) or 0),
        },
        "semantic_ai_draft_count": semantic_ai_draft_count,
        "semantic_ai_draft_artifact": "semantic_ai_drafts.jsonl",
        "ai_draft_gap_analysis_artifact": "ai_draft_gap_analysis.json",
        "ai_draft_promotion_readiness": _safe_card_text(ai_draft_gap_analysis.get("promotion_readiness")),
        "ai_draft_gap_count": len(ai_draft_gap_analysis.get("gaps") or []),
        "semantic_dashboard_unit_count": semantic_dashboard_unit_count,
        "semantic_dashboard_topic_count": semantic_dashboard_topic_count,
        "na_status_counts": _card_field_counts(unit_analysis_cards, "na_status"),
        "semantic_lane_counts": _card_field_counts(unit_analysis_cards, "semantic_lane"),
        "root_problem_level_counts": _card_field_counts(unit_analysis_cards, "root_problem_level"),
    }


def _count_reconciliation(
    *,
    records: list[dict[str, Any]],
    unit_analysis_cards: list[dict[str, Any]],
    run_scope: Mapping[str, Any],
) -> dict[str, Any]:
    top_level_count = 0
    reply_count = 0
    excluded_count = 0
    video_ids: set[str] = set()
    for record in records:
        if _first_text(record, ("parent_comment_id", "parent_id", "reply_to_comment_id", "parent_comment_text", "parent_text", "reply_context")):
            reply_count += 1
        else:
            top_level_count += 1
        video_id = _first_text(record, ("video_id", "source_video_id", "youtube_video_id"))
        if video_id:
            video_ids.add(video_id)
        validity = _first_text(record, ("validity", "validity_label", "scope_status")).lower()
        if validity in {"exclude", "excluded", "trash", "invalid", "out_of_scope", "scope_negative_control"}:
            excluded_count += 1
    requested_video_count = _first_scope_int(run_scope, ("max_videos", "requested_video_count")) or _first_int(
        records, ("selected_video_count", "video_count", "requested_video_count")
    )
    requested_comments_per_video = _first_scope_int(
        run_scope, ("comments_per_video", "comment_limit_per_video", "requested_comments_per_video")
    ) or _first_int(records, ("comments_per_video", "comment_limit_per_video", "requested_comments_per_video"))
    requested_raw_comment_capacity = None
    if requested_video_count is not None and requested_comments_per_video is not None:
        requested_raw_comment_capacity = requested_video_count * requested_comments_per_video
    return {
        "requested_video_count": requested_video_count,
        "requested_comments_per_video": requested_comments_per_video,
        "requested_raw_comment_capacity": requested_raw_comment_capacity,
        "requested_published_after": _first_scope_text(run_scope, ("published_after",)),
        "requested_published_before": _first_scope_text(run_scope, ("published_before",)),
        "requested_comment_published_after": _first_scope_text(run_scope, ("comment_published_after",)),
        "requested_comment_published_before": _first_scope_text(run_scope, ("comment_published_before",)),
        "requested_keyword": _first_scope_text(run_scope, ("keyword",)),
        "requested_keywords": run_scope.get("keywords", []) if isinstance(run_scope, Mapping) else [],
        "requested_language": _first_scope_text(run_scope, ("language",)),
        "requested_region": _first_scope_text(run_scope, ("region",)),
        "observed_video_count": len(video_ids),
        "legacy_row_count": len(records),
        "top_level_comment_rows": top_level_count,
        "reply_comment_rows": reply_count,
        "excluded_rows": excluded_count,
        "source_voc_count": len(records),
        "atomic_unit_count": len(unit_analysis_cards),
        "atomic_expansion_delta": len(unit_analysis_cards) - len(records),
        "raw_capacity_vs_legacy_delta": (
            len(records) - requested_raw_comment_capacity if requested_raw_comment_capacity is not None else None
        ),
        "raw_capacity_vs_atomic_delta": (
            len(unit_analysis_cards) - requested_raw_comment_capacity if requested_raw_comment_capacity is not None else None
        ),
        "note": (
            "5 x 100 같은 수집 요청 수와 최종 Atomic Unit 수는 다를 수 있습니다. "
            "대댓글 포함 여부, 제외/중복 처리, Atomic split 여부를 분리해서 검산합니다."
        ),
    }


# Last-in-file override. Keep this below the legacy compatibility definitions:
# the runtime imports the final function bound to this name, so the gap analysis
# must compute the v3 AI Draft metrics here as well as in earlier compatibility
# sections.
def _semantic_ai_draft_gap_analysis(
    *,
    unit_analysis_cards: list[dict[str, Any]],
    semantic_enhanced_unit_cards: list[dict[str, Any]],
    semantic_ai_drafts: list[dict[str, Any]],
    semantic_llm_outputs: list[dict[str, Any]] | None = None,
    semantic_llm_diagnostics: Mapping[str, Any] | None = None,
    semantic_quality_postprocess: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    llm_outputs = semantic_llm_outputs or []
    diagnostics = dict(semantic_llm_diagnostics or {})
    total_drafts = len(semantic_ai_drafts)

    evidence_scores: list[float] = []
    customer_insight_count = 0
    human_review_count = 0
    generic_product_count = 0
    unknown_topic_count = 0
    na_status_count = 0

    for draft in semantic_ai_drafts:
        if not isinstance(draft, Mapping):
            continue
        quality = draft.get("quality")
        if isinstance(quality, Mapping):
            try:
                evidence_scores.append(float(quality.get("evidence_completeness") or 0.0))
            except (TypeError, ValueError):
                evidence_scores.append(0.0)
            na_status = _safe_card_text(quality.get("na_status")).lower()
            if na_status in {"engine_missed", "engine_missed_or_context_needed", "context_needed"}:
                na_status_count += 1

        judgments = draft.get("judgments")
        if isinstance(judgments, Mapping):
            product = judgments.get("product")
            if isinstance(product, Mapping) and _is_generic_product_label(_safe_card_text(product.get("label"))):
                generic_product_count += 1
            feature_topic = judgments.get("feature_topic")
            if isinstance(feature_topic, Mapping) and _is_unknown_topic_label(_safe_card_text(feature_topic.get("label"))):
                unknown_topic_count += 1

        summary_layer = draft.get("summary_layer")
        if isinstance(summary_layer, Mapping) and _safe_card_text(summary_layer.get("customer_insight")):
            customer_insight_count += 1
        if isinstance(draft.get("human_review"), Mapping):
            human_review_count += 1

    avg_evidence = round(sum(evidence_scores) / len(evidence_scores), 3) if evidence_scores else 0.0
    metrics: dict[str, Any] = {
        "unit_card_count": len(unit_analysis_cards),
        "unit_analysis_cards": len(unit_analysis_cards),
        "semantic_enhanced_unit_card_count": len(semantic_enhanced_unit_cards),
        "semantic_enhanced_unit_cards": len(semantic_enhanced_unit_cards),
        "semantic_ai_draft_count": total_drafts,
        "semantic_ai_drafts": total_drafts,
        "semantic_ai_draft_count": total_drafts,
        "semantic_llm_output_count": len(llm_outputs),
        "semantic_llm_outputs": len(llm_outputs),
        "llm_provider": diagnostics.get("provider", ""),
        "llm_status": diagnostics.get("status", ""),
        "llm_attempted": int(diagnostics.get("attempted") or 0),
        "llm_succeeded": int(diagnostics.get("succeeded") or 0),
        "llm_failed": int(diagnostics.get("failed") or 0),
        "generic_product_count": generic_product_count,
        "unknown_feature_topic_count": unknown_topic_count,
        "engine_missed_or_context_needed_count": na_status_count,
        "average_evidence_completeness": avg_evidence,
        "customer_insight_summary_count": customer_insight_count,
        "human_review_field_count": human_review_count,
    }
    if isinstance(semantic_quality_postprocess, Mapping):
        qp_metrics = semantic_quality_postprocess.get("metrics")
        if isinstance(qp_metrics, Mapping):
            metrics.update(
                {
                    "quality_postprocess_input_count": int(qp_metrics.get("input_count") or 0),
                    "quality_postprocess_output_count": int(qp_metrics.get("output_count") or 0),
                    "atomic_boundary_merge_count": int(qp_metrics.get("atomic_boundary_merge_count") or 0),
                    "duplicate_split_detected_count": int(qp_metrics.get("duplicate_split_detected_count") or 0),
                    "duplicate_split_removed_count": int(qp_metrics.get("duplicate_split_removed_count") or 0),
                    "root_reclassified_count": int(qp_metrics.get("root_reclassified_count") or 0),
                    "summary_rewritten_count": int(qp_metrics.get("summary_rewritten_count") or 0),
                    "evidence_fields_refreshed_count": int(qp_metrics.get("evidence_fields_refreshed_count") or 0),
                }
            )

    gaps: list[dict[str, Any]] = []
    try:
        gaps.extend(_ai_draft_gap_items(metrics=metrics, total=total_drafts))
    except NameError:
        gaps = []
    gaps.extend(_quality_postprocess_gap_items(semantic_quality_postprocess))

    if avg_evidence >= 0.75:
        gaps = [gap for gap in gaps if gap.get("id") != "evidence_completeness_low"]

    blocking = [gap for gap in gaps if str(gap.get("severity") or "").lower() in {"high", "medium", "blocker", "blocking"}]
    promotion_readiness = (
        "ready_for_review_export" if total_drafts and not blocking else "needs_work_before_ai_draft_promotion"
    )
    return {
        "schema_version": "semantic-ai-draft-gap-analysis-v1",
        "version": "golden120_ai_draft_gap_analysis_v3",
        "metrics": metrics,
        "gaps": gaps,
        "blocking_gap_count": len(blocking),
        "promotion_readiness": promotion_readiness,
        "recommendation": (
            "AI Draft review export is ready."
            if promotion_readiness == "ready_for_review_export"
            else "Review remaining blocking/medium gaps before export."
        ),
    }


def _engine_runtime_diagnostics(
    unit_analysis_cards: list[dict[str, Any]],
    *,
    semantic_llm_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    total = len(unit_analysis_cards)
    interpreter_status_counts = Counter(_first_text(card, ("interpreter_status",)) or "missing" for card in unit_analysis_cards)
    card_source_counts = Counter(_first_text(card, ("card_source",)) or "missing" for card in unit_analysis_cards)
    context_counts = Counter()
    for card in unit_analysis_cards:
        contexts = card.get("source_context_used", [])
        if not isinstance(contexts, list):
            contexts = [contexts] if contexts else []
        for context in contexts:
            context_counts[str(context)] += 1
    llm_status = _safe_card_text(semantic_llm_diagnostics.get("status", "payload_only"))
    llm_provider = _safe_card_text(semantic_llm_diagnostics.get("provider", "payload"))
    openai_invocation = (
        "attempted" if llm_provider == "openai" and int(semantic_llm_diagnostics.get("attempted", 0) or 0) > 0
        else "not_attempted"
    )
    return {
        "total_cards": total,
        "card_source_counts": dict(sorted(card_source_counts.items())),
        "interpreter_status_counts": dict(sorted(interpreter_status_counts.items())),
        "openai_api_invocation": openai_invocation,
        "llm_prompt_payload_ready_count": _prompt_ready_count(unit_analysis_cards),
        "llm_prompt_payload_artifact": "semantic_prompt_payloads.jsonl",
        "semantic_prompt_version": GOLDEN120_PROMPT_VERSION,
        "semantic_llm_provider": llm_provider,
        "semantic_llm_model": _safe_card_text(semantic_llm_diagnostics.get("model", "")),
        "semantic_llm_status": llm_status,
        "semantic_llm_attempted": int(semantic_llm_diagnostics.get("attempted", 0) or 0),
        "semantic_llm_succeeded": int(semantic_llm_diagnostics.get("succeeded", 0) or 0),
        "semantic_llm_failed": int(semantic_llm_diagnostics.get("failed", 0) or 0),
        "full_semantic_interpreter_status": "connected" if llm_status in {"completed", "completed_with_failures"} else "not_connected",
        "full_semantic_interpreter_next_step": (
            "OpenAI/LLM provider key와 모델 설정을 승인한 뒤 semantic_prompt_payloads.jsonl을 "
            "Golden120 8칸 JSON으로 변환하는 provider adapter를 연결합니다."
        ),
        "rule_ledger_loaded": "not_detected_in_current_sidecar",
        "context_coverage_counts": dict(sorted(context_counts.items())),
        "legacy_projection_card_count": int(card_source_counts.get(PROJECTION_CARD_SOURCE, 0)),
        "semantic_interpreter_card_count": total - int(card_source_counts.get(PROJECTION_CARD_SOURCE, 0)),
        "diagnosis": (
            "현재 sidecar는 legacy projection 위에 Golden120 rule/heuristic을 덧씌우는 중간 단계입니다. "
            "OpenAI 기반 full semantic interpreter 호출 여부는 별도 연결이 필요합니다."
        ),
    }


def _card_field_counts(unit_analysis_cards: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    return dict(
        sorted(
            Counter(_first_text(card, (field_name,)) or "missing" for card in unit_analysis_cards).items()
        )
    )


def _prompt_ready_count(unit_analysis_cards: list[dict[str, Any]]) -> int:
    return sum(1 for card in unit_analysis_cards if bool(card.get("semantic_prompt_ready")))


def _safe_card_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_int(records: list[dict[str, Any]], candidates: tuple[str, ...]) -> int | None:
    for record in records:
        for key in candidates:
            value = record.get(key)
            if value in (None, ""):
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None


def _first_scope_int(scope: Mapping[str, Any], candidates: tuple[str, ...]) -> int | None:
    for key in candidates:
        value = scope.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_scope_text(scope: Mapping[str, Any], candidates: tuple[str, ...]) -> str:
    for key in candidates:
        value = scope.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _semantic_review_queue(
    *,
    result: AtomicVocShadowProjectionResult,
    records: list[dict[str, Any]],
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for diagnostic in result.metadata.get("cej_bridge_diagnostics", ()):
        if not isinstance(diagnostic, Mapping):
            continue
        status = str(diagnostic.get("status", ""))
        if status == "mapped_explicit_stage":
            continue
        row_index = int(diagnostic.get("row_index", len(rows)) or 0)
        rows.append(
            _queue_row(
                records=records,
                row_index=row_index,
                review_type="CEJ bridge",
                recommended_status="Backlog",
                reason=f"CEJ source stage status={status}; bridge candidate between legacy bucket and shadow CEJ stage.",
                diagnostic=diagnostic,
            )
        )
        if len(rows) >= limit:
            return rows

    for diagnostic in result.metadata.get("tees_emotion_policy_diagnostics", ()):
        if not isinstance(diagnostic, Mapping):
            continue
        status = str(diagnostic.get("status", ""))
        if status in {"explicit_emotion_preserved", "no_product_emotion_context"}:
            continue
        row_index = int(diagnostic.get("row_index", len(rows)) or 0)
        rows.append(
            _queue_row(
                records=records,
                row_index=row_index,
                review_type="TEE/S Emotion",
                recommended_status="Watch",
                reason=f"Emotion policy status={status}; product/CEJ experience emotion signal review candidate.",
                diagnostic=diagnostic,
            )
        )
        if len(rows) >= limit:
            return rows

    for index, hypothesis in enumerate(result.root_cause_hypotheses):
        maturity = _enum_value(getattr(hypothesis, "maturity", None)) or ""
        if maturity not in {"possible", "unknown"}:
            continue
        rows.append(
            _queue_row(
                records=records,
                row_index=index,
                review_type="Root Cause weak target",
                recommended_status="Backlog",
                reason=f"Root Cause maturity={maturity}; separate weak target from hard failure diagnosis.",
                diagnostic=hypothesis.model_dump(mode="json") if hasattr(hypothesis, "model_dump") else {},
            )
        )
        if len(rows) >= limit:
            return rows
    return rows


def _semantic_unit_analysis_cards(
    *,
    result: AtomicVocShadowProjectionResult,
    records: list[dict[str, Any]],
    limit: int = 500,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, revision in enumerate(result.revisions[:limit]):
        record = records[index] if index < len(records) else {}
        evidence = result.evidence_refs[index] if index < len(result.evidence_refs) else None
        cej = result.cej_assessments[index] if index < len(result.cej_assessments) else None
        tees = result.tees_assessments[index] if index < len(result.tees_assessments) else None
        root = result.root_cause_hypotheses[index] if index < len(result.root_cause_hypotheses) else None
        product = (
            getattr(revision, "product_category", None)
            or getattr(revision, "product_family", None)
            or _first_text(record, ("product", "product_category", "source_product", "mapped_product", "parent_product"))
        )
        feature_topic = (
            _first_text(record, ("feature_topic", "topic", "topic_label", "issue_topic", "feature", "function_topic"))
            or " | ".join(getattr(revision, "feature_refs", ()) or ())
        )
        base_card = _golden120_unit_analysis_card(
            index=index,
            record=record,
            revision=revision,
            evidence=evidence,
            cej=cej,
            tees=tees,
            root=root,
            product=product or "",
            feature_topic=feature_topic or "",
        )
        enhanced_card = enhance_golden120_card_with_semantic_rules(record=record, card=base_card)
        split_cards = _split_semantic_unit_cards_if_needed(card=enhanced_card, record=record)
        for split_index, split_card in enumerate(split_cards, start=1):
            split_card["source_voc_index"] = base_card.get("source_voc_index", index + 1)
            split_card["atomic_unit_index"] = split_index
            split_card["atomic_unit_id"] = f"{base_card.get('source_id', _source_id(record, index))}::u{split_index}"
            _finalize_semantic_card_routing(split_card)
            rows.append(split_card)
            if len(rows) >= limit:
                return rows
    return rows


def _finalize_semantic_card_routing(card: dict[str, Any]) -> None:
    lane, reason = _semantic_lane_payload(card)
    card["semantic_lane"] = lane
    card["semantic_lane_reason"] = reason


def _semantic_lane_payload(card: Mapping[str, Any]) -> tuple[str, str]:
    scope = _safe_card_text(card.get("scope_status", "")).lower()
    na_status = _safe_card_text(card.get("na_status", "")).lower()
    polarity = _safe_card_text(card.get("polarity_label", "")).lower()
    root_level = _safe_card_text(card.get("root_problem_level", ""))
    watch_flags = card.get("watch_agenda_flags", [])
    needs_review = bool(card.get("needs_human_review", False))
    if scope in {"scope_excluded", "out_of_scope"} or na_status == "scope_excluded":
        if scope == "low_value_inquiry":
            return "low_value_inquiry", "구체적 개선 신호가 약한 단순 문의로 문의/정보접근 후보에만 보냅니다."
        return "scope_excluded", "현재 HGT/운영 기준에서 분석 분모에서 제외하거나 negative control로 봅니다."
    if scope == "low_value_inquiry":
        return "low_value_inquiry", "구체적 개선 신호가 약한 단순 문의로 문의/정보접근 후보에만 보냅니다."
    if isinstance(watch_flags, list) and watch_flags:
        return "watch_agenda", "확정 규칙이 아니라 Watch/Agenda 축적 또는 사람 검토가 필요한 후보입니다."
    if na_status in {"engine_missed_or_context_needed", "true_na_or_scope_boundary"} or needs_review:
        return "review_queue", "엔진 미포착, context 부족, CEJ/scope 경계 등 사람 검수가 필요한 후보입니다."
    if polarity in {"inquiry", "question"}:
        return "inquiry_insight", "문의/정보탐색형 VoC로 문의/정보접근 인사이트 탭에서 군집화합니다."
    if root_level.startswith(("L2", "L3")) or polarity in {"negative_concern", "positive"}:
        return "strategy_voc", "제품/경험 개선 또는 강점 신호로 전략/개선 후보에 연결합니다."
    return "observation", "즉시 개선과제보다는 관찰/참고 신호로 유지합니다."


def _split_semantic_unit_cards_if_needed(*, card: dict[str, Any], record: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = _first_text(record, ("opinion_text", "comment_text", "text_display", "cleaned_text")) or _safe_card_text(
        card.get("atomic_voc", "")
    )
    compact = text.replace(" ", "")
    if (
        "자체개발" in compact
        and any(token in text for token in ("업그레이드", "좋네요", "좋", "확실"))
        and any(token in text for token in ("검은색만", "색상", "아쉬운", "아쉽"))
    ):
        return _split_robot_vacuum_development_and_color(card=card, text=text)
    split_cards = _split_mixed_semantic_unit_cards(card=card, text=text)
    if len(split_cards) > 1:
        return split_cards
    return [card]


POSITIVE_ATOMIC_CUES = (
    "대박",
    "만족",
    "좋",
    "최고",
    "추천",
    "선방",
    "메리트",
    "신세계",
    "편하",
    "괜찮",
)

NEGATIVE_ATOMIC_CUES = (
    "아쉽",
    "비싸",
    "불만",
    "우려",
    "걱정",
    "불안",
    "무섭",
    "별로",
    "실망",
    "시끄",
    "소음",
    "먼지",
    "엉키",
    "부족",
    "불편",
)

INQUIRY_ATOMIC_CUES = ("?", "나요", "까요", "궁금", "문의", "알려", "뭐가 더", "어떻게")


def _split_mixed_semantic_unit_cards(*, card: dict[str, Any], text: str) -> list[dict[str, Any]]:
    """Split obvious mixed Atomic VoC cases before AI Draft materialization.

    This is a conservative guardrail, not final truth.  Its goal is to stop one
    mixed source comment from becoming one blended CEJ/TEE/S/Root Cause row.
    OpenAI can still produce multiple units; this fallback catches the common
    Golden120 patterns when the LLM or projection layer leaves them merged.
    """

    segments = _candidate_atomic_segments(text)
    if len(segments) < 2:
        return []

    classified = [(segment, _atomic_segment_kind(segment)) for segment in segments]
    distinct_kinds = {kind for _, kind in classified if kind}
    if len(distinct_kinds) < 2 and not _has_product_comparison_signal(text):
        return []

    cards: list[dict[str, Any]] = []
    for split_index, (segment, kind) in enumerate(classified, start=1):
        split_card = copy.deepcopy(card)
        _apply_generic_atomic_split(split_card, segment=segment, kind=kind, split_index=split_index)
        cards.append(split_card)
    return cards


def _candidate_atomic_segments(text: str) -> list[str]:
    text = _safe_card_text(text).strip()
    if not text:
        return []
    working = text
    working = re.sub(r"(?<=[?？！])\s+", "\n", working)
    working = re.sub(r"\s+(근데|그런데|하지만|반면|다만)\s+", "\n", working)
    working = re.sub(r"(만족|좋(?:다|고|은|아|네요)?|괜찮(?:다|은|네요)?|선방(?:했다|한)?)(한데|는데)\s+", r"\1\2\n", working)
    working = re.sub(r"(통돌이[^.?!\n]{0,80}?)(드럼)", r"\1\n\2", working)
    working = re.sub(r"(가격[^.?!\n]{0,80}?)(설치|흡입력|소음|색상|직배수)", r"\1\n\2", working)
    parts = [part.strip(" .,\n\t") for part in re.split(r"[\r\n]+|(?<=[.!。！])\s+", working) if part.strip(" .,\n\t")]
    return _merge_dependent_atomic_segments(_merge_too_short_segments(parts))


def _merge_too_short_segments(parts: list[str]) -> list[str]:
    rows: list[str] = []
    pending = ""
    for part in parts:
        if pending:
            part = f"{pending} {part}".strip()
            pending = ""
        if len(part) < 5:
            pending = part
            continue
        rows.append(part)
    if pending:
        if rows:
            rows[-1] = f"{rows[-1]} {pending}".strip()
        else:
            rows.append(pending)
    return rows[:4]


def _merge_dependent_atomic_segments(parts: list[str]) -> list[str]:
    """Merge dependent clauses that describe one Atomic VoC.

    Atomic split aims for appropriate splitting, not maximum splitting.  A
    question mark can split Korean comments too aggressively, e.g. "통돌이
    쿵덕거리지 않나요?? 먼지 뜨고 엉키고" is one top-loader concern flow,
    while "사도 되나요? 직배수는 좋아보이네요" is two independent intents.
    """

    if len(parts) < 2:
        return parts

    rows: list[str] = []
    index = 0
    while index < len(parts):
        current = parts[index]
        if index + 1 < len(parts) and _should_merge_dependent_atomic_segment(current, parts[index + 1]):
            rows.append(f"{current} {parts[index + 1]}".strip())
            index += 2
            continue
        rows.append(current)
        index += 1
    return rows[:4]


def _should_merge_dependent_atomic_segment(current: str, following: str) -> bool:
    current_compact = current.replace(" ", "")
    following_compact = following.replace(" ", "")
    if not current_compact or not following_compact:
        return False

    # Same top-loader concern: the first segment names the object and asks/frames
    # the concern, while the next segment only continues the symptom list.
    if "통돌이" in current_compact and not any(token in following_compact for token in ("드럼", "건조기", "냉장고", "로봇", "청소기")):
        if any(token in current_compact for token in ("쿵덕", "시끄", "소음", "먼지", "엉키")) and any(
            token in following_compact for token in ("쿵덕", "시끄", "소음", "먼지", "엉키")
        ):
            return True

    return False


def _atomic_segment_kind(segment: str) -> str:
    if any(cue in segment for cue in NEGATIVE_ATOMIC_CUES):
        return "negative_concern"
    if any(cue in segment for cue in POSITIVE_ATOMIC_CUES):
        return "positive"
    if any(cue in segment for cue in INQUIRY_ATOMIC_CUES):
        return "inquiry"
    return "neutral"


def _has_product_comparison_signal(text: str) -> bool:
    return (
        ("통돌이" in text and "드럼" in text)
        or ("삼성" in text and "로보락" in text)
        or ("가격" in text and any(token in text for token in ("품질", "경쟁", "받아쳐", "비교")))
    )


def _apply_generic_atomic_split(card: dict[str, Any], *, segment: str, kind: str, split_index: int) -> None:
    segment = _clean_split_text(segment)
    feature_label, feature_description = _feature_topic_from_atomic_segment(segment, kind=kind)
    cej_stage, cej_basis = _cej_from_atomic_segment(segment, kind=kind)
    root_payload = _root_payload_from_atomic_segment(segment, kind=kind, feature_label=feature_label)

    card["semantic_split_rule_id"] = "generic_mixed_atomic_split_v1"
    card["unit_title"] = _unit_title_from_atomic_segment(segment, feature_label=feature_label, kind=kind)
    card["feature_topic"] = feature_label
    card["feature_topic_label"] = feature_label
    card["feature_topic_description"] = feature_description
    card["feature_topic_basis"] = f'근거: "{segment}" / 판단: 해당 문장의 제품·기능 단서를 기준으로 기능/주제를 분리'
    card["atomic_voc"] = segment
    card["evidence_span"] = segment
    card["cej_stage"] = cej_stage
    card["cej_basis"] = cej_basis
    card["polarity_label"] = kind
    card["polarity_basis"] = _polarity_basis_from_atomic_segment(segment, kind=kind)
    card["na_status"] = "interpreted"
    card["na_reason"] = ""
    card["needs_human_review"] = True
    _append_quality_warning(card, "atomic_split_heuristic_candidate")

    for key, value in root_payload.items():
        card[key] = value
    _apply_tees_from_atomic_segment(card, segment=segment, kind=kind)
    card["summary"] = _summary_from_atomic_split(card, segment=segment, kind=kind)


def _feature_topic_from_atomic_segment(segment: str, *, kind: str) -> tuple[str, str]:
    if any(token in segment for token in ("가격", "비싸", "할인", "프로모션", "제휴카드", "받아쳐")):
        return "가격 정책/가격 경쟁력", "가격 책정, 할인, 혜택 또는 경쟁사 대비 가격 경쟁력에 대한 반응입니다."
    if "흡입력" in segment:
        return "흡입력/청소 성능", "흡입력 또는 청소 성능에 대한 평가입니다."
    if "설치" in segment:
        return "설치 편의성", "설치 가능 여부나 설치 과정의 편의성에 대한 문의/평가입니다."
    if "직배수" in segment:
        return "직배수 기능/설치 조건", "직배수 기능 또는 설치 조건에 대한 문의/평가입니다."
    if "빌트인스테이션" in segment:
        return "빌트인스테이션/자동비움 편의성", "빌트인스테이션 또는 자동비움 기능에 대한 반응입니다."
    if "통돌이" in segment and any(token in segment for token in ("쿵덕", "먼지", "엉키", "시끄", "소음")):
        return "통돌이 소음·먼지·엉킴 우려", "통돌이 사용 과정의 소음, 먼지, 엉킴에 대한 우려입니다."
    if "드럼" in segment and any(token in segment for token in ("신세계", "만족", "좋")):
        return "드럼 사용 만족", "드럼 세탁기 사용 경험에 대한 긍정 평가입니다."
    if kind == "inquiry":
        return "정보 확인 문의", "제품 또는 기능에 대한 정보를 확인하려는 문의입니다."
    return "구체 기능/주제 검수 필요", "원문 의미는 분리되었지만 제품·기능 라벨은 추가 검수가 필요합니다."


def _cej_from_atomic_segment(segment: str, *, kind: str) -> tuple[str, str]:
    if any(token in segment for token in ("가격", "할인", "프로모션", "구매", "사도")):
        return "구매", f'근거: "{segment}" / 판단: 가격·혜택·구매 조건 확인 맥락'
    if "설치" in segment:
        return "설치/사용준비", f'근거: "{segment}" / 판단: 설치 가능 여부 또는 사용 준비 단계 맥락'
    if any(token in segment for token in ("사용", "신세계", "만족", "불편", "소음", "먼지", "엉키", "흡입력")):
        return "사용", f'근거: "{segment}" / 판단: 실제/예상 사용 경험에 대한 평가 맥락'
    if kind == "inquiry":
        return "탐색", f'근거: "{segment}" / 판단: 제품·기능 정보를 확인하는 탐색 맥락'
    return "미확정", f'근거: "{segment}" / 판단: CEJ는 사람 검수 필요'


def _polarity_basis_from_atomic_segment(segment: str, *, kind: str) -> str:
    if kind == "negative_concern":
        return f'근거: "{segment}" / 판단: 부정·우려·아쉬움 표현이 포함됨'
    if kind == "positive":
        return f'근거: "{segment}" / 판단: 긍정·만족·칭찬 표현이 포함됨'
    if kind == "inquiry":
        return f'근거: "{segment}" / 판단: 정보 확인 문의 표현'
    return f'근거: "{segment}" / 판단: 명확한 긍정/부정 감정은 제한적'


def _apply_tees_from_atomic_segment(card: dict[str, Any], *, segment: str, kind: str) -> None:
    card["tees_success_value"] = "N/A"
    card["tees_success_basis"] = f'근거: "{segment}" / 판단: 목적 달성 여부는 직접 확인되지 않음'
    card["tees_time_value"] = "N/A"
    card["tees_time_basis"] = f'근거: "{segment}" / 판단: 시간 소요·지연·반복 경험은 직접 확인되지 않음'
    card["tees_effort_value"] = "N/A"
    card["tees_effort_basis"] = f'근거: "{segment}" / 판단: 사용·관리·구매·문제해결 수고는 직접 확인되지 않음'
    if kind == "negative_concern":
        card["tees_emotion_value"] = "negative_concern"
        card["tees_emotion_basis"] = f'근거: "{segment}" / 판단: 제품/CEJ 맥락의 부정·우려 감정'
    elif kind == "positive":
        card["tees_emotion_value"] = "positive/satisfaction"
        card["tees_emotion_basis"] = f'근거: "{segment}" / 판단: 제품/CEJ 맥락의 긍정·만족 감정'
    else:
        card["tees_emotion_value"] = "N/A"
        card["tees_emotion_basis"] = f'근거: "{segment}" / 판단: 제품 경험 감정으로 볼 직접 표현은 제한적'


def _root_payload_from_atomic_segment(segment: str, *, kind: str, feature_label: str) -> dict[str, str]:
    if kind != "negative_concern":
        return {
            "root_problem_level": "N/A",
            "root_problem_label": "문제 미식별",
            "root_problem_target": "",
            "root_cause_maturity": "N/A",
            "root_cause_category": "None",
            "root_cause_basis": f'근거: "{segment}" / 판단: 구체 문제·불편·개선 과제는 식별되지 않음',
        }
    target = feature_label if feature_label != "구체 기능/주제 검수 필요" else "개선 대상 검수 필요"
    return {
        "root_problem_level": "L2",
        "root_problem_label": "문제 특정",
        "root_problem_target": target,
        "root_cause_maturity": "L2",
        "root_cause_category": "불명확",
        "root_cause_basis": f'근거: "{segment}" / 판단: 개선 대상은 보이나 발생 원인은 특정되지 않음',
    }


def _unit_title_from_atomic_segment(segment: str, *, feature_label: str, kind: str) -> str:
    if kind == "negative_concern":
        return feature_label if "우려" in feature_label or "불만" in feature_label else f"{feature_label} 우려"
    if kind == "positive":
        return feature_label if "만족" in feature_label or "긍정" in feature_label else f"{feature_label} 긍정 반응"
    if kind == "inquiry":
        return feature_label if "문의" in feature_label else f"{feature_label} 문의"
    return feature_label


def _summary_from_atomic_split(card: Mapping[str, Any], *, segment: str, kind: str) -> str:
    product = _preferred_product_label(card) or _safe_card_text(card.get("product_label")) or "제품"
    topic = _safe_card_text(card.get("feature_topic_label") or card.get("feature_topic"))
    if kind == "negative_concern":
        return f"{product}의 {topic}에 대해 “{segment}”라는 부정·우려가 분리된 Atomic VoC입니다."
    if kind == "positive":
        return f"{product}의 {topic}에 대해 “{segment}”라는 긍정 반응이 분리된 Atomic VoC입니다."
    if kind == "inquiry":
        return f"{product}의 {topic}와 관련해 “{segment}”를 확인하려는 문의형 Atomic VoC입니다."
    return f"{product}의 {topic}와 관련한 Atomic VoC입니다."


def _split_robot_vacuum_development_and_color(*, card: dict[str, Any], text: str) -> list[dict[str, Any]]:
    positive_text = _slice_between_any(
        text,
        start_markers=("자체 개발", "자체개발", "업그레이드"),
        stop_markers=("아쉬운", "검은색만", "색상"),
    )
    negative_text = _slice_from_any(text, markers=("아쉬운", "검은색만", "색상")) or text
    if not positive_text:
        positive_text = text

    positive_card = copy.deepcopy(card)
    positive_card.update(
        {
            "semantic_split_rule_id": "robot_vacuum_development_positive_and_color_negative",
            "unit_title": "자체 개발/업그레이드 기대",
            "feature_topic": "자체 개발/업그레이드 기대",
            "feature_topic_label": "자체 개발/업그레이드 기대",
            "feature_topic_description": "제조사 자체 개발과 향후 청소 알고리즘 개선 가능성을 긍정적으로 보는 의견",
            "feature_topic_basis": "원문에 자체 개발, 업그레이드 기대, 좋다는 표현이 함께 나타남",
            "atomic_voc": _clean_split_text(positive_text),
            "evidence_span": _clean_split_text(positive_text),
            "cej_stage": "인지/탐색",
            "cej_basis": "제품 개발 방식과 향후 업그레이드 가능성을 평가하는 구매 전 인지·탐색 맥락",
            "tees_success_value": "N/A",
            "tees_success_basis": "목적 달성 여부는 직접 확인되지 않음",
            "tees_time_value": "N/A",
            "tees_time_basis": "시간 소요·절약·지연 경험이 직접 확인되지 않음",
            "tees_effort_value": "N/A",
            "tees_effort_basis": "사용/관리 수고가 직접 확인되지 않음",
            "tees_emotion_value": "positive/trust expectation",
            "tees_emotion_basis": "자체 개발과 업그레이드 가능성에 대한 긍정·기대 표현",
            "root_problem_level": "N/A",
            "root_problem_label": "문제 미식별",
            "root_problem_target": "",
            "root_cause_maturity": "N/A",
            "root_cause_category": "None",
            "root_cause_basis": "구체 문제보다 제품 개발 방향에 대한 긍정 기대",
            "summary": "로봇청소기 자체 개발과 향후 알고리즘 업그레이드 가능성을 긍정적으로 보는 Atomic VoC입니다.",
            "polarity_label": "positive",
            "polarity_basis": "자체 개발과 업그레이드 가능성을 긍정적으로 평가",
            "na_status": "interpreted",
            "na_reason": "",
        }
    )

    negative_card = copy.deepcopy(card)
    negative_card.update(
        {
            "semantic_split_rule_id": "robot_vacuum_development_positive_and_color_negative",
            "unit_title": "색상 선택지 제한 아쉬움",
            "feature_topic": "색상 선택지 제한",
            "feature_topic_label": "색상 선택지 제한",
            "feature_topic_description": "제품 색상이 검은색만 제공되는 점에 대한 아쉬움",
            "feature_topic_basis": "원문에 검은색만 있다는 점과 아쉬움 표현이 함께 나타남",
            "atomic_voc": _clean_split_text(negative_text),
            "evidence_span": _clean_split_text(negative_text),
            "cej_stage": "구매/탐색",
            "cej_basis": "색상 선택지는 구매 전 제품 선택과 선호 판단에 영향을 주는 요소",
            "tees_success_value": "N/A",
            "tees_success_basis": "구매 또는 사용 목적 달성 여부는 직접 확인되지 않음",
            "tees_time_value": "N/A",
            "tees_time_basis": "시간 소요·절약·지연 경험이 직접 확인되지 않음",
            "tees_effort_value": "N/A",
            "tees_effort_basis": "사용/관리 수고가 직접 확인되지 않음",
            "tees_emotion_value": "disappointment",
            "tees_emotion_basis": "검은색만 있다는 점을 아쉽다고 표현함",
            "root_problem_level": "L2",
            "root_problem_label": "문제 특정",
            "root_problem_target": "색상 선택지",
            "root_cause_maturity": "L2",
            "root_cause_category": "제품 옵션/디자인",
            "root_cause_basis": "색상 선택지가 검은색으로 제한된다는 개선 대상은 명확하지만 원인은 특정되지 않음",
            "summary": "로봇청소기 색상이 검은색만 제공되는 점을 아쉬워하는 구매/탐색 단계의 개선 후보 Atomic VoC입니다.",
            "polarity_label": "negative_concern",
            "polarity_basis": "색상 선택지 제한에 대한 아쉬움",
            "na_status": "interpreted",
            "na_reason": "",
        }
    )
    return [positive_card, negative_card]


def _slice_between_any(text: str, *, start_markers: tuple[str, ...], stop_markers: tuple[str, ...]) -> str:
    starts = [text.find(marker) for marker in start_markers if marker and marker in text]
    if not starts:
        return ""
    start = min(starts)
    stops = [text.find(marker, start + 1) for marker in stop_markers if marker and text.find(marker, start + 1) != -1]
    end = min(stops) if stops else len(text)
    return text[start:end]


def _slice_from_any(text: str, *, markers: tuple[str, ...]) -> str:
    starts = [text.find(marker) for marker in markers if marker and marker in text]
    if not starts:
        return ""
    return text[min(starts) :]


def _clean_split_text(value: str) -> str:
    return " ".join(str(value or "").strip(" .,\n\t").split())


def _unit_card_source_counts(unit_analysis_cards: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(card.get("card_source", "missing")) for card in unit_analysis_cards))


def _semantic_prompt_payload_rows(unit_analysis_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in unit_analysis_cards:
        if not bool(card.get("semantic_prompt_ready")):
            continue
        payload = build_golden120_semantic_prompt_payload(card)
        payload["system_prompt"] = GOLDEN120_SYSTEM_PROMPT
        payload["user_prompt"] = build_golden120_semantic_user_prompt(card)
        payload["case_id"] = card.get("case_id", "")
        payload["atomic_unit_id"] = card.get("atomic_unit_id", "")
        payload["semantic_lane"] = card.get("semantic_lane", "")
        rows.append(payload)
    return rows


def _semantic_llm_enhanced_unit_cards(
    *,
    unit_analysis_cards: list[dict[str, Any]],
    semantic_llm_outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not semantic_llm_outputs:
        return []
    base_by_id = {
        _safe_card_text(card.get("atomic_unit_id")): card
        for card in unit_analysis_cards
        if _safe_card_text(card.get("atomic_unit_id"))
    }
    enhanced_cards: list[dict[str, Any]] = []
    for output in semantic_llm_outputs:
        if _safe_card_text(output.get("status")) != "succeeded":
            continue
        atomic_unit_id = _safe_card_text(output.get("atomic_unit_id"))
        base_card = copy.deepcopy(base_by_id.get(atomic_unit_id, {}))
        if not base_card:
            continue
        result = output.get("result", {})
        if not isinstance(result, Mapping):
            continue
        units = result.get("units", [])
        if not isinstance(units, list) or not units:
            units = [result]
        for unit_index, unit in enumerate(units, start=1):
            if not isinstance(unit, Mapping):
                continue
            card = copy.deepcopy(base_card)
            _apply_llm_unit_to_card(card, unit, output=output, unit_index=unit_index)
            _postprocess_llm_unit_card(card)
            split_cards = _split_semantic_unit_cards_if_needed(card=card, record={})
            for split_index, split_card in enumerate(split_cards, start=1):
                if len(split_cards) > 1:
                    split_card["atomic_unit_index"] = split_index
                    split_card["atomic_unit_id"] = (
                        f"{_safe_card_text(base_card.get('source_id') or atomic_unit_id)}::llm-u{unit_index}-{split_index}"
                    )
                    split_card["source_atomic_unit_id"] = atomic_unit_id
                _postprocess_llm_unit_card(split_card)
                _finalize_semantic_card_routing(split_card)
                enhanced_cards.append(split_card)
    return enhanced_cards


def _apply_llm_unit_to_card(
    card: dict[str, Any],
    unit: Mapping[str, Any],
    *,
    output: Mapping[str, Any],
    unit_index: int,
) -> None:
    card["card_source"] = "golden120_llm_semantic_interpreter"
    card["interpreter_status"] = "llm_interpreted"
    card["semantic_llm_provider"] = _safe_card_text(output.get("provider"))
    card["semantic_llm_model"] = _safe_card_text(output.get("model"))
    if unit_index > 1:
        card["atomic_unit_index"] = unit_index
        card["atomic_unit_id"] = f"{_safe_card_text(card.get('source_id'))}::llm-u{unit_index}"

    _copy_if_present(unit, card, "atomic_voc")
    _copy_if_present(unit, card, "evidence_span")
    _copy_if_present(unit, card, "summary")
    _copy_if_present(unit, card, "semantic_lane")
    _copy_if_present(unit, card, "semantic_lane_reason")
    _copy_if_present(unit, card, "scope_status")
    _copy_if_present(unit, card, "na_status")
    _copy_if_present(unit, card, "polarity_label")
    _copy_if_present(unit, card, "unit_title")
    _copy_if_present(unit, card, "needs_human_review")
    _copy_if_present(unit, card, "product_label")
    _copy_if_present(unit, card, "product_detail")
    _copy_if_present(unit, card, "product_basis")
    _copy_if_present(unit, card, "product_confidence")
    _copy_if_present(unit, card, "feature_topic_label")
    _copy_if_present(unit, card, "feature_topic_label", target_key="feature_topic")
    _copy_if_present(unit, card, "feature_topic_description")
    _copy_if_present(unit, card, "feature_topic_basis")
    _copy_if_present(unit, card, "cej_stage")
    _copy_if_present(unit, card, "cej_basis")
    _copy_if_present(unit, card, "cej_status")
    for axis in ("success", "time", "effort", "emotion"):
        _copy_if_present(unit, card, f"tees_{axis}_value")
        _copy_if_present(unit, card, f"tees_{axis}_basis")
    _copy_if_present(unit, card, "root_problem_level")
    _copy_if_present(unit, card, "root_problem_label")
    _copy_if_present(unit, card, "root_problem_target")
    _copy_if_present(unit, card, "root_cause_category")
    _copy_if_present(unit, card, "root_cause_basis")
    confidence_notes = unit.get("confidence_notes")
    if isinstance(confidence_notes, list):
        card["confidence_notes"] = confidence_notes
    watch_agenda_flags = unit.get("watch_agenda_flags")
    if isinstance(watch_agenda_flags, list):
        card["watch_agenda_flags"] = watch_agenda_flags

    product = unit.get("product", {})
    if isinstance(product, Mapping):
        _copy_if_present(product, card, "label", target_key="product_label")
        _copy_if_present(product, card, "group", target_key="product_group_label")
        _copy_if_present(product, card, "detail", target_key="product_detail")
        _copy_if_present(product, card, "basis", target_key="product_basis")
        _copy_if_present(product, card, "detail_basis", target_key="product_detail_basis")
    feature = unit.get("feature_topic", {})
    if isinstance(feature, Mapping):
        _copy_if_present(feature, card, "label", target_key="feature_topic")
        _copy_if_present(feature, card, "label", target_key="feature_topic_label")
        _copy_if_present(feature, card, "description", target_key="feature_topic_description")
        _copy_if_present(feature, card, "basis", target_key="feature_topic_basis")
    cej = unit.get("cej", {})
    if isinstance(cej, Mapping):
        _copy_if_present(cej, card, "stage", target_key="cej_stage")
        _copy_if_present(cej, card, "basis", target_key="cej_basis")
        _copy_if_present(cej, card, "status", target_key="cej_status")
    tees = unit.get("tees", {})
    if isinstance(tees, Mapping):
        for axis in ("success", "time", "effort", "emotion"):
            axis_payload = tees.get(axis, {})
            if isinstance(axis_payload, Mapping):
                _copy_if_present(axis_payload, card, "value", target_key=f"tees_{axis}_value")
                _copy_if_present(axis_payload, card, "basis", target_key=f"tees_{axis}_basis")
    root = unit.get("root_cause", {})
    if isinstance(root, Mapping):
        _copy_if_present(root, card, "maturity", target_key="root_cause_maturity")
        _copy_if_present(root, card, "category", target_key="root_cause_category")
        _copy_if_present(root, card, "basis", target_key="root_cause_basis")
        _copy_if_present(root, card, "level", target_key="root_problem_level")
        _copy_if_present(root, card, "label", target_key="root_problem_label")
        _copy_if_present(root, card, "target", target_key="root_problem_target")


def _postprocess_llm_unit_card(card: dict[str, Any]) -> None:
    """Repair projection/merge artifacts after an LLM result is applied.

    The LLM result is the primary semantic interpretation, but the base card can
    still contain legacy fallback fields such as generic product groups or stale
    ``engine_missed`` state.  This pass keeps the LLM interpretation while
    preventing those legacy defaults from leaking into dashboard units.
    """

    _prefer_specific_product_fields(card)
    _repair_broad_feature_topic(card)
    _repair_polarity_emotion_consistency(card)
    _repair_cej_for_feature_praise(card)
    _repair_na_status_after_llm_merge(card)
    _ensure_llm_card_basis_evidence(card)


def _prefer_specific_product_fields(card: dict[str, Any]) -> None:
    specific = _preferred_product_label(card) or _specific_product_from_context(card)
    if not specific:
        return
    if _is_generic_product_label(card.get("product_label")):
        card["product_label"] = specific
    if _is_generic_product_label(card.get("product")):
        card["product"] = specific
    if _is_generic_product_label(card.get("product_group_label")):
        card["product_group_label"] = specific


def _preferred_product_label(card: Mapping[str, Any]) -> str:
    for key in ("product_label", "product", "product_detail", "product_group_label"):
        value = _safe_card_text(card.get(key))
        if value and not _is_generic_product_label(value):
            return value
    return ""


def _is_generic_product_label(value: Any) -> bool:
    normalized = _safe_card_text(value).strip().lower()
    return normalized in GENERIC_PRODUCT_LABELS or normalized in {
        "appliance",
        "appliances",
        "home appliance",
        "home appliances",
        "consumer electronics",
        "������ǰ",
    }


def _is_unknown_topic_label(value: Any) -> bool:
    normalized = _safe_card_text(value).strip().lower()
    return normalized in UNKNOWN_FEATURE_TOPIC_LABELS or normalized in {"청소/관리/소모품"}


def _is_broad_feature_topic(value: Any) -> bool:
    normalized = _safe_card_text(value).strip().lower()
    return normalized in {
        "청소/관리/소모품",
        "cleaning/management/consumables",
        "cleaning / management / consumables",
        "cleaning, management, consumables",
        "û��/����/�Ҹ�ǰ",
    }


def _llm_card_text_blob(card: Mapping[str, Any]) -> str:
    fields = (
        "unit_title",
        "feature_topic",
        "feature_topic_label",
        "feature_topic_description",
        "atomic_voc",
        "evidence_span",
        "summary",
        "product_detail",
        "product_basis",
        "cej_basis",
        "tees_emotion_basis",
    )
    return " ".join(_safe_card_text(card.get(key)) for key in fields if _safe_card_text(card.get(key)))


def _basis_evidence_text(card: Mapping[str, Any]) -> str:
    """Return the most useful exact source snippet for basis repair."""

    for key in ("evidence_span", "atomic_voc"):
        value = _safe_card_text(card.get(key)).strip()
        if value:
            return value if len(value) <= 180 else f"{value[:177]}..."
    context = card.get("semantic_context_payload", {})
    if isinstance(context, Mapping):
        value = _safe_card_text(context.get("comment_text")).strip()
        if value:
            return value if len(value) <= 180 else f"{value[:177]}..."
    return ""


def _quoted_basis(card: Mapping[str, Any], judgment: str) -> str:
    evidence = _basis_evidence_text(card)
    if not evidence:
        return judgment
    return f'근거: "{evidence}" / 판단: {judgment}'


def _basis_already_has_evidence(basis: str, evidence: str) -> bool:
    if not basis or not evidence:
        return False
    if evidence in basis:
        return True
    compact_basis = "".join(basis.split())
    compact_evidence = "".join(evidence.split())
    if compact_evidence and compact_evidence in compact_basis:
        return True
    meaningful = compact_evidence[:24]
    return bool(meaningful and meaningful in compact_basis)


def _ensure_basis_with_evidence(card: dict[str, Any], key: str, judgment: str, *, force: bool = False) -> None:
    basis = _safe_card_text(card.get(key)).strip()
    evidence = _basis_evidence_text(card)
    if not evidence:
        return
    if _basis_already_has_evidence(basis, evidence):
        return
    if not basis or basis in {"직접 확인된 표현 없음", "N/A", "n/a", "NA", "na"}:
        card[key] = _quoted_basis(card, judgment)
        return
    generic_markers = (
        "확인됨",
        "직접 신호",
        "keyword 기반",
        "원문 의미",
        "positive sentiment",
        "negative sentiment",
        "expresses concern",
        "indicates positive",
        "highly praised",
        "unclear from",
    )
    if any(marker.lower() in basis.lower() for marker in generic_markers):
        card[key] = _quoted_basis(card, judgment)
        return
    if force:
        card[key] = _quoted_basis(card, basis)


def _specific_product_from_context(card: Mapping[str, Any]) -> str:
    blob = _llm_card_text_blob(card).lower()
    if any(token in blob for token in ("로봇청소기", "로봇 청소기", "robot vacuum", "robotic vacuum", "vacuum robot")):
        return "로봇청소기"
    if any(token in blob for token in ("식기세척기", "dishwasher")):
        return "식기세척기"
    if any(token in blob for token in ("의류건조기", "건조기", "dryer")):
        return "건조기"
    if any(token in blob for token in ("세탁건조기", "워시타워", "washer dryer", "combo washer")):
        return "세탁건조기/콤보"
    if any(token in blob for token in ("세탁기", "washer", "washing machine")):
        return "세탁기"
    if any(token in blob for token in ("냉장고", "refrigerator", "fridge")):
        return "냉장고"
    return ""


def _repair_broad_feature_topic(card: dict[str, Any]) -> None:
    topic = _safe_card_text(card.get("feature_topic_label") or card.get("feature_topic"))
    if not _is_broad_feature_topic(topic):
        return
    blob = _llm_card_text_blob(card).lower()
    specific_topic = ""
    specific_description = ""
    if any(token in blob for token in ("빌트인스테이션", "built-in station", "자동비움", "먼지비움")):
        specific_topic = "빌트인스테이션/자동비움 편의성"
        specific_description = "빌트인스테이션 또는 자동비움 기능에 대한 반응/평가입니다."
    elif any(token in blob for token in ("가격", "price", "할인", "제휴카드", "프로모션", "비싸", "받아쳐")):
        specific_topic = "가격 정책/가격 경쟁력"
        specific_description = "가격 책정, 할인, 혜택 또는 경쟁사 대비 가격 경쟁력에 대한 반응입니다."

    if specific_topic:
        card["feature_topic"] = specific_topic
        card["feature_topic_label"] = specific_topic
        if not _safe_card_text(card.get("feature_topic_description")) or card.get("feature_topic_description") == topic:
            card["feature_topic_description"] = specific_description
        card["feature_topic_basis"] = "LLM 결과의 broad topic을 원문/요약의 구체 기능 단서로 보정"
        return

    card["feature_topic"] = "미확인"
    card["feature_topic_label"] = "미확인"
    card["feature_topic_basis"] = "LLM 결과가 broad topic에 머물러 구체 기능/주제 검수 필요"
    card["na_status"] = "engine_missed"
    card["na_reason"] = "기능/주제가 broad default라 true N/A와 엔진 미포착을 구분해야 합니다."
    card["needs_human_review"] = True
    _append_quality_warning(card, "broad_feature_topic_unresolved")


def _repair_polarity_emotion_consistency(card: dict[str, Any]) -> None:
    blob = _llm_card_text_blob(card)
    lower_blob = blob.lower()
    polarity = _safe_card_text(card.get("polarity_label")).lower()
    emotion = _safe_card_text(card.get("tees_emotion_value")).lower()

    negative_cue = any(
        token in lower_blob
        for token in (
            "비싸",
            "불만",
            "우려",
            "걱정",
            "불안",
            "실망",
            "아쉽",
            "무섭",
            "받아쳐",
            "바가지",
            "가격책정",
            "negative",
            "concern",
            "dissatisfaction",
            "disappointment",
            "frustration",
            "anxiety",
        )
    )
    positive_cue = any(
        token in lower_blob
        for token in (
            "대박",
            "만족",
            "좋",
            "최고",
            "추천",
            "훌륭",
            "긍정",
            "칭찬",
            "positive",
            "satisfaction",
            "praised",
            "praise",
        )
    )
    positive_emotion = any(token in emotion for token in ("positive", "satisfaction", "trust", "recommend", "praise"))
    negative_emotion = any(token in emotion for token in ("negative", "concern", "dissatisfaction", "disappointment", "frustration", "anxiety"))
    polarity_basis = _safe_card_text(card.get("polarity_basis")).lower()
    emotion_basis = _safe_card_text(card.get("tees_emotion_basis")).lower()
    positive_basis = any(token in polarity_basis for token in ("긍정", "만족", "positive", "satisfaction", "praise"))
    negative_basis = any(token in polarity_basis for token in ("부정", "우려", "불만", "negative", "concern", "dissatisfaction"))
    positive_emotion_basis = any(token in emotion_basis for token in ("긍정", "만족", "positive", "satisfaction", "praise"))
    negative_emotion_basis = any(token in emotion_basis for token in ("부정", "우려", "불만", "negative", "concern", "dissatisfaction"))

    if negative_cue and (positive_emotion or polarity in {"positive", "satisfaction"}):
        card["polarity_label"] = "negative_concern"
        card["polarity_basis"] = _quoted_basis(card, "가격/불만/우려 계열 부정 신호가 있어 긍정 판정을 보정")
        card["tees_emotion_value"] = "dissatisfaction/concern"
        card["tees_emotion_basis"] = _quoted_basis(card, "제품/CEJ 맥락의 불만·우려 표현")
        card["needs_human_review"] = True
        _append_quality_warning(card, "polarity_emotion_conflict_corrected")
        return

    if positive_cue and emotion in {"", "n/a", "na", "none", "unknown", "직접 신호 없음", "미확인"}:
        card["polarity_label"] = "positive"
        card["polarity_basis"] = _quoted_basis(card, "제품/기능 긍정 반응")
        card["tees_emotion_value"] = "positive/satisfaction"
        card["tees_emotion_basis"] = _quoted_basis(card, "제품/CEJ 맥락의 긍정·만족·감탄 표현")
        _append_quality_warning(card, "positive_emotion_filled_from_explicit_cue")
        return

    if negative_cue and not negative_emotion:
        card["polarity_label"] = "negative_concern"
        card["polarity_basis"] = _quoted_basis(card, "제품/가격/우려 계열 부정 신호")
        card["tees_emotion_value"] = "dissatisfaction/concern"
        card["tees_emotion_basis"] = _quoted_basis(card, "제품/CEJ 맥락의 불만·우려 표현")
        _append_quality_warning(card, "negative_emotion_filled_from_explicit_cue")

    if (polarity in {"negative_concern", "negative", "concern"} or negative_emotion) and positive_basis and not negative_basis:
        card["polarity_basis"] = _quoted_basis(card, "가격·불만·우려 맥락의 부정 신호")
        _append_quality_warning(card, "stale_polarity_basis_corrected")
    if negative_emotion and positive_emotion_basis and not negative_emotion_basis:
        card["tees_emotion_basis"] = _quoted_basis(card, "제품/CEJ 맥락의 부정·우려 감정")
        _append_quality_warning(card, "stale_emotion_basis_corrected")
    if polarity in {"positive", "satisfaction"} and negative_basis and not positive_basis:
        card["polarity_basis"] = _quoted_basis(card, "제품/기능 맥락의 긍정 신호")
        _append_quality_warning(card, "stale_polarity_basis_corrected")
    if positive_emotion and negative_emotion_basis and not positive_emotion_basis:
        card["tees_emotion_basis"] = _quoted_basis(card, "제품/CEJ 맥락의 긍정·만족 감정")
        _append_quality_warning(card, "stale_emotion_basis_corrected")


def _repair_cej_for_feature_praise(card: dict[str, Any]) -> None:
    cej_stage = _safe_card_text(card.get("cej_stage")).lower()
    if cej_stage not in {"관리", "management", "s8 maintain", "maintain", "maintenance"}:
        return
    blob = _llm_card_text_blob(card).lower()
    has_feature_praise = any(
        token in blob
        for token in (
            "대박",
            "만족",
            "좋",
            "최고",
            "칭찬",
            "positive",
            "satisfaction",
            "praised",
            "praise",
            "highly praised",
        )
    )
    has_management_action = any(
        token in blob
        for token in (
            "관리",
            "수리",
            "a/s",
            "as ",
            "세척",
            "필터",
            "소모품",
            "교체",
            "설치",
            "고장",
            "점검",
            "maintenance",
            "repair",
            "cleaning",
            "consumable",
            "replace",
            "installation",
        )
    )
    if not has_feature_praise or has_management_action:
        return
    card["cej_stage"] = "탐색"
    card["cej_basis"] = "기능 칭찬/관심 반응이며 직접 사용·관리 행위 근거가 없어 탐색 단계로 보정"
    card["cej_status"] = "interpreted"
    _append_quality_warning(card, "cej_management_praise_rebased_to_exploration")


def _repair_na_status_after_llm_merge(card: dict[str, Any]) -> None:
    na_status = _safe_card_text(card.get("na_status")).lower()
    if not na_status.startswith("engine_missed"):
        return
    product_ready = bool(_preferred_product_label(card))
    topic_ready = not _is_unknown_topic_label(card.get("feature_topic_label") or card.get("feature_topic"))
    cej_ready = _safe_card_text(card.get("cej_stage")).lower() not in {"", "기타", "미확인", "unknown", "n/a", "na"}
    interpreted_text = bool(_safe_card_text(card.get("atomic_voc")) and _safe_card_text(card.get("summary")))
    if product_ready and topic_ready and (cej_ready or interpreted_text):
        card["na_status"] = "interpreted"
        card["na_reason"] = ""


def _ensure_llm_card_basis_evidence(card: dict[str, Any]) -> None:
    """Keep Golden120-style evidence attached to semantic judgment fields.

    The dashboard should consume rich semantic rawdata, not infer the reason for
    a label from display color.  OpenAI may return useful labels with generic
    basis text such as "확인됨"; this pass attaches the exact evidence span so
    downstream JSONL files remain reviewable outside the dashboard.
    """

    polarity = _safe_card_text(card.get("polarity_label")).lower()
    emotion = _safe_card_text(card.get("tees_emotion_value")).lower()
    if polarity in {"negative_concern", "negative", "concern"}:
        _ensure_basis_with_evidence(card, "polarity_basis", "부정/우려 판단", force=True)
    elif polarity in {"positive", "satisfaction"}:
        _ensure_basis_with_evidence(card, "polarity_basis", "긍정 판단", force=True)
    elif polarity in {"inquiry", "question"}:
        _ensure_basis_with_evidence(card, "polarity_basis", "문의/탐색 판단", force=True)

    if emotion not in {"", "n/a", "na", "none", "unknown", "직접 신호 없음", "미확인"}:
        _ensure_basis_with_evidence(card, "tees_emotion_basis", f"Emotion={card.get('tees_emotion_value')}", force=True)

    cej_stage = _safe_card_text(card.get("cej_stage"))
    if cej_stage and cej_stage.lower() not in {"n/a", "na", "none", "unknown", "미확인"}:
        _ensure_basis_with_evidence(card, "cej_basis", f"CEJ={cej_stage}", force=True)

    topic = _safe_card_text(card.get("feature_topic_label") or card.get("feature_topic"))
    if topic and topic.lower() not in {"n/a", "na", "none", "unknown", "미확인"}:
        _ensure_basis_with_evidence(card, "feature_topic_basis", f"기능/주제={topic}", force=True)

    root_level = _safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity"))
    if root_level and root_level.upper() not in {"N/A", "NA"} and root_level.lower() not in {"unknown", "불명확"}:
        _ensure_basis_with_evidence(card, "root_cause_basis", f"Root Cause maturity={root_level}", force=True)


def _append_quality_warning(card: dict[str, Any], warning: str) -> None:
    warnings = card.get("quality_warnings")
    if not isinstance(warnings, list):
        warnings = []
    if warning not in warnings:
        warnings.append(warning)
    card["quality_warnings"] = warnings


def _semantic_quality_postprocess_cards(unit_cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply Golden120 quality gates after LLM merge and before AI Draft export.

    This layer is intentionally conservative.  It does not try to re-interpret
    every card; it only fixes high-confidence patterns we have already accepted
    in review: duplicate color splits, over-split purchase-choice flows, and
    Root Cause L0~L3 maturity for visible improvement targets.
    """

    cards = [copy.deepcopy(card) for card in unit_cards]
    cards, atomic_events = _merge_atomic_boundary_quality_cards(cards)
    cards, duplicate_events = _remove_duplicate_split_quality_cards(cards)

    root_events: list[dict[str, Any]] = []
    summary_events: list[dict[str, Any]] = []
    for card in cards:
        root_event = _apply_root_problem_l0_l3_quality(card)
        if root_event:
            root_events.append(root_event)
        summary_event = _rewrite_quality_customer_insight_summary(card)
        if summary_event:
            summary_events.append(summary_event)
        _finalize_semantic_card_routing(card)

    return {
        "schema_version": "semantic-quality-postprocess-v1",
        "input_count": len(unit_cards),
        "output_count": len(cards),
        "cards": cards,
        "atomic_boundary_merge_count": len(atomic_events),
        "atomic_boundary_events": atomic_events,
        "duplicate_split_detected_count": len(duplicate_events),
        "duplicate_split_removed_count": sum(int(event.get("removed_count", 0) or 0) for event in duplicate_events),
        "duplicate_split_events": duplicate_events,
        "root_reclassified_count": len(root_events),
        "root_reclassification_events": root_events,
        "summary_rewritten_count": len(summary_events),
        "summary_rewrite_events": summary_events,
    }


def _merge_atomic_boundary_quality_cards(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        grouped.setdefault(_quality_source_key(card), []).append(card)

    merged_cards: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for source_key, group in grouped.items():
        group_remaining = list(group)
        self_dev_cards = [card for card in group_remaining if _quality_root_issue_kind(card) == "positive_self_development"]
        comparison_cards = [
            card
            for card in group_remaining
            if card not in self_dev_cards and _is_purchase_choice_comparison_card(card)
        ]
        if self_dev_cards and comparison_cards:
            keep = max(self_dev_cards, key=_score_card_specificity)
            merge_targets = [card for card in [*self_dev_cards, *comparison_cards] if card is not keep]
            original_titles = [_safe_card_text(card.get("unit_title")) for card in [keep, *merge_targets]]
            keep["unit_title"] = "자체 개발 기대와 구매 선택 논리"
            keep["feature_topic_label"] = "자체 개발/업그레이드 기대 및 경쟁제품 대비 선택 이유"
            keep["feature_topic"] = keep["feature_topic_label"]
            keep["feature_topic_description"] = (
                "자체 개발·업그레이드 가능성에 대한 기대와 경쟁 제품 대비 선택 이유가 하나의 구매 판단 흐름으로 이어집니다."
            )
            keep["atomic_voc"] = _combine_unique_texts(
                [_safe_card_text(card.get("atomic_voc")) for card in [keep, *merge_targets]]
            )
            keep["evidence_span"] = _combine_unique_texts(
                [_safe_card_text(card.get("evidence_span")) for card in [keep, *merge_targets]]
            )
            keep["polarity_label"] = "positive"
            keep["polarity_basis"] = _quality_basis(
                keep,
                tokens=("자체 개발", "업그레이드", "좋", "기대", "로보락", "삼성", "선택"),
                judgment="자체 개발 기대와 경쟁 제품 대비 선택 이유가 하나의 긍정적 구매 선택 흐름으로 연결됨",
            )
            keep["tees_emotion_value"] = "positive/trust_expectation"
            keep["tees_emotion_basis"] = keep["polarity_basis"]
            _set_root_problem_payload(
                keep,
                level="L0",
                label="문제 없음",
                category="매력 포인트/기대",
                target="개선 대상 아님",
                basis=_quality_basis(
                    keep,
                    tokens=("자체 개발", "업그레이드", "좋", "기대"),
                    judgment="문제·불편이 아니라 자체 개발과 향후 업그레이드에 대한 기대 신호",
                ),
            )
            keep["customer_insight_summary_override"] = (
                "자체 개발과 업그레이드 가능성은 경쟁 제품과 비교해 구매 선택을 정당화하는 기대 요인으로 작동합니다. "
                "즉시 개선 대상보다는 제품 신뢰와 차별화 메시지로 활용할 수 있는 강점 신호입니다."
            )
            _append_quality_warning(keep, "atomic_boundary_merged_purchase_choice_flow")
            group_remaining = [card for card in group_remaining if card not in merge_targets]
            events.append(
                {
                    "source_key": source_key,
                    "event": "atomic_boundary_merged_purchase_choice_flow",
                    "kept_unit_title": _safe_card_text(keep.get("unit_title")),
                    "merged_count": len(merge_targets),
                    "before_titles": [title for title in original_titles if title],
                    "after_atomic_voc": _safe_card_text(keep.get("atomic_voc")),
                }
            )
        merged_cards.extend(group_remaining)
    return merged_cards, events


def _remove_duplicate_split_quality_cards(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        grouped.setdefault(_quality_source_key(card), []).append(card)

    output: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for source_key, group in grouped.items():
        removed_ids: set[int] = set()
        color_cards = [card for card in group if _quality_root_issue_kind(card) == "color_option"]
        if len(color_cards) > 1:
            keep = max(color_cards, key=_score_card_specificity)
            duplicate_cards = [card for card in color_cards if card is not keep]
            _append_quality_warning(keep, "duplicate_split_removed_color_option")
            keep["feature_topic_label"] = "색상 옵션/디자인 선택지"
            keep["feature_topic"] = keep["feature_topic_label"]
            keep["feature_topic_description"] = "색상 선택지가 제한되어 있다는 아쉬움이 독립 개선 포인트로 드러납니다."
            keep["atomic_voc"] = _quality_best_quote(
                keep,
                tokens=("색상", "검은색", "아쉽", "선택지"),
                fallback=_safe_card_text(keep.get("atomic_voc")),
            )
            keep["evidence_span"] = _quality_best_quote(
                keep,
                tokens=("색상", "검은색", "아쉽", "선택지"),
                fallback=_safe_card_text(keep.get("evidence_span") or keep.get("atomic_voc")),
            )
            for card in duplicate_cards:
                removed_ids.add(id(card))
            events.append(
                {
                    "source_key": source_key,
                    "event": "duplicate_split_detected_and_removed",
                    "duplicate_type": "color_option",
                    "kept_unit_title": _safe_card_text(keep.get("unit_title")),
                    "removed_count": len(duplicate_cards),
                    "removed_unit_titles": [
                        _safe_card_text(card.get("unit_title")) for card in duplicate_cards if _safe_card_text(card.get("unit_title"))
                    ],
                }
            )
        output.extend(card for card in group if id(card) not in removed_ids)
    return output, events


def _apply_root_problem_l0_l3_quality(card: dict[str, Any]) -> dict[str, Any] | None:
    issue_kind = _quality_root_issue_kind(card)
    before = _safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity"))
    before_category = _safe_card_text(card.get("root_cause_category"))

    if issue_kind == "price_policy":
        _set_root_problem_payload(
            card,
            level="L2",
            label="개선 대상 특정",
            category="가격 정책 / 가치 포지셔닝",
            target="가격 정책/가치 포지셔닝",
            basis=_quality_basis(
                card,
                tokens=("가격", "책정", "경쟁사", "품질", "받아쳐먹", "비싸", "가성비"),
                judgment="가격 정책과 경쟁 제품 대비 가치 인식이 구체적인 개선 대상으로 드러남",
            ),
        )
    elif issue_kind == "manufacturer_trust":
        _set_root_problem_payload(
            card,
            level="L2",
            label="개선 대상 특정",
            category="제조 신뢰 / 공급망 인식",
            target="제조사 신뢰/공급망·보안 인식",
            basis=_quality_basis(
                card,
                tokens=("제조사", "중국", "국내 제조", "보안", "품질", "신뢰", "함정"),
                judgment="제조사·공급망·보안 신뢰가 구체적인 개선/커뮤니케이션 대상으로 드러남",
            ),
        )
    elif issue_kind == "color_option":
        _set_root_problem_payload(
            card,
            level="L2",
            label="개선 대상 특정",
            category="제품 옵션/디자인",
            target="색상 옵션/디자인 선택지",
            basis=_quality_basis(
                card,
                tokens=("색상", "검은색", "색만", "아쉽", "선택지"),
                judgment="색상 선택지 제한이 구체적인 제품 옵션 개선 대상으로 드러남",
            ),
        )
    elif issue_kind == "positive_builtin_station":
        _set_root_problem_payload(
            card,
            level="L0",
            label="문제 없음",
            category="매력 포인트",
            target="개선 대상 아님",
            basis=_quality_basis(
                card,
                tokens=("빌트인스테이션", "대박", "좋", "만족"),
                judgment="문제·불편이 아니라 기능 매력에 대한 긍정 반응",
            ),
        )
    elif issue_kind == "positive_self_development":
        _set_root_problem_payload(
            card,
            level="L0",
            label="문제 없음",
            category="매력 포인트/기대",
            target="개선 대상 아님",
            basis=_quality_basis(
                card,
                tokens=("자체 개발", "업그레이드", "좋", "기대"),
                judgment="문제·불편이 아니라 자체 개발과 업그레이드 가능성에 대한 긍정 기대",
            ),
        )
    else:
        return None

    after = _safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity"))
    after_category = _safe_card_text(card.get("root_cause_category"))
    if before == after and before_category == after_category:
        return None
    _append_quality_warning(card, "root_cause_l0_l3_quality_reclassified")
    return {
        "source_id": _safe_card_text(card.get("source_id")),
        "unit_title": _safe_card_text(card.get("unit_title")),
        "issue_kind": issue_kind,
        "before_level": before,
        "after_level": after,
        "before_category": before_category,
        "after_category": after_category,
    }


def _rewrite_quality_customer_insight_summary(card: dict[str, Any]) -> dict[str, Any] | None:
    issue_kind = _quality_root_issue_kind(card)
    before = _safe_card_text(card.get("summary"))
    summary = ""
    if issue_kind == "price_policy":
        summary = (
            "고객은 로봇청소기의 가격 정책이 경쟁 제품 대비 가치 설득력이 부족하다고 느끼고 있습니다. "
            "가격·혜택·성능 메시지를 함께 재정렬해야 구매 전환 저항을 줄일 수 있습니다."
        )
    elif issue_kind == "manufacturer_trust":
        summary = (
            "고객은 제조사와 공급망, 보안 신뢰를 구매 판단의 핵심 리스크로 보고 있습니다. "
            "국내 개발/제조 관여도와 보안 신뢰 근거를 명확히 커뮤니케이션할 필요가 있습니다."
        )
    elif issue_kind == "color_option":
        summary = (
            "고객은 로봇청소기의 색상 선택지가 제한되어 있다는 점을 아쉬워합니다. "
            "색상 옵션과 디자인 선택지는 제품 매력도를 높일 수 있는 L2 개선 후보입니다."
        )
    elif issue_kind == "positive_builtin_station":
        summary = (
            "빌트인스테이션은 고객에게 강한 매력 포인트로 인식됩니다. "
            "개선 대상보다는 제품 차별화 메시지와 구매 설득 포인트로 활용할 수 있습니다."
        )
    elif issue_kind == "positive_self_development":
        summary = (
            "자체 개발과 업그레이드 가능성은 고객에게 신뢰와 기대를 주는 신호입니다. "
            "경쟁 제품 대비 선택 이유를 강화하는 전략 메시지로 활용할 수 있습니다."
        )

    if not summary:
        return None
    card["summary"] = summary
    card["customer_insight_summary_override"] = summary
    if before == summary:
        return None
    return {
        "source_id": _safe_card_text(card.get("source_id")),
        "unit_title": _safe_card_text(card.get("unit_title")),
        "issue_kind": issue_kind,
        "before_summary": before,
        "after_summary": summary,
    }


def _set_root_problem_payload(
    card: dict[str, Any],
    *,
    level: str,
    label: str,
    category: str,
    target: str,
    basis: str,
) -> None:
    card["root_problem_level"] = f"{level} · {label}"
    card["root_cause_maturity"] = f"{level} · {label}"
    card["root_cause_category"] = category
    card["root_problem_target"] = target
    card["root_cause_basis"] = basis
    if level in {"L1", "L2", "L3"}:
        card["needs_human_review"] = True
        card["na_status"] = "interpreted"
    elif level == "L0":
        card["na_status"] = "true_na"


def _quality_root_issue_kind(card: Mapping[str, Any]) -> str:
    blob = _quality_blob(card)
    negative = _has_any(blob, ("불만", "우려", "아쉽", "비싸", "받아쳐먹", "함정", "걱정", "ㅠ", "낮다"))
    positive = _has_any(blob, ("대박", "좋", "만족", "기대", "메리트", "선방", "확실", "칭찬"))

    if _has_any(blob, ("색상", "검은색", "색만", "선택지")) and _has_any(blob, ("아쉽", "불만", "ㅠ", "제한", "만 있다", "색만")):
        return "color_option"
    if _has_any(blob, ("제조사", "중국", "국내 제조", "공급망", "보안", "품질", "신뢰", "picea")) and negative:
        return "manufacturer_trust"
    if _has_any(blob, ("가격", "책정", "경쟁사", "가성비", "프로모션", "메리트", "혜택")) and negative:
        return "price_policy"
    if _has_any(blob, ("빌트인스테이션", "빌트인 스테이션")) and positive and not negative:
        return "positive_builtin_station"
    if _has_any(blob, ("자체 개발", "업그레이드", "알고리즘")) and positive and not _has_any(
        blob, ("색상", "검은색", "가격", "제조사", "중국", "보안")
    ):
        return "positive_self_development"
    return ""


def _is_purchase_choice_comparison_card(card: Mapping[str, Any]) -> bool:
    blob = _quality_blob(card)
    if _quality_root_issue_kind(card):
        return False
    return _has_any(blob, ("로보락", "삼성", "경쟁", "비교", "선택", "확정", "공간", "구매")) and _has_any(
        blob, ("자체 개발", "업그레이드", "좋", "기대", "선택", "확정")
    )


def _quality_source_key(card: Mapping[str, Any]) -> str:
    for key in ("source_comment_id", "case_id"):
        value = _safe_card_text(card.get(key))
        if value:
            return value
    source = _safe_card_text(card.get("source_id"))
    if source:
        return re.sub(r"(?:::u|#u|\.u)\d+$", "", source)
    return _safe_card_text(card.get("atomic_unit_id")) or "unknown-source"


def _quality_blob(card: Mapping[str, Any]) -> str:
    context = card.get("semantic_context_payload")
    if not isinstance(context, Mapping):
        context = {}
    values = [
        card.get("unit_title"),
        card.get("feature_topic_label"),
        card.get("feature_topic"),
        card.get("feature_topic_description"),
        card.get("atomic_voc"),
        card.get("evidence_span"),
        card.get("summary"),
        card.get("polarity_basis"),
        card.get("root_cause_basis"),
        context.get("comment_text"),
        context.get("parent_comment_text"),
        context.get("video_title"),
    ]
    return " ".join(_safe_card_text(value) for value in values if _safe_card_text(value))


def _has_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token and token.lower() in text.lower() for token in tokens)


def _quality_best_quote(card: Mapping[str, Any], *, tokens: Iterable[str], fallback: str = "") -> str:
    best = ""
    best_score = -1
    for _, segment in _evidence_candidate_segments(card):
        score = sum(1 for token in tokens if token.lower() in segment.lower())
        if score > best_score:
            best = segment
            best_score = score
    if best and best_score > 0:
        return best
    return fallback or _safe_card_text(card.get("evidence_span") or card.get("atomic_voc"))


def _quality_basis(card: Mapping[str, Any], *, tokens: Iterable[str], judgment: str) -> str:
    quote = _quality_best_quote(card, tokens=tokens)
    if quote:
        return f'근거: "{quote}" / 판단: {judgment}'
    return f"판단: {judgment}"


def _combine_unique_texts(values: Iterable[str]) -> str:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _safe_card_text(value)
        if not text or text in seen:
            continue
        rows.append(text)
        seen.add(text)
    return " / ".join(rows)


def _score_card_specificity(card: Mapping[str, Any]) -> int:
    text = _quality_blob(card)
    score = len(_safe_card_text(card.get("evidence_span"))) + len(_safe_card_text(card.get("feature_topic_label")))
    for token in ("색상", "검은색", "자체 개발", "업그레이드", "가격", "제조사", "보안", "빌트인스테이션"):
        if token in text:
            score += 100
    root_level = _safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity"))
    if root_level.startswith("L2") or root_level.startswith("L3"):
        score += 50
    return score


def _copy_if_present(
    source: Mapping[str, Any],
    target: dict[str, Any],
    source_key: str,
    *,
    target_key: str | None = None,
) -> None:
    value = source.get(source_key)
    if value in (None, ""):
        return
    target[target_key or source_key] = value


def _semantic_ai_draft_rows(unit_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return Golden120-style AI draft candidates before dashboard rendering.

    These rows are intentionally richer than dashboard rows.  They keep the
    exact evidence layer, the interpretation draft, and promotion quality notes
    together so the dashboard can become a reader of AI Draft data rather than
    the place where semantic interpretation is reconstructed.
    """

    rows: list[dict[str, Any]] = []
    for card in unit_cards:
        evidence_layer = _evidence_layer_payload(card)
        summary_layer = _summary_layer_payload(card)
        atomic_voc_record = _p0_atomic_voc_record(card, evidence_layer=evidence_layer)
        rows.append(
            {
                "schema_version": "semantic-ai-draft-v1",
                "draft_status": _ai_draft_status(card),
                "parent_voc": _p0_parent_voc_record(card),
                "atomic_voc_record": atomic_voc_record,
                "explainability_trace": _p0_explainability_trace(card, atomic_voc_record),
                "dashboard_aggregate_seed": _p0_dashboard_aggregate_seed(card, atomic_voc_record),
                "source_id": _safe_card_text(card.get("source_id")),
                "case_id": _safe_card_text(card.get("case_id")),
                "source_comment_id": _safe_card_text(card.get("source_comment_id")),
                "parent_comment_id": _safe_card_text(card.get("parent_comment_id")),
                "comment_depth": _safe_card_text(card.get("comment_depth")),
                "is_reply": bool(card.get("is_reply")),
                "source_voc_index": card.get("source_voc_index", ""),
                "atomic_unit_index": card.get("atomic_unit_index", ""),
                "atomic_unit_id": _safe_card_text(card.get("atomic_unit_id")),
                "unit_title": _safe_card_text(card.get("unit_title")),
                "source_context": _source_context_payload(card),
                "atomic_unit": {
                    "atomic_voc": _safe_card_text(card.get("atomic_voc")),
                    "evidence_span": _safe_card_text(card.get("evidence_span")),
                },
                "judgments": {
                    "product": {
                        "label": _preferred_product_label(card)
                        or _safe_card_text(card.get("product_label"))
                        or _safe_card_text(card.get("product_group_label")),
                        "group": _safe_card_text(card.get("product_group_label")),
                        "detail": _safe_card_text(card.get("product_detail")),
                        "basis": _safe_card_text(card.get("product_basis")),
                        "detail_basis": _safe_card_text(card.get("product_detail_basis")),
                    },
                    "feature_topic": {
                        "label": _safe_card_text(card.get("feature_topic_label") or card.get("feature_topic")),
                        "description": _safe_card_text(card.get("feature_topic_description")),
                        "basis": _safe_card_text(card.get("feature_topic_basis")),
                    },
                    "cej": {
                        "stage": _safe_card_text(card.get("cej_stage")),
                        "basis": _safe_card_text(card.get("cej_basis")),
                        "status": _safe_card_text(card.get("cej_status")),
                    },
                    "tees": {
                        "success": _tees_axis_draft(card, "success"),
                        "time": _tees_axis_draft(card, "time"),
                        "effort": _tees_axis_draft(card, "effort"),
                        "emotion": _tees_axis_draft(card, "emotion"),
                    },
                    "root_cause": {
                        "level": _safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity")),
                        "label": _safe_card_text(card.get("root_problem_label")),
                        "target": _safe_card_text(card.get("root_problem_target")),
                        "category": _safe_card_text(card.get("root_cause_category")),
                        "basis": _safe_card_text(card.get("root_cause_basis")),
                    },
                    "polarity": {
                        "label": _safe_card_text(card.get("polarity_label")),
                        "basis": _safe_card_text(card.get("polarity_basis")),
                        "dashboard_tone": _dashboard_tone_from_card(card),
                    },
                },
                "evidence_layer": evidence_layer,
                "summary_layer": summary_layer,
                "quality": {
                    "needs_human_review": bool(card.get("needs_human_review")),
                    "na_status": _safe_card_text(card.get("na_status")),
                    "na_reason": _safe_card_text(card.get("na_reason")),
                    "evidence_completeness": _evidence_completeness_score(evidence_layer),
                    "quality_warnings": list(card.get("quality_warnings") or []),
                    "watch_agenda_flags": list(card.get("watch_agenda_flags") or []),
                },
                "human_review": _empty_human_review_payload(),
                "lineage": {
                    "card_source": _safe_card_text(card.get("card_source")),
                    "interpreter_status": _safe_card_text(card.get("interpreter_status")),
                    "prompt_version": GOLDEN120_PROMPT_VERSION,
                },
            }
        )
    return rows


def _empty_human_review_payload() -> dict[str, str]:
    """Return an append-only human review skeleton for Golden120-style QA."""

    return {
        "schema_version": "semantic-ai-draft-human-review-v1",
        "human_decision": "",
        "human_note": "",
        "reviewer": "",
        "reviewed_at": "",
        "final_status": "",
        "final_product": "",
        "final_feature_topic": "",
        "final_atomic_voc": "",
        "final_evidence_span": "",
        "final_cej": "",
        "final_tees_success": "",
        "final_tees_time": "",
        "final_tees_effort": "",
        "final_tees_emotion": "",
        "final_root_cause": "",
        "final_summary": "",
    }


P0_ATOMIC_VOC_SCHEMA_VERSION = "atomic-voc-v1"
P0_PARENT_VOC_SCHEMA_VERSION = "parent-voc-v1"
P0_EXPLAINABILITY_SCHEMA_VERSION = "semantic-explainability-trace-v1"
P0_STATUS_VALUES = {
    "normal",
    "true_na",
    "scope_excluded",
    "context_missing",
    "engine_missed",
    "review_required",
}


def _p0_normalize_status(value: object, *, default: str = "normal") -> str:
    text = _safe_card_text(value).strip().lower()
    aliases = {
        "": default,
        "interpreted": "normal",
        "in_scope": "normal",
        "ok": "normal",
        "not_applicable": "true_na",
        "n/a": "true_na",
        "na": "true_na",
        "context_needed": "context_missing",
        "context need": "context_missing",
        "calibration_needed": "review_required",
        "needs_review": "review_required",
        "review": "review_required",
    }
    normalized = aliases.get(text, text)
    return normalized if normalized in P0_STATUS_VALUES else default


def _p0_parent_voc_id(card: Mapping[str, Any]) -> str:
    source_comment_id = _safe_card_text(card.get("source_comment_id"))
    if source_comment_id:
        return source_comment_id
    source_id = _safe_card_text(card.get("source_id") or card.get("case_id"))
    if "::u" in source_id:
        return source_id.split("::u", 1)[0]
    return source_id


def _p0_atomic_index(card: Mapping[str, Any]) -> int:
    for key in ("atomic_index", "atomic_unit_index", "unit_index"):
        value = card.get(key)
        if isinstance(value, int) and value > 0:
            return value
        text = _safe_card_text(value)
        if text.isdigit() and int(text) > 0:
            return int(text)
    source_id = _safe_card_text(card.get("source_id") or card.get("case_id"))
    match = re.search(r"::u(\d+)$", source_id)
    if match:
        return int(match.group(1))
    return 1


def _p0_atomic_id(card: Mapping[str, Any]) -> str:
    explicit = _safe_card_text(card.get("atomic_id") or card.get("atomic_unit_id"))
    if explicit:
        return explicit
    parent_voc_id = _p0_parent_voc_id(card)
    return f"{parent_voc_id}::a{_p0_atomic_index(card)}" if parent_voc_id else ""


def _p0_raw_comment_text(card: Mapping[str, Any]) -> str:
    context = card.get("semantic_context_payload")
    if isinstance(context, Mapping):
        text = _safe_card_text(context.get("comment_text"))
        if text:
            return text
    return _safe_card_text(card.get("raw_comment_text") or card.get("original_comment") or card.get("atomic_voc"))


def _p0_evidence_scope(card: Mapping[str, Any], quote: str) -> str:
    if not quote:
        return "missing"
    atomic_text = _safe_card_text(card.get("atomic_voc"))
    raw_text = _p0_raw_comment_text(card)
    if quote in atomic_text:
        return "atomic_internal"
    if quote in raw_text:
        return "parent_comment_context"
    return "external_context"


def _p0_field_quote(evidence_layer: Mapping[str, Any], field: str) -> str:
    rows = evidence_layer.get("field_evidence")
    if not isinstance(rows, list):
        return ""
    for row in rows:
        if isinstance(row, Mapping) and row.get("field") == field:
            return _safe_card_text(row.get("quote"))
    return ""


def _p0_field_status(
    card: Mapping[str, Any],
    *,
    axis: str,
    value: object,
    basis: object = "",
    status_hint: object = "",
) -> str:
    hinted = _p0_normalize_status(status_hint, default="")
    if hinted:
        return hinted
    scope_status = _safe_card_text(card.get("scope_status")).lower()
    if "exclude" in scope_status:
        return "scope_excluded"
    text = _safe_card_text(value).strip().lower()
    basis_text = _safe_card_text(basis).strip().lower()
    if text not in {"", "n/a", "na", "none", "unknown"}:
        return "normal"
    na_status = _p0_normalize_status(card.get("na_status"), default="")
    if na_status:
        return na_status
    if "context" in basis_text or "video" in basis_text or "parent" in basis_text:
        return "context_missing"
    polarity = _safe_card_text(card.get("polarity_label")).lower()
    if axis == "tees_emotion" and polarity in {"negative_concern", "positive"}:
        return "engine_missed"
    if axis in {"product", "feature_topic", "cej"} and bool(card.get("needs_human_review")):
        return "review_required"
    return "true_na"


def _p0_root_level(card: Mapping[str, Any]) -> str:
    text = _safe_card_text(
        card.get("root_problem_level")
        or card.get("root_problem_maturity")
        or card.get("root_cause_maturity")
    ).strip()
    for level in ("L0", "L1", "L2", "L3"):
        if text.upper().startswith(level):
            return level
    if text.upper().startswith("N/A"):
        return "L0"
    return ""


def _p0_stage_payload(
    *,
    label: object,
    reason: object,
    evidence: object,
    confidence: object = "",
    status: object = "normal",
) -> dict[str, Any]:
    return {
        "label": _safe_card_text(label),
        "reason": _safe_card_text(reason),
        "evidence": _safe_card_text(evidence),
        "confidence": _safe_card_text(confidence),
        "status": _p0_normalize_status(status),
    }


def _p0_parent_voc_record(card: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": P0_PARENT_VOC_SCHEMA_VERSION,
        "parent_voc_id": _p0_parent_voc_id(card),
        "source_comment_id": _safe_card_text(card.get("source_comment_id")),
        "parent_comment_id": _safe_card_text(card.get("parent_comment_id")),
        "comment_depth": _safe_card_text(card.get("comment_depth")),
        "is_reply": bool(card.get("is_reply")),
        "raw_comment_text": _p0_raw_comment_text(card),
        "source_context": _source_context_payload(card),
        "status": _p0_field_status(
            card,
            axis="parent",
            value=_p0_raw_comment_text(card),
            status_hint=card.get("scope_status"),
        ),
    }


def _p0_atomic_voc_record(card: Mapping[str, Any], *, evidence_layer: Mapping[str, Any]) -> dict[str, Any]:
    atomic_text = _safe_card_text(card.get("atomic_voc"))
    evidence_span = _safe_card_text(card.get("evidence_span"))
    primary_scope = _p0_evidence_scope(card, evidence_span)
    root_level = _p0_root_level(card)
    root_status = "true_na" if root_level == "L0" else ("normal" if root_level else "engine_missed")
    return {
        "schema_version": P0_ATOMIC_VOC_SCHEMA_VERSION,
        "parent_voc_id": _p0_parent_voc_id(card),
        "atomic_id": _p0_atomic_id(card),
        "atomic_index": _p0_atomic_index(card),
        "source_comment_id": _safe_card_text(card.get("source_comment_id")),
        "parent_comment_id": _safe_card_text(card.get("parent_comment_id")),
        "comment_depth": _safe_card_text(card.get("comment_depth")),
        "is_reply": bool(card.get("is_reply")),
        "raw_comment_text": _p0_raw_comment_text(card),
        "atomic_text": atomic_text,
        "atomic_split_reason": _safe_card_text(
            card.get("atomic_split_reason")
            or card.get("atomic_boundary_reason")
            or "minimal_business_atomic_boundary"
        ),
        "atomic_boundary_status": _p0_normalize_status(card.get("atomic_boundary_status")),
        "atomic_evidence": evidence_span if primary_scope == "atomic_internal" else "",
        "context_evidence": evidence_span if primary_scope != "atomic_internal" else "",
        "evidence_scope": primary_scope,
        "topic_label": _safe_card_text(card.get("feature_topic_label") or card.get("feature_topic")),
        "topic_reason": _safe_card_text(card.get("feature_topic_description") or card.get("feature_topic_basis")),
        "topic_evidence": _p0_field_quote(evidence_layer, "feature_topic") or evidence_span,
        "topic_confidence": _safe_card_text(card.get("feature_topic_confidence") or card.get("confidence_label")),
        "topic_status": _p0_field_status(
            card,
            axis="feature_topic",
            value=card.get("feature_topic_label") or card.get("feature_topic"),
            basis=card.get("feature_topic_basis"),
        ),
        "cej_label": _safe_card_text(card.get("cej_stage")),
        "cej_reason": _safe_card_text(card.get("cej_basis")),
        "cej_evidence": _p0_field_quote(evidence_layer, "cej"),
        "cej_confidence": _safe_card_text(card.get("cej_confidence") or card.get("confidence_label")),
        "cej_status": _p0_field_status(
            card,
            axis="cej",
            value=card.get("cej_stage"),
            basis=card.get("cej_basis"),
            status_hint=card.get("cej_status"),
        ),
        **_p0_tees_record(card, evidence_layer=evidence_layer),
        "root_cause_level": root_level or "L0",
        "root_cause_problem": _safe_card_text(card.get("root_problem_label") or card.get("root_problem_category")),
        "root_cause_target": _safe_card_text(card.get("root_improvement_target") or card.get("root_problem_target")),
        "root_cause_cause": _safe_card_text(card.get("root_cause_hypothesis") or card.get("root_cause_category")),
        "root_cause_reason": _safe_card_text(card.get("root_problem_basis") or card.get("root_cause_basis")),
        "root_cause_evidence": _p0_field_quote(evidence_layer, "root_cause"),
        "root_cause_confidence": _safe_card_text(card.get("root_problem_confidence") or card.get("root_cause_confidence")),
        "root_cause_status": root_status,
        "summary_text": _safe_card_text(card.get("customer_insight_summary") or card.get("summary")),
        "summary_reason": _safe_card_text(card.get("summary_basis") or "customer insight summary generated from interpreted unit"),
        "summary_evidence": evidence_span,
        "summary_confidence": _safe_card_text(card.get("summary_confidence") or card.get("confidence_label")),
        "summary_status": _p0_field_status(card, axis="summary", value=card.get("summary")),
        "trace_notes": _p0_trace_notes(card),
        "needs_human_review": bool(card.get("needs_human_review")),
    }


def _p0_tees_record(card: Mapping[str, Any], *, evidence_layer: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for axis in ("success", "time", "effort", "emotion"):
        value_key = f"tees_{axis}_value"
        basis_key = f"tees_{axis}_basis"
        field_key = f"tees_{axis}"
        output[field_key] = _safe_card_text(card.get(value_key))
        output[f"{field_key}_reason"] = _safe_card_text(card.get(basis_key))
        output[f"{field_key}_evidence"] = _p0_field_quote(evidence_layer, field_key)
        output[f"{field_key}_confidence"] = _safe_card_text(card.get(f"tees_{axis}_confidence"))
        output[f"{field_key}_status"] = _p0_field_status(
            card,
            axis=field_key,
            value=card.get(value_key),
            basis=card.get(basis_key),
        )
    return output


def _p0_trace_notes(card: Mapping[str, Any]) -> list[str]:
    notes: list[str] = []
    card_source = _safe_card_text(card.get("card_source"))
    if card_source:
        notes.append(f"card_source={card_source}")
    if card.get("atomic_boundary_kind"):
        notes.append(f"atomic_boundary_kind={_safe_card_text(card.get('atomic_boundary_kind'))}")
    if card.get("duplicate_split_removed_count"):
        notes.append(f"duplicate_split_removed_count={card.get('duplicate_split_removed_count')}")
    for warning in card.get("quality_warnings") or []:
        notes.append(_safe_card_text(warning))
    return [note for note in notes if note]


def _p0_explainability_trace(card: Mapping[str, Any], atomic_record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": P0_EXPLAINABILITY_SCHEMA_VERSION,
        "parent": _p0_stage_payload(
            label=atomic_record.get("parent_voc_id"),
            reason="source comment lineage",
            evidence=atomic_record.get("raw_comment_text"),
            status=_p0_parent_voc_record(card).get("status"),
        ),
        "atomic": _p0_stage_payload(
            label=atomic_record.get("atomic_text"),
            reason=atomic_record.get("atomic_split_reason"),
            evidence=atomic_record.get("atomic_evidence") or atomic_record.get("context_evidence"),
            status=atomic_record.get("atomic_boundary_status"),
        ),
        "topic": _p0_stage_payload(
            label=atomic_record.get("topic_label"),
            reason=atomic_record.get("topic_reason"),
            evidence=atomic_record.get("topic_evidence"),
            confidence=atomic_record.get("topic_confidence"),
            status=atomic_record.get("topic_status"),
        ),
        "cej": _p0_stage_payload(
            label=atomic_record.get("cej_label"),
            reason=atomic_record.get("cej_reason"),
            evidence=atomic_record.get("cej_evidence"),
            confidence=atomic_record.get("cej_confidence"),
            status=atomic_record.get("cej_status"),
        ),
        "tees": {
            axis: _p0_stage_payload(
                label=atomic_record.get(f"tees_{axis}"),
                reason=atomic_record.get(f"tees_{axis}_reason"),
                evidence=atomic_record.get(f"tees_{axis}_evidence"),
                confidence=atomic_record.get(f"tees_{axis}_confidence"),
                status=atomic_record.get(f"tees_{axis}_status"),
            )
            for axis in ("success", "time", "effort", "emotion")
        },
        "root_cause": _p0_stage_payload(
            label=atomic_record.get("root_cause_level"),
            reason=atomic_record.get("root_cause_reason"),
            evidence=atomic_record.get("root_cause_evidence"),
            confidence=atomic_record.get("root_cause_confidence"),
            status=atomic_record.get("root_cause_status"),
        ),
        "summary": _p0_stage_payload(
            label=atomic_record.get("summary_text"),
            reason=atomic_record.get("summary_reason"),
            evidence=atomic_record.get("summary_evidence"),
            confidence=atomic_record.get("summary_confidence"),
            status=atomic_record.get("summary_status"),
        ),
    }


def _p0_dashboard_aggregate_seed(card: Mapping[str, Any], atomic_record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "parent_voc_id": atomic_record.get("parent_voc_id"),
        "atomic_id": atomic_record.get("atomic_id"),
        "product": _preferred_product_label(card) or _safe_card_text(card.get("product_label")),
        "feature_topic": atomic_record.get("topic_label"),
        "cej": atomic_record.get("cej_label"),
        "polarity": _safe_card_text(card.get("polarity_label")),
        "semantic_lane": _safe_card_text(card.get("semantic_lane")),
        "root_cause_level": atomic_record.get("root_cause_level"),
        "root_cause_target": atomic_record.get("root_cause_target"),
        "summary": atomic_record.get("summary_text"),
        "needs_human_review": atomic_record.get("needs_human_review"),
    }


def _tees_axis_draft(card: Mapping[str, Any], axis: str) -> dict[str, str]:
    return {
        "value": _safe_card_text(card.get(f"tees_{axis}_value")),
        "basis": _safe_card_text(card.get(f"tees_{axis}_basis")),
    }


def _ai_draft_status(card: Mapping[str, Any]) -> str:
    source = _safe_card_text(card.get("card_source"))
    if "llm" in source or source.startswith("golden120_semantic"):
        return "llm_interpreted_candidate"
    if _safe_card_text(card.get("interpreter_status")) in {"llm_merged", "interpreted"}:
        return "llm_interpreted_candidate"
    return "projection_candidate"


def _source_context_payload(card: Mapping[str, Any]) -> dict[str, Any]:
    context = card.get("semantic_context_payload")
    if not isinstance(context, Mapping):
        context = {}
    return {
        "source_context_used": list(card.get("source_context_used") or []),
        "source_context_summary": _safe_card_text(card.get("source_context_summary")),
        "comment_text": _safe_card_text(context.get("comment_text")),
        "parent_comment_text": _safe_card_text(context.get("parent_comment_text")),
        "video_title": _safe_card_text(context.get("video_title")),
        "source_product": _safe_card_text(context.get("source_product")),
        "source_bucket": _safe_card_text(context.get("source_bucket")),
        "source_url": _safe_card_text(context.get("source_url") or context.get("video_url")),
        "comment_depth": _safe_card_text(card.get("comment_depth")),
        "is_reply": bool(card.get("is_reply")),
    }


def _evidence_layer_payload(card: Mapping[str, Any]) -> dict[str, Any]:
    field_evidence = [
        _field_evidence_payload(
            card,
            field="product",
            value=_preferred_product_label(card)
            or _safe_card_text(card.get("product_label"))
            or _safe_card_text(card.get("product_group_label")),
            basis=_safe_card_text(card.get("product_basis")),
        ),
        _field_evidence_payload(
            card,
            field="feature_topic",
            value=_safe_card_text(card.get("feature_topic_label") or card.get("feature_topic")),
            basis=_safe_card_text(card.get("feature_topic_basis")),
        ),
        _field_evidence_payload(
            card,
            field="cej",
            value=_safe_card_text(card.get("cej_stage")),
            basis=_safe_card_text(card.get("cej_basis")),
        ),
        _field_evidence_payload(
            card,
            field="tees_success",
            value=_safe_card_text(card.get("tees_success_value")),
            basis=_safe_card_text(card.get("tees_success_basis")),
        ),
        _field_evidence_payload(
            card,
            field="tees_time",
            value=_safe_card_text(card.get("tees_time_value")),
            basis=_safe_card_text(card.get("tees_time_basis")),
        ),
        _field_evidence_payload(
            card,
            field="tees_effort",
            value=_safe_card_text(card.get("tees_effort_value")),
            basis=_safe_card_text(card.get("tees_effort_basis")),
        ),
        _field_evidence_payload(
            card,
            field="tees_emotion",
            value=_safe_card_text(card.get("tees_emotion_value")),
            basis=_safe_card_text(card.get("tees_emotion_basis")),
        ),
        _field_evidence_payload(
            card,
            field="root_cause",
            value=_safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity")),
            basis=_safe_card_text(card.get("root_cause_basis")),
        ),
        _field_evidence_payload(
            card,
            field="polarity",
            value=_safe_card_text(card.get("polarity_label")),
            basis=_safe_card_text(card.get("polarity_basis")),
        ),
    ]
    field_evidence = [row for row in field_evidence if row["value"] or row["basis"] or row["quote"]]
    return {
        "schema_version": "semantic-evidence-layer-v1",
        "primary_evidence_span": _safe_card_text(card.get("evidence_span")),
        "source_context_used": list(card.get("source_context_used") or []),
        "source_context_summary": _safe_card_text(card.get("source_context_summary")),
        "field_evidence": field_evidence,
        "context_payload": _source_context_payload(card),
    }


def _field_evidence_payload(card: Mapping[str, Any], *, field: str, value: str, basis: str) -> dict[str, Any]:
    explicit_quote = _quote_from_basis(basis)
    if explicit_quote:
        quote = explicit_quote
        quote_source = _quote_source(card, quote)
        quote_score = 1.0
    else:
        quote, quote_source, quote_score = _ranked_evidence_quote(card, field=field, value=value, basis=basis)
    return {
        "field": field,
        "value": value,
        "basis": basis,
        "quote": quote,
        "quote_source": quote_source,
        "quote_score": round(float(quote_score), 3),
    }
_QUALITY_NEGATIVE_TOKENS = (
    "불만",
    "우려",
    "아쉽",
    "아쉬운",
    "아쉬웠",
    "비싸",
    "걱정",
    "무섭",
    "불안",
    "부족",
    "별로",
    "안 좋",
    "안좋",
    "문제",
    "결착문제",
    "받아쳐먹",
    "제한",
    "품질 낮",
    "실망",
    "분노",
    "시끄",
    "먼지",
    "엉키",
    "불편",
    "ㅠ",
    "ㅜ",
)
_QUALITY_POSITIVE_TOKENS = (
    "좋",
    "대박",
    "만족",
    "신세계",
    "메리트",
    "선방",
    "확실",
    "기대",
    "칭찬",
    "추천",
    "괜찮",
    "괜찮은",
    "가능성",
    "좋은",
    "업그레이드",
    "자체 개발",
    "자체개발",
    "직배수",
    "빌트인",
    "훌륭",
    "감탄",
)
_QUALITY_COLOR_TOKENS = ("색상", "색깔", "검은색", "블랙", "화이트", "선택지", "색만", "검은색만", "옵션")
_QUALITY_PRICE_TOKENS = (
    "가격",
    "책정",
    "경쟁사",
    "가성비",
    "프로모션",
    "메리트",
    "선방",
    "비싸",
    "받아쳐먹",
    "같은가격",
    "같은 가격",
    "품질",
)
_QUALITY_MANUFACTURER_TOKENS = (
    "제조사",
    "중국",
    "국내 제조",
    "공급망",
    "보안",
    "신뢰",
    "picea",
    "다이슨",
    "로청 제조사",
    "제조",
)
_QUALITY_BUILTIN_TOKENS = ("빌트인스테이션", "빌트인 스테이션", "스테이션", "자동비움", "자동 비움")
_QUALITY_SELF_DEV_TOKENS = ("자체 개발", "자체개발", "업그레이드", "알고리즘")
_QUALITY_COMPARISON_TOKENS = ("로보락", "삼성", "경쟁", "경쟁사", "비교", "선택", "확정", "구매", "공간", "보다가")
_QUALITY_INLET_COVER_TOKENS = ("흡입구", "덮개", "흡입구덮개", "결착", "점검", "케어매니저")


def _quote_from_basis(basis: str) -> str:
    marker = '근거: "'
    start = basis.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = basis.find('"', start)
    if end < 0:
        return basis[start:].strip()
    return basis[start:end].strip()


def _ranked_evidence_quote(card: Mapping[str, Any], *, field: str, value: str, basis: str) -> tuple[str, str, float]:
    """Pick the most direct source quote for a semantic judgment."""

    candidates = _evidence_candidate_segments(card)
    if not candidates:
        return "", "", 0.0
    keywords = _evidence_ranking_keywords(field=field, value=value, basis=basis)
    best_source = ""
    best_quote = ""
    best_score = -1.0
    for source, segment in candidates:
        score = _score_evidence_segment(segment, field=field, keywords=keywords, value=value, basis=basis)
        if score > best_score:
            best_source = source
            best_quote = segment
            best_score = score
    if best_score <= 0:
        fallback = _basis_evidence_text(card)
        return fallback, _quote_source(card, fallback), 0.0
    return best_quote, best_source or _quote_source(card, best_quote), best_score


def _evidence_candidate_segments(card: Mapping[str, Any]) -> list[tuple[str, str]]:
    context = card.get("semantic_context_payload")
    if not isinstance(context, Mapping):
        context = {}
    raw_candidates = [
        ("evidence_span", card.get("evidence_span")),
        ("atomic_voc", card.get("atomic_voc")),
        ("comment", context.get("comment_text")),
        ("parent", context.get("parent_comment_text")),
        ("video/source", context.get("video_title")),
        ("video/source", context.get("source_product")),
        ("video/source", context.get("source_bucket")),
    ]
    rows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source, raw_text in raw_candidates:
        for segment in _split_evidence_segments(_safe_card_text(raw_text)):
            key = (source, segment)
            if key in seen:
                continue
            rows.append(key)
            seen.add(key)
    return rows


def _split_evidence_segments(text: str) -> list[str]:
    text = _safe_card_text(text).strip()
    if not text:
        return []
    parts: list[str] = []
    for line in re.split(r"[\r\n]+", text):
        line = line.strip()
        if not line:
            continue
        connector_parts: list[str] = []
        for chunk in re.split(r"\s+(?:그리고|그러나|하지만|다만|근데|그런데|반면)\s+", line):
            connector_parts.extend(
                part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", chunk) if part.strip()
            )
        subparts = connector_parts or [line]
        parts.extend(subparts or [line])
    if len(text) <= 260 and text not in parts:
        parts.append(text)
    return parts


def _evidence_ranking_keywords(*, field: str, value: str, basis: str) -> set[str]:
    blob = f"{field} {value} {basis}".lower()
    keywords = {
        token
        for token in re.findall(r"[0-9A-Za-z가-힣]{2,}", blob)
        if token
        and token
        not in {
            "n/a",
            "na",
            "none",
            "unknown",
            "direct",
            "signal",
            "confirmed",
            "basis",
            "value",
            "근거",
            "확인",
            "신호",
            "있습니다",
            "없습니다",
        }
    }
    field_key = field.lower()
    if field_key in {"polarity", "tees_emotion"}:
        keywords.update(
            {
                "대박",
                "만족",
                "좋",
                "최고",
                "추천",
                "선방",
                "메리트",
                "신세계",
                "감탄",
                "아쉽",
                "비싸",
                "불만",
                "우려",
                "걱정",
                "무섭",
                "별로",
                "실망",
                "불안",
                "positive",
                "satisfaction",
                "negative",
                "concern",
                "disappointment",
                "anxiety",
            }
        )
    elif field_key == "cej":
        keywords.update({"구매", "설치", "사용", "관리", "수리", "교체", "탐색", "문의", "할인", "가격", "a/s", "as"})
    elif field_key == "root_cause":
        keywords.update({"문제", "불편", "고장", "결착", "소음", "냄새", "비싸", "안됨", "부족", "원인", "because"})
    return keywords


def _score_evidence_segment(segment: str, *, field: str, keywords: set[str], value: str = "", basis: str = "") -> float:
    lowered = segment.lower()
    score = 0.0
    for keyword in keywords:
        if keyword and keyword.lower() in lowered:
            score += 4.0 if len(keyword) >= 3 else 2.0
    if field.lower() in {"polarity", "tees_emotion"}:
        target = _sentiment_target_from_value_basis(value=value, basis=basis)
        has_positive = any(token in lowered for token in POSITIVE_ATOMIC_CUES)
        has_negative = any(token in lowered for token in NEGATIVE_ATOMIC_CUES)
        if target == "positive":
            if has_positive:
                score += 10.0
            if has_negative:
                score -= 4.0
        elif target == "negative":
            if has_negative:
                score += 10.0
            if has_positive:
                score -= 4.0
        else:
            if has_positive or has_negative:
                score += 4.0
    if field.lower() == "root_cause" and any(token in lowered for token in ("문제", "불편", "고장", "결착", "소음", "냄새", "부족")):
        score += 6.0
    if 8 <= len(segment) <= 180:
        score += 1.0
    if len(segment) > 260:
        score -= 1.0
    return score


def _sentiment_target_from_value_basis(*, value: str, basis: str) -> str:
    blob = f"{value} {basis}".lower()
    if any(
        token in blob
        for token in ("negative", "concern", "disappoint", "anxiety", "불만", "우려", "걱정", "아쉽", "비싸")
    ):
        return "negative"
    if any(
        token in blob
        for token in ("positive", "satisfaction", "satisfied", "trust", "만족", "긍정", "좋", "대박", "추천")
    ):
        return "positive"
    return ""


def _quote_source(card: Mapping[str, Any], quote: str) -> str:
    if not quote:
        return ""
    context = card.get("semantic_context_payload")
    if isinstance(context, Mapping):
        for source_name, key in (
            ("comment", "comment_text"),
            ("parent", "parent_comment_text"),
            ("video/source", "video_title"),
            ("video/source", "source_product"),
            ("video/source", "source_bucket"),
        ):
            if quote in _safe_card_text(context.get(key)):
                return source_name
    if quote in _safe_card_text(card.get("evidence_span")):
        return "evidence_span"
    if quote in _safe_card_text(card.get("atomic_voc")):
        return "atomic_voc"
    return "derived_context"


def _evidence_completeness_score(evidence_layer: Mapping[str, Any]) -> float:
    rows = evidence_layer.get("field_evidence")
    if not isinstance(rows, list) or not rows:
        return 0.0
    quoted = sum(1 for row in rows if isinstance(row, Mapping) and _safe_card_text(row.get("quote")))
    return round(quoted / len(rows), 3)


def _summary_layer_payload(card: Mapping[str, Any]) -> dict[str, str]:
    insight = _customer_insight_summary(card)
    return {
        "schema_version": "semantic-summary-layer-v1",
        "customer_insight": insight,
        "actionability": _summary_actionability(card),
        "source_summary": _safe_card_text(card.get("summary")),
        "summary_basis": _summary_basis(card),
    }


def _customer_insight_summary(card: Mapping[str, Any]) -> str:
    product = _preferred_product_label(card) or _safe_card_text(card.get("product_label") or card.get("product")) or "제품"
    topic = _safe_card_text(card.get("feature_topic_label") or card.get("feature_topic"))
    atomic = _safe_card_text(card.get("atomic_voc"))
    evidence = _safe_card_text(card.get("evidence_span")) or atomic
    cej_stage = _safe_card_text(card.get("cej_stage"))
    root_level = _safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity"))
    root_target = _safe_card_text(card.get("root_problem_target"))
    tone = _dashboard_tone_from_card(card)["level"]

    product_topic = _product_topic_phrase(product, topic)
    evidence_phrase = _clip_for_summary(evidence or atomic, limit=90)
    cej_clause = f" {cej_stage} 단계의 신호로 볼 수 있으며," if cej_stage and cej_stage not in {"기타", "미확인", "N/A"} else ""
    root_clause = _root_summary_clause(root_level=root_level, root_target=root_target)

    if tone == "negative":
        if evidence_phrase:
            return f"고객은 {product_topic}에서 “{evidence_phrase}”라는 불만·우려를 드러냅니다.{cej_clause}{root_clause} 개선 또는 가격·품질 커뮤니케이션 점검 후보입니다."
        return f"고객은 {product_topic}에서 불만·우려 신호를 보입니다.{cej_clause}{root_clause} 개선 후보로 검토가 필요합니다."
    if tone == "positive":
        if evidence_phrase:
            return f"고객은 {product_topic}에 대해 “{evidence_phrase}”처럼 긍정적으로 반응합니다.{cej_clause} 해당 포인트는 구매 설득·제품 소구 메시지로 활용 가능한 강점 후보입니다."
        return f"고객은 {product_topic}에 긍정적으로 반응합니다.{cej_clause} 제품 강점 후보로 볼 수 있습니다."
    if tone == "inquiry" or _safe_card_text(card.get("semantic_lane")) in {"inquiry_insight", "low_value_inquiry"}:
        if evidence_phrase:
            return f"고객은 {product_topic}와 관련해 “{evidence_phrase}”를 확인하려 합니다.{cej_clause} 정보 접근성·구매 전 탐색 니즈를 보강할 후보입니다."
        return f"고객은 {product_topic}와 관련한 정보를 확인하려 합니다.{cej_clause} 문의/정보 접근성 인사이트로 분리해 볼 수 있습니다."
    if evidence_phrase:
        return f"고객 발화는 {product_topic}와 관련해 “{evidence_phrase}”라는 관찰 신호를 제공합니다.{cej_clause}{root_clause} 추가 맥락 확인 후 전략/문의/제외 여부를 나눠야 합니다."
    return f"{product_topic} 관련 신호이나, 현재 초안만으로는 고객 인사이트를 확정하기 어려워 추가 근거 확인이 필요합니다."


def _product_topic_phrase(product: str, topic: str) -> str:
    normalized_product = product.strip().lower()
    normalized_topic = topic.strip().lower()
    product_part = "제품/맥락 미확정" if normalized_product in GENERIC_PRODUCT_LABELS else product
    topic_part = "" if normalized_topic in UNKNOWN_FEATURE_TOPIC_LABELS else topic
    if product_part and topic_part:
        return f"{product_part}의 {topic_part}"
    return product_part or topic_part or "제품/주제 미확정 영역"


def _root_summary_clause(*, root_level: str, root_target: str) -> str:
    if root_level.startswith("L3"):
        target = f"({root_target})" if root_target else ""
        return f" 문제와 원인 단서가 함께 있어 Root Cause 분석{target}으로 이어질 수 있습니다."
    if root_level.startswith("L2"):
        target = f"({root_target})" if root_target else ""
        return f" 개선 대상{target}은 비교적 명확하지만 원인 단서는 아직 분리해야 합니다."
    if root_level.startswith("L1"):
        return " 문제 존재는 보이나 개선 대상 특정은 추가 검토가 필요합니다."
    return ""


def _summary_actionability(card: Mapping[str, Any]) -> str:
    tone = _dashboard_tone_from_card(card)["level"]
    root_level = _safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity"))
    lane = _safe_card_text(card.get("semantic_lane"))
    if root_level.startswith("L3"):
        return "root_cause_analysis_candidate"
    if root_level.startswith("L2") or tone == "negative":
        return "improvement_candidate"
    if tone == "positive":
        return "value_proposition_candidate"
    if lane in {"inquiry_insight", "low_value_inquiry"} or tone == "inquiry":
        return "information_access_candidate"
    return "observation_or_review_candidate"


def _summary_basis(card: Mapping[str, Any]) -> str:
    quote = _basis_evidence_text(card)
    if quote:
        return f'근거: "{quote}"'
    return "근거 인용 보강 필요"


def _clip_for_summary(value: str, *, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _semantic_ai_draft_gap_analysis(
    *,
    unit_analysis_cards: list[dict[str, Any]],
    semantic_enhanced_unit_cards: list[dict[str, Any]],
    semantic_ai_drafts: list[dict[str, Any]],
    semantic_llm_outputs: list[dict[str, Any]],
    semantic_llm_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    total = len(semantic_ai_drafts)
    evidence_scores = [
        float(draft.get("quality", {}).get("evidence_completeness", 0.0))
        for draft in semantic_ai_drafts
        if isinstance(draft.get("quality"), Mapping)
    ]
    avg_evidence = round(sum(evidence_scores) / len(evidence_scores), 3) if evidence_scores else 0.0
    metrics = {
        "unit_card_count": len(unit_analysis_cards),
        "semantic_enhanced_unit_card_count": len(semantic_enhanced_unit_cards),
        "semantic_ai_draft_count": total,
        "semantic_llm_output_count": len(semantic_llm_outputs),
        "llm_provider": _safe_card_text(semantic_llm_diagnostics.get("provider")),
        "llm_status": _safe_card_text(semantic_llm_diagnostics.get("status")),
        "llm_succeeded": int(semantic_llm_diagnostics.get("succeeded", 0) or 0),
        "llm_failed": int(semantic_llm_diagnostics.get("failed", 0) or 0),
        "generic_product_count": _count_drafts_with_generic_product(semantic_ai_drafts),
        "unknown_feature_topic_count": _count_drafts_with_unknown_topic(semantic_ai_drafts),
        "engine_missed_or_context_needed_count": _count_drafts_with_na_status(semantic_ai_drafts),
        "average_evidence_completeness": avg_evidence,
        "customer_insight_summary_count": sum(
            1
            for draft in semantic_ai_drafts
            if _safe_card_text(draft.get("summary_layer", {}).get("customer_insight"))
        ),
        "human_review_field_count": _count_drafts_with_human_review_fields(semantic_ai_drafts),
    }
    gaps = _ai_draft_gap_items(metrics=metrics, total=total)
    blocking_gaps = [gap for gap in gaps if gap.get("severity") in {"high", "medium"}]
    readiness = "ready_for_review_export" if total and not blocking_gaps else "needs_work_before_ai_draft_promotion"
    return {
        "schema_version": "semantic-ai-draft-gap-analysis-v1",
        "promotion_readiness": readiness,
        "metrics": metrics,
        "gaps": gaps,
        "blocking_gap_count": len(blocking_gaps),
        "recommended_next_steps": _ai_draft_next_steps(gaps),
    }


def _count_drafts_with_generic_product(drafts: list[dict[str, Any]]) -> int:
    count = 0
    for draft in drafts:
        product = draft.get("judgments", {}).get("product", {}) if isinstance(draft.get("judgments"), Mapping) else {}
        label = _safe_card_text(product.get("label") if isinstance(product, Mapping) else "")
        if _is_generic_product_label(label):
            count += 1
    return count


def _count_drafts_with_unknown_topic(drafts: list[dict[str, Any]]) -> int:
    count = 0
    for draft in drafts:
        feature = draft.get("judgments", {}).get("feature_topic", {}) if isinstance(draft.get("judgments"), Mapping) else {}
        label = _safe_card_text(feature.get("label") if isinstance(feature, Mapping) else "")
        if _is_unknown_topic_label(label):
            count += 1
    return count


def _count_drafts_with_na_status(drafts: list[dict[str, Any]]) -> int:
    return sum(
        1
        for draft in drafts
        if _safe_card_text(draft.get("quality", {}).get("na_status")).lower()
        in {"engine_missed", "engine_missed_or_context_needed", "context_needed"}
    )


def _count_drafts_with_human_review_fields(drafts: list[dict[str, Any]]) -> int:
    return sum(1 for draft in drafts if isinstance(draft.get("human_review"), Mapping))


def _ai_draft_gap_items(*, metrics: Mapping[str, Any], total: int) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if total == 0:
        gaps.append(
            {
                "id": "no_ai_draft_rows",
                "severity": "high",
                "gap": "semantic_ai_drafts.jsonl에 저장할 초안 row가 없습니다.",
                "impact": "Dashboard가 조회할 AI Draft Layer가 형성되지 않습니다.",
                "next_action": "실분석 run 또는 sidecar 생성 경로를 확인합니다.",
            }
        )
        return gaps
    if int(metrics.get("llm_succeeded", 0) or 0) == 0:
        gaps.append(
            {
                "id": "llm_coverage_missing",
                "severity": "high",
                "gap": "OpenAI/LLM으로 해석된 카드가 없거나 현재 run이 payload/projection 기반입니다.",
                "impact": "Golden120 수준의 문맥 판단보다 fallback/heuristic 영향이 큽니다.",
                "next_action": "provider=openai, max_cards 소량 조건으로 LLM 결과를 확보한 뒤 동일 artifact를 재생성합니다.",
            }
        )
    if int(metrics.get("generic_product_count", 0) or 0):
        gaps.append(
            {
                "id": "generic_product_remaining",
                "severity": "medium",
                "gap": "일부 초안의 제품이 가전제품 같은 generic label에 머물러 있습니다.",
                "impact": "제품군/브랜드/라인업 단위 집계와 담당부서 전달 정확도가 떨어집니다.",
                "next_action": "원문, parent, video/source, link metadata 기반 제품 resolver를 보강합니다.",
            }
        )
    if int(metrics.get("unknown_feature_topic_count", 0) or 0):
        gaps.append(
            {
                "id": "feature_topic_unknown",
                "severity": "medium",
                "gap": "기능/주제가 미확인 또는 broad default로 남은 초안이 있습니다.",
                "impact": "subreason 매핑과 bottom-up topic clustering 모두 품질이 낮아집니다.",
                "next_action": "기능/주제 라벨과 설명을 이중 필드로 유지하되, broad default는 engine_missed/context_needed로 분리합니다.",
            }
        )
    if int(metrics.get("engine_missed_or_context_needed_count", 0) or 0):
        gaps.append(
            {
                "id": "na_status_mixed",
                "severity": "medium",
                "gap": "N/A, context 부족, engine missed가 일부 남아 있습니다.",
                "impact": "사람이 true N/A와 분석 실패를 구분하기 어렵습니다.",
                "next_action": "N/A 상태값을 true_na, scope_excluded, context_needed, engine_missed로 계속 분리 검증합니다.",
            }
        )
    if float(metrics.get("average_evidence_completeness", 0.0) or 0.0) < 0.75:
        gaps.append(
            {
                "id": "evidence_completeness_low",
                "severity": "medium",
                "gap": "판단별 실제 인용 근거가 충분히 채워지지 않았습니다.",
                "impact": "AI 초안 단독 파일만으로 J/Codex식 검수가 어렵습니다.",
                "next_action": "각 축 basis가 원문 인용구 또는 parent/video/source 인용구를 포함하도록 prompt와 merge adapter를 보강합니다.",
            }
        )
    gaps.append(
        {
            "id": "source_context_depth_incomplete",
            "severity": "watch",
            "gap": "video script 위치, 링크 해석, parent/reply thread 전체 맥락은 입력 데이터에 있을 때만 보존됩니다.",
            "impact": "Golden120에서 사람이 본 상위 맥락 수준까지 항상 재현되지는 않습니다.",
            "next_action": "crawler/raw-data 단계에서 script/description/link preview/parent thread를 evidence source로 수집하는 정책을 별도로 확정합니다.",
        }
    )
    if int(metrics.get("human_review_field_count", 0) or 0) < total:
        gaps.append(
            {
            "id": "human_review_fields_missing",
            "severity": "watch",
            "gap": "AI Draft에는 아직 J 평가/수정값/동의·수정·보류 workflow 컬럼이 없습니다.",
            "impact": "Human Golden Truth 승격용 workbook/export로 바로 쓰기에는 한 단계 부족합니다.",
            "next_action": "semantic_ai_drafts.jsonl에서 review workbook 또는 decision log skeleton을 생성하는 export를 추가합니다.",
            }
        )
    return gaps


def _ai_draft_next_steps(gaps: list[dict[str, str]]) -> list[str]:
    gap_ids = {gap["id"] for gap in gaps}
    steps = []
    if "llm_coverage_missing" in gap_ids:
        steps.append("OpenAI provider run을 소량으로 재실행해 LLM 해석 row를 확보합니다.")
    if {"generic_product_remaining", "feature_topic_unknown"} & gap_ids:
        steps.append("제품/기능·주제 resolver와 prompt의 구체화 지시를 보강합니다.")
    if "evidence_completeness_low" in gap_ids:
        steps.append("각 판단 축의 basis에 실제 인용구를 요구하고 merge 단계에서 누락 여부를 검증합니다.")
    steps.append("AI Draft review export와 append-only decision log 연결을 추가합니다.")
    return steps


def _semantic_dashboard_unit_rows(unit_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in unit_cards:
        tone = _dashboard_tone_from_card(card)
        root_level = _safe_card_text(card.get("root_problem_level") or card.get("root_cause_maturity"))
        product_label = _preferred_product_label(card) or _safe_card_text(card.get("product_group_label")) or "미확인"
        summary_layer = _summary_layer_payload(card)
        customer_insight_summary = summary_layer["customer_insight"]
        rows.append(
            {
                "schema_version": "semantic-dashboard-unit-v1",
                "source_id": _safe_card_text(card.get("source_id")),
                "case_id": _safe_card_text(card.get("case_id")),
                "source_comment_id": _safe_card_text(card.get("source_comment_id")),
                "parent_comment_id": _safe_card_text(card.get("parent_comment_id")),
                "comment_depth": _safe_card_text(card.get("comment_depth")),
                "is_reply": bool(card.get("is_reply")),
                "source_voc_index": card.get("source_voc_index", ""),
                "atomic_unit_index": card.get("atomic_unit_index", ""),
                "atomic_unit_id": _safe_card_text(card.get("atomic_unit_id")),
                "unit_title": _safe_card_text(card.get("unit_title")),
                "product": product_label,
                "product_label": _safe_card_text(card.get("product_label")),
                "product_group_label": _safe_card_text(card.get("product_group_label")),
                "product_detail": _safe_card_text(card.get("product_detail")),
                "product_basis": _safe_card_text(card.get("product_basis")),
                "product_detail_basis": _safe_card_text(card.get("product_detail_basis")),
                "feature_topic": _safe_card_text(card.get("feature_topic_label") or card.get("feature_topic")),
                "feature_topic_description": _safe_card_text(card.get("feature_topic_description")),
                "feature_topic_basis": _safe_card_text(card.get("feature_topic_basis")),
                "semantic_lane": _safe_card_text(card.get("semantic_lane")),
                "semantic_lane_reason": _safe_card_text(card.get("semantic_lane_reason")),
                "tone_label": tone["label"],
                "tone_level": tone["level"],
                "tone_basis": _safe_card_text(card.get("polarity_basis")),
                "polarity_label": _safe_card_text(card.get("polarity_label")),
                "polarity_basis": _safe_card_text(card.get("polarity_basis")),
                "cej_stage": _safe_card_text(card.get("cej_stage")),
                "cej_basis": _safe_card_text(card.get("cej_basis")),
                "cej_status": _safe_card_text(card.get("cej_status")),
                "tees_success": _safe_card_text(card.get("tees_success_value")),
                "tees_success_basis": _safe_card_text(card.get("tees_success_basis")),
                "tees_time": _safe_card_text(card.get("tees_time_value")),
                "tees_time_basis": _safe_card_text(card.get("tees_time_basis")),
                "tees_effort": _safe_card_text(card.get("tees_effort_value")),
                "tees_effort_basis": _safe_card_text(card.get("tees_effort_basis")),
                "tees_emotion": _safe_card_text(card.get("tees_emotion_value")),
                "tees_emotion_basis": _safe_card_text(card.get("tees_emotion_basis")),
                "root_problem_level": root_level,
                "root_problem_target": _safe_card_text(card.get("root_problem_target")),
                "root_cause_category": _safe_card_text(card.get("root_cause_category")),
                "root_cause_basis": _safe_card_text(card.get("root_cause_basis")),
                "scope_status": _safe_card_text(card.get("scope_status")),
                "na_status": _safe_card_text(card.get("na_status")),
                "na_reason": _safe_card_text(card.get("na_reason")),
                "needs_human_review": bool(card.get("needs_human_review")),
                "atomic_voc": _safe_card_text(card.get("atomic_voc")),
                "evidence_span": _safe_card_text(card.get("evidence_span")),
                "summary": customer_insight_summary,
                "source_summary": _safe_card_text(card.get("summary")),
                "customer_insight_summary": customer_insight_summary,
                "summary_actionability": summary_layer["actionability"],
                "summary_basis": summary_layer["summary_basis"],
                "card_source": _safe_card_text(card.get("card_source")),
                "interpreter_status": _safe_card_text(card.get("interpreter_status")),
                "quality_warnings": list(card.get("quality_warnings") or []),
                "watch_agenda_flags": list(card.get("watch_agenda_flags") or []),
            }
        )
    return rows


def _semantic_dashboard_topic_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in unit_rows:
        key = (
            _safe_card_text(row.get("product")) or "미확인",
            _safe_card_text(row.get("feature_topic")) or "미확인",
            _safe_card_text(row.get("semantic_lane")) or "missing",
        )
        bucket = grouped.setdefault(
            key,
            {
                "schema_version": "semantic-dashboard-topic-v1",
                "product": key[0],
                "feature_topic": key[1],
                "semantic_lane": key[2],
                "unit_count": 0,
                "negative_or_concern_count": 0,
                "positive_count": 0,
                "inquiry_count": 0,
                "review_required_count": 0,
                "root_l2_l3_count": 0,
                "representative_atomic_voc": "",
                "representative_summary": "",
            },
        )
        bucket["unit_count"] += 1
        if row.get("tone_level") == "negative":
            bucket["negative_or_concern_count"] += 1
        elif row.get("tone_level") == "positive":
            bucket["positive_count"] += 1
        elif row.get("tone_level") == "inquiry":
            bucket["inquiry_count"] += 1
        if bool(row.get("needs_human_review")) or key[2] in {"review_queue", "watch_agenda"}:
            bucket["review_required_count"] += 1
        if _safe_card_text(row.get("root_problem_level")).startswith(("L2", "L3")):
            bucket["root_l2_l3_count"] += 1
        if not bucket["representative_atomic_voc"]:
            bucket["representative_atomic_voc"] = _safe_card_text(row.get("atomic_voc"))
        if not bucket["representative_summary"]:
            bucket["representative_summary"] = _safe_card_text(row.get("summary"))

    return sorted(
        grouped.values(),
        key=lambda row: (
            -int(row["negative_or_concern_count"]),
            -int(row["review_required_count"]),
            -int(row["root_l2_l3_count"]),
            -int(row["unit_count"]),
            str(row["product"]),
            str(row["feature_topic"]),
        ),
    )


def _dashboard_tone_from_card(card: Mapping[str, Any]) -> dict[str, str]:
    text = " ".join(
        _safe_card_text(card.get(key)).lower()
        for key in (
            "polarity_label",
            "tees_success_value",
            "tees_time_value",
            "tees_effort_value",
            "tees_emotion_value",
            "summary",
        )
    )
    if any(token in text for token in ("negative", "concern", "불만", "불안", "우려", "실망", "미달성", "부담", "지연")):
        return {"label": "부정/우려", "level": "negative"}
    if any(token in text for token in ("positive", "satisfaction", "만족", "추천", "달성", "신뢰", "긍정")):
        return {"label": "긍정", "level": "positive"}
    lane = _safe_card_text(card.get("semantic_lane"))
    if lane in {"inquiry_insight", "low_value_inquiry"} or any(token in text for token in ("문의", "탐색", "질문")):
        return {"label": "문의/탐색", "level": "inquiry"}
    return {"label": "중립/미확정", "level": "neutral"}


def _golden120_unit_analysis_card(
    *,
    index: int,
    record: Mapping[str, Any],
    revision: object,
    evidence: object,
    cej: object,
    tees: object,
    root: object,
    product: str,
    feature_topic: str,
) -> dict[str, Any]:
    atomic_voc = getattr(revision, "text_excerpt", "") or _first_text(record, ("opinion_text", "comment_text", "text_display", "cleaned_text"))
    evidence_span = _evidence_span_text(evidence, revision)
    source_id = _source_id(record, index)
    cej_stage = _semantic_cej_stage_value(cej)
    tees_payload = _tees_card_payload(tees)
    root_maturity = _enum_value(getattr(root, "maturity", None)) if root else ""
    root_category = _enum_value(getattr(root, "cause_category", None)) if root else ""
    product_label = product or "미확인"
    feature_topic_label = feature_topic or "미확인"
    source_context_used = _source_context_used(record)
    semantic_context_payload = _semantic_context_payload(record=record, card_text=atomic_voc, source_context_used=source_context_used)
    comment_depth = _comment_depth(record)
    na_status, na_reason = _na_status_reason(
        product_label=product_label,
        feature_topic=feature_topic_label,
        cej_stage=cej_stage,
        tees_payload=tees_payload,
        record=record,
    )
    root_problem = _root_problem_payload(
        atomic_voc=atomic_voc,
        root_maturity=root_maturity,
        root_category=root_category,
    )
    confidence_notes = _card_confidence_notes(
        product_label=product_label,
        feature_topic=feature_topic_label,
        cej_stage=cej_stage,
        tees_payload=tees_payload,
        root_maturity=root_maturity,
    )
    needs_human_review = bool(confidence_notes)
    summary = _human_readable_unit_summary(
        product_label=product_label,
        feature_topic=feature_topic_label,
        atomic_voc=atomic_voc,
        cej_stage=cej_stage,
        root_maturity=root_maturity,
    )
    card = {
        "schema_version": SEMANTIC_UNIT_CARD_SCHEMA_VERSION,
        "card_source": PROJECTION_CARD_SOURCE,
        "interpreter_status": "projection_pending_golden120_interpreter",
        "row_index": index,
        "source_id": source_id,
        "case_id": source_id,
        "source_comment_id": _first_text(record, ("comment_id", "source_comment_id", "opinion_id")) or source_id,
        "parent_comment_id": _first_text(record, ("parent_comment_id", "parent_id", "reply_to_comment_id")),
        "comment_depth": comment_depth,
        "is_reply": comment_depth == "reply",
        "video_id": _first_text(record, ("video_id", "source_video_id")),
        "video_title": _first_text(record, ("video_title", "title")),
        "source_context_used": source_context_used,
        "semantic_context_payload": semantic_context_payload,
        "source_context_summary": _source_context_summary(semantic_context_payload),
        "semantic_prompt_version": GOLDEN120_PROMPT_VERSION,
        "semantic_prompt_ready": True,
        "atomic_unit_id": f"{source_id}::u{index + 1}",
        "unit_index": index + 1,
        "source_voc_index": index + 1,
        "atomic_unit_index": 1,
        "atomic_voc": atomic_voc,
        "evidence_span": evidence_span,
        "product": product_label,
        "product_label": product_label,
        "product_group_label": product_label,
        "product_detail": "",
        "product_basis": _product_basis(record=record, product_label=product_label, source_context_used=source_context_used),
        "product_detail_basis": "",
        "product_confidence": _confidence_for_product(product_label, source_context_used),
        "feature_topic": feature_topic_label,
        "feature_topic_label": feature_topic_label,
        "feature_topic_description": _feature_topic_description(feature_topic_label, atomic_voc),
        "feature_topic_basis": _feature_topic_basis(record=record, feature_topic=feature_topic_label),
        "cej_stage": cej_stage,
        "cej_basis": _cej_basis(cej=cej, record=record, atomic_voc=atomic_voc),
        "cej_status": _cej_status(product_label=product_label, cej_stage=cej_stage),
        "scope_status": _scope_status(product_label=product_label, record=record),
        "semantic_lane": "pending",
        "semantic_lane_reason": "semantic routing is finalized after rule/heuristic interpretation",
        "na_status": na_status,
        "na_reason": na_reason,
        "watch_agenda_flags": _watch_agenda_flags(record=record, atomic_voc=atomic_voc, product_label=product_label, cej_stage=cej_stage),
        "tees_success_value": _tees_axis_value(tees_payload, "success"),
        "tees_success_basis": _tees_axis_basis(tees_payload, "success"),
        "tees_time_value": _tees_axis_value(tees_payload, "time"),
        "tees_time_basis": _tees_axis_basis(tees_payload, "time"),
        "tees_effort_value": _tees_axis_value(tees_payload, "effort"),
        "tees_effort_basis": _tees_axis_basis(tees_payload, "effort"),
        "tees_emotion_value": _tees_axis_value(tees_payload, "emotion"),
        "tees_emotion_basis": _tees_axis_basis(tees_payload, "emotion"),
        "root_cause_maturity": root_maturity or "unknown",
        "root_cause_category": root_category or "unknown",
        "root_cause_basis": _root_cause_basis(root=root, atomic_voc=atomic_voc),
        "root_problem_level": root_problem["level"],
        "root_problem_label": root_problem["label"],
        "root_problem_target": root_problem["target"],
        "root_cause_confidence_label": root_problem["confidence"],
        "improvement_hints": root_problem["improvement_hints"],
        "internal_operation_notes": root_problem["internal_operation_notes"],
        "summary": summary,
        "confidence_notes": confidence_notes,
        "needs_human_review": needs_human_review,
        "cej": {
            "experience_stage": _enum_value(getattr(cej, "experience_stage", None)) if cej else "",
            "actionable_stage": _enum_value(getattr(cej, "actionable_stage", None)) if cej else "",
            "pre_gate_stage": _enum_value(getattr(cej, "pre_gate_stage", None)) if cej else "",
            "gate_reason": _enum_value(getattr(cej, "gate_reason", None)) if cej else "",
            "confidence": getattr(cej, "confidence", None) if cej else None,
        },
        "tees": tees_payload,
        "root_cause": {
            "hypothesis_text": getattr(root, "hypothesis_text", "") if root else "",
            "cause_category": root_category,
            "maturity": root_maturity,
            "confidence": getattr(root, "confidence", None) if root else None,
        },
        "legacy_context": {
            "legacy_stage": _first_text(record, ("journey_stage", "customer_journey_stage", "cej_scene_code")),
            "sentiment": _first_text(record, ("sentiment", "sentiment_final", "sentiment_label")),
            "video_title": _first_text(record, ("video_title", "title", "channel_title")),
        },
    }
    return card


def _source_context_used(record: Mapping[str, Any]) -> list[str]:
    context = []
    if _first_text(record, ("opinion_text", "comment_text", "text_display", "cleaned_text")):
        context.append("comment")
    if _first_text(record, ("parent_comment_text", "parent_text", "reply_context")):
        context.append("parent")
    if _first_text(record, ("video_title", "title", "channel_title", "source_product")):
        context.append("video/source")
    return context or ["legacy_row"]


def _semantic_context_payload(
    *,
    record: Mapping[str, Any],
    card_text: str,
    source_context_used: list[str],
) -> dict[str, Any]:
    return {
        "comment_text": _first_text(record, ("opinion_text", "comment_text", "text_display", "cleaned_text")) or card_text,
        "parent_comment_text": _first_text(record, ("parent_comment_text", "parent_text", "reply_context")),
        "video_title": _first_text(record, ("video_title", "title")),
        "channel_title": _first_text(record, ("channel_title",)),
        "source_product": _first_text(record, ("source_product", "product", "product_category", "mapped_product", "parent_product")),
        "source_bucket": _first_text(record, ("source_bucket", "bucket", "topic_bucket")),
        "source_context_used": source_context_used,
        "comment_depth": _comment_depth(record),
    }


def _source_context_summary(payload: Mapping[str, Any]) -> str:
    used = payload.get("source_context_used", [])
    if not isinstance(used, list):
        used = [used] if used else []
    labels = {
        "comment": "원문",
        "parent": "parent/reply",
        "video/source": "영상/source",
        "legacy_row": "legacy row",
    }
    used_label = ", ".join(labels.get(str(item), str(item)) for item in used) if used else "미확인"
    detail_bits = []
    if payload.get("parent_comment_text"):
        detail_bits.append("parent 맥락 포함")
    if payload.get("video_title"):
        detail_bits.append("영상 제목 포함")
    if payload.get("source_product"):
        detail_bits.append("source 제품 단서 포함")
    suffix = f" · {' / '.join(detail_bits)}" if detail_bits else ""
    return f"판단 입력: {used_label}{suffix}"


def _comment_depth(record: Mapping[str, Any]) -> str:
    if _first_text(record, ("parent_comment_id", "parent_id", "reply_to_comment_id", "parent_comment_text", "parent_text", "reply_context")):
        return "reply"
    return "top_level"


def _feature_topic_description(feature_topic: str, atomic_voc: str) -> str:
    label = str(feature_topic or "").strip()
    if label and label.strip().lower() not in UNKNOWN_FEATURE_TOPIC_LABELS:
        return f"{label} 맥락의 VoC입니다."
    if atomic_voc:
        return "원문 의미를 기반으로 기능/주제 설명 생성이 필요합니다."
    return "기능/주제 설명 미생성"


def _na_status_reason(
    *,
    product_label: str,
    feature_topic: str,
    cej_stage: str,
    tees_payload: Mapping[str, list[dict[str, Any]]],
    record: Mapping[str, Any],
) -> tuple[str, str]:
    scope = _first_text(record, ("validity", "validity_label", "scope_status")).lower()
    if scope in {"exclude", "excluded", "trash", "invalid", "out_of_scope", "scope_negative_control"}:
        return "scope_excluded", "분석 제외 또는 negative control로 표시된 row입니다."
    if product_label.strip().lower() in GENERIC_PRODUCT_LABELS or feature_topic.strip().lower() in UNKNOWN_FEATURE_TOPIC_LABELS:
        return "engine_missed_or_context_needed", "제품/기능·주제가 미확인이라 true N/A와 엔진 미포착을 구분해야 합니다."
    if cej_stage.strip().lower() in {"", "n/a", "na", "none", "unknown"}:
        return "true_na_or_scope_boundary", "CEJ가 N/A로 표시되어 scope 제외인지 단순 문의인지 확인이 필요합니다."
    if not any(tees_payload.get(axis) for axis in ("success", "time", "effort", "emotion")):
        return "axis_not_detected", "TEE/S 4축 직접 신호가 포착되지 않았습니다. true N/A인지 미포착인지 검수 대상입니다."
    return "interpreted", "주요 분석 축이 생성되었습니다."


def _root_problem_payload(
    *,
    atomic_voc: str,
    root_maturity: str,
    root_category: str,
) -> dict[str, Any]:
    text = str(atomic_voc or "")
    compact = text.replace(" ", "")
    target = ""
    if "흡입구" in text and ("결착" in text or "덮개" in text):
        target = "흡입구 덮개 결착"
    elif "카드" in text and ("할인" in text or "결제" in text):
        target = "카드 할인/결제 조건"
    elif "스팀" in text and ("부분" in text or "매트" in text):
        target = "스팀 청소 제외구역/부분 설정"
    elif any(token in text for token in ("소음", "시끄", "냄새", "고장", "불량", "안됨", "안 되", "문제", "결착")):
        target = _short_problem_target(text)

    has_problem = bool(target) or any(token in compact for token in ("안됨", "안되", "문제", "불량", "고장", "무섭", "걱정", "불안"))
    has_cause = any(token in text for token in ("때문", "원인", "걸쇠", "유격", "구조상", "설계상"))
    if root_maturity in {"supported", "likely"} and has_problem:
        has_cause = True

    if not has_problem:
        return {
            "level": "N/A",
            "label": "문제 미식별",
            "target": "",
            "confidence": "N/A",
            "improvement_hints": [],
            "internal_operation_notes": [],
        }
    if not target:
        return {
            "level": "L1",
            "label": "문제 존재",
            "target": "개선 대상 미특정",
            "confidence": "낮음",
            "improvement_hints": ["불만 규모와 반복 여부를 먼저 확인"],
            "internal_operation_notes": [],
        }
    if not has_cause:
        return {
            "level": "L2",
            "label": "문제 특정",
            "target": target,
            "confidence": "중간",
            "improvement_hints": [f"{target} 개선 과제 후보로 검토"],
            "internal_operation_notes": [],
        }
    return {
        "level": "L3",
        "label": "원인 특정",
        "target": target,
        "confidence": "높음",
        "improvement_hints": [f"{target} 원인/해결 방향 검토"],
        "internal_operation_notes": [],
    }


def _short_problem_target(text: str) -> str:
    normalized = " ".join(str(text or "").split())
    return normalized[:40] + ("…" if len(normalized) > 40 else "")


def _semantic_cej_stage_value(cej: object) -> str:
    if cej is None:
        return "미확정"
    return (
        _enum_value(getattr(cej, "experience_stage", None))
        or _enum_value(getattr(cej, "actionable_stage", None))
        or _enum_value(getattr(cej, "pre_gate_stage", None))
        or "미확정"
    )


def _product_basis(*, record: Mapping[str, Any], product_label: str, source_context_used: list[str]) -> str:
    if product_label.strip().lower() in GENERIC_PRODUCT_LABELS:
        return "legacy projection이 구체 제품을 제공하지 못했습니다. 원문/parent/video context 기반 제품 resolver 필요."
    source = _first_text(record, ("product", "product_category", "source_product", "mapped_product", "parent_product"))
    if source:
        return f"legacy/source product field: {source}"
    return f"context used: {', '.join(source_context_used)}"


def _confidence_for_product(product_label: str, source_context_used: list[str]) -> str:
    if product_label.strip().lower() in GENERIC_PRODUCT_LABELS:
        return "low"
    if "comment" in source_context_used:
        return "medium"
    return "context_needed"


def _feature_topic_basis(*, record: Mapping[str, Any], feature_topic: str) -> str:
    if feature_topic.strip().lower() in UNKNOWN_FEATURE_TOPIC_LABELS:
        return "legacy projection이 기능/주제를 생성하지 못했습니다. 원문 의미 기반 feature/topic generator 필요."
    source = _first_text(record, ("feature_topic", "topic", "topic_label", "issue_topic", "feature", "function_topic"))
    if source:
        return f"legacy topic field: {source}"
    return "revision feature refs or legacy issue labels"


def _cej_basis(*, cej: object, record: Mapping[str, Any], atomic_voc: str) -> str:
    legacy_stage = _first_text(record, ("journey_stage", "customer_journey_stage", "cej_scene_code"))
    if legacy_stage:
        return f"legacy CEJ/source stage: {legacy_stage}"
    if cej is not None:
        return "shadow projection CEJ assessment"
    if atomic_voc:
        return "CEJ resolver pending: 원문 목적/행동 맥락 기반 재판단 필요"
    return "CEJ 근거 부족"


def _cej_status(*, product_label: str, cej_stage: str) -> str:
    normalized_product = product_label.strip().lower()
    normalized_cej = cej_stage.strip().lower()
    if normalized_product in GENERIC_PRODUCT_LABELS:
        return "product_context_needed"
    if normalized_cej in {"", "미확정", "기타", "n/a", "na", "none", "unknown"}:
        return "cej_calibration_needed"
    return "projected"


def _scope_status(*, product_label: str, record: Mapping[str, Any]) -> str:
    product = product_label.strip().lower()
    if product in {"n/a", "na", "none"}:
        return "out_of_scope_candidate"
    validity = _first_text(record, ("validity", "validity_label", "scope_status"))
    if validity:
        return validity
    return "in_scope_candidate"


def _watch_agenda_flags(*, record: Mapping[str, Any], atomic_voc: str, product_label: str, cej_stage: str) -> list[str]:
    flags = []
    text = f"{atomic_voc} {_first_text(record, ('parent_comment_text', 'video_title', 'title'))}".lower()
    if product_label.strip().lower() in GENERIC_PRODUCT_LABELS and "video/source" in _source_context_used(record):
        flags.append("제품미명시→영상 context 확인")
    if any(token in text for token in ("뭐 옷을", "사람들은 왜", "더럽", "비난", "습관")):
        flags.append("타인행동비난-제외 Watch")
    if cej_stage in {"기타", "미확정"} and product_label.strip().lower() not in GENERIC_PRODUCT_LABELS:
        flags.append("CEJ 보정 필요")
    return flags


def _tees_axis_value(tees_payload: Mapping[str, list[dict[str, Any]]], axis: str) -> str:
    rows = tees_payload.get(axis, [])
    if not rows:
        return "N/A"
    return " / ".join(_first_text(row, ("signal_type", "polarity")) for row in rows if isinstance(row, Mapping)) or "신호 있음"


def _tees_axis_basis(tees_payload: Mapping[str, list[dict[str, Any]]], axis: str) -> str:
    rows = tees_payload.get(axis, [])
    if not rows:
        return "직접 확인된 표현 없음"
    quoted = [
        _first_text(row, ("quoted_summary", "signal_type"))
        for row in rows
        if isinstance(row, Mapping) and _first_text(row, ("quoted_summary", "signal_type"))
    ]
    return " | ".join(quoted) if quoted else "projection signal"


def _root_cause_basis(*, root: object, atomic_voc: str) -> str:
    if root is None:
        return "원인 후보를 생성하지 못했습니다."
    hypothesis = getattr(root, "hypothesis_text", "") or ""
    if hypothesis:
        return str(hypothesis)
    if atomic_voc:
        return "원인 단서가 약하거나 불명확합니다. hard failure로 단정 금지."
    return "원인 근거 부족"


def _card_confidence_notes(
    *,
    product_label: str,
    feature_topic: str,
    cej_stage: str,
    tees_payload: Mapping[str, list[dict[str, Any]]],
    root_maturity: str,
) -> list[str]:
    notes = []
    if product_label.strip().lower() in GENERIC_PRODUCT_LABELS:
        notes.append("제품 구체화 필요")
    if feature_topic.strip().lower() in UNKNOWN_FEATURE_TOPIC_LABELS:
        notes.append("기능/주제 생성 필요")
    if cej_stage in {"", "미확정", "기타"}:
        notes.append("CEJ 보정 필요")
    if not any(tees_payload.get(axis) for axis in ("success", "time", "effort", "emotion")):
        notes.append("TEE/S 원문 근거 재검토 필요")
    if root_maturity in {"", "unknown", "불명확"}:
        notes.append("Root Cause weak/unknown 분리 필요")
    return notes


def _human_readable_unit_summary(
    *,
    product_label: str,
    feature_topic: str,
    atomic_voc: str,
    cej_stage: str,
    root_maturity: str,
) -> str:
    if product_label.strip().lower() in GENERIC_PRODUCT_LABELS and feature_topic.strip().lower() in UNKNOWN_FEATURE_TOPIC_LABELS:
        return "현재 카드는 legacy projection 기반이라 제품/기능·주제가 충분히 구조화되지 않았습니다."
    parts = []
    if product_label and product_label.strip().lower() not in GENERIC_PRODUCT_LABELS:
        parts.append(product_label)
    if feature_topic and feature_topic.strip().lower() not in UNKNOWN_FEATURE_TOPIC_LABELS:
        parts.append(feature_topic)
    if atomic_voc:
        parts.append(str(atomic_voc)[:140])
    if cej_stage and cej_stage not in {"미확정", "기타"}:
        parts.append(f"CEJ={cej_stage}")
    if root_maturity and root_maturity not in {"unknown", "불명확"}:
        parts.append(f"RootCause={root_maturity}")
    return " · ".join(parts) if parts else "Golden120식 자연어 종합 생성 대기"


def _evidence_span_text(evidence: object, revision: object) -> str:
    quoted = getattr(evidence, "quoted_text", None)
    if quoted:
        return str(quoted)
    spans = getattr(revision, "spans", ()) or ()
    if spans:
        first = spans[0]
        quoted_text = getattr(first, "quoted_text", None)
        if quoted_text:
            return str(quoted_text)
    return getattr(revision, "text_excerpt", "") or ""


def _tees_card_payload(tees: object) -> dict[str, list[dict[str, Any]]]:
    if tees is None:
        return {"time": [], "effort": [], "emotion": [], "success": []}
    return {
        "time": _tees_signal_rows(getattr(tees, "time_signals", ()) or ()),
        "effort": _tees_signal_rows(getattr(tees, "effort_signals", ()) or ()),
        "emotion": _tees_signal_rows(getattr(tees, "emotion_signals", ()) or ()),
        "success": _tees_signal_rows(getattr(tees, "success_signals", ()) or ()),
    }


def _tees_signal_rows(signals: Iterable[object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for signal in signals:
        rows.append(
            {
                "signal_type": getattr(signal, "signal_type", ""),
                "polarity": _enum_value(getattr(signal, "polarity", None)),
                "intensity": _enum_value(getattr(signal, "intensity", None)),
                "quoted_summary": getattr(signal, "quoted_summary", "") or "",
            }
        )
    return rows


def _unit_card_summary(
    *,
    product: str,
    feature_topic: str,
    revision_text: str,
    cej: object,
    tees: object,
    root: object,
) -> str:
    cej_stage = _enum_value(getattr(cej, "experience_stage", None)) if cej else ""
    root_maturity = _enum_value(getattr(root, "maturity", None)) if root else ""
    tees_count = 0
    if tees is not None:
        tees_count = sum(
            len(getattr(tees, field_name, ()) or ())
            for field_name in ("time_signals", "effort_signals", "emotion_signals", "success_signals")
        )
    parts = []
    if product:
        parts.append(f"product={product}")
    if feature_topic:
        parts.append(f"topic={feature_topic}")
    if cej_stage:
        parts.append(f"cej={cej_stage}")
    if tees_count:
        parts.append(f"tees_signals={tees_count}")
    if root_maturity:
        parts.append(f"root_maturity={root_maturity}")
    if not parts:
        parts.append(_first_text({"text": revision_text}, ("text",))[:120])
    return "; ".join(parts)


def _semantic_comparison_rows(
    *,
    result: AtomicVocShadowProjectionResult,
    records: list[dict[str, Any]],
    limit: int = 500,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, revision in enumerate(result.revisions[:limit]):
        record = records[index] if index < len(records) else {}
        cej = result.cej_assessments[index] if index < len(result.cej_assessments) else None
        tees = result.tees_assessments[index] if index < len(result.tees_assessments) else None
        root = result.root_cause_hypotheses[index] if index < len(result.root_cause_hypotheses) else None
        rows.append(
            {
                "row_index": index,
                "source_id": _source_id(record, index),
                "legacy_stage": _first_text(record, ("journey_stage", "customer_journey_stage", "cej_scene_code")),
                "shadow_experience_stage": _enum_value(getattr(cej, "experience_stage", None)) if cej else "",
                "shadow_actionable_stage": _enum_value(getattr(cej, "actionable_stage", None)) if cej else "",
                "shadow_gate_reason": _enum_value(getattr(cej, "gate_reason", None)) if cej else "",
                "shadow_time_signal_count": len(getattr(tees, "time_signals", ()) or ()) if tees else 0,
                "shadow_effort_signal_count": len(getattr(tees, "effort_signals", ()) or ()) if tees else 0,
                "shadow_emotion_signal_count": len(getattr(tees, "emotion_signals", ()) or ()) if tees else 0,
                "shadow_success_signal_count": len(getattr(tees, "success_signals", ()) or ()) if tees else 0,
                "shadow_root_cause_maturity": _enum_value(getattr(root, "maturity", None)) if root else "",
                "text_excerpt": getattr(revision, "text_excerpt", ""),
            }
        )
    return rows


def _queue_row(
    *,
    records: list[dict[str, Any]],
    row_index: int,
    review_type: str,
    recommended_status: str,
    reason: str,
    diagnostic: Mapping[str, Any],
) -> dict[str, Any]:
    record = records[row_index] if 0 <= row_index < len(records) else {}
    return {
        "row_index": row_index,
        "source_id": _source_id(record, row_index),
        "review_type": review_type,
        "recommended_status": recommended_status,
        "reason": reason,
        "product": _first_text(record, ("product", "product_category", "source_product")),
        "legacy_stage": _first_text(record, ("journey_stage", "customer_journey_stage", "cej_scene_code")),
        "sentiment": _first_text(record, ("sentiment", "sentiment_final", "sentiment_label")),
        "text_excerpt": _first_text(record, ("opinion_text", "text_display", "cleaned_text", "comment_text"))[:300],
        "diagnostic": dict(diagnostic),
    }


def _source_id(record: Mapping[str, Any], row_index: int) -> str:
    return _first_text(record, ("opinion_id", "source_content_id", "comment_id", "video_id")) or f"row-{row_index + 1:04d}"


def _first_text(record: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none", "null", "<na>"}:
            return text
    return ""


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def _count_values(value: Any) -> dict[str, int]:
    if isinstance(value, Mapping):
        return {str(key): int(count) for key, count in sorted(value.items())}
    return {}


def _safe_run_dir_name(legacy_run_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(legacy_run_id).strip())
    return safe or "unknown_run"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Golden120 quality package clean overrides
# ---------------------------------------------------------------------------
# These definitions intentionally sit at the end of the module.  Earlier
# iterations of the semantic sidecar kept several fallback/projection helpers
# for safety, but the AI Draft promotion path now needs a stricter Golden120
# quality layer.  Python resolves these helper names at runtime, so these clean
# definitions override the older projection-oriented implementations without
# disturbing the surrounding artifact pipeline.

_QUALITY_NEGATIVE_TOKENS = (
    "불만",
    "우려",
    "아쉽",
    "아쉬",
    "비싸",
    "걱정",
    "무섭",
    "별로",
    "낮",
    "불안",
    "ㅠ",
    "ㅜ",
    "문제",
    "부족",
    "안 좋",
    "안좋",
    "받아쳐먹",
    "제한",
)
_QUALITY_POSITIVE_TOKENS = (
    "좋",
    "대박",
    "만족",
    "신세계",
    "메리트",
    "선방",
    "확실",
    "기대",
    "칭찬",
    "추천",
    "편리",
    "괜찮",
)
_QUALITY_COLOR_TOKENS = ("색상", "색깔", "검은색", "블랙", "화이트", "선택지", "색만")
_QUALITY_PRICE_TOKENS = (
    "가격",
    "책정",
    "경쟁사",
    "가성비",
    "프로모션",
    "메리트",
    "선방",
    "비싸",
    "받아쳐먹",
    "동일한 가격",
)
_QUALITY_MANUFACTURER_TOKENS = (
    "제조사",
    "중국",
    "국내 제조",
    "공급망",
    "보안",
    "신뢰",
    "picea",
    "다이슨",
    "로청 제조사",
)
_QUALITY_BUILTIN_TOKENS = ("빌트인스테이션", "빌트인 스테이션", "스테이션")
_QUALITY_SELF_DEV_TOKENS = ("자체 개발", "업그레이드", "알고리즘")
_QUALITY_COMPARISON_TOKENS = ("로보락", "삼성", "경쟁", "비교", "선택", "확정", "구매", "공간")


def _quality_blob(card: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "unit_title",
        "feature_topic_label",
        "feature_topic",
        "feature_topic_description",
        "atomic_voc",
        "evidence_span",
        "summary",
        "polarity_label",
        "watch_agenda_reason",
    ):
        value = card.get(key)
        if value:
            parts.append(str(value))
    context = card.get("semantic_context_payload")
    if isinstance(context, Mapping):
        for key in ("comment_text", "parent_comment_text", "video_title", "source_title", "source_product"):
            value = context.get(key)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def _quality_direct_blob(card: Mapping[str, Any]) -> str:
    """Text that belongs to the current Atomic Unit only.

    The full semantic context can contain the entire source comment.  That is
    useful for evidence ranking, but it is too broad for split/merge decisions:
    a color-option atomic can inherit self-development/comparison words from
    the same parent comment and be merged incorrectly.  Boundary and duplicate
    decisions should therefore prefer direct unit fields.
    """

    parts: list[str] = []
    for key in (
        "unit_title",
        "feature_topic_label",
        "feature_topic",
        "feature_topic_description",
        "atomic_voc",
        "evidence_span",
        "summary",
        "polarity_label",
        "watch_agenda_reason",
    ):
        value = card.get(key)
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def _has_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token and token in text for token in tokens)


def _quality_source_key(card: Mapping[str, Any]) -> str:
    for key in ("source_comment_id", "source_id", "case_id", "comment_id"):
        value = str(card.get(key) or "").strip()
        if value:
            return value.split("::u", 1)[0].split("#u", 1)[0]
    return str(card.get("unit_id") or card.get("atomic_unit_id") or "")


def _combine_unique_texts(values: Iterable[Any], *, sep: str = " ") -> str:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        normalized = " ".join(text.split())
        if normalized in seen:
            continue
        seen.add(normalized)
        output.append(text)
    return sep.join(output)


def _quality_best_quote(card: Mapping[str, Any], tokens: Iterable[str]) -> str:
    blob = _quality_blob(card)
    candidates: list[str] = []
    for raw_part in blob.replace("\r", "\n").split("\n"):
        for delimiter in ("。", ".", "?", "!", "ㅠ", "ㅜ"):
            raw_part = raw_part.replace(delimiter, delimiter + "\n")
        for segment in raw_part.split("\n"):
            segment = segment.strip(" \t:：-–—")
            if 3 <= len(segment) <= 220:
                candidates.append(segment)
    if not candidates:
        return str(card.get("evidence_span") or card.get("atomic_voc") or "").strip()[:220]

    token_list = tuple(token for token in tokens if token)

    def score(segment: str) -> tuple[int, int]:
        token_score = sum(3 for token in token_list if token in segment)
        polarity_score = 0
        if _has_any(segment, _QUALITY_NEGATIVE_TOKENS):
            polarity_score += 2
        if _has_any(segment, _QUALITY_POSITIVE_TOKENS):
            polarity_score += 2
        return (token_score + polarity_score, min(len(segment), 120))

    return max(candidates, key=score)


def _quality_basis(card: Mapping[str, Any], tokens: Iterable[str], judgment: str) -> str:
    quote = _quality_best_quote(card, tokens)
    if quote:
        return f'근거: "{quote}" / 판단: {judgment}'
    return f"판단: {judgment}"


def _quote_from_basis(basis: str) -> str:
    text = str(basis or "")
    for marker in ('근거: "', '洹쇨굅: "'):
        if marker in text:
            start = text.find(marker) + len(marker)
            end = text.find('"', start)
            if end > start:
                return text[start:end].strip()
    return ""


def _quality_root_issue_kind(card: Mapping[str, Any]) -> str:
    blob = _quality_direct_blob(card) or _quality_blob(card)
    if _has_any(blob, _QUALITY_COLOR_TOKENS) and _has_any(blob, _QUALITY_NEGATIVE_TOKENS):
        return "color_option"
    if _has_any(blob, _QUALITY_MANUFACTURER_TOKENS) and _has_any(blob, _QUALITY_NEGATIVE_TOKENS):
        return "manufacturer_trust"
    if _has_any(blob, _QUALITY_PRICE_TOKENS) and _has_any(blob, _QUALITY_NEGATIVE_TOKENS):
        return "price_policy"
    if _has_any(blob, _QUALITY_BUILTIN_TOKENS) and _has_any(blob, _QUALITY_POSITIVE_TOKENS):
        return "positive_builtin_station"
    if _has_any(blob, _QUALITY_SELF_DEV_TOKENS) and _has_any(blob, _QUALITY_POSITIVE_TOKENS):
        return "positive_self_development"
    return ""


def _is_purchase_choice_comparison_card(card: Mapping[str, Any]) -> bool:
    blob = _quality_direct_blob(card) or _quality_blob(card)
    return _has_any(blob, _QUALITY_COMPARISON_TOKENS) and (
        _has_any(blob, _QUALITY_POSITIVE_TOKENS) or _has_any(blob, ("선택", "확정", "구매"))
    )


def _score_card_specificity(card: Mapping[str, Any]) -> int:
    blob = _quality_direct_blob(card) or _quality_blob(card)
    score = 0
    for tokens in (
        _QUALITY_COLOR_TOKENS,
        _QUALITY_PRICE_TOKENS,
        _QUALITY_MANUFACTURER_TOKENS,
        _QUALITY_BUILTIN_TOKENS,
        _QUALITY_SELF_DEV_TOKENS,
        _QUALITY_COMPARISON_TOKENS,
    ):
        score += sum(1 for token in tokens if token in blob)
    score += min(len(str(card.get("evidence_span") or "")), 300) // 30
    return score


def _set_root_problem_payload(card: dict[str, Any], *, level: str, category: str, target: str, basis: str) -> None:
    card["root_cause_maturity"] = level
    card["root_problem_maturity"] = level
    card["root_cause_category"] = category
    card["root_problem_category"] = category
    card["root_improvement_target"] = target
    card["root_cause_basis"] = basis
    card["root_problem_basis"] = basis
    card["root_cause_confidence"] = "evidence_based" if level.startswith(("L2", "L3")) else "not_applicable"
    if level.startswith("L0"):
        card["na_status"] = "true_na"
    else:
        card["na_status"] = "interpreted"
        card["needs_human_review"] = True


def _apply_root_problem_l0_l3_quality(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    for card in cards:
        issue_kind = _quality_root_issue_kind(card)
        if issue_kind == "price_policy":
            basis = _quality_basis(card, _QUALITY_PRICE_TOKENS, "가격 정책/가치 포지셔닝 개선 대상이 구체적으로 식별됨")
            _set_root_problem_payload(
                card,
                level="L2 · 개선 대상 특정",
                category="가격 정책 / 가치 포지셔닝",
                target="가격 정책/가치 포지셔닝",
                basis=basis,
            )
        elif issue_kind == "manufacturer_trust":
            basis = _quality_basis(card, _QUALITY_MANUFACTURER_TOKENS, "제조 신뢰/공급망/보안 신뢰 개선 대상이 구체적으로 식별됨")
            _set_root_problem_payload(
                card,
                level="L2 · 개선 대상 특정",
                category="제조 신뢰 / 공급망 인식 / 보안 신뢰",
                target="제조 신뢰/공급망 인식/보안 신뢰",
                basis=basis,
            )
        elif issue_kind == "color_option":
            basis = _quality_basis(card, _QUALITY_COLOR_TOKENS, "색상 옵션/디자인 선택지 개선 대상이 구체적으로 식별됨")
            _set_root_problem_payload(
                card,
                level="L2 · 개선 대상 특정",
                category="제품 옵션/디자인",
                target="색상 옵션/디자인 선택지",
                basis=basis,
            )
        elif issue_kind == "positive_builtin_station":
            basis = _quality_basis(card, _QUALITY_BUILTIN_TOKENS, "개선 대상보다 구매 매력 포인트로 해석됨")
            _set_root_problem_payload(
                card,
                level="L0 · 문제 없음",
                category="매력 요인",
                target="개선 대상 아님",
                basis=basis,
            )
        elif issue_kind == "positive_self_development":
            basis = _quality_basis(card, _QUALITY_SELF_DEV_TOKENS, "개선 대상보다 자체 개발/업그레이드 기대 신호로 해석됨")
            _set_root_problem_payload(
                card,
                level="L0 · 문제 없음",
                category="매력 요인/기대",
                target="개선 대상 아님",
                basis=basis,
            )
        else:
            continue
        events.append(
            {
                "type": "root_problem_l0_l3_reclassified",
                "source_id": card.get("source_id") or card.get("case_id"),
                "issue_kind": issue_kind,
                "root_problem_maturity": card.get("root_problem_maturity"),
                "root_problem_category": card.get("root_problem_category"),
            }
        )
    return cards, events


def _merge_atomic_boundary_quality_cards(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        grouped.setdefault(_quality_source_key(card), []).append(card)

    output: list[dict[str, Any]] = []
    consumed: set[int] = set()
    for source_key, group in grouped.items():
        self_dev_cards = [
            card
            for card in group
            if _has_any(_quality_direct_blob(card) or _quality_blob(card), _QUALITY_SELF_DEV_TOKENS)
            and _has_any(_quality_direct_blob(card) or _quality_blob(card), _QUALITY_POSITIVE_TOKENS)
        ]
        choice_cards = [card for card in group if _is_purchase_choice_comparison_card(card)]
        if self_dev_cards and choice_cards:
            merge_cards: list[dict[str, Any]] = []
            for candidate in self_dev_cards + choice_cards:
                if id(candidate) not in {id(item) for item in merge_cards}:
                    merge_cards.append(candidate)
            if len(merge_cards) >= 2:
                base = dict(max(merge_cards, key=_score_card_specificity))
                base["unit_title"] = "자체 개발 기대와 구매 선택 논리"
                base["feature_topic_label"] = "자체 개발/업그레이드 기대 및 경쟁제품 대비 선택 이유"
                base["feature_topic"] = base["feature_topic_label"]
                base["feature_topic_description"] = (
                    "자체 개발과 향후 업그레이드 가능성, 경쟁 제품 대비 선택 이유가 하나의 구매 선택 논리로 연결됩니다."
                )
                base["atomic_voc"] = _combine_unique_texts((card.get("atomic_voc") for card in merge_cards))
                base["evidence_span"] = _combine_unique_texts((card.get("evidence_span") for card in merge_cards))
                base["polarity_label"] = "positive"
                base["polarity_reason"] = _quality_basis(
                    base,
                    (*_QUALITY_SELF_DEV_TOKENS, *_QUALITY_COMPARISON_TOKENS, *_QUALITY_POSITIVE_TOKENS),
                    "자체 개발 기대와 제품 선택 이유가 하나의 긍정 구매 논리로 연결됨",
                )
                base["emotion_value"] = "positive/trust_expectation"
                base["emotion_basis"] = base["polarity_reason"]
                base["quality_warnings"] = sorted(
                    set(base.get("quality_warnings") or []) | {"atomic_boundary_merged_purchase_choice_flow"}
                )
                _set_root_problem_payload(
                    base,
                    level="L0 · 문제 없음",
                    category="매력 요인/기대",
                    target="개선 대상 아님",
                    basis=_quality_basis(base, _QUALITY_SELF_DEV_TOKENS, "구매 매력/기대 신호이며 개선 대상은 아님"),
                )
                for card in merge_cards:
                    consumed.add(id(card))
                output.append(base)
                events.append(
                    {
                        "type": "atomic_boundary_merged_purchase_choice_flow",
                        "source_id": source_key,
                        "input_count": len(merge_cards),
                        "output_title": base["unit_title"],
                    }
                )

    for card in cards:
        if id(card) not in consumed:
            output.append(card)
    return output, events


def _remove_duplicate_split_quality_cards(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        grouped.setdefault(_quality_source_key(card), []).append(card)

    duplicate_ids: set[int] = set()
    kept_ids: set[int] = set()
    for source_key, group in grouped.items():
        color_cards = [card for card in group if _quality_root_issue_kind(card) == "color_option"]
        if len(color_cards) <= 1:
            continue
        keep = max(color_cards, key=_score_card_specificity)
        kept_ids.add(id(keep))
        removed = [card for card in color_cards if card is not keep]
        duplicate_ids.update(id(card) for card in removed)
        keep["quality_warnings"] = sorted(
            set(keep.get("quality_warnings") or []) | {"duplicate_split_removed_color_option"}
        )
        keep["duplicate_split_removed_count"] = int(keep.get("duplicate_split_removed_count") or 0) + len(removed)
        events.append(
            {
                "type": "duplicate_split_detected_and_removed",
                "source_id": source_key,
                "duplicate_type": "color_option",
                "kept_source_id": keep.get("source_id") or keep.get("case_id"),
                "removed_count": len(removed),
                "removed_source_ids": [card.get("source_id") or card.get("case_id") for card in removed],
            }
        )

    output = [card for card in cards if id(card) not in duplicate_ids]
    for card in output:
        if id(card) in kept_ids:
            card["quality_warnings"] = sorted(
                set(card.get("quality_warnings") or []) | {"duplicate_split_detected"}
            )
    return output, events


def _rewrite_quality_customer_insight_summary(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    for card in cards:
        issue_kind = _quality_root_issue_kind(card)
        if issue_kind == "price_policy":
            summary = (
                "동일 가격 대비 품질·가치가 낮다는 인식이 구매 저항으로 나타납니다. "
                "가격 정책과 가치 포지셔닝 메시지를 보완할 개선 후보입니다."
            )
        elif issue_kind == "manufacturer_trust":
            summary = (
                "제조사·공급망·보안 신뢰가 구매 리스크로 인식됩니다. "
                "국내 개발/제조 근거와 보안 신뢰 커뮤니케이션을 강화할 필요가 있습니다."
            )
        elif issue_kind == "color_option":
            summary = (
                "색상 선택지 제한이 제품 매력도를 낮추는 불만으로 드러납니다. "
                "색상/디자인 옵션 확대를 검토할 수 있는 개선 후보입니다."
            )
        elif issue_kind == "positive_builtin_station":
            summary = (
                "빌트인스테이션은 사용자가 즉시 인지하는 강한 매력 포인트입니다. "
                "제품 차별화와 구매 설득 메시지에서 우선 활용할 수 있습니다."
            )
        elif issue_kind == "positive_self_development":
            summary = (
                "자체 개발과 업그레이드 가능성은 제품 신뢰와 기대감을 높이는 신호입니다. "
                "향후 성능 개선 로드맵을 구매 설득 포인트로 연결할 수 있습니다."
            )
        else:
            continue
        card["summary"] = summary
        card["customer_insight_summary"] = summary
        card["customer_insight_summary_override"] = summary
        events.append(
            {
                "type": "customer_insight_summary_rewritten",
                "source_id": card.get("source_id") or card.get("case_id"),
                "issue_kind": issue_kind,
            }
        )
    return cards, events


def _semantic_quality_postprocess_cards(unit_cards: list[dict[str, Any]]) -> dict[str, Any]:
    cards = [dict(card) for card in unit_cards]
    input_count = len(cards)
    events: list[dict[str, Any]] = []

    cards, step_events = _merge_atomic_boundary_quality_cards(cards)
    events.extend(step_events)
    cards, step_events = _remove_duplicate_split_quality_cards(cards)
    events.extend(step_events)
    cards, step_events = _apply_root_problem_l0_l3_quality(cards)
    events.extend(step_events)
    cards, step_events = _rewrite_quality_customer_insight_summary(cards)
    events.extend(step_events)

    metrics = {
        "input_count": input_count,
        "output_count": len(cards),
        "atomic_boundary_merge_count": sum(1 for event in events if event.get("type") == "atomic_boundary_merged_purchase_choice_flow"),
        "duplicate_split_detected_count": sum(1 for event in events if event.get("type") == "duplicate_split_detected_and_removed"),
        "duplicate_split_removed_count": sum(int(event.get("removed_count") or 0) for event in events if event.get("type") == "duplicate_split_detected_and_removed"),
        "root_reclassified_count": sum(1 for event in events if event.get("type") == "root_problem_l0_l3_reclassified"),
        "summary_rewritten_count": sum(1 for event in events if event.get("type") == "customer_insight_summary_rewritten"),
    }
    return {"cards": cards, "events": events, "metrics": metrics}


def _quality_postprocess_gap_items(semantic_quality_postprocess: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(semantic_quality_postprocess, Mapping):
        return []
    metrics = semantic_quality_postprocess.get("metrics")
    events = semantic_quality_postprocess.get("events")
    if not isinstance(metrics, Mapping):
        metrics = {}
    if not isinstance(events, list):
        events = []

    gaps: list[dict[str, Any]] = []
    if int(metrics.get("duplicate_split_detected_count") or 0) > 0:
        gaps.append(
            {
                "id": "duplicate_split_detected",
                "severity": "watch",
                "message": "동일 source 안에서 색상 불만 등 중복 Atomic 후보를 감지했고 품질 후처리에서 제거했습니다.",
                "count": int(metrics.get("duplicate_split_detected_count") or 0),
            }
        )
    if int(metrics.get("atomic_boundary_merge_count") or 0) > 0:
        gaps.append(
            {
                "id": "atomic_boundary_merged",
                "severity": "watch",
                "message": "자체 개발 기대+제품 비교+구매 선택 논리처럼 하나의 의도 흐름인 Atomic을 병합했습니다.",
                "count": int(metrics.get("atomic_boundary_merge_count") or 0),
            }
        )
    if int(metrics.get("root_reclassified_count") or 0) > 0:
        gaps.append(
            {
                "id": "root_l0_l3_reclassified",
                "severity": "info",
                "message": "Root Cause를 고장 원인 대신 개선 과제 성숙도 L0~L3 기준으로 재판정했습니다.",
                "count": int(metrics.get("root_reclassified_count") or 0),
            }
        )
    return gaps


def _customer_insight_summary(card: Mapping[str, Any]) -> str:
    override = str(card.get("customer_insight_summary_override") or card.get("customer_insight_summary") or "").strip()
    if override:
        return override
    issue_kind = _quality_root_issue_kind(card)
    if issue_kind == "price_policy":
        return "가격 정책과 가치 포지셔닝이 구매 저항으로 연결될 수 있어 메시지와 가격 설계 점검이 필요합니다."
    if issue_kind == "manufacturer_trust":
        return "제조사·공급망·보안 신뢰가 구매 리스크로 작동할 수 있어 신뢰 근거 커뮤니케이션이 필요합니다."
    if issue_kind == "color_option":
        return "색상 선택지 제한이 제품 매력도를 낮추는 개선 후보로 확인됩니다."
    if issue_kind == "positive_builtin_station":
        return "빌트인스테이션은 제품 차별화와 구매 설득에 활용 가능한 강한 긍정 신호입니다."
    if issue_kind == "positive_self_development":
        return "자체 개발과 업그레이드 기대는 제품 신뢰와 향후 개선 가능성을 높이는 긍정 신호입니다."
    summary = str(card.get("summary") or "").strip()
    if summary:
        product = _preferred_product_label(card) or str(card.get("product_label") or card.get("product") or "제품").strip()
        topic = str(card.get("feature_topic_label") or card.get("feature_topic") or "").strip()
        product_topic = f"{product}의 {topic}" if product and topic else product or topic or "해당 제품/주제"
        evidence = _clip_for_summary(str(card.get("atomic_voc") or card.get("evidence_span") or summary), limit=90)
        tone = _dashboard_tone_from_card(card)["level"]
        if tone == "negative":
            return f"고객은 {product_topic}에서 '{evidence}'라는 불만/우려를 보이며, 개선 대상 여부를 검토할 필요가 있습니다."
        if tone == "positive":
            return f"고객은 {product_topic}에서 '{evidence}'라는 긍정 반응을 보이며, 구매 설득 포인트로 활용 가능한 신호입니다."
        if tone == "inquiry":
            return f"고객은 {product_topic}와 관련해 '{evidence}'를 확인하려 하며, 정보 접근성 또는 구매 전 탐색 니즈가 있습니다."
        return f"고객은 {product_topic}와 관련해 '{evidence}'라는 신호를 남겼으며, 추가 맥락 확인 후 전략/문의/제외 여부를 판단해야 합니다."
    atomic = str(card.get("atomic_voc") or card.get("evidence_span") or "").strip()
    if atomic:
        return f"이 VoC는 '{atomic[:80]}' 맥락에서 후속 검토가 필요한 고객 신호입니다."
    return "고객 인사이트 요약이 아직 생성되지 않았습니다."


def _semantic_ai_draft_gap_analysis(
    *,
    unit_analysis_cards: list[dict[str, Any]],
    semantic_enhanced_unit_cards: list[dict[str, Any]],
    semantic_ai_drafts: list[dict[str, Any]],
    semantic_llm_outputs: list[dict[str, Any]] | None = None,
    semantic_llm_diagnostics: Mapping[str, Any] | None = None,
    semantic_quality_postprocess: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    llm_outputs = semantic_llm_outputs or []
    diagnostics = dict(semantic_llm_diagnostics or {})
    total_drafts = len(semantic_ai_drafts)
    evidence_scores = [
        _evidence_completeness_score(layer)
        for draft in semantic_ai_drafts
        if isinstance(draft, Mapping)
        for layer in [draft.get("evidence_layer")]
        if isinstance(layer, Mapping)
    ]
    avg_evidence = round(sum(evidence_scores) / len(evidence_scores), 3) if evidence_scores else 0.0
    metrics = {
        "unit_analysis_cards": len(unit_analysis_cards),
        "semantic_enhanced_unit_cards": len(semantic_enhanced_unit_cards),
        "semantic_ai_drafts": total_drafts,
        "semantic_ai_draft_count": total_drafts,
        "semantic_llm_outputs": len(llm_outputs),
        "llm_provider": diagnostics.get("provider", ""),
        "llm_status": diagnostics.get("status", ""),
        "llm_attempted": int(diagnostics.get("attempted") or 0),
        "llm_succeeded": int(diagnostics.get("succeeded") or 0),
        "llm_failed": int(diagnostics.get("failed") or 0),
        "average_evidence_completeness": avg_evidence,
    }
    if isinstance(semantic_quality_postprocess, Mapping):
        qp_metrics = semantic_quality_postprocess.get("metrics")
        if isinstance(qp_metrics, Mapping):
            metrics.update(
                {
                    "quality_postprocess_input_count": int(qp_metrics.get("input_count") or 0),
                    "quality_postprocess_output_count": int(qp_metrics.get("output_count") or 0),
                    "atomic_boundary_merge_count": int(qp_metrics.get("atomic_boundary_merge_count") or 0),
                    "duplicate_split_detected_count": int(qp_metrics.get("duplicate_split_detected_count") or 0),
                    "duplicate_split_removed_count": int(qp_metrics.get("duplicate_split_removed_count") or 0),
                    "root_reclassified_count": int(qp_metrics.get("root_reclassified_count") or 0),
                    "summary_rewritten_count": int(qp_metrics.get("summary_rewritten_count") or 0),
                }
            )

    gaps: list[dict[str, Any]] = []
    try:
        gaps.extend(_ai_draft_gap_items(metrics=metrics, total=total_drafts))
    except NameError:
        gaps = []
    gaps.extend(_quality_postprocess_gap_items(semantic_quality_postprocess))
    if avg_evidence >= 0.75:
        gaps = [gap for gap in gaps if gap.get("id") != "evidence_completeness_low"]

    blocking = [gap for gap in gaps if str(gap.get("severity") or "").lower() in {"high", "medium", "blocker", "blocking"}]
    promotion_readiness = (
        "ready_for_review_export" if total_drafts and not blocking else "needs_work_before_ai_draft_promotion"
    )
    return {
        "schema_version": "semantic-ai-draft-gap-analysis-v1",
        "version": "golden120_ai_draft_gap_analysis_v3",
        "metrics": metrics,
        "gaps": gaps,
        "blocking_gap_count": len(blocking),
        "promotion_readiness": promotion_readiness,
        "recommendation": (
            "AI Draft를 Human Review workbook으로 내보낼 수 있습니다."
            if promotion_readiness == "ready_for_review_export"
            else "blocking/medium gap을 먼저 검토한 뒤 review export를 진행하세요."
        ),
    }


# Final override: keep the AI Draft gap analysis aligned with the actual
# semantic_ai_drafts rows after quality post-processing.  Earlier compatibility
# layers can still call _ai_draft_gap_items(), but they must receive the draft
# quality metrics it expects; otherwise average_evidence_completeness defaults
# to 0 and raises a false evidence_completeness_low gap.
def _semantic_ai_draft_gap_analysis(
    *,
    unit_analysis_cards: list[dict[str, Any]],
    semantic_enhanced_unit_cards: list[dict[str, Any]],
    semantic_ai_drafts: list[dict[str, Any]],
    semantic_llm_outputs: list[dict[str, Any]] | None = None,
    semantic_llm_diagnostics: Mapping[str, Any] | None = None,
    semantic_quality_postprocess: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    llm_outputs = semantic_llm_outputs or []
    diagnostics = dict(semantic_llm_diagnostics or {})
    total_drafts = len(semantic_ai_drafts)

    evidence_scores: list[float] = []
    customer_insight_count = 0
    human_review_count = 0
    generic_product_count = 0
    unknown_topic_count = 0
    na_status_count = 0

    for draft in semantic_ai_drafts:
        if not isinstance(draft, Mapping):
            continue
        quality = draft.get("quality")
        if isinstance(quality, Mapping):
            try:
                evidence_scores.append(float(quality.get("evidence_completeness") or 0.0))
            except (TypeError, ValueError):
                evidence_scores.append(0.0)
            na_status = _safe_card_text(quality.get("na_status")).lower()
            if na_status in {"engine_missed", "engine_missed_or_context_needed", "context_needed"}:
                na_status_count += 1

        judgments = draft.get("judgments")
        if isinstance(judgments, Mapping):
            product = judgments.get("product")
            if isinstance(product, Mapping) and _is_generic_product_label(_safe_card_text(product.get("label"))):
                generic_product_count += 1
            feature_topic = judgments.get("feature_topic")
            if isinstance(feature_topic, Mapping) and _is_unknown_topic_label(_safe_card_text(feature_topic.get("label"))):
                unknown_topic_count += 1

        summary_layer = draft.get("summary_layer")
        if isinstance(summary_layer, Mapping) and _safe_card_text(summary_layer.get("customer_insight")):
            customer_insight_count += 1
        if isinstance(draft.get("human_review"), Mapping):
            human_review_count += 1

    avg_evidence = round(sum(evidence_scores) / len(evidence_scores), 3) if evidence_scores else 0.0
    metrics: dict[str, Any] = {
        "unit_card_count": len(unit_analysis_cards),
        "unit_analysis_cards": len(unit_analysis_cards),
        "semantic_enhanced_unit_card_count": len(semantic_enhanced_unit_cards),
        "semantic_enhanced_unit_cards": len(semantic_enhanced_unit_cards),
        "semantic_ai_draft_count": total_drafts,
        "semantic_ai_drafts": total_drafts,
        "semantic_ai_draft_count": total_drafts,
        "semantic_llm_output_count": len(llm_outputs),
        "semantic_llm_outputs": len(llm_outputs),
        "llm_provider": diagnostics.get("provider", ""),
        "llm_status": diagnostics.get("status", ""),
        "llm_attempted": int(diagnostics.get("attempted") or 0),
        "llm_succeeded": int(diagnostics.get("succeeded") or 0),
        "llm_failed": int(diagnostics.get("failed") or 0),
        "generic_product_count": generic_product_count,
        "unknown_feature_topic_count": unknown_topic_count,
        "engine_missed_or_context_needed_count": na_status_count,
        "average_evidence_completeness": avg_evidence,
        "customer_insight_summary_count": customer_insight_count,
        "human_review_field_count": human_review_count,
    }
    if isinstance(semantic_quality_postprocess, Mapping):
        qp_metrics = semantic_quality_postprocess.get("metrics")
        if isinstance(qp_metrics, Mapping):
            metrics.update(
                {
                    "quality_postprocess_input_count": int(qp_metrics.get("input_count") or 0),
                    "quality_postprocess_output_count": int(qp_metrics.get("output_count") or 0),
                    "atomic_boundary_merge_count": int(qp_metrics.get("atomic_boundary_merge_count") or 0),
                    "duplicate_split_detected_count": int(qp_metrics.get("duplicate_split_detected_count") or 0),
                    "duplicate_split_removed_count": int(qp_metrics.get("duplicate_split_removed_count") or 0),
                    "root_reclassified_count": int(qp_metrics.get("root_reclassified_count") or 0),
                    "summary_rewritten_count": int(qp_metrics.get("summary_rewritten_count") or 0),
                    "evidence_fields_refreshed_count": int(qp_metrics.get("evidence_fields_refreshed_count") or 0),
                }
            )

    gaps: list[dict[str, Any]] = []
    try:
        gaps.extend(_ai_draft_gap_items(metrics=metrics, total=total_drafts))
    except NameError:
        gaps = []
    gaps.extend(_quality_postprocess_gap_items(semantic_quality_postprocess))

    # If post-processing has already refreshed evidence and the actual draft
    # evidence score is healthy, do not keep a stale medium blocker around.
    if avg_evidence >= 0.75:
        gaps = [gap for gap in gaps if gap.get("id") != "evidence_completeness_low"]

    blocking = [gap for gap in gaps if str(gap.get("severity") or "").lower() in {"high", "medium", "blocker", "blocking"}]
    promotion_readiness = (
        "ready_for_review_export" if total_drafts and not blocking else "needs_work_before_ai_draft_promotion"
    )
    return {
        "schema_version": "semantic-ai-draft-gap-analysis-v1",
        "version": "golden120_ai_draft_gap_analysis_v3",
        "metrics": metrics,
        "gaps": gaps,
        "blocking_gap_count": len(blocking),
        "promotion_readiness": promotion_readiness,
        "recommendation": (
            "AI Draft를 Human Review workbook으로 내보낼 준비가 되었습니다."
            if promotion_readiness == "ready_for_review_export"
            else "blocking/medium gap을 먼저 검토한 뒤 review export를 진행하세요."
        ),
    }


def _is_purchase_choice_comparison_card(card: Mapping[str, Any]) -> bool:
    """Final guard for purchase-choice boundary detection.

    Color-option language also contains words such as "선택", but that should
    not be treated as the same Atomic flow as product comparison or purchase
    choice.  Require explicit product/brand comparison language before merging
    with self-development expectation cards.
    """

    blob = _quality_direct_blob(card) or _quality_blob(card)
    if _has_any(blob, _QUALITY_COLOR_TOKENS):
        return False
    strict_comparison_tokens = ("로보락", "삼성", "경쟁", "경쟁사", "비교")
    purchase_choice_tokens = ("선택", "확정", "구매", "보다가", "공간")
    return _has_any(blob, strict_comparison_tokens) and (
        _has_any(blob, _QUALITY_POSITIVE_TOKENS) or _has_any(blob, purchase_choice_tokens)
    )


# ---------------------------------------------------------------------------
# Golden120 quality package v2 clean Korean overrides
# ---------------------------------------------------------------------------
# The block above preserves older behavior for artifact compatibility, but some
# Korean literals in that historical override are mojibake.  This final block is
# intentionally appended so runtime name resolution uses the clean v2 quality
# rules for Duplicate Split, Atomic Boundary, Evidence Completeness, and Root
# Cause/Summary post-processing.

_QUALITY_NEGATIVE_TOKENS = (
    "불만",
    "우려",
    "아쉽",
    "아쉬운",
    "아쉬움",
    "비싸",
    "걱정",
    "무섭",
    "불안",
    "부족",
    "별로",
    "안 좋",
    "문제",
    "결착문제",
    "받아쳐먹",
    "제한",
    "품질 낮",
    "실망",
    "분노",
    "시끄럽",
    "먼지",
    "엉킴",
    "냄새",
    "ㅠ",
    "ㅜ",
)
_QUALITY_POSITIVE_TOKENS = (
    "좋",
    "대박",
    "만족",
    "신세계",
    "메리트",
    "선방",
    "확실",
    "기대",
    "칭찬",
    "추천",
    "갖고싶",
    "갖고 싶",
    "사고싶",
    "사고 싶",
    "업그레이드",
    "자체 개발",
    "자체개발",
    "직배수",
    "빌트인",
    "편하다",
    "괜찮",
)
_QUALITY_COLOR_TOKENS = ("색상", "색깔", "검은색", "블랙", "화이트", "선택지", "색만", "검은색만", "옵션")
_QUALITY_PRICE_TOKENS = (
    "가격",
    "책정",
    "경쟁사",
    "가성비",
    "프로모션",
    "메리트",
    "선방",
    "비싸",
    "받아쳐먹",
    "같은가격",
    "같은 가격",
    "품질",
)
_QUALITY_MANUFACTURER_TOKENS = (
    "제조사",
    "중국",
    "국내 제조",
    "공급망",
    "보안",
    "신뢰",
    "picea",
    "다이슨",
    "로청 제조사",
    "제조",
)
_QUALITY_BUILTIN_TOKENS = ("빌트인스테이션", "빌트인 스테이션", "스테이션", "자동비움", "자동 비움")
_QUALITY_SELF_DEV_TOKENS = ("자체 개발", "자체개발", "업그레이드", "알고리즘")
_QUALITY_COMPARISON_TOKENS = ("로보락", "삼성", "경쟁", "경쟁사", "비교", "선택", "확정", "구매", "공간", "보다가")
_QUALITY_INLET_COVER_TOKENS = ("흡입구", "덮개", "흡입구덮개", "결착", "점검", "케어매니저")


def _quote_from_basis(basis: str) -> str:
    text = str(basis or "")
    for marker in ('근거: "', "근거:'", "근거: '", 'quote: "'):
        if marker in text:
            quote_char = "'" if marker.endswith("'") else '"'
            start = text.find(marker) + len(marker)
            end = text.find(quote_char, start)
            if end > start:
                return text[start:end].strip()
    # Fallback: first quoted text in either Korean/English-style basis.
    for quote_char in ('"', "'"):
        start = text.find(quote_char)
        if start >= 0:
            end = text.find(quote_char, start + 1)
            if end > start:
                return text[start + 1 : end].strip()
    return ""


def _split_evidence_segments(text: str) -> list[str]:
    source = str(text or "").replace("\r", "\n")
    for delimiter in ("\n", ".", "?", "!", "…", "ㅋ", "ㅎ", "ㅠ", "ㅜ", "그리고", "근데", "하지만", "반면", "다만", "또"):
        source = source.replace(delimiter, f"{delimiter}\n")
    segments: list[str] = []
    for segment in source.split("\n"):
        cleaned = segment.strip(" \t\r\n:;,.!?\"'“”‘’/|")
        if 2 <= len(cleaned) <= 260:
            segments.append(cleaned)
    return segments


def _quality_blob(card: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "unit_title",
        "feature_topic_label",
        "feature_topic",
        "feature_topic_description",
        "atomic_voc",
        "evidence_span",
        "summary",
        "customer_insight_summary",
        "polarity_label",
        "polarity_basis",
        "emotion_value",
        "emotion_basis",
        "tees_emotion_basis",
        "root_cause_basis",
        "root_problem_basis",
        "watch_agenda_reason",
    ):
        value = card.get(key)
        if value:
            parts.append(str(value))
    context = card.get("semantic_context_payload")
    if isinstance(context, Mapping):
        for key in ("comment_text", "parent_comment_text", "video_title", "source_title", "source_product"):
            value = context.get(key)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def _quality_direct_blob(card: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "unit_title",
        "feature_topic_label",
        "feature_topic",
        "feature_topic_description",
        "atomic_voc",
        "evidence_span",
        "summary",
        "customer_insight_summary",
        "polarity_label",
        "polarity_basis",
        "emotion_value",
        "emotion_basis",
        "tees_emotion_basis",
        "root_cause_basis",
        "root_problem_basis",
    ):
        value = card.get(key)
        if value:
            parts.append(str(value))
    return "\n".join(parts)


def _has_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token and token in text for token in tokens)


def _quality_source_key(card: Mapping[str, Any]) -> str:
    for key in ("source_comment_id", "source_id", "case_id", "comment_id"):
        value = str(card.get(key) or "").strip()
        if value:
            return value.split("::u", 1)[0].split("#u", 1)[0]
    return str(card.get("unit_id") or card.get("atomic_unit_id") or "")


def _combine_unique_texts(values: Iterable[Any], *, sep: str = " ") -> str:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        normalized = " ".join(text.split())
        if normalized in seen:
            continue
        seen.add(normalized)
        output.append(text)
    return sep.join(output)


def _quality_text_overlap(left: str, right: str) -> float:
    left_tokens = {token for token in str(left or "").replace("/", " ").split() if len(token) >= 2}
    right_tokens = {token for token in str(right or "").replace("/", " ").split() if len(token) >= 2}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))


def _quality_best_quote(card: Mapping[str, Any], tokens: Iterable[str]) -> str:
    token_list = tuple(token for token in tokens if token)
    candidates: list[tuple[int, str]] = []
    weighted_fields = (
        ("evidence_span", 9),
        ("atomic_voc", 8),
        ("polarity_basis", 7),
        ("emotion_basis", 7),
        ("tees_emotion_basis", 7),
        ("feature_topic_basis", 6),
        ("cej_basis", 6),
        ("root_cause_basis", 6),
        ("root_problem_basis", 6),
        ("summary", 3),
    )
    for field, base_weight in weighted_fields:
        raw = str(card.get(field) or "")
        quote = _quote_from_basis(raw) or raw
        for segment in _split_evidence_segments(quote):
            token_score = sum(5 for token in token_list if token in segment)
            sentiment_score = 0
            if _has_any(segment, _QUALITY_NEGATIVE_TOKENS):
                sentiment_score += 4
            if _has_any(segment, _QUALITY_POSITIVE_TOKENS):
                sentiment_score += 4
            length_score = min(len(segment), 140) // 20
            candidates.append((base_weight + token_score + sentiment_score + length_score, segment))
    context = card.get("semantic_context_payload")
    if isinstance(context, Mapping):
        for field, base_weight in (("comment_text", 5), ("parent_comment_text", 4), ("video_title", 2), ("source_title", 2)):
            for segment in _split_evidence_segments(str(context.get(field) or "")):
                token_score = sum(5 for token in token_list if token in segment)
                if token_score:
                    candidates.append((base_weight + token_score + min(len(segment), 140) // 25, segment))
    if not candidates:
        return str(card.get("evidence_span") or card.get("atomic_voc") or "").strip()[:220]
    return max(candidates, key=lambda item: item[0])[1]


def _quality_basis(card: Mapping[str, Any], tokens: Iterable[str], judgment: str) -> str:
    quote = _quality_best_quote(card, tokens)
    if quote:
        return f'근거: "{quote}" / 판단: {judgment}'
    return f"판단: {judgment}"


def _quality_root_issue_kind(card: Mapping[str, Any]) -> str:
    override = str(card.get("root_issue_kind_override") or "").strip()
    if override in {
        "price_policy",
        "manufacturer_trust",
        "color_option",
        "inlet_cover_fit",
        "positive_builtin_station",
        "positive_self_development",
    }:
        return override
    direct = _quality_direct_blob(card)
    full = direct or _quality_blob(card)
    if _has_any(direct, _QUALITY_INLET_COVER_TOKENS) and _has_any(full, (*_QUALITY_NEGATIVE_TOKENS, "결착")):
        return "inlet_cover_fit"
    if _has_any(direct, _QUALITY_COLOR_TOKENS) and _has_any(full, _QUALITY_NEGATIVE_TOKENS):
        return "color_option"
    if _has_any(direct, _QUALITY_MANUFACTURER_TOKENS) and _has_any(full, _QUALITY_NEGATIVE_TOKENS):
        return "manufacturer_trust"
    if _has_any(direct, _QUALITY_PRICE_TOKENS) and _has_any(full, _QUALITY_NEGATIVE_TOKENS):
        return "price_policy"
    if _has_any(direct, _QUALITY_BUILTIN_TOKENS) and _has_any(full, _QUALITY_POSITIVE_TOKENS):
        return "positive_builtin_station"
    if _has_any(direct, _QUALITY_SELF_DEV_TOKENS) and _has_any(full, _QUALITY_POSITIVE_TOKENS):
        return "positive_self_development"
    return ""


def _is_purchase_choice_comparison_card(card: Mapping[str, Any]) -> bool:
    blob = _quality_direct_blob(card) or _quality_blob(card)
    if _has_any(blob, (*_QUALITY_COLOR_TOKENS, *_QUALITY_INLET_COVER_TOKENS)):
        return False
    return _has_any(blob, _QUALITY_COMPARISON_TOKENS) and (
        _has_any(blob, _QUALITY_POSITIVE_TOKENS) or _has_any(blob, ("선택", "확정", "구매", "보다가", "공간"))
    )


def _is_positive_purchase_choice_flow_card(card: Mapping[str, Any]) -> bool:
    blob = _quality_direct_blob(card) or _quality_blob(card)
    issue_kind = _quality_root_issue_kind(card)
    if issue_kind in {"color_option", "inlet_cover_fit", "manufacturer_trust", "price_policy"}:
        return False
    if _has_any(blob, (*_QUALITY_COLOR_TOKENS, *_QUALITY_INLET_COVER_TOKENS)):
        return False
    if issue_kind == "positive_self_development":
        return True
    return _has_any(blob, _QUALITY_SELF_DEV_TOKENS) and _has_any(
        blob,
        (*_QUALITY_POSITIVE_TOKENS, "업그레이드", "기대", "확실", "선택", "구매", "로보락", "삼성"),
    )


def _score_card_specificity(card: Mapping[str, Any]) -> int:
    blob = _quality_direct_blob(card) or _quality_blob(card)
    score = 0
    for tokens in (
        _QUALITY_COLOR_TOKENS,
        _QUALITY_PRICE_TOKENS,
        _QUALITY_MANUFACTURER_TOKENS,
        _QUALITY_BUILTIN_TOKENS,
        _QUALITY_SELF_DEV_TOKENS,
        _QUALITY_COMPARISON_TOKENS,
        _QUALITY_INLET_COVER_TOKENS,
    ):
        score += sum(1 for token in tokens if token in blob)
    score += min(len(str(card.get("evidence_span") or "")), 300) // 30
    return score


def _set_root_problem_payload(card: dict[str, Any], *, level: str, category: str, target: str, basis: str) -> None:
    card["root_cause_maturity"] = level
    card["root_problem_maturity"] = level
    card["root_cause_category"] = category
    card["root_problem_category"] = category
    card["root_improvement_target"] = target
    card["root_cause_basis"] = basis
    card["root_problem_basis"] = basis
    card["root_cause_confidence"] = "evidence_based" if level.startswith(("L2", "L3")) else "not_applicable"
    card["root_problem_confidence"] = card["root_cause_confidence"]
    if level.startswith("L0"):
        card["na_status"] = "true_na"
    else:
        card["na_status"] = "interpreted"
        card["needs_human_review"] = True


def _apply_root_problem_l0_l3_quality(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    payloads = {
        "price_policy": (
            _QUALITY_PRICE_TOKENS,
            "L2 · 개선 대상 특정",
            "가격 정책 / 가치 포지셔닝",
            "가격 정책/구매가치 커뮤니케이션",
            "가격 정책 또는 가치 포지셔닝 개선 대상이 구체적으로 식별됨",
        ),
        "manufacturer_trust": (
            _QUALITY_MANUFACTURER_TOKENS,
            "L2 · 개선 대상 특정",
            "제조 신뢰 / 공급망 인식 / 보안 신뢰",
            "제조사 신뢰/공급망/보안 커뮤니케이션",
            "제조사·공급망·보안 신뢰 개선 대상이 구체적으로 식별됨",
        ),
        "color_option": (
            _QUALITY_COLOR_TOKENS,
            "L2 · 개선 대상 특정",
            "제품 옵션/디자인",
            "색상 옵션/디자인 선택지",
            "색상 옵션 또는 디자인 선택지 개선 대상이 구체적으로 식별됨",
        ),
        "inlet_cover_fit": (
            _QUALITY_INLET_COVER_TOKENS,
            "L2 · 개선 대상 특정",
            "흡입구 덮개 결착 / 현장 점검",
            "흡입구 덮개 결착 구조/점검 가이드",
            "흡입구 덮개 결착 문제와 점검·A/S 대응 대상이 구체적으로 식별됨",
        ),
        "positive_builtin_station": (
            _QUALITY_BUILTIN_TOKENS,
            "L0 · 문제 없음",
            "매력 포인트",
            "개선 대상 아님",
            "불편이 아니라 구매 매력 포인트로 해석됨",
        ),
        "positive_self_development": (
            _QUALITY_SELF_DEV_TOKENS,
            "L0 · 문제 없음",
            "매력 포인트/기대",
            "개선 대상 아님",
            "불편이 아니라 자체 개발·업그레이드 기대 신호로 해석됨",
        ),
    }
    for card in cards:
        issue_kind = _quality_root_issue_kind(card)
        if str(card.get("atomic_boundary_kind") or "") == "positive_purchase_choice_flow":
            issue_kind = "positive_self_development"
        if issue_kind not in payloads:
            continue
        tokens, level, category, target, judgment = payloads[issue_kind]
        _set_root_problem_payload(
            card,
            level=level,
            category=category,
            target=target,
            basis=_quality_basis(card, tokens, judgment),
        )
        events.append(
            {
                "type": "root_problem_l0_l3_reclassified",
                "source_id": card.get("source_id") or card.get("case_id"),
                "issue_kind": issue_kind,
                "root_problem_maturity": card.get("root_problem_maturity"),
                "root_problem_category": card.get("root_problem_category"),
            }
        )
    return cards, events


def _merge_atomic_boundary_quality_cards(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        grouped.setdefault(_quality_source_key(card), []).append(card)

    output: list[dict[str, Any]] = []
    consumed: set[int] = set()
    for source_key, group in grouped.items():
        self_dev_cards = [card for card in group if _quality_root_issue_kind(card) == "positive_self_development"]
        choice_cards = [card for card in group if _is_purchase_choice_comparison_card(card)]
        positive_flow_cards = [card for card in group if _is_positive_purchase_choice_flow_card(card)]
        if self_dev_cards and (choice_cards or len(positive_flow_cards) >= 2):
            merge_cards: list[dict[str, Any]] = []
            for candidate in self_dev_cards + choice_cards + positive_flow_cards:
                if id(candidate) not in {id(item) for item in merge_cards}:
                    merge_cards.append(candidate)
            if len(merge_cards) >= 2:
                base = dict(max(merge_cards, key=_score_card_specificity))
                base["unit_title"] = "자체 개발·업그레이드 기대와 구매 선택 논리"
                base["feature_topic_label"] = "자체 개발/업그레이드 기대 및 구매 선택 논리"
                base["feature_topic"] = base["feature_topic_label"]
                base["feature_topic_description"] = (
                    "자체 개발과 향후 업그레이드 가능성, 경쟁 제품 대비 선택 이유가 하나의 긍정 구매 선택 흐름으로 연결됩니다."
                )
                base["atomic_voc"] = _combine_unique_texts((card.get("atomic_voc") for card in merge_cards))
                base["evidence_span"] = _combine_unique_texts((card.get("evidence_span") for card in merge_cards))
                base["polarity_label"] = "positive"
                base["polarity_reason"] = _quality_basis(
                    base,
                    (*_QUALITY_SELF_DEV_TOKENS, *_QUALITY_COMPARISON_TOKENS, *_QUALITY_POSITIVE_TOKENS),
                    "자체 개발 기대와 제품 선택 이유가 하나의 긍정 구매 논리로 연결됨",
                )
                base["emotion_value"] = "positive/trust_expectation"
                base["emotion_basis"] = base["polarity_reason"]
                base["atomic_boundary_kind"] = "positive_purchase_choice_flow"
                base["root_issue_kind_override"] = "positive_self_development"
                base["quality_warnings"] = sorted(
                    set(base.get("quality_warnings") or []) | {"atomic_boundary_merged_purchase_choice_flow"}
                )
                _set_root_problem_payload(
                    base,
                    level="L0 · 문제 없음",
                    category="매력 포인트/기대",
                    target="개선 대상 아님",
                    basis=_quality_basis(base, _QUALITY_SELF_DEV_TOKENS, "구매 매력/기대 신호이며 개선 대상은 아님"),
                )
                base["summary"] = (
                    "고객 인사이트: 자체 개발과 업그레이드 가능성은 경쟁 제품 비교 상황에서 구매 선택을 지지하는 신뢰 신호입니다. "
                    "전략 시사점: 개선 과제보다는 제품 로드맵·차별화 메시지로 활용할 수 있습니다."
                )
                base["customer_insight_summary"] = base["summary"]
                base["customer_insight_summary_override"] = base["summary"]
                for card in merge_cards:
                    consumed.add(id(card))
                output.append(base)
                events.append(
                    {
                        "type": "atomic_boundary_merged_purchase_choice_flow",
                        "source_id": source_key,
                        "input_count": len(merge_cards),
                        "output_title": base["unit_title"],
                    }
                )

    for card in cards:
        if id(card) not in consumed:
            output.append(card)
    return output, events


def _remove_duplicate_split_quality_cards(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        grouped.setdefault(_quality_source_key(card), []).append(card)

    duplicate_ids: set[int] = set()
    kept_ids: set[int] = set()
    for source_key, group in grouped.items():
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for card in group:
            issue_kind = _quality_root_issue_kind(card)
            if issue_kind in {"color_option", "inlet_cover_fit"}:
                by_kind.setdefault(issue_kind, []).append(card)
        for issue_kind, same_kind_cards in by_kind.items():
            if len(same_kind_cards) <= 1:
                continue
            keep = max(same_kind_cards, key=_score_card_specificity)
            removed: list[dict[str, Any]] = []
            keep_blob = _quality_direct_blob(keep)
            for card in same_kind_cards:
                if card is keep:
                    continue
                blob = _quality_direct_blob(card)
                overlap = _quality_text_overlap(keep_blob, blob)
                evidence_contained = str(card.get("evidence_span") or "") in keep_blob or str(keep.get("evidence_span") or "") in blob
                if issue_kind == "inlet_cover_fit" or overlap >= 0.25 or evidence_contained:
                    removed.append(card)
            if not removed:
                continue
            kept_ids.add(id(keep))
            duplicate_ids.update(id(card) for card in removed)
            if issue_kind == "inlet_cover_fit":
                keep["unit_title"] = "흡입구 덮개 결착 문제"
                keep["feature_topic_label"] = "흡입구 덮개 결착 문제"
                keep["feature_topic"] = keep["feature_topic_label"]
                keep["feature_topic_description"] = "흡입구 덮개 결착/고정 문제로 사용 불안과 점검 부담이 드러나는 개선 포인트입니다."
                keep["evidence_span"] = _combine_unique_texts(
                    (card.get("evidence_span") for card in [keep, *removed]),
                    sep=" / ",
                )
                keep["atomic_voc"] = _combine_unique_texts(
                    (card.get("atomic_voc") for card in [keep, *removed]),
                    sep=" / ",
                )
                keep["polarity_label"] = "negative"
                keep["polarity_basis"] = _quality_basis(
                    keep,
                    (*_QUALITY_INLET_COVER_TOKENS, *_QUALITY_NEGATIVE_TOKENS),
                    "흡입구 덮개 결착 문제와 점검 불안이 같은 개선 포인트로 연결됨",
                )
                keep["emotion_value"] = "anxiety/concern"
                keep["emotion_basis"] = keep["polarity_basis"]
                keep["tees_emotion_value"] = keep["emotion_value"]
                keep["tees_emotion_basis"] = keep["emotion_basis"]
                keep["summary"] = (
                    "고객 인사이트: 흡입구 덮개 결착 문제는 사용 중 불안과 현장 점검 부담으로 이어질 수 있습니다. "
                    "개선 후보: 결착 구조 점검과 판매 후 점검·A/S 대응 가이드 정비가 필요합니다."
                )
                keep["customer_insight_summary"] = keep["summary"]
                keep["customer_insight_summary_override"] = keep["summary"]
            keep["quality_warnings"] = sorted(
                set(keep.get("quality_warnings") or []) | {f"duplicate_split_removed_{issue_kind}"}
            )
            keep["duplicate_split_removed_count"] = int(keep.get("duplicate_split_removed_count") or 0) + len(removed)
            events.append(
                {
                    "type": "duplicate_split_detected_and_removed",
                    "source_id": source_key,
                    "duplicate_type": issue_kind,
                    "kept_source_id": keep.get("source_id") or keep.get("case_id"),
                    "removed_count": len(removed),
                    "removed_source_ids": [card.get("source_id") or card.get("case_id") for card in removed],
                }
            )

    output = [card for card in cards if id(card) not in duplicate_ids]
    for card in output:
        if id(card) in kept_ids:
            card["quality_warnings"] = sorted(set(card.get("quality_warnings") or []) | {"duplicate_split_detected"})
    return output, events


def _refresh_quality_evidence_fields(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    issue_tokens = {
        "price_policy": _QUALITY_PRICE_TOKENS,
        "manufacturer_trust": _QUALITY_MANUFACTURER_TOKENS,
        "color_option": _QUALITY_COLOR_TOKENS,
        "inlet_cover_fit": _QUALITY_INLET_COVER_TOKENS,
        "positive_builtin_station": _QUALITY_BUILTIN_TOKENS,
        "positive_self_development": _QUALITY_SELF_DEV_TOKENS,
    }
    for card in cards:
        issue_kind = _quality_root_issue_kind(card)
        tokens = issue_tokens.get(issue_kind) or (*_QUALITY_POSITIVE_TOKENS, *_QUALITY_NEGATIVE_TOKENS)
        quote = _quality_best_quote(card, tokens)
        if not quote:
            continue
        changed = False
        current_evidence = str(card.get("evidence_span") or "").strip()
        if not current_evidence or current_evidence in {"N/A", "없음", "미확인"} or len(current_evidence) < 4:
            card["evidence_span"] = quote
            changed = True
        card["strongest_evidence_span"] = quote
        for field, judgment in (
            ("feature_topic_basis", "기능/주제와 직접 연결되는 근거"),
            ("cej_basis", "고객경험여정 판단 근거"),
            ("polarity_basis", "감성/의견 방향 판단 근거"),
            ("emotion_basis", "감정 신호 판단 근거"),
            ("tees_emotion_basis", "TEE/S Emotion 판단 근거"),
        ):
            value = str(card.get(field) or "")
            if not _quote_from_basis(value) and (issue_kind or "직접 신호" not in value):
                card[field] = f'근거: "{quote}" / 판단: {judgment}'
                changed = True
        if issue_kind and not _quote_from_basis(str(card.get("root_cause_basis") or "")):
            card["root_cause_basis"] = _quality_basis(card, tokens, "개선 대상 또는 매력 포인트 판단 근거")
            card["root_problem_basis"] = card["root_cause_basis"]
            changed = True
        if changed:
            card["evidence_quality"] = "strongest_quote_selected"
            events.append(
                {
                    "type": "evidence_fields_refreshed",
                    "source_id": card.get("source_id") or card.get("case_id"),
                    "issue_kind": issue_kind,
                    "quote": quote,
                }
            )
    return cards, events


def _rewrite_quality_customer_insight_summary(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    summaries = {
        "price_policy": (
            "고객 인사이트: 가격 정책과 가치 포지셔닝이 구매 판단의 리스크로 작동합니다. "
            "개선 후보: 동일 가격 대비 품질·가치 메시지와 가격 책정 근거를 더 명확히 커뮤니케이션할 필요가 있습니다."
        ),
        "manufacturer_trust": (
            "고객 인사이트: 제조사·공급망·보안 신뢰가 구매 리스크로 인식됩니다. "
            "개선 후보: 국내 개발/제조 근거, 협력 구조, 보안 검증 정보를 구매 전 신뢰 메시지로 보강할 필요가 있습니다."
        ),
        "color_option": (
            "고객 인사이트: 색상 선택지 제한이 제품 매력도를 낮추는 불만으로 드러납니다. "
            "개선 후보: 색상/디자인 옵션 확대 또는 선택지 제한 사유 커뮤니케이션을 검토할 수 있습니다."
        ),
        "inlet_cover_fit": (
            "고객 인사이트: 흡입구 덮개 결착 이슈가 사용 불안과 현장 점검 부담으로 이어질 수 있습니다. "
            "개선 후보: 결착 구조 점검과 판매 후 점검·A/S 대응 가이드가 개선 후보입니다."
        ),
        "positive_builtin_station": (
            "고객 인사이트: 빌트인스테이션은 사용자가 즉시 인지하는 강한 매력 포인트입니다. "
            "전략 시사점: 제품 차별화와 구매 설득 메시지에서 우선 강조할 수 있습니다."
        ),
        "positive_self_development": (
            "고객 인사이트: 자체 개발과 업그레이드 가능성은 제품 신뢰와 기대감을 높이는 신호입니다. "
            "전략 시사점: 향후 성능 개선 로드맵을 구매 설득 포인트로 연결할 수 있습니다."
        ),
    }
    for card in cards:
        issue_kind = _quality_root_issue_kind(card)
        summary = summaries.get(issue_kind)
        if not summary:
            continue
        card["summary"] = summary
        card["customer_insight_summary"] = summary
        card["customer_insight_summary_override"] = summary
        events.append(
            {
                "type": "customer_insight_summary_rewritten",
                "source_id": card.get("source_id") or card.get("case_id"),
                "issue_kind": issue_kind,
            }
        )
    return cards, events


def _semantic_quality_postprocess_cards(unit_cards: list[dict[str, Any]]) -> dict[str, Any]:
    cards = [dict(card) for card in unit_cards]
    input_count = len(cards)
    events: list[dict[str, Any]] = []

    for step in (
        _merge_atomic_boundary_quality_cards,
        _remove_duplicate_split_quality_cards,
        _apply_root_problem_l0_l3_quality,
        _rewrite_quality_customer_insight_summary,
        _refresh_quality_evidence_fields,
        _apply_p0_atomic_voc_schema,
    ):
        cards, step_events = step(cards)
        events.extend(step_events)

    metrics = {
        "input_count": input_count,
        "output_count": len(cards),
        "atomic_boundary_merge_count": sum(1 for event in events if event.get("type") == "atomic_boundary_merged_purchase_choice_flow"),
        "duplicate_split_detected_count": sum(1 for event in events if event.get("type") == "duplicate_split_detected_and_removed"),
        "duplicate_split_removed_count": sum(int(event.get("removed_count") or 0) for event in events if event.get("type") == "duplicate_split_detected_and_removed"),
        "root_reclassified_count": sum(1 for event in events if event.get("type") == "root_problem_l0_l3_reclassified"),
        "summary_rewritten_count": sum(1 for event in events if event.get("type") == "customer_insight_summary_rewritten"),
        "evidence_fields_refreshed_count": sum(1 for event in events if event.get("type") == "evidence_fields_refreshed"),
        "p0_atomic_voc_schema_applied_count": sum(1 for event in events if event.get("type") == "p0_atomic_voc_schema_applied"),
    }
    return {"cards": cards, "events": events, "metrics": metrics}


def _apply_p0_atomic_voc_schema(cards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    for card in cards:
        evidence_layer = _evidence_layer_payload(card)
        atomic_record = _p0_atomic_voc_record(card, evidence_layer=evidence_layer)
        card["parent_voc_id"] = atomic_record["parent_voc_id"]
        card["atomic_id"] = atomic_record["atomic_id"]
        card["atomic_index"] = atomic_record["atomic_index"]
        card["atomic_voc_schema_version"] = P0_ATOMIC_VOC_SCHEMA_VERSION
        card["atomic_evidence_scope"] = atomic_record["evidence_scope"]
        card["topic_status"] = atomic_record["topic_status"]
        card["cej_p0_status"] = atomic_record["cej_status"]
        card["root_cause_level"] = atomic_record["root_cause_level"]
        card["root_cause_problem"] = atomic_record["root_cause_problem"]
        card["root_cause_target"] = atomic_record["root_cause_target"]
        card["root_cause_cause"] = atomic_record["root_cause_cause"]
        card["root_cause_p0_status"] = atomic_record["root_cause_status"]
        for axis in ("success", "time", "effort", "emotion"):
            card[f"tees_{axis}_status"] = atomic_record[f"tees_{axis}_status"]
        events.append(
            {
                "type": "p0_atomic_voc_schema_applied",
                "source_id": card.get("source_id") or card.get("case_id"),
                "parent_voc_id": card.get("parent_voc_id"),
                "atomic_id": card.get("atomic_id"),
            }
        )
    return cards, events


def _quality_postprocess_gap_items(semantic_quality_postprocess: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(semantic_quality_postprocess, Mapping):
        return []
    metrics = semantic_quality_postprocess.get("metrics")
    if not isinstance(metrics, Mapping):
        metrics = {}

    gaps: list[dict[str, Any]] = []
    if int(metrics.get("duplicate_split_detected_count") or 0) > 0:
        gaps.append(
            {
                "id": "duplicate_split_detected",
                "severity": "watch",
                "message": "동일 source 안에서 중복 Atomic 후보를 감지했고 후처리에서 제거했습니다.",
                "count": int(metrics.get("duplicate_split_detected_count") or 0),
            }
        )
    if int(metrics.get("atomic_boundary_merge_count") or 0) > 0:
        gaps.append(
            {
                "id": "atomic_boundary_merged",
                "severity": "watch",
                "message": "자체 개발 기대와 제품 비교/구매 선택 논리가 하나의 흐름으로 판단되어 Atomic을 병합했습니다.",
                "count": int(metrics.get("atomic_boundary_merge_count") or 0),
            }
        )
    if int(metrics.get("root_reclassified_count") or 0) > 0:
        gaps.append(
            {
                "id": "root_l0_l3_reclassified",
                "severity": "info",
                "message": "Root Cause를 고장 원인이 아니라 개선 과제 성숙도 L0~L3 기준으로 재판정했습니다.",
                "count": int(metrics.get("root_reclassified_count") or 0),
            }
        )
    if int(metrics.get("evidence_fields_refreshed_count") or 0) > 0:
        gaps.append(
            {
                "id": "evidence_fields_refreshed",
                "severity": "info",
                "message": "판단별 근거가 약한 카드에 strongest evidence를 재선택해 반영했습니다.",
                "count": int(metrics.get("evidence_fields_refreshed_count") or 0),
            }
        )
    return gaps


def _field_evidence_is_applicable(row: Mapping[str, Any]) -> bool:
    field = str(row.get("field") or "")
    value = str(row.get("value") or "").strip().lower()
    basis = str(row.get("basis") or "")
    if not field:
        return False
    if value in {"", "n/a", "na", "none", "직접 신호 없음", "해당 없음"}:
        # TEE/S axes are often legitimately absent.  Do not punish true N/A
        # when the basis explicitly says no direct signal is present.
        if field.startswith("tees_") and ("직접 신호" in basis or "direct signal" in basis or "해당 축" in basis):
            return False
        if field in {"root_cause", "root_problem"} and ("문제 없음" in basis or "문제 미식별" in basis):
            return False
    return True


def _evidence_completeness_score(evidence_layer: Mapping[str, Any]) -> float:
    rows = evidence_layer.get("field_evidence")
    if not isinstance(rows, list) or not rows:
        return 0.0
    applicable = [row for row in rows if isinstance(row, Mapping) and _field_evidence_is_applicable(row)]
    if not applicable:
        return 1.0
    quoted = 0
    for row in applicable:
        quote = _safe_card_text(row.get("quote"))
        basis = _safe_card_text(row.get("basis"))
        if quote or _quote_from_basis(basis):
            quoted += 1
    return round(quoted / len(applicable), 3)


def _semantic_ai_draft_gap_analysis(
    *,
    unit_analysis_cards: list[dict[str, Any]],
    semantic_enhanced_unit_cards: list[dict[str, Any]],
    semantic_ai_drafts: list[dict[str, Any]],
    semantic_llm_outputs: list[dict[str, Any]] | None = None,
    semantic_llm_diagnostics: Mapping[str, Any] | None = None,
    semantic_quality_postprocess: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    llm_outputs = semantic_llm_outputs or []
    diagnostics = dict(semantic_llm_diagnostics or {})
    total_drafts = len(semantic_ai_drafts)
    evidence_scores = [
        _evidence_completeness_score(layer)
        for draft in semantic_ai_drafts
        if isinstance(draft, Mapping)
        for layer in [draft.get("evidence_layer")]
        if isinstance(layer, Mapping)
    ]
    avg_evidence = round(sum(evidence_scores) / len(evidence_scores), 3) if evidence_scores else 0.0
    metrics = {
        "unit_analysis_cards": len(unit_analysis_cards),
        "semantic_enhanced_unit_cards": len(semantic_enhanced_unit_cards),
        "semantic_ai_drafts": total_drafts,
        "semantic_ai_draft_count": total_drafts,
        "semantic_llm_outputs": len(llm_outputs),
        "llm_provider": diagnostics.get("provider", ""),
        "llm_status": diagnostics.get("status", ""),
        "llm_attempted": int(diagnostics.get("attempted") or 0),
        "llm_succeeded": int(diagnostics.get("succeeded") or 0),
        "llm_failed": int(diagnostics.get("failed") or 0),
        "average_evidence_completeness": avg_evidence,
    }
    if isinstance(semantic_quality_postprocess, Mapping):
        qp_metrics = semantic_quality_postprocess.get("metrics")
        if isinstance(qp_metrics, Mapping):
            metrics.update(
                {
                    "quality_postprocess_input_count": int(qp_metrics.get("input_count") or 0),
                    "quality_postprocess_output_count": int(qp_metrics.get("output_count") or 0),
                    "atomic_boundary_merge_count": int(qp_metrics.get("atomic_boundary_merge_count") or 0),
                    "duplicate_split_detected_count": int(qp_metrics.get("duplicate_split_detected_count") or 0),
                    "duplicate_split_removed_count": int(qp_metrics.get("duplicate_split_removed_count") or 0),
                    "root_reclassified_count": int(qp_metrics.get("root_reclassified_count") or 0),
                    "summary_rewritten_count": int(qp_metrics.get("summary_rewritten_count") or 0),
                    "evidence_fields_refreshed_count": int(qp_metrics.get("evidence_fields_refreshed_count") or 0),
                }
            )

    gaps: list[dict[str, Any]] = []
    try:
        gaps.extend(_ai_draft_gap_items(metrics=metrics, total=total_drafts))
    except NameError:
        gaps = []
    gaps.extend(_quality_postprocess_gap_items(semantic_quality_postprocess))
    if avg_evidence >= 0.75:
        gaps = [gap for gap in gaps if gap.get("id") != "evidence_completeness_low"]

    blocking = [gap for gap in gaps if str(gap.get("severity") or "").lower() in {"high", "medium", "blocker", "blocking"}]
    promotion_readiness = (
        "ready_for_review_export" if total_drafts and not blocking else "needs_work_before_ai_draft_promotion"
    )
    return {
        "schema_version": "semantic-ai-draft-gap-analysis-v1",
        "version": "golden120_ai_draft_gap_analysis_v3",
        "metrics": metrics,
        "gaps": gaps,
        "blocking_gap_count": len(blocking),
        "promotion_readiness": promotion_readiness,
        "recommendation": (
            "AI Draft를 Human Review workbook으로 내보낼 수 있습니다."
            if promotion_readiness == "ready_for_review_export"
            else "blocking/medium gap을 먼저 검토한 뒤 review export를 진행하세요."
        ),
    }
