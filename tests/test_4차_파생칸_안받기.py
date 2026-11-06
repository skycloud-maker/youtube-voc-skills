# -*- coding: utf-8 -*-
"""4차에서 **받지 않는 칸**을 승인하면 아무것도 옮기기 전에 멈추는가 (2026-11-06).

★ 왜 이 시험이 있나 — 판 2.1 에서 여러 칸을 섞은 4차 시험(31칸)을 돌렸다.
  사람이 `sentiment_dir` 6칸을 승인했고 총괄이 csv 에 그대로 넣었다. 그런데 최종 엑셀에서
  **5칸이 도로 뒤집혔다** — 엔진 `data_contract.py` 가 엑셀을 만들 때 이 칸을
  `tee_emotion_score` 에서 다시 셈해 덮어쓴다. 승인이 **조용히 사라졌다.**
  sky 결정 「4차에서 안 받기」 — 그런 칸을 승인하면 멈추고 알린다.

★ 칸 목록은 엔진 `DERIVED_COLUMNS_DEFAULTS` 한 곳에서 읽는다. 이 시험도 엔진에서 직접 읽어
  돌리개가 읽은 것과 **같은지** 본다 (두 벌이 되면 엔진이 칸을 늘리는 날 검사가 눈먼다).
"""
from __future__ import annotations

import csv
import importlib
import io
import json
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
sys.path.insert(0, str(REPO / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"))

_머리 = ["source_id", "atomic_id", "atomic_voc", "field", "원본값", "제안값", "사유",
        "근거인용", "오류유형", "승인상태"]


@pytest.fixture()
def 돌리개():
    m = importlib.import_module("한줄_돌리기")
    return importlib.reload(m)


def _엔진_파생칸() -> set:
    sys.path.insert(0, str(REPO / "plugin" / "engine"))
    from src.dashboard60.data_contract import DERIVED_COLUMNS_DEFAULTS  # noqa: PLC0415
    return set(DERIVED_COLUMNS_DEFAULTS)


def _판단표(쪽: Path, 줄들: list[tuple[str, str, str]]) -> None:
    """(field, 제안값, 승인상태) 들로 수정로그_재검토필요.csv 를 쓴다."""
    쪽.mkdir(parents=True, exist_ok=True)
    with io.open(쪽 / "수정로그_재검토필요.csv", "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=_머리)
        w.writeheader()
        for i, (칸, 값, 상) in enumerate(줄들):
            w.writerow({"source_id": "S%02d" % i, "atomic_id": "S%02d-01" % i, "atomic_voc": "글",
                        "field": 칸, "원본값": "", "제안값": 값, "사유": "", "근거인용": "",
                        "오류유형": "4차 결정", "승인상태": 상})


def _판(tmp_path: Path) -> Path:
    판 = tmp_path / "판"
    (판 / "총괄" / "판1").mkdir(parents=True)
    (판 / "상태.json").write_text(json.dumps({"끝난단계": [], "소견": []}, ensure_ascii=False),
                                encoding="utf-8")
    return 판


def test_돌리개가_읽은_목록이_엔진과_같다(돌리개):
    """한 곳에서 읽는다 — 엔진의 사전과 글자까지 같아야 한다. sentiment_dir 이 꼭 들어 있다."""
    읽은 = set(돌리개.파생칸들())
    assert 읽은, "돌리개가 엔진에서 받지 않는 칸 목록을 못 읽었다"
    assert 읽은 == _엔진_파생칸()
    assert "sentiment_dir" in 읽은


def test_감성방향을_승인하면_아무것도_안_옮기고_멈춘다(돌리개, tmp_path, monkeypatch, capsys):
    """★ 알맹이. 멈추지 않으면 승인이 최종 엑셀에서 조용히 사라진다."""
    판 = _판(tmp_path)
    _판단표(판 / "아웃풋1_회의에서_정할것",
           [("topic", "구매의사", "승인"), ("sentiment_dir", "긍정", "승인")])
    옮김 = []
    monkeypatch.setattr(돌리개, "인풋2_옮기기", lambda *a, **k: 옮김.append(1) or (1, "x"))
    monkeypatch.setattr(돌리개, "AI돌리기",
                        lambda *a, **k: pytest.fail("멈춰야 하는데 총괄 AI 를 띄웠다"))
    코드 = 돌리개.사차반영(판, {}, {"이름": "판1"})
    말 = capsys.readouterr().out
    assert 코드 == 2
    assert not 옮김, "멈추기 전에 아웃풋 1 을 총괄 자리로 옮겼다"
    assert "sentiment_dir" in 말 and "받지 않는 칸" in 말
    assert "S01-01" in 말, "어느 줄이 걸렸는지 말하지 않았다"


def test_반려한_감성방향과_다른_칸_승인은_막지_않는다(돌리개, tmp_path):
    """반려는 반영되지 않으니 문제없다. topic 같은 보통 칸 승인도 그대로 간다."""
    쪽 = tmp_path / "아웃풋1"
    _판단표(쪽, [("sentiment_dir", "긍정", "반려"), ("topic", "구매의사", "승인"),
               ("cej", "탐색", "승인"), ("status", "scope_excluded", "승인")])
    걸린, 못봄 = 돌리개.파생칸_승인(쪽)
    assert 걸린 == [] and 못봄 == []


def test_엔진_목록을_못_읽으면_통과가_아니라_멈춘다(돌리개, tmp_path, monkeypatch, capsys):
    """「못 찾음」 은 「없음」 이 아니다 — 목록을 못 읽은 채 지나가면 검사가 눈먼다."""
    판 = _판(tmp_path)
    _판단표(판 / "아웃풋1_회의에서_정할것", [("topic", "구매의사", "승인")])
    monkeypatch.setattr(돌리개, "파생칸들", lambda: ())
    monkeypatch.setattr(돌리개, "인풋2_옮기기",
                        lambda *a, **k: pytest.fail("확인 못 했는데 옮겼다"))
    assert 돌리개.사차반영(판, {}, {"이름": "판1"}) == 2
    assert "확인하지 못했습니다" in capsys.readouterr().out


def test_안내문에_받지_않는_칸이_엔진_목록대로_적힌다(돌리개):
    글 = 돌리개.정하는법_글()
    assert "{받지않는칸}" not in 글, "자리를 안 바꿨다"
    for 칸 in _엔진_파생칸():
        assert "`%s`" % 칸 in 글, "안내문에 %s 가 없다" % 칸
