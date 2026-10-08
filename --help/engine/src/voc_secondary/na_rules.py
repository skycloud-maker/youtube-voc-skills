"""Frozen legitimate-N/A rule from the Phase-1 closeout audit.

This is a direct code extraction of ``rc316_na_baseline_20260813.py``.  The
wording and thresholds are intentionally unchanged because that rule matched
the 30-row human adjudication set exactly.
"""

from __future__ import annotations

import re


CREATOR_CONTEXT = re.compile(r"(?:영상|리뷰|후기|콘텐츠|채널|댓글|효과음|편집|워딩|귀곰|곰님)", re.I)
REQUEST_OR_FEEDBACK = re.compile(
    r"(?:부탁|해\s*주세요|해주세요|해주시면|해주라|한번\s*해|기다리|기대|빼\s*주세요|"
    r"올려|링크|업데이트|잘\s*봤|재밌|감사|좋은\s*리뷰|천재적|현기증)", re.I
)
PRODUCT_SIGNAL = re.compile(
    r"(?:가격|비싸|싸다|성능|고장|불량|소음|냄새|세척|살균|설치|타공|플라스틱|"
    r"필터|거름망|기능|모델|구매|사고\s*싶|불편|물고임|축축|자외선|식초|배터리|"
    r"흡입|물걸레|문턱|주행)", re.I
)
THANKS_REACTION = re.compile(r"(?:감사|잘\s*봤|재밌|좋은\s*리뷰|워딩|천재적|깜짝\s*놀라)", re.I)
SHORT_REACTION = re.compile(r"(?:안녕하세요|반갑|좋아요|좋네요|멋지|최고|대박|화이팅|응원|굿|짱|ㅋㅋ|ㅎㅎ)", re.I)
OWNERSHIP_WORD = re.compile(r"(?:샀|구매|쓰고|사용|보유|간택)", re.I)
OWNERSHIP = re.compile(r"(?:구형|예전|기존)?\s*(?:제품\s*)?(?:쓰고\s*있|사용\s*중|보유\s*중|샀(?:어요|습니다)?)", re.I)
SPELLING = re.compile(r"(?:맞춤법|오타|설거지(?:에요|예요)?\s*설겆이가\s*아니라)", re.I)
CONTENT_MEME_REACTION = re.compile(
    r"(?:쾌유|쾌차|완쾌|힘내|기도|투병|암환우|건강.{0,8}(?:회복|기원)|"
    r"교수님|명강의|강의|장인|박사님|구독|유튜버|워딩|빵터|재밌|"
    r"잘\s*봤|잘보고|처음\s*알|알았음|국룰|외국인|한국인|노래|음악|"
    r"소절|어깨춤|자판기|벌컥|왜\s*기다|끝까지\s*(?:듣|기다)|"
    r"리뷰는\s*귀곰|귀곰님.*(?:유명|광고)|눈밑지방|닮으셨)",
    re.I,
)
CONTENT_MEME_SUBSTANTIVE = re.compile(
    r"(?:가격|구매|구입|사야|사고|안사|모델|설치|타공|기능|고장|불량|"
    r"세척|살균|세제|알칼리|중성|식초|필터|거름망|컨덴서|냄새|소음|"
    r"플라스틱|위생|잠금|문이\s*열|자동\s*열|안전|인식|신호|사용|"
    r"쓰고|제품|사이트|쿠팡|수납|성능|물\s*넣|정수기|수돗물|자외선|"
    r"얼음|섬유유연제|멈추지|끝났|열리|이유|알리|자판기|뭔\s*소리|"
    r"없는데|쓸데없)",
    re.I,
)
OTHER_VIEWER_REQUEST = re.compile(
    r"(?:사신|쓰시는|사용하시는).{0,18}(?:분들|분).{0,20}(?:후기|답변|알려)|"
    r"답변\s*받으셨나요",
    re.I,
)
NEWS_INDUSTRY_REACTION = re.compile(
    r"(?:드디어\s*자체\s*기술|연구원.{0,8}고생|한국\s*기업.{0,8}흥|"
    r"북미.{0,15}(?:팔|수요)|혁명|마지막\s*제품)",
    re.I,
)


def compact(value: str) -> str:
    value = re.sub(r"@[\w가-힣-]+", " ", str(value))
    value = re.sub(r"[^0-9A-Za-z가-힣]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def legitimate_na_rule(text: str) -> tuple[bool, str]:
    raw = str(text).strip()
    body = compact(raw)
    if not body:
        return True, "empty_or_symbol_reaction"
    if SPELLING.search(raw) or (len(body) <= 18 and re.fullmatch(r"설거지|설겆이", body)):
        return True, "spelling_correction"
    if CREATOR_CONTEXT.search(raw) and REQUEST_OR_FEEDBACK.search(raw) and not PRODUCT_SIGNAL.search(raw):
        return True, "channel_video_request_or_feedback"
    if re.search(r"(?:다음|나중에).{0,30}(?:도\s*)?(?:한번\s*)?해\s*주세요", raw, re.I) and not PRODUCT_SIGNAL.search(raw):
        return True, "channel_video_request_or_feedback"
    if len(body) <= 70 and THANKS_REACTION.search(raw) and not PRODUCT_SIGNAL.search(raw):
        return True, "short_thanks_praise_reaction"
    if len(body) <= 30 and SHORT_REACTION.search(raw) and not PRODUCT_SIGNAL.search(raw) and not OWNERSHIP_WORD.search(raw) and "?" not in raw:
        return True, "short_thanks_praise_reaction"
    if len(body) <= 28 and OWNERSHIP.search(raw) and not PRODUCT_SIGNAL.search(raw) and "?" not in raw:
        return True, "simple_ownership_fact"
    if OTHER_VIEWER_REQUEST.search(raw) and not PRODUCT_SIGNAL.search(raw):
        return True, "other_viewer_request"
    if NEWS_INDUSTRY_REACTION.search(raw) and not PRODUCT_SIGNAL.search(raw):
        return True, "news_industry_reaction"
    if CONTENT_MEME_REACTION.search(raw) and not CONTENT_MEME_SUBSTANTIVE.search(raw):
        return True, "content_meme_reaction"
    return False, "not_legitimate_na_by_rule"
