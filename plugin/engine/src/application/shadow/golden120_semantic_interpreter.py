"""First-pass Golden120 semantic interpreter for sidecar preview cards.

This is intentionally modest: it is not an LLM and does not claim final human
truth.  It applies the high-confidence Golden120 boundary cases that have
already been reviewed so the dashboard preview stops rendering every weak
legacy projection as "appliance / unknown / other".
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.application.shadow.semantic_card_contract import (
    GENERIC_PRODUCT_LABELS,
    SEMANTIC_INTERPRETER_CARD_SOURCE,
    UNKNOWN_FEATURE_TOPIC_LABELS,
)

INTERPRETER_VERSION = "golden120_rule_heuristic_v0"


def enhance_golden120_card_with_semantic_rules(
    *,
    record: Mapping[str, Any],
    card: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay high-confidence Golden120 semantic fields onto a base card."""

    enhanced = dict(card)
    text = _context_text(record, enhanced)
    rule = _match_high_confidence_rule(text)
    if rule:
        _apply_rule(enhanced, rule)
        _finalize_display_fields(enhanced, text)
        enhanced["card_source"] = SEMANTIC_INTERPRETER_CARD_SOURCE
        enhanced["interpreter_status"] = INTERPRETER_VERSION
        enhanced["semantic_rule_id"] = rule["rule_id"]
        enhanced["needs_human_review"] = bool(rule.get("needs_human_review", False))
        enhanced["confidence_notes"] = list(rule.get("confidence_notes", ()))
        return enhanced

    before = _semantic_quality_tuple(enhanced)
    _apply_lightweight_general_resolvers(enhanced, text)
    _finalize_display_fields(enhanced, text)
    after = _semantic_quality_tuple(enhanced)
    if before == after or _is_still_projection_quality(enhanced):
        return enhanced
    enhanced["card_source"] = SEMANTIC_INTERPRETER_CARD_SOURCE
    enhanced["interpreter_status"] = f"{INTERPRETER_VERSION}_general"
    return enhanced


def _context_text(record: Mapping[str, Any], card: Mapping[str, Any]) -> str:
    fields = [
        card.get("atomic_voc"),
        card.get("evidence_span"),
        record.get("opinion_text"),
        record.get("comment_text"),
        record.get("text_display"),
        record.get("cleaned_text"),
        record.get("parent_comment_text"),
        record.get("parent_text"),
        record.get("reply_context"),
        record.get("video_title"),
        record.get("title"),
        record.get("source_product"),
    ]
    return " ".join(str(value) for value in fields if value).strip()


