from __future__ import annotations

from dataclasses import dataclass


LOG_ONLY = "LOG_ONLY"
KEEP = "KEEP"
KEEP_LIMIT = "KEEP + LIMIT"
REMAP = "REMAP"
BLOCK = "BLOCK"


@dataclass(frozen=True)
class ClassificationResult:
    state: str
    representative: bool
    five_w_one_h: bool
    decision_path: tuple[str, ...] = ()


USAGE_MARKERS = (
    # Korean runtime markers
    "사용",
    "사용해",
    "사용할수록",
    "쓰다",
    "써보",
    "매번",
    "항상",
    "자주",
    "다시",
    "돌아가",
    "열어두",
    "닦",
    "세척",
    "건조",
    "청소",
    "필터",
    "거름망",
    "애벌",
    "설거지",
    "소독",
    "남은시간",
    "물튀",
    "물고임",
    "전기료",
    # Mojibake compatibility markers (existing harness data)
    "?ъ슜",
    "?ъ슜?대낫",
    "?ъ슜?섎㈃",
    "留ㅻ쾲",
    "??긽",
    "?먯＜",
    "?ㅼ떆",
    "?뚯븘",
    "嫄댁“",
    "?꾪꽣",
    "臾쇨퀬??",
    "?꾩깉",
    "由곗뒪",
    "?⑥??쒓컙",
    "?먯꽕嫄곗?",
    "泥?냼",
)

REPEAT_OR_BEHAVIOR_MARKERS = (
    "매번",
    "항상",
    "자주",
    "계속",
    "다시",
    "결국",
    "회피",
    "돌아가",
    "미루",
    "주기",
    "해야",
    "매일",
    "留ㅻ쾲",
    "??긽",
    "?먯＜",
    "怨꾩냽",
    "?ㅼ떆",
    "寃곌뎅",
    "?뚯븘",
    "誘몃（",
)

NON_PRODUCT_TARGET_MARKERS = (
    "영상",
    "음악",
    "편집",
    "설명",
    "리뷰",
    "감사",
    "좋은 영상",
    "구매했",
    "구매완료",
    "도움",
    "기대",
    "나오면 좋",
    "나왔으면 좋",
    "출시되면",
    # Mojibake compatibility
    "?곸긽",
    "?뚯븙",
    "?몄쭛",
    "?ㅻ챸",
    "由щ럭",
    "媛먯궗",
    "援щℓ?덉뒿",
    "諛섎젮?앸Ъ ?ㅽ듃???섏삤硫?醫뗪쿋?댁슂.",
    "醫뗪쿋",
)

ISSUE_AXIS_MARKERS = (
    "가격",
    "비싸",
    "조건",
    "키트",
    "건조",
    "소음",
    "냄새",
    "필터",
    "거름망",
    "물고임",
    "전기료",
    "고장",
    "누수",
    "귀찮",
    "불편",
    "린스",
    "성능",
    "남은시간",
    "물튀",
    "세척",
    "소독",
    "鍮꾩떥",
    "媛寃?",
    "嫄댁“",
    "?뚯쓬",
    "?꾩깉",
    "?꾪꽣",
    "嫄곕쫫留?",
    "臾쇨퀬??",
    "?꾧린??",
    "怨좎옣",
    "?꾩닔",
    "洹李?",
    "遺덊렪",
    "由곗뒪",
    "?깅뒫",
    "?⑥??쒓컙",
    "臾쇳?",
)

RESOLVED_KEEP_HINT_MARKERS = (
    "감안",
    "해결",
    "적응",
    "괜찮",
    "문제없",
    "만족",
    "媛먯븞",
    "?닿껐",
    "?곸쓳",
    "愿쒖갖",
    "留뚯”",
)

MIXED_KEEP_MARKERS = (
    "괜찮",
    "좋",
    "편하",
    "별 불편",
    "없는",
    "愿쒖갖",
    "醫?",
    "?명븯",
    "?꾩돺",
    "?녿뒗??",
)

EXPERIENCE_TONE_MARKERS = (
    "불편",
    "귀찮",
    "괜찮",
    "좋",
    "비싸",
    "비쌈",
    "있",
    "遺덊렪",
    "洹李?",
    "愿쒖갖",
    "醫?",
    "鍮꾩떥",
    "鍮꾩떬",
)

REMAP_BRAND_MARKERS = (
    "브랜드",
    "마이디어",
    "midea",
    "haier",
    "hisense",
    "xiaomi",
    "중국",
    "중소기업",
    "대기업",
    "이미지",
    "인식",
    "釉뚮옖??",
    "留덉씠?붿뼱",
    "以묎뎅",
    "以묒냼湲곗뾽",
    "?湲곗뾽",
    "?대?吏",
    "?몄떇",
)

REMAP_PERCEPTION_MARKERS = (
    "같",
    "보이",
    "느낌",
    "우려",
    "인식",
    "애매",
    "선호",
    "媛숈븘",
    "蹂댁씠",
    "?먮굦",
    "?곕젮",
    "?좊ℓ",
)

REMAP_TARGET_FIT_MARKERS = (
    "맞는 제품",
    "맞는",
    "아님",
    "아닌",
    "누구",
    "용도",
    "사치품",
    "留욌뒗",
    "?ㅻ땲",
    "?源?",
    "?⑸룄",
    "?ъ튂??",
)

