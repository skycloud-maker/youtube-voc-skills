"""Generate decision-ready topic insight + action outputs."""

from __future__ import annotations

import hashlib
import json
import logging

import pandas as pd

from .common import clamp, ensure_required_columns, parse_list, safe_text

logger = logging.getLogger(__name__)


INSIGHT_REQUIRED_COLUMNS = [
    "topic_id",
    "insight_text",
    "action_text",
    "priority_level",
    "evidence_strength",
    "supporting_comment_ids",
]

AXIS_LABEL = {
    "price_value_fit": "가격/가치 불일치",
    "installation_space_fit": "설치/공간 제약",
    "maintenance_burden": "유지관리 부담",
    "automation_convenience": "자동화 편의성",
    "durability_lifespan": "내구성/수명",
    "brand_trust": "브랜드 신뢰",
    "usage_pattern_fit": "사용 패턴 적합성",
    "comparison_substitute_judgment": "비교/대체 판단",
    "design_interior_fit": "디자인/인테리어 적합",
    "service_after_sales": "서비스/A/S",
    "purchase_strategy_contract": "구매 전략/계약",
    "repurchase_recommendation": "재구매/추천",
}

STAGE_LABEL = {
    "awareness": "인지",
    "exploration": "탐색",
    "purchase": "구매",
    "decision": "결정",
    "delivery": "배송",
    "onboarding": "사용준비",
    "usage": "사용",
    "maintenance": "관리",
    "replacement": "교체",
}

DOMAIN_BY_AXIS = {
    "price_value_fit": "가격 정책",
    "installation_space_fit": "설치/제품",
    "maintenance_burden": "운영/서비스",
    "automation_convenience": "UX",
    "durability_lifespan": "제품 신뢰",
    "brand_trust": "메시지/브랜드",
    "usage_pattern_fit": "제품 기획",
    "comparison_substitute_judgment": "메시지/포지셔닝",
    "design_interior_fit": "제품 디자인",
    "service_after_sales": "운영/서비스",
    "purchase_strategy_contract": "정책/계약",
    "repurchase_recommendation": "CRM/메시지",
}

ACTION_CATALOG = {
    "price_value_fit": [
        "가격 구성과 번들 구성을 재정비해 진입 장벽을 낮춥니다",
        "가격 대비 가치가 보이도록 등급별 비교 기준을 명확히 제시합니다",
    ],
    "installation_space_fit": [
        "설치 전 공간 적합성 체크와 시각 안내를 기본 프로세스로 적용합니다",
        "설치 제약과 호환 조건을 구매 전 단계에서 명확히 고지합니다",
    ],
    "maintenance_burden": [
        "청소/관리 과정을 단순화하고 리마인드 체계를 도입해 관리 부담을 줄입니다",
        "유지관리 단계의 주요 불편 프로세스를 재설계해 처리 시간을 단축합니다",
    ],
    "automation_convenience": [
        "초기 설정 단계를 줄여 도입 기능까지의 진입 시간을 단축합니다",
        "도입 UX 흐름에서 이탈을 유발하는 고마찰 단계를 제거합니다",
    ],
    "durability_lifespan": [
        "반복 고장 패턴을 우선순위로 분류해 개선 과제를 실행합니다",
        "고위험 부품 진단과 사전 점검 항목을 강화합니다",
    ],
    "brand_trust": [
        "신뢰를 흔드는 쟁점을 체계적 근거 기반 메시지로 보완합니다",
        "지원 채널과 마케팅 채널의 메시지 일관성을 재정렬합니다",
    ],
    "usage_pattern_fit": [
        "대상 사용 패턴에 맞춘 기본 기능 설정과 우선순위를 재배치합니다",
        "대표 사용 시나리오 기반으로 모드 추천 가이드를 제공합니다",
    ],
    "comparison_substitute_judgment": [
        "비교 구간에서 도입 우위 사인을 수치로 보이게 메시지를 재정비합니다",
        "대체 선택지와의 차이를 사용 시나리오 기준으로 명확히 제시합니다",
    ],
    "design_interior_fit": [
        "요청 빈도가 높은 디자인 속성을 우선순위로 개선합니다",
        "구매 단계에서의 기대 불일치를 줄이도록 비주얼 선택지를 조정합니다",
    ],
    "service_after_sales": [
        "미해결 건에 대한 응답 SLA와 에스컬레이션 기준을 강화합니다",
        "서비스 운영 프로세스를 정비해 처리 리드타임을 단축합니다",
    ],
    "purchase_strategy_contract": [
        "계약 조건을 단순화해 구매 단계의 마찰을 줄입니다",
        "프로모션/할인 규칙을 재구성해 구매 판단의 명확성을 높입니다",
    ],
    "repurchase_recommendation": [
        "재구매 전환율을 위한 메시지 타이밍과 트리거를 정교화합니다",
        "긍정 반응을 실제 재구매로 이어지도록 전환 경로를 설계합니다",
    ],
}