def _match_high_confidence_rule(text: str) -> dict[str, Any] | None:
    normalized = text.replace(" ", "")
    if "제휴카드" in text and ("190만원" in text or "구매링크" in text or "프로모션" in text):
        return _rule(
            "robot_vacuum_affiliate_price_benefit",
            product_label="로봇청소기",
            product_group_label="로봇청소기",
            product_detail="LG 홈봇 로니 · 직배수 · 제휴카드 할인/프로모션 가격",
            product_detail_basis="원문에 '엘지 홈봇 로니', '직배수', '제휴카드 할인', '190만원 초반대'가 함께 언급됨",
            feature_topic="구매/가격/혜택 조건",
            feature_topic_label="구매/가격/혜택 조건",
            feature_topic_description="구매 희망자에게 제휴카드 할인과 프로모션 가격 조건을 안내하는 댓글",
            atomic_voc=text,
            evidence_span=_evidence_slice(text, ("제휴카드", "190만원", "프로모션", "구매링크")),
            cej_stage="구매",
            cej_basis="구매링크, 제휴카드 할인, 190만원 초반대 프로모션 가격 언급으로 구매 조건 확인 맥락",
            cej_status="semantic_rule_applied",
            tees_success_value="N/A",
            tees_time_value="N/A",
            tees_effort_value="N/A",
            tees_emotion_value="N/A",
            root_cause_maturity="N/A",
            root_cause_category="None",
            root_cause_basis="구체 문제나 원인 후보가 아니라 가격/혜택 정보 제공 맥락",
            root_problem_level="N/A",
            root_problem_label="문제 미식별",
            root_problem_target="",
            root_cause_confidence_label="N/A",
            improvement_hints=[],
            internal_operation_notes=[],
            summary="로봇청소기 구매 검토자에게 제휴카드 할인과 프로모션 가격 조건을 안내하는 구매 단계 정보성 VoC입니다.",
            polarity_label="inquiry",
            polarity_basis="가격/혜택 조건을 확인·안내하는 구매 정보 맥락",
        )
    if ("사도" in text and "되나요" in text) or normalized in {"사도되나요~?!", "사도되나요?!", "사도되나요"} or text.strip() in {"사도 되나요~?!", "사도 되나요?!"}:
        return _rule(
            "robot_vacuum_simple_purchase_availability_question",
            product_label="로봇청소기",
            product_group_label="로봇청소기",
            product_detail="로봇청소기 구매 가능 여부 문의",
            product_detail_basis="원문 '사도 되나요~?!'와 영상/source context로 로봇청소기 맥락을 보정",
            feature_topic="단순 구매 가능 여부 문의",
            feature_topic_label="단순 구매 가능 여부 문의",
            feature_topic_description="구체적 제품 경험이나 개선 신호 없이 구매 가능 여부만 확인하는 짧은 문의",
            atomic_voc=text,
            evidence_span=text,
            cej_stage="구매",
            cej_basis="사도 되는지 묻는 구매 가능 여부 확인 표현",
            scope_status="low_value_inquiry",
            na_status="scope_excluded",
            na_reason="작성자 의도나 제품 개선 신호가 거의 없는 단순 구매 가능 여부 문의",
            tees_success_value="N/A",
            tees_time_value="N/A",
            tees_effort_value="N/A",
            tees_emotion_value="N/A",
            root_cause_maturity="N/A",
            root_cause_category="None",
            root_cause_basis="제품/서비스 문제 또는 원인 후보가 식별되지 않음",
            root_problem_level="N/A",
            root_problem_label="문제 미식별",
            root_problem_target="",
            root_cause_confidence_label="N/A",
            improvement_hints=[],
            internal_operation_notes=["문의/정보접근 탭 또는 low-value inquiry로 분리"],
            summary="단순히 구매 가능 여부만 묻는 짧은 문의로, 메인 전략 VoC보다는 문의/정보접근 후보로 분리하는 것이 적합합니다.",
            polarity_label="inquiry",
            polarity_basis="단순 구매 가능 여부 문의",
            needs_human_review=False,
        )
    if "삼성 로보락" in text and ("비교" in text or "뭐가 더 좋" in text):
        return _rule(
            "robot_vacuum_brand_comparison_inquiry",
            product_label="로봇청소기",
            product_group_label="로봇청소기",
            product_detail="삼성·로보락 비교 문의",
            product_detail_basis="원문에 '삼성 로보락과 비교'가 직접 언급됨",
            feature_topic="제품 전반 사용 경험 비교 문의",
            feature_topic_label="제품 전반 사용 경험 비교 문의",
            feature_topic_description="타 브랜드/제품과 비교해 어떤 제품 경험이 더 나은지 묻는 탐색형 문의",
            atomic_voc=text,
            evidence_span="삼성 로보락과 비교해서 뭐가 더 좋을까요",
            cej_stage="탐색",
            cej_basis="타 브랜드와 비교해 더 좋은 선택을 묻는 구매 전 탐색 맥락",
            tees_success_value="N/A",
            tees_time_value="N/A",
            tees_effort_value="N/A",
            tees_emotion_value="N/A",
            tees_emotion_basis="단순 비교 문의이며 댓글 작성자의 만족 감정으로 볼 직접 근거 없음",
            root_cause_maturity="N/A",
            root_cause_category="None",
            root_cause_basis="제품 문제나 원인 후보가 아니라 비교 정보 탐색",
            root_problem_level="N/A",
            root_problem_label="문제 미식별",
            root_problem_target="",
            root_cause_confidence_label="N/A",
            improvement_hints=[],
            internal_operation_notes=["문의/정보접근 인사이트 탭에서 비교 문의 군집으로 관리"],
            summary="로봇청소기를 삼성/로보락 등 타 제품과 비교해 어떤 선택이 더 나은지 묻는 탐색형 문의입니다.",
            polarity_label="inquiry",
            polarity_basis="정보 비교 요청이며 긍정/부정 감정 신호는 아님",
        )
    if "흡입구" in text and ("결착" in text or "덮개" in text):
        return _rule(
            "robot_vacuum_inlet_cover_fit_issue",
            product_label="로봇청소기",
            product_group_label="로봇청소기",
            product_detail="흡입구 덮개 결착 문제",
            product_detail_basis="원문에 '흡입구덮개 결착문제'가 직접 언급됨",
            feature_topic="흡입구 덮개 결착 문제",
            feature_topic_label="흡입구 덮개 결착 문제",
            feature_topic_description="제품 사용 중 관측될 수 있는 흡입구 덮개 결착 문제와 점검/A/S 우려",
            atomic_voc=text,
            evidence_span=_evidence_slice(text, ("흡입구", "결착", "점검", "무섭")),
            cej_stage="사용 + 관리",
            cej_basis="흡입구 덮개 결착 문제는 사용 중 제품 문제이면서 판매 후 점검/A/S 관리 이슈로도 연결됨",
            tees_success_value="N/A",
            tees_time_value="N/A",
            tees_effort_value="N/A",
            tees_emotion_value="frustration/anxiety",
            tees_emotion_basis="벌써 점검가기 무섭다는 표현에서 제품/관리 맥락의 불안·우려가 확인됨",
            root_cause_maturity="L2",
            root_cause_category="불명확",
            root_cause_basis="흡입구 덮개 결착이라는 개선 대상은 명확하지만 원인은 특정되지 않음",
            root_problem_level="L2",
            root_problem_label="문제 특정",
            root_problem_target="흡입구 덮개 결착",
            root_cause_confidence_label="중간",
            improvement_hints=[
                "흡입구 덮개 결착 구조 점검",
                "판매 후 점검/A/S 대응 가이드 검토",
            ],
            internal_operation_notes=["실제 케어매니저라면 온라인 자사 제품 언급 가이드 검토"],
            summary="로봇청소기 흡입구 덮개 결착 문제를 보고 점검/A/S가 걱정된다는 사용+관리 경계의 개선 후보 VoC입니다.",
            polarity_label="negative_concern",
            polarity_basis="제품 결착 문제와 점검 우려가 함께 드러남",
        )
    if all(token in text for token in ("통돌이", "드럼")) and any(token in text for token in ("쿵덕", "먼지", "엉키", "신세계")):
        return _rule(
            "laundry_topload_vs_drum",
            product_label="통돌이 / 드럼 세탁기",
            feature_topic="통돌이 소음·먼지·엉킴 vs 드럼 만족",
            atomic_voc="통돌이는 쿵덕거림·먼지·엉킴이 있지 않냐고 묻고, 드럼은 신세계였다고 평가",
            cej_stage="사용",
            tees_success_value="달성",
            tees_success_basis="드럼이 신세계였다는 직접 만족 표현",
            tees_emotion_value="surprise/positive for drum",
            tees_emotion_basis="드럼이 신세계라는 긍정적 놀람/만족 표현",
            root_cause_maturity="possible",
            root_cause_category="사용성/성능 인식",
            root_cause_basis="통돌이의 쿵덕거림·먼지·엉킴을 불만/우려 원인 후보로 언급",
            root_problem_level="L2",
            root_problem_label="문제 특정",
            root_problem_target="통돌이 소음·먼지·엉킴",
            summary="통돌이 사용성 우려와 드럼 만족을 비교하는 사용 경험성 댓글.",
        )
    if "뭐옷을하루에세벌" in normalized or ("세 벌" in text and "갈아입" in text):
        return _rule(
            "other_person_usage_habit_blame",
            product_label="N/A — 타인의 세탁물 양/행동에 대한 비꼼",
            feature_topic="옷을 자주 갈아입는 행동 비난",
            atomic_voc="상대가 옷을 하루에 세 벌씩 갈아입느냐고 비꼼",
            cej_stage="N/A",
            scope_status="watch",
            watch_agenda_flags=["타인행동비난-제외 Watch"],
            tees_success_value="N/A",
            tees_time_value="N/A",
            tees_effort_value="N/A",
            tees_emotion_value="N/A",
            root_cause_maturity="unknown",
            root_cause_category="None",
            root_cause_basis="제품 기능보다 타인의 사용 습관/행동 비난에 가까움",
            summary="제품 기능 평가보다 타인의 사용 습관/행동 비난에 가까워 Watch 증거로 둔다.",
            needs_human_review=True,
            confidence_notes=["Watch 축적: 타인행동비난-제외"],
        )
    if "세탁소비전력" in normalized:
        return _rule(
            "combo_power_measurement_question",
            product_label="일체형 세탁건조기",
            feature_topic="세탁 소비전력 측정 범위",
            atomic_voc="세탁 소비전력이 전체 소비전력인지 건조만 해당하는지 문의",
            cej_stage="탐색",
            tees_success_value="N/A",
            root_cause_maturity="unknown",
            root_cause_category="None",
            root_cause_basis="정보 탐색 질문이며 제품 결함 원인으로 단정할 근거 없음",
            summary="일체형 세탁건조기 소비전력 측정 범위를 묻는 정보 탐색.",
        )
    if "저항150" in normalized:
        return _rule(
            "washer_repair_resistor_theory",
            product_label="세탁기 수리/전기 부품",
            feature_topic="저항 150으로 맞추기 위한 회로 이론",
            atomic_voc="저항을 150으로 맞추려고 엮은 것이 맞는 이론인지 문의",
            cej_stage="탐색/관리 경계",
            scope_status="conditional",
            root_cause_maturity="unknown",
            root_cause_category="None",
            root_cause_basis="수리 성공과 직접 연결되는지 불명확하여 원인 단정 금지",
            summary="세탁기 수리 영상의 전기 부품 이론을 묻는 기술적 문의.",
            needs_human_review=True,
            confidence_notes=["수리 맥락인지 순수 전기 이론 호기심인지 확인 필요"],
        )
    if "628" in text and "키친핏" in text:
        return _rule(
            "refrigerator_kitchenfit_capacity",
            product_label="냉장고 628L 키친핏",
            feature_topic="628L 키친핏 제품/크기 의미",
            atomic_voc="628L 키친핏 제품이라는 뜻인지, 키친핏 크기라는 뜻인지 헷갈린다고 문의",
            cej_stage="탐색",
            tees_emotion_value="confusion",
            tees_emotion_basis="잘 모르겠다는 혼동 표현",
            root_cause_maturity="unknown",
            root_cause_category="정보 접근성/표현 명확성",
            root_cause_basis="용량과 키친핏 표현의 의미가 헷갈린다는 정보 접근성 단서",
            summary="냉장고 용량과 키친핏 표현의 의미를 묻는 구매 전 사양 탐색.",
        )
    if "고장" in text and "케바케" in text and ("안나" in normalized or "안나던데" in normalized):
        return _rule(
            "refrigerator_no_failure_case_by_case",
            product_label="냉장고 / 삼성·LG 브랜드 비교",
            feature_topic="고장 경험과 케바케 인식",
            atomic_voc="본인은 고장이 안 났으며 고장 여부는 케이스마다 다르다고 응답",
            cej_stage="사용",
            tees_success_value="달성/문제 없음",
            tees_success_basis="전 고장 안 나던데라는 직접 사용 경험",
            root_cause_maturity="unknown",
            root_cause_category="None",
            root_cause_basis="본인 경험 공유이며 원인 후보는 특정되지 않음",
            summary="브랜드/서비스 대화 중 본인 냉장고 고장 없음 경험을 제시.",
        )
    if "패킹젤" in normalized or "패킹 젤" in text:
        return _rule(
            "washer_packing_gel_question",
            product_label="세탁기 패킹젤",
            feature_topic="세탁기 패킹젤 존재와 성분",
            atomic_voc="패킹젤이라는 제품이 있는지, 어떤 성분인지 문의",
            cej_stage="탐색/관리 경계",
            root_cause_maturity="unknown",
            root_cause_category="None",
            root_cause_basis="관리 소모품 정보 탐색이며 결함 원인 단정 근거 없음",
            summary="세탁기 패킹 청소용 젤의 존재와 성분을 묻는 관리 정보 탐색.",
        )
    if ("국민카드" in text and "롯데카드" in text) or "주문할려고" in normalized or "주문하려고" in normalized:
        return _rule(
            "refrigerator_card_discount_purchase_blocker",
            product_label="냉장고",
            feature_topic="카드 할인 조건과 주문 가능성",
            atomic_voc="국민카드 할인은 안 되고 롯데카드만 할인되는지, 주문하려 했다고 문의",
            cej_stage="구매",
            tees_success_value="미달성 가능 + 해결 여부 불명확",
            tees_success_basis="주문하려 했지만 카드 할인 조건 때문에 막힌 정황",
            tees_emotion_value="disappointment",
            tees_emotion_basis="ㅜㅜ 표현",
            root_cause_maturity="unknown",
            root_cause_category="정보 접근성/구매 조건",
            root_cause_basis="카드 할인 조건 확인 이슈이며 제품 결함 원인은 아님",
            root_problem_level="L2",
            root_problem_label="문제 특정",
            root_problem_target="카드 할인 조건/주문 가능성",
            summary="냉장고 구매 과정에서 카드 할인 조건 때문에 주문 가능성을 묻는 구매 단계 VoC.",
        )
    if "귀곰" in text and "세척력" in text and "드럼" in text:
        return _rule(
            "washer_cleaning_performance_conflict",
            product_label="드럼 / 통돌이 세탁기",
            feature_topic="드럼 세탁기 세척력 검증 결과와 영상 주장 충돌",
            atomic_voc="다른 채널에서 드럼 세탁기가 세척력이 더 좋다고 증명됐는데 왜 다른지 반문",
            cej_stage="탐색/인지",
            tees_emotion_value="confusion/challenge",
            tees_emotion_basis="뭐죠???라는 혼동/반문 표현",
            root_cause_maturity="unknown",
            root_cause_category="None",
            root_cause_basis="외부 정보와 비교하는 탐색 반응이며 제품 결함 원인 단정 근거 없음",
            summary="세탁기 세척력 비교 정보가 채널별로 충돌하는 데 대한 탐색 단계 반응.",
        )
    if "10벌" in text and "20벌" in text and ("티 두 장" in text or "티두장" in normalized):
        return _rule(
            "washer_real_load_experiment_condition",
            product_label="드럼 / 통돌이 세탁기",
            feature_topic="실생활 세탁물 양에서의 세척력 실험 조건",
            atomic_voc="10~20벌 또는 15벌 등 실생활 세탁물 양으로 세척력 실험을 해야 한다고 지적",
            cej_stage="탐색/사용 경계",
            tees_emotion_value="criticism",
            tees_emotion_basis="실험 조건이 현실과 다르다는 비판적 표현",
            root_cause_maturity="possible",
            root_cause_category="실사용 조건/성능 검증",
            root_cause_basis="실생활 부하 조건에서 드럼 세척력 저하 가능성을 제기",
            root_problem_level="L2",
            root_problem_label="문제 특정",
            root_problem_target="실생활 세탁물 양 실험 조건",
            summary="실생활 세탁물 양을 반영한 세척력 비교를 요구하는 다중 Atomic VoC.",
        )
    return None


