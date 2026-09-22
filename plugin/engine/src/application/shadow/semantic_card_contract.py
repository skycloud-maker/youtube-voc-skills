"""Golden120-style semantic card contract for dashboard preview artifacts.

The first production path that writes ``unit_analysis_cards.jsonl`` is still a
legacy projection.  This module makes the target contract explicit so the
projection can be replaced incrementally without changing the dashboard UI
shape every time the interpreter improves.
"""

from __future__ import annotations

from typing import Any

GOLDEN120_UNIT_CARD_SCHEMA_VERSION = "golden120-unit-card-v2"

GOLDEN120_UNIT_CARD_REQUIRED_FIELDS: tuple[str, ...] = (
    "case_id",
    "source_comment_id",
    "parent_comment_id",
    "comment_depth",
    "is_reply",
    "video_id",
    "video_title",
    "source_context_used",
    "semantic_context_payload",
    "source_context_summary",
    "semantic_prompt_version",
    "semantic_prompt_ready",
    "atomic_unit_id",
    "unit_index",
    "source_voc_index",
    "atomic_unit_index",
    "atomic_voc",
    "evidence_span",
    "product_label",
    "product_group_label",
    "product_detail",
    "product_basis",
    "product_detail_basis",
    "product_confidence",
    "feature_topic",
    "feature_topic_label",
    "feature_topic_description",
    "feature_topic_basis",
    "cej_stage",
    "cej_basis",
    "cej_status",
    "scope_status",
    "semantic_lane",
    "semantic_lane_reason",
    "na_status",
    "na_reason",
    "watch_agenda_flags",
    "tees_success_value",
    "tees_success_basis",
    "tees_time_value",
    "tees_time_basis",
    "tees_effort_value",
    "tees_effort_basis",
    "tees_emotion_value",
    "tees_emotion_basis",
    "root_cause_maturity",
    "root_cause_category",
    "root_cause_basis",
    "root_problem_level",
    "root_problem_label",
    "root_problem_target",
    "root_cause_confidence_label",
    "improvement_hints",
    "internal_operation_notes",
    "summary",
    "confidence_notes",
    "needs_human_review",
)

PROJECTION_CARD_SOURCE = "legacy_projection"
SEMANTIC_INTERPRETER_CARD_SOURCE = "golden120_semantic_interpreter"

GENERIC_PRODUCT_LABELS = frozenset({"", "미확인", "n/a", "na", "none", "unknown", "가전제품"})
UNKNOWN_FEATURE_TOPIC_LABELS = frozenset({"", "미확인", "n/a", "na", "none", "unknown"})