CATEGORY_LABELS = {
    "dishwasher": "식기세척기",
    "washer": "세탁기",
    "dryer": "건조기",
    "refrigerator": "냉장고",
    "plant_care_device": "식물관리기",
    "coffee_machine": "커피머신",
    "air_conditioner": "에어컨",
    "vacuum_cleaner": "청소기",
    "unknown": "대상 미분류(분류 보강 필요)",
}


def validate_insight_action_schema(frame: pd.DataFrame) -> None:
    ensure_required_columns(frame, INSIGHT_REQUIRED_COLUMNS, "insight_action_generator")


def _priority(rank_score: float, negative_or_mixed_weight: float, insufficient: bool) -> str:
    if insufficient:
        return "monitor"
    if rank_score >= 72.0 and negative_or_mixed_weight >= 0.55:
        return "immediate_fix"
    if rank_score >= 42.0:
        return "short_term_improvement"
    return "monitor"


def _polarity_phrase(distribution_json: str) -> str:
    try:
        dist = json.loads(distribution_json or "{}")
    except Exception:
        dist = {}
    neg = float(dist.get("negative", 0.0))
    mixed = float(dist.get("mixed", 0.0))
    pos = float(dist.get("positive", 0.0))
    if neg >= 0.5:
        return "부정 반응이 우세합니다."
    if mixed >= 0.35:
        return "긍정과 부정이 공존하는 혼합 반응입니다."
    if pos >= 0.6:
        return "긍정 반응이 우세합니다."
    return "반응이 분산되어 추가 확인이 필요합니다."


def _parse_semantic_id(semantic_id: str) -> tuple[str, str]:
    text = safe_text(semantic_id)
    category = ""
    named = ""
    if "cat:" in text:
        category = safe_text(text.split("cat:", 1)[1].split("|", 1)[0]).lower()
    if "|name:" in text:
        named = safe_text(text.split("|name:", 1)[1].split("|", 1)[0]).lower()
    if category == "na":
        category = ""
    if named == "na":
        named = ""
    return category, named


def _resolve_action_target(
    semantic_id: str,
    *,
    scope_categories: set[str] | None = None,
) -> tuple[str, str]:
    category, named = _parse_semantic_id(semantic_id)
    normalized_scope = {safe_text(value).lower() for value in (scope_categories or set()) if safe_text(value)}

    if not category or category == "unknown":
        return CATEGORY_LABELS["unknown"], "unknown"
    if normalized_scope and category not in normalized_scope:
        return "현재 범위 외 대상(검증 필요)", "out_of_scope"
    if named:
        return named, "in_scope"
    return CATEGORY_LABELS.get(category, category), "in_scope"


def _pick_variant(topic_id: str, options: list[str]) -> str:
    if not options:
        return "핵심 개선 과제를 우선 정의합니다"
    digest = hashlib.sha1(topic_id.encode("utf-8")).hexdigest()
    idx = int(digest[:4], 16) % len(options)
    return options[idx]


def _insight_sentence(
    topic_id: str,
    *,
    stage_label: str,
    axis_label: str,
    coverage_pct: float,
    frequency_count: int,
    polarity_phrase: str,
) -> str:
    templates = [
        f"{stage_label} 단계에서 {axis_label} 이슈가 반복적으로 관찰됩니다 (비중 {coverage_pct:.1f}%, 근거 {frequency_count:,}건). {polarity_phrase}",
        f"{axis_label} 관련 반응이 {stage_label} 구간에서 집중되어 나타납니다 (근거 {frequency_count:,}건, 비중 {coverage_pct:.1f}%). {polarity_phrase}",
        f"{stage_label} 과정에서 {axis_label} 이슈가 유의미한 비중으로 확인됩니다 (비중 {coverage_pct:.1f}%, 근거 {frequency_count:,}건). {polarity_phrase}",
    ]
    digest = hashlib.sha1((topic_id + "|insight").encode("utf-8")).hexdigest()
    idx = int(digest[:4], 16) % len(templates)
    return templates[idx]