def _rule(rule_id: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "rule_id": rule_id,
        "tees_time_value": "N/A",
        "tees_time_basis": "직접 확인된 시간 경험 표현 없음",
        "tees_effort_value": "N/A",
        "tees_effort_basis": "직접 확인된 사용/관리 수고 표현 없음",
        "tees_success_value": "N/A",
        "tees_success_basis": "목적 달성 여부 직접 확인 어려움",
        "tees_emotion_value": "N/A",
        "tees_emotion_basis": "제품/CEJ 맥락 감정 직접 표현 없음",
        "scope_status": "in_scope_candidate",
        "watch_agenda_flags": [],
        "product_confidence": "medium",
        "product_basis": "Golden120 reviewed rule/heuristic match",
        "feature_topic_basis": "원문 의미 기반 rule/heuristic match",
        "cej_basis": "Golden120 reviewed CEJ boundary match",
        "root_problem_level": "N/A",
        "root_problem_label": "문제 미식별",
        "root_problem_target": "",
        "root_cause_confidence_label": "N/A",
    }
    payload.update(fields)
    return payload


def _evidence_slice(text: str, markers: tuple[str, ...]) -> str:
    if not text:
        return ""
    positions = [text.find(marker) for marker in markers if marker and marker in text]
    if not positions:
        return text
    start = max(0, min(positions) - 18)
    end = min(len(text), max(positions) + 80)
    return text[start:end].strip()


