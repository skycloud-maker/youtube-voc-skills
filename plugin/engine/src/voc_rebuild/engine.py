"""LLM runtime VoC rebuild engine.

Round 2 correction:
    The answer key is for validation only. This module does not encode
    case-specific decisions such as "if text contains X then topic=Y".
    Each unseen comment is analyzed through the runtime prompt from the
    reproduction design (Part A) plus the schema/rule contract.

The engine uses the OpenAI Chat Completions HTTP API via the standard library
so that it does not depend on the ``openai`` Python package being installed.
"""

from __future__ import annotations

import csv
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover - validated by entrypoint
    load_workbook = None

from .lexicon import get_evidence_excludes, get_labels_for_scope, get_price_value_guard_terms
from .scope_config import load_out_of_scope_products
from .schema import (
    CANONICAL_TOPICS,
    ENGINE_OWNED_COLUMNS,
    ENUM_COLUMNS,
    INQUIRY_TYPES,
    NEED_SIGNAL_TYPES,
    PRODUCT_CATEGORY_VALUES,
    REFERENCE_BRAND,
    STEP_CONFIDENCE_VALUES,
    TARGET_COLUMNS,
    assert_column_contract,
    enum_prompt_block,
)
from .text_clean import clean_text, cleaning_length_ratio
from ..v5.signal_splitter import ATOMIC_SPLIT_CONJUNCTIONS


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_LLM_CONCURRENCY = 2
DEFAULT_OPENAI_MAX_RETRIES = 5
RATE_LIMIT_RETRY_SECONDS_RE = re.compile(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)
RATE_LIMIT_BACKOFF_SECONDS = [2.0, 5.0, 10.0, 20.0, 30.0]

TOPIC_NORMALIZATION_MAP = {
    "가격 정책/구매가치": "가격/가성비",
    "제품 가성비 문의": "가격/가성비",
    "구매가치": "가격/가성비",
    "가성비": "가격/가성비",
    "가격 정책": "가격/가성비",
    "가격 비교": "가격/가성비",
    "링크 오류": "프로모션",
    "구매경로 문의": "프로모션",
    "프로모션/링크성": "프로모션",
    "제품 품질": "제품 전반",
    "제품 품질(부정)": "제품 전반",
    "로봇청소기 불만족": "제품 전반",
    "제품 평가 긍정(신뢰성)": "제품 전반",
    "청소신뢰성": "제품 전반",
    "청소신뢰성(긍정)": "제품 전반",
    "제조사 신뢰/품질 우려": "제조사 신뢰/품질",
    "배터리 안전성": "안전(화재·감전·누수)",
    "원산지 우려": "제조사 신뢰/품질",
    "화재/중국산 우려": "안전(화재·감전·누수)",
    "성능 평가(흡입력)": "청소/흡입 성능",
    "흡입력": "청소/흡입 성능",
    "성능 평가(물걸레)": "물걸레",
    "성능 평가(주행/장애물)": "동선/주행",
    "문턱 돌파": "주행/문턱돌파",
    "문턱돌파": "주행/문턱돌파",
    "단차 등반": "주행/문턱돌파",
    "회피력": "장애물 회피",
    "회피력 우수": "장애물 회피",
    "제품 평가 긍정(회피력)": "장애물 회피",
    "직배수 설치 사용성": "설치/설치 편의성",
    "배터리 지속성능": "배터리",
    "소음": "소음/진동",
    "앱/소프트웨어 안정성": "앱/스마트(원격제어)",
    "앱/스마트": "앱/스마트(원격제어)",
    "소프트웨어": "앱/스마트(원격제어)",
    "지도/맵핑": "앱/스마트(원격제어)",
    "지도/매핑": "앱/스마트(원격제어)",
    "맵핑": "앱/스마트(원격제어)",
    "매핑": "앱/스마트(원격제어)",
    "지도 저장": "앱/스마트(원격제어)",
    "원격제어": "앱/스마트(원격제어)",
    "펌웨어/업데이트": "앱/스마트(원격제어)",
    "A/S 경험": "A/S·고객응대",
    "배송/물류": "배송",
    "디자인/크기": "디자인",
    "호환성(문턱·러그·매트)": "동선/주행",
    "먼지봉투": "소모품/유지관리재",
    "관리제": "소모품/유지관리재",
    "세정제": "소모품/유지관리재",
    "필터": "소모품/유지관리재",
    "소모품": "소모품/유지관리재",
    "유지관리재": "소모품/유지관리재",
    "에러": "에러/오작동",
    "오류": "에러/오작동",
    "오작동": "에러/오작동",
    "E코드": "에러/오작동",
    "설치": "설치/설치 편의성",
    "스테이션 설치": "설치/설치 편의성",
    "급수배수 연결": "설치/설치 편의성",
    "세척력": "세척 성능",
    "헹굼": "세척 성능",
    "잔여물": "세척 성능",
    "건조": "건조 성능",
    "위생/살균(물상태)": "위생/살균",
    "물상태": "위생/살균",
    "살균": "위생/살균",
    "노즐": "노즐/잔수",
    "잔수": "노즐/잔수",
    "누수": "안전(화재·감전·누수)",
    "도어": "누수/도어",
    "배수": "배수·부품",
    "후기 요청": "N/A",
    "긍정적 피드백": "N/A",
    "제품 출시 문의": "N/A",
    "단순 감탄": "N/A",
}

LOW_VALUE_TOPIC_ALIASES = {
    "후기 요청",
    "긍정적 피드백",
    "제품 출시 문의",
    "단순 감탄",
    "단순 구매의향",
    "구매 의향",
    "범위 밖 제품 문의",
    "순수 정보 요청",
    "N/A",
}

LOW_VALUE_INQUIRY_TYPES = {"review_request", "product_identification", "other_question"}
LOW_VALUE_NEED_TYPES = {"none", "low_value", "content_information_need"}
PURCHASE_ONLY_NEED_TYPES = {"purchase_confidence_need", "conversion_signal"}
ALLOWED_INQUIRY_TYPES = INQUIRY_TYPES
ALLOWED_NEED_SIGNAL_TYPES = NEED_SIGNAL_TYPES
INQUIRY_VALUE_MISPLACED_IN_NEED = ALLOWED_INQUIRY_TYPES - {"none"}
NEED_VALUE_MISPLACED_IN_INQUIRY = ALLOWED_NEED_SIGNAL_TYPES - {"none"}
NEED_SIGNAL_TYPE_ALIASES = {
    "installation_fit_need": "environment_fit_need",
    "design": "feature_need",
}
INQUIRY_TYPE_ALIASES = {
    "installation": "installation_fit",
    "installation_environment_fit": "installation_fit",
}
STEP_CONFIDENCE_COLS = (
    "confidence_topic",
    "confidence_cej",
    "confidence_inquiry",
    "confidence_need_signal",
    "confidence_entity_role",
    "confidence_score",
)
SUBSTANTIVE_INQUIRY_TYPES = {
    "feature_spec",
    "product_comparison",
    "installation_fit",
    "usage_environment_fit",
    "promotion_benefit",
    "as_trust_quality",
    "purchase_path_link",
}
SUBSTANTIVE_NEED_TYPES = {
    "feature_need",
    "price_value_need",
    "problem_solution_need",
    "trust_safety_need",
    "environment_fit_need",
    "purchase_path_need",
}

COMPETITOR_ENTITY_NAMES = {
    "삼성",
    "로보락",
    "드리미",
    "MOVA",
    "모바",
    "DJI",
    "ROMO",
    "에코백스",
    "테슬라",
}

COMPETITOR_ENTITY_NAMES_LOWER = {name.lower() for name in COMPETITOR_ENTITY_NAMES}


PRODUCT_CATEGORY_LEXICON_SCOPE = {
    "로봇청소기": "robot_vacuum",
    "식기세척기": "dishwasher",
    "세탁기": "washer_dryer",
    "건조기": "washer_dryer",
    "냉장고": "refrigerator",
}

PRODUCT_CATEGORY_TOKEN_MAP = {
    "로봇청소기": (
        "로봇청소기",
        "로청",
        "홈봇",
        "로니",
        "로보락",
        "드리미",
        "mova",
        "모바",
        "dji",
        "romo",
        "에코백스",
        "비스포크 로봇",
        "x11",
        "z50",
        "도어 단 모델",
        "직수형 스테이션",
        "직배수",
        "리얼스팀",
        "스팀 제너레이터",
        "더스트백",
        "먼지통",
        "먼지봉투",
        "물걸레",
        "걸레질",
        "회피력",
        "쇼파 아래 청소",
        "청소신뢰성",
        "문턱",
        "턱",
        "매트",
        "카메라 달려",
    ),
    "식기세척기": (
        "식기세척기",
        "식세기",
        "dishwasher",
        "bosch",
        "maytag",
        "whirlpool",
        "midea",
        "dishwasher pod",
        "true dishwasher",
    ),
    "세탁기": (
        "세탁기", "washer", "washing machine", "트롬", "통돌이",
        "ai 일체형", "일체형 세탁기", "워시타워", "세탁건조", "세탁건조기",
        "올인원", "콤보", "워시콤보", "드럼", "드럼세탁기", "일체형",
    ),
    "건조기": ("건조기", "dryer", "건조기능", "드럼건조기"),
    "냉장고": ("냉장고", "refrigerator", "fridge", "김치냉장고"),
}

AMBIGUOUS_PRODUCT_TOKENS = {
    "트롬",
    "드럼",
    "콤보",
    "올인원",
    "워시콤보",
    "세탁건조",
    "일체형",
}

EXTENDED_APPLIANCE_SCOPE_TERMS = (
    "에어컨",
    "휘센",
    "스타일러",
    "틔운",
    "tiiun",
    "마이컵",
    "mycup",
    "정수기",
    "오븐",
    "인덕션",
    "공기청정기",
)
HOUSING_OUT_OF_SCOPE_CONTEXT_TERMS = (
    "스마트코티지",
    "모듈러",
    "모듈러하우스",
    "이동식주택",
    "소형주택",
    "전원주택",
    "세컨하우스",
    "주거공간",
    "조립식",
    "주택",
    "집을 만들",
    "부동산",
    "건축",
    "인테리어",
    "화장실",
    "세면대",
    "이층방",
    "modular",
    "cottage",
    "tiny house",
    "house",
    "louvers",
)
HOUSING_ARCHITECTURE_ONLY_COMMENT_TERMS = (
    "이층방",
    "방 크기",
    "방이",
    "방은",
    "방도",
    "방 좁",
    "방문",
    "화장실",
    "세면대",
    "세면기",
    "욕실",
    "주방",
    "싱크",
    "싱크대",
    "창문",
    "창호",
    "처마",
    "지붕",
    "창고",
    "외벽",
    "벽체",
    "다용도실",
    "수납장",
    "붙박이",
    "평면",
    "평수",
    "공간 설계",
    "공간이",
    "공간은",
    "구조",
    "인테리어",
    "계단",
    "복층",
    "천장",
    "침실",
    "거실",
    "현관",
    "마당",
    "테라스",
    "louvers",
    "louver",
    "kitchen",
    "sink",
    "counter",
    "bathroom",
    "bedroom",
    "roof",
    "eaves",
    "wall",
    "stairs",
    "floor plan",
    "interior",
)
SMART_COTTAGE_PRODUCT_SERVICE_TERMS = (
    "스마트코티지",
    "smart cottage",
    "스마트 홈",
    "스마트홈",
    "스마트 창문",
    "스마트 유리",
    "smart home",
    "iot",
    "씽큐",
    "thin q",
    "thinq",
    "가전 연동",
    "가전이",
    "가전을",
    "가전은",
    "가전도",
    "가전 옵션",
    "appliance",
    "태양광",
    "에너지 자립",
    "에너지자립",
    "히트펌프",
    "service",
    "서비스",
    "a/s",
    "as",
    "가격",
    "비싸",
    "구매",
    "신뢰",
    "퀄리티",
    "품질",
    "상품",
    "옵션",
    "방범",
    "스마트관리",
    "대기업",
)
PRODUCT_REVIEW_OR_ISSUE_CUES = (
    "고장",
    "불량",
    "냄새",
    "소음",
    "누수",
    "세척",
    "건조",
    "설치",
    "수리",
    "a/s",
    "가격",
    "비싸",
    "추천",
    "비교",
    "후기",
    "사용",
    "청소",
    "problem",
    "issue",
    "smell",
    "noise",
    "leak",
    "clean",
    "dry",
    "wash",
    "repair",
    "install",
    "review",
    "buy",
    "recommend",
)
INCIDENTAL_PRODUCT_PRESENCE_CUES = (
    "have a",
    "has a",
    "also have",
    "also has",
    "looks to",
    "보이",
    "있는 것",
    "있어 보",
)
ALLOWED_CEJ_VALUES = ENUM_COLUMNS["cej"]

PRODUCT_CATEGORY_TOPIC_SCOPE_MAP = {
    "식기세척기": {
        "청소/흡입 성능": "세척 성능",
        "물걸레": "미분류",
        "스팀": "미분류",
        "먼지통/자동비움": "미분류",
        "동선/주행": "미분류",
        "장애물 회피": "미분류",
        "배터리": "미분류",
    },
    "세탁기": {
        "청소/흡입 성능": "미분류",
        "세척 성능": "세탁 성능",
        "건조 성능": "미분류",
        "물걸레": "미분류",
        "동선/주행": "미분류",
        "장애물 회피": "미분류",
        "배터리": "미분류",
        "먼지통/자동비움": "미분류",
    },
    "건조기": {
        "청소/흡입 성능": "건조 성능",
        "세척 성능": "미분류",
        "물걸레": "미분류",
        "동선/주행": "미분류",
        "장애물 회피": "미분류",
        "배터리": "미분류",
        "먼지통/자동비움": "미분류",
    },
    "냉장고": {
        "청소/흡입 성능": "미분류",
        "세척 성능": "미분류",
        "건조 성능": "미분류",
        "물걸레": "미분류",
        "동선/주행": "미분류",
        "장애물 회피": "미분류",
        "배터리": "미분류",
        "먼지통/자동비움": "미분류",
    },
}

ROBOT_VACUUM_TOPIC_PRIORITY_RULES = [
    (
        "주행/문턱돌파",
        (
            "문턱",
            "단차",
            "경사",
            "매트",
            "층간소음매트",
            "시공매트",
            "넘어가",
            "올라가",
            "못올라",
            "못 올라",
            "돌파",
            "등반",
        ),
    ),
    (
        "장애물 회피",
        (
            "장애물",
            "회피",
            "피하",
            "전선",
            "액체",
            "배설물",
            "강아지 똥",
            "강아지 쉬",
            "반려동물",
            "똥",
        ),
    ),
    (
        "동선/주행",
        (
            "동선",
            "경로",
            "못 가",
            "안 가",
            "쇼파 아래",
            "소파 아래",
            "가구 아래",
            "갇힘",
            "알고리즘",
            "구역",
        ),
    ),
    ("배터리", ("배터리",)),
    ("스팀", ("스팀",)),
    ("물걸레", ("물걸레", "걸레판", "물걸레 압력", "걸레 압력", "반복으로 닦")),
    ("먼지통/자동비움", ("먼지통", "자동비움", "히든스테이션", "스테이션용", "내장된 작은 먼지봉투")),
    ("청소/흡입 성능", ("흡입", "설탕흡입", "머리카락", "먼지 제거", "청소 성능", "청소 결과")),
]

COMMON_TOPIC_PROTECTION_RULES = [
    ("A/S·고객응대", ("as ", "a/s", "서비스센터", "기사님", "고객센터", "센터")),
    (
        "앱/스마트(원격제어)",
        ("소프트웨어", "앱", "지도", "맵핑", "매핑", "지도 저장", "원격제어", "다운로드 코스", "앱 알림", "펌웨어", "업데이트"),
    ),
    ("제조사 신뢰/품질", ("제조국", "국산", "국내산", "중국", "odm", "jdm", "외주", "마감")),
    ("내구성/고장", ("내구성", "부러", "고장", "변형", "곰팡이", "설계오류", "설계 오류")),
    (
        "디자인",
        (
            "디자인",
            "비주얼",
            "인테리어",
            "예쁜",
            "예쁘",
            "가구 같",
            "가구같",
            "서랍장",
            "깔끔",
            "빌트인",
            "하부장",
            "걸레받이",
        ),
    ),
    (
        "설치/설치 편의성",
        ("설치공간", "설치 공간", "공간 제약", "장 높이", "높이", "배송 및 설치", "설치 가능", "싱크대 밑", "하부장 밑", "공간에 들어"),
    ),
]

PRICE_VALUE_DIRECT_TOKENS = get_price_value_guard_terms()

INSTALL_ENVIRONMENT_TOKENS = (
    "설치공간",
    "설치 공간",
    "공간 제약",
    "장 높이",
    "높이",
    "하부장",
    "싱크대 밑",
    "수납장",
    "가구 안",
    "가구 밑",
    "들어가",
    "안 들어",
)

CONTEXTLESS_REACTION_TOKENS = ("ㅋㅋ", "ㅎㅎ", "드립", "농담", "싸우신", "싸운")
SHORT_REACTION_ONLY_TOKENS = ("1등", "일등", "첫댓", "첫 댓글", "왔습니다", "출석")
PRODUCT_OR_ASPECT_EVIDENCE_TOKENS = tuple(
    token
    for topic_tokens in (
        PRICE_VALUE_DIRECT_TOKENS,
        INSTALL_ENVIRONMENT_TOKENS,
        ("로청", "로봇청소기", "제품", "기능", "성능", "스팀", "물걸레", "흡입", "동선", "주행", "문턱", "설치", "디자인", "국산", "중국", "as", "a/s"),
    )
    for token in topic_tokens
)

POSITIVE_EVALUATION_TOKENS = (
    "좋",
    "대박",
    "역대급",
    "잘 나왔",
    "미쳤",
    "예쁘",
    "깔끔",
    "끝났다",
    "메리트",
    "장점",
    "뛰어나다",
    "우수",
    "훌륭",
    "만족",
)

STRONG_POSITIVE_EVALUATION_TOKENS = ("대박", "역대급", "미쳤", "끝났다", "진짜 잘", "너무 좋", "확실히 메리트")

NEGATIVE_EVALUATION_TOKENS = (
    "걱정",
    "우려",
    "불안",
    "불편",
    "문제",
    "아쉽",
    "안 좋",
    "별로",
    "못",
    "안 ",
    "비싸",
    "고장",
    "귀찮",
)


class LLMRuntimeUnavailable(RuntimeError):
    """Raised when the runtime cannot perform actual LLM analysis."""


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def append_trace(row: dict[str, Any], note: str) -> None:
    trace = safe_text(row.get("trace_summary"))
    row["trace_summary"] = f"{trace} | {note}" if trace else note


def affiliate_promo_notice_signals(text: str) -> list[str]:
    """Return conservative pre-LLM exclusion signals for affiliate/link dumps."""

    normalized = safe_text(text).lower()
    signals: list[str] = []
    if any(token in normalized for token in ["수수료", "커미션", "제휴", "파트너스", "광고 포함", "유료광고"]):
        signals.append("commission_or_ad_disclosure")
    if any(
        token in normalized
        for token in [
            "구매링크",
            "구매 링크",
            "링크를 통해",
            "최저가",
            "쿠팡 링크",
            "쿠팡파트너스",
            "influencers.coupang",
            "redirect?event=comments",
        ]
    ):
        signals.append("purchase_link")
    emoji_count = normalized.count("🔥") + normalized.count("✅")
    if any(token in normalized for token in ["추천 제품", "한눈에 보기", "추천 모델", "라인업"]) or emoji_count >= 3:
        signals.append("catalog_or_promo_list")

    catalog_names = {
        "로보락",
        "드리미",
        "에코백스",
        "나르왈",
        "dji",
        "모바",
        "mova",
        "샤오미",
        "삼성",
        "비스포크",
        "에코백스",
        "ecovacs",
        "narwal",
        "roborock",
        "dreame",
        "x40",
        "x50",
        "x11",
        "s8",
        "s9",
        "romo",
    }
    mentioned = {name for name in catalog_names if name in normalized}
    if len(mentioned) >= 3:
        signals.append("competitor_model_catalog")
    return signals


def is_operator_notice(text: str) -> bool:
    normalized = safe_text(text).lower()
    if "[영상 속 제품 할인가 구매링크]" in normalized and "일정액의 수수료" in normalized:
        return True
    return len(affiliate_promo_notice_signals(normalized)) >= 2


def operator_notice_reason(text: str) -> str:
    signals = affiliate_promo_notice_signals(text)
    if len(signals) >= 2:
        return "제휴/홍보 링크 덤프"
    return "운영자 제휴링크/공지성 안내문"


SCOPE_REASON_WHITELIST = {
    "empty",
    "operator_notice",
    "channel_request",
    "channel_feedback",
    "out_of_scope_product",
    "no_analytic_value",
    "unresolvable_reply",
}

D1_BETA_NEED_SENTIMENT_PATTERNS = (
    r"\uc0ac\uc57c",
    r"\uc0ac\uaca0",
    r"(?:^|\s)\uc0ac\uba74",
    r"\uc0b4\ub798",
    r"\uc0bd\ub2c8\ub2e4",
    r"\uc0ac\uace0\s*\uc2f6",
    r"\uad6c\ub9e4",
    r"\uc9c8\ub7ec",
    r"\uc548\s*\uc0ac",
    r"\uc0ac\uc9c0\s*\uc54a",
    r"\ud328\uc2a4",
    r"\uc88b",
    r"\ub9cc\uc871",
    r"\ub300\ubc15",
    r"\ucd5c\uace0",
    r"\uba4b\uc9c0",
    r"\ud574\ub0c8",
    r"\uc2eb",
    r"\ubcc4\ub85c",
    r"\uc2e4\ub9dd",
    r"\ucd5c\uc545",
    r"\ubd88\ub9cc",
)

PRE_LLM_SCOPE_REASON_MAP = {
    "정제 후 분석 가능한 VoC 없음": "empty",
    "운영자 제휴링크/공지성 안내문": "operator_notice",
    "제휴/홍보 링크 덤프": "operator_notice",
}


def canonical_scope_exclusion_reason(reason: object) -> str:
    value = safe_text(reason)
    if value in SCOPE_REASON_WHITELIST:
        return value
    return PRE_LLM_SCOPE_REASON_MAP.get(value, "")


