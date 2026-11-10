# -*- coding: utf-8 -*-
"""규칙 스크립트로 찍은 판독을 성실성검사가 잡는가 — 그리고 총괄이 직접 돌려 멈추는가 (2026-11-10).

★ 왜 이 시험이 있나 — 실측 판(LG 로봇청소기 · 2026-11-09)에서 판독B(Codex)가
  판정을 **규칙 스크립트로** 찍었다. 판정 칸 730줄의 사유가 9가지 문장뿐이었고
  (회차별 고유율 6.7~9.8%), 근거(quote)는 조각 본문을 통째로 붙였다.
  그런데 성실성검사는 통과시켰다 — 회차끼리 견주는 검사라 **모든 회차가 똑같이**
  얕으면 못 잡고, 「근거 돌려 씀」 은 본문 통째 인용(행마다 다르다)으로 피해 갔다.
  또 성실성검사는 판독자가 **스스로** 돌리게만 되어 있어 총괄은 몰랐다.
  같은 판에서 원문을 읽은 판독A(Claude)는 고유율 47~75% 였다.
  (sky 2026-11-10 「LLM 이 직접 읽고 판단해서 분석을 해야」)

★ 재는 것
  · 사유가 몇 가지 문장뿐인 회차를 반려한다 (한 줄 JSON · ```json 배열 두 형식 모두)
  · 행마다 사유가 다른 회차는 반려하지 않는다 (헛경보도 사고다)
  · 근거 칸 · 본문 · 요약 글의 사유는 세지 않는다 (같은 말이 정상인 칸)
  · 판정이 적은 회차는 보지 않는다
  · 총괄이 직접 돌려 사유 판박이면 **멈춘다** · 판정 파일을 못 찾으면 「이상 없음」 이라 하지 않는다
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parents[1]
_도구 = _뿌리 / "plugin" / "shared" / "tools" / "성실성검사.py"
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
sys.path.insert(0, str(_뿌리 / "plugin" / "shared" / "tools"))
sys.path.insert(0, str(_뿌리 / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"))
sys.path.insert(0, str(_뿌리 / "tools"))
총괄 = pytest.importorskip("한줄_돌리기", reason="총괄 스크립트를 못 읽었다")


@pytest.fixture()
def 검사():
    spec = importlib.util.spec_from_file_location("성실성검사_시험", _도구)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _행(i: int, 사유, 통째: bool = False) -> dict:
    본 = "로봇청소기 %d번 댓글인데 흡입력은 좋은데 앱 연결이 자꾸 끊겨요 진짜" % i
    return {"atomic_id": "a-%03d" % i, "atomic_voc": 본, "findings": [
        {"field": "topic", "current": "N/A", "proposed": "앱/스마트",
         "reason": 사유(i), "quote": 본 if 통째 else "앱 연결이 자꾸 끊겨요"},
        {"field": "topic_evidence", "current": "", "proposed": "앱 연결이 자꾸 끊겨요",
         "reason": "라벨을 바꿨으므로 근거도 바꾼다", "quote": "앱 연결이 자꾸 끊겨요"},
    ]}


def _한줄형(길: Path, 행들: list) -> Path:
    길.write_text("# 판독결과\n\n- 시작: 2026-11-09 21:40:04\n- 종료: 2026-11-09 21:57:00\n"
                 + "\n".join(json.dumps(r, ensure_ascii=False) for r in 행들), encoding="utf-8")
    return 길


def _배열형(길: Path, 행들: list) -> Path:
    길.write_text("# 판독 결과\n\n- 시작: 2026-11-09 18:37:52\n- 종료: 2026-11-09 19:10:30\n\n```json\n"
                 + json.dumps(행들, ensure_ascii=False, indent=1) + "\n```\n", encoding="utf-8")
    return 길


판박이 = lambda i: ["라벨을 바로잡음", "점수 정합화", "니즈 맞춤"][i % 3]
제각각 = lambda i: "%d번 댓글은 앱 끊김을 말한다 — 연결 문제라 앱/스마트" % i


@pytest.mark.parametrize("쓰기", [_한줄형, _배열형])
def test_사유가_판에_박힌_회차를_반려한다(검사, tmp_path, monkeypatch, capsys, 쓰기):
    f = 쓰기(tmp_path / "판독결과_full_01_Codex.md", [_행(i, 판박이, 통째=True) for i in range(40)])
    r = 검사.사유재기(f.read_text(encoding="utf-8"))
    assert r["사유"] == 40, "판정 칸을 못 읽었다 — 형식(%s)을 못 읽으면 검사가 헛통과한다" % 쓰기.__name__
    assert r["사유가짓"] == 3
    monkeypatch.setattr(sys, "argv", ["성실성검사.py", str(f)])
    assert 검사.main() == 1
    assert "★사유가 판에 박힘" in capsys.readouterr().out


@pytest.mark.parametrize("쓰기", [_한줄형, _배열형])
def test_행마다_사유가_다르면_반려하지_않는다(검사, tmp_path, monkeypatch, capsys, 쓰기):
    f = 쓰기(tmp_path / "판독결과_full_01_claudecode.md", [_행(i, 제각각) for i in range(40)])
    monkeypatch.setattr(sys, "argv", ["성실성검사.py", str(f)])
    검사.main()
    assert "사유가 판에 박힘" not in capsys.readouterr().out


def test_근거_칸의_같은_사유는_세지_않는다(검사, tmp_path):
    f = _한줄형(tmp_path / "판독결과_full_01_x.md", [_행(i, 제각각) for i in range(40)])
    r = 검사.사유재기(f.read_text(encoding="utf-8"))
    assert r["사유"] == 40, "topic_evidence 의 사유까지 셌다 — 근거 칸은 같은 말이 정상이다"


def test_판정이_적은_회차는_보지_않는다(검사, tmp_path, monkeypatch, capsys):
    f = _한줄형(tmp_path / "판독결과_full_01_Codex.md", [_행(i, 판박이) for i in range(10)])
    monkeypatch.setattr(sys, "argv", ["성실성검사.py", str(f)])
    검사.main()
    assert "사유가 판에 박힘" not in capsys.readouterr().out


def test_총괄이_직접_돌려_판박이면_멈춘다(tmp_path):
    결과 = tmp_path / "판독B" / "_판독패키지" / "_결과"
    결과.mkdir(parents=True)
    _한줄형(결과 / "판독결과_full_01_Codex.md", [_행(i, 판박이, 통째=True) for i in range(40)])
    with pytest.raises(총괄.멈춤) as e:
        총괄.성실성_직접(tmp_path / "판독B", "판독B")
    assert "판에 박혀" in str(e.value)


def test_총괄이_직접_돌려_제대로_한_판독은_통과한다(tmp_path):
    결과 = tmp_path / "판독A" / "_판독패키지" / "_결과"
    결과.mkdir(parents=True)
    _배열형(결과 / "판독결과_full_01_claudecode.md", [_행(i, 제각각) for i in range(40)])
    assert 총괄.성실성_직접(tmp_path / "판독A", "판독A") == "이상 없음"


def test_판정_파일을_못_찾으면_이상_없음이라_하지_않는다(tmp_path):
    (tmp_path / "판독A" / "_판독패키지" / "_결과").mkdir(parents=True)
    말 = 총괄.성실성_직접(tmp_path / "판독A", "판독A")
    assert 말 != "이상 없음" and "확인하지 못함" in 말