def _apply_rule(card: dict[str, Any], rule: Mapping[str, Any]) -> None:
    for key, value in rule.items():
        if key in {"rule_id", "needs_human_review", "confidence_notes"}:
            continue
        card[key] = value
    if "product_label" in rule:
        card["product"] = rule["product_label"]
    if "cej_stage" in rule:
        card["cej_status"] = "semantic_rule_applied"
        cej = dict(card.get("cej", {}))
        cej["experience_stage"] = rule["cej_stage"]
        card["cej"] = cej
    card["root_cause"] = {
        **dict(card.get("root_cause", {})),
        "maturity": rule.get("root_cause_maturity", card.get("root_cause_maturity", "")),
        "cause_category": rule.get("root_cause_category", card.get("root_cause_category", "")),
        "hypothesis_text": rule.get("root_cause_basis", card.get("root_cause_basis", "")),
    }


def _apply_lightweight_general_resolvers(card: dict[str, Any], text: str) -> None:
    product = str(card.get("product_label", "")).strip().lower()
    if product in GENERIC_PRODUCT_LABELS:
        resolved = _resolve_general_product(text)
        if resolved:
            card["product_label"] = resolved
            card["product"] = resolved
            card["product_basis"] = "원문/상위 context 제품명 keyword 기반 보정"
            card["product_confidence"] = "medium"
    _demote_unsupported_generic_feature_topic(card, text)
    topic = str(card.get("feature_topic", "")).strip().lower()
    if topic in UNKNOWN_FEATURE_TOPIC_LABELS and not card.get("feature_topic_broad_default_demoted"):
        resolved_topic = _resolve_general_topic(text)
        if resolved_topic:
            card["feature_topic"] = resolved_topic
            card["feature_topic_basis"] = "원문 의미 keyword 기반 보정"
    if card.get("cej_stage") in {"", "미확정", "기타"}:
        cej = _resolve_general_cej(text)
        if cej:
            card["cej_stage"] = cej
            card["cej_status"] = "heuristic_candidate"
            card["cej_basis"] = "원문 목적/행동 keyword 기반 후보"
            cej_payload = dict(card.get("cej", {}))
            cej_payload["experience_stage"] = cej
            card["cej"] = cej_payload
    if card.get("summary", "").startswith("현재 카드는 legacy projection"):
        card["summary"] = _general_summary(card, text)


