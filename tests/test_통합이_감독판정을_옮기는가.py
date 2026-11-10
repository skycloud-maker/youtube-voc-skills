# -*- coding: utf-8 -*-
"""통합(`build_master.py`)이 **감독 한 명만 본 행을 합의로 적지 않는가** (결정 0012 ㉣).

★★ 이 파일은 **동결 3a 에서 ㉣ 하나만** 담고 있다 (2026-11-04).

  sky 결정 2026-11-04 — 동결점을 넷으로 갈랐다. 동결 3 을 둘로 나눈다.

      동결 3a  **결과를 바꾸지 않고** 「틀린 것이 숨는 것」 만 막는다 — ㉣ ㉤ ㉥
      동결 3b  **결과가 달라지는 것** — ㉠ ㉢ ㉦ · 그리고 3차 측정에서 찾은 넷

  그래서 앞선 저장소(`claude/시험환경`, 커밋 `e1331da`)에 있던 이 파일의
  **시험 여섯 중 다섯**(㉠ ㉢ 쪽)을 **여기 넣지 않았다.** 그 다섯은 ㉠ ㉢ 가
  들어오는 **동결 3b 에서 이 파일로 돌아온다.** 파일을 두 벌로 만들지 않기
  위해 **이름을 그대로 두었다** — 돌아올 때 git 이 이 자리를 가리킨다.

      동결 3b 에서 돌아올 시험 다섯 (`e1331da` 에 있다)
        test_감독이_고른_쪽의_24칸을_옮긴다        ㉠
        test_CC_FIELDS_에_판정_칸이_다_들어_있다    ㉠
        test_바탕_번들을_찍는다                   ㉢
        test_바탕을_골라_줄_수_있다                ㉢
        test_바탕이_하나로_안_정해지면_멈춘다        ㉢

  ★ 원문 시험 6개 / 지금 옮긴 것 **1개** / 동결 3b 로 미룬 것 **5개**.
    아래 시험 하나는 `e1331da` 의 것을 **글자 그대로** 옮긴 것이다 (줄이지 않았다).

  ★★ 뒤 이야기 (sky 2026-11-10 「판독A 바탕」) — ㉢ 를 **먼저** 들여왔다.
    실측 판(LG 로봇청소기)에서 3차_마무리 가 번들을 정렬해 넘겼고, 윈도우 정렬은
    대소문자를 안 가려 Codex 가 바탕이 됐다 — 최종 서술 칸 825행이 전부 Codex 값,
    CC 조각 60행 누락. 그 판의 판독B 를 다시 돌리려면 바탕부터 정해야 했다.
    ㉢ 시험 셋을 `e1331da` 에서 **글자 그대로** 옮겼다 (맨 끝 쪽 셋).
    더한 시험 둘 — 3차_마무리 가 판독A 를 고르는가 · `--바탕` 값을 번들로 안 세는가.
    ㉠ 시험 둘은 아직 동결 3b 에 있다.
    ★ 원문 시험 6개 / 지금 옮긴 것 **4개** / 동결 3b 로 미룬 것 **2개** (㉠).

★ 왜 ㉣ 는 지금 넣나 — 값을 바꾸는 것이 아니라 **거짓 기록을 막는 것**이기 때문이다.
  판독자 둘이 **갈려서** 3차로 간 행인데 감독 한 명만 보면 그 행이
  `reader_agree`(두 판독자 합의)로 적히고 **경고도 없었다.** 사람은 합의된 줄 안다.
  2026-11-01 판에서는 한쪽만 본 행이 0 이라 터지지 않았지만, 감독이 한 회차라도
  빠뜨리면 그대로 둔갑한다.
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


def test_아직_안_옮긴_것이_있다는_것을_적어_둔다():
    """★ 「못 찾음」 을 「없음」 으로 돌려주지 않는다 — 미룬 것이 있음을 시험으로도 남긴다.

    ㉠ 를 **일부러 안 넣었다.** 그런데 코드에 그것이 들어와 있으면
    이 파일의 시험 둘이 빠진 채로 통과해 버린다 — 그러면 ㉠ 가
    **시험 없이** 들어간 것이 된다. 그것을 막는다.
    (㉢ 는 2026-11-10 에 시험 셋과 함께 들어왔다 — 맨 위 뒤 이야기)
    """
    글 = 도구쪽.read_text(encoding="utf-8")
    들어왔다 = [이름 for 이름, 무늬 in (("㉠ 24칸 옮기기", "for _f in CC_FIELDS"),)
             if 무늬 in 글]
    assert not 들어왔다, (
        "동결 3a 에는 없어야 할 것이 build_master.py 에 들어와 있다 — %s.\n"
        "  동결 3b 로 넘어간 것이라면 `e1331da` 의 시험 둘을 이 파일로 **같이** "
        "가져오고 이 시험을 지우십시오. 시험 없이 들어가면 안 됩니다."
        % " · ".join(들어왔다))


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


def test_돌리개가_판독A를_바탕으로_고른다():
    """★ sky 2026-11-10 「판독A 바탕」 — 돌리개가 3차_마무리 에 `--바탕 claudecode` 를 넘기고,
    3차_마무리 는 그것을 build_master 에 넘긴다.

    넘기지 않으면 바탕은 번들 순서로 정해지고, 윈도우에서는 Codex 가 바탕이 된다
    (실측 판에서 실제로 그랬다). 화면에도 어느 쪽이 바탕인지 찍어야 한다 —
    build_master 의 말은 끝 14줄만 보여 주므로 바탕 줄이 잘린다.
    ★ 3차_마무리 의 **기본값은 그대로** 다 — 얼린 2판 기준이 옛 순서로 만들어졌다.
    """
    돌리개 = (REPO / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"
            / "한줄_돌리기.py").read_text(encoding="utf-8")
    assert '{"3차_마무리.py": ["--바탕", "claudecode"]}' in 돌리개, \
        "돌리개가 바탕을 고르지 않는다 — 순서가 바탕을 정한다"
    assert "*_더.get(도구, [])" in 돌리개, "고른 바탕을 3차_마무리 에 넘기지 않는다"
    글 = (REPO / "plugin" / "shared" / "tools" / "3차_마무리.py").read_text(encoding="utf-8")
    assert "*바탕인자" in 글, "3차_마무리 가 받은 바탕을 build_master 에 넘기지 않는다"
    assert '"바탕 번들 ="' in 글, "어느 쪽이 바탕인지 화면에 따로 찍지 않는다"
    assert "i not in _값자리" in 글, "`--바탕` 뒤 값을 감독 폴더로 센다"


def test_바탕_값이_앞에_와도_번들로_세지_않는다(통합, monkeypatch, capsys):
    """`--바탕 claudecode` 의 `claudecode` 는 번들이 아니다 (준비본에서 고친 한 군데)."""
    monkeypatch.setattr(sys, "argv",
                        ["build_master.py", "--바탕", "claudecode", "claudecode_bundle", "Codex_bundle"])
    하나, 둘 = 통합._판독번들()
    assert (하나, 둘) == ("Codex_bundle", "claudecode_bundle")
