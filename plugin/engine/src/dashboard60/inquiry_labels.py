"""문의·니즈 유형의 화면 표시 이름 — 이 파일이 유일한 사전이다.

★ 사전이 views/inquiry.py 에 한 벌 더 복사돼 있었고, 두 벌 다 허용값의
  3분의 1만 담고 있었다. 나머지는 원본 값(installation_fit 같은)이 그대로
  화면에 나왔다 (sky 2026-08-20). 복사본을 지우고 여기로 모았다.

★ 한국어 이름의 출처
  - 기준문서 v4.3 『23_VoC_결과파일_점검_기준문서』 — 허용값 목록
  - phase5a 구현명세 3.3 — 유형별 한국어 설명
  지어낸 이름을 쓰지 않는다. 문서에 없던 둘은 주석에 표시해 두었다.
"""

from __future__ import annotations


# 기준문서 v4.3 허용값 11종
INQUIRY_TYPE_LABELS = {
    "feature_spec": "기능/스펙 문의",
    "product_comparison": "제품 비교 문의",
    "product_identification": "제품 식별 문의",   # ※ 문서에 한국어 없음 — 이웃 어법을 따름
    "usage_environment_fit": "사용환경 적합 문의",
    "installation_fit": "설치 적합 문의",          # ※ 문서에 한국어 없음 — v2.7 신설 enum
    "promotion_benefit": "할인/혜택 문의",
    "as_trust_quality": "A/S·품질 신뢰 문의",
    "review_request": "후기 요청",
    "purchase_path_link": "구매경로/링크 문의",
    "other_question": "기타 질문",
    "none": "해당없음",
    "N/A": "해당없음",
    "": "해당없음",
}

# 기준문서 v4.3 허용값 12종
NEED_SIGNAL_TYPE_LABELS = {
    "feature_need": "기능 니즈",
    "price_value_need": "가격/가성비 니즈",
    "purchase_confidence_need": "구매확신 니즈",
    "conversion_signal": "구매 임박 신호",
    "problem_solution_need": "문제 해결 니즈",
    "trust_safety_need": "신뢰/안전 니즈",
    "content_information_need": "정보 요청 니즈",
    "environment_fit_need": "사용환경 적합 니즈",
    "purchase_path_need": "구매경로 니즈",
    "positive_message_candidate": "홍보 메시지 후보",
    "low_value": "실무 가치 낮음",
    "none": "해당없음",
    "N/A": "해당없음",
    "": "해당없음",
}


def display_inquiry_label(value: object) -> str:
    text = str(value or "").strip()
    return INQUIRY_TYPE_LABELS.get(text, text or "해당없음")


def display_need_signal_label(value: object) -> str:
    text = str(value or "").strip()
    return NEED_SIGNAL_TYPE_LABELS.get(text, text or "해당없음")