def _demote_unsupported_generic_feature_topic(card: dict[str, Any], text: str) -> None:
    """Do not keep broad legacy feature buckets without direct text support."""

    topic = str(card.get("feature_topic", "")).strip()
    if topic != "청소/관리/소모품":
        return
    if _text_supports_cleaning_management_topic(text):
        return
    card["feature_topic"] = "미확인"
    card["feature_topic_label"] = "미확인"
    card["feature_topic_description"] = "원문만으로 기능/주제가 특정되지 않아 context 확인 또는 semantic interpreter 판단이 필요합니다."
    card["feature_topic_basis"] = "legacy broad topic이지만 원문에 청소/관리/소모품 직접 근거가 없어 미확정으로 되돌림"
    card["feature_topic_broad_default_demoted"] = True
    card["na_status"] = "engine_missed_or_context_needed"
    card["na_reason"] = "기능/주제 broad default를 신뢰할 수 없어 true N/A와 엔진 미포착을 구분해야 합니다."
    card["needs_human_review"] = True
    notes = list(card.get("confidence_notes", []) or [])
    if "기능/주제 broad default 검수 필요" not in notes:
        notes.append("기능/주제 broad default 검수 필요")
    card["confidence_notes"] = notes


def _text_supports_cleaning_management_topic(text: str) -> bool:
    normalized = str(text or "").replace(" ", "").lower()
    normalized_without_product_name = (
        normalized.replace("로봇청소기", "")
        .replace("로보청소기", "")
        .replace("청소기", "")
        .replace("robotvacuum", "")
        .replace("vacuumcleaner", "")
    )
    direct_markers = (
        "세제",
        "소모품",
        "패킹",
        "필터",
        "먼지통",
        "브러시",
        "브러쉬",
        "물걸레",
        "걸레",
        "흡입구",
        "관리",
        "세척",
        "a/s",
        "as",
    )
    if any(marker.replace(" ", "").lower() in normalized_without_product_name for marker in direct_markers):
        return True
    return "청소" in normalized_without_product_name


