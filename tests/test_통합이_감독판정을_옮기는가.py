# -*- coding: utf-8 -*-
"""통합(`build_master.py`)이 **감독 판정을 판정 칸에 옮기는가** (2026-11-01 · 결정 0012).

★ 왜 이 시험이 있나 — 2판을 통째로 다시 돌리고 **단계마다** 옛 2판과 대서 찾았다.

      칸              2차 판독A(claude)   2차 판독B(codex)   3차 최종
      brand               91.72%             47.61%        46.46%
      entity_role         87.73%             49.22%        48.40%

  판독A 는 옛 2판과 꽤 맞았는데 **최종은 판독B 숫자를 그대로 물려받았다.**
  까닭 — `base = dict(K[aid])` 로 **둘째 번들**을 깔고 `CC_FIELDS` 24칸을 거기서
  **무조건** 가져왔다. 감독 판정은 `topic`·`status`·`topic_evidence` 에만 닿았다.

  측정으로 못 박았다 — 감독이 「판독A 가 맞다」 고 한 행에서 최종 값:
      brand 526행 → A값 **0** · B값 **526**     entity_role 629행 → 0 · 629
      cej   804행 → 0 · 804                   rootcause_score 796행 → 0 · 796
  감독은 전체에서 판독A 를 1,893 대 405 로 택했는데 **한 건도** 안 닿았다.

재는 것 셋 —
  ㉠ 감독이 고른 쪽의 값이 **24칸에** 들어가는가
  ㉢ 어느 번들이 **바탕**인지 찍는가 · `--바탕` 으로 고를 수 있는가
  ㉣ 감독 **한 명만** 본 행을 `reader_agree`(합의)로 적지 **않는가**
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
도구쪽 = REPO / "plugin" / "shared" / "tools" / "build_master.py"


@pytest.fixture()
def 통합():
    spec = importlib.util.spec_from_file_location("빌드마스터_시험", 도구쪽)
    m = importlib.util.module_from_spec(spec)
    sys.modules["빌드마스터_시험"] = m
    spec.loader.exec_module(m)
    return m


def test_감독이_고른_쪽의_24칸을_옮긴다(통합):
    """★ 알맹이 — 합의 분기에서 `CC_FIELDS` 를 고른 쪽에서 가져오는가."""
    글 = inspect.getsource(통합.main)
    # 합의 분기 뒤쪽만 본다 (`elif a[:2] == b[:2]` 아래)
    i = 글.find("elif a[:2] == b[:2]")
    assert i > 0, "합의 분기를 못 찾았다 — 코드가 바뀌었으면 이 시험을 고친다"
    뒤 = 글[i:i + 4000]
    assert "for _f in CC_FIELDS" in 뒤, (
        "감독이 합의한 행에서 **CC_FIELDS 24칸을 옮기지 않는다.** "
        "그러면 감독 판정이 topic 하나에만 닿고, brand·cej·entity_role 은 "
        "바탕(판독자 둘째) 값이 그대로 간다 — 실측으로 526/629/804/796행이 그랬다.")
    assert "_고른쪽자료" in 뒤, "고른 쪽 자료를 집는 이름이 없다"
    # 감독이 직접 낸 라벨(judge)은 판독자 쪽이 없으므로 바탕을 둔다
    assert "else None" in 뒤, (
        "감독이 **직접** 낸 라벨(who == 'judge')일 때 판독자 쪽이 없는데 "
        "무언가를 가져오면 **없는 값을 지어내는** 것이다")


def test_CC_FIELDS_에_판정_칸이_다_들어_있다(통합):
    """24칸 목록이 줄면 옮기는 것도 같이 줄어든다 — 목록을 지킨다."""
    꼭 = {"brand", "entity_role", "cej", "rootcause_score", "rootcause_target",
         "need_signal_type", "inquiry_type", "tee_emotion_score", "tee_summary"}
    빠진 = 꼭 - set(통합.CC_FIELDS)
    assert not 빠진, "CC_FIELDS 에서 빠진 판정 칸 — %s" % sorted(빠진)
    assert len(통합.CC_FIELDS) >= 24, "CC_FIELDS 가 %d칸이다 — 24칸 이상이어야 한다" % len(통합.CC_FIELDS)


def test_감독_한명만_본_행을_합의로_적지_않는다(통합):
    """★ 판독자 둘이 **갈려서** 3차로 간 행이다. 「합의」 로 적으면 사람이 속는다."""
    글 = inspect.getsource(통합.main)
    i = 글.find("elif aid in JX or aid in JK")
    assert i > 0, (
        "감독 **한 명만** 본 행을 가르는 분기가 없다 — 그러면 그 행이 "
        "`reader_agree`(두 판독자 합의)로 적힌다. 갈려서 3차로 간 행인데 「합의」 다.")
    뒤 = 글[i:i + 900]
    assert "감독_한쪽만" in 뒤, "decided_by 를 「감독_한쪽만」 으로 적지 않는다"
    assert "합의가 아니다" in 뒤, "사람이 읽을 말에 「합의가 아니다」 가 없다"
    # reader_agree 는 그 **뒤** else 에만 있어야 한다
    j = 글.find("'reader_agree'", i)
    assert j > i, "reader_agree 가 한쪽만 본 행에도 걸린다"


def test_바탕_번들을_찍는다(통합, capsys, monkeypatch):
    """★ 몰래 정해지지 않게. 지금은 폴더 이름 **글자 순서**가 바탕을 정했다."""
    monkeypatch.setattr(sys, "argv", ["build_master.py", "claudecode_bundle", "Codex_bundle"])
    하나, 둘 = 통합._판독번들()
    assert (하나, 둘) == ("claudecode_bundle", "Codex_bundle")
    말 = capsys.readouterr().out
    assert "바탕 번들 = Codex_bundle" in 말, ("어느 쪽이 바탕인지 안 찍었다 —\n%s" % 말)
    assert "판정 24칸을 여기서" in 말, 말


def test_바탕을_골라_줄_수_있다(통합, capsys, monkeypatch):
    """`--바탕` 으로 고르면 그 번들이 바탕(둘째)이 된다."""
    monkeypatch.setattr(sys, "argv",
                        ["build_master.py", "claudecode_bundle", "Codex_bundle",
                         "--바탕", "claudecode"])
    하나, 둘 = 통합._판독번들()
    assert 둘 == "claudecode_bundle", (
        "`--바탕 claudecode` 인데 바탕이 %r 다" % 둘)
    assert 하나 == "Codex_bundle"
    assert "`--바탕` 으로 고른 것" in capsys.readouterr().out


def test_바탕이_하나로_안_정해지면_멈춘다(통합, monkeypatch):
    """★ 「못 찾음」 을 「아무거나」 로 바꾸지 않는다."""
    monkeypatch.setattr(sys, "argv",
                        ["build_master.py", "a_bundle", "b_bundle", "--바탕", "없는이름"])
    with pytest.raises(SystemExit):
        통합._판독번들()
    monkeypatch.setattr(sys, "argv",
                        ["build_master.py", "x_bundle", "x2_bundle", "--바탕", "x"])
    with pytest.raises(SystemExit):
        통합._판독번들()
