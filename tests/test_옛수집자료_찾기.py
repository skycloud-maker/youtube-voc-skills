# -*- coding: utf-8 -*-
"""옛 저장소에 2판 수집 자료가 남아 있나 재는 도구 (`tools/옛수집자료_찾기.py`).

★ 왜 이 시험이 있나 (2026-11-02) — sky 기준 표의 마지막 빈 칸이 「② 1차 분석 재현」 이고,
  내 권고가 「옛 저장소에서 2판의 수집 결과를 **찾아보는 것**」 이었다. 찾은 결과는
  **없다**(881/6,240 · 14.1%)였는데, 그 답은 **도구가 제대로 찾았을 때만** 뜻이 있다.

  그래서 두 가지를 지킨다 —
    ① 「못 찾음」 을 「없음」 으로 돌려주지 않는다 (입력이 없으면 **멈춘다**)
    ② 수집 꼴을 **판정된 자료와 가른다** (`topic` 이 있으면 수집 자리가 아니다)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
도구쪽 = REPO / "tools" / "옛수집자료_찾기.py"


def _불러오기(argv: list[str]):
    """argv 를 바꿔 끼우고 모듈을 새로 불러온다 (모듈이 읽는 때에 argv 를 본다)."""
    옛argv = sys.argv
    sys.argv = ["옛수집자료_찾기.py"] + argv
    try:
        spec = importlib.util.spec_from_file_location("옛수집찾기_시험", 도구쪽)
        m = importlib.util.module_from_spec(spec)
        sys.modules["옛수집찾기_시험"] = m
        spec.loader.exec_module(m)
        return m
    finally:
        sys.argv = 옛argv


def test_입력을_안_주면_멈춘다(monkeypatch):
    """★ 알맹이 — 「못 찾음」 은 통과가 아니다. 댈 것이 없으면 **답을 내지 않는다.**"""
    monkeypatch.delenv("VOC_1차입력", raising=False)
    m = _불러오기([])
    with pytest.raises(SystemExit) as e:
        m.우리댓글번호()
    assert "댈 것이 없으면" in str(e.value), str(e.value)


def test_없는_파일을_주면_멈춘다(tmp_path, monkeypatch):
    monkeypatch.delenv("VOC_1차입력", raising=False)
    m = _불러오기([str(tmp_path / "없는것.csv")])
    with pytest.raises(SystemExit) as e:
        m.우리댓글번호()
    assert "못 찾음" in str(e.value), str(e.value)


def test_열쇠_칸이_없으면_멈춘다(tmp_path, monkeypatch):
    """`source_id` 가 없으면 **맞출 열쇠가 없다** — 0% 라고 답하면 거짓이다."""
    monkeypatch.delenv("VOC_1차입력", raising=False)
    쪽 = tmp_path / "엉뚱.csv"
    쪽.write_text("a,b\n1,2\n", encoding="utf-8")
    m = _불러오기([str(쪽)])
    with pytest.raises(SystemExit) as e:
        m.우리댓글번호()
    assert "열쇠" in str(e.value), str(e.value)


def test_댓글과_영상을_읽는다(tmp_path, monkeypatch):
    monkeypatch.delenv("VOC_1차입력", raising=False)
    쪽 = tmp_path / "1차.csv"
    쪽.write_text("source_id,video_id\nc1,v1\nc2,v1\nc3,v2\nc3,v2\n", encoding="utf-8")
    m = _불러오기([str(쪽)])
    댓글, 영상 = m.우리댓글번호()
    assert 댓글 == {"c1", "c2", "c3"} and 영상 == {"v1", "v2"}


def test_판정된_자료를_수집_자리로_세지_않는다(monkeypatch):
    """★ 이것을 못 가르면 「수집 자료가 있다」 는 **거짓 답**이 나온다 —
    2차·3차 결과 파일에도 `comment_id` 와 원문이 다 들어 있다."""
    monkeypatch.delenv("VOC_1차입력", raising=False)
    m = _불러오기(["x.csv"])
    assert m.수집꼴인가(["comment_id", "text_original", "published_at"]) is True
    assert m.수집꼴인가(["comment_id", "text_display", "like_count"]) is True
    # 판정 칸이 있으면 수집 자리가 아니다
    assert m.수집꼴인가(["comment_id", "text_original", "topic"]) is False
    # 원문이 없으면 수집 자리가 아니다
    assert m.수집꼴인가(["comment_id", "like_count"]) is False
    # 댓글 번호가 없으면 맞출 수 없다
    assert m.수집꼴인가(["text_original", "published_at"]) is False


def test_옛_저장소_경로를_박지_않는다(monkeypatch):
    """경로는 `paths.py` 한 자리에서만 온다 (공통 규칙 6). 뿌리는 거기서 끌어낸다."""
    monkeypatch.delenv("VOC_1차입력", raising=False)
    글 = 도구쪽.read_text(encoding="utf-8")
    assert "from paths import 옛저장소" in 글, "paths.py 에서 가져오지 않는다"
    m = _불러오기(["x.csv"])
    뿌리 = m.옛뿌리들()
    # 적어도 본체 하나는 나온다 (이 컴퓨터에 옛 저장소가 있을 때)
    assert isinstance(뿌리, list)
