"""사외 공유용 산출물 — 받을 때 그 자리에서 만든다.

★ 왜 있는가 (sky 2026-08-20)
  「개인정보가 제외된 별도 파일 다운로드 버튼을 만드는것도 좋은 방법 같습니다.
   매번 고민하지 않아도 되도록요.」

★ 왜 「그 자리에서」 만드나
  분석이 끝날 때 미리 만들어 두면 파일이 두 배로 쌓이고, 안 쓰는 것도 만들어진다.
  게다가 규칙이 바뀌면 예전에 만들어 둔 것이 옛 규칙으로 남는다.
  누를 때 만들면 언제나 지금 규칙으로 나온다.

★ 원본은 손대지 않는다
  사내 보관본에는 원문·식별자가 그대로 있어야 한다. 내부 분석·재현에 필요하다.
  이 모듈은 읽기만 하고, 새 파일을 메모리에 만들어 돌려준다.

★ 만들고 나서 다시 검사한다
  검사를 통과하지 못하면 **파일을 내주지 않는다.**
  같은 성격의 코드가 조용히 아무것도 안 가린 채 정상 종료한 적이 있다
  (dtype 조건이 라이브러리 판 차이로 항상 거짓이 되었다). 오류는 나지 않았다.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd

# 특정 영상·댓글로 이어지는 열쇠 — 칸째 뺀다
LOCATOR_COLUMNS = frozenset(
    {
        "video_url",
        "video_id",
        "source_id",
        "atomic_id",
        "parent_voc_id",
        "origin_atomic_id",
        "split_origin_atomic_id",
        "raw_row_index",
    }
)

# 원문 전량 시트 — 반출에 필요하지 않고 위험은 가장 크다
EXCLUDED_SHEETS = frozenset({"raw_voc", "inquiry_rows"})

MENTION_PATTERN = re.compile(r"@[\w가-힣][\w가-힣._-]*")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
LINK_PATTERN = re.compile(r"https?://\S+|(?<![\w.])www\.\S+", re.IGNORECASE)

RELEASE_SUFFIX = "_사외공유용"


class ReleaseCheckFailed(RuntimeError):
    """검사를 통과하지 못했다. 파일을 내주면 안 된다."""


def _scrub(value: object, counts: dict[str, int]) -> object:
    """글 한 덩이에서 사람으로 이어지는 값을 가린다.

    ★ 이메일을 먼저 가린다. 이메일에도 @ 가 있어 사용자명 규칙이 먼저 돌면
      주소 앞부분만 남아 더 이상해진다.
    """

    if not isinstance(value, str) or not value:
        return value
    text, n = EMAIL_PATTERN.subn("[메일 지움]", value)
    counts["메일"] += n
    text, n = LINK_PATTERN.subn("[링크 지움]", text)
    counts["링크"] += n
    text, n = MENTION_PATTERN.subn("@***", text)
    counts["사용자명"] += n
    return text


def _mask_frame(frame: pd.DataFrame, counts: dict[str, int]) -> pd.DataFrame:
    """칸을 빼고 글을 가린 사본을 만든다. 원본은 그대로 둔다.

    ★ dtype 으로 칸을 고르지 않는다. pandas 판에 따라 문자열이 object 가 아니라
      str 로 오는데, object 로 걸렀더니 훑기가 통째로 건너뛰어져
      「가렸다고 믿었지만 하나도 안 가려진」 파일이 나온 적이 있다.
    """

    masked = frame.drop(columns=[c for c in frame.columns if c in LOCATOR_COLUMNS])
    for column in masked.columns:
        masked[column] = masked[column].map(lambda value: _scrub(value, counts))
    return masked


def _find_leftovers(book: dict[str, pd.DataFrame]) -> list[str]:
    """만든 결과를 다시 훑는다. 만들 때 쓴 변수가 아니라 결과를 본다."""

    danger = {
        "링크": LINK_PATTERN,
        "이메일": EMAIL_PATTERN,
        "남은 사용자명": re.compile(r"@(?!\*\*\*)[\w가-힣]"),
    }
    problems: list[str] = []
    for sheet_name, frame in book.items():
        left = [c for c in frame.columns if c in LOCATOR_COLUMNS]
        if left:
            problems.append(f"{sheet_name}: 식별자 칸이 남았다 — {', '.join(left)}")
        for column in frame.columns:
            text = frame[column].astype(str)
            for label, pattern in danger.items():
                hits = int(text.str.contains(pattern, na=False).sum())
                if hits:
                    problems.append(f"{sheet_name}.{column}: {label} {hits}건")
    return problems


def build_release_workbook(source: Path) -> tuple[bytes, dict[str, int]]:
    """사내 보관본 엑셀을 읽어 사외 공유용 엑셀 바이트를 만든다.

    돌려주는 것: (엑셀 바이트, 처리 건수)
    검사를 통과하지 못하면 ReleaseCheckFailed 를 낸다 — 파일을 내주지 않는다.
    """

    book = pd.read_excel(source, sheet_name=None)
    counts = {"메일": 0, "링크": 0, "사용자명": 0}

    released: dict[str, pd.DataFrame] = {}
    # ★ 가리기 「전」 의 글을 따로 들고 있는다. 아래에서 「정말 가릴 것이 있었나」 를
    #   볼 때 쓴다. 칸을 빼서 없어진 것은 여기 안 들어온다 — 그게 요점이다
    survived_text: list[str] = []
    for sheet_name, frame in book.items():
        if sheet_name in EXCLUDED_SHEETS:
            continue
        if frame.empty:
            continue
        kept = frame.drop(columns=[c for c in frame.columns if c in LOCATOR_COLUMNS])
        survived_text.append(kept.astype(str).to_string())
        released[sheet_name] = _mask_frame(frame, counts)

    if not released:
        raise ReleaseCheckFailed("내보낼 시트가 없습니다.")

    guide = pd.DataFrame(
        [
            ["이 파일은?", "사외 공유용입니다. 개인정보 처리를 마쳤습니다."],
            ["", ""],
            ["뺀 것", "특정 영상·댓글로 이어지는 식별자(영상 링크·영상 ID·행 식별자)를 "
                     "칸째 제거했습니다. 원문 전량 시트(raw_voc, inquiry_rows)도 뺐습니다."],
            ["가린 것", f"본문 속 YouTube 사용자명 {counts['사용자명']:,}건 · "
                        f"이메일 {counts['메일']:,}건 · 링크 {counts['링크']:,}건"],
            ["남긴 것", "판단 근거로 필요한 인용문은 남겼습니다. "
                        "누가 말했는지는 지우고, 무슨 말인지는 남기는 방식입니다."],
            ["", ""],
            ["확인", "만든 뒤 다시 훑어 링크·이메일·사용자명 잔존 0건을 확인했습니다. "
                     "확인을 통과하지 못하면 이 파일은 만들어지지 않습니다."],
            ["", ""],
            ["★ 무엇이 들어 있지 않나", "이 파일에는 2차 판독 결과가 들어 있지 않습니다. "
                                        "수정로그(2차가 바로잡은 것)·분리제안·구조적결함·기준서개정후보는 "
                                        "2차 판독을 돌려야 나오며, 대시보드가 만드는 산출물이 아닙니다. "
                                        "여기 담긴 것은 분석 결과(개선 우선순위·판단 근거·영상별 요약)입니다."],
            ["", ""],
            ["원본이 필요하면", "대시보드의 「분석 결과 전체 (Excel)」 을 받으십시오. "
                                "사내 보관·재현용이며 원문과 식별자가 그대로 있습니다."],
        ],
        columns=["항목", "설명"],
    )

    problems = _find_leftovers(released)
    # ★ 가린 것이 0건이면 의심한다 — 훑기가 통째로 건너뛰어진 신호일 수 있다.
    #   ★ 다만 「남는 글」 만 본다. 칸을 빼서 없어진 것(video_url 의 링크 같은)은
    #     가릴 필요가 없었던 것이지 못 가린 것이 아니다.
    #     처음에 원본 전체를 보고 판정했다가 멀쩡한 파일이 실패로 막혔다.
    #     검사기가 틀리면 일이 멈춘다 — 오탐도 사고다.
    if sum(counts.values()) == 0:
        survived = "".join(survived_text)
        if (
            MENTION_PATTERN.search(survived)
            or EMAIL_PATTERN.search(survived)
            or LINK_PATTERN.search(survived)
        ):
            problems.append(
                "남는 글에 가릴 것이 있는데 한 건도 가려지지 않았다 — 훑기가 건너뛰어졌다"
            )

    if problems:
        raise ReleaseCheckFailed("\n".join(problems))

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        guide.to_excel(writer, sheet_name="0_읽는_순서", index=False)
        for sheet_name, frame in released.items():
            frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return buffer.getvalue(), counts


def release_filename(source: Path) -> str:
    return f"{source.stem}{RELEASE_SUFFIX}{source.suffix}"