def _resolve_general_product(text: str) -> str:
    product_keywords = (
        ("식기세척기", ("식기세척", "식세기")),
        ("세탁기", ("세탁기", "통돌이", "드럼")),
        ("건조기", ("건조기",)),
        ("일체형 세탁건조기", ("워시타워", "세탁건조", "콤보")),
        ("냉장고", ("냉장고", "키친핏")),
        ("로봇청소기", ("로봇청소기", "로청")),
    )
    for label, keywords in product_keywords:
        if any(keyword in text for keyword in keywords):
            return label
    return ""


def _resolve_general_topic(text: str) -> str:
    robot_vacuum_specific_topics = (
        (
            "제조사 신뢰·보안·품질 우려",
            ("중국 제조사", "중국제조사", "국내 제조", "국내제조", "보안", "picae", "제조도 중요"),
        ),
        (
            "스팀 청소 제외구역/부분 설정 문의",
            ("스팀", "타일맵", "매트", "부분 설정", "부분설정", "스팀을 안하게"),
        ),
        (
            "청소 방식/운영 방식 문의",
            ("몇분 들고", "하는식", "청소를 하게", "되는 걸까요", "되는걸까요"),
        ),
    )
    for label, keywords in robot_vacuum_specific_topics:
        if any(keyword in text for keyword in keywords):
            return label

    topic_keywords = (
        ("구매/가격/혜택 조건", ("가격", "할인", "카드", "구매", "주문", "혜택")),
        ("설치/사용 가능 여부", ("설치", "사용 가능", "가능한가", "되나요")),
        ("청소/관리/소모품", ("청소", "세제", "소모품", "패킹", "필터", "관리")),
        ("성능/효과 검증", ("성능", "세척력", "건조", "효과", "비교")),
        ("고장/수리/A/S", ("고장", "수리", "as", "a/s", "서비스")),
        ("사양/크기/스펙 정보", ("용량", "리터", "L", "스펙", "크기", "소비전력")),
    )
    for label, keywords in topic_keywords:
        if any(keyword in text for keyword in keywords):
            return label
    return ""


