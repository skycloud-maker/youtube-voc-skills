from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.analytics.comment_analysis import analyze_comment_with_context

CONTRAST_SPLIT_RE = re.compile(
    r"\b(?:but|however|though|although|while|yet|except)\b|"
    r"\ud558\uc9c0\ub9cc|\uadf8\ub7f0\ub370|\ub2e4\ub9cc|\ubc18\uba74|\uadfc\ub370|\uadf8\ub7ec\ub098|"
    r"\uadf8\ub798\ub3c4|\ub300\uc2e0|\uadf8\ub9ac\uace0|\ub610\ud55c|\ub610",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\\s+|(?<=\u3002)|\\n+")
MODEL_RE = re.compile(r"\b[A-Z0-9]{4,}(?:[-_][A-Z0-9]+)*\b")
INQUIRY_PATTERNS = {
    "HOW_TO": ["how to", "how do i", "\uc0ac\uc6a9\ubc95", "\uc5b4\ub5bb\uac8c", "\uc124\uc815", "\ubc29\ubc95"],
    "OFFICIAL_SERVICE": ["official service", "service center", "\uc11c\ube44\uc2a4\uc13c\ud130", "\uacf5\uc2dd \uc11c\ube44\uc2a4", "as \uc13c\ud130", "a/s"],
    "RISK_CONCERN": ["safe", "risk", "\uac71\uc815", "\uc704\ud5d8", "\uad1c\ucc2e\uc744\uae4c\uc694", "\uc2e4\uc218"],
    "WARRANTY": ["warranty", "\ubcf4\uc99d", "\ubb34\uc0c1", "\uc720\uc0c1"],
    "COST": ["cost", "price", "\ube44\uc6a9", "\uac00\uaca9", "\uc5bc\ub9c8"],
    "ELIGIBILITY": [
        "eligible",
        "\uac00\ub2a5\ud55c\uac00",
        "\uac00\ub2a5\ud55c\uc9c0",
        "\uac00\ub2a5\ud560\uae4c\uc694",
        "\uac00\ub2a5 \ud55c\uac00",
        "\uac00\ub2a5 \ud55c\uc9c0",
        "\ub418\ub098\uc694",
        "\ub420\uae4c\uc694",
        "\ub3fc\uc694",
        "\uad81\uae08",
        "\ub300\uc0c1",
        "\ud574\ub2f9",
        "\uad50\ud658 \uac00\ub2a5",
    ],
}
SCENE_RULES = [
    ("S8 Maintain", ["repair", "service", "technician", "tech", "warranty", "a/s", "as", "\uc218\ub9ac", "\uc11c\ube44\uc2a4", "\uae30\uc0ac", "\uc13c\ud130", "\ubcf4\uc99d", "\uc810\uac80"]),
    ("S5 Deliver", ["delivery", "install", "installation", "shipping", "\ubc30\uc1a1", "\uc124\uce58", "\ud30c\uc190", "\ubc29\ubb38", "\uc9c0\uc5f0"]),
    ("S6 On-board", ["setup", "set up", "register", "registration", "app", "thinq", "wifi", "\uc5f0\ub3d9", "\ub4f1\ub85d", "\ub85c\uadf8\uc778", "\ucd08\uae30 \uc124\uc815", "\uc571"]),
    ("S4 Purchase", ["bought", "purchase", "purchased", "order", "ordered", "\uad6c\ub9e4", "\uc8fc\ubb38", "\uacb0\uc81c"]),
    ("S9 Replace", ["replace", "replaced", "replacement", "\uad50\uccb4", "\ubc14\uafe8", "\uc0c8\ub85c \uc0c0"]),
    ("S2 Explore", ["compare", "comparison", "recommend", "review", "difference", "\ucd94\ucc9c", "\ube44\uad50", "\ud6c4\uae30", "\ucc28\uc774"]),
    ("S1 Aware", ["ad", "advertisement", "thumbnail", "\uad11\uace0", "\uc378\ub124\uc77c"]),
]
ASPECT_RULES = [
    ("Noise/Vibration", ["\uc18c\uc74c", "\uc2dc\ub044", "\uc870\uc6a9", "\uc6c5\uc6c5", "\uc9c4\ub3d9", "\ub5a8\ub9bc", "\uc18c\ub9ac", "\ucff5\ucff5", "\ub4dc\ub974\ub975", "noise", "vibration", "buzz"]),
    ("Performance", ["\uc138\ud0c1\ub825", "\ub54c", "\uc624\uc5fc", "\ud5f9\uad7c", "\uac74\uc870", "\ub9d0\ub9bc", "\uc138\ucc99", "\uc138\ucc99\ub825", "\uc794\uc5ec\ubb3c", "\ud761\uc785", "\ud761\uc785\ub825", "\ub0c9\uac01", "\uc628\ub3c4", "\uc2e0\uc120", "performance", "cleaning", "cooling", "temperature"]),
    ("Convenience/Usability", ["\ud3b8\ud574", "\ubd88\ud3b8", "\uc870\uc791", "\ubc84\ud2bc", "\uba54\ub274", "ui", "\uac04\ud3b8", "\ubcf5\uc7a1", "\uc124\uc815", "convenient", "inconvenient", "easy to use"]),
    ("Reliability/Breakdown", ["\uace0\uc7a5", "\ubd88\ub7c9", "\uba39\ud1b5", "\uc548 \ucf1c", "\uc791\ub3d9 \uc548", "\uc5d0\ub7ec", "\uc5d0\ub7ec\ucf54\ub4dc", "\uc218\uba85", "\ub0b4\uad6c", "broken", "broke", "doesn't work", "error", "failed"]),
    ("Delivery/Installation", ["\ubc30\uc1a1", "\uc124\uce58", "\uc124\uce58\uae30\uc0ac", "\uc9c0\uc5f0", "\ud30c\uc190", "\uc2dc\uac04\uc57d\uc18d", "delivery", "installation", "shipping"]),
    ("App/Connectivity", ["\uc571", "thinq", "\uc640\uc774\ud30c\uc774", "\uc5f0\ub3d9", "\uc5f0\uacb0", "\ub4f1\ub85d", "\ub85c\uadf8\uc778", "\uc5c5\ub370\uc774\ud2b8", "app", "wifi", "connect", "login"]),
    ("Maintenance/Cleaning", ["\uad00\ub9ac", "\uccad\uc18c", "\uc138\ucc99", "\ud544\ud130", "\ud544\ud130 \uad50\uccb4", "\ub9ac\uc14b", "\uba3c\uc9c0\ud1b5", "\ubb3c\ud1b5", "\ud0c8\ucde8", "clean", "cleaning", "maintenance", "filter"]),
    ("A/S & Support", ["as", "a/s", "\uc11c\ube44\uc2a4\uc13c\ud130", "\uc13c\ud130", "\uc218\ub9ac", "\uc811\uc218", "\uc0c1\ub2f4", "\uc751\ub300", "\ucc98\ub9ac\uc9c0\uc5f0", "\ubd88\uce5c\uc808", "\ubcf4\uc99d", "\uc218\ub9ac\ube44", "service", "support", "warranty", "repair"]),
    ("Price/Value", ["\uac00\uaca9", "\ube44\uc2f8", "\uac00\uc131\ube44", "\ud61c\ud0dd", "\ud560\uc778", "\ube44\uc6a9", "\uad6c\ub3c5\ub8cc", "price", "expensive", "value", "cost"]),
    ("Design/Build", ["\ub514\uc790\uc778", "\ub9c8\uac10", "build", "design", "overdesign", "overdesigned", "sku", "simple", "\ub2e8\uc21c", "\uacfc\uc124\uacc4"]),
    ("Safety", ["\uc548\uc804", "\uc704\ud5d8", "safe", "safety", "hazard"]),
    ("Energy/Consumption", ["\uc804\uae30\uc138", "\uc804\ub825", "\uc18c\ube44\uc804\ub825", "\ud6a8\uc728", "\uc5d0\ub108\uc9c0", "energy", "power"]),
    ("Smell/Odor", ["\ub0c4\uc0c8", "\uc545\ucde8", "\ucff0\ucff0", "odor", "smell"]),
    ("Leakage/Water", ["\ub204\uc218", "\ubb3c\uc0d8", "\uc0c8\uc694", "\ubc30\uc218", "\uc5ed\ub958", "leak", "water"]),
    ("Fit/Space", ["\uacf5\uac04", "\ud06c\uae30", "\uc790\ub9ac", "fit", "space"]),
    ("Documentation/Instructions", ["\uc124\uba85\uc11c", "\ub9e4\ub274\uc5bc", "\uac00\uc774\ub4dc", "manual", "instruction"]),
]
PRODUCT_MAP = {
    "\ub0c9\uc7a5\uace0": "Refrigerator",
    "\uc138\ud0c1\uae30": "Washer",
    "\uac74\uc870\uae30": "Dryer",
    "\uc2dd\uae30\uc138\ucc99\uae30": "Dishwasher",
    "\uccad\uc18c\uae30": "Vacuum",
    "\uc624\ube10": "Oven",
    "\uc815\uc218\uae30": "Water Purifier",
    "\uc778\ub355\uc158": "Induction",
    "\uc640\uc778\uc140\ub7ec": "Wine Cellar",
    "\ucef5\uc138\ucc99\uae30": "Cup Washer",
    "\uc2e4\ub0b4\uc2dd\ubb3c\uc7ac\ubc30\uae30(\ud2d4\uc6b4)": "Indoor Plant Grower (Tiiun)",
}


SUBTYPE_RULES = {
    "Refrigerator": {
        "???": ["???", "side-by-side", "side by side"],
        "???????": ["???", "???", "top freezer", "bottom freezer", "top-fridge-bottom-freezer"],
        "?????": ["?????", "kimchi fridge"],
        "???": ["???", "built-in", "built in"],
        "??(???)": ["?????", "mini fridge", "personal fridge"],
        "????": ["????", "wine cellar", "wine fridge"],
        "????": ["showcase"],
    },
    "Washer": {
        "??": ["front loader", "front-load", "drum washer", "??"],
        "???": ["top loader", "top-load", "???"],
        "????": ["washtower", "wash tower", "????"],
        "??": ["combo", "all-in-one", "all in one", "??"],
        "????": ["mini washer", "????"],
    },
    "Dryer": {
        "??": ["combo", "all-in-one", "all in one", "washer dryer combo", "??"],
        "????": ["heat pump", "????"],
        "???": ["condenser", "???"],
        "??": ["vented", "??"],
    },
    "Dishwasher": {
        "6??": ["6 place", "6-place", "6??"],
        "12~14??": ["12 place", "14 place", "12-14", "12~14", "12??", "14??"],
        "???": ["built-in", "built in", "???"],
        "?????": ["freestanding", "?????"],
    },
    "Vacuum": {
        "??": ["robot", "robot vacuum", "?????"],
        "??": ["stick", "cordless", "??"],
        "???(W&D)": ["wet&dry", "wet and dry", "???", "w&d"],
        "??": ["handheld", "??"],
    },
    "Cup Washer": {
        "??(????)": ["countertop", "compact", "????", "??"],
        "???": ["built-in", "built in", "???"],
        "???(??????)": ["commercial", "cafe", "office", "???", "??", "???"],
    },
    "Indoor Plant Grower (Tiiun)": {
        "??(???)": ["compact", "personal", "??", "???"],
        "????": ["stand", "stand-type", "????"],
    },
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null", "<na>"} else text


def _contains_any(text: str, markers: list[str]) -> bool:
    lowered = _safe_text(text).lower()
    return any(marker.lower() in lowered for marker in markers)


def _context_review_reason(text: str) -> str:
    lowered = _safe_text(text).lower()
    has_timestamp = bool(re.search(r"\d+\s*\ubd84\s*\d*\s*\ucd08|\d{1,2}:\d{2}", lowered))
    video_markers = ["\uc601\uc0c1", "\uc790\ub9c9", "\ud654\uba74", "\ucea1\uc158", "\uc2e4\ud5d8", "\ub9ac\ubdf0", "video", "caption"]
    mismatch_markers = ["\uc548\ub2e6", "\uc548 \ub2e6", "\ub2e6\uc600\ub2e4\uace0", "\uc65c", "\ubcf4\uc774\ub294\ub370", "mismatch"]
    thanks_markers = ["\uc815\ubcf4\uacf5\uc720", "\uc798 \ubcf4\uace0", "\uc88b\uc740 \uc601\uc0c1", "\uac10\uc0ac\ud569\ub2c8\ub2e4"]
    if (has_timestamp and _contains_any(lowered, video_markers + mismatch_markers)) or (
        _contains_any(lowered, video_markers) and _contains_any(lowered, mismatch_markers)
    ):
        return "video_context_or_caption_comment"
    if _contains_any(lowered, thanks_markers) and not _contains_any(lowered, ["\ub0c4\uc0c8", "\ubd88\ud3b8", "\uace0\uc7a5", "\ub204\uc218", "\uc18c\uc74c", "\uc138\ucc99"]):
        return "simple_opinion_or_info_share"
    return ""


def _is_video_context_comment(text: str) -> bool:
    return bool(_context_review_reason(text))


def _is_weak_reaction_only(text: str) -> bool:
    compact = re.sub(r"[\s.!?~ㅋㅎㅠㅜ]+", "", _safe_text(text).lower())
    if not compact:
        return True
    weak_reactions = {
        "lg\uc2dd\uae30\uc138\ucc99\uae30\uadf8\ub798\ub3c4\ucd5c\uace0\ub2e4",
        "\uc2dd\uae30\uc138\ucc99\uae30\uc88b\ub354\ub77c",
        "lg\uc2dd\uc138\uae30\uc88b\ub354\ub77c",
        "\uc88b\ub124\uc694",
        "\uc88b\ub354\ub77c",
        "\ucd5c\uace0\ub2e4",
        "\uae30\ubd84\ub098\ube60",
        "\ubcc4\ub85c\uc57c",
        "\uc2eb\uc5b4",
    }
    if compact in weak_reactions:
        return True
    if len(compact) <= 14 and _contains_any(compact, ["\uc88b", "\ucd5c\uace0", "\uae30\ubd84\ub098\ube60", "\ubcc4\ub85c", "\uc2eb"]):
        product_or_aspect = ["\ud544\ud130", "\uac70\ub984\ub9dd", "\uc18c\ub3c5", "\ub0c4\uc0c8", "\ub204\uc218", "\uc18c\uc74c", "\uc2dc\uac04", "\ub0a8\uc740", "\uc138\ucc99", "\uad50\uccb4", "\uba3c\uc9c0"]
        return not _contains_any(compact, product_or_aspect)
    return False


def _is_usage_friction_comment(text: str) -> bool:
    return _contains_any(
        text,
        [
            "\ub118\uce58", "\ud758\ub7ec", "\ud758\ub9bc", "\ub123\ub294 \uacfc\uc815", "\uc0b4\uc9dd", "\uc870\uc2ec",
            "\ud301", "\uc218\uc6d4", "\ubd88\ud3b8", "\ubc88\uac70", "\uadc0\ucc2e", "\uc548 \ubcf4", "\ub0a8\uc740 \uc2dc\uac04",
            "\ubcf4\uc774\uc9c0", "\ud45c\uc2dc", "\ub514\uc2a4\ud50c\ub808\uc774",
        ],
    )


def _clause_sentiment_fallback(text: str, fallback: str = "neutral") -> str:
    lowered = _safe_text(text).lower()
    positive_markers = [
        "\uc88b", "\ucd5c\uace0", "\ub9cc\uc871", "\ud3b8\ud558", "\uc798", "\uc18c\ub3c5", "\uac78\ub7ec", "\ud3ec\uc9d1",
        "good", "great", "love", "satisfied", "well",
    ]
    negative_markers = [
        "\ubd88\ud3b8", "\ub0c4\uc0c8", "\uc545\ucde8", "\uace0\uc7a5", "\uc548 \ubcf4", "\ubcf4\uc774\uc9c0", "\ub0a8\uc740 \uc2dc\uac04",
        "\ub118\uce58", "\ud758\ub7ec", "\ubc88\uac70", "\uc544\uc27d", "\uc2e4\ub9dd", "\uc9dc\uc99d", "bad", "hard", "broken",
    ]
    pos_score = sum(marker in lowered for marker in positive_markers)
    neg_score = sum(marker in lowered for marker in negative_markers)
    if pos_score > neg_score:
        return "positive"
    if neg_score > pos_score:
        return "negative"
    return fallback if fallback in {"positive", "negative", "neutral"} else "neutral"


def _split_opinion_text(text: str) -> list[str]:
    source = _safe_text(text)
    if not source:
        return []
    segments = [source]
    if CONTRAST_SPLIT_RE.search(source):
        segments = [part.strip(" ,.;:-\n\t") for part in re.split(CONTRAST_SPLIT_RE, source) if _safe_text(part)] or [source]
    clauses: list[str] = []
    for segment in segments:
        subparts = [part.strip(" ,.;:-\n\t") for part in SENTENCE_SPLIT_RE.split(segment) if _safe_text(part)]
        clauses.extend(subparts or [segment])
    seen: set[str] = set()
    deduped: list[str] = []
    for clause in clauses:
        normalized = clause.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped or [source]


def _derive_scene(text: str, fallback_scene: str = "") -> str:
    lowered = _safe_text(text).lower()
    for scene, markers in SCENE_RULES:
        if any(marker in lowered for marker in markers):
            return scene
    if fallback_scene:
        return fallback_scene
    return "S7 Use" if lowered else "S10 Other"


def _derive_aspect(text: str) -> tuple[str, str]:
    lowered = _safe_text(text).lower()
    best_key = "General"
    best_hits = 0
    best_marker = ""
    for aspect, markers in ASPECT_RULES:
        hits = sum(1 for marker in markers if marker in lowered)
        if hits > best_hits:
            best_hits = hits
            best_key = aspect
            best_marker = next((marker for marker in markers if marker in lowered), "")
    return best_key, best_marker


def _extract_inquiry(text: str) -> tuple[bool, list[str]]:
    lowered = _safe_text(text).lower()
    flags = [label for label, markers in INQUIRY_PATTERNS.items() if any(marker in lowered for marker in markers)]
    return bool(flags), flags or (["OTHER"] if "?" in lowered else [])


def _extract_model_tokens(source_blob: str) -> list[str]:
    candidates = []
    for match in MODEL_RE.finditer(_safe_text(source_blob).upper()):
        token = match.group(0)
        if any(ch.isdigit() for ch in token) and len(token) >= 5:
            candidates.append(token)
    return list(dict.fromkeys(candidates))


def _derive_product_subtype(category: str, source_blob: str) -> tuple[str, list[str]]:
    blob = _safe_text(source_blob).lower()
    for subtype, markers in SUBTYPE_RULES.get(category, {}).items():
        hits = [marker for marker in markers if marker.lower() in blob]
        if hits:
            return subtype, hits
    return "Unknown", []


def _extract_evidence_spans(clause_text: str, aspect_marker: str = "") -> list[str]:
    clause = _safe_text(clause_text)
    if not clause:
        return []
    spans: list[str] = [clause]
    lowered = clause.lower()
    if aspect_marker:
        marker = aspect_marker.lower()
        idx = lowered.find(marker)
        if idx >= 0:
            spans.append(clause[idx:idx + len(aspect_marker)])
    return list(dict.fromkeys(span for span in spans if _safe_text(span)))


def _unit_type(sentiment_code: str, inquiry_flag: bool, classification_type: str, validity: str) -> str:
    if validity != "valid" or sentiment_code == "excluded":
        return "log_only"
    if inquiry_flag:
        return "inquiry"
    if sentiment_code == "positive":
        return "praise"
    if sentiment_code == "negative":
        return "issue"
    if _safe_text(classification_type).lower() in {"suggestion", "comparison", "preference"}:
        return "suggestion"
    return "review_needed"


def _routing_for_unit(unit_type: str, signal_strength: str, confidence_level: str, text: str) -> tuple[str, list[str]]:
    lowered = _safe_text(text).lower()
    review_reasons: list[str] = []
    if unit_type == "log_only":
        return "LOG_ONLY", []
    safety_markers = ["탄 냄새", "타는 냄새", "연기", "화재", "감전", "누전", "폭발", "burning smell", "smoke", "fire", "electric shock"]
    if any(marker in lowered for marker in safety_markers):
        review_reasons.append("safety_or_high_risk_signal")
    if unit_type == "review_needed":
        review_reasons.append("weak_or_ambiguous_unit")
    if unit_type == "inquiry" and any(marker in lowered for marker in ["궁금증", "클릭", "click"]):
        review_reasons.append("weak_or_ambiguous_inquiry")
    if _safe_text(confidence_level).lower() == "low" and _safe_text(signal_strength).lower() == "weak":
        review_reasons.append("low_confidence_weak_signal")
    if review_reasons:
        return "REVIEW_LANE", sorted(set(review_reasons))
    if unit_type == "inquiry":
        return "INQUIRY_LANE", []
    return "KEEP", []


def _topic_group_candidate(product_category: str, aspect_key: str, text: str) -> str:
    product = _safe_text(product_category) or "Other"
    lowered = _safe_text(text).lower()
    if any(token in lowered for token in ["냄새", "악취", "odor", "smell"]):
        topic = "위생관리"
    elif any(token in lowered for token in ["필터", "거름망", "filter"]):
        topic = "필터 사용성"
    elif any(token in lowered for token in ["앱", "wifi", "wi-fi", "thinq", "연동", "로그인", "connect"]):
        topic = "앱 연결/로그인"
    elif any(token in lowered for token in ["소음", "진동", "noise", "vibration"]):
        topic = "소음·진동"
    elif any(token in lowered for token in ["흡입", "suction", "먼지통", "dust bin"]):
        topic = "청소 성능/먼지비움"
    elif any(token in lowered for token in ["문", "도어", "door", "누수", "물이 새", "leak"]):
        topic = "도어/누수 품질"
    elif any(token in lowered for token in ["디스플레이", "글씨", "화면", "display"]):
        topic = "표시/조작 사용성"
    elif any(token in lowered for token in ["as", "a/s", "서비스", "수리", "warranty", "repair"]):
        topic = "A/S 대응"
    elif any(token in lowered for token in ["가격", "비용", "비싸", "price", "cost", "expensive"]):
        topic = "비용·구매조건"
    else:
        topic = _safe_text(aspect_key) or "제품 경험"
    return f"{product} · {topic}"


def _task_candidate(topic_group: str, unit_type: str, sentiment_code: str, text: str) -> str:
    corpus = f"{topic_group} {_safe_text(text)}".lower()
    if unit_type == "inquiry":
        if any(token in corpus for token in ["필터", "filter", "교체", "replace"]):
            return "필터 교체 방법 안내 강화"
        if any(token in corpus for token in ["가격", "비용", "price", "cost"]):
            return "구매·소모품 정보 안내 강화"
        return f"{topic_group.split(' · ')[-1]} 문의 해소"
    if unit_type == "praise" or sentiment_code == "positive":
        if any(token in corpus for token in ["필터", "filter", "먼지", "dust", "걸러"]):
            return "필터 먼지 포집 성능 메시지 강화"
        return f"{topic_group.split(' · ')[-1]} 강점 유지·확장"
    if any(token in corpus for token in ["냄새", "악취", "odor", "smell"]):
        if any(token in corpus for token in ["문", "열", "door", "open"]):
            return "위생관리: 문 열림 시 악취 개선"
        if any(token in corpus for token in ["잔수", "물", "고여", "건조", "dry"]):
            return "건조 후 잔수/냄새 의심 개선"
        return "냄새/위생 원인 개선"
    if any(token in corpus for token in ["흡입", "suction", "고양이 모래", "cat litter"]):
        if any(token in corpus for token in ["뱉", "다시", "재배출"]):
            return "고양이 모래/이물 재배출 원인 개선"
        return "흡입력 약함으로 인한 청소 실패 개선"
    if any(token in corpus for token in ["먼지통", "dust bin", "자동 먼지비움"]):
        if unit_type == "praise" or sentiment_code == "positive":
            return "먼지통 비움 편의성 Value Up"
        return "먼지통 비움 동선 부담 완화"
    if any(token in corpus for token in ["디스플레이", "글씨", "화면", "display"]):
        return "디스플레이 글씨/가독성 개선"
    if any(token in corpus for token in ["누수", "물이 새", "leak"]):
        return "초기 누수/도어 밀폐 품질 개선"
    if any(token in corpus for token in ["컴프레서", "밤", "소음", "noise"]):
        return "야간 컴프레서 소음 저감"
    if any(token in corpus for token in ["필터", "거름망", "filter"]):
        if any(token in corpus for token in ["청소", "세척", "hard", "불편", "힘들"]):
            return "필터/거름망 세척 부담 완화"
        if any(token in corpus for token in ["내구", "파손", "깨", "부러"]):
            return "필터 내구도 불만 개선"
        return "필터 사용성 개선"
    if any(token in corpus for token in ["앱", "wifi", "wi-fi", "thinq", "connect", "로그인"]):
        return "앱 연결 실패로 인한 사용 중단 개선"
    if any(token in corpus for token in ["가격", "비용", "price", "cost", "expensive"]):
        return "소모품 비용 부담 완화"
    return f"{topic_group.split(' · ')[-1]} 개선"


def _tee_s_profile(text: str, sentiment_code: str, inquiry_flag: bool) -> dict[str, dict[str, str]]:
    lowered = _safe_text(text).lower()

    def axis(status: str, evidence: str = "", meaning: str = "") -> dict[str, str]:
        return {"status": status, "evidence": evidence, "meaning": meaning}

    if sentiment_code == "positive":
        success = axis("success", text, "제품/서비스가 기대 역할을 충족한 신호입니다.")
    elif sentiment_code == "negative":
        success = axis("failure", text, "제품/서비스 경험이 기대에 미치지 못한 신호입니다.")
    else:
        success = axis("not_applicable", "", "")

    time_markers = ["오래", "늦", "지연", "기다", "반복", "매번", "자주", "항상", "month", "week", "delay", "always", "every time"]
    effort_markers = ["불편", "힘들", "어렵", "귀찮", "번거", "청소", "세척", "교체", "찾", "방법", "모르", "hard", "difficult", "annoying"]
    emotion_markers = ["불만", "짜증", "답답", "실망", "불쾌", "걱정", "불안", "만족", "좋", "추천", "최고", "annoying", "love", "satisfied"]
    time_hit = next((marker for marker in time_markers if marker in lowered), "")
    effort_hit = next((marker for marker in effort_markers if marker in lowered), "")
    emotion_hit = next((marker for marker in emotion_markers if marker in lowered), "")

    if time_hit in {"늦", "지연", "기다", "delay"}:
        time_status = "delay"
    elif time_hit:
        time_status = "repeat_frequency" if time_hit in {"반복", "매번", "자주", "항상", "always", "every time"} else "time_signal"
    else:
        time_status = "not_mentioned"
    effort_status = "hard" if effort_hit or inquiry_flag else "not_mentioned"
    if "모르" in lowered or "?" in lowered:
        emotion_status = "uncertainty"
    elif sentiment_code == "positive":
        emotion_status = "satisfaction"
    elif sentiment_code == "negative":
        emotion_status = "frustration"
    else:
        emotion_status = "not_mentioned"

    return {
        "success": success,
        "time": axis(time_status, text if time_status != "not_mentioned" else "", "반복, 지연, 초기 실패, 사용 주기처럼 운영 판단에 필요한 시간 신호입니다." if time_status != "not_mentioned" else ""),
        "effort": axis(effort_status, text if effort_status != "not_mentioned" else "", "탐색·사용·관리·교체 과정에서 고객이 추가 노력을 쓰는 신호입니다." if effort_status != "not_mentioned" else ""),
        "emotion": axis(emotion_status, text if emotion_status != "not_mentioned" else "", "만족, 불쾌감, 불안, 불확실성처럼 우선순위 판단에 영향을 주는 정서 신호입니다." if emotion_status != "not_mentioned" else ""),
    }


def _product_fields(row: pd.Series, clause_text: str) -> dict[str, Any]:
    product_raw = _safe_text(row.get("product", ""))
    title_text = _safe_text(row.get("title", ""))
    source_blob = " ".join([clause_text, product_raw, title_text])
    category = PRODUCT_MAP.get(product_raw, product_raw or "Other")
    subtype, subtype_hits = _derive_product_subtype(category, source_blob)
    model_tokens = _extract_model_tokens(source_blob)
    model_mentioned = _safe_text(row.get("model_mentioned", "")) or (model_tokens[0] if model_tokens else "")
    evidence = []
    for token in [product_raw, title_text, *subtype_hits, *model_tokens[:1]]:
        token = _safe_text(token)
        if token and token not in evidence and token.lower() in source_blob.lower():
            evidence.append(token)
    return {
        "product_category": category or "Other",
        "product_subtype": _safe_text(row.get("product_subtype", "")) or subtype or "Unknown",
        "brand_mentioned": _safe_text(row.get("brand_label", "")),
        "model_mentioned": model_mentioned,
        "product_evidence_spans": evidence,
    }


def _strength_score(sentiment_code: str, signal_strength: str, text: str) -> float:
    lowered = _safe_text(text).lower()
    score = 8.0 if sentiment_code in {"positive", "negative"} and signal_strength == "strong" else 5.0 if sentiment_code in {"positive", "negative"} else 0.0
    score += 2.0 * sum(1 for token in ["\uc9c4\uc9dc", "\uc644\uc804", "\ub108\ubb34", "\ucd5c\uace0", "\ucd5c\uc545", "\uc808\ub300", "\ubb34\uc870\uac74", "always", "never", "worst", "best"] if token in lowered)
    return max(0.0, min(score, 10.0))


def _richness_score(text: str) -> float:
    lowered = _safe_text(text).lower()
    length = len(lowered)
    len_bucket = 0 if length < 20 else 1 if length < 60 else 2 if length < 140 else 3
    score = float(len_bucket)
    score += 2.0 * sum(1 for token in ["because", "so ", "\ub54c\ubb38", "\ud574\uc11c", "\uadf8\ub798\uc11c"] if token in lowered)
    score += 2.0 * sum(1 for token in ["when", "if ", "\ud560 \ub54c", "\ubaa8\ub4dc", "\uc124\uc815"] if token in lowered)
    score += 2.0 * sum(1 for token in ["month", "week", "year", "3\uac1c\uc6d4", "2\uc8fc", "\ud55c\ub2ec", "\ub9e4\ubc88"] if token in lowered)
    score += 1.0 * sum(1 for token in ["than", "compared", "\ubcf4\ub2e4", "\uc774\uc804", "\uc804 \ubaa8\ub378"] if token in lowered)
    return max(0.0, min(score, 10.0))


def _normalized_bundle_text(text: str) -> str:
    lowered = _safe_text(text).lower()
    lowered = re.sub(r"[^\w\s\uac00-\ud7a3]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered[:120]


def _is_bundle_candidate(row: pd.Series) -> bool:
    sentiment = _safe_text(row.get("sentiment_code", "neutral")).lower()
    if sentiment not in {"positive", "negative"}:
        return False
    if bool(row.get("duplicate_opinion_flag", False)):
        return False
    if bool(row.get("inquiry_flag", False)) and _safe_text(row.get("classification_type", "")).lower() == "informational":
        return False
    if not bool(row.get("product_related", False)):
        return False
    return True


def _likes_score(likes_count: Any) -> float:
    try:
        likes = float(likes_count)
    except Exception:
        likes = 0.0
    return max(0.0, min(math.log10(1.0 + max(likes, 0.0)) * 4.0, 10.0))


def _quality_penalty(row: pd.Series) -> float:
    penalty = 0.0
    if bool(row.get("spam_like", False)):
        penalty += 7.0
    return penalty


def _compute_opinion_score(row: pd.Series, sentiment_code: str, clause_text: str, signal_strength: str) -> float:
    if sentiment_code not in {"positive", "negative"}:
        return 0.0
    strength = _strength_score(sentiment_code, signal_strength, clause_text)
    richness = _richness_score(clause_text)
    likes = _likes_score(row.get("like_count", 0))
    penalty = _quality_penalty(row)
    return (5.0 * strength) + (2.0 * richness) + (1.5 * likes) - penalty


def _masked_text(text: str, pii_raw_text: str) -> str:
    masked = _safe_text(text)
    pii_raw = _safe_text(pii_raw_text)
    if not masked or not pii_raw:
        return masked
    for chunk in [part.strip() for part in pii_raw.split(",") if part.strip()]:
        if len(chunk) >= 2:
            masked = masked.replace(chunk, "[PII]")
    return masked


def _routing_for_unit(unit_type: str, signal_strength: str, confidence_level: str, text: str) -> tuple[str, list[str]]:
    lowered = _safe_text(text).lower()
    review_reasons: list[str] = []
    if unit_type == "log_only":
        return "LOG_ONLY", []
    safety_markers = [
        "탄 냄새",
        "타는 냄새",
        "연기",
        "화재",
        "감전",
        "위험",
        "불꽃",
        "burning smell",
        "smoke",
        "fire",
        "electric shock",
    ]
    if any(marker in lowered for marker in safety_markers):
        review_reasons.append("safety_or_high_risk_signal")
    if unit_type == "review_needed":
        review_reasons.append("weak_or_ambiguous_unit")
    if unit_type == "inquiry" and any(marker in lowered for marker in ["궁금증", "클릭", "click"]):
        review_reasons.append("weak_or_ambiguous_inquiry")
    if _safe_text(confidence_level).lower() == "low" and _safe_text(signal_strength).lower() == "weak":
        review_reasons.append("low_confidence_weak_signal")
    if review_reasons:
        return "REVIEW_LANE", sorted(set(review_reasons))
    if unit_type == "inquiry":
        return "INQUIRY_LANE", []
    return "KEEP", []


def _topic_group_candidate(product_category: str, aspect_key: str, text: str) -> str:
    product = _safe_text(product_category) or "Other"
    lowered = _safe_text(text).lower()
    if any(token in lowered for token in ["냄새", "악취", "odor", "smell"]):
        topic = "위생관리"
    elif any(token in lowered for token in ["필터", "거름망", "filter"]):
        topic = "필터 사용성"
    elif any(token in lowered for token in ["앱", "wifi", "wi-fi", "thinq", "연동", "로그인", "connect"]):
        topic = "앱 연결/로그인"
    elif any(token in lowered for token in ["소음", "진동", "noise", "vibration"]):
        topic = "소음/진동"
    elif any(token in lowered for token in ["흡입", "suction", "먼지통", "dust bin"]):
        topic = "청소 성능/먼지비움"
    elif any(token in lowered for token in ["문", "도어", "door", "누수", "물이 새", "leak"]):
        topic = "도어/누수 품질"
    elif any(token in lowered for token in ["디스플레이", "글씨", "화면", "display"]):
        topic = "표시/조작 사용성"
    elif any(token in lowered for token in ["as", "a/s", "서비스", "수리", "warranty", "repair"]):
        topic = "A/S 대응"
    elif any(token in lowered for token in ["가격", "비용", "비쌈", "price", "cost", "expensive"]):
        topic = "비용/구매조건"
    else:
        topic = _safe_text(aspect_key) or "제품 경험"
    return f"{product} · {topic}"


def _task_candidate(topic_group: str, unit_type: str, sentiment_code: str, text: str) -> str:
    corpus = f"{topic_group} {_safe_text(text)}".lower()
    topic_label = topic_group.split(" · ")[-1]
    if unit_type == "inquiry":
        if any(token in corpus for token in ["필터", "filter", "교체", "replace"]):
            return "필터 교체 방법 안내 강화"
        if any(token in corpus for token in ["가격", "비용", "price", "cost"]):
            return "구매/소모품 정보 안내 강화"
        return f"{topic_label} 문의 해소"
    if unit_type == "praise" or sentiment_code == "positive":
        if any(token in corpus for token in ["필터", "filter", "먼지", "dust", "걸러"]):
            return "필터 먼지 포집 성능 메시지 강화"
        if any(token in corpus for token in ["먼지통", "dust bin", "자동 먼지비움"]):
            return "먼지통 비움 편의성 Value Up"
        return f"{topic_label} 강점 유지/확장"
    if any(token in corpus for token in ["냄새", "악취", "odor", "smell"]):
        if any(token in corpus for token in ["문", "열", "door", "open"]):
            return "위생관리: 문 열림 시 악취 개선"
        if any(token in corpus for token in ["잔수", "물", "고여", "건조", "dry"]):
            return "건조 후 잔수/냄새 의심 개선"
        return "냄새/위생 원인 개선"
    if any(token in corpus for token in ["흡입", "suction", "고양이 모래", "cat litter"]):
        if any(token in corpus for token in ["뱉", "다시", "재배출"]):
            return "고양이 모래/이물 재배출 원인 개선"
        return "흡입력 약함으로 인한 청소 실패 개선"
    if any(token in corpus for token in ["먼지통", "dust bin", "자동 먼지비움"]):
        return "먼지통 비움 동선 부담 완화"
    if any(token in corpus for token in ["디스플레이", "글씨", "화면", "display"]):
        return "디스플레이 글씨 가독성 개선"
    if any(token in corpus for token in ["누수", "물이 새", "leak"]):
        return "초기 누수/도어 밀폐 품질 개선"
    if any(token in corpus for token in ["컴프레서", "밤", "소음", "noise"]):
        return "야간 컴프레서 소음 저감"
    if any(token in corpus for token in ["필터", "거름망", "filter"]):
        if any(token in corpus for token in ["청소", "세척", "hard", "불편", "힘들"]):
            return "필터/거름망 세척 부담 완화"
        if any(token in corpus for token in ["내구", "파손", "찢", "부러"]):
            return "필터 내구도 불만 개선"
        return "필터 사용성 개선"
    if any(token in corpus for token in ["앱", "wifi", "wi-fi", "thinq", "connect", "로그인"]):
        return "앱 연결 실패로 인한 사용 중단 개선"
    if any(token in corpus for token in ["가격", "비용", "price", "cost", "expensive"]):
        return "소모품 비용 부담 완화"
    return f"{topic_label} 개선"


def _tee_s_profile(text: str, sentiment_code: str, inquiry_flag: bool) -> dict[str, dict[str, str]]:
    lowered = _safe_text(text).lower()

    def axis(status: str, evidence: str = "", meaning: str = "") -> dict[str, str]:
        return {"status": status, "evidence": evidence, "meaning": meaning}

    if sentiment_code == "positive":
        success = axis("success", text, "제품/서비스가 고객 기대를 충족한 신호입니다.")
    elif sentiment_code == "negative":
        success = axis("failure", text, "제품/서비스 경험이 고객 기대에 미치지 못한 신호입니다.")
    else:
        success = axis("not_applicable", "", "")

    time_markers = ["오래", "늦", "지연", "기다", "반복", "매번", "자주", "항상", "month", "week", "delay", "always", "every time"]
    effort_markers = ["불편", "힘들", "어려", "귀찮", "번거", "청소", "세척", "교체", "찾", "방법", "모르", "hard", "difficult", "annoying"]
    emotion_markers = ["불만", "짜증", "답답", "실망", "불쾌", "걱정", "불안", "만족", "좋", "추천", "최고", "annoying", "love", "satisfied"]
    time_hit = next((marker for marker in time_markers if marker in lowered), "")
    effort_hit = next((marker for marker in effort_markers if marker in lowered), "")
    emotion_hit = next((marker for marker in emotion_markers if marker in lowered), "")

    if time_hit in {"늦", "지연", "기다", "delay"}:
        time_status = "delay"
    elif time_hit:
        time_status = "repeat_frequency" if time_hit in {"반복", "매번", "자주", "항상", "always", "every time"} else "time_signal"
    else:
        time_status = "not_mentioned"
    effort_status = "hard" if effort_hit or inquiry_flag else "not_mentioned"
    if "모르" in lowered or "?" in lowered:
        emotion_status = "uncertainty"
    elif sentiment_code == "positive":
        emotion_status = "satisfaction"
    elif sentiment_code == "negative":
        emotion_status = "frustration"
    elif emotion_hit:
        emotion_status = "emotion_signal"
    else:
        emotion_status = "not_mentioned"

    return {
        "success": success,
        "time": axis(time_status, text if time_status != "not_mentioned" else "", "반복, 지연, 초기 실패, 사용 주기처럼 운영 판단에 필요한 시간 신호입니다." if time_status != "not_mentioned" else ""),
        "effort": axis(effort_status, text if effort_status != "not_mentioned" else "", "탐색, 사용, 관리 과정에서 고객에게 추가 노력이 생기는 신호입니다." if effort_status != "not_mentioned" else ""),
        "emotion": axis(emotion_status, text if emotion_status != "not_mentioned" else "", "만족, 불쾌감, 불안, 불확실성처럼 우선순위 판단에 영향을 주는 정서 신호입니다." if emotion_status != "not_mentioned" else ""),
    }


def _topic_group_candidate(product_category: str, aspect_key: str, text: str) -> str:
    product = _safe_text(product_category) or "Other"
    lowered = _safe_text(text).lower()
    if any(token in lowered for token in ["가격", "비용", "비쌈", "구매", "구입", "중고", "페이코", "만원", "price", "cost", "expensive"]):
        topic = "비용/구매조건"
    elif any(token in lowered for token in ["씨앗", "씨 ", "씨를", "씨 넣", "씨앗키트", "키트", "키울", "키우", "베지", "그로우폼", "암면", "식물", "재배", "수확", "발아", "틔운", "화분", "뿌리", "옮겨심", "눈뽕", "풀", "고구마", "빛", "수분", "바람", "공기"]):
        topic = "씨앗키트/재배 관리"
    elif any(token in lowered for token in ["냄새", "악취", "odor", "smell"]):
        topic = "위생관리"
    elif any(token in lowered for token in ["필터", "거름망", "filter"]):
        topic = "필터 사용성"
    elif any(token in lowered for token in ["앱", "wifi", "wi-fi", "thinq", "연동", "로그인", "connect"]):
        topic = "앱 연결/로그인"
    elif any(token in lowered for token in ["소음", "진동", "noise", "vibration"]):
        topic = "소음/진동"
    elif any(token in lowered for token in ["흡입", "suction", "먼지통", "dust bin"]):
        topic = "청소 성능/먼지비움"
    elif any(token in lowered for token in ["문", "도어", "door", "누수", "물이 새", "leak"]):
        topic = "도어/누수 품질"
    elif any(token in lowered for token in ["디스플레이", "글씨", "화면", "display"]):
        topic = "표시/조작 사용성"
    elif any(token in lowered for token in ["as", "a/s", "서비스", "수리", "warranty", "repair"]):
        topic = "A/S 대응"
    else:
        topic = _safe_text(aspect_key) or "사용 경험"
    return f"{product} · {topic}"


def _task_candidate(topic_group: str, unit_type: str, sentiment_code: str, text: str) -> str:
    corpus = f"{topic_group} {_safe_text(text)}".lower()
    topic_label = topic_group.split("·")[-1].strip() if "·" in topic_group else topic_group
    if unit_type == "inquiry":
        if any(token in corpus for token in ["가격", "비용", "구매", "구입", "중고", "페이코", "만원", "price", "cost"]):
            return "구매/소모품 정보 안내 강화"
        if any(token in corpus for token in ["씨앗", "씨 ", "씨를", "씨 넣", "씨앗키트", "키트", "키울", "키우", "베지", "그로우폼", "암면", "식물", "재배", "수확", "발아", "틔운", "화분", "뿌리", "옮겨심", "눈뽕", "풀", "고구마", "빛", "수분", "바람", "공기"]):
            return "씨앗키트 구매/재배 관리 안내 강화"
        if any(token in corpus for token in ["필터", "filter", "교체", "replace"]):
            return "필터 교체 방법 안내 강화"
        return f"{topic_label} 문의 해소"
    if unit_type == "praise" or sentiment_code == "positive":
        if any(token in corpus for token in ["필터", "filter", "먼지", "dust", "걸러"]):
            return "필터 먼지 포집 성능 메시지 강화"
        if any(token in corpus for token in ["먼지통", "dust bin", "자동 먼지비움"]):
            return "먼지통 비움 편의성 Value Up"
        if any(token in corpus for token in ["씨앗", "식물", "재배", "수확", "틔운", "빛", "수분", "바람", "공기"]):
            return "실내 재배 성공 경험 Value Up"
        return f"{topic_label} 강점 유지/확장"
    if any(token in corpus for token in ["씨앗", "씨 ", "씨를", "씨 넣", "씨앗키트", "키트", "키울", "키우", "베지", "그로우폼", "암면", "식물", "재배", "수확", "발아", "틔운", "화분", "뿌리", "옮겨심", "눈뽕", "풀", "고구마", "빛", "수분", "바람", "공기"]):
        return "씨앗키트 구매/재배 관리 개선"
    if any(token in corpus for token in ["냄새", "악취", "odor", "smell"]):
        if any(token in corpus for token in ["문", "열", "door", "open"]):
            return "위생관리: 문 열림 시 악취 개선"
        if any(token in corpus for token in ["잔수", "물", "고여", "건조", "dry"]):
            return "건조 후 잔수/냄새 의심 개선"
        return "냄새/위생 원인 개선"
    if any(token in corpus for token in ["흡입", "suction", "고양이 모래", "cat litter"]):
        if any(token in corpus for token in ["뱉", "다시", "재배출"]):
            return "고양이 모래/이물 재배출 원인 개선"
        return "흡입력 약함으로 인한 청소 실패 개선"
    if any(token in corpus for token in ["먼지통", "dust bin", "자동 먼지비움"]):
        return "먼지통 비움 동선 부담 완화"
    if any(token in corpus for token in ["디스플레이", "글씨", "화면", "display"]):
        return "디스플레이 글씨 가독성 개선"
    if any(token in corpus for token in ["누수", "물이 새", "leak"]):
        return "초기 누수/도어 밀폐 품질 개선"
    if any(token in corpus for token in ["컴프레서", "밤", "소음", "noise"]):
        return "야간 컴프레서 소음 저감"
    if any(token in corpus for token in ["필터", "거름망", "filter"]):
        if any(token in corpus for token in ["청소", "세척", "hard", "불편", "힘들"]):
            return "필터/거름망 세척 부담 완화"
        if any(token in corpus for token in ["내구", "파손", "찢", "부러"]):
            return "필터 내구도 불만 개선"
        return "필터 사용성 개선"
    if any(token in corpus for token in ["앱", "wifi", "wi-fi", "thinq", "connect", "로그인"]):
        return "앱 연결 실패로 인한 사용 중단 개선"
    if any(token in corpus for token in ["가격", "비용", "price", "cost", "expensive"]):
        return "소모품 비용 부담 완화"
    return f"{topic_label} 개선"


def build_opinion_units(comments_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if comments_df.empty:
        return pd.DataFrame()

    for _, row in comments_df.iterrows():
        source_id = _safe_text(row.get("comment_id", ""))
        source_text = _safe_text(row.get("text_display", row.get("cleaned_text", "")))
        validity = _safe_text(row.get("comment_validity", "valid")) or "valid"
        parent_comment = _safe_text(row.get("parent_comment_text", ""))
        context_comments = [_safe_text(row.get("title", "")), _safe_text(row.get("product", ""))]
        clauses = _split_opinion_text(source_text) or [source_text]
        opinion_count = len([clause for clause in clauses if _safe_text(clause)]) or 1
        fallback_scene = _safe_text(row.get("topic_label", ""))

        for idx, clause in enumerate(clauses, start=1):
            clause_text = _safe_text(clause)
            if not clause_text:
                continue
            if len(clauses) == 1:
                sentiment_code = _safe_text(row.get("sentiment_label", "neutral")).lower() or "neutral"
                signal_strength = _safe_text(row.get("signal_strength", "weak")) or "weak"
                classification_type = _safe_text(row.get("classification_type", "informational")) or "informational"
                confidence_level = _safe_text(row.get("confidence_level", "low")) or "low"
                reason = _safe_text(row.get("classification_reason", ""))
                product_related = bool(row.get("product_related", False))
            else:
                result = analyze_comment_with_context(
                    clause_text,
                    validity=validity,
                    exclusion_reason=_safe_text(row.get("exclusion_reason", "")) or None,
                    parent_comment=parent_comment,
                    context_comments=context_comments,
                    is_reply=bool(row.get("is_reply", False)),
                )
                sentiment_code = _safe_text(result.sentiment_label or "neutral").lower() or "neutral"
                signal_strength = _safe_text(result.signal_strength or "weak") or "weak"
                classification_type = _safe_text(result.classification_type or "informational") or "informational"
                confidence_level = _safe_text(result.confidence_level or "low") or "low"
                reason = _safe_text(result.reason)
                product_related = bool(result.product_related)
                if sentiment_code not in {"positive", "negative"}:
                    sentiment_code = _clause_sentiment_fallback(clause_text, "neutral")
                    if sentiment_code in {"positive", "negative"}:
                        signal_strength = "medium" if signal_strength == "weak" else signal_strength
                        classification_type = "praise" if sentiment_code == "positive" else "complaint"
                        confidence_level = "medium" if confidence_level == "low" else confidence_level
                        product_related = True
                        reason = reason or "split clause sentiment fallback"

            if validity != "valid":
                sentiment_code = "excluded"
                signal_strength = "weak"
                classification_type = "informational"
                confidence_level = "low"

            forced_review_reasons: list[str] = []
            context_reason = _context_review_reason(clause_text) if validity == "valid" else ""
            if context_reason:
                sentiment_code = "neutral"
                signal_strength = "weak"
                classification_type = "video_context"
                confidence_level = "low"
                product_related = False
                forced_review_reasons.append(context_reason)
                reason = (
                    "영상 시간대/자막/실험 화면에 대한 맥락 댓글로 제품 VoC 자동 과제화 전 검수가 필요합니다."
                    if context_reason == "video_context_or_caption_comment"
                    else "단순 소감 또는 정보공유 반응으로 구매/소모품 과제화 전 검수가 필요합니다."
                )
            elif validity == "valid" and _is_weak_reaction_only(clause_text):
                sentiment_code = "neutral"
                signal_strength = "weak"
                classification_type = "weak_reaction"
                confidence_level = "low"
                product_related = False
                forced_review_reasons.append("weak_reaction_without_actionable_evidence")
                reason = "단순 감정 반응만 있어 제품 개선과제 근거로 쓰기 어렵습니다."
            elif sentiment_code == "positive" and _is_usage_friction_comment(clause_text):
                sentiment_code = "negative"
                signal_strength = "medium" if signal_strength == "weak" else signal_strength
                classification_type = "complaint"
                reason = "긍정 표현 안에 사용 노력/표시/넘침 같은 보완 신호가 있어 개선 Unit으로 해석했습니다."

            scene = _derive_scene(clause_text, fallback_scene=_safe_text(fallback_scene))
            aspect_key, aspect_marker = _derive_aspect(clause_text)
            inquiry_flag, inquiry_types = _extract_inquiry(clause_text)
            product_fields = _product_fields(row, clause_text)
            evidence_spans = _extract_evidence_spans(clause_text, aspect_marker=aspect_marker)
            pii_flag = "Y" if _safe_text(row.get("pii_flag", "N")).upper() == "Y" else "N"
            pii_raw = _safe_text(row.get("pii_raw_text", ""))
            opinion_score = _compute_opinion_score(row, sentiment_code, clause_text, signal_strength)
            voc_unit_id = f"{source_id}#u{idx}"
            unit_type = _unit_type(sentiment_code, inquiry_flag, classification_type, validity)
            if forced_review_reasons:
                unit_type = "review_needed"
            routing, review_reasons = _routing_for_unit(unit_type, signal_strength, confidence_level, clause_text)
            if forced_review_reasons:
                review_reasons = sorted(set([*review_reasons, *forced_review_reasons]))
                routing = "REVIEW_LANE"
            topic_group_candidate = _topic_group_candidate(product_fields["product_category"], aspect_key, clause_text)
            if "video_context_or_caption_comment" in forced_review_reasons:
                topic_group_candidate = f"{product_fields['product_category']} · 영상/자막 맥락 검수"
            elif "simple_opinion_or_info_share" in forced_review_reasons:
                topic_group_candidate = f"{product_fields['product_category']} · 단순 소감 검수"
            elif "weak_reaction_without_actionable_evidence" in forced_review_reasons:
                topic_group_candidate = f"{product_fields['product_category']} · 약한 반응 검수"
            task_candidate = _task_candidate(topic_group_candidate, unit_type, sentiment_code, clause_text)
            if "video_context_or_caption_comment" in forced_review_reasons:
                task_candidate = "영상 맥락과 제품 VoC 분리 검수"
            elif "simple_opinion_or_info_share" in forced_review_reasons:
                task_candidate = "단순 소감/제품 VoC 여부 검수"
            elif "weak_reaction_without_actionable_evidence" in forced_review_reasons:
                task_candidate = "분석 제외/관찰 여부 검수"
            tee_s = _tee_s_profile(clause_text, sentiment_code, inquiry_flag)

            rows.append({
                "opinion_id": f"{source_id}::u{idx}",
                "voc_unit_id": voc_unit_id,
                "unit_type": unit_type,
                "routing": routing,
                "review_reasons_json": json.dumps(review_reasons, ensure_ascii=False),
                "source_content_id": source_id,
                "source_type": "YT_COMMENT",
                "source_count": 1,
                "opinion_count": opinion_count,
                "duplicate_opinion_flag": bool(row.get("spam_like", False)),
                "product_related": product_related,
                "opinion_text": clause_text,
                "cej_scene_code": scene,
                "sentiment_code": sentiment_code,
                "sentiment": sentiment_code.title(),
                "signal_strength": signal_strength,
                "classification_type": classification_type,
                "confidence_level": confidence_level,
                "aspect_key": aspect_key,
                "topic_group_candidate": topic_group_candidate,
                "task_candidate": task_candidate,
                "tee_s": json.dumps(tee_s, ensure_ascii=False),
                "evidence_spans_json": json.dumps(evidence_spans, ensure_ascii=False),
                "inquiry_flag": inquiry_flag,
                "inquiry_type_json": json.dumps(inquiry_types, ensure_ascii=False),
                "product_category": product_fields["product_category"],
                "product_subtype": product_fields["product_subtype"],
                "brand_mentioned": product_fields["brand_mentioned"],
                "model_mentioned": product_fields["model_mentioned"],
                "product_evidence_spans_json": json.dumps(product_fields["product_evidence_spans"], ensure_ascii=False),
                "likes_count": pd.to_numeric(row.get("like_count", 0), errors="coerce"),
                "source_link": _safe_text(row.get("video_url", "")),
                "region": _safe_text(row.get("region", "")),
                "product": _safe_text(row.get("product", "")),
                "title": _safe_text(row.get("title", "")),
                "pii_flag": pii_flag,
                "pii_types": _safe_text(row.get("pii_types", "")),
                "pii_raw_text": pii_raw,
                "display_text": _masked_text(clause_text, pii_raw) if pii_flag == "Y" else clause_text,
                "original_text": clause_text,
                "masked_text": _masked_text(clause_text, pii_raw) if pii_flag == "Y" else "",
                "translated_text": _safe_text(row.get("translated_text", row.get("\ud55c\uad6d\uc5b4 \ubc88\uc5ed", ""))),
                "summary_text": _safe_text(row.get("summary", row.get("short_summary_ko", ""))),
                "classification_reason": reason,
                "opinion_score": opinion_score,
            })
    return pd.DataFrame(rows)


def _bundle_selection_reason(top_row: pd.Series, cluster_size: int) -> str:
    sentiment = _safe_text(top_row.get("sentiment_code", "neutral"))
    sentiment_label = "??" if sentiment == "negative" else "??" if sentiment == "positive" else "??"
    strength = _strength_score(_safe_text(top_row.get("sentiment_code", "")), _safe_text(top_row.get("signal_strength", "weak")), _safe_text(top_row.get("opinion_text", "")))
    richness = _richness_score(_safe_text(top_row.get("opinion_text", "")))
    likes = top_row.get("likes_count")
    likes_text = ""
    try:
        if pd.notna(likes) and float(likes) > 0:
            likes_text = f", ???={int(float(likes))}"
    except Exception:
        likes_text = ""
    return f"?? {sentiment_label} ??(????={strength:.0f}/10), ?? ?? ??(????={richness:.0f}/10){likes_text}, ?? ?? {cluster_size}?? ???? ?? ??? ??????."


def build_representative_bundles(opinion_units_df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    if opinion_units_df.empty:
        return pd.DataFrame()
    working = opinion_units_df[opinion_units_df.apply(_is_bundle_candidate, axis=1)].copy()
    if working.empty:
        return pd.DataFrame()
    working["_dedup_text_key"] = working["opinion_text"].map(_normalized_bundle_text)
    working = working.sort_values(["opinion_score", "likes_count"], ascending=[False, False], na_position="last")
    working = working.drop_duplicates(
        subset=["sentiment_code", "product_category", "brand_mentioned", "cej_scene_code", "aspect_key", "_dedup_text_key"],
        keep="first",
    )
    rows: list[dict[str, Any]] = []
    group_cols = ["sentiment_code", "product_category", "product_subtype", "brand_mentioned", "cej_scene_code", "aspect_key"]
    for _, group in working.groupby(group_cols, dropna=False):
        ordered = group.sort_values(["opinion_score", "likes_count"], ascending=[False, False], na_position="last")
        top_row = ordered.iloc[0]
        cluster_size = len(group)
        likes_sum = pd.to_numeric(group.get("likes_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
        size_bonus = max(0.0, min(math.log10(1.0 + cluster_size) * 5.0, 10.0))
        bundle_score = float(top_row.get("opinion_score", 0.0) or 0.0) + size_bonus + (0.5 * max(0.0, min(math.log10(1.0 + likes_sum) * 4.0, 10.0)))
        sample_comments = [
            {
                "opinion_id": _safe_text(sample.get("opinion_id", "")),
                "display_text": _safe_text(sample.get("display_text", "")),
                "translated_text": _safe_text(sample.get("translated_text", "")),
                "pii_flag": _safe_text(sample.get("pii_flag", "N")) or "N",
                "likes_count": None if pd.isna(sample.get("likes_count", pd.NA)) else int(float(sample.get("likes_count", 0) or 0)),
            }
            for _, sample in ordered.head(5).iterrows()
        ]
        evidence_spans = json.loads(_safe_text(top_row.get("evidence_spans_json", "[]")) or "[]")
        voc_items = [{
            "topic": _safe_text(top_row.get("aspect_key", "General")) or "General",
            "sentiment": _safe_text(top_row.get("sentiment", "Neutral")) or "Neutral",
            "insight_message": _safe_text(top_row.get("classification_reason", "")) or "\ub300\ud45c \uc758\uacac\uc758 \ud575\uc2ec \ud3ec\uc778\ud2b8\uc785\ub2c8\ub2e4.",
            "evidence_span": evidence_spans[0] if evidence_spans else _safe_text(top_row.get("opinion_text", "")),
        }]
        rows.append({
            "sentiment_code": _safe_text(top_row.get("sentiment_code", "")),
            "sentiment": _safe_text(top_row.get("sentiment", "")),
            "aspect_key": _safe_text(top_row.get("aspect_key", "General")) or "General",
            "cluster_size": cluster_size,
            "cej_scene_code": _safe_text(top_row.get("cej_scene_code", "S10 Other")) or "S10 Other",
            "product_category": _safe_text(top_row.get("product_category", "Other")) or "Other",
            "product_subtype": _safe_text(top_row.get("product_subtype", "Unknown")) or "Unknown",
            "brand_mentioned": _safe_text(top_row.get("brand_mentioned", "")),
            "model_mentioned": _safe_text(top_row.get("model_mentioned", "")),
            "bundle_score": bundle_score,
            "selection_reason": _bundle_selection_reason(top_row, cluster_size),
            "top_opinion_id": _safe_text(top_row.get("opinion_id", "")),
            "top_source_content_id": _safe_text(top_row.get("source_content_id", "")),
            "top_source_link": _safe_text(top_row.get("source_link", "")),
            "top_likes_count": None if pd.isna(top_row.get("likes_count", pd.NA)) else int(float(top_row.get("likes_count", 0) or 0)),
            "top_pii_flag": _safe_text(top_row.get("pii_flag", "N")) or "N",
            "top_pii_types": _safe_text(top_row.get("pii_types", "")),
            "top_display_text": _safe_text(top_row.get("display_text", "")),
            "top_original_text": _safe_text(top_row.get("original_text", "")),
            "top_masked_text": _safe_text(top_row.get("masked_text", "")),
            "top_translation_text": _safe_text(top_row.get("translated_text", "")),
            "top_summary_text": _safe_text(top_row.get("summary_text", "")),
            "pii_raw_text": _safe_text(top_row.get("pii_raw_text", "")),
            "sample_comments_json": json.dumps(sample_comments, ensure_ascii=False),
            "voc_items_json": json.dumps(voc_items, ensure_ascii=False),
            "region": _safe_text(top_row.get("region", "")),
            "product": _safe_text(top_row.get("product", "")),
        })
    bundle_df = pd.DataFrame(rows)
    if bundle_df.empty:
        return bundle_df
    ranked_frames = []
    bundle_df["_top_text_key"] = bundle_df["top_display_text"].map(_normalized_bundle_text)
    for sentiment_code in ["negative", "positive"]:
        subset = bundle_df[bundle_df["sentiment_code"] == sentiment_code].sort_values(["bundle_score", "cluster_size"], ascending=[False, False])
        subset = subset.drop_duplicates(subset=["product_category", "brand_mentioned", "aspect_key", "_top_text_key"], keep="first").head(top_n).copy()
        if subset.empty:
            continue
        subset["rank"] = range(1, len(subset) + 1)
        ranked_frames.append(subset.drop(columns=["_top_text_key"], errors="ignore"))
    return pd.concat(ranked_frames, ignore_index=True) if ranked_frames else pd.DataFrame(columns=bundle_df.columns.tolist() + ["rank"])



def build_source_records(opinion_units_df: pd.DataFrame) -> list[dict[str, Any]]:
    if opinion_units_df.empty:
        return []
    records: list[dict[str, Any]] = []
    for source_id, group in opinion_units_df.groupby("source_content_id", dropna=False):
        first = group.iloc[0]
        opinion_units: list[dict[str, Any]] = []
        for _, row in group.iterrows():
            opinion_units.append({
                "opinion_id": _safe_text(row.get("opinion_id", "")),
                "voc_unit_id": _safe_text(row.get("voc_unit_id", "")),
                "unit_type": _safe_text(row.get("unit_type", "")),
                "opinion_text": _safe_text(row.get("opinion_text", "")),
                "cej_scene_code": _safe_text(row.get("cej_scene_code", "S10 Other")) or "S10 Other",
                "sentiment": _safe_text(row.get("sentiment", "Neutral")) or "Neutral",
                "inquiry_flag": bool(row.get("inquiry_flag", False)),
                "inquiry_type": json.loads(_safe_text(row.get("inquiry_type_json", "[]")) or "[]"),
                "aspect_key": _safe_text(row.get("aspect_key", "")),
                "topic_group_candidate": _safe_text(row.get("topic_group_candidate", "")),
                "task_candidate": _safe_text(row.get("task_candidate", "")),
                "tee_s": json.loads(_safe_text(row.get("tee_s", "{}")) or "{}"),
                "evidence_spans": json.loads(_safe_text(row.get("evidence_spans_json", "[]")) or "[]"),
                "product": {
                    "product_category": _safe_text(row.get("product_category", "Other")) or "Other",
                    "product_subtype": _safe_text(row.get("product_subtype", "Unknown")) or "Unknown",
                    "brand_mentioned": _safe_text(row.get("brand_mentioned", "")),
                    "model_mentioned": _safe_text(row.get("model_mentioned", "")),
                    "product_evidence_spans": json.loads(_safe_text(row.get("product_evidence_spans_json", "[]")) or "[]"),
                },
            })
        records.append({
            "source_content_id": _safe_text(source_id),
            "source_type": _safe_text(first.get("source_type", "YT_COMMENT")) or "YT_COMMENT",
            "source_count": 1,
            "pii_flag": _safe_text(first.get("pii_flag", "N")) or "N",
            "pii_types": _safe_text(first.get("pii_types", "")),
            "pii_raw_text": _safe_text(first.get("pii_raw_text", "")),
            "context_attachment": None,
            "opinion_units": opinion_units,
            "opinion_count": len(opinion_units),
            "duplicate_opinion_flag": bool(first.get("duplicate_opinion_flag", False)),
        })
    return records


def build_representative_section_payload(bundle_df: pd.DataFrame) -> dict[str, Any]:
    payload = {
        "positive_top5_bundles": [],
        "negative_top5_bundles": [],
        "section_notes": [
            "??(Original)? AI ??(??)? ?? ??? ???? ????? ????.",
            "PII ?? ??? ???? ???? ?? ??? ?????, ???? ????? ??? ????.",
            "?? ???? ??? ???? ???? ?? aspect ??? ?? ?? ?? ???? ????.",
        ],
    }
    if bundle_df.empty:
        return payload
    for sentiment_code, key in [("positive", "positive_top5_bundles"), ("negative", "negative_top5_bundles")]:
        subset = bundle_df[bundle_df["sentiment_code"] == sentiment_code].sort_values(["rank", "bundle_score"], ascending=[True, False])
        for _, row in subset.iterrows():
            sample_comments = json.loads(_safe_text(row.get("sample_comments_json", "[]")) or "[]")
            payload[key].append({
                "rank": int(row.get("rank", 0) or 0),
                "sentiment": sentiment_code.upper(),
                "aspect_key": _safe_text(row.get("aspect_key", "General")) or "General",
                "cluster_size": int(row.get("cluster_size", 0) or 0),
                "cej_scene_code": _safe_text(row.get("cej_scene_code", "S10 Other")) or "S10 Other",
                "product": {
                    "product_category": _safe_text(row.get("product_category", "Other")) or "Other",
                    "product_subtype": _safe_text(row.get("product_subtype", "Unknown")) or "Unknown",
                    "brand_mentioned": _safe_text(row.get("brand_mentioned", "")),
                    "model_mentioned": _safe_text(row.get("model_mentioned", "")),
                },
                "top_comment": {
                    "source_content_id": _safe_text(row.get("top_source_content_id", "")),
                    "source_link": _safe_text(row.get("top_source_link", "")),
                    "likes_count": None if pd.isna(row.get("top_likes_count", pd.NA)) else int(float(row.get("top_likes_count", 0) or 0)),
                    "pii_flag": _safe_text(row.get("top_pii_flag", "N")) or "N",
                    "pii_types": _safe_text(row.get("top_pii_types", "")),
                    "display_text": _safe_text(row.get("top_display_text", "")),
                    "original_text": _safe_text(row.get("top_original_text", "")),
                    "masked_text": _safe_text(row.get("top_masked_text", "")),
                    "translation": {"translated_text": _safe_text(row.get("top_translation_text", "")), "note": "??"},
                },
                "selection_reason": _safe_text(row.get("selection_reason", "")),
                "pii_review_panel": {
                    "expand_label": "???? ??(?????)",
                    "pii_raw_text": _safe_text(row.get("pii_raw_text", "")),
                },
                "drilldown": {
                    "expand_label": "?? ??? ??",
                    "sample_comments": sample_comments[:5],
                },
            })
    return payload