def has_d1_beta_need_or_sentiment_signal(row: dict[str, Any]) -> bool:
    """Return whether D1-beta step 3 must keep the row in the analysis base.

    Phase 0 does not implement the taxonomy-v0.7 lexical topic gates yet.  It
    does, however, have to prevent ``no_analytic_value`` from discarding rows
    where the LLM already found a customer need or TEE/S signal.  Such rows stay
    normal with topic=N/A and remain part of the denominator.
    """

    need_type = safe_text(row.get("need_signal_type"))
    has_need = safe_text(row.get("need_signal_flag")) == "Y" or need_type not in {
        "",
        "none",
        "low_value",
    }
    has_sentiment = False
    for key in ("tee_time_score", "tee_effort_score", "tee_emotion_score", "tee_success_score"):
        try:
            if int(float(row.get(key) or 0)) != 0:
                has_sentiment = True
                break
        except (TypeError, ValueError):
            continue
    return has_need or has_sentiment


def has_explicit_d1_beta_need_or_sentiment_text(row: dict[str, Any]) -> bool:
    """Conservative fallback for explicit step-3 language missed by LLM fields."""

    text = " ".join(
        part
        for part in (safe_text(row.get("atomic_voc")), safe_text(row.get("original_voc")))
        if part
    )
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in D1_BETA_NEED_SENTIMENT_PATTERNS)


CHANNEL_REQUEST_COMPLETE_PHRASES = (
    "해주세요", "해주십시오", "해주시면", "해주라", "부탁드려요",
    "부탁드립니다", "부탁해요", "리뷰 해", "리뷰해달라",
)
CHANNEL_REQUEST_STEM_PATTERN = re.compile(
    r"(?:정해주|다뤄주|올려주|리뷰해|해봐주)(?!신|셨|셔서|시는|시던|줘서|줬|준|주신)"
)
IN_SCOPE_PRODUCT_REQUEST_TERMS = tuple(
    token
    for tokens in PRODUCT_CATEGORY_TOKEN_MAP.values()
    for token in tokens
)


def _contains_channel_request_phrase(text: str) -> bool:
    return (
        any(token in text for token in CHANNEL_REQUEST_COMPLETE_PHRASES)
        or CHANNEL_REQUEST_STEM_PATTERN.search(text) is not None
    )


def _contains_in_scope_product_term(text: str) -> bool:
    return any(
        _product_token_matches(text, token)
        for token in IN_SCOPE_PRODUCT_REQUEST_TERMS
    )


def is_explicit_channel_request_text(row: dict[str, Any]) -> bool:
    """Recognize an operator-addressed content/review request (RT-22)."""

    text = " ".join(
        part
        for part in (safe_text(row.get("atomic_voc")), safe_text(row.get("original_voc")))
        if part
    )
    if not _contains_channel_request_phrase(text):
        return False
    out_of_scope_request = any(
        _product_token_matches(text, token)
        for token in load_out_of_scope_products()
    )
    if out_of_scope_request:
        return True
    if _contains_in_scope_product_term(text):
        return False
    channel_context = any(
        token in text
        for token in ("귀곰", "채널", "리뷰어", "유튜버", "영상", "편집", "자막", "다음편")
    ) or re.search(r"(?:^|\s)\d+부(?:는|가|를|은|\s|$)", text) is not None
    if channel_context:
        return True
    return False


def is_simple_d1_beta_na_row(row: dict[str, Any]) -> bool:
    """Keep short need/sentiment-only rows as N/A rather than unclassified."""

    if safe_text(row.get("topic")) not in {"N/A", "\ubbf8\ubd84\ub958"}:
        return False
    if safe_text(row.get("inquiry_flag")) == "Y":
        return False
    text = safe_text(row.get("atomic_voc")) or safe_text(row.get("original_voc"))
    if len(re.sub(r"\s+", "", text)) > 40:
        return False
    return has_explicit_d1_beta_need_or_sentiment_text(row)


def is_effectively_empty(text: str) -> bool:
    cleaned = re.sub(r"@\S+", "", safe_text(text))
    cleaned = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", cleaned)
    meaningful = "".join(re.findall(r"[0-9A-Za-z가-힣]+", cleaned))
    return meaningful in {"", "안녕하세요", "감사합니다"}


CHANNEL_REQUEST_PRIORITY_REASONS = {"no_analytic_value", "out_of_scope_product"}


def normalize_scope_exclusion(row: dict[str, Any]) -> None:
    """Allow scope exclusion only with a canonical reason.

    Phase 0 inverts the old guard: pre-LLM empty/operator gates remain hard
    exclusions, while LLM semantic exclusions are accepted only when they carry
    a whitelisted ``scope_exclusion_reason``. Unlisted/missing reasons are
    reverted to normal with review_required=Y and an auditable reason token.
    """

    if safe_text(row.get("status")) != "scope_excluded":
        if is_explicit_channel_request_text(row):
            row["status"] = "scope_excluded"
            row["scope_exclusion_reason"] = "channel_request"
            row["topic"] = "N/A"
            row["topic_provisional"] = safe_text(row.get("topic_provisional")) or "채널 요청으로 분석 대상에서 제외됨"
            row["topic_score"] = 0
            row["rootcause_score"] = 0
            clear_rootcause_details_when_score_zero(row)
            append_trace(row, "channel_request_promoted_from_normal")
            return
        row["scope_exclusion_reason"] = ""
        topic_was_blank = bool(row.get("_topic_label_was_blank")) or not safe_text(row.get("topic"))
        if not safe_text(row.get("topic")) or (topic_was_blank and safe_text(row.get("topic")) in {"N/A", "미분류"}):
            if has_d1_beta_need_or_sentiment_signal(row) or has_explicit_d1_beta_need_or_sentiment_text(row):
                row["topic"] = "N/A"
                row["topic_provisional"] = safe_text(row.get("topic_provisional")) or "요구나 감정 신호는 있으나 독립 주제를 확정하지 못함"
                row["topic_score"] = 0
                trace = safe_text(row.get("trace_summary"))
                note = "d1_beta_blank_topic_resolved: need_or_sentiment_signal"
                row["trace_summary"] = f"{trace} | {note}" if trace else note
            elif not is_substantive_voc(row):
                row["status"] = "scope_excluded"
                row["topic"] = "N/A"
                row["topic_provisional"] = safe_text(row.get("topic_provisional")) or "분석 가능한 실질 VoC가 없음"
                row["topic_score"] = 0
                row["scope_exclusion_reason"] = "no_analytic_value"
                trace = safe_text(row.get("trace_summary"))
                note = "d1_beta_blank_topic_resolved: no_analytic_value"
                row["trace_summary"] = f"{trace} | {note}" if trace else note
            else:
                row["topic"] = "미분류"
                row["topic_provisional"] = safe_text(row.get("topic_provisional")) or "제품 관련 실질 발화지만 잠정 주제를 확정하지 못함"
                row["topic_score"] = 1
                trace = safe_text(row.get("trace_summary"))
                note = "d1_beta_blank_topic_resolved: unclassified_substantive_voc"
                row["trace_summary"] = f"{trace} | {note}" if trace else note
        if is_simple_d1_beta_na_row(row):
            row["topic"] = "N/A"
            row["topic_provisional"] = safe_text(row.get("topic_provisional")) or "독립 분석 주제가 없는 단순 발화"
            row["topic_score"] = 0
        return

    reason = canonical_scope_exclusion_reason(row.get("scope_exclusion_reason"))
    if reason in CHANNEL_REQUEST_PRIORITY_REASONS and is_explicit_channel_request_text(row):
        reason = "channel_request"
        row["scope_exclusion_reason"] = reason
        trace = safe_text(row.get("trace_summary"))
        note = "scope_reason_normalized: channel_request"
        row["trace_summary"] = f"{trace} | {note}" if trace else note
    override_requested = reason == "no_analytic_value" and (
        has_d1_beta_need_or_sentiment_signal(row)
        or has_explicit_d1_beta_need_or_sentiment_text(row)
    )
    preserved_signal = (
        safe_text(row.get("topic")) not in {"", "N/A"}
        or _score_as_int(row.get("topic_score")) > 0
        or (
            safe_text(row.get("need_signal_flag")) == "Y"
            and safe_text(row.get("need_signal_type")) not in {"", "none"}
        )
        or any(
            _score_as_int(row.get(key)) != 0
            for key in ("tee_time_score", "tee_effort_score", "tee_emotion_score", "tee_success_score")
        )
    )
    if override_requested and preserved_signal:
        row["status"] = "normal"
        row["topic"] = "N/A"
        row["topic_provisional"] = safe_text(row.get("topic_provisional")) or "제외 판정은 해제됐지만 독립 주제를 확정하지 못함"
        row["topic_score"] = 0
        row["scope_exclusion_reason"] = ""
        trace = safe_text(row.get("trace_summary"))
        note = "scope_exclusion_overridden: d1_beta_need_or_sentiment_signal"
        row["trace_summary"] = f"{trace} | {note}" if trace else note
        return
    if override_requested and not preserved_signal:
        append_trace(row, "scope_override_declined: no_preserved_signal")
    if reason:
        row["scope_exclusion_reason"] = reason
        return

    raw_reason = safe_text(row.get("scope_exclusion_reason")) or "missing"
    row["status"] = "normal"
    row["review_required"] = "Y"
    row["scope_exclusion_reason"] = ""
    trace = safe_text(row.get("trace_summary"))
    note = f"scope_exclusion_overridden: reason={raw_reason}"
    row["trace_summary"] = f"{trace} | {note}" if trace else note


