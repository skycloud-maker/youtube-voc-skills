"""Canonical 66-column contract for the VoC rebuild engine."""

from __future__ import annotations

import json
from collections.abc import Iterable, MutableMapping
from typing import Any


TARGET_COLUMNS = [
    "source_id", "raw_row_index", "parent_voc_id", "comment_relation",
    "atomic_id", "atomic_index", "original_voc", "voc_cleaned", "voc_residual",
    "atomic_voc", "atomic_voc_summary", "topic_provisional", "topic",
    "topic_evidence", "topic_score", "reference_brand", "product_tags",
    "product_additional_info", "competitor_brand_tags", "competitor_product_tags",
    "competitor_product_additional_info", "brand", "market", "language", "cej",
    "cej_evidence", "inquiry_flag", "inquiry_type", "inquiry_type_raw",
    "need_signal_flag", "need_signal_type", "need_signal_type_raw", "entity_role",
    "tee_time_score", "tee_time_evidence", "tee_effort_score", "tee_effort_evidence",
    "tee_emotion_score", "tee_emotion_evidence", "tee_success_score",
    "tee_success_evidence", "tee_summary", "rootcause_problem", "rootcause_target",
    "rootcause_cause", "rootcause_summary", "rootcause_score", "confidence_rating",
    "voc_total_score", "confidence_topic", "confidence_cej", "confidence_inquiry",
    "confidence_need_signal", "confidence_entity_role", "confidence_score",
    "source_context_summary", "trace_summary", "status", "review_required",
    "scope_exclusion_reason", "proposal_flag", "video_id", "video_title", "video_url",
    "product_category", "product_category_source",
]

FLAG_Y = "Y"
FLAG_N = "N"
REFERENCE_BRAND = "LG"

CANONICAL_TOPICS = [
    "제품 전반", "제조사 신뢰/품질", "내구성/고장", "에러/오작동",
    "안전(화재·감전·누수)", "A/S·고객응대", "가격/가성비", "프로모션",
    "소모품/유지관리재", "설치/설치 편의성", "배송", "구독", "소음/진동",
    "디자인", "사용 편의성(조작)", "앱/스마트(원격제어)", "용량",
    "동선/주행", "주행/문턱돌파", "청소/흡입 성능", "장애물 회피", "물걸레",
    "스팀", "배터리", "먼지통/자동비움", "세척 성능", "건조 성능", "식기 수납",
    "위생/살균", "노즐/잔수", "누수/도어", "배수·부품", "세탁 성능",
    "탈수", "의류 냄새", "옷감 손상(구김/수축)", "냉각", "신선보관",
    "제빙/정수", "성에", "수납(선반·도어)", "구매의사/이탈",
    "기타(로봇청소기)", "기타(식기세척기)", "기타(세탁기)", "기타(냉장고)",
    "N/A", "미분류",
]

# R-C2-00: every output column belongs to exactly one ownership class.
ENGINE_OWNED_COLUMNS = {
    "source_id", "raw_row_index", "parent_voc_id", "comment_relation",
    "atomic_id", "atomic_index", "original_voc", "voc_cleaned", "voc_residual",
    "reference_brand", "confidence_rating", "voc_total_score", "proposal_flag",
    "video_id", "video_title", "video_url", "product_category",
    "product_category_source",
}

FREE_TEXT_COLUMNS = {
    column
    for column in TARGET_COLUMNS
    if column.endswith(("_evidence", "_summary", "_raw")) or column == "trace_summary"
}
FREE_TEXT_COLUMNS.add("topic_provisional")

LLM_JUDGED_COLUMNS = set(TARGET_COLUMNS) - ENGINE_OWNED_COLUMNS - FREE_TEXT_COLUMNS

assert ENGINE_OWNED_COLUMNS | LLM_JUDGED_COLUMNS | FREE_TEXT_COLUMNS == set(TARGET_COLUMNS)
assert not (ENGINE_OWNED_COLUMNS & LLM_JUDGED_COLUMNS)
assert not (ENGINE_OWNED_COLUMNS & FREE_TEXT_COLUMNS)
assert not (LLM_JUDGED_COLUMNS & FREE_TEXT_COLUMNS)

