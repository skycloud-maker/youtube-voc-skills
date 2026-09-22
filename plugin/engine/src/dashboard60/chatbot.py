"""Natural-language helper for dashboard operation only.

★ 2026-08-20 현재 이 모듈은 화면에 붙어 있지 않다 (sky 판단).
  하는 일이 「유튜브 실행 파라미터 설정」 과 「필터 적용」 둘뿐인데,
  둘 다 사이드바에 직접 UI 가 있어 같은 일로 가는 두 번째 입구였고,
  그 입구가 잘 동작하지 않았다. app_operating.py 의 호출만 끊었고
  코드와 시험(tests/test_dashboard60_chatbot.py)은 되살릴 때를 위해 남겼다.
  다시 붙이려면 app_operating.py 사이드바에서 render_chatbot_assistant 를 부르면 된다.

This module deliberately does not judge VoC quality. It only translates a
small set of natural-language requests into existing dashboard actions:

1. fill/confirm first-pass YouTube analysis parameters, then call the existing
   dashboard analysis subprocess,
2. set existing sidebar filters.

Channel-like phrases such as "귀곰 채널" are treated as ordinary YouTube search
keywords. We intentionally do not validate whether a channel exists because the
dashboard dataset does not reliably carry channel metadata, and keyword
intersection search is sufficient for this prototype.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from src.dashboard60 import analysis_runner


CHATBOT_TEXT_KEY = "dashboard60_chatbot_text"
CHATBOT_PLAN_KEY = "dashboard60_chatbot_plan"
CHATBOT_ANALYSIS_EDIT_PREFIX = "dashboard60_chatbot_analysis_edit"
DEFAULT_CHATBOT_KEYWORD_MODEL = "gpt-4o-mini"

SUPPORTED_EXAMPLES = (
    "귀곰 채널 LG가전 영상 5개 VoC 분석해줘",
    "브랜드는 LG, 제품군은 로봇청소기로 필터 걸어줘",
)

KNOWN_BRANDS = {
    "LG": {"lg", "엘지", "lg전자", "lg가전"},
    "삼성": {"삼성", "삼성전자"},
    "로보락": {"로보락", "roborock"},
    "드리미": {"드리미", "dreame"},
    "에코백스": {"에코백스", "ecovacs"},
    "DJI": {"dji"},
    "나르왈": {"나르왈", "narwal"},
    "샤오미": {"샤오미", "xiaomi"},
    "피세아": {"피세아", "picea"},
    "중국 브랜드": {"중국브랜드", "중국 브랜드", "중국회사", "중국기업"},
}

KNOWN_PRODUCT_CATEGORIES = {
    "로봇청소기": {"로봇청소기", "로봇 청소기", "로청", "로니"},
    "식기세척기": {"식기세척기", "식기 세척기", "식세기"},
    "세탁기": {"세탁기"},
    "건조기": {"건조기"},
    "냉장고": {"냉장고"},
}


@dataclass(frozen=True)
class AnalysisPlan:
    keywords: list[str]
    keyword_mode: str = "AND"
    max_videos: int = 3
    comments_per_video: int = 20
    limit: int = 60
    product: str = ""
    region: str = "KR"
    language: str = "ko"
    include_replies: bool = True
    channel_id: str = ""
    brand: str = ""
    run_suffix: str = "chatbot_youtube_run"
    parse_error: str = ""


@dataclass(frozen=True)
class FilterPlan:
    products: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    markets: list[str] = field(default_factory=list)
    cejs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChatPlan:
    intent: str
    summary: str
    analysis: AnalysisPlan | None = None
    filters: FilterPlan | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = _safe_text(raw)
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _extract_first_int(text: str, patterns: Iterable[str], default: int) -> int:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            for group in match.groups():
                if group and group.isdigit():
                    return int(group)
    return default


class KeywordExtractionError(RuntimeError):
    """Raised when LLM keyword extraction cannot produce usable keywords."""


KEYWORD_EXTRACTION_SYSTEM_PROMPT = """\
You extract YouTube search keywords from Korean dashboard requests.
Return only keywords that should be sent to YouTube search.