def _resolve_general_cej(text: str) -> str:
    normalized = text.replace(" ", "")
    if any(keyword in text for keyword in ("구매", "주문", "할인", "가격", "혜택")):
        return "구매"
    if any(keyword in text for keyword in ("제조사", "국내 제조", "중국 제조사", "보안", "품질 우려")):
        return "탐색"
    if any(keyword in normalized for keyword in ("인가요", "되나요", "될까요", "있을까요", "뭔가요", "궁금", "알려", "어떤", "걸까요")):
        return "탐색"
    if any(keyword in text for keyword in ("청소", "관리", "수리", "필터", "세제", "소모품", "A/S", "as")):
        return "관리"
    if any(keyword in text for keyword in ("사용", "써보", "만족", "고장 안", "좋네요", "신세계")):
        return "사용"
    return ""


def _finalize_display_fields(card: dict[str, Any], text: str) -> None:
    _apply_general_emotion_signal(card, text)
    _apply_card_polarity(card, text)
    if not card.get("unit_title"):
        card["unit_title"] = _derive_unit_title(card, text)


def _apply_general_emotion_signal(card: dict[str, Any], text: str) -> None:
    if str(card.get("polarity_label", "")).lower() in {"inquiry", "question"}:
        return
    current = str(card.get("tees_emotion_value", "")).strip()
    if current and current not in {"N/A", "직접 신호 없음", "미확인"}:
        return
    concern_markers = ("우려", "걱정", "불안", "찝찝", "의심", "함정", "좋지 않", "보안", "중국 제조사", "중국제조사")
    positive_markers = ("좋", "만족", "추천", "편하", "신세계", "최고", "기대")
    if any(marker in text for marker in concern_markers):
        card["tees_emotion_value"] = "anxiety/trust concern"
        card["tees_emotion_basis"] = "제품/제조사/보안 맥락에서 우려·신뢰 리스크 표현이 확인됨"
    elif any(marker in text for marker in positive_markers):
        card["tees_emotion_value"] = "positive/satisfaction"
        card["tees_emotion_basis"] = "제품/CEJ 맥락의 긍정 감정 표현이 확인됨"