CEJ_VALUES = {
    "인지", "탐색", "결정", "구매", "배송", "사용준비", "사용", "관리", "교체", "해당없음",
}
ENTITY_ROLES = {"product_brand", "competitor_brand", "creator_channel", "unknown"}
CONFIDENCE_VALUES = {"Low", "Medium", "High", "Very High"}
STEP_CONFIDENCE_VALUES = {"Low", "Medium", "High"}
INQUIRY_TYPES = {
    "none", "feature_spec", "product_comparison", "product_identification",
    "installation_fit", "usage_environment_fit", "promotion_benefit", "as_trust_quality",
    "review_request", "purchase_path_link", "other_question",
}
NEED_SIGNAL_TYPES = {
    "none", "feature_need", "price_value_need", "purchase_confidence_need",
    "conversion_signal", "problem_solution_need", "trust_safety_need",
    "content_information_need", "environment_fit_need", "purchase_path_need",
    "positive_message_candidate", "low_value",
}
STATUS_VALUES = {"normal", "review_required", "scope_excluded"}
SCOPE_EXCLUSION_REASON_VALUES = {
    "empty", "operator_notice", "channel_request", "channel_feedback",
    "out_of_scope_product", "no_analytic_value", "unresolvable_reply",
}
PRODUCT_CATEGORY_VALUES = {"로봇청소기", "식기세척기", "세탁기", "건조기", "냉장고", "기타"}
PRODUCT_CATEGORY_SOURCE_VALUES = {"text", "parent", "video"}
PROPOSAL_FLAG_VALUES = {"engine_llm", "engine_pre_llm_exclusion", "cowork_proposal"}

TOPIC_VALUES = set(CANONICAL_TOPICS)

ENUM_COLUMNS: dict[str, set[str]] = {
    "cej": CEJ_VALUES,
    "entity_role": ENTITY_ROLES,
    "status": STATUS_VALUES,
    "scope_exclusion_reason": SCOPE_EXCLUSION_REASON_VALUES,
    "product_category": PRODUCT_CATEGORY_VALUES,
    "product_category_source": PRODUCT_CATEGORY_SOURCE_VALUES,
    "inquiry_type": INQUIRY_TYPES,
    "need_signal_type": NEED_SIGNAL_TYPES,
    "inquiry_flag": {FLAG_Y, FLAG_N},
    "need_signal_flag": {FLAG_Y, FLAG_N},
    "review_required": {FLAG_Y, FLAG_N},
    "proposal_flag": PROPOSAL_FLAG_VALUES,
    "confidence_rating": CONFIDENCE_VALUES,
    "confidence_topic": STEP_CONFIDENCE_VALUES,
    "confidence_cej": STEP_CONFIDENCE_VALUES,
    "confidence_inquiry": STEP_CONFIDENCE_VALUES,
    "confidence_need_signal": STEP_CONFIDENCE_VALUES,
    "confidence_entity_role": STEP_CONFIDENCE_VALUES,
    "confidence_score": STEP_CONFIDENCE_VALUES,
    "reference_brand": {REFERENCE_BRAND},
    "topic": TOPIC_VALUES,
}

ENUM_SAFE_VALUES = {
    "cej": "해당없음",
    "entity_role": "unknown",
    "status": "review_required",
    "scope_exclusion_reason": "no_analytic_value",
    "product_category": "기타",
    "product_category_source": "text",
    "inquiry_type": "none",
    "need_signal_type": "none",
    "inquiry_flag": FLAG_N,
    "need_signal_flag": FLAG_N,
    "review_required": FLAG_Y,
    "proposal_flag": "engine_llm",
    "confidence_rating": "Low",
    "confidence_topic": "Low",
    "confidence_cej": "Low",
    "confidence_inquiry": "Low",
    "confidence_need_signal": "Low",
    "confidence_entity_role": "Low",
    "confidence_score": "Low",
    "reference_brand": REFERENCE_BRAND,
    "topic": "N/A",
}


def enum_prompt_block() -> str:
    """Render LLM-owned enum constraints from the single registry."""

    lines = ["[허용 값]"]
    for column in TARGET_COLUMNS:
        if column not in LLM_JUDGED_COLUMNS or column not in ENUM_COLUMNS:
            continue
        values = ", ".join(sorted(ENUM_COLUMNS[column]))
        lines.append(f"- {column}: {values}")
    return "\n".join(lines)


def _append_trace(row: MutableMapping[str, Any], message: str) -> None:
    existing = str(row.get("trace_summary") or "").strip()
    row["trace_summary"] = f"{existing}; {message}" if existing else message


def assert_column_contract(rows: Iterable[MutableMapping[str, Any]]) -> dict[str, int]:
    """Normalize final enum violations and print a complete per-column report."""

    counts = {column: 0 for column in ENUM_COLUMNS}
    for row in rows:
        for column, allowed in ENUM_COLUMNS.items():
            value = str(row.get(column) or "").strip()
            if column == "scope_exclusion_reason" and not value and str(row.get("status") or "").strip() != "scope_excluded":
                continue
            if value in allowed:
                continue
            safe_value = ENUM_SAFE_VALUES[column]
            row[column] = safe_value
            counts[column] += 1
            _append_trace(row, f"column_contract_normalized: {column}={value or '<blank>'}->{safe_value}")
    print(json.dumps({"column_contract": counts}, ensure_ascii=False, sort_keys=True), flush=True)
    return counts