GOLDEN120_REGRESSION_EXAMPLES: tuple[dict[str, Any], ...] = (
    {
        "id": "regression_laundry_topload_vs_drum",
        "comment": "헉 통돌이 쿵덕거리지 않나요??먼지둥둥뜨고…엉키고 드럼이 신세계던데",
        "expected": {
            "product_label": "통돌이 / 드럼 세탁기",
            "feature_topic": "통돌이 소음·먼지·엉킴 vs 드럼 만족",
            "atomic_voc": "통돌이는 쿵덕거림·먼지·엉킴이 있지 않냐고 묻고, 드럼은 신세계였다고 평가",
            "cej_stage": "사용",
            "tees_success_value": "달성",
            "tees_emotion_value": "surprise/positive for drum",
            "root_cause_maturity": "possible",
            "root_problem_level": "L2",
            "root_problem_target": "통돌이 소음·먼지·엉킴",
        },
    },
    {
        "id": "regression_other_person_usage_habit_blame",
        "comment": "@user-hk9ez9nc5h 뭐 옷을 하루에 세 벌씩 갈아입음??",
        "expected": {
            "product_label": "N/A — 타인의 세탁물 양/행동에 대한 비꼼",
            "feature_topic": "옷을 자주 갈아입는 행동 비난",
            "cej_stage": "N/A",
            "scope_status": "watch",
            "watch_agenda_flags": ["타인행동비난-제외 Watch"],
            "root_problem_level": "N/A",
        },
    },
    {
        "id": "regression_combo_power_measurement_question",
        "comment": "세탁 소비전력은 전체 소비측정인가요??? 아님 건조만 해당하는건가요",
        "expected": {
            "product_label": "일체형 세탁건조기",
            "feature_topic": "세탁 소비전력 측정 범위",
            "cej_stage": "탐색",
            "tees_success_value": "N/A",
            "root_cause_maturity": "unknown",
            "root_problem_level": "N/A",
        },
    },
    {
        "id": "regression_washer_repair_resistor_theory",
        "comment": "전알못인데 저항 150으로 맞추려고 엮은 거는 진짜 맞는 이론임??",
        "expected": {
            "product_label": "세탁기 수리/전기 부품",
            "feature_topic": "저항 150으로 맞추기 위한 회로 이론",
            "cej_stage": "탐색/관리 경계",
            "scope_status": "conditional",
            "root_problem_level": "N/A",
        },
    },
    {
        "id": "regression_refrigerator_kitchenfit_capacity",
        "comment": "628L키친핏이라는 건가요?? 아님 키친핏크기라는건지 잘 모르겠어요",
        "expected": {
            "product_label": "냉장고 628L 키친핏",
            "feature_topic": "628L 키친핏 제품/크기 의미",
            "cej_stage": "탐색",
            "tees_emotion_value": "confusion",
            "root_problem_level": "N/A",
        },
    },
    {
        "id": "regression_refrigerator_no_failure_case_by_case",
        "comment": "@jianim4799 그래요?? 전 고장. 안나던데~~케바케겟지요",
        "expected": {
            "product_label": "냉장고 / 삼성·LG 브랜드 비교",
            "feature_topic": "고장 경험과 케바케 인식",
            "cej_stage": "사용",
            "tees_success_value": "달성/문제 없음",
            "root_problem_level": "N/A",
        },
    },
    {
        "id": "regression_washer_packing_gel_question",
        "comment": "패킹 젤?? 그런 것도 있어요? 그거는 어떤 성분이 있는 건가요?",
        "expected": {
            "product_label": "세탁기 패킹젤",
            "feature_topic": "세탁기 패킹젤 존재와 성분",
            "cej_stage": "탐색/관리 경계",
            "root_problem_level": "N/A",
        },
    },
    {
        "id": "regression_refrigerator_card_discount_purchase_blocker",
        "comment": "국민카드할인도 안되는데 롯데카드만 할인되나요??주문할려고했는데ㅜㅜ",
        "expected": {
            "product_label": "냉장고",
            "feature_topic": "카드 할인 조건과 주문 가능성",
            "cej_stage": "구매",
            "tees_emotion_value": "disappointment",
            "tees_success_value": "미달성 가능 + 해결 여부 불명확",
            "root_problem_level": "L2",
            "root_problem_target": "카드 할인 조건/주문 가능성",
        },
    },
    {
        "id": "regression_washer_cleaning_performance_conflict",
        "comment": "귀곰채널에서 드럼세탁기가 세척력 더 좋다는거 증명됐는데 뭐죠???",
        "expected": {
            "product_label": "드럼 / 통돌이 세탁기",
            "feature_topic": "드럼 세탁기 세척력 검증 결과와 영상 주장 충돌",
            "cej_stage": "탐색/인지",
            "tees_emotion_value": "confusion/challenge",
            "root_problem_level": "N/A",
        },
    },
    {
        "id": "regression_washer_real_load_experiment_condition",
        "comment": "옷을 적어도 10벌에서 20벌은 넣고 빨아봐야 하지 않음?? 꼴랑 티 두 장씩 넣고 빨아도 드럼이 현저하게 세탁력이 주는데 실생활에 티 두 장 넣고 세탁기 돌리는 사람 없잖음??? 실생활에서 사용하는 것처럼 15벌 정도 넣고 돌려보삼. 그럼 통돌이가 나을지도",
        "expected": {
            "product_label": "드럼 / 통돌이 세탁기",
            "feature_topic": "실생활 세탁물 양에서의 세척력 실험 조건",
            "cej_stage": "탐색/사용 경계",
            "tees_emotion_value": "criticism",
            "root_cause_maturity": "possible",
            "root_problem_level": "L2",
            "root_problem_target": "실생활 세탁물 양 실험 조건",
        },
    },
)


GOLDEN120_ATOMIC_SPLIT_REGRESSION_EXAMPLES: tuple[dict[str, Any], ...] = (
    {
        "id": "atomic_split_comparison_negative_positive",
        "comment": "헉 통돌이 쿵덕거리지 않나요?? 먼지 둥둥 뜨고 엉키고. 드럼은 신세계던데",
        "expected_unit_count": 2,
        "expected": [
            {"polarity_label": "negative_concern", "feature_hint": "통돌이", "cej_hint": "사용"},
            {"polarity_label": "positive", "feature_hint": "드럼", "cej_hint": "사용"},
        ],
        "quality_note": "통돌이 증상 나열은 하나의 불만 흐름으로 묶고, 드럼 만족은 별도 Atomic.",
    },
    {
        "id": "atomic_keep_one_purchase_value_flow",
        "comment": "직배수 기술이 들어갔는데 가격이 오르지 않았고 충분히 살 만한 메리트가 있다.",
        "expected_unit_count": 1,
        "expected": [{"polarity_label": "positive", "feature_hint": "구매가치", "cej_hint": "구매"}],
        "quality_note": "기술·가격·메리트가 하나의 구매가치 주장 흐름을 이루므로 과분리 금지.",
    },
    {
        "id": "atomic_split_positive_negative_feature_mix",
        "comment": "가격은 만족한데 흡입력은 아쉽다.",
        "expected_unit_count": 2,
        "expected": [
            {"polarity_label": "positive", "feature_hint": "가격", "cej_hint": "구매"},
            {"polarity_label": "negative_concern", "feature_hint": "흡입력", "cej_hint": "사용"},
        ],
        "quality_note": "독립 감성·독립 개선 포인트가 있으므로 2 Atomic.",
    },
    {
        "id": "atomic_split_inquiry_plus_praise",
        "comment": "사도 되나요? 직배수는 좋아보이네요.",
        "expected_unit_count": 2,
        "expected": [
            {"polarity_label": "inquiry", "feature_hint": "구매 가능 여부", "cej_hint": "탐색"},
            {"polarity_label": "positive", "feature_hint": "직배수", "cej_hint": "인지"},
        ],
        "quality_note": "문의 의도와 기능 평가 의도가 독립적이므로 2 Atomic.",
    },
)