REMAP_PRODUCT_HINT_MARKERS = (
    "제품",
    "식기세척기",
    "가전",
    "기기",
    "?쒗뭹",
    "?앷린?몄쿃湲?",
    "媛??",
    "湲곌린",
)

BLOCK_MARKERS = (
    "http://",
    "https://",
    "bit.ly/",
)

REPRESENTATIVE_REPEAT_MARKERS = (
    "매번",
    "항상",
    "계속",
    "결국",
    "다시",
    "돌아가",
    "留ㅻ쾲",
    "??긽",
    "怨꾩냽",
    "寃곌뎅",
    "?ㅼ떆",
    "?뚯븘",
)

REPRESENTATIVE_SEVERE_ISSUE_MARKERS = (
    "가격",
    "비싸",
    "건조",
    "물고임",
    "누수",
    "고장",
    "거름망",
    "전기료",
    "소음",
    "냄새",
    "필터",
    "청소",
    "세척",
    "귀찮",
    "불편",
    "鍮꾩떥",
    "媛寃?",
    "嫄댁“",
    "臾쇨퀬??",
    "?꾩닔",
    "怨좎옣",
    "嫄곕쫫留?",
    "?꾧린??",
    "?뚯쓬",
    "?꾩깉",
    "?꾪꽣",
    "洹李?",
    "遺덊렪",
)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker and marker in text for marker in markers)


def _should_remap(text: str, has_usage: bool) -> bool:
    has_target_fit = _contains_any(text, REMAP_TARGET_FIT_MARKERS)
    has_product_hint = _contains_any(text, REMAP_PRODUCT_HINT_MARKERS)
    if has_target_fit and (has_product_hint or has_usage):
        return True

    # Brand-perception remap should not fire for generic market/forecast comments.
    has_brand = _contains_any(text, REMAP_BRAND_MARKERS)
    has_perception = _contains_any(text, REMAP_PERCEPTION_MARKERS)
    return has_usage and has_brand and has_perception


def _allow_representative_in_keep(text: str) -> bool:
    has_repeat = _contains_any(text, REPRESENTATIVE_REPEAT_MARKERS)
    has_severe_issue = _contains_any(text, REPRESENTATIVE_SEVERE_ISSUE_MARKERS)
    return has_repeat and has_severe_issue


def _decide_state(text: str) -> tuple[str, tuple[str, ...]]:
    path: list[str] = []

    if not text:
        path.append("PRECHECK_EMPTY->BLOCK")
        return BLOCK, tuple(path)

    if _contains_any(text, BLOCK_MARKERS):
        path.append("PRECHECK_BLOCK_MARKER->BLOCK")
        return BLOCK, tuple(path)

    has_issue_axis = _contains_any(text, ISSUE_AXIS_MARKERS)
    usage_explicit = _contains_any(text, USAGE_MARKERS)
    usage_inferred = False
    if (not usage_explicit) and has_issue_axis and _contains_any(text, EXPERIENCE_TONE_MARKERS):
        usage_inferred = True

    q1_usage = usage_explicit or usage_inferred
    if not q1_usage:
        path.append("Q1_FAIL_NO_USAGE->LOG_ONLY")
        return LOG_ONLY, tuple(path)

    if usage_inferred:
        path.append("Q1_PASS_USAGE_INFERRED")
    else:
        path.append("Q1_PASS_USAGE")

    q2_repeat = _contains_any(text, REPEAT_OR_BEHAVIOR_MARKERS)
    if q2_repeat:
        path.append("Q2_PASS_REPEAT_OR_BEHAVIOR")
    else:
        path.append("Q2_FAIL_NO_REPEAT_OR_BEHAVIOR")

    if _should_remap(text, has_usage=q1_usage):
        path.append("REMAP_PRECHECK_PASS->REMAP")
        return REMAP, tuple(path)
    path.append("REMAP_GATE_SKIP")

    if _contains_any(text, NON_PRODUCT_TARGET_MARKERS):
        path.append("Q3_FAIL_NON_PRODUCT_TARGET->LOG_ONLY")
        return LOG_ONLY, tuple(path)
    path.append("Q3_PASS_PRODUCT_TARGET")

    if not has_issue_axis:
        path.append("Q4_FAIL_NO_ISSUE_AXIS->KEEP_LIMIT")
        return KEEP_LIMIT, tuple(path)
    path.append("Q4_PASS_ISSUE_AXIS")

    has_resolved_hint = _contains_any(text, RESOLVED_KEEP_HINT_MARKERS)
    has_mixed_hint = _contains_any(text, MIXED_KEEP_MARKERS)
    if q2_repeat:
        path.append("KEEP_DECISION->KEEP")
        return KEEP, tuple(path)
    if usage_explicit and (has_resolved_hint or has_mixed_hint):
        path.append("KEEP_DECISION_RESOLVED_OR_MIXED->KEEP")
        return KEEP, tuple(path)

    path.append("KEEP_DECISION_WEAK->KEEP_LIMIT")
    return KEEP_LIMIT, tuple(path)


def _decide_promotion(text: str, state: str) -> tuple[bool, bool]:
    if state == KEEP:
        return _allow_representative_in_keep(text), False
    return False, False


def classify_comment(raw_comment: str) -> ClassificationResult:
    text = (raw_comment or "").strip().lower()
    state, path = _decide_state(text)
    representative, five_w_one_h = _decide_promotion(text, state)
    return ClassificationResult(
        state=state,
        representative=representative,
        five_w_one_h=five_w_one_h,
        decision_path=path,
    )