def _action_sentence(topic_id: str, *, target: str, action_base: str, domain: str, cautious: bool) -> str:
    if cautious:
        return f"{target} 이슈는 현재 범위에서 대상 정합성 확인이 필요해, {domain} 관점의 추가 검증 과제로 우선 관리합니다."
    templates = [
        f"{target} 대상에서는 {domain} 영역의 우선 과제로 '{action_base}'를 즉시 실행해야 합니다.",
        f"{target} 이슈를 줄이기 위해 {domain} 측면에서 '{action_base}'를 먼저 집행해야 합니다.",
        f"{target} 고객경험 개선을 위해 {domain} 축의 핵심 조치로 '{action_base}'를 바로 추진해야 합니다.",
    ]
    digest = hashlib.sha1((topic_id + "|action").encode("utf-8")).hexdigest()
    idx = int(digest[:4], 16) % len(templates)
    return templates[idx]


def generate_insight_actions(
    topic_ranked: pd.DataFrame,
    topics: pd.DataFrame,
    topic_representatives: pd.DataFrame,
    *,
    scope_categories: set[str] | None = None,
) -> pd.DataFrame:
    ensure_required_columns(
        topic_ranked,
        [
            "topic_id",
            "frequency_count",
            "coverage_pct",
            "polarity_distribution",
            "negative_or_mixed_weight",
            "importance_signal",
            "rank_score",
            "insufficient_evidence",
        ],
        "insight_action_input_ranked",
    )
    ensure_required_columns(
        topics,
        ["topic_id", "journey_stage", "judgment_axis", "product_semantic_id"],
        "insight_action_input_topics",
    )
    ensure_required_columns(
        topic_representatives,
        ["topic_id", "representative_comment_ids", "alignment_score"],
        "insight_action_input_representatives",
    )

    merged = topic_ranked.merge(topics, on="topic_id", how="left").merge(topic_representatives, on="topic_id", how="left")
    rows: list[dict] = []

    for _, row in merged.iterrows():
        topic_id = safe_text(row.get("topic_id"))
        journey_stage = safe_text(row.get("journey_stage"))
        judgment_axis = safe_text(row.get("judgment_axis"))
        stage_label = STAGE_LABEL.get(journey_stage, journey_stage or "unspecified_stage")
        axis_label = AXIS_LABEL.get(judgment_axis, judgment_axis or "unspecified_issue")
        coverage_pct = float(pd.to_numeric(row.get("coverage_pct", 0.0), errors="coerce") or 0.0)
        frequency_count = int(pd.to_numeric(row.get("frequency_count", 0), errors="coerce") or 0)
        rank_score = float(pd.to_numeric(row.get("rank_score", 0.0), errors="coerce") or 0.0)
        importance_signal = float(pd.to_numeric(row.get("importance_signal", 0.0), errors="coerce") or 0.0)
        negative_or_mixed_weight = float(pd.to_numeric(row.get("negative_or_mixed_weight", 0.0), errors="coerce") or 0.0)
        insufficient = bool(row.get("insufficient_evidence", False))

        target, target_status = _resolve_action_target(
            safe_text(row.get("product_semantic_id")),
            scope_categories=scope_categories,
        )
        domain = DOMAIN_BY_AXIS.get(judgment_axis, "product")
        action_base = _pick_variant(topic_id, ACTION_CATALOG.get(judgment_axis, []))

        polarity_phrase = _polarity_phrase(safe_text(row.get("polarity_distribution")))
        insight_text = _insight_sentence(
            topic_id,
            stage_label=stage_label,
            axis_label=axis_label,
            coverage_pct=coverage_pct,
            frequency_count=frequency_count,
            polarity_phrase=polarity_phrase,
        )
        action_text = _action_sentence(
            topic_id,
            target=target,
            action_base=action_base,
            domain=domain,
            cautious=(target_status != "in_scope"),
        )
        priority_level = _priority(rank_score, negative_or_mixed_weight, insufficient)
        if target_status != "in_scope":
            priority_level = "monitor"

        rep_ids_raw = row.get("representative_comment_ids", [])
        rep_ids = parse_list(rep_ids_raw)
        evidence_strength = clamp(
            (0.7 * importance_signal) + (0.3 * float(pd.to_numeric(row.get("alignment_score", 0.0), errors="coerce") or 0.0)),
            0.0,
            1.0,
        )
        if insufficient:
            evidence_strength = min(evidence_strength, 0.49)

        rows.append(
            {
                "topic_id": topic_id,
                "insight_text": insight_text,
                "action_text": action_text,
                "priority_level": priority_level,
                "evidence_strength": round(float(evidence_strength), 6),
                "supporting_comment_ids": rep_ids,
                "action_target": target,
                "action_target_status": target_status,
            }
        )

    output = pd.DataFrame(rows).sort_values("evidence_strength", ascending=False).reset_index(drop=True)
    validate_insight_action_schema(output)
    logger.info("[v5][insight_action_generator] rows=%s", len(output))
    return output