def _apply_card_polarity(card: dict[str, Any], text: str) -> None:
    if card.get("polarity_label"):
        return
    emotion = str(card.get("tees_emotion_value", "")).lower()
    success = str(card.get("tees_success_value", "")).lower()
    if any(token in emotion for token in ("anxiety", "concern", "disappointment", "criticism", "frustration")):
        card["polarity_label"] = "negative_concern"
        card["polarity_basis"] = card.get("tees_emotion_basis", "제품/CEJ 맥락의 우려·불만 신호")
    elif any(token in emotion for token in ("positive", "satisfaction", "trust")) or "달성" in success:
        card["polarity_label"] = "positive"
        card["polarity_basis"] = card.get("tees_emotion_basis", "제품/CEJ 맥락의 긍정 신호")
    elif any(token in text for token in ("?", "궁금", "인가요", "되나요", "될까요", "있을까요", "걸까요")):
        card["polarity_label"] = "inquiry"
        card["polarity_basis"] = "정보 탐색/문의형 표현"
    else:
        card["polarity_label"] = "neutral"
        card["polarity_basis"] = "명확한 긍정/부정 감정 신호 없음"


def _derive_unit_title(card: Mapping[str, Any], text: str) -> str:
    topic = str(card.get("feature_topic", "")).strip()
    if topic and topic.lower() not in UNKNOWN_FEATURE_TOPIC_LABELS and topic not in {"청소/관리/소모품"}:
        return topic
    atomic = str(card.get("atomic_voc", "") or text).strip()
    if not atomic:
        return "Atomic VoC"
    compact = " ".join(atomic.split())
    if len(compact) <= 34:
        return compact
    return compact[:34].rstrip() + "…"


def _general_summary(card: Mapping[str, Any], text: str) -> str:
    product = card.get("product_label", "")
    topic = card.get("feature_topic", "")
    atomic = card.get("atomic_voc") or text[:120]
    return f"{product} 관련 {topic} VoC 후보: {atomic}"


def _is_still_projection_quality(card: Mapping[str, Any]) -> bool:
    product = str(card.get("product_label", "")).strip().lower()
    topic = str(card.get("feature_topic", "")).strip().lower()
    cej = str(card.get("cej_stage", "")).strip()
    return (
        product in GENERIC_PRODUCT_LABELS
        and topic in UNKNOWN_FEATURE_TOPIC_LABELS
        and cej in {"", "기타", "미확정"}
    )


def _semantic_quality_tuple(card: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(card.get("product_label", "")),
        str(card.get("feature_topic", "")),
        str(card.get("cej_stage", "")),
        str(card.get("summary", "")),
    )