def load_dotenv(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE pairs without printing secrets."""

    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class SourceRow:
    values: dict[str, Any]

    @property
    def source_id(self) -> str:
        return safe_text(self.values.get("source_id"))

    @property
    def raw_row_index(self) -> str:
        return safe_text(self.values.get("raw_row_index"))

    @property
    def original_voc(self) -> str:
        return safe_text(self.values.get("original_voc"))

    @property
    def voc_cleaned(self) -> str:
        return clean_text(self.original_voc)

    @property
    def cleaning_length_ratio(self) -> float:
        return cleaning_length_ratio(self.original_voc, self.voc_cleaned)

    @property
    def parent_voc_id(self) -> str:
        return safe_text(self.values.get("parent_voc_id"))

    @property
    def comment_relation(self) -> str:
        return safe_text(self.values.get("comment_relation")) or safe_text(self.values.get("rel"))


TOPIC_EXTRACTION_SYSTEM_PROMPT = """You extract ONE independent VoC topic at a time.
Return JSON only with provisional_summary, provisional_label, and excerpt.
The excerpt must be copied verbatim from remaining_text.
The excerpt must cover exactly one independent analysis result.
Return the entire remaining_text as the excerpt ONLY when the remaining text is
a single coherent unit with no other independent result in it.
Before returning, check whether remaining_text still contains another independent
analysis result after your excerpt. If it does, your excerpt is too long — shorten
it to the first one only.
provisional_label is an internal canonical label used only for duplicate prevention
and trace. Return provisional_label='N/A' when no independent topic remains.
provisional_summary is free Korean prose that explains what the selected excerpt
is about and what evidence it contains. It must not merely repeat a canonical
label. If no label can be chosen, explain why.

Atomic = 독립 분석 단위 — 문장이 여럿이라 나누지 말고, 독립적 분석결과(Topic/Inquiry/Need 또는 TEE/S/RootCause)가 도출될 때만 01,02,03…으로 분리한다. 상한은 없다.
가격+성능이 결합된 가성비 문의는 단일 atomic이다.
여러 사실이 모두 하나의 추천 요청 조건이면 단일 atomic이다.

[Atomic Split Examples]
- A long product-use review with independent suction, cleaning reliability, and obstacle-avoidance judgments must be split into three atomics.
- Split: 'The installation space is too narrow, and the service response was also disappointing.' => separate installation-fit and service-response atomics.
- Split: 'I distrust the manufacturing origin, and separately want to know the battery runtime.' => separate manufacturing-trust and battery-information atomics.

[Atomic Non-Split Examples]
- Do not split: 'It is expensive, but is the cleaning performance worth that price?' => one price/performance value atomic (R9).
- Do not split: 'The motor failed because hair was tangled, so I cleaned the brush.' => one defect/cause/remedy atomic.
- Do not split: 'The design is clean and fits the kitchen interior well.' => one design atomic.

조건 나열형 추천 요청 비분리 예시:
'60만원 이하 입문기 갈까요? 걸레빠는것 지쳐요.. 고양이 3마리, 강화마루'는 모두 하나의 추천 요청 조건이므로 단일 atomic이다.

[Context Preservation Rules]
The purpose of excerpting is not to maximize splitting. It is to make each excerpt
understandable to a practitioner when read by itself.
E-1: Extract at least a complete sentence. Never return only a clause or phrase.
E-2: Include adjacent sentences that provide the topic's evidence, conditions, or
background. If the excerpt alone does not explain the situation, it is too narrow.
E-2 requires enough context, not the whole comment. Include the sentences that
support this one topic. Stop there.
E-3: Split only when two or more independent analysis results (Topic/Inquiry/Need
or TEE-S/RootCause) are present. Different possible topic names alone do not
justify splitting. If the text reads as one coherent unit, return one atomic.

[Context Preservation Example]
Full text:
'쿠쿠 최저가 초기 모델 6인용 식세기(20만원대) 쓰는데 내부 올스텐에 바스켓
고무코팅 기본인데 lg가 급하긴 했나보네요.. 자동 개폐는 안돼는게 흠이지만
큰 불편함은 없고 예약기능도 있고 가성비는 진짜 갑인듯요. 타공 안돼서
급수관 걸레받이 사이로 넣어서 설치했는데 예민하신 성격아니면 크게 걸림돌 안될듯'
Wrong excerpt: '가성비는 진짜 갑인듯요.' (a narrow clause without context)
Correct atomic 01: '쿠쿠 최저가 초기 모델 6인용 식세기(20만원대) 쓰는데 내부
올스텐에 바스켓 고무코팅 기본인데 lg가 급하긴 했나보네요.. 자동 개폐는
안돼는게 흠이지만 큰 불편함은 없고 예약기능도 있고 가성비는 진짜 갑인듯요.'
Correct atomic 02: '타공 안돼서 급수관 걸레받이 사이로 넣어서 설치했는데
예민하신 성격아니면 크게 걸림돌 안될듯'
On this call, return ONLY 'Correct atomic 01' as the excerpt. 'Correct atomic 02'
will be extracted on the next call from the remaining text. Never return both in
one response.
Do not split automatic-door and reservation details again; they are context for
the value judgment."""


TOPIC_EXTRACTION_SYSTEM_PROMPT += (
    "\n\n[Canonical Topic Taxonomy]\n"
    "provisional_label MUST be exactly one label from this list:\n"
    + "\n".join(f"- {topic}" for topic in CANONICAL_TOPICS)
    + "\nIf no listed topic applies, return 미분류 or N/A. Do not invent a label."
    + "\nUse 기타(제품명) only after checking every established label and finding no fit."
    + "\nIn provisional_summary, explain why no established label fits."
    + "\nDo not use 기타 when the product category itself is unknown; use 미분류."
)


def build_topic_extraction_prompt(
    source: SourceRow,
    remaining_text: str,
    *,
    repair_excerpt: str = "",
    extracted_topics: Iterable[str] = (),
    extracted_excerpts: Iterable[str] = (),
) -> str:
    """Build the iterative topic/excerpt request without judging other fields."""

    payload = {
        "source_id": source.source_id,
        "full_voc_cleaned_context": source.voc_cleaned,
        "already_extracted": [
            safe_text(excerpt) for excerpt in extracted_excerpts if safe_text(excerpt)
        ],
        "remaining_text": remaining_text,
        "parent_voc": safe_text(source.values.get("parent_voc")) or safe_text(source.values.get("parent_comment")),
        "video_context": {
            "title": safe_text(source.values.get("video_title")),
            "tags": safe_text(source.values.get("video_tags")),
            "description": safe_text(source.values.get("video_description")),
        },
        "output_schema": {
            "provisional_summary": "free Korean prose describing the selected excerpt and its evidence",
            "provisional_label": "one canonical topic or N/A; internal/trace only",
            "excerpt": "verbatim substring of remaining_text",
        },
        "canonical_topics": CANONICAL_TOPICS,
        "already_extracted_provisional_labels": [
            safe_text(topic) for topic in extracted_topics if safe_text(topic)
        ],
        "rules": [
            "Extract exactly one independent analysis result, not one sentence.",
            "Copy excerpt verbatim; do not paraphrase, correct punctuation, or alter endings.",
            "E-1: Excerpt at least a complete sentence; never return only a clause or phrase.",
            "E-2: Include adjacent evidence, condition, and background sentences needed to understand the excerpt alone.",
            "E-3: Split only for independent analysis results, not merely because different topic names are possible.",
            "Never extract a provisional_label that is already listed in already_extracted_provisional_labels.",
            "If the remaining text only belongs to an already extracted label, return provisional_label=N/A and stop.",
            "If another independent topic remains, extract that different topic instead.",
            "Write provisional_summary as free prose; do not copy provisional_label as the summary.",
            "Use 기타(제품명) only when the product is known and every established topic label has been checked.",
            "If the product is not identifiable, use 미분류 rather than 기타(제품명).",
            "Do not split a combined price/performance value inquiry.",
            "Do not split several facts that are all conditions of one recommendation request.",
            "Return provisional_label=N/A when no independent topic remains.",
        ],
    }
    if repair_excerpt:
        payload["repair"] = {
            "invalid_excerpt": repair_excerpt,
            "instruction": "Copy the intended excerpt again, exactly as it appears in remaining_text.",
        }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def split_by_topic(
    source: SourceRow,
    runtime: Any,
    *,
    max_iterations: int = 20,
) -> tuple[list[dict[str, Any]], str, bool, list[str]]:
    """Iteratively extract topic atomics while preserving source character spans."""

    text = source.voc_cleaned
    used = [False] * len(text)
    atomics: list[dict[str, Any]] = []
    traces: list[str] = []
    review_required = False

    def residual_is_nonanalytic(value: str) -> bool:
        """Recognize only narrow, high-precision residual noise; ambiguity is analytic."""

        compact = re.sub(r"\s+", " ", safe_text(value)).strip()
        if not compact:
            return True
        without_handles = re.sub(r"@[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ_.-]+", " ", compact)
        without_noise = re.sub(r"[\sㅋㅎㅠㅜ!?~.,:;·♡♥❤💙💜💚💛🧡🤍🖤😊😂🤣😭🥰😍👍👏🙏✨⭐🌟-]+", "", without_handles)
        if not without_noise:
            return True
        phrase = re.sub(r"\s+", "", without_handles).casefold()
        phrase = re.sub(r"[ㅋㅎㅠㅜ!?~.,:;·♡♥❤💙💜💚💛🧡🤍🖤😊😂🤣😭🥰😍👍👏🙏✨⭐🌟-]+", "", phrase)
        return bool(
            re.fullmatch(
                r"(?:귀곰님)?(?:안녕하세요|감사합니다|감사해요|고맙습니다|고마워요|"
                r"좋은리뷰감사합니다|리뷰감사합니다|영상잘봤어요|영상잘보았습니다|"
                r"잘봤어요|잘보았습니다|재미있어요|재밌어요)",
                phrase,
            )
        )

    def absorb_meaningful_residual() -> None:
        """Expand the final atomic's source span without inventing or duplicating text."""

        nonlocal review_required
        residual_before = "".join(char for index, char in enumerate(text) if not used[index])
        if not atomics or residual_is_nonanalytic(residual_before):
            return
        last = atomics[-1]
        last_start = int(last["_source_span_start"])
        last_end = int(last["_source_span_end"])
        remaining_offsets = [index for index, is_used in enumerate(used) if not is_used]
        if not remaining_offsets:
            return
        expanded_start = min(last_start, remaining_offsets[0])
        expanded_end = max(last_end, remaining_offsets[-1] + 1)
        prior_spans = [
            (int(item["_source_span_start"]), int(item["_source_span_end"]))
            for item in atomics[:-1]
        ]
        if any(start < expanded_end and end > expanded_start for start, end in prior_spans):
            review_required = True
            traces.append("meaningful_residual_absorption_blocked_by_prior_atomic_span")
            return
        for offset in range(expanded_start, expanded_end):
            used[offset] = True
        last["_source_span_start"] = expanded_start
        last["_source_span_end"] = expanded_end
        last["atomic_voc"] = text[expanded_start:expanded_end]
        traces.append(
            "meaningful_residual_absorbed_into_last_atomic: "
            f"chars={len(residual_before)}"
        )

    def order_and_merge_duplicate_topics() -> None:
        """Order plans by source span and merge only contiguous duplicate topics."""

        nonlocal atomics, review_required
        original_order = [int(item["_source_span_start"]) for item in atomics]
        atomics.sort(key=lambda item: int(item["_source_span_start"]))
        if original_order != [int(item["_source_span_start"]) for item in atomics]:
            traces.append("atomic_order_sorted_by_source_span")

        merged: list[dict[str, Any]] = []
        for item in atomics:
            topic = safe_text(item.get("_provisional_label"))
            if merged and safe_text(merged[-1].get("_provisional_label")) == topic:
                previous = merged[-1]
                previous_end = int(previous["_source_span_end"])
                current_start = int(item["_source_span_start"])
                if not text[previous_end:current_start].strip():
                    current_end = int(item["_source_span_end"])
                    previous["_source_span_end"] = current_end
                    previous["atomic_voc"] = text[int(previous["_source_span_start"]):current_end]
                    previous_summary = safe_text(previous.get("topic_provisional"))
                    current_summary = safe_text(item.get("topic_provisional"))
                    if current_summary and current_summary != previous_summary:
                        previous["topic_provisional"] = f"{previous_summary} {current_summary}".strip()
                    for offset in range(previous_end, current_end):
                        used[offset] = True
                    traces.append(f"duplicate_topic_adjacent_merged: topic={topic}")
                    continue
            if any(safe_text(existing.get("_provisional_label")) == topic for existing in merged):
                review_required = True
                traces.append(f"duplicate_topic_nonadjacent_review: topic={topic}")
            merged.append(item)
        atomics = merged

    def extraction_call(user_prompt: str) -> tuple[dict[str, Any] | None, Exception | None]:
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                response = runtime.complete_json(TOPIC_EXTRACTION_SYSTEM_PROMPT, user_prompt)
                return (response if isinstance(response, dict) else {}), None
            except Exception as exc:  # noqa: BLE001 - one retry, then a traceable source fallback
                last_error = exc
        return None, last_error

    def record_extraction_iteration(
        *, iteration: int, remaining_text: str, response: dict[str, Any] | None
    ) -> None:
        """Expose extraction decisions to an opt-in dry-run recorder only."""

        recorder = getattr(runtime, "record_topic_extraction", None)
        if not callable(recorder):
            return
        payload = response or {}
        recorder(
            {
                "source_id": source.source_id,
                "iteration": iteration,
                "remaining_text": remaining_text,
                "provisional_summary": safe_text(payload.get("provisional_summary")),
                "provisional_label": safe_text(
                    payload.get("provisional_label")
                    or payload.get("topic")
                ),
                "excerpt": safe_text(payload.get("excerpt") or payload.get("atomic_voc")),
            }
        )

    def extraction_failure_fallback(stage: str, error: Exception | None) -> tuple[list[dict[str, Any]], str, bool, list[str]]:
        source_provisional = safe_text(source.values.get("topic_provisional"))
        provisional_summary = "LLM 호출 실패로 잠정 주제 설명을 생성하지 못함"
        if source_provisional:
            provisional_summary += f"; 기존 잠정값은 {source_provisional}"
        provisional_label = TOPIC_NORMALIZATION_MAP.get(
            safe_text(source.values.get("topic")),
            safe_text(source.values.get("topic")),
        )
        if provisional_label not in CANONICAL_TOPICS:
            provisional_label = "미분류"
        error_type = type(error).__name__ if error is not None else "UnknownError"
        failure_trace = f"llm_call_failed: stage={stage} exception={error_type} attempts=2"
        traces.append(failure_trace)
        return (
            [
                {
                    "atomic_voc": text,
                    "topic_provisional": provisional_summary,
                    "_provisional_label": provisional_label,
                    "_source_span_start": 0,
                    "_source_span_end": len(text),
                    "_skip_atomic_judgment": True,
                }
            ],
            "",
            True,
            traces,
        )

    def remaining_display() -> str:
        pieces: list[str] = []
        current: list[str] = []
        for index, char in enumerate(text):
            if used[index]:
                if current:
                    pieces.append("".join(current))
                    current = []
                continue
            current.append(char)
        if current:
            pieces.append("".join(current))
        return " ".join(piece.strip() for piece in pieces if piece.strip())

    def exact_candidates(excerpt: str) -> list[tuple[int, int]]:
        candidates: list[tuple[int, int]] = []
        start = text.find(excerpt)
        while start >= 0:
            end = start + len(excerpt)
            if not any(used[start:end]):
                candidates.append((start, end))
            start = text.find(excerpt, start + 1)
        return candidates

    def whitespace_candidates(excerpt: str) -> list[tuple[int, int]]:
        target = "".join(char for char in unicodedata.normalize("NFC", excerpt) if not char.isspace())
        if not target:
            return []
        candidates: list[tuple[int, int]] = []
        for start, char in enumerate(text):
            if used[start] or char.isspace() or char != target[0]:
                continue
            cursor = start
            matched = 0
            last = start
            while cursor < len(text) and matched < len(target):
                if used[cursor]:
                    break
                if text[cursor].isspace():
                    cursor += 1
                    continue
                if text[cursor] != target[matched]:
                    break
                last = cursor
                cursor += 1
                matched += 1
            if matched == len(target):
                candidates.append((start, last + 1))
        return candidates

    for iteration in range(1, max_iterations + 1):
        before = remaining_display()
        if not before.strip():
            break
        extracted_topics = [safe_text(item.get("_provisional_label")) for item in atomics]
        extracted_excerpts = [safe_text(item.get("atomic_voc")) for item in atomics]
        response, extraction_error = extraction_call(
            build_topic_extraction_prompt(
                source,
                before,
                extracted_topics=extracted_topics,
                extracted_excerpts=extracted_excerpts,
            )
        )
        record_extraction_iteration(
            iteration=iteration,
            remaining_text=before,
            response=response,
        )
        if extraction_error is not None:
            return extraction_failure_fallback("topic_extraction", extraction_error)
        response = response or {}
        legacy_label = safe_text(response.get("topic"))
        provisional_label = safe_text(response.get("provisional_label")) or legacy_label
        provisional_summary = safe_text(response.get("provisional_summary"))
        if not provisional_summary and legacy_label:
            # Compatibility for deterministic pre-R-C3-16 test clients only.
            provisional_summary = legacy_label
        excerpt = safe_text(response.get("excerpt") or response.get("atomic_voc"))
        if provisional_label in {"", "N/A", "None", "none"}:
            traces.append(
                "topic_extraction_stopped: provisional_label=N/A "
                f"remaining_text={json.dumps(before, ensure_ascii=False)}"
            )
            break
        provisional_label = TOPIC_NORMALIZATION_MAP.get(provisional_label, provisional_label)
        if provisional_label not in CANONICAL_TOPICS:
            traces.append(
                "topic_extraction_noncanonical_normalized: "
                f"raw={provisional_label}->미분류"
            )
            provisional_label = "미분류"
        if not provisional_summary:
            provisional_summary = "잠정 주제의 근거를 서술하지 못함"
        if not excerpt:
            review_required = True
            traces.append("split_empty_excerpt")
            break

        candidates = exact_candidates(excerpt)
        if not candidates:
            candidates = whitespace_candidates(excerpt)
        if not candidates:
            repaired, repair_error = extraction_call(
                build_topic_extraction_prompt(
                    source,
                    before,
                    repair_excerpt=excerpt,
                    extracted_topics=extracted_topics,
                    extracted_excerpts=extracted_excerpts,
                )
            )
            if repair_error is not None:
                return extraction_failure_fallback("topic_extraction_repair", repair_error)
            repaired = repaired or {}
            excerpt = safe_text(repaired.get("excerpt") or repaired.get("atomic_voc"))
            candidates = exact_candidates(excerpt) if excerpt else []
            if not candidates and excerpt:
                candidates = whitespace_candidates(excerpt)
        if len(candidates) > 1:
            review_required = True
            traces.append(f"split_duplicate_excerpt_ambiguous: candidates={len(candidates)}")
            break
        if not candidates:
            review_required = True
            traces.append("split_excerpt_repair_failed")
            break

        start, end = candidates[0]
        source_excerpt = text[start:end]
        for offset in range(start, end):
            used[offset] = True
        after = remaining_display()
        if len(after) >= len(before):
            review_required = True
            traces.append("split_remaining_not_reduced")
            break
        atomics.append(
            {
                "atomic_voc": source_excerpt,
                "topic_provisional": provisional_summary,
                "_provisional_label": provisional_label,
                "_source_span_start": start,
                "_source_span_end": end,
            }
        )
    else:
        review_required = True
        traces.append(f"split_iteration_limit: max_iterations={max_iterations}")

    if not atomics:
        atomics.append(
            {
                "atomic_voc": text,
                "topic_provisional": "독립 분석 주제를 찾지 못함",
                "_provisional_label": "N/A",
                "_source_span_start": 0,
                "_source_span_end": len(text),
            }
        )
        for offset in range(len(text)):
            used[offset] = True
        traces.append("topic_extraction_na_full_source_fallback")
    else:
        order_and_merge_duplicate_topics()
        absorb_meaningful_residual()

    residual = "".join(char for index, char in enumerate(text) if not used[index])
    return atomics, residual, review_required, traces


def source_canonical_record(source: SourceRow) -> dict[str, Any]:
    """Freeze source-owned fields before topic extraction begins."""

    market = (
        safe_text(source.values.get("market"))
        or safe_text(source.values.get("region"))
        or safe_text(source.values.get("country"))
        or "KR"
    )
    language = safe_text(source.values.get("language")) or "한국어"
    probe = {
        "original_voc": source.original_voc,
        "voc_cleaned": source.voc_cleaned,
        "_parent_comment": safe_text(source.values.get("parent_comment")) or safe_text(source.values.get("parent_voc")),
        "_video_title": safe_text(source.values.get("video_title")),
        "_video_tags": safe_text(source.values.get("video_tags")),
        "_video_description": safe_text(source.values.get("video_description")),
        "_source_context_summary": safe_text(source.values.get("source_context_summary")),
        "status": safe_text(source.values.get("status")) or "normal",
        "scope_exclusion_reason": safe_text(source.values.get("scope_exclusion_reason")),
        "trace_summary": "",
    }
    category, category_source = infer_product_category_with_source(probe, source_canonical=True)
    probe["product_category"] = category
    probe["product_category_source"] = category_source
    probe["topic"] = "N/A"
    probe["topic_provisional"] = "N/A"
    probe["topic_score"] = 0
    probe["rootcause_score"] = 0
    probe["review_required"] = "N"
    normalize_scope_exclusion(probe)
    return {
        "source_id": source.source_id,
        "raw_row_index": source.raw_row_index,
        "parent_voc_id": source.parent_voc_id,
        "comment_relation": source.comment_relation,
        "original_voc": source.original_voc,
        "voc_cleaned": source.voc_cleaned,
        "reference_brand": REFERENCE_BRAND,
        "market": market,
        "language": language,
        "source_context_summary": safe_text(source.values.get("source_context_summary")),
        "status": safe_text(probe.get("status")) or "normal",
        "scope_exclusion_reason": safe_text(probe.get("scope_exclusion_reason")),
        "proposal_flag": "engine_llm",
        "video_id": safe_text(source.values.get("video_id")),
        "video_title": safe_text(source.values.get("video_title")),
        "video_url": safe_text(source.values.get("video_url")),
        "product_category": category,
        "product_category_source": category_source,
    }


RUNTIME_SYSTEM_PROMPT = """당신은 유튜브 댓글 기반 VoC 분석 엔진이다.

입력: voc_cleaned(파이썬 정제본) + parent 댓글/영상 컨텍스트.
출력: 지정 스키마의 모든 컬럼(최종값 + 중간값 + 근거 evidence + 신뢰도 confidence).

[불변 원칙]
1) 발췌 우선 — atomic_voc는 입력된 voc_cleaned에서 그대로 발췌한 텍스트다. 요약/의역/의미추가 금지. 요약은 atomic_voc_summary에만 넣는다.
2) 정제만 허용 — @호출명·이모티콘·순수 인사말 제거, 오탈자·줄임말 보정. 원문에 없는 의미를 주입하지 않는다.
4) 근거 필수 — 모든 판정값에 근거 문구/판단 단계를 evidence 컬럼에 남긴다.
5) 판단 순서 — 원문(atomic) → parent 댓글 → 영상(title→tags→description). 앞 단계에서 판단되면 멈춘다.
6) N/A 허용 — 근거 없으면 억지로 만들지 말고 N/A + 사유를 근거 컬럼에 남긴다.
7) 분석 제외 — 정제 후 내용이 없거나 운영자 안내문(제휴링크/공지), 채널/리뷰어 요청·피드백, 대상 밖 제품만 언급, 무가치 잡담, 부모가 있어도 해소 불가한 단답이면 status=scope_excluded와 scope_exclusion_reason을 함께 쓴다.
8) Primary/Secondary — 현재 정보 기준 판단이 Primary. Parent 맥락 재해석은 개선후보로만 다룬다.

[핵심 판단 규칙]
- CEJ는 인지/탐색/결정/구매/배송/사용준비/사용/관리/교체의 9단계 중 하나이며, 해당 없으면 해당없음이다. 설치만 사용준비로 매핑한다.
- reference_brand는 LG다. product_tags/product_additional_info는 자사(LG)만 담고, 경쟁사는 competitor_*에 분리한다.
- product_category는 제품군이며 로봇청소기/식기세척기/세탁기/건조기/냉장고/기타 중 하나다.
- entity_role은 product_brand/competitor_brand/creator_channel/unknown 중 하나다. 크리에이터명(귀곰 등)은 브랜드가 아니며 creator_channel이다.
- 질문형(~나요/~까요/어떤가요/어디/언제/알려주세요/후기 요청 등)이면 inquiry_flag=Y다. 다만 링크오류 신고처럼 질문이 아닌 운영 장애 보고는 문의로 과검출하지 않는다.
- 이 문의에 답하려면 설치 사양·시공 조건·설치 정책을 알아야 하는가 (→ installation_fit), 아니면 설치는 전제하고 제품이 그 환경에서 어떻게 동작하는지를 알아야 하는가 (→ usage_environment_fit)? installation_fit은 설치 가능 여부·설치 치수/사양·시공 조건·설치 정책/비용이고, usage_environment_fit은 설치 후 그 환경에서의 동작·성능·적합성이다.
- 단, 문턱·단차·매트 등 제품이 이동 중 넘는 대상에 관한 문의는 치수를 묻더라도 설치 사양이 아니라 주행 성능이므로 feature_spec이고, 이 이슈가 속한 여정 단계는 사용이다.
- Topic은 제품군과 감성을 뺀 '이유' 카테고리다. 제품명/제품군명(예: 로봇청소기, 식기세척기)과 감성어(불만족, 긍정, 우려)를 topic에 넣지 않는다.
- Topic은 카테고리 수준으로 유지하고, 구체 대상은 rootcause_target 또는 atomic_voc에 둔다.
- TEE/S 점수는 time/effort/emotion/success 각각 -5,-3,-1,0,+1,+3,+5 중 하나다. 0은 언급 없음이다.
- Success 점수는 실제 사용·목적 달성/실패 근거가 원문에 있을 때만 부여한다. 재구매 거부는 이전 사용을 시사하므로 Success 근거가 될 수 있다.
- Root Cause maturity: 0=N/A, 1=문제만, 3=문제+개선대상, 5=문제+개선대상+원인.
- 링크 오류 등 운영성 이슈는 제품 Root Cause N/A/0으로 둔다.
- 경쟁사 부정 경험을 자사 긍정으로 부호 전환하지 않는다. TEE 점수는 논의 대상 엔티티의 고객 경험을 반영한다.
- Confidence: Topic 없음=Low, Topic만=Medium, Topic+TEE 또는 RootCause 일부=High, Topic+TEE+RootCause 완결=Very High.
- Topic에는 CEJ 단계명(사용/배송/구매 등)만 단독으로 쓰지 않는다. Topic은 제품-무관 reason 또는 product_category로 스코프된 reason이어야 한다
  (예: 가격/가성비, 배송, A/S·고객응대, 앱/스마트(원격제어), 배터리, 세척 성능, 동선/주행, 물걸레).
- topic_score=0은 Topic=N/A일 때만 가능하다. Topic이 있으면 최소 1, 고객 니즈/문의/문제 해결 신호가 있으면 3 이상이다.
- market은 입력의 market_hint 또는 수집 region을 기본값으로 사용한다. 원문에 다른 국가/시장이 명시되지 않으면 market_hint를 그대로 계승한다.
- 제품 자체의 성능/기능이 아니라 리뷰어·유튜버의 테스트 방법, 시연 방식, 영상 연출, 설명 방식에 대한 비판이면 entity_role=creator_channel로 판정하고 제품 topic/TEE/RootCause 부정 점수에 반영하지 않는다.

반드시 JSON만 반환한다. JSON 구조:
{"rows": [ {스키마 컬럼: 값, ...}, ... ]}
"""

RUNTIME_SYSTEM_PROMPT = RUNTIME_SYSTEM_PROMPT.replace(
    "\n반드시 JSON만 반환한다.",
    f"\n{enum_prompt_block()}\n\n반드시 JSON만 반환한다.",
)


RUNTIME_SYSTEM_PROMPT += (
    "\n\n[Canonical Topic Taxonomy]\n"
    "The topic field MUST be exactly one of the following labels. Do not create labels outside this list:\n"
    + "\n".join(f"- {topic}" for topic in CANONICAL_TOPICS)
    + "\n\n[Canonical Topic Discipline]\n"
    "- topic is a product-decoupled, sentiment-decoupled reason label. Do not put product categories such as 로봇청소기/식기세척기 or sentiment words such as 불만족/긍정/우려 in topic.\n"
    "- product_category carries the product group. sentiment is carried by TEE/S and derived sentiment_dir, not topic.\n"
    "- Topic must fire for concrete positive or neutral aspect evaluations, not only for complaints. Do not leave concrete aspect praise as 미분류 just because sentiment is positive.\n"
    "- If a concrete aspect is present, choose that reason label regardless of sentiment: 디자인, 스팀, 물걸레, 설치/설치 편의성, 앱/스마트, etc. Put positive/negative/neutral sentiment only in TEE/S.\n"
    "- Concrete product praise without a specific aspect such as '잘 나왔다' about the product overall should be 제품 전반. Pure reactions/noise such as '가즈아', 'ㅋㅋ', '드디어!!', or channel/video praise should remain N/A.\n"
    "- Use 가격/가성비 only when the comment directly mentions price, amount, cost, discount, value-for-money, or relative expensiveness/cheapness. Do not infer 가격/가성비 from mere brand comparison, purchase hesitation, or 'which one should I buy' without price/value evidence.\n"
    "- If a comment compares brands/products without price evidence and no more specific reason label fits, use 미분류 rather than 가격/가성비.\n"
    "- If the issue is installation space/environment such as cabinet height, under-sink fit, furniture clearance, or space constraints, use 설치/설치 편의성 before mechanism/performance labels.\n"
    "- Short jokes, puns, banter, or reactions that mention nearby objects but do not actually evaluate product performance should be 미분류 or N/A; do not force them into 청소/흡입 성능 or another adjacent topic.\n"
    "- Critique of the reviewer's test method, review setup, demo scenario, or explanation quality must be entity_role=creator_channel and must not create product-brand negative TEE/S or RootCause.\n"
    "- Interpret reason labels within product_category. For example, 소모품/유지관리재 means detergent/rinse/salt for dishwashers and dust bags/filters/mop pads for robot vacuums.\n"
    "- When product_category=로봇청소기, prefer robot-vacuum specific reason labels over generic/common labels when evidence is explicit: 동선/주행, 주행/문턱돌파, 청소/흡입 성능, 장애물 회피, 물걸레, 스팀, 배터리, 먼지통/자동비움.\n"
    "- Keep common reason labels when they are the more direct issue, even for robot vacuums: 가격/가성비, 제조사 신뢰/품질, 내구성/고장, A/S·고객응대, 소모품/유지관리재, 설치/설치 편의성, 디자인, 사용 편의성(조작).\n"
    "- For robot vacuums, do not use 내구성/고장 or 사용 편의성(조작) when the actual issue is route/path/coverage/obstacle/mop/steam/battery/dust-bin performance. Use the specific robot-vacuum reason label.\n"
    "- Do not classify 걸레받이(baseboard/kickboard/under-cabinet trim) as 물걸레 unless the comment explicitly discusses mop pads, mop pressure, or mopping performance.\n"
    "- Classify 먼지봉투/filter/pad replacement or purchase as 소모품/유지관리재. Use 먼지통/자동비움 only for dust-bin/station/auto-emptying mechanism issues.\n"
    "- Do not classify generic '청소' mentions as 청소/흡입 성능 unless suction, dust/hair removal, or cleaning result/performance is the direct issue.\n"
    "- 앱/스마트(원격제어) includes software, app, map/mapping, saved maps, mapping errors, remote control, downloadable courses, app notifications, firmware, and updates.\n"
    "- If 지도/맵핑/매핑/소프트웨어/앱 is the core issue, use 앱/스마트(원격제어), not 동선/주행 or 미분류. 동선/주행 is for physical route/path/coverage/stuck-zone behavior.\n"
    "- 동선/주행 includes route/path, places the robot cannot reach, sofa/furniture-under coverage, getting stuck, route algorithms, and recognition/avoidance failure when described as physical path/navigation behavior.\n"
    "- 장애물 회피 includes obstacle/liquid/wire/pet waste avoidance success or failure. If the issue is a zone/path/coverage problem rather than obstacle detection, use 동선/주행.\n"
    "- 주행/문턱돌파 includes thresholds, steps, slopes, mats, floor-noise mats, climb/pass-over success or failure, and numeric height such as cm/센치. Indoor route/zone issues remain 동선/주행.\n"
    "- topic is a category, not a detailed solution phrase. Put details in rootcause_target or atomic_voc.\n"
    "- If the comment is only a greeting, simple reaction, review/content request, out-of-scope product request, or meaningless short answer, use topic=N/A and topic_score=0.\n"
    "- Apply N/A discipline before 미분류. Use topic=N/A for greeting, simple reaction, channel/video praise, review/content request, meaningless short answer, out-of-scope product request, pure information request, or simple purchase-intent statement.\n"
    "- Use topic=미분류 only when there is a concrete product/use/purchase opinion, experience, issue, or customer need but no canonical topic fits. For 미분류, still judge sentiment, CEJ, inquiry, and TEE/S normally, but do not assign RootCause; set rootcause_score=0 and rootcause_*='N/A'.\n"
    "\n[TEE/RootCause Anchors]\n"
    "- Use +/-3 for clear dissatisfaction/satisfaction in most cases.\n"
    "- Use +/-5 only for extreme evidence such as actual return, giving up, inability to use, or exceptional praise.\n"
    "- Concern/anxiety/distrust is negative emotion.\n"
    "- success_score is non-zero only when actual use success/failure or repurchase refusal evidence exists.\n"
    "- Use success -5 only for actual return/refund/replacement/abandonment or inability to use. Ordinary satisfaction is usually +3, not +5.\n"
    "- Ordinary strong dissatisfaction is usually emotion -3; mild annoyance/concern is -1. Reserve emotion -5 for extreme language beyond a normal complaint.\n"
    "- If Topic=N/A and the row is not scope_excluded, CEJ should usually be 해당없음, but keep 탐색/결정/구매 when the LLM evidence clearly indicates an inquiry or purchase-decision context.\n"
    "- CEJ is the journey stage where the issue/experience belongs, not necessarily the author's current shopping position.\n"
    "- Do not use CEJ to distinguish actual use from hypothetical use. Use success_score and confidence for that distinction. For example, a predicted usage inconvenience is CEJ=사용 with success_score=0.\n"
    "- Do not default substantive VoC, including 미분류, to CEJ=해당없음. 해당없음 is only for journey-unrelated operational/noise rows.\n"
    "- CEJ has nine stages: 인지=awareness/first recognition; 탐색=learning product information/specs/comparison/recommendation; 결정=whether to buy, purchase hesitation, final decision; 구매=order/payment/purchase path; 배송=delivery/logistics; 사용준비=setup/readiness before use; 사용=usage experience or usage question, including hypothetical usage inconvenience with success_score=0; 관리=maintenance/consumables/cleaning; 교체=replacement/refund/churn. Use 해당없음 only outside these stages. Never output 설치; map installation/setup readiness to 사용준비.\n"
    "- If the VoC concerns awareness or first recognition, use 인지. If it concerns confusing comparison or product information, use 탐색; if it concerns purchase hesitation/value judgment, use 결정. If it is only an operational link failure, use 해당없음.\n"
    "- If no explicit brand is mentioned but the comment is about the reviewed product category, entity_role is product_brand. If a non-LG brand is named in comparison, entity_role is competitor_brand.\n"
    "- CEJ anchors: purchase refusal or purchase hesitation at decision time=결정; delivery/logistics=배송; actual post-use replacement/refund/churn=교체; pre-use trust concern=탐색; comparison/selection inquiry=결정.\n"
    "- RootCause score 5 requires problem + target + cause. If cause is absent, do not use 5.\n"
    "- R2: topic is only the category label. Detailed solution/target phrases such as route algorithm, installation position, or battery origin go to rootcause_target/rootcause_problem, not topic.\n"
    "- R14 Gate1: pure information questions, pure comparison/selection questions, and purchase hesitation without an explicit defect/inconvenience do not receive RootCause. Examples: '다른 로청들 사용하고 추천 하는거 맞나요?', '삼성 엘지 둘중 어떤걸 사는게 베스트일까요?', '리뷰 나올때까지 기다려볼까?' => rootcause_score=0 and rootcause_* = N/A.\n"
    "- R14 Gate1: resolved or positive experience narratives do not receive RootCause. Do not reverse a tip/solution into rootcause_cause: '린스 사용하면 비린내 안나요', '냄새없고 만족합니다', or '해보니 괜찮습니다' => rootcause_score=0. Third-party purchase advice, non-product targets, and very short reactive rejection without concrete product defect also do not receive RootCause.\n"
    "- RootCause maturity anchors: no problem=0; problem only=1; problem+target=3; problem+target+cause=5. Positive praise or operational link issues are 0.\n"
    "- Do not fill rootcause_cause just because the user states a problem. A high price, distrust, vague poor quality, or comparison is usually a problem/target, not an underlying cause. Use rootcause_cause only when an explicit causal mechanism or reason is stated.\n"
    "- In comparison/recommendation sentences, preserve the subject direction. If the speaker says they use LG and then recommends a competitor because it '못 미침/못 따라감', the underperforming subject is LG/reference_brand, not the recommended competitor.\n"
    "- Vague generalized dissatisfaction without a concrete need, target, or cause is low maturity: topic_score 1 and rootcause_score 1.\n"
    "- Product/model plus price plus performance/value question is 가격/가성비. Do not mark it N/A merely because it is short.\n"
    "- Competitor feature weakness is still negative performance evaluation for that feature. Do not convert competitor weakness into a positive topic; keep sentiment in TEE/S.\n"
    "- Positive product praise should score only the TEE/S axes directly evidenced. Do not assign effort/emotion/success all +3 unless all three are explicitly supported.\n"
    "- Positive aspect evaluation should have positive tee_emotion_score (+1 mild/expected, +3 clear praise, +5 only exceptional). Factual statements or inquiries without affect should have tee_emotion_score=0.\n"
    "- Repurchase refusal or 'would not buy again' implies prior use and should be success -3 unless the evidence shows actual return/abandonment/inability to use.\n"
    "\n[Robot Vacuum Few-shot Topic Examples]\n"
    "- '로청 바보 동선, 동선 알고리즘 개선' => topic=동선/주행.\n"
    "- '쇼파 아래 청소 안 함' => topic=동선/주행.\n"
    "- '흰색 전선 인식 못함 / 강아지 쉬 못 피함' => topic=장애물 회피.\n"
    "- '4cm 문턱 못 넘음 / 매트 못 올라감' => topic=주행/문턱돌파.\n"
    "- '스팀 능력 좋다 / 스팀 배출 어디로' => topic=스팀.\n"
    "- '물걸레 압력 / 걸레판 청소 귀찮음' => topic=물걸레.\n"
    "- '배터리 문제로 스팀 방 하나 겨우' => topic=배터리.\n"
    "- '소프트웨어 비교 거의 없다' => topic=앱/스마트(원격제어).\n"
    "- '지도 바꿔댐 / 지도 2개 저장 안됨 / 맵핑 다시해라' => topic=앱/스마트(원격제어).\n"
    "- '앱 원격제어 / 다운로드 코스' => topic=앱/스마트(원격제어).\n"
    "- '스팀청소할 때 스팀배출을 어디로 하는가' => topic=스팀.\n"
    "- '디자인 역대급 / 디자인 진짜 잘 나왔어요 / 서랍장 느낌' => topic=디자인 with positive emotion.\n"
    "- '빌트인 스테이션/걸레받이 대박' => topic=디자인 if the evidence is visual/interior fit; use 설치/설치 편의성 if the evidence is installation or space-fit.\n"
    "- '싱크대 밑 들어가는거 좋아보여요' => topic=설치/설치 편의성 or 디자인 depending on whether the evidence is space-fit/installation or visual design.\n"
    "- '스팀 좋다' => topic=스팀 with positive emotion. '물걸레 좋다' => topic=물걸레 with positive emotion.\n"
    "- '먼지봉투 처리 / 히든스테이션 먼지통' => topic=먼지통/자동비움 or 소모품/유지관리재 depending on whether the issue is the robot/station bin mechanism or consumable replacement.\n"
)

RUNTIME_SYSTEM_PROMPT += (
    "\n\n[Scope Decision Order D1-beta -- apply in this exact order]\n"
    "1. If a canonical product reason is supported, assign that canonical topic.\n"
    "2. If there is substantive product VoC but no canonical topic fits, use topic='\ubbf8\ubd84\ub958'.\n"
    "3. Even without a canonical topic or substantive product detail, if there is a customer-need or sentiment signal "
    "(purchase intent/refusal, recommendation/non-recommendation, overall satisfaction/dissatisfaction), keep status='normal' "
    "and use topic='N/A'. These rows stay in the denominator and are omitted only from topic aggregation.\n"
    "4. Use status='scope_excluded' only when none of steps 1-3 applies.\n"
    "Examples that MUST remain normal with topic='N/A': '\ubb34\uc870\uac74 \uc0bd\ub2c8\ub2e4', "
    "'\ub2e4\uc74c \uc138\ub300 \uc0ac\uc57c\uaca0\ub124\uc694', '\uc548\uc0ac\uc694'. A meaningless reaction such as '\uc5b4!!' may be excluded.\n"
    "Do not use no_analytic_value when any need or sentiment signal is present.\n"
    "\n[Canonical scope_exclusion_reason definitions]\n"
    "- empty: no analyzable text remains after deterministic cleaning.\n"
    "- operator_notice: operator notice, affiliate disclosure, or promotional link dump.\n"
    "- channel_request: request addressed to the channel/operator, including a request to review another product; "
    "examples: '\ubbf8\ub2c8 \uae40\uce58\ub0c9\uc7a5\uace0\ub3c4 \ub9ac\ubdf0\ud574\uc8fc\uc138\uc694', "
    "'\uc120\ud48d\uae30 \ub9ac\ubdf0 \uc548\ud558\ub098\uc694?'.\n"
    "- channel_feedback: feedback about the channel, reviewer, presentation, or video production rather than product VoC.\n"
    "- out_of_scope_product: content only about a product outside the current analysis scope, with no relevant target-product VoC.\n"
    "- no_analytic_value: product-unrelated meaningless reaction, insult, or joke with no customer need or sentiment signal.\n"
    "- unresolvable_reply: a reply whose meaning cannot be resolved even with the available parent comment.\n"
)


def build_user_prompt(
    source: SourceRow,
    target_columns: list[str] | None = None,
    *,
    atomic_voc: str | None = None,
    sibling_atomics: Iterable[str] | None = None,
    topic_provisional: str | None = None,
) -> str:
    target_columns = target_columns or TARGET_COLUMNS
    # R-C3-05 absorbs the former topic-only CALL2 into this atomic judgment.
    llm_target_columns = [
        column
        for column in target_columns
        if column not in ENGINE_OWNED_COLUMNS and column != "topic_provisional"
    ]
    payload = {
        "analysis_brand": REFERENCE_BRAND,
        "target_columns": llm_target_columns,
        "input": {
            "judgment_target_atomic_voc": safe_text(atomic_voc) or source.voc_cleaned,
            "full_voc_cleaned_context": source.voc_cleaned,
            "sibling_atomic_context": [safe_text(value) for value in (sibling_atomics or ())],
            "topic_provisional": safe_text(topic_provisional),
            "cleaning_stats": {
                "original_length": len(source.original_voc),
                "cleaned_length": len(source.voc_cleaned),
                "length_ratio": source.cleaning_length_ratio,
            },
            "parent_text": safe_text(source.values.get("parent_voc")) or safe_text(source.values.get("parent_comment")),
            "existing_analysis_text_reference_only": safe_text(source.values.get("analysis_text")),
            "video_context": {
                "title": safe_text(source.values.get("video_title")),
                "tags": safe_text(source.values.get("video_tags")),
                "description": safe_text(source.values.get("video_description")),
            },
            "market_hint": (
                safe_text(source.values.get("market"))
                or safe_text(source.values.get("region"))
                or safe_text(source.values.get("country"))
            ),
            "source_context_summary": safe_text(source.values.get("source_context_summary")),
        },
        "output_requirements": [
            "rows에는 지정된 atomic 하나의 전체 판정 결과 한 행만 출력한다.",
            "target_columns에 지정된 모든 컬럼을 포함한다. 엔진 소유 컬럼은 출력하지 않는다.",
            "topic을 포함한 모든 atomic 단위 판정을 한 번에 출력한다.",
            "atomic_voc는 judgment_target_atomic_voc를 변형 없이 그대로 출력한다.",
            "전문과 형제 조각은 의미 해석을 돕기 위한 참고 자료다. 판정 대상은 지정된 atomic 하나뿐이며, 근거는 그 atomic 안에서 인용한다. 다른 조각의 내용을 이번 판정의 근거로 삼지 않는다.",
            "entity_role은 댓글 작성자가 atomic_voc/parent_text에서 직접 언급한 주체를 기준으로 판단한다. video_context/source_context_summary의 브랜드명만으로 competitor_brand로 판정하지 않는다.",
            "근거가 없으면 evidence에는 N/A 사유를 쓴다.",
            "정답지 예문을 암기하지 말고 현재 입력 원문을 분석한다.",
            "market은 명시적 반증이 없으면 input.market_hint를 계승한다.",
            "status=scope_excluded이면 scope_exclusion_reason을 허용값 중 하나로 반드시 채운다.",
            "status가 scope_excluded가 아니면 scope_exclusion_reason은 비운다.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_atomic_judgment_prompt(
    source: SourceRow,
    atomic_voc: str,
    sibling_atomics: Iterable[str],
    topic_provisional: str,
) -> str:
    """Build the full-judgment prompt with prose only, never the internal label."""

    payload = json.loads(
        build_user_prompt(
            source,
            atomic_voc=atomic_voc,
            sibling_atomics=sibling_atomics,
            topic_provisional=topic_provisional,
        )
    )
    payload["rc316_topic_rules"] = [
        "The supplied topic_provisional is free prose for context, not an answer label; judge topic independently.",
        "Use 기타(제품명) only when the product category is known and no established topic label fits after full review.",
        "When using 기타(제품명), explain in topic_evidence why established labels do not fit.",
        "If the product category is not identifiable, use 미분류 rather than 기타(제품명).",
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


TOPIC_RECALL_SYSTEM_PROMPT = """당신은 VoC atomic 단위 topic 재판정기다.

입력으로 주어진 atomic_voc 하나에 대해서만 topic을 재판정한다.
CEJ, TEE, RootCause, inquiry, need_signal, product_category 등 다른 필드는 절대 판단하거나 출력하지 않는다.
반드시 JSON 형식으로, 아래 canonical_topics 중 하나만 topic으로 출력한다.
"""


def build_topic_recall_prompt(source: SourceRow, atomic_voc: str, topic_provisional: str) -> str:
    payload = {
        "reference_brand": REFERENCE_BRAND,
        "canonical_topics": CANONICAL_TOPICS,
        "input": {
            "source_id": source.source_id,
            "atomic_voc": atomic_voc,
            "topic_provisional": topic_provisional,
            "parent_voc": safe_text(source.values.get("parent_voc")) or safe_text(source.values.get("parent_comment")),
            "video_title": safe_text(source.values.get("video_title")),
            "video_tags": safe_text(source.values.get("video_tags")),
            "video_description": safe_text(source.values.get("video_description")),
            "source_context_summary": safe_text(source.values.get("source_context_summary")),
        },
        "output_schema": {"topic": "one canonical topic only"},
        "rules": [
            "atomic_voc 본문을 최우선 근거로 삼는다.",
            "parent/video 컨텍스트는 제품군·맥락 보조에만 사용한다.",
            "여러 atomic이 분리된 원문이라도 현재 atomic_voc 밖의 내용을 끌어오지 않는다.",
            "topic 외 다른 필드는 출력하지 않는다.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def needs_topic_recall(source: SourceRow, candidate: dict[str, Any]) -> bool:
    """Deprecated compatibility hook; R-C3-05 absorbs CALL2 into atomic judgment."""

    return False


def apply_topic_recall(
    source: SourceRow,
    payload: dict[str, Any],
    runtime: OpenAIChatClient,
) -> tuple[dict[str, Any], int]:
    """Deprecated compatibility hook; no second LLM call is made."""

    return payload, 0


class OpenAIChatClient:
    def __init__(
        self,
        model: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = DEFAULT_OPENAI_MAX_RETRIES,
    ) -> None:
        load_dotenv()
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, int(max_retries))
        self._rate_limit_lock = threading.Lock()
        self._rate_limit_resume_at = 0.0
        if not self.api_key:
            raise LLMRuntimeUnavailable(
                "OPENAI_API_KEY is not available. Actual LLM runtime analysis cannot run."
            )

    def _wait_for_rate_limit_window(self) -> None:
        with self._rate_limit_lock:
            sleep_seconds = max(0.0, self._rate_limit_resume_at - time.time())
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    def _record_rate_limit_delay(self, delay_seconds: float) -> None:
        resume_at = time.time() + max(0.0, delay_seconds)
        with self._rate_limit_lock:
            self._rate_limit_resume_at = max(self._rate_limit_resume_at, resume_at)

    @classmethod
    def _rate_limit_retry_delay(cls, detail: str, attempt: int, headers: Any | None = None) -> float:
        header_value = ""
        if headers is not None:
            try:
                header_value = str(headers.get("Retry-After") or "")
            except Exception:
                header_value = ""
        try:
            parsed = float(header_value) if header_value else 0.0
        except ValueError:
            parsed = 0.0
        if parsed <= 0:
            match = RATE_LIMIT_RETRY_SECONDS_RE.search(detail or "")
            if match:
                try:
                    parsed = float(match.group(1))
                except ValueError:
                    parsed = 0.0
        if parsed > 0:
            return min(60.0, parsed + 0.5)
        index = min(max(0, int(attempt)), len(RATE_LIMIT_BACKOFF_SECONDS) - 1)
        return RATE_LIMIT_BACKOFF_SECONDS[index]

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        started = time.time()
        for attempt in range(self.max_retries + 1):
            try:
                self._wait_for_rate_limit_window()
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    raw = resp.read().decode("utf-8")
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < self.max_retries:
                    delay_seconds = self._rate_limit_retry_delay(detail, attempt, exc.headers)
                    self._record_rate_limit_delay(delay_seconds)
                    time.sleep(delay_seconds)
                    continue
                raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from exc
            except Exception as exc:
                raise RuntimeError(f"OpenAI request failed after {time.time() - started:.1f}s: {exc}") from exc
        parsed = json.loads(raw)
        content = parsed["choices"][0]["message"]["content"]
        return json.loads(content)


def normalize_score(value: Any, allowed: set[int], default: int = 0) -> int:
    text = safe_text(value).replace("+", "")
    try:
        parsed = int(float(text))
    except Exception:
        return default
    return parsed if parsed in allowed else default


def normalize_flag(value: Any) -> str:
    text = safe_text(value).upper()
    return "Y" if text == "Y" else "N"


def _score_as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def compute_confidence(row: dict[str, Any]) -> None:
    """Apply the deterministic data-dictionary #47 confidence formula."""

    has_topic = safe_text(row.get("topic")) not in {"", "N/A", "미분류"}
    has_tee = any(
        _score_as_int(row.get(f"tee_{axis}_score")) != 0
        for axis in ("time", "effort", "emotion", "success")
    )
    has_rc = (
        _score_as_int(row.get("rootcause_score")) > 0
        and safe_text(row.get("rootcause_problem")) not in {"", "N/A"}
    )

    if not has_topic:
        row["confidence_rating"] = "Low"
    elif has_tee and has_rc:
        row["confidence_rating"] = "Very High"
    elif has_tee:
        row["confidence_rating"] = "High"
    else:
        row["confidence_rating"] = "Medium"


def normalize_step_confidence(row: dict[str, Any]) -> None:
    """Keep the six step-confidence fields on their documented 3-step scale."""

    canonical_by_casefold = {value.casefold(): value for value in STEP_CONFIDENCE_VALUES | {"Very High"}}
    for column in STEP_CONFIDENCE_COLS:
        raw_value = safe_text(row.get(column))
        normalized = canonical_by_casefold.get(raw_value.casefold(), raw_value)
        if normalized == "Very High":
            row[column] = "High"
            append_trace(row, f"step_confidence_very_high_clamped: {column}=Very High->High")
        elif normalized in STEP_CONFIDENCE_VALUES:
            row[column] = normalized
        else:
            row[column] = "Low"
            append_trace(row, f"step_confidence_invalid_reset: {column}={raw_value}")


def analysis_blob(row: dict[str, Any]) -> str:
    """Combine LLM-produced judgement fields for generic consistency checks."""

    return " ".join(
        safe_text(row.get(key))
        for key in [
            "topic",
            "atomic_voc",
            "atomic_voc_summary",
            "product",
            "product_tags",
            "product_additional_info",
            "competitor_brand_tags",
            "competitor_product_tags",
            "topic_evidence",
            "cej_evidence",
            "inquiry_type",
            "need_signal_type",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_cause",
            "rootcause_summary",
            "tee_time_evidence",
            "tee_effort_evidence",
            "tee_emotion_evidence",
            "tee_success_evidence",
        ]
    )


def _not_empty_label(value: Any) -> bool:
    return safe_text(value) not in {"", "N/A", "None", "none", "unknown"}


def _has_problem_signal(row: dict[str, Any]) -> bool:
    return any(
        _not_empty_label(row.get(key))
        for key in [
            "rootcause_problem",
            "rootcause_target",
            "rootcause_cause",
            "rootcause_summary",
        ]
    ) or int(row.get("rootcause_score") or 0) > 0


def _has_tee_signal(row: dict[str, Any]) -> bool:
    return any(
        int(row.get(key) or 0) != 0
        for key in ["tee_time_score", "tee_effort_score", "tee_emotion_score", "tee_success_score"]
    )


def is_low_value_na_candidate(row: dict[str, Any], canonical: str, explicit_low_value: bool) -> bool:
    """Return True for rows that must remain N/A before 미분류 is considered.

    This gate intentionally relies on LLM-produced semantic fields. It avoids
    raw-string case tokens while keeping review requests, pure information
    requests, out-of-scope requests, and simple purchase-intent statements from
    being promoted to `미분류`.
    """

    if explicit_low_value:
        return True
    if safe_text(row.get("status")) == "scope_excluded":
        return True
    inquiry_type = safe_text(row.get("inquiry_type"))
    need_type = safe_text(row.get("need_signal_type"))
    entity_role = safe_text(row.get("entity_role"))
    has_problem = _has_problem_signal(row)
    has_tee = _has_tee_signal(row)
    if entity_role == "creator_channel" or is_creator_review_method_critique(row):
        return True
    if (
        not has_problem
        and safe_text(row.get("inquiry_flag")) != "Y"
        and safe_text(row.get("need_signal_flag")) != "Y"
        and int(row.get("tee_time_score") or 0) == 0
        and int(row.get("tee_effort_score") or 0) == 0
        and int(row.get("tee_success_score") or 0) == 0
        and int(row.get("tee_emotion_score") or 0) > 0
    ):
        return canonical in {"", "N/A"} or canonical in LOW_VALUE_TOPIC_ALIASES
    if inquiry_type in LOW_VALUE_INQUIRY_TYPES and need_type in LOW_VALUE_NEED_TYPES and not has_problem and not has_tee:
        return True
    if need_type in LOW_VALUE_NEED_TYPES and inquiry_type in {"none", "review_request", "product_identification", "other_question"} and not has_problem and not has_tee:
        return True
    if need_type in PURCHASE_ONLY_NEED_TYPES and inquiry_type not in SUBSTANTIVE_INQUIRY_TYPES and not has_problem and not has_tee:
        return True
    return canonical in LOW_VALUE_TOPIC_ALIASES


def is_substantive_voc(row: dict[str, Any]) -> bool:
    """Return True when the LLM output describes a real product VoC.

    This intentionally uses only LLM-produced fields, not answer-key strings.
    Unknown/out-of-taxonomy product VoC should become `미분류`, while true
    noise remains N/A and may be wiped by the N/A discipline.
    """

    if safe_text(row.get("status")) == "scope_excluded":
        return False
    inquiry_type = safe_text(row.get("inquiry_type"))
    need_type = safe_text(row.get("need_signal_type"))
    if _has_problem_signal(row):
        return True
    if safe_text(row.get("inquiry_flag")) == "Y" and inquiry_type in SUBSTANTIVE_INQUIRY_TYPES:
        return True
    if safe_text(row.get("need_signal_flag")) == "Y" and need_type in SUBSTANTIVE_NEED_TYPES:
        return True
    if _has_tee_signal(row):
        return True
    return False


CREATOR_REVIEW_METHOD_CONTEXT_TOKENS = (
    "리뷰",
    "리뷰어",
    "유튜버",
    "테스트",
    "시연",
    "영상",
    "연출",
    "검증",
    "설명",
    "비교 방식",
    "테스트 방식",
    "테스트 방법",
)
CREATOR_REVIEW_METHOD_CRITIQUE_TOKENS = (
    "상식적인",
    "수준의 테스트",
    "테스트를 봤으면",
    "보여줬으면",
    "봤으면 좋",
    "아쉽",
    "부족",
    "제대로",
    "공정",
    "비교가 없",
    "시연이",
    "영상이",
)


def is_creator_review_method_critique(row: dict[str, Any]) -> bool:
    """Detect critique of the creator/reviewer method rather than product VoC.

    This is a generic semantic guard for comments about testing/review/demo
    quality.  It prevents those rows from being counted as product-brand
    negative improvement tasks.
    """

    haystack = row_evidence_haystack(row)
    if not _contains_any(haystack, CREATOR_REVIEW_METHOD_CONTEXT_TOKENS):
        return False
    if not _contains_any(haystack, CREATOR_REVIEW_METHOD_CRITIQUE_TOKENS):
        return False
    # Explicit product-use failure should remain a product VoC. A hypothetical
    # phrase such as "고장만 안 나면" is not an actual failure report.
    if _contains_any(haystack, ("샀는데", "써보니", "사용해보니", "고장남", "고장 났", "고장났", "불량", "에러", "환불", "교체")):
        return False
    return True


def apply_creator_review_method_discipline(row: dict[str, Any]) -> None:
    if not is_creator_review_method_critique(row):
        return
    row["entity_role"] = "creator_channel"
    row["brand"] = "creator_channel"
    row["topic"] = "N/A"
    row["topic_score"] = 0
    row["rootcause_problem"] = "N/A"
    row["rootcause_target"] = "N/A"
    row["rootcause_cause"] = "N/A"
    row["rootcause_summary"] = "N/A(리뷰/테스트 방식 비판)"
    row["rootcause_score"] = 0
    row["tee_time_score"] = 0
    row["tee_effort_score"] = 0
    row["tee_emotion_score"] = 0
    row["tee_success_score"] = 0
    row["cej"] = "해당없음"
    row["review_required"] = "Y"
    trace = safe_text(row.get("trace_summary"))
    note = "creator_channel_review_method_guard: 제품 자체가 아닌 리뷰/테스트 방식 비판"
    row["trace_summary"] = f"{trace} | {note}" if trace else note


def _product_token_matches(text: str, token: str) -> bool:
    haystack = safe_text(text).lower()
    needle = safe_text(token).lower()
    if not haystack or not needle:
        return False
    if re.fullmatch(r"[가-힣]+", needle):
        return re.search(rf"(?<![가-힣]){re.escape(needle)}", haystack) is not None
    if re.fullmatch(r"[a-z0-9]+", needle):
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    return needle in haystack


def _detect_product_categories(text: str) -> tuple[str, ...]:
    haystack = safe_text(text).lower()
    if not haystack:
        return ()
    return tuple(
        category
        for category, tokens in PRODUCT_CATEGORY_TOKEN_MAP.items()
        if any(
            _product_token_matches(haystack, token)
            for token in tokens
            if token not in AMBIGUOUS_PRODUCT_TOKENS
        )
    )


def _detect_product_category(text: str) -> str:
    categories = _detect_product_categories(text)
    return categories[0] if categories else ""


PRODUCT_OWNERSHIP_OR_USE_CUES = (
    "샀", "구매했", "쓰고 있", "쓰고있", "사용 중", "사용중", "사용하고", "설치했",
)
PRODUCT_HOME_CONTEXT_CUES = ("우리집", "저희집", "우리 집")
PRODUCT_DIRECT_EXPERIENCE_CUES = (
    "소음", "냄새", "고장", "불량", "안돼", "안 돼", "불편", "커요", "작아요",
)


def _categories_with_usage_context(text: str, categories: tuple[str, ...]) -> tuple[str, ...]:
    haystack = safe_text(text).lower()
    if not haystack:
        return ()
    matches: list[str] = []
    for category in categories:
        spans: list[int] = []
        for token in PRODUCT_CATEGORY_TOKEN_MAP[category]:
            start = haystack.find(token.lower())
            if start >= 0:
                spans.append(start)
        for start in spans:
            after = haystack[start: start + 40]
            around = haystack[max(0, start - 30): start + 70]
            if (
                any(cue in after for cue in PRODUCT_OWNERSHIP_OR_USE_CUES)
                or any(cue in around for cue in PRODUCT_HOME_CONTEXT_CUES + PRODUCT_DIRECT_EXPERIENCE_CUES)
            ):
                matches.append(category)
                break
    return tuple(dict.fromkeys(matches))


def _has_specific_appliance_scope_text(text: str) -> bool:
    haystack = safe_text(text).lower()
    if not haystack:
        return False
    concrete_terms: list[str] = []
    for tokens in PRODUCT_CATEGORY_TOKEN_MAP.values():
        concrete_terms.extend(str(token) for token in tokens)
    concrete_terms.extend(EXTENDED_APPLIANCE_SCOPE_TERMS)
    return any(term.lower() in haystack for term in concrete_terms if term)


def _has_housing_out_of_scope_context(row: dict[str, Any]) -> bool:
    context = _product_category_text(
        row,
        (
            "video_title",
            "video_tags",
            "video_description",
            "source_context_summary",
            "_video_title",
            "_video_tags",
            "_video_description",
            "_source_context_summary",
            "original_voc",
            "voc_cleaned",
            "atomic_voc",
            "atomic_voc_summary",
        ),
    ).lower()
    return any(term in context for term in HOUSING_OUT_OF_SCOPE_CONTEXT_TERMS)


def _has_housing_architecture_only_comment_text(text: str) -> bool:
    haystack = safe_text(text).lower()
    if not haystack:
        return False
    return any(term in haystack for term in HOUSING_ARCHITECTURE_ONLY_COMMENT_TERMS)


def _has_smart_cottage_product_service_text(text: str) -> bool:
    haystack = safe_text(text).lower()
    if not haystack:
        return False
    return any(term in haystack for term in SMART_COTTAGE_PRODUCT_SERVICE_TERMS)


def _user_product_scope_text(row: dict[str, Any]) -> str:
    return _product_category_text(
        row,
        (
            "original_voc",
            "voc_cleaned",
            "atomic_voc",
            "atomic_voc_summary",
            "parent_comment",
            "parent_voc",
            "parent_voc_text",
            "_parent_comment",
            "_parent_voc",
        ),
    )


def _has_product_review_or_issue_cue(text: str) -> bool:
    haystack = safe_text(text).lower()
    for cue in PRODUCT_REVIEW_OR_ISSUE_CUES:
        cue_text = safe_text(cue).lower()
        if not cue_text:
            continue
        if re.fullmatch(r"[a-z0-9]+", cue_text):
            if re.search(rf"(?<![a-z0-9]){re.escape(cue_text)}(?![a-z0-9])", haystack):
                return True
        elif cue_text in haystack:
            return True
    return False


def _is_incidental_product_presence_mention(row: dict[str, Any], category: str) -> bool:
    user_text = _user_product_scope_text(row).lower()
    if not user_text or not _has_housing_out_of_scope_context(row):
        return False
    if category != "식기세척기":
        return False
    if any(korean_term in user_text for korean_term in ("식기세척기", "식세기")):
        return False
    if "dishwasher" not in user_text:
        return False
    if _has_product_review_or_issue_cue(user_text):
        return False
    return any(cue in user_text for cue in INCIDENTAL_PRODUCT_PRESENCE_CUES)


def apply_misc_out_of_scope_product_guard(row: dict[str, Any]) -> None:
    """Exclude only pure housing/interior comments inside miscellaneous housing contexts."""

    if safe_text(row.get("status")) == "scope_excluded":
        return
    if safe_text(row.get("product_category")) != "기타":
        return
    if not _has_housing_out_of_scope_context(row):
        return
    user_scope_text = _user_product_scope_text(row)
    incidental_presence = _is_incidental_product_presence_mention(row, "식기세척기")
    if not incidental_presence and _has_specific_appliance_scope_text(user_scope_text):
        return
    if not incidental_presence and _has_smart_cottage_product_service_text(user_scope_text):
        return
    if not incidental_presence and not _has_housing_architecture_only_comment_text(user_scope_text):
        return
    row["status"] = "scope_excluded"
    row["scope_exclusion_reason"] = "out_of_scope_product"
    row["topic"] = "N/A"
    row["topic_provisional"] = safe_text(row.get("topic_provisional")) or "분석 대상 제품 범위 밖의 내용"
    row["topic_score"] = 0
    row["rootcause_score"] = 0
    row["review_required"] = "N"
    clear_rootcause_details_when_score_zero(row)
    append_trace(row, "misc_product_housing_scope_excluded")


def _product_category_text(row: dict[str, Any], fields: Iterable[str]) -> str:
    return " ".join(safe_text(row.get(field)) for field in fields)


def has_product_category_conflict(
    detected_categories: Iterable[str], final_category: str
) -> bool:
    """Return whether text evidence names a category other than the final one."""

    return bool(set(detected_categories) - {final_category})


def infer_product_category_with_source(
    row: dict[str, Any], *, source_canonical: bool = False
) -> tuple[str, str]:
    """Infer product family in the designed 3-step order.

    Text evidence wins over parent context. Video metadata is only a fallback
    when no product signal exists in the comment/atomic text or parent.
    """

    frozen_category = safe_text(row.get("_source_canonical_product_category"))
    if frozen_category and not source_canonical:
        return frozen_category, safe_text(row.get("_source_canonical_product_category_source")) or "text"

    # Use one user-authored layer only. Concatenating original/cleaned/atomic
    # duplicates the same sentence and can falsely associate a cue with a
    # different product mention in the duplicated copy.
    text = (
        (safe_text(row.get("voc_cleaned")) or safe_text(row.get("original_voc")))
        if source_canonical
        else (
            safe_text(row.get("atomic_voc"))
            or safe_text(row.get("voc_cleaned"))
            or safe_text(row.get("original_voc"))
        )
    )
    text_categories = _detect_product_categories(text)
    usage_categories = _categories_with_usage_context(text, text_categories)
    if len(usage_categories) == 1:
        text_category = usage_categories[0]
        if _is_incidental_product_presence_mention(row, text_category):
            append_trace(row, f"product_category_incidental_presence_reset: {text_category}->기타")
            return "기타", "text"
        return text_category, "text"
    incidental_categories = tuple(
        category
        for category in text_categories
        if _is_incidental_product_presence_mention(row, category)
    )
    if incidental_categories:
        append_trace(
            row,
            "product_category_incidental_presence_reset: "
            + ",".join(incidental_categories)
            + "->기타",
        )

    parent_category = _detect_product_category(
        _product_category_text(
            row,
            (
                "parent_comment",
                "parent_voc",
                "parent_voc_text",
                "_parent_comment",
                "_parent_voc",
            ),
        )
    )
    if parent_category:
        return parent_category, "parent"

    video_category = _detect_product_category(
        _product_category_text(
            row,
            (
                "video_title",
                "video_tags",
                "video_description",
                "source_context_summary",
                "_video_title",
                "_video_tags",
                "_video_description",
                "_source_context_summary",
            ),
        )
    )
    if video_category:
        conflicting_categories = tuple(
            category for category in text_categories if category != video_category
        )
        if has_product_category_conflict(text_categories, video_category) and safe_text(row.get("status")) != "scope_excluded":
            row["review_required"] = "Y"
            append_trace(
                row,
                "product_category_conflict_review: detected="
                + ",".join(conflicting_categories)
                + f" final={video_category}",
            )
        if text_categories:
            append_trace(
                row,
                "product_category_text_ambiguous_fallback_to_video: "
                + ",".join(text_categories),
            )
        else:
            append_trace(row, "product_category_fallback_to_video: no_text_product_evidence")
        return video_category, "video"
    video_text = _product_category_text(
        row,
        (
            "video_title",
            "video_tags",
            "video_description",
            "_video_title",
            "_video_tags",
            "_video_description",
        ),
    )
    other_by_design = (
        safe_text(row.get("scope_exclusion_reason")) == "out_of_scope_product"
        or _has_housing_out_of_scope_context(row)
        or bool(safe_text(video_text))
    )
    if other_by_design:
        append_trace(row, "product_category_other_by_design")
    else:
        if safe_text(row.get("status")) != "scope_excluded":
            row["review_required"] = "Y"
        append_trace(row, "product_category_unresolved: no_text_parent_or_video_evidence")
    return "기타", "text"


def infer_product_category(row: dict[str, Any]) -> str:
    """Backward-compatible category-only wrapper."""

    return infer_product_category_with_source(row)[0]


def row_evidence_haystack(row: dict[str, Any]) -> str:
    """Collect topic evidence fields for conservative normalization guards."""

    return " ".join(
        safe_text(row.get(field))
        for field in (
            "topic",
            "topic_evidence",
            "original_voc",
            "voc_cleaned",
            "atomic_voc",
            "atomic_voc_summary",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_summary",
            "trace_summary",
        )
    ).lower()


def semantic_evidence_haystack(row: dict[str, Any]) -> str:
    """Evidence text excluding the model's own final topic label.

    Guards that check whether a topic is justified must not treat the LLM's
    proposed topic string as supporting evidence for itself.
    """

    return " ".join(
        safe_text(row.get(field))
        for field in (
            "original_voc",
            "voc_cleaned",
            "atomic_voc",
            "atomic_voc_summary",
            "topic_evidence",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_summary",
            "need_signal_summary",
            "need_signal_evidence",
            "trace_summary",
        )
    ).lower()


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token.lower() in text for token in tokens)


def has_direct_price_value_evidence(row: dict[str, Any]) -> bool:
    # Price/value assignment must be grounded in the user's actual wording.
    # LLM-generated evidence/rootcause text can over-infer "가격" from generic
    # purchase hesitation, so it is intentionally excluded here.
    haystack = safe_text(row.get("atomic_voc")).lower()
    return _contains_any(haystack, PRICE_VALUE_DIRECT_TOKENS)


def _compact_match_text(text: str) -> str:
    return re.sub(r"\s+", "", safe_text(text).lower())


def _requires_korean_left_boundary(term: str) -> bool:
    value = safe_text(term).lower()
    return bool(value) and re.match(r"[가-힣]", value) is not None


def _requires_ascii_word_boundary(term: str) -> bool:
    value = safe_text(term).lower()
    return bool(value) and re.search(r"[a-z0-9]", value) is not None


def _contains_evidence_term(text: str, term: str) -> bool:
    if not term:
        return False
    if _requires_ascii_word_boundary(term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    if not _requires_korean_left_boundary(term):
        return term in text
    start = text.find(term)
    while start >= 0:
        if start == 0 or not re.match(r"[가-힣]", text[start - 1]):
            return True
        start = text.find(term, start + 1)
    return False


def _matchable_evidence_term(term: str) -> str:
    value = safe_text(term).lower()
    if not value:
        return ""
    return value


def _evidence_term_matches(text: str, compact_text: str, term: str) -> bool:
    value = _matchable_evidence_term(term)
    if not value:
        return False
    if not _contains_evidence_term(text, value):
        return False
    exclusions = tuple(safe_text(item).lower() for item in get_evidence_excludes(term))
    if not exclusions:
        return True

    candidate_starts: list[int] = []
    start = text.find(value)
    while start >= 0:
        if _requires_ascii_word_boundary(value):
            left_ok = start == 0 or not re.match(r"[a-z0-9]", text[start - 1])
            end = start + len(value)
            right_ok = end == len(text) or not re.match(r"[a-z0-9]", text[end])
            boundary_ok = left_ok and right_ok
        elif _requires_korean_left_boundary(value):
            boundary_ok = start == 0 or not re.match(r"[가-힣]", text[start - 1])
        else:
            boundary_ok = True
        if boundary_ok:
            candidate_starts.append(start)
        start = text.find(value, start + 1)

    for candidate_start in candidate_starts:
        candidate_end = candidate_start + len(value)
        covered_by_exclusion = False
        for exclusion in exclusions:
            exclusion_start = text.find(exclusion)
            while exclusion_start >= 0:
                exclusion_end = exclusion_start + len(exclusion)
                if exclusion_start <= candidate_start and candidate_end <= exclusion_end:
                    covered_by_exclusion = True
                    break
                exclusion_start = text.find(exclusion, exclusion_start + 1)
            if covered_by_exclusion:
                break
        if not covered_by_exclusion:
            return True
    return False


def _has_substantive_peer_term(terms: tuple[str, ...]) -> bool:
    return any(
        len("".join(re.findall(r"[0-9a-z가-힣]+", term.lower()))) > 1
        for term in terms
    )


def topic_evidence_matches(atomic_voc: str, product_category: str) -> list[dict[str, Any]]:
    """Return YAML-backed E1 label matches using *only* atomic_voc.

    Phase 1 fixes the scope to atomic_voc only.  Including voc_cleaned would
    reintroduce whole-comment evidence leakage between split atomic rows.
    """

    atomic_text = safe_text(atomic_voc).lower()
    if not atomic_text:
        return []
    compact_text = _compact_match_text(atomic_text)
    scope = PRODUCT_CATEGORY_LEXICON_SCOPE.get(safe_text(product_category), "common")
    matches: list[dict[str, Any]] = []
    for index, entry in enumerate(get_labels_for_scope(scope)):
        if entry.fallback_only:
            continue
        raw_matched_terms = tuple(
            term
            for term in entry.evidence_terms
            if _evidence_term_matches(atomic_text, compact_text, term)
        )
        matched_terms = raw_matched_terms if _has_substantive_peer_term(raw_matched_terms) else ()
        if not matched_terms:
            continue
        max_term_len = max(len(re.sub(r"\s+", "", term)) for term in matched_terms)
        matches.append(
            {
                "label": entry.label,
                "scope": entry.scope,
                "terms": matched_terms,
                "scope_rank": 1 if entry.scope != "common" else 0,
                "match_count": len(matched_terms),
                "max_term_len": max_term_len,
                "order": index,
            }
        )
    return matches


def select_e1_topic_match(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda item: (
            int(item["scope_rank"]),
            int(item["match_count"]),
            int(item["max_term_len"]),
            -int(item["order"]),
        ),
        reverse=True,
    )[0]


def apply_evidence_guard(row: dict[str, Any], canonical: str) -> str:
    """Apply taxonomy §7 E1 evidence guard without touching price_value_guard.

    The legacy price_value_guard runs earlier in ``normalize_topic_label`` and
    still inspects original_voc+voc_cleaned+atomic_voc.  This E1 layer is broader
    but intentionally atomic-only, so it never weakens RT-08's direct price guard.
    """

    if safe_text(row.get("status")) == "scope_excluded":
        return canonical
    atomic_voc = safe_text(row.get("atomic_voc"))
    if not atomic_voc:
        return canonical
    other_topic_categories = {
        "기타(로봇청소기)": "로봇청소기",
        "기타(식기세척기)": "식기세척기",
        "기타(세탁기)": "세탁기",
        "기타(냉장고)": "냉장고",
    }
    current = safe_text(canonical)
    if current in other_topic_categories:
        product_category = safe_text(row.get("product_category")) or infer_product_category(row)
        expected_category = other_topic_categories[current]
        append_trace(row, "기타 라벨 · E1 미적용")
        if product_category != expected_category:
            row["review_required"] = "Y"
            append_trace(
                row,
                "other_topic_product_category_mismatch: "
                f"topic={current} product_category={product_category or 'unknown'} "
                f"expected={expected_category}",
            )
        return canonical
    if is_contextless_joke_reaction(row):
        return canonical
    protected = protected_common_topic(row)
    if protected in {"설치/설치 편의성"} and safe_text(canonical) == protected:
        return canonical

    product_category = safe_text(row.get("product_category")) or infer_product_category(row)
    matches = topic_evidence_matches(atomic_voc, product_category)
    if not matches:
        if current not in {"", "N/A", "미분류", "제품 전반", "프로모션"}:
            row["review_required"] = "Y"
            row["topic_evidence"] = "N/A: 원문 근거 없음"
            append_trace(row, f"e1_evidence_guard: no_atomic_evidence_for_topic={current}")
            return "미분류"
        return canonical

    labels = [TOPIC_NORMALIZATION_MAP.get(str(item["label"]), str(item["label"])) for item in matches]
    unique_labels = list(dict.fromkeys(labels))
    selected = select_e1_topic_match(matches)
    if selected is None:
        return canonical
    if len(unique_labels) >= 2:
        append_trace(row, "e2_split_candidate: " + ", ".join(unique_labels))

    selected_label = TOPIC_NORMALIZATION_MAP.get(str(selected["label"]), str(selected["label"]))
    terms = ", ".join(str(term) for term in selected["terms"])
    if selected_label != current:
        row["review_required"] = "Y"
        append_trace(row, f"e1_evidence_guard: {current or 'blank'} -> {selected_label}; terms={terms}")
        evidence = safe_text(row.get("topic_evidence"))
        note = f"E1 evidence_guard({selected_label}): {terms}"
        row["topic_evidence"] = f"{evidence} | {note}" if evidence and evidence != "N/A: 근거 없음" else note
        return selected_label
    if terms:
        evidence = safe_text(row.get("topic_evidence"))
        if "E1 evidence_guard" not in evidence:
            note = f"E1 evidence_guard({selected_label}): {terms}"
            row["topic_evidence"] = f"{evidence} | {note}" if evidence and evidence != "N/A: 근거 없음" else note
    return canonical


def is_install_environment_issue(row: dict[str, Any]) -> bool:
    haystack = " ".join(
        safe_text(row.get(field))
        for field in (
            "atomic_voc",
            "atomic_voc_summary",
            "topic_evidence",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_summary",
            "need_signal_summary",
            "need_signal_evidence",
            "trace_summary",
        )
    ).lower()
    return _contains_any(haystack, INSTALL_ENVIRONMENT_TOKENS)


def is_contextless_joke_reaction(row: dict[str, Any]) -> bool:
    haystack = semantic_evidence_haystack(row)
    user_text = " ".join(
        safe_text(row.get(field))
        for field in ("original_voc", "voc_cleaned", "atomic_voc")
    ).lower()
    original_only = safe_text(row.get("original_voc")).lower()
    compact_user_text = re.sub(r"\s+", "", original_only)
    if (
        len(compact_user_text) <= 12
        and _contains_any(original_only, SHORT_REACTION_ONLY_TOKENS)
        and not _contains_any(original_only, PRODUCT_OR_ASPECT_EVIDENCE_TOKENS)
    ):
        return True
    if not _contains_any(haystack, CONTEXTLESS_REACTION_TOKENS):
        return False
    if _contains_any(haystack, ("국산", "국내산", "중국", "제조국", "odm", "jdm")):
        return False
    if _contains_any(haystack, ("흡입", "청소 성능", "청소 결과", "안 빨", "못 빨", "제거", "성능")):
        return False
    # Keep substantive problem/inquiry rows. This guard is only for banter or
    # adjacent visual reactions that the LLM over-eagerly maps to a nearby
    # product aspect.
    if safe_text(row.get("inquiry_flag")) == "Y" and safe_text(row.get("inquiry_type")) in SUBSTANTIVE_INQUIRY_TYPES:
        return False
    return True


def is_actual_durability_failure(row: dict[str, Any]) -> bool:
    haystack = " ".join(
        safe_text(row.get(field))
        for field in (
            "atomic_voc",
            "atomic_voc_summary",
            "topic_evidence",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_summary",
            "need_signal_summary",
            "need_signal_evidence",
            "trace_summary",
        )
    ).lower()
    return _contains_any(
        haystack,
        (
            "고장남",
            "고장 났",
            "고장났",
            "망가",
            "부러",
            "불량",
            "에러",
            "작동 안",
            "안 켜",
            "수리",
            "교체",
            "환불",
        ),
    )


def aspect_reason_from_evidence(row: dict[str, Any]) -> str:
    """Recover concrete aspect topics that the LLM sometimes leaves as 미분류.

    This is intentionally generic and aspect-based: it does not replay an
    answer-key row. It only upgrades rows that already carry direct evidence for
    a concrete reason label while preserving sentiment in TEE/S.
    """

    haystack = " ".join(
        safe_text(row.get(field))
        for field in (
            "atomic_voc",
            "atomic_voc_summary",
            "topic_evidence",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_summary",
            "need_signal_summary",
            "need_signal_evidence",
            "trace_summary",
        )
    ).lower()
    if is_install_environment_issue(row):
        return "설치/설치 편의성"
    if "걸레받이" in haystack and "스팀" not in haystack and not _contains_any(
        haystack, ("물걸레", "걸레판", "걸레 압력")
    ):
        if _contains_any(haystack, ("설치", "직배수", "하부장", "싱크대 밑", "공간에 들어")):
            return "설치/설치 편의성"
        return "디자인"
    if _contains_any(haystack, ("싱크대 밑", "하부장 밑", "공간에 들어", "빌트인")) and not _contains_any(
        haystack, ("먼지통", "더스트백", "먼지봉투", "자동비움")
    ):
        return "설치/설치 편의성"
    if _contains_any(haystack, ("디자인", "비주얼", "인테리어", "서랍장", "가구 같", "가구같", "예쁘", "깔끔")):
        return "디자인"
    if "스팀" in haystack:
        return "스팀"
    if _contains_any(haystack, ("물걸레", "걸레판", "물걸레 압력", "걸레 압력", "반복으로 닦")):
        return "물걸레"
    if _contains_any(haystack, POSITIVE_EVALUATION_TOKENS) and not _contains_any(
        haystack, ("영상", "편집", "채널", "댓글", "귀곰")
    ):
        return "제품 전반"
    return ""


def protected_common_topic(row: dict[str, Any]) -> str:
    """Keep explicit common reason labels from being swallowed by robot-specific labels."""

    haystack = " ".join(
        safe_text(row.get(field))
        for field in (
            "topic_evidence",
            "atomic_voc",
            "atomic_voc_summary",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_summary",
        )
    ).lower()
    if is_install_environment_issue(row):
        return "설치/설치 편의성"
    if "걸레받이" in haystack and "스팀" not in haystack and not _contains_any(
        haystack, ("물걸레", "걸레판", "걸레 압력")
    ):
        if _contains_any(haystack, ("공간활용", "깔끔", "가구", "비주얼", "인테리어")):
            return "디자인"
        if _contains_any(haystack, ("설치", "직배수", "하부장")):
            return "설치/설치 편의성"
        return "사용 편의성(조작)"
    if "먼지봉투" in haystack and not _contains_any(
        haystack, ("먼지통", "자동비움", "히든스테이션", "스테이션용", "내장된 작은 먼지봉투")
    ):
        return "소모품/유지관리재"
    for topic, tokens in COMMON_TOPIC_PROTECTION_RULES:
        if topic == "내구성/고장" and not is_actual_durability_failure(row):
            continue
        if _contains_any(haystack, tokens):
            return topic
    if _contains_any(haystack, ("13년째", "오래 사용", "계속 사용중")) and _contains_any(
        haystack, ("as부품", "부품", "문제가 없")
    ):
        return "내구성/고장"
    return ""


def robot_vacuum_priority_topic(row: dict[str, Any]) -> str:
    """Prefer robot-vacuum specific reason labels when evidence is explicit."""

    product_category = safe_text(row.get("product_category")) or infer_product_category(row)
    if product_category != "로봇청소기":
        return ""
    haystack = " ".join(
        safe_text(row.get(field))
        for field in (
            "topic",
            "topic_evidence",
            "atomic_voc",
            "atomic_voc_summary",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_summary",
            "trace_summary",
        )
    ).lower()
    if "걸레받이" in haystack and "스팀" not in haystack and not _contains_any(
        haystack, ("물걸레", "걸레판", "물걸레 압력")
    ):
        return ""
    for topic, tokens in ROBOT_VACUUM_TOPIC_PRIORITY_RULES:
        if any(token.lower() in haystack for token in tokens):
            return topic
    return ""


def ensure_topic_provisional_summary(row: dict[str, Any], reason: str) -> None:
    """Fill a missing provisional summary without copying the canonical topic."""

    if safe_text(row.get("topic_provisional")):
        return
    row["topic_provisional"] = "잠정 주제 설명 없음"
    append_trace(row, reason)


def normalize_topic_label(row: dict[str, Any]) -> None:
    """Normalize LLM topic labels to the canonical taxonomy.

    This function reads only the LLM-produced label, never the raw comment.
    It is a schema contract normalizer, not an answer-key replay.
    """

    topic = safe_text(row.get("topic"))
    canonical = TOPIC_NORMALIZATION_MAP.get(topic, topic)
    inquiry_type = safe_text(row.get("inquiry_type"))
    need_type = safe_text(row.get("need_signal_type"))
    inquiry_flag = safe_text(row.get("inquiry_flag"))
    entity_role = safe_text(row.get("entity_role"))
    explicit_low_value = canonical in (LOW_VALUE_TOPIC_ALIASES - {"N/A"})
    if is_low_value_na_candidate(row, canonical, explicit_low_value):
        canonical = "N/A"
    if canonical == "가격/가성비" and not has_direct_price_value_evidence(row):
        row["review_required"] = "Y"
        trace = safe_text(row.get("trace_summary"))
        note = "price_value_guard: 가격/가성비 직접 근거 없음"
        row["trace_summary"] = f"{trace} | {note}" if trace else note
        canonical = "미분류"
    if canonical == "내구성/고장" and has_direct_price_value_evidence(row) and not is_actual_durability_failure(row):
        canonical = "가격/가성비"
        trace = safe_text(row.get("trace_summary"))
        note = "topic_rootcause_alignment_guard: 실제 고장 경험보다 가격 부담 근거가 직접적"
        row["trace_summary"] = f"{trace} | {note}" if trace else note
    if canonical == "제품 전반" and inquiry_flag == "Y" and need_type in {"price_value_need", "content_information_need"} and has_direct_price_value_evidence(row):
        canonical = "가격/가성비"
    if canonical == "A/S·고객응대" and (need_type == "trust_safety_need" or inquiry_type == "as_trust_quality"):
        canonical = "A/S·고객응대"
    product_category, product_category_source = infer_product_category_with_source(row)
    row["product_category"] = product_category
    row["product_category_source"] = product_category_source
    common_priority = protected_common_topic(row)
    if common_priority:
        canonical = common_priority
    else:
        robot_priority = robot_vacuum_priority_topic(row)
        if robot_priority:
            canonical = robot_priority
    if canonical in {"N/A", "미분류", "제품 전반"}:
        aspect_reason = aspect_reason_from_evidence(row)
        if aspect_reason:
            canonical = aspect_reason
    if is_contextless_joke_reaction(row) and canonical not in {"", "N/A", "프로모션"}:
        row["review_required"] = "Y"
        trace = safe_text(row.get("trace_summary"))
        note = "contextless_reaction_guard: topic 직접 근거 부족"
        row["trace_summary"] = f"{trace} | {note}" if trace else note
        canonical = "미분류"
    scoped_canonical = PRODUCT_CATEGORY_TOPIC_SCOPE_MAP.get(product_category, {}).get(canonical, canonical)
    if scoped_canonical == "미분류" and canonical != "미분류":
        row["review_required"] = "Y"
        trace = safe_text(row.get("trace_summary"))
        scope_note = f"product_scope_review: product_category={product_category}, original_topic={canonical}"
        row["trace_summary"] = f"{trace} | {scope_note}" if trace else scope_note
    canonical = scoped_canonical
    canonical = apply_evidence_guard(row, canonical)
    if canonical == "N/A" and not explicit_low_value and is_substantive_voc(row):
        canonical = "미분류"
    elif canonical not in CANONICAL_TOPICS:
        canonical = "미분류" if is_substantive_voc(row) else "N/A"
    row["topic"] = canonical
    if canonical in LOW_VALUE_TOPIC_ALIASES:
        row["topic"] = "N/A"
        row["topic_score"] = 0
    ensure_topic_provisional_summary(row, "topic_provisional_summary_missing_after_normalization")


def normalize_entity_role(row: dict[str, Any]) -> None:
    """Route obvious LLM-extracted competitor entities to competitor columns."""

    if is_creator_review_method_critique(row):
        row["entity_role"] = "creator_channel"
        row["brand"] = "creator_channel"
        return

    fields = [
        safe_text(row.get("brand")),
        safe_text(row.get("product")),
        safe_text(row.get("product_tags")),
        safe_text(row.get("competitor_brand_tags")),
        safe_text(row.get("competitor_product_tags")),
    ]
    joined = " ".join(fields)
    joined_lower = joined.lower()
    comment_context = " ".join(
        [
            safe_text(row.get("atomic_voc")),
            safe_text(row.get("original_voc")),
            safe_text(row.get("voc_cleaned")),
            safe_text(row.get("_parent_comment")),
            safe_text(row.get("parent_voc")),
        ]
    ).lower()
    metadata_context = " ".join(
        [
            safe_text(row.get("source_context_summary")),
            safe_text(row.get("video_title")),
            safe_text(row.get("video_url")),
        ]
    ).lower()
    brand = safe_text(row.get("brand"))
    product = safe_text(row.get("product"))
    looks_like_non_lg_entity = (
        brand
        and brand not in {"LG", "엘지", "N/A", "unknown", "creator_channel"}
        and not any(creator in brand for creator in ["귀곰", "피크", "끼룩"])
    )
    has_competitor_comment_evidence = any(name in comment_context for name in COMPETITOR_ENTITY_NAMES_LOWER)
    explicit_competitor_fields = " ".join(
        [
            safe_text(row.get("competitor_brand_tags")),
            safe_text(row.get("competitor_product_tags")),
        ]
    ).lower()
    has_explicit_competitor_field = any(name in explicit_competitor_fields for name in COMPETITOR_ENTITY_NAMES_LOWER)
    if has_competitor_comment_evidence or has_explicit_competitor_field or looks_like_non_lg_entity:
        row["entity_role"] = "competitor_brand"
        if not safe_text(row.get("competitor_brand_tags")) or safe_text(row.get("competitor_brand_tags")) == "N/A":
            found = [
                name
                for name in COMPETITOR_ENTITY_NAMES
                if name.lower() in joined_lower or name.lower() in comment_context
            ]
            if not found and looks_like_non_lg_entity:
                found = [brand]
            row["competitor_brand_tags"] = "; ".join(sorted(set(found)))
        if safe_text(row.get("product_tags")) and safe_text(row.get("product_tags")) != "N/A":
            row["competitor_product_tags"] = safe_text(row.get("competitor_product_tags")) or safe_text(row.get("product_tags"))
            row["product_tags"] = ""
            row["product_additional_info"] = ""
    elif any(name in metadata_context for name in COMPETITOR_ENTITY_NAMES_LOWER):
        if safe_text(row.get("entity_role")) == "competitor_brand":
            row["entity_role"] = "unknown"
            append_trace(row, "entity_role_metadata_competitor_ignored")
        if safe_text(row.get("entity_role")) == "unknown" and safe_text(row.get("topic")) not in {"", "N/A", "프로모션"}:
            row["entity_role"] = "product_brand"
    elif safe_text(row.get("entity_role")) == "unknown" and safe_text(row.get("topic")) not in {"", "N/A", "프로모션"}:
        row["entity_role"] = "product_brand"


def clamp_tee_scores(row: dict[str, Any]) -> None:
    """Apply generic TEE score anchors without raw-string answer branches."""

    concern = ["걱정", "우려", "불안", "못믿", "신중"]
    for score_col, evidence_col in [
        ("tee_time_score", "tee_time_evidence"),
        ("tee_effort_score", "tee_effort_evidence"),
        ("tee_emotion_score", "tee_emotion_evidence"),
        ("tee_success_score", "tee_success_evidence"),
    ]:
        score = int(row.get(score_col) or 0)
        evidence = safe_text(row.get(evidence_col))
        if score != 0 and evidence in {"", "N/A", "None", "none", "N/A: 근거 없음", "0=언급없음"}:
            row[score_col] = 0
            continue
        if score_col == "tee_emotion_score" and score in {-5, 5}:
            row[score_col] = -3 if score < 0 else 3
        if score_col == "tee_success_score" and score == 5:
            row[score_col] = 3
        if score_col == "tee_time_score" and score != 0 and not any(token in evidence for token in ["오래", "지연", "매번", "반복", "기다", "시간", "3주"]):
            row[score_col] = 0
        if score_col == "tee_emotion_score" and any(token in evidence for token in concern) and int(row.get(score_col) or 0) > 0:
            row[score_col] = -3

    success_evidence = safe_text(row.get("tee_success_evidence"))
    if int(row.get("tee_success_score") or 0) != 0 and success_evidence in {"", "N/A", "None", "none", "N/A: 근거 없음", "0=언급없음"}:
        row["tee_success_score"] = 0


def align_aspect_sentiment(row: dict[str, Any]) -> None:
    """Keep sentiment separate from topic while preserving clear praise signals."""

    topic = safe_text(row.get("topic"))
    if topic in {"", "N/A", "미분류", "프로모션"}:
        return
    if int(row.get("tee_emotion_score") or 0) != 0:
        return
    haystack = " ".join(
        safe_text(row.get(field))
        for field in (
            "topic",
            "topic_evidence",
            "atomic_voc",
            "atomic_voc_summary",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_summary",
            "trace_summary",
        )
    ).lower()
    if not _contains_any(haystack, POSITIVE_EVALUATION_TOKENS):
        return
    if _contains_any(haystack, NEGATIVE_EVALUATION_TOKENS):
        return
    row["tee_emotion_score"] = 3 if _contains_any(haystack, STRONG_POSITIVE_EVALUATION_TOKENS) else 1
    if safe_text(row.get("tee_emotion_evidence")) in {"", "N/A", "None", "none", "0=언급없음"}:
        row["tee_emotion_evidence"] = "구체 aspect에 대한 긍정 평가 표현"


R14_GATE1_QUESTION_INQUIRY_TYPES = {
    "feature_spec",
    "product_comparison",
    "product_identification",
    "other_question",
}
R14_GATE1_DECISION_NEED_TYPES = {
    "purchase_confidence_need",
    "conversion_signal",
    "content_information_need",
    "low_value",
    "none",
}
R14_EXPLICIT_PROBLEM_TEXT_TOKENS = (
    "고장",
    "불량",
    "오류",
    "문제",
    "누수",
    "냄새",
    "소음",
    "불편",
    "안됨",
    "안 되",
    "안돼",
    "못",
    "지연",
    "오래걸",
    "반품",
    "환불",
    "교체",
)
REFERENCE_BRAND_CONTEXT_TOKENS = ("LG", "엘지", "엘쥐")
REFERENCE_BRAND_OWNERSHIP_TOKENS = ("쓰는데", "쓰고", "사용", "4년째", "몇년째")
COMPETITOR_RECOMMENDATION_TOKENS = ("사세요", "사라", "추천", "가세요")
UNDERPERFORMANCE_COMPARISON_TOKENS = ("못미침", "못 미침", "못미치", "못 미치", "못따라", "못 따라", "한참 못")
R14_RESOLVED_OR_POSITIVE_RESULT_TOKENS = (
    "안나요",
    "안 나요",
    "안나네요",
    "안 나네요",
    "안나",
    "안 나",
    "없고",
    "없네요",
    "없어요",
    "냄새없",
    "문제없",
    "괜찮",
    "괜춘",
    "갠춘",
    "만족",
    "해결",
)
R14_SOLUTION_OR_EXPERIENCE_CUES = (
    "사용하면",
    "쓰면",
    "하면",
    "하니",
    "해보니",
    "넣고",
    "바꾸고",
    "잘라서",
    "대신",
    "팁",
    "노하우",
    "저도",
    "전",
    "쓰는데",
    "쓰고",
    "사용",
    "후기",
)
R14_THIRD_PARTY_ADVICE_TOKENS = ("판매자", "기사님", "직원", "타인이", "남들이")
R14_THIRD_PARTY_NEGATIVE_ADVICE_TOKENS = ("사지말", "사지 말", "절대 사지", "권장하지", "말라")
R14_NON_PRODUCT_ROOTCAUSE_TARGET_TOKENS = ("냄비", "오징어")
R14_SHORT_REACTION_TOKENS = ("탈락", "패스", "안사", "안 사")


def is_r14_gate1_excluded_rootcause(row: dict[str, Any]) -> bool:
    if int(row.get("rootcause_score") or 0) <= 0:
        return False
    if safe_text(row.get("status")) == "scope_excluded":
        return True
    inquiry_type = safe_text(row.get("inquiry_type"))
    need_type = safe_text(row.get("need_signal_type"))
    is_question_or_decision = (
        safe_text(row.get("inquiry_flag")) == "Y"
        and inquiry_type in R14_GATE1_QUESTION_INQUIRY_TYPES
        and need_type in R14_GATE1_DECISION_NEED_TYPES
    )
    if not is_question_or_decision:
        return False
    atomic_text = safe_text(row.get("atomic_voc"))
    if _contains_any(atomic_text, R14_EXPLICIT_PROBLEM_TEXT_TOKENS):
        return False
    if int(row.get("tee_time_score") or 0) != 0 or int(row.get("tee_effort_score") or 0) != 0 or int(row.get("tee_success_score") or 0) != 0:
        return False
    return True


def reset_rootcause_for_r14_gate1(row: dict[str, Any]) -> None:
    row["rootcause_problem"] = "N/A"
    row["rootcause_target"] = "N/A"
    row["rootcause_cause"] = "N/A"
    row["rootcause_summary"] = "N/A(R14 Gate1: 순수 질문/비교/구매고민)"
    row["rootcause_score"] = 0
    append_trace(row, "r14_gate1_rootcause_reset")


def reset_rootcause_for_unclassified_topic(row: dict[str, Any]) -> None:
    row["rootcause_problem"] = "N/A"
    row["rootcause_target"] = "N/A"
    row["rootcause_cause"] = "N/A"
    row["rootcause_summary"] = "N/A(topic=미분류: RootCause 미부여)"
    row["rootcause_score"] = 0
    append_trace(row, "topic_unclassified_rootcause_reset")


def _compact_korean_text(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def is_r14_experience_narrative_excluded_rootcause(row: dict[str, Any]) -> tuple[bool, str]:
    if int(row.get("rootcause_score") or 0) <= 0:
        return False, ""
    if safe_text(row.get("status")) == "scope_excluded":
        return True, "scope_excluded"
    atomic_text = safe_text(row.get("atomic_voc"))
    if not atomic_text:
        return False, ""
    rootcause_text = " ".join(
        safe_text(row.get(field))
        for field in ("rootcause_problem", "rootcause_target", "rootcause_cause", "rootcause_summary")
    )
    positive_or_resolved = _contains_any(atomic_text, R14_RESOLVED_OR_POSITIVE_RESULT_TOKENS)
    solution_or_experience = _contains_any(atomic_text, R14_SOLUTION_OR_EXPERIENCE_CUES)
    if positive_or_resolved and solution_or_experience:
        return True, "resolved_positive_experience"
    if "후기" in atomic_text and not _contains_any(atomic_text, R14_EXPLICIT_PROBLEM_TEXT_TOKENS):
        return True, "experience_review_without_problem"
    if (
        _contains_any(atomic_text, R14_THIRD_PARTY_ADVICE_TOKENS)
        and _contains_any(atomic_text, R14_THIRD_PARTY_NEGATIVE_ADVICE_TOKENS)
    ):
        return True, "third_party_advice"
    if _contains_any(rootcause_text, R14_NON_PRODUCT_ROOTCAUSE_TARGET_TOKENS):
        return True, "non_product_target"
    compact = _compact_korean_text(atomic_text)
    if len(compact) <= 18 and _contains_any(atomic_text, R14_SHORT_REACTION_TOKENS):
        return True, "short_reaction"
    return False, ""


def reset_rootcause_for_r14_experience_narrative(row: dict[str, Any], reason: str) -> None:
    row["rootcause_problem"] = "N/A"
    row["rootcause_target"] = "N/A"
    row["rootcause_cause"] = "N/A"
    row["rootcause_summary"] = f"N/A(R14 Gate1: 경험담/해결/인용/반응성 문장 - {reason})"
    row["rootcause_score"] = 0
    append_trace(row, f"r14_experience_rootcause_reset: {reason}")


def _mentioned_competitors(row: dict[str, Any]) -> list[str]:
    explicit = [
        item.strip()
        for item in re.split(r"[;,/|]", safe_text(row.get("competitor_brand_tags")))
        if item.strip()
    ]
    atomic_text = safe_text(row.get("atomic_voc")).lower()
    found = [
        name
        for name in COMPETITOR_ENTITY_NAMES
        if name.lower() in atomic_text or name in safe_text(row.get("atomic_voc"))
    ]
    return list(dict.fromkeys(explicit + found))


def is_reference_brand_underperformance_reversed(row: dict[str, Any]) -> tuple[bool, str]:
    atomic_text = safe_text(row.get("atomic_voc"))
    if not atomic_text:
        return False, ""
    atomic_text_lower = atomic_text.lower()
    competitors = _mentioned_competitors(row)
    if not competitors:
        return False, ""
    judgment_text = " ".join(
        safe_text(row.get(field))
        for field in ("rootcause_problem", "rootcause_target", "rootcause_summary")
    )
    if not any(competitor in judgment_text for competitor in competitors):
        return False, ""
    if not _contains_any(atomic_text_lower, REFERENCE_BRAND_CONTEXT_TOKENS):
        return False, ""
    if not _contains_any(atomic_text_lower, REFERENCE_BRAND_OWNERSHIP_TOKENS):
        return False, ""
    if not _contains_any(atomic_text_lower, COMPETITOR_RECOMMENDATION_TOKENS):
        return False, ""
    if not _contains_any(atomic_text_lower, UNDERPERFORMANCE_COMPARISON_TOKENS):
        return False, ""
    return True, competitors[0]


def correct_rootcause_subject_direction(row: dict[str, Any]) -> None:
    reversed_subject, competitor = is_reference_brand_underperformance_reversed(row)
    if not reversed_subject:
        return
    product_category = safe_text(row.get("product_category")) or "제품"
    row["rootcause_problem"] = f"LG {product_category}가 {competitor} 대비 성능이 부족하다는 평가"
    row["rootcause_target"] = f"LG {product_category}"
    row["rootcause_cause"] = "N/A"
    row["rootcause_summary"] = f"화자는 LG 사용 경험을 근거로 {competitor}를 추천하며, 부족한 주체는 추천 대상({competitor})이 아니라 LG라고 표현함"
    row["rootcause_score"] = min(int(row.get("rootcause_score") or 3), 3)
    append_trace(row, f"rootcause_subject_direction_guard: target=LG, comparator={competitor}")


def clamp_rootcause_score(row: dict[str, Any]) -> None:
    """Apply RootCause maturity constraints."""

    topic = safe_text(row.get("topic"))
    summary = safe_text(row.get("rootcause_summary"))
    problem = safe_text(row.get("rootcause_problem"))
    target = safe_text(row.get("rootcause_target"))
    cause = safe_text(row.get("rootcause_cause"))
    if topic == "N/A" or topic == "프로모션" or summary.startswith("N/A"):
        row["rootcause_score"] = 0
        clear_rootcause_details_when_score_zero(row)
        return
    if topic == "미분류":
        reset_rootcause_for_unclassified_topic(row)
        return
    if is_r14_gate1_excluded_rootcause(row):
        reset_rootcause_for_r14_gate1(row)
        return
    excluded_experience, experience_reason = is_r14_experience_narrative_excluded_rootcause(row)
    if excluded_experience:
        reset_rootcause_for_r14_experience_narrative(row, experience_reason)
        return
    correct_rootcause_subject_direction(row)
    problem = safe_text(row.get("rootcause_problem"))
    target = safe_text(row.get("rootcause_target"))
    cause = safe_text(row.get("rootcause_cause"))
    summary = safe_text(row.get("rootcause_summary"))
    if cause in {"", "N/A", "None", "none"}:
        if target in {"", "N/A", "None", "none"}:
            row["rootcause_score"] = 1 if problem not in {"", "N/A", "None", "none"} else 0
        else:
            row["rootcause_score"] = 3
    elif target in {"", "N/A", "None", "none"}:
        row["rootcause_score"] = 1 if problem not in {"", "N/A", "None", "none"} else 0
    elif problem in {"", "N/A", "None", "none"}:
        row["rootcause_score"] = 0
    else:
        row["rootcause_score"] = 5


def apply_na_and_promo_discipline(row: dict[str, Any]) -> None:
    topic = safe_text(row.get("topic"))
    inquiry_type = safe_text(row.get("inquiry_type"))
    need_type = safe_text(row.get("need_signal_type"))
    if topic == "프로모션":
        evidence_blob = " ".join([safe_text(row.get("topic_evidence")), safe_text(row.get("cej_evidence"))])
        atomic_text = safe_text(row.get("atomic_voc"))
        if inquiry_type == "purchase_path_link" and "구매 가능" in evidence_blob and not any(token in atomic_text for token in ["링크", "경로", "네이버", "쿠팡", "지마켓"]):
            row["topic"] = "N/A"
            row["topic_score"] = 0
            row["cej"] = "결정"
            row["rootcause_score"] = 0
            ensure_topic_provisional_summary(row, "topic_provisional_summary_missing_after_na_promo_discipline")
            clear_rootcause_details_when_score_zero(row)
            return
        if inquiry_type in {"review_request", "product_identification"} and need_type == "content_information_need":
            row["topic"] = "N/A"
            row["topic_score"] = 0
            row["rootcause_score"] = 0
            ensure_topic_provisional_summary(row, "topic_provisional_summary_missing_after_na_promo_discipline")
            clear_rootcause_details_when_score_zero(row)
            if inquiry_type == "product_identification":
                row["inquiry_type"] = "review_request"
            return
        row["topic_score"] = 1
        row["rootcause_score"] = 0
        row["rootcause_problem"] = "N/A" if safe_text(row.get("rootcause_problem")) in {"", "N/A", "링크 오류"} else row["rootcause_problem"]
        row["rootcause_target"] = "N/A"
        row["rootcause_cause"] = "N/A"
        row["rootcause_summary"] = "N/A(운영성/구매경로 이슈)"
        clear_rootcause_details_when_score_zero(row)
        if safe_text(row.get("need_signal_type")) == "problem_solution_need":
            row["need_signal_flag"] = "N"
            row["need_signal_type"] = "none"
        link_evidence = " ".join(
            [
                safe_text(row.get("topic_evidence")),
                safe_text(row.get("cej_evidence")),
                safe_text(row.get("rootcause_problem")),
            ]
        )
        if inquiry_type == "purchase_path_link":
            row["cej"] = "해당없음" if any(token in link_evidence for token in ["오류", "안열", "장애"]) else "구매"
    if topic == "N/A":
        row["topic_score"] = 0
        row["rootcause_score"] = 0
        ensure_topic_provisional_summary(row, "topic_provisional_summary_missing_after_na_discipline")
        row["tee_time_score"] = 0
        row["tee_effort_score"] = 0
        row["tee_emotion_score"] = 0
        row["tee_success_score"] = 0
        blob = analysis_blob(row)
        if safe_text(row.get("entity_role")) == "unknown" and any(token in blob for token in ["영상", "편집", "채널", "댓글"]):
            row["entity_role"] = "creator_channel"
        if (
            safe_text(row.get("inquiry_flag")) == "Y"
            and inquiry_type in {"", "none", "product_identification", "other_question"}
            and need_type in {"", "none", "content_information_need", "low_value"}
            and not _has_problem_signal(row)
            and not _has_tee_signal(row)
        ):
            row["inquiry_type"] = "review_request"
        if safe_text(row.get("status")) == "scope_excluded":
            row["cej"] = "해당없음"
        elif safe_text(row.get("cej")) not in {"탐색", "결정", "구매"} or safe_text(row.get("inquiry_flag")) != "Y":
            row["cej"] = "해당없음"
        clear_rootcause_details_when_score_zero(row)


def normalize_cej(row: dict[str, Any]) -> None:
    blob = analysis_blob(row)
    topic = safe_text(row.get("topic"))
    cej = safe_text(row.get("cej"))
    cej_aliases = {"설치": "사용준비"}
    if cej in cej_aliases:
        normalized = cej_aliases[cej]
        row["cej"] = normalized
        append_trace(row, f"cej_value_normalized: {cej}->{normalized}")
        cej = normalized
    if cej == "이탈":
        row["cej"] = "해당없음"
        cej = "해당없음"
    if topic == "제조사 신뢰/품질" and int(row.get("tee_success_score") or 0) == 0:
        row["cej"] = "탐색"
        return
    if cej in ALLOWED_CEJ_VALUES:
        return
    if cej not in {"", "N/A", "None", "none"}:
        row["cej"] = "해당없음"
        append_trace(row, f"cej_value_invalid_reset: {cej}")
        return
    if cej == "해당없음":
        return
    if safe_text(row.get("status")) == "scope_excluded" or topic == "N/A":
        row["cej"] = "해당없음"
        return
    inquiry_type = safe_text(row.get("inquiry_type"))
    need_type = safe_text(row.get("need_signal_type"))
    if topic == "배송":
        row["cej"] = "배송"
    elif topic in {"소모품/유지관리재", "A/S·고객응대"}:
        row["cej"] = "관리"
    elif topic in {"프로모션"}:
        row["cej"] = "구매" if inquiry_type == "purchase_path_link" else "해당없음"
    elif inquiry_type in {"product_comparison", "feature_spec", "product_identification", "as_trust_quality"}:
        row["cej"] = "탐색"
    elif inquiry_type in {"promotion_benefit", "purchase_path_link"} or need_type in {
        "purchase_confidence_need",
        "price_value_need",
        "conversion_signal",
        "purchase_path_need",
    }:
        row["cej"] = "결정"
    elif inquiry_type == "usage_environment_fit" or need_type in {
        "feature_need",
        "environment_fit_need",
        "problem_solution_need",
    }:
        row["cej"] = "사용"
    elif _has_tee_signal(row) or _has_problem_signal(row):
        row["cej"] = "사용"
    else:
        row["cej"] = "탐색"


def finalize_score_fields(row: dict[str, Any]) -> None:
    """Ensure score columns are always concrete machine-safe values."""

    row["topic_score"] = normalize_score(row.get("topic_score"), {0, 1, 3, 5})
    row["tee_time_score"] = normalize_score(row.get("tee_time_score"), {-5, -3, -1, 0, 1, 3, 5})
    row["tee_effort_score"] = normalize_score(row.get("tee_effort_score"), {-5, -3, -1, 0, 1, 3, 5})
    row["tee_emotion_score"] = normalize_score(row.get("tee_emotion_score"), {-5, -3, -1, 0, 1, 3, 5})
    row["tee_success_score"] = normalize_score(row.get("tee_success_score"), {-5, -3, -1, 0, 1, 3, 5})
    row["rootcause_score"] = normalize_score(row.get("rootcause_score"), {0, 1, 3, 5})


def enforce_topic_not_blank(row: dict[str, Any]) -> None:
    """Keep the export contract from emitting an empty topic cell."""

    if safe_text(row.get("topic")):
        return
    row["topic"] = "N/A"
    row["topic_score"] = 0
    if not safe_text(row.get("topic_provisional")):
        row["topic_provisional"] = "최종 topic이 비어 있어 N/A로 정규화됨"
    append_trace(row, "topic_blank_normalized_to_na")


def clear_rootcause_details_when_score_zero(row: dict[str, Any]) -> None:
    """RootCause detail text is not valid when rootcause_score is 0."""

    if int(row.get("rootcause_score") or 0) != 0:
        return
    fields = ("rootcause_problem", "rootcause_target", "rootcause_cause", "rootcause_summary")
    had_detail = any(
        safe_text(row.get(field)) not in {"", "N/A", "None", "none"} and not safe_text(row.get(field)).startswith("N/A")
        for field in fields
    )
    row["rootcause_problem"] = "N/A"
    row["rootcause_target"] = "N/A"
    row["rootcause_cause"] = "N/A"
    summary = safe_text(row.get("rootcause_summary"))
    if not summary:
        row["rootcause_summary"] = "N/A"
    elif not summary.startswith("N/A"):
        row["rootcause_summary"] = "N/A(rootcause_score=0: detail reset)"
    if had_detail:
        append_trace(row, "rootcause_zero_detail_reset")


def normalize_inquiry_need_types(row: dict[str, Any]) -> None:
    """Keep inquiry_type and need_signal_type within their own enum domains."""

    inquiry_type = safe_text(row.get("inquiry_type")) or "none"
    need_type = safe_text(row.get("need_signal_type")) or "none"
    if inquiry_type in INQUIRY_TYPE_ALIASES:
        normalized = INQUIRY_TYPE_ALIASES[inquiry_type]
        row["inquiry_type"] = normalized
        append_trace(row, f"inquiry_type_alias_normalized: {inquiry_type}->{normalized}")
        inquiry_type = normalized

    if need_type in NEED_SIGNAL_TYPE_ALIASES:
        normalized = NEED_SIGNAL_TYPE_ALIASES[need_type]
        row["need_signal_type"] = normalized
        row["need_signal_flag"] = "Y"
        append_trace(row, f"need_signal_type_alias_normalized: {need_type}->{normalized}")
        need_type = normalized

    if inquiry_type not in ALLOWED_INQUIRY_TYPES:
        if inquiry_type in NEED_VALUE_MISPLACED_IN_INQUIRY:
            if need_type in {"", "none"} or need_type not in ALLOWED_NEED_SIGNAL_TYPES:
                row["need_signal_type"] = inquiry_type
                row["need_signal_flag"] = "Y"
                need_type = inquiry_type
            row["inquiry_type"] = "none"
            row["inquiry_flag"] = "N"
            append_trace(row, f"inquiry_type_enum_misplaced_to_need: {inquiry_type}")
        else:
            row["inquiry_type"] = "none"
            row["inquiry_flag"] = "N"
            append_trace(row, f"inquiry_type_invalid_reset: {inquiry_type}")
        inquiry_type = safe_text(row.get("inquiry_type")) or "none"

    if need_type not in ALLOWED_NEED_SIGNAL_TYPES:
        if need_type in INQUIRY_VALUE_MISPLACED_IN_NEED:
            if inquiry_type in {"", "none"} or inquiry_type not in ALLOWED_INQUIRY_TYPES:
                row["inquiry_type"] = need_type
                row["inquiry_flag"] = "Y"
                inquiry_type = need_type
            row["need_signal_type"] = "none"
            row["need_signal_flag"] = "N"
            append_trace(row, f"need_signal_type_enum_misplaced_to_inquiry: {need_type}")
        else:
            row["need_signal_type"] = "none"
            row["need_signal_flag"] = "N"
            append_trace(row, f"need_signal_type_invalid_reset: {need_type}")

    normalize_need_signal_consistency(row)


INSTALLATION_FIT_CONTEXT_TERMS = (
    "설치", "시공", "걸레받이", "하부장", "싱크대", "빌트인", "배수구",
    "배수캡", "y커넥터", "Y커넥터", "사전답사", "가구장", "전세집", "사업장", "매립",
)
DRIVE_FEATURE_TERMS = ("문턱", "단차", "등반", "올라타", "넘", "경사", "턱", "매트")
DRIVE_MOTION_PREDICATES = ("넘", "올라타", "등반", "돌파", "지나가")
FLOOR_MATERIAL_TERMS = ("마루", "강마루", "원목", "타일", "장판", "데코타일")
DRIVE_FEATURE_TOPICS = {"주행/문턱돌파", "장애물 회피", "동선/주행"}
QUESTION_CUES = ("?", "나요", "까요", "는지", "한지", "가능", "궁금", "어떻게", "얼마나", "상관없")


def normalize_installation_inquiry_boundary(row: dict[str, Any]) -> None:
    """R-C2-07: keep driving and floor-fit questions out of installation_fit."""

    if safe_text(row.get("inquiry_type")) != "installation_fit":
        return
    text = safe_text(row.get("atomic_voc")) or safe_text(row.get("original_voc"))
    question_text = text.replace("(?)", "")
    if not question_text or not any(cue in question_text for cue in QUESTION_CUES):
        return

    if any(term in text for term in FLOOR_MATERIAL_TERMS):
        row["inquiry_type"] = "usage_environment_fit"
        row["inquiry_flag"] = "Y"
        append_trace(
            row,
            "installation_fit_boundary_normalized: installation_fit->usage_environment_fit reason=floor_material",
        )
        return

    has_drive_term = any(term in text for term in DRIVE_FEATURE_TERMS)
    has_installation_context = any(term in text for term in INSTALLATION_FIT_CONTEXT_TERMS)
    asks_movement_predicate = any(term in text for term in DRIVE_MOTION_PREDICATES)
    if has_drive_term and (not has_installation_context or asks_movement_predicate):
        row["inquiry_type"] = "feature_spec"
        row["inquiry_flag"] = "Y"
        append_trace(
            row,
            "installation_fit_boundary_normalized: installation_fit->feature_spec reason=drive_feature",
        )


def flag_installation_fit_cej_mismatch(row: dict[str, Any]) -> None:
    """R-C2-07: flag, but never rewrite, a CEJ mismatch."""

    inquiry_type = safe_text(row.get("inquiry_type"))
    topic = safe_text(row.get("topic"))
    cej = safe_text(row.get("cej"))
    if inquiry_type == "feature_spec" and topic in DRIVE_FEATURE_TOPICS:
        if cej != "사용":
            row["review_required"] = "Y"
            append_trace(row, f"drive_feature_cej_mismatch: cej={cej}")
        return
    if inquiry_type != "installation_fit":
        return
    if topic in DRIVE_FEATURE_TOPICS:
        row["review_required"] = "Y"
        append_trace(row, "installation_fit_topic_conflict")
        return
    if cej == "사용준비":
        return
    row["review_required"] = "Y"
    append_trace(row, f"installation_fit_cej_mismatch: cej={cej}")


def normalize_need_signal_consistency(row: dict[str, Any]) -> None:
    """Derive need_signal_flag from the normalized type, recovering raw aliases first."""

    need_type = safe_text(row.get("need_signal_type")) or "none"
    need_flag = normalize_flag(row.get("need_signal_flag"))
    if need_flag == "Y" and need_type in {"", "none"}:
        raw_value = safe_text(row.get("need_signal_type_raw"))
        recovered = NEED_SIGNAL_TYPE_ALIASES.get(raw_value, raw_value)
        if recovered in ALLOWED_NEED_SIGNAL_TYPES - {"none"}:
            row["need_signal_type"] = recovered
            row["need_signal_flag"] = "Y"
            append_trace(row, f"need_signal_type_recovered_from_raw: {raw_value}->{recovered}")
            return

    if need_type in {"", "none"}:
        row["need_signal_type"] = "none"
        row["need_signal_flag"] = "N"
        if need_flag == "Y":
            append_trace(row, "need_signal_flag_derived_from_type: Y->N (type=none)")
    else:
        row["need_signal_flag"] = "Y"


def apply_contract_scoring_rules(row: dict[str, Any]) -> None:
    """Apply schema-level scoring invariants without case-specific content rules."""

    topic = safe_text(row.get("topic"))
    topic_score = int(row.get("topic_score") or 0)
    rootcause_score = int(row.get("rootcause_score") or 0)
    tee_scores = [
        int(row.get("tee_time_score") or 0),
        int(row.get("tee_effort_score") or 0),
        int(row.get("tee_emotion_score") or 0),
        int(row.get("tee_success_score") or 0),
    ]
    has_topic = topic not in {"", "N/A", "None", "none"}
    if not has_topic:
        row["topic_score"] = 0
        return
    if topic == "프로모션":
        row["topic_score"] = min(int(row.get("topic_score") or 1), 1)
        return
    if topic_score == 0:
        row["topic_score"] = 3 if rootcause_score >= 3 or any(score != 0 for score in tee_scores) or row.get("need_signal_flag") == "Y" else 1
    if int(row.get("topic_score") or 0) == 5 and safe_text(row.get("need_signal_type")) not in {"feature_need", "environment_fit_need"}:
        row["topic_score"] = 3


_ATOMIC_EXTRACT_TYPO_NORMALIZATIONS = {
    "맞어요": "맞아요",
    "뭉처": "뭉쳐",
}


def _normalize_atomic_extract_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", safe_text(value))
    text = re.sub(r"\[[^\]]+\]", " ", text)
    for source_text, normalized_text in _ATOMIC_EXTRACT_TYPO_NORMALIZATIONS.items():
        text = text.replace(source_text, normalized_text)
    return "".join(re.findall(r"[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ]+", text)).casefold()


def _atomic_extract_sentences(value: object) -> tuple[str, ...]:
    text = re.sub(r"\[[^\]]+\]", " ", safe_text(value))
    return tuple(
        normalized
        for part in re.split(r"[.!?。！？]+", text)
        if (normalized := _normalize_atomic_extract_text(part))
    )


def atomic_excerpt_matches_source(voc_cleaned: object, atomic_voc: object) -> bool:
    source_sentences = _atomic_extract_sentences(voc_cleaned)
    atomic_sentences = _atomic_extract_sentences(atomic_voc)
    if not source_sentences or not atomic_sentences:
        return False
    return all(any(atomic in source for source in source_sentences) for atomic in atomic_sentences)


ATOMIC_SCORE_VECTOR_FIELDS = (
    "topic_score",
    "tee_time_score",
    "tee_effort_score",
    "tee_emotion_score",
    "tee_success_score",
    "rootcause_score",
)


def count_sentence_endings(value: object) -> int:
    """Count contiguous .!? runs as sentence endings for R-C2-06 A-4."""

    return len(re.findall(r"[.!?]+", safe_text(value)))


def audit_atomic_group(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return the deterministic R-C2-06 A-1 through A-4 findings."""

    group = list(rows)
    findings: dict[str, Any] = {
        "format_violations": [],
        "r12_duplicate_topic": False,
        "r3_identical_score_vector": False,
        "atomic_split_candidate": False,
    }
    if not group:
        return findings

    expected_indexes = [f"{index:02d}" for index in range(1, len(group) + 1)]
    actual_indexes = [safe_text(row.get("atomic_index")) for row in group]
    if actual_indexes != expected_indexes:
        findings["format_violations"].append("atomic_index_sequence")

    numeric_indexes = [
        int(value)
        for value in actual_indexes
        if re.fullmatch(r"\d+", value)
    ]
    if len(numeric_indexes) != len(group) or not numeric_indexes or max(numeric_indexes) != len(group):
        findings["format_violations"].append("atomic_count_index_max")

    source_text = safe_text(group[0].get("voc_cleaned"))
    extract_rows = [
        row
        for row in group
        if safe_text(row.get("atomic_voc"))
        not in {"", "N/A", "None", "none", "N/A (분석 제외)"}
    ]
    if any(
        not atomic_excerpt_matches_source(source_text, row.get("atomic_voc"))
        for row in extract_rows
    ):
        findings["format_violations"].append("atomic_excerpt")

    source_length = len(_normalize_atomic_extract_text(source_text))
    atomic_length_sum = sum(
        len(_normalize_atomic_extract_text(row.get("atomic_voc")))
        for row in extract_rows
    )
    if atomic_length_sum > source_length:
        findings["format_violations"].append("atomic_length_sum")

    if len(group) >= 2:
        topics = {safe_text(row.get("topic")) for row in group}
        findings["r12_duplicate_topic"] = len(topics) == 1

        score_vectors = {
            tuple(_score_as_int(row.get(field)) for field in ATOMIC_SCORE_VECTOR_FIELDS)
            for row in group
        }
        tee_and_rootcause_are_all_zero = all(
            _score_as_int(row.get(field)) == 0
            for row in group
            for field in ATOMIC_SCORE_VECTOR_FIELDS[1:]
        )
        findings["r3_identical_score_vector"] = (
            len(score_vectors) == 1 and not tee_and_rootcause_are_all_zero
        )

    if len(group) == 1:
        row = group[0]
        atomic_text = safe_text(row.get("atomic_voc"))
        long_enough = len(re.sub(r"\s+", "", atomic_text)) >= 110
        has_two_endings = count_sentence_endings(atomic_text) >= 2
        has_conjunction = any(token in atomic_text for token in ATOMIC_SPLIT_CONJUNCTIONS)
        findings["atomic_split_candidate"] = (
            safe_text(row.get("status")) == "normal"
            and long_enough
            and (has_two_endings or has_conjunction)
        )

    return findings


def apply_atomic_group_guards(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply R-C2-06 group findings without changing semantic judgments."""

    findings = audit_atomic_group(rows)
    for violation in findings["format_violations"]:
        for row in rows:
            row["review_required"] = "Y"
            append_trace(row, f"atomic_format_guard: {violation}")
    if findings["r12_duplicate_topic"]:
        for row in rows:
            row["review_required"] = "Y"
            append_trace(row, "r12_duplicate_topic_after_split")
    if findings["r3_identical_score_vector"]:
        for row in rows:
            row["review_required"] = "Y"
            append_trace(row, "r3_identical_score_vector_after_split")
    if findings["atomic_split_candidate"]:
        append_trace(rows[0], "atomic_split_candidate")
    return findings


def resplit_if_multilabel(rows: list[dict[str, Any]]) -> None:
    """Mark E2 multi-label residue; never trigger another split or API call."""

    for row in rows:
        matches = topic_evidence_matches(
            safe_text(row.get("atomic_voc")),
            safe_text(row.get("product_category")),
        )
        labels = list(dict.fromkeys(str(item["label"]) for item in matches))
        if len(labels) < 2:
            continue
        row["review_required"] = "Y"
        append_trace(row, "e2_multilabel_after_split: " + ", ".join(labels))
        concrete = [label for label in labels if label != "제품 전반"]
        if "제품 전반" not in labels or not concrete:
            append_trace(row, "hierarchy_unknown: " + ", ".join(labels))


def verify_evidence_scope(
    row: dict[str, Any], sibling_atomics: Iterable[dict[str, Any]]
) -> None:
    """Mark V-1~V-3 evidence-scope findings without changing judgments."""

    atomic = safe_text(row.get("atomic_voc")).lower()
    siblings = [
        item
        for item in sibling_atomics
        if safe_text(item.get("atomic_id")) != safe_text(row.get("atomic_id"))
    ]
    topic = safe_text(row.get("topic"))
    if topic not in {"", "N/A", "미분류", "제품 전반", "프로모션"}:
        labels = {
            str(item["label"])
            for item in topic_evidence_matches(
                atomic, safe_text(row.get("product_category"))
            )
        }
        if topic not in labels:
            row["review_required"] = "Y"
            append_trace(row, f"v1_topic_without_atomic_lexicon_evidence: topic={topic}")

    stopwords = {
        "근거", "없음", "언급", "해당", "사용", "제품", "관련", "대한",
        "으로", "에서", "하고", "있음", "보임", "느낌", "문제", "내용",
    }
    for field in (
        "cej_evidence",
        "tee_time_evidence",
        "tee_effort_evidence",
        "tee_emotion_evidence",
        "tee_success_evidence",
    ):
        evidence = safe_text(row.get(field)).lower()
        if evidence in {"", "n/a", "none", "0=언급없음", "n/a: 근거 없음"}:
            continue
        words = {
            word
            for word in re.findall(r"[0-9a-z가-힣]{2,}", evidence)
            if word not in stopwords and not word.isdigit()
        }
        if not words or any(word in atomic for word in words):
            continue
        row["review_required"] = "Y"
        append_trace(row, f"v2_evidence_without_atomic_content: field={field}")
        for sibling in siblings:
            sibling_text = safe_text(sibling.get("atomic_voc")).lower()
            if any(word in sibling_text for word in words):
                append_trace(
                    row,
                    "v3_sibling_evidence_leak: "
                    f"field={field} sibling_atomic_id={safe_text(sibling.get('atomic_id'))}",
                )
                break


def normalize_atomic_rows(
    source: SourceRow,
    payload: dict[str, Any],
    *,
    source_canonical: dict[str, Any] | None = None,
    voc_residual: str = "",
    split_review_required: bool = False,
    split_traces: Iterable[str] = (),
) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("LLM response must include non-empty rows list")
    normalized: list[dict[str, Any]] = []
    for index, candidate in enumerate(rows, start=1):
        if not isinstance(candidate, dict):
            raise ValueError("Each LLM row must be an object")
        row = {column: "" for column in TARGET_COLUMNS}
        row.update({k: v for k, v in candidate.items() if k in row})
        row["source_id"] = source.source_id
        row["raw_row_index"] = source.raw_row_index
        row["parent_voc_id"] = source.parent_voc_id
        row["comment_relation"] = source.comment_relation
        row["original_voc"] = source.original_voc
        row["voc_cleaned"] = source.voc_cleaned
        row["voc_residual"] = voc_residual
        row["reference_brand"] = REFERENCE_BRAND
        row["atomic_index"] = f"{index:02d}"
        row["atomic_id"] = f"{source.source_id}-{index:02d}"
        if source.cleaning_length_ratio < 0.6:
            append_trace(
                row,
                f"text_cleaning_ratio_low: ratio={source.cleaning_length_ratio}",
            )
        atomic_voc = safe_text(row.get("atomic_voc"))
        if (
            atomic_voc
            and atomic_voc not in {"N/A", "None", "none"}
            and not atomic_excerpt_matches_source(source.voc_cleaned, atomic_voc)
        ):
            row["review_required"] = "Y"
            append_trace(row, "atomic_extract_guard: atomic_voc not found in voc_cleaned")
        market_hint = (
            safe_text(source.values.get("market"))
            or safe_text(source.values.get("region"))
            or safe_text(source.values.get("country"))
            or "KR"
        )
        row_market = safe_text(row["market"])
        row["market"] = market_hint if row_market in {"", "N/A", "None", "none", "unknown"} else row_market
        row["language"] = safe_text(row["language"]) or "한국어"
        row["video_id"] = safe_text(source.values.get("video_id"))
        row["video_title"] = safe_text(source.values.get("video_title"))
        row["video_url"] = safe_text(source.values.get("video_url"))
        row["_parent_comment"] = safe_text(source.values.get("parent_comment")) or safe_text(source.values.get("parent_voc"))
        row["_video_title"] = safe_text(source.values.get("video_title"))
        row["_video_tags"] = safe_text(source.values.get("video_tags"))
        row["_video_description"] = safe_text(source.values.get("video_description"))
        row["_source_context_summary"] = safe_text(source.values.get("source_context_summary"))
        if not safe_text(row.get("source_context_summary")):
            row["source_context_summary"] = safe_text(source.values.get("source_context_summary"))
        if source_canonical:
            source_fields = (
                "source_id", "raw_row_index", "parent_voc_id", "comment_relation",
                "original_voc", "voc_cleaned", "reference_brand", "market", "language",
                "source_context_summary", "proposal_flag", "video_id", "video_title",
                "video_url", "product_category", "product_category_source",
            )
            for field in source_fields:
                candidate_value = safe_text(row.get(field))
                canonical_value = source_canonical.get(field, "")
                if candidate_value and safe_text(canonical_value) and candidate_value != safe_text(canonical_value):
                    append_trace(row, f"source_canonical_override_ignored: field={field}")
                row[field] = canonical_value
            row["_source_canonical_product_category"] = source_canonical.get("product_category", "")
            row["_source_canonical_product_category_source"] = source_canonical.get("product_category_source", "")
            if safe_text(source.values.get("status")):
                row["status"] = source_canonical.get("status", "normal")
                row["scope_exclusion_reason"] = source_canonical.get("scope_exclusion_reason", "")
        if split_review_required:
            row["review_required"] = "Y"
        for split_trace in split_traces:
            append_trace(row, split_trace)
        row["_topic_label_was_blank"] = not safe_text(row.get("topic"))
        if (
            not safe_text(row.get("topic_provisional"))
            and safe_text(row.get("status")) != "scope_excluded"
        ):
            row["review_required"] = "Y"
            append_trace(row, "topic_provisional_missing_after_split")
        if not safe_text(row.get("topic")):
            row["topic"] = (
                "N/A"
                if safe_text(row.get("status")) == "scope_excluded" or not is_substantive_voc(row)
                else "미분류"
            )
            row["review_required"] = "Y"
            append_trace(row, "topic_missing_not_filled_from_provisional_summary")
        if not safe_text(row.get("inquiry_type_raw")):
            row["inquiry_type_raw"] = safe_text(row.get("inquiry_type"))
        if not safe_text(row.get("need_signal_type_raw")):
            row["need_signal_type_raw"] = safe_text(row.get("need_signal_type"))
        normalize_inquiry_need_types(row)
        row["proposal_flag"] = "engine_llm"
        row["status"] = safe_text(row["status"]) or "normal"
        row["review_required"] = normalize_flag(row["review_required"])
        row["inquiry_flag"] = normalize_flag(row["inquiry_flag"])
        row["need_signal_flag"] = normalize_flag(row["need_signal_flag"])
        row["topic_score"] = normalize_score(row["topic_score"], {0, 1, 3, 5})
        row["tee_time_score"] = normalize_score(row["tee_time_score"], {-5, -3, -1, 0, 1, 3, 5})
        row["tee_effort_score"] = normalize_score(row["tee_effort_score"], {-5, -3, -1, 0, 1, 3, 5})
        row["tee_emotion_score"] = normalize_score(row["tee_emotion_score"], {-5, -3, -1, 0, 1, 3, 5})
        row["tee_success_score"] = normalize_score(row["tee_success_score"], {-5, -3, -1, 0, 1, 3, 5})
        row["rootcause_score"] = normalize_score(row["rootcause_score"], {0, 1, 3, 5})
        normalize_topic_label(row)
        normalize_installation_inquiry_boundary(row)
        apply_misc_out_of_scope_product_guard(row)
        normalize_scope_exclusion(row)
        normalize_entity_role(row)
        apply_creator_review_method_discipline(row)
        clamp_tee_scores(row)
        align_aspect_sentiment(row)
        clamp_rootcause_score(row)
        apply_na_and_promo_discipline(row)
        normalize_cej(row)
        flag_installation_fit_cej_mismatch(row)
        apply_contract_scoring_rules(row)
        finalize_score_fields(row)
        enforce_topic_not_blank(row)
        if safe_text(row.get("topic")) in {"N/A", "프로모션"}:
            row["rootcause_score"] = 0
        finalize_score_fields(row)
        clear_rootcause_details_when_score_zero(row)
        normalize_step_confidence(row)
        try:
            row["voc_total_score"] = (
                int(row["topic_score"])
                + int(row["tee_time_score"])
                + int(row["tee_effort_score"])
                + int(row["tee_emotion_score"])
                + int(row["tee_success_score"])
                + int(row["rootcause_score"])
            )
        except Exception:
            row["voc_total_score"] = 0
        for evidence_col in [
            "topic_evidence",
            "cej_evidence",
            "tee_time_evidence",
            "tee_effort_evidence",
            "tee_emotion_evidence",
            "tee_success_evidence",
        ]:
            if not safe_text(row[evidence_col]):
                row[evidence_col] = "N/A: 근거 없음"
        compute_confidence(row)
        if source_canonical:
            canonical_status = safe_text(source_canonical.get("status")) or "normal"
            canonical_reason = safe_text(source_canonical.get("scope_exclusion_reason"))
            if safe_text(row.get("status")) != canonical_status:
                append_trace(
                    row,
                    f"source_canonical_override_ignored: field=status atomic={safe_text(row.get('status'))} source={canonical_status}",
                )
            row["status"] = canonical_status
            row["scope_exclusion_reason"] = canonical_reason if canonical_status == "scope_excluded" else ""
        if safe_text(row["trace_summary"]) in {"", "N/A", "None", "none"}:
            row["trace_summary"] = (
                f"LLM runtime judgment: topic={row['topic']}; cej={row['cej']}; "
                f"entity_role={row['entity_role']}; confidence={row['confidence_rating']}"
            )
        for transient_key in (
            "_parent_comment",
            "_video_title",
            "_video_tags",
            "_video_description",
            "_source_context_summary",
            "_topic_label_was_blank",
            "_source_canonical_product_category",
            "_source_canonical_product_category_source",
        ):
            row.pop(transient_key, None)
        normalized.append(row)
    resplit_if_multilabel(normalized)
    for row in normalized:
        verify_evidence_scope(row, normalized)
    apply_atomic_group_guards(normalized)
    return normalized


def build_scope_excluded_row(source: SourceRow, reason: str) -> dict[str, Any]:
    row = {column: "" for column in TARGET_COLUMNS}
    reason_code = canonical_scope_exclusion_reason(reason) or "no_analytic_value"
    is_operator = reason_code == "operator_notice"
    market_hint = (
        safe_text(source.values.get("market"))
        or safe_text(source.values.get("region"))
        or safe_text(source.values.get("country"))
        or "KR"
    )
    product_category, product_category_source = infer_product_category_with_source(
        {
            "original_voc": source.original_voc,
            "voc_cleaned": source.voc_cleaned,
            "_parent_comment": safe_text(source.values.get("parent_comment")) or safe_text(source.values.get("parent_voc")),
            "_video_title": safe_text(source.values.get("video_title")),
            "_video_tags": safe_text(source.values.get("video_tags")),
            "_video_description": safe_text(source.values.get("video_description")),
            "_source_context_summary": safe_text(source.values.get("source_context_summary")),
        }
    )
    row.update(
        {
            "source_id": source.source_id,
            "raw_row_index": source.raw_row_index,
            "parent_voc_id": source.parent_voc_id,
            "comment_relation": source.comment_relation,
            "atomic_id": f"{source.source_id}-01",
            "atomic_index": "01",
            "original_voc": source.original_voc,
            "voc_cleaned": source.voc_cleaned,
            "atomic_voc": "N/A (분석 제외)",
            "atomic_voc_summary": reason,
            "topic_provisional": "N/A",
            "topic": "N/A",
            "topic_evidence": reason,
            "topic_score": 0,
            "reference_brand": REFERENCE_BRAND,
            "product_category": product_category,
            "product_category_source": product_category_source,
            "product_tags": "",
            "product_additional_info": "",
            "competitor_brand_tags": "",
            "competitor_product_tags": "",
            "competitor_product_additional_info": "",
            "brand": "creator_channel" if is_operator else "unknown",
            "market": market_hint,
            "language": "한국어",
            "cej": "해당없음",
            "cej_evidence": reason,
            "inquiry_flag": "N",
            "inquiry_type": "none",
            "inquiry_type_raw": "none",
            "need_signal_flag": "N",
            "need_signal_type": "none",
            "need_signal_type_raw": "none",
            "entity_role": "creator_channel" if is_operator else "unknown",
            "tee_time_score": 0,
            "tee_time_evidence": "0=분석 제외",
            "tee_effort_score": 0,
            "tee_effort_evidence": "0=분석 제외",
            "tee_emotion_score": 0,
            "tee_emotion_evidence": "0=분석 제외",
            "tee_success_score": 0,
            "tee_success_evidence": "0=분석 제외",
            "tee_summary": "분석 제외",
            "rootcause_problem": "N/A",
            "rootcause_target": "N/A",
            "rootcause_cause": "N/A",
            "rootcause_summary": "N/A",
            "rootcause_score": 0,
            "voc_total_score": 0,
            "confidence_topic": "Low",
            "confidence_cej": "Low",
            "confidence_inquiry": "High",
            "confidence_need_signal": "High",
            "confidence_entity_role": "High",
            "confidence_score": "Low",
            "source_context_summary": safe_text(source.values.get("source_context_summary")) or "LLM 전 분석 제외 게이트",
            "trace_summary": f"pre-LLM scope exclusion: {reason}",
            "status": "scope_excluded",
            "review_required": "N",
            "scope_exclusion_reason": reason_code,
            "proposal_flag": "engine_pre_llm_exclusion",
            "video_id": safe_text(source.values.get("video_id")),
            "video_title": safe_text(source.values.get("video_title")),
            "video_url": safe_text(source.values.get("video_url")),
        }
    )
    compute_confidence(row)
    return row


def _analyze_source_row(source: SourceRow, runtime: OpenAIChatClient) -> list[dict[str, Any]]:
    if is_operator_notice(source.original_voc):
        return [build_scope_excluded_row(source, operator_notice_reason(source.original_voc))]
    if is_effectively_empty(source.original_voc):
        return [build_scope_excluded_row(source, "정제 후 분석 가능한 VoC 없음")]
    payload = runtime.complete_json(RUNTIME_SYSTEM_PROMPT, build_user_prompt(source))
    payload, recall_count = apply_topic_recall(source, payload, runtime)
    if recall_count:
        rows_count = len(payload.get("rows") or [])
        print(
            f"topic_recall: source_id={source.source_id}, recalled={recall_count}/{rows_count}",
            flush=True,
        )
    return normalize_atomic_rows(source, payload)


def analyze_rows(
    rows: Iterable[dict[str, Any]],
    *,
    client: OpenAIChatClient | None = None,
    model: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    llm_concurrency: int = DEFAULT_LLM_CONCURRENCY,
) -> list[dict[str, Any]]:
    runtime = client or OpenAIChatClient(model=model, timeout_seconds=timeout_seconds)
    row_values = list(rows)

    def assert_source_coverage(output_rows: list[dict[str, Any]]) -> None:
        expected = {safe_text(values.get("source_id")) for values in row_values}
        actual = {safe_text(row.get("source_id")) for row in output_rows}
        missing = sorted(source_id for source_id in expected - actual if source_id)
        if missing:
            raise AssertionError(f"C-6 source coverage violation: missing_source_ids={missing}")

    def analyze_source(values: dict[str, Any]) -> list[dict[str, Any]]:
        source = SourceRow(values)
        if is_operator_notice(source.original_voc):
            return [build_scope_excluded_row(source, operator_notice_reason(source.original_voc))]
        if is_effectively_empty(source.original_voc):
            return [build_scope_excluded_row(source, "정제 후 분석 가능한 VoC 없음")]

        canonical = source_canonical_record(source)
        if safe_text(canonical.get("status")) == "scope_excluded":
            return [
                build_scope_excluded_row(
                    source,
                    safe_text(canonical.get("scope_exclusion_reason")) or "no_analytic_value",
                )
            ]
        plans, residual, split_review, split_traces = split_by_topic(source, runtime)
        if not plans:
            return []
        sibling_texts = [safe_text(plan.get("atomic_voc")) for plan in plans]
        candidates: list[dict[str, Any]] = []
        for plan in plans:
            atomic_voc = safe_text(plan.get("atomic_voc"))
            provisional_summary = (
                safe_text(plan.get("topic_provisional"))
                or "잠정 주제의 근거를 서술하지 못함"
            )
            provisional_label = TOPIC_NORMALIZATION_MAP.get(
                safe_text(plan.get("_provisional_label")),
                safe_text(plan.get("_provisional_label")),
            )
            if provisional_label not in CANONICAL_TOPICS:
                provisional_label = "미분류"
            if plan.get("_skip_atomic_judgment"):
                candidate = {
                    "atomic_voc": atomic_voc,
                    "topic_provisional": provisional_summary,
                    "topic": provisional_label,
                    "review_required": "Y",
                }
            else:
                response: dict[str, Any] | None = None
                judgment_error: Exception | None = None
                judgment_prompt = build_atomic_judgment_prompt(
                    source,
                    atomic_voc,
                    sibling_texts,
                    provisional_summary,
                )
                for _attempt in range(2):
                    try:
                        raw_response = runtime.complete_json(RUNTIME_SYSTEM_PROMPT, judgment_prompt)
                        response = raw_response if isinstance(raw_response, dict) else {}
                        judgment_error = None
                        break
                    except Exception as exc:  # noqa: BLE001 - one retry, then a traceable atomic fallback
                        judgment_error = exc
                if judgment_error is not None:
                    candidate = {
                        "atomic_voc": atomic_voc,
                        "topic_provisional": provisional_summary,
                        "topic": provisional_label,
                        "review_required": "Y",
                    }
                    append_trace(
                        candidate,
                        "llm_call_failed: "
                        f"stage=atomic_judgment exception={type(judgment_error).__name__} attempts=2",
                    )
                else:
                    response = response or {}
                    response_rows = response.get("rows")
                    if isinstance(response_rows, list) and response_rows:
                        candidate = dict(response_rows[0]) if isinstance(response_rows[0], dict) else {}
                        if len(response_rows) != 1:
                            candidate["review_required"] = "Y"
                            append_trace(candidate, f"atomic_judgment_row_count_ignored: count={len(response_rows)}")
                    else:
                        candidate = dict(response)
            candidate["atomic_voc"] = atomic_voc
            candidate["topic_provisional"] = provisional_summary
            append_trace(candidate, f"provisional_label: {provisional_label}")
            if not safe_text(candidate.get("topic")):
                candidate["topic"] = provisional_label
                candidate["review_required"] = "Y"
                append_trace(candidate, "llm_output_fallback: stage=atomic_judgment reason=missing_topic")
            candidates.append(candidate)

        normalized_rows = normalize_atomic_rows(
            source,
            {"rows": candidates},
            source_canonical=canonical,
            voc_residual=residual,
            split_review_required=split_review,
            split_traces=split_traces,
        )
        for normalized_row, fallback_candidate in zip(normalized_rows, candidates):
            trace = safe_text(normalized_row.get("trace_summary"))
            if "llm_call_failed:" in trace or "llm_output_fallback:" in trace:
                preserved_summary = (
                    safe_text(fallback_candidate.get("topic_provisional"))
                    or "잠정 주제의 근거를 서술하지 못함"
                )
                preserved_label = "미분류"
                match = re.search(r"(?:^|\|)\s*provisional_label:\s*([^|]+)", trace)
                if match:
                    traced_label = TOPIC_NORMALIZATION_MAP.get(
                        safe_text(match.group(1)), safe_text(match.group(1))
                    )
                    if traced_label in CANONICAL_TOPICS:
                        preserved_label = traced_label
                normalized_row["topic_provisional"] = preserved_summary
                normalized_row["topic"] = preserved_label
                normalized_row["review_required"] = "Y"
        return normalized_rows

    max_workers = max(1, int(llm_concurrency or 1))
    if max_workers > 1 and len(row_values) > 1:
        output: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for analyzed in executor.map(analyze_source, row_values):
                output.extend(analyzed)
        assert_source_coverage(output)
        return output
    output: list[dict[str, Any]] = []
    for values in row_values:
        output.extend(analyze_source(values))
    assert_source_coverage(output)
    return output


def read_workbook_rows(path: str | Path, sheet_name: str | None = None) -> list[dict[str, Any]]:
    if load_workbook is None:
        raise RuntimeError("openpyxl is required to read workbook inputs")
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb[wb.sheetnames[0]]
    iterator = ws.iter_rows(values_only=True)
    header = [safe_text(v) for v in next(iterator)]
    rows = []
    for row in iterator:
        if all(v is None or safe_text(v) == "" for v in row):
            continue
        rows.append(dict(zip(header, row)))
    return rows


def analyze_workbook_rows(
    path: str | Path,
    sheet_name: str | None = None,
    *,
    model: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    llm_concurrency: int = DEFAULT_LLM_CONCURRENCY,
    offset: int = 0,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    rows = read_workbook_rows(path, sheet_name)
    if offset:
        rows = rows[offset:]
    if limit is not None:
        rows = rows[:limit]
    return analyze_rows(rows, model=model, timeout_seconds=timeout_seconds, llm_concurrency=llm_concurrency)


def write_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    assert_column_contract(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_jsonl(rows: list[dict[str, Any]], path: str | Path) -> None:
    assert_column_contract(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