Include:
- brand names, channel names, product categories, product names, and model names
- English model names inside parentheses as separate keywords

Exclude:
- verbs, endings, particles, helper phrases, quantities, and generic nouns
- words meaning video, comments, review, reaction, evaluation, analysis, collection, request, recent, all, possible, and similar operational instructions

Preserve brand and model names exactly. Never trim Korean brand names as if the final syllable were a particle.
브랜드명·모델명은 원형 그대로 보존하고, 한국어 마지막 음절을 조사처럼 잘라내지 마세요.
Limit the result to at most 6 keywords. If there are no usable search terms, return an empty list.

Examples:
- "테크몽 채널 애플 맥북(M5) 영상 4개 분석해줘" -> {"keywords":["테크몽","애플","맥북","M5"]}
- "린나이 보일러랑 경동나비엔 온수기 비교 댓글 모아줘" -> {"keywords":["린나이","보일러","경동나비엔","온수기"]}
- "김반장 채널 발뮤다 조명 후기 찾아봐줘" -> {"keywords":["김반장","발뮤다","조명"]}
"""

KEYWORD_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["keywords"],
}


def _parse_keyword_payload(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise KeywordExtractionError("LLM keyword response is not an object")
    raw_keywords = payload.get("keywords")
    if not isinstance(raw_keywords, list):
        raise KeywordExtractionError("LLM keyword response has no keywords array")
    keywords = _dedupe(str(item).strip() for item in raw_keywords if str(item).strip())
    if len(keywords) > 6:
        raise KeywordExtractionError("LLM keyword response contains more than 6 keywords")
    return keywords


def _call_keyword_extraction_llm(text: str, *, model: str | None = None, timeout_seconds: int = 30) -> dict[str, Any]:
    api_key = analysis_runner._resolve_openai_api_key()
    if not api_key:
        raise KeywordExtractionError("OPENAI_API_KEY is not set")
    selected_model = model or os.environ.get("VOC_CHATBOT_MODEL") or os.environ.get("OPENAI_MODEL") or DEFAULT_CHATBOT_KEYWORD_MODEL
    body = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": KEYWORD_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"request": text}, ensure_ascii=False)},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "dashboard_keyword_extraction",
                "strict": True,
                "schema": KEYWORD_EXTRACTION_SCHEMA,
            },
        },
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise KeywordExtractionError(f"OpenAI keyword extraction failed: HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise KeywordExtractionError(f"OpenAI keyword extraction failed: {exc}") from exc
    try:
        content = parsed["choices"][0]["message"]["content"] or "{}"
        return json.loads(content)
    except Exception as exc:
        raise KeywordExtractionError(f"OpenAI keyword extraction returned invalid JSON: {exc}") from exc


def _extract_keywords(text: str) -> list[str]:
    return _parse_keyword_payload(_call_keyword_extraction_llm(text))


def _canonical_from_alias(text: str, alias_map: dict[str, set[str]]) -> str:
    folded = _safe_text(text).casefold()
    if not folded:
        return ""
    for canonical, aliases in alias_map.items():
        if folded == canonical.casefold() or folded in {alias.casefold() for alias in aliases}:
            return canonical
    return ""


def _mentioned_canonical(text: str, alias_map: dict[str, set[str]]) -> str:
    folded = _safe_text(text).casefold()
    if not folded:
        return ""
    for canonical, aliases in alias_map.items():
        candidates = {canonical.casefold(), *(alias.casefold() for alias in aliases)}
        if any(candidate and candidate in folded for candidate in candidates):
            return canonical
    return ""


def _extract_explicit_value(text: str, labels: Iterable[str]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{label_pattern})\s*(?:은|는|:|=)?\s*([0-9A-Za-z가-힣. -]+?)(?=\s*(?:브랜드|brand|제품군|제품|product|국가|시장|CEJ|cej|로|으로|만|필터|영상|댓글|분석|수집|,|$))",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _validate_execution_terms(text: str) -> tuple[str, str, list[str]]:
    """Validate explicit brand/product-category terms only.

    Channel names are intentionally not validated. They stay in the keyword
    list and are handled by the existing YouTube search/intersection pipeline.
    """

    errors: list[str] = []

    explicit_brand = _extract_explicit_value(text, ("브랜드", "brand"))
    brand = _canonical_from_alias(explicit_brand, KNOWN_BRANDS) if explicit_brand else _mentioned_canonical(text, KNOWN_BRANDS)
    if explicit_brand and not brand:
        errors.append(f"알 수 없는 브랜드입니다: {explicit_brand}. 브랜드명을 확인해 주세요.")

    # Generic prose such as "로니 제품에 대한 영상" must not be interpreted as
    # an explicit product-category assignment. Only labelled product-group
    # expressions participate in strict validation.
    explicit_product = _extract_explicit_value(text, ("제품군", "product"))
    product = (
        _canonical_from_alias(explicit_product, KNOWN_PRODUCT_CATEGORIES)
        if explicit_product
        else _mentioned_canonical(text, KNOWN_PRODUCT_CATEGORIES)
    )
    if explicit_product and not product:
        errors.append(f"알 수 없는 제품군입니다: {explicit_product}. 등록된 제품군만 사용할 수 있습니다.")

    return brand, product, errors


def parse_analysis_request(text: str) -> AnalysisPlan:
    brand, product_category, _errors = _validate_execution_terms(text)
    parse_error = ""
    try:
        keywords = _extract_keywords(text)
    except KeywordExtractionError as exc:
        keywords = []
        parse_error = str(exc)

    max_videos = _extract_first_int(
        text,
        [
            r"영상\s*(\d+)\s*개",
            r"(\d+)\s*개\s*영상",
            r"video[s]?\s*(\d+)",
        ],
        3,
    )
    comments_per_video = _extract_first_int(
        text,
        [
            r"영상당\s*댓글\s*(\d+)\s*(개|건)?",
            r"댓글\s*(\d+)\s*(개|건)",
            r"(\d+)\s*(개|건)\s*댓글",
        ],
        20,
    )
    all_videos = bool(re.search(r"(?:영상|비디오).{0,8}(?:전부|모두|가능한\s*모두)", text, re.IGNORECASE))
    all_comments = bool(re.search(r"(?:댓글).{0,8}(?:전부|모두|가능한\s*모두)", text, re.IGNORECASE))
    if all_videos:
        max_videos = analysis_runner.MAX_YOUTUBE_VIDEOS
    if all_comments:
        comments_per_video = 0
    explicit_limit = _extract_first_int(
        text,
        [
            r"최대\s*(\d+)\s*(행|건)",
            r"(\d+)\s*(행|건)\s*만",
        ],
        0,
    )
    limit = explicit_limit or (0 if all_videos or all_comments else max(1, max_videos * comments_per_video))

    mode = "AND" if len(keywords) > 1 else "OR"
    suffix_base = "_".join(re.sub(r"[^0-9A-Za-z가-힣-]+", "", item) for item in keywords[:3])
    run_suffix = f"chatbot_{suffix_base or 'manual_keywords'}"
    return AnalysisPlan(
        keywords=keywords,
        keyword_mode=mode,
        max_videos=max(1, min(analysis_runner.MAX_YOUTUBE_VIDEOS, max_videos)),
        comments_per_video=max(0, min(analysis_runner.MAX_COMMENTS_PER_VIDEO, comments_per_video)),
        limit=max(0, min(10_000, limit)),
        product=product_category,
        brand=brand,
        run_suffix=run_suffix,
        parse_error=parse_error,
    )


def _match_options(text: str, options: Iterable[str], aliases: dict[str, str] | None = None) -> list[str]:
    aliases = aliases or {}
    values = list(options)
    value_by_fold = {value.casefold(): value for value in values}
    matched: list[str] = []
    folded_text = text.casefold()
    for value in values:
        if value and value.casefold() in folded_text:
            matched.append(value)
    for alias, canonical in aliases.items():
        if alias.casefold() in folded_text:
            canonical_value = value_by_fold.get(canonical.casefold(), canonical)
            if canonical_value in values or canonical:
                matched.append(canonical_value)
    return _dedupe(matched)


def parse_filter_request(
    text: str,
    *,
    product_options: Iterable[str],
    brand_options: Iterable[str],
    market_options: Iterable[str],
    cej_options: Iterable[str],
) -> FilterPlan:
    product_aliases = {
        "로청": "로봇청소기",
        "로봇 청소기": "로봇청소기",
        "식세기": "식기세척기",
        "식기 세척기": "식기세척기",
    }
    brand_aliases = {
        "엘지": "LG",
        "lg전자": "LG",
        "중국회사": "중국 브랜드",
        "중국기업": "중국 브랜드",
        "중국브랜드": "중국 브랜드",
        "중국 제품": "중국 브랜드",
        "중국제품": "중국 브랜드",
        "피세아": "피세아",
        "picea": "피세아",
    }
    market_aliases = {"한국": "한국", "국내": "한국", "kr": "한국", "korea": "한국"}
    return FilterPlan(
        products=_match_options(text, product_options, product_aliases),
        brands=_match_options(text, brand_options, brand_aliases),
        markets=_match_options(text, market_options, market_aliases),
        cejs=_match_options(text, cej_options),
    )


def is_quality_review_request(text: str) -> bool:
    normalized = _safe_text(text)
    if not normalized:
        return False
    quality_terms = r"(판정|분류|토픽|topic|entity|엔티티|cej|rootcause|루트코즈|결과|분석|스코어|점수|라벨)"
    review_terms = r"(맞아|맞나요|맞는지|대상|이상|검증|검토|확인|봐줘|봐|오분류|정확|괜찮|정답지|믿을|믿을\s*만|ground\s*truth)"
    if re.search(quality_terms + r".{0,20}" + review_terms, normalized, re.IGNORECASE):
        return True
    if re.search(review_terms + r".{0,20}" + quality_terms, normalized, re.IGNORECASE):
        return True
    return bool(re.search(r"(이\s*판정\s*맞|판정\s*맞|오분류인지|분류\s*맞|결과\s*맞)", normalized, re.IGNORECASE))


def parse_chat_request(
    text: str,
    *,
    product_options: Iterable[str] = (),
    brand_options: Iterable[str] = (),
    market_options: Iterable[str] = (),
    cej_options: Iterable[str] = (),
) -> ChatPlan:
    normalized = _safe_text(text)
    if not normalized:
        return ChatPlan("unknown", "요청 문장이 비어 있습니다.", warnings=["요청을 입력해 주세요."])

    if is_quality_review_request(normalized):
        return ChatPlan(
            "unknown",
            "지원 범위 밖 요청입니다.",
            warnings=[
                "이 챗봇은 판정 검증은 하지 않습니다. 대신 이렇게 요청해보세요: "
                + " / ".join(SUPPORTED_EXAMPLES)
            ],
        )

    looks_like_analysis = bool(re.search(r"(분석|수집|VoC|VOC|유튜브|youtube|영상)", normalized, re.IGNORECASE))
    looks_like_filter = bool(re.search(r"(필터|걸어|보여|브랜드|제품군|국가|시장|CEJ|cej)", normalized, re.IGNORECASE))

    if looks_like_filter and not looks_like_analysis:
        filters = parse_filter_request(
            normalized,
            product_options=product_options,
            brand_options=brand_options,
            market_options=market_options,
            cej_options=cej_options,
        )
        selected_count = len(filters.products) + len(filters.brands) + len(filters.markets) + len(filters.cejs)
        warnings = [] if selected_count else ["대시보드 옵션과 일치하는 필터 값을 찾지 못했습니다."]
        return ChatPlan("filter", f"{selected_count}개 필터 값을 찾았습니다.", filters=filters, warnings=warnings)

    if looks_like_analysis:
        analysis = parse_analysis_request(normalized)
        _brand, _product, errors = _validate_execution_terms(normalized)
        if analysis.parse_error:
            if analysis.parse_error == "OPENAI_API_KEY is not set":
                extraction_error = (
                    "키워드 자동 추출에 필요한 OPENAI_API_KEY가 로컬 실행 환경에 없습니다. "
                    "키를 설정하거나 실행 전 키워드를 직접 입력해 주세요."
                )
            else:
                extraction_error = (
                    "키워드 자동 추출 API 호출에 실패했습니다. 실행 전 키워드를 직접 입력해 주세요. "
                    f"({analysis.parse_error})"
                )
            errors = [*errors, extraction_error]
        return ChatPlan(
            "analysis",
            "YouTube 직접 수집 + 1차 분석 실행 요청으로 해석했습니다. 실행 전 확인이 필요합니다.",
            analysis=analysis,
            errors=errors,
        )

    return ChatPlan(
        "unknown",
        "지원 범위 밖 요청입니다.",
        warnings=[
            "이 챗봇은 유튜브 실행 파라미터 설정과 대시보드 필터 적용만 지원합니다. "
            "이렇게 요청해보세요: " + " / ".join(SUPPORTED_EXAMPLES)
        ],
    )


def _plan_to_dict(plan: ChatPlan) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "intent": plan.intent,
        "summary": plan.summary,
        "warnings": list(plan.warnings),
        "errors": list(plan.errors),
    }
    if plan.analysis:
        payload["analysis"] = plan.analysis.__dict__
    if plan.filters:
        payload["filters"] = plan.filters.__dict__
    return payload


def _plan_from_dict(payload: object) -> ChatPlan | None:
    if not isinstance(payload, dict):
        return None
    analysis_payload = payload.get("analysis")
    filter_payload = payload.get("filters")
    if isinstance(analysis_payload, dict):
        allowed_analysis = AnalysisPlan.__dataclass_fields__.keys()
        analysis = AnalysisPlan(**{key: value for key, value in analysis_payload.items() if key in allowed_analysis})
    else:
        analysis = None
    if isinstance(filter_payload, dict):
        allowed_filters = FilterPlan.__dataclass_fields__.keys()
        filters = FilterPlan(**{key: value for key, value in filter_payload.items() if key in allowed_filters})
    else:
        filters = None
    return ChatPlan(
        intent=_safe_text(payload.get("intent")) or "unknown",
        summary=_safe_text(payload.get("summary")),
        analysis=analysis,
        filters=filters,
        warnings=[_safe_text(item) for item in payload.get("warnings", []) if _safe_text(item)]
        if isinstance(payload.get("warnings"), list)
        else [],
        errors=[_safe_text(item) for item in payload.get("errors", []) if _safe_text(item)]
        if isinstance(payload.get("errors"), list)
        else [],
    )


def _analysis_edit_key(name: str) -> str:
    return f"{CHATBOT_ANALYSIS_EDIT_PREFIX}_{name}"


def _seed_analysis_editor(plan: AnalysisPlan, *, force: bool = False) -> None:
    defaults: dict[str, object] = {
        "keywords": "\n".join(plan.keywords),
        "keyword_mode": plan.keyword_mode,
        "max_videos": int(plan.max_videos),
        "comments_per_video": int(plan.comments_per_video),
        "limit": int(plan.limit),
        "region": plan.region,
        "language": plan.language,
        "include_replies": bool(plan.include_replies),
        "run_suffix": plan.run_suffix,
    }
    for name, value in defaults.items():
        key = _analysis_edit_key(name)
        if force or key not in st.session_state:
            st.session_state[key] = value


def _analysis_plan_with_overrides(plan: AnalysisPlan) -> AnalysisPlan:
    keywords_text = _safe_text(st.session_state.get(_analysis_edit_key("keywords")))
    keywords = _dedupe(line.strip() for line in keywords_text.splitlines())
    if not keywords:
        keywords = list(plan.keywords)

    keyword_mode = _safe_text(st.session_state.get(_analysis_edit_key("keyword_mode"))) or plan.keyword_mode
    keyword_mode = keyword_mode.upper() if keyword_mode.upper() in {"AND", "OR"} else plan.keyword_mode

    return AnalysisPlan(
        keywords=keywords,
        keyword_mode=keyword_mode,
        max_videos=max(
            1,
            min(
                analysis_runner.MAX_YOUTUBE_VIDEOS,
                int(st.session_state.get(_analysis_edit_key("max_videos"), plan.max_videos) or 1),
            ),
        ),
        comments_per_video=max(
            0,
            min(
                analysis_runner.MAX_COMMENTS_PER_VIDEO,
                int(st.session_state.get(_analysis_edit_key("comments_per_video"), plan.comments_per_video)),
            ),
        ),
        limit=max(0, min(10_000, int(st.session_state.get(_analysis_edit_key("limit"), plan.limit) or 0))),
        region=_safe_text(st.session_state.get(_analysis_edit_key("region"))) or plan.region,
        language=_safe_text(st.session_state.get(_analysis_edit_key("language"))) or plan.language,
        include_replies=bool(st.session_state.get(_analysis_edit_key("include_replies"), plan.include_replies)),
        channel_id=plan.channel_id,
        brand=plan.brand,
        run_suffix=_safe_text(st.session_state.get(_analysis_edit_key("run_suffix"))) or plan.run_suffix,
        parse_error=plan.parse_error,
    )


def _run_analysis_from_plan(plan: AnalysisPlan, *, dataset_session_key: str) -> None:
    if not analysis_runner._resolve_openai_api_key():
        st.error("OPENAI_API_KEY가 없어 분석을 시작할 수 없습니다.")
        return
    if not analysis_runner._resolve_youtube_api_key():
        st.error("YOUTUBE_API_KEY가 없어 YouTube 직접 수집을 시작할 수 없습니다.")
        return
    if st.session_state.get(analysis_runner.SESSION_RUN_KEY, {}).get("status") == "running":
        st.warning("이미 실행 중인 분석이 있습니다. 완료 후 다시 시도해 주세요.")
        return

    run_id = f"{analysis_runner._safe_slug(plan.run_suffix)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = analysis_runner.RUN_ROOT / run_id
    command = analysis_runner._build_command(
        source_type="youtube",
        source_path=None,
        out_dir=out_dir,
        run_id=run_id,
        model="",
        limit=int(plan.limit),
        batch_size=5,
        timeout_seconds=120,
        sample_across_videos=True,
        youtube_keyword="\n".join(plan.keywords),
        youtube_keywords=list(plan.keywords),
        youtube_keyword_mode=plan.keyword_mode,
        youtube_region=plan.region,
        youtube_language=plan.language,
        youtube_max_videos=int(plan.max_videos),
        youtube_comments_per_video=int(plan.comments_per_video),
        youtube_include_replies=bool(plan.include_replies),
        youtube_channel_id=plan.channel_id,
    )
    process = analysis_runner._start_subprocess(command, out_dir)
    state = {
        "status": "running",
        "run_id": run_id,
        "out_dir": str(out_dir),
        "source_type": "youtube",
        "source_path": ", ".join(plan.keywords),
        "command": command,
        "pid": process.pid,
        "process": process,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_monotonic": time.time(),
        "started_by": "dashboard60_chatbot",
        "dataset_session_key": dataset_session_key,
    }
    st.session_state[analysis_runner.SESSION_RUN_KEY] = state
    analysis_runner._persist_run_state(state)
    analysis_runner._append_run_log(
        {
            "status": "started",
            "run_id": run_id,
            "out_dir": str(out_dir),
            "source_type": "youtube",
            "source_path": ", ".join(plan.keywords),
            "pid": process.pid,
            "limit": int(plan.limit),
            "batch_size": 5,
            "started_by": "dashboard60_chatbot",
        }
    )
    st.success(f"기존 분석 파이프라인을 백그라운드로 시작했습니다. PID={process.pid}")
    st.rerun()


def _apply_filter_plan(plan: FilterPlan, *, filter_keys: dict[str, str]) -> None:
    st.session_state[filter_keys["products"]] = list(plan.products)
    st.session_state[filter_keys["brands"]] = list(plan.brands)
    st.session_state[filter_keys["markets"]] = list(plan.markets)
    st.session_state[filter_keys["cejs"]] = list(plan.cejs)
    st.success("필터 값을 적용했습니다.")
    st.rerun()


def render_chatbot_assistant(
    *,
    frame: pd.DataFrame,
    product_options: list[str],
    brand_options: list[str],
    market_options: list[str],
    cej_options: list[str],
    filter_keys: dict[str, str],
    dataset_session_key: str,
) -> None:
    """Render the scoped natural-language assistant in the sidebar."""

    del frame  # Channel validation was intentionally removed; loaded rows are not needed here.

    if hasattr(st, "popover"):
        chat_container = st.popover(
            "챗봇 열기",
            icon="💬",
            help="자연어로 YouTube 분석 실행 파라미터를 채우거나 대시보드 필터를 적용합니다.",
            use_container_width=True,
        )
    else:
        chat_container = st.expander("💬 챗봇 실행/필터 도우미 · 프로토타입", expanded=False)

    with chat_container:
        st.markdown("### 💬 챗봇 실행/필터 도우미")
        st.caption(
            "역할은 두 가지뿐입니다: ① 자연어를 분석 실행 파라미터로 바꾸고 확인을 받고 실행, "
            "② 기존 필터 선택값 적용. 판정 검증/QC는 하지 않습니다."
        )
        st.markdown("**이렇게 요청해보세요**")
        example_cols = st.columns(2)
        for index, example in enumerate(SUPPORTED_EXAMPLES):
            with example_cols[index % 2]:
                if st.button(example, key=f"dashboard60_chatbot_example_{index}", width="stretch"):
                    st.session_state[CHATBOT_TEXT_KEY] = example
                    st.session_state.pop(CHATBOT_PLAN_KEY, None)
                    st.rerun()

        text = st.text_area(
            "요청",
            key=CHATBOT_TEXT_KEY,
            placeholder="예: 귀곰 채널 LG가전 영상 5개 VoC 분석해줘\n예: 브랜드는 LG, 제품군은 로봇청소기로 필터 걸어줘",
            height=92,
        )
        if st.button("요청 해석", width="stretch"):
            plan = parse_chat_request(
                text,
                product_options=product_options,
                brand_options=brand_options,
                market_options=market_options,
                cej_options=cej_options,
            )
            st.session_state[CHATBOT_PLAN_KEY] = _plan_to_dict(plan)
            if plan.analysis:
                _seed_analysis_editor(plan.analysis, force=True)
            st.rerun()

        plan = _plan_from_dict(st.session_state.get(CHATBOT_PLAN_KEY))
        if not plan:
            return
        st.markdown(f"**해석 결과:** {plan.summary}")
        for warning in plan.warnings:
            st.warning(warning)
        for error in plan.errors:
            st.error(error)

        if plan.intent == "filter" and plan.filters:
            rows = [
                ("제품군", ", ".join(plan.filters.products) or "-"),
                ("브랜드", ", ".join(plan.filters.brands) or "-"),
                ("국가/시장", ", ".join(plan.filters.markets) or "-"),
                ("CEJ", ", ".join(plan.filters.cejs) or "-"),
            ]
            st.table(pd.DataFrame(rows, columns=["구분", "적용값"]))
            matched = bool(plan.filters.products or plan.filters.brands or plan.filters.markets or plan.filters.cejs)
            if st.button("필터 적용", width="stretch", disabled=not matched):
                _apply_filter_plan(plan.filters, filter_keys=filter_keys)

        elif plan.intent == "analysis" and plan.analysis:
            _seed_analysis_editor(plan.analysis)
            st.markdown("##### 실행 전 파라미터 확인/수정")
            st.caption("챗봇이 제안한 초안입니다. 실행 전에 필요한 값은 여기서 바로 고칠 수 있습니다.")

            st.text_area(
                "키워드 (한 줄에 하나씩 입력)",
                key=_analysis_edit_key("keywords"),
                height=78,
                help="예: 귀곰↵LG가전 처럼 줄을 나누면 키워드 2개로 전달됩니다.",
            )
            edit_cols = st.columns(2)
            with edit_cols[0]:
                st.selectbox("키워드 결합", ["AND", "OR"], key=_analysis_edit_key("keyword_mode"))
                st.number_input(
                    analysis_runner.VIDEO_COUNT_LABEL,
                    min_value=1,
                    max_value=analysis_runner.MAX_YOUTUBE_VIDEOS,
                    step=1,
                    key=_analysis_edit_key("max_videos"),
                )
                st.number_input(
                    analysis_runner.ANALYSIS_LIMIT_LABEL,
                    min_value=0,
                    max_value=analysis_runner.MAX_ANALYSIS_ROWS,
                    step=1,
                    key=_analysis_edit_key("limit"),
                )
                st.text_input(
                    "국가/시장 코드",
                    key=_analysis_edit_key("region"),
                    help=analysis_runner.REGION_HELP_TEXT,
                )
            with edit_cols[1]:
                st.number_input(
                    analysis_runner.COMMENT_COUNT_LABEL + " · 0=가능한 모두",
                    min_value=0,
                    max_value=analysis_runner.MAX_COMMENTS_PER_VIDEO,
                    step=5,
                    key=_analysis_edit_key("comments_per_video"),
                )
                st.text_input(
                    "언어 코드",
                    key=_analysis_edit_key("language"),
                    help=analysis_runner.LANGUAGE_HELP_TEXT,
                )
                st.text_input("run suffix", key=_analysis_edit_key("run_suffix"))
            st.checkbox("답글 포함", key=_analysis_edit_key("include_replies"))

            edited_plan = _analysis_plan_with_overrides(plan.analysis)
            keyword_lines = "\n".join(f"{index}. {keyword}" for index, keyword in enumerate(edited_plan.keywords, start=1))
            st.info(f"키워드 {len(edited_plan.keywords)}개를 {edited_plan.keyword_mode} 조건으로 검색합니다.")
            plan_rows = [
                ("입력 유형", "YouTube 직접 수집"),
                ("키워드", keyword_lines),
                ("키워드 결합", edited_plan.keyword_mode),
                ("영상 수", str(edited_plan.max_videos)),
                ("영상당 댓글 수", str(edited_plan.comments_per_video)),
                ("분석 최대 행 수", str(edited_plan.limit)),
                ("감지된 제품군", edited_plan.product or "-"),
                ("검증된 브랜드", edited_plan.brand or "-"),
                ("국가/언어", f"{edited_plan.region}/{edited_plan.language}"),
                ("답글 포함", "Y" if edited_plan.include_replies else "N"),
                ("run suffix", edited_plan.run_suffix),
            ]
            st.table(pd.DataFrame(plan_rows, columns=["파라미터", "값"]))
            st.warning("이 버튼은 YouTube API와 OpenAI API를 실제 호출합니다. 실행 전 사람이 한 번 확인해야 합니다.")
            blocking_errors = [
                error for error in plan.errors if "키워드 자동 추출에 실패" not in error
            ]
            if plan.errors and not blocking_errors and edited_plan.keywords:
                st.caption("키워드를 수동으로 입력했으므로 실행할 수 있습니다.")
            if st.button(
                "확인 후 분석 실행",
                type="primary",
                width="stretch",
                disabled=bool(blocking_errors) or not bool(edited_plan.keywords),
            ):
                _run_analysis_from_plan(edited_plan, dataset_session_key=dataset_session_key)
