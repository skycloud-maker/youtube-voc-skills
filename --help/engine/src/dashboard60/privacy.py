"""화면에 그릴 때만 사람으로 이어지는 값을 가린다.

★ 왜 있는가 (sky 2026-08-20)
  대시보드는 실무자 전원이 본다. 판정을 확인하려면 댓글 원문은 보여야 하지만,
  원문에 섞여 있는 YouTube 사용자명(@호출명)은 분석에 쓰는 값이 아니면서
  계정을 바로 가리킨다. 실측: 파일럿 1,698행 중 original_voc 77행, atomic_voc 14행.
  영상 설명(video_description)에는 채널 업무 이메일과 링크가 761·977행 들어 있다.

★ 원칙 — 누가 말했는지는 지우고, 무슨 말인지는 남긴다.
  원문 자체는 그대로 둔다. 없으면 판정을 확인할 수 없다.

★ 어디에만 거는가 — 「화면」 에만 건다.
  원본 CSV·산출물 엑셀은 건드리지 않는다. 사내 보관본은 원본이어야 하고,
  export_bundle 은 디스크에서 읽은 프레임을 쓰므로 이 함수를 타지 않는다.
  2차 판독이 낸 「구조적결함」 에도 멘션 조각 문제가 이미 잡혀 있다 —
  엔진이 고쳐지면 이 가림막은 걷어도 된다.
"""

from __future__ import annotations

import re

import pandas as pd

# YouTube 호출명: @ 뒤에 한글/영문/숫자/밑줄/점/붙임표가 이어진다
MENTION_PATTERN = re.compile(r"@[\w가-힣][\w가-힣._-]*")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
LINK_PATTERN = re.compile(r"https?://\S+|(?<![\w.])www\.\S+", re.IGNORECASE)

MENTION_MASK = "@***"
EMAIL_MASK = "[메일 가림]"
LINK_MASK = "[링크 가림]"

# 사람이 읽는 글이 담기는 칸. 여기만 훑는다 —
# 집계·점수 칸까지 훑으면 느려지기만 하고 얻는 게 없다
TEXT_COLUMNS = (
    "original_voc",
    "atomic_voc",
    "atomic_voc_summary",
    "voc_cleaned",
    "voc_residual",
    "video_description",
    "rootcause_summary",
    "rootcause_problem",
    "rootcause_target",
    "rootcause_cause",
    "topic_evidence",
    "evidence_quote",
)


def mask_identifiers(value: object) -> object:
    """글 한 덩이에서 사람으로 이어지는 값을 가린다.

    문자열이 아니면 그대로 돌려준다.
    ★ 이메일을 먼저 가린다. 이메일에도 @ 가 있어 멘션 규칙이 먼저 돌면
      주소 앞부분만 남아 더 이상해진다.
    """

    if not isinstance(value, str) or not value:
        return value
    text = EMAIL_PATTERN.sub(EMAIL_MASK, value)
    text = LINK_PATTERN.sub(LINK_MASK, text)
    return MENTION_PATTERN.sub(MENTION_MASK, text)


def mask_frame_for_display(frame: pd.DataFrame) -> pd.DataFrame:
    """화면에 그릴 사본을 만든다. 원본은 건드리지 않는다.

    ★ dtype 으로 칸을 고르지 않는다. pandas 판에 따라 문자열이 object 가 아니라
      str 로 오는데, object 로 걸렀더니 훑기가 통째로 건너뛰어져
      「가렸다고 믿었지만 하나도 안 가려진」 파일이 나온 적이 있다.
      칸 이름으로 고르고, 값이 문자열이 아니면 mask_identifiers 가 알아서 넘긴다.
    """

    if frame is None or frame.empty:
        return frame
    targets = [column for column in TEXT_COLUMNS if column in frame.columns]
    if not targets:
        return frame
    masked = frame.copy()
    for column in targets:
        masked[column] = masked[column].map(mask_identifiers)
    return masked
