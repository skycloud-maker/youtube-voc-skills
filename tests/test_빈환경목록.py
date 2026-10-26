# -*- coding: utf-8 -*-
"""빈 컴퓨터에 **무엇을 깔라고 적었나** 가 실제로 필요한 것과 같은가 (2026-10-26).

★ 왜 (sky 2026-10-26) — 「완전 깨끗한 새 노트북에서 클로드로 skill 주고 돌리면 안된다는 것인가요?」
  밟아 보니 **안 되는 자리가 있었다.** 안내서·스킬·도구가 모두 「pandas · openpyxl」 이라고 적었는데,
  대시보드 HTML 은 `pyyaml` 도 필요했다 (엔진의 계산 모듈이 설정 yaml 을 읽는다).
  빈 환경에서 `No module named 'yaml'` 로 막혔다 — 받는 사람이 그 자리에서 멈췄을 것이다.

★ 목록은 `tools/빈환경_시험.py` 의 `보기패키지` **한 곳에서만** 정한다 (공통 규칙 6).
  이 시험은 **적어 둔 세 자리**(꾸러미 안내서 · 스킬 설명 · 도구 안내문)가 그것과 같은지 댄다.
  하나만 고치고 나머지를 두면 다시 어긋난다 — 전에 그래서 어긋나 있었다.

★ 여기서 재지 **않는** 것 — 1차(키 둘)와 2·3·4차(`claude`·`codex` 명령)는 빈 환경 시험으로
  확인할 수 없다. 그 자리는 「안 해 봤다」 로 남는다 (결정 0005).
"""
from __future__ import annotations

import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
_뿌리 = _여기.parent
sys.path.insert(0, str(_뿌리 / "tools"))
import 빈환경_시험 as 빈환경  # noqa: E402

적힌자리 = {
    "꾸러미 안내서 (tools/판_묶기.py)": _뿌리 / "tools" / "판_묶기.py",
    "대시보드 스킬 설명": _뿌리 / "plugin" / "skills" / "showing-voc-dashboard" / "SKILL.md",
    "도구 안내문 (자료_담기.py)": (_뿌리 / "plugin" / "skills" / "showing-voc-dashboard"
                           / "scripts" / "자료_담기.py"),
}


def test_목록이_한_곳에서_정해진다():
    assert 빈환경.보기패키지, "보기패키지 목록이 비었다"
    assert set(빈환경.보기패키지) == {"pandas", "openpyxl", "pyyaml"}, (
        "보기패키지가 바뀌었다 — 바꿀 때는 빈 환경 시험을 다시 돌려 확인하고 적힌 자리를 다 고친다: %s"
        % (빈환경.보기패키지,))


def test_적어_둔_자리마다_목록이_같다():
    """★ 셋 다 같은 꾸러미를 적어야 한다. 하나라도 빠지면 빈 컴퓨터에서 막힌다.

    ★ **한 줄에 셋이 다** 있어야 한다. 「파일 어딘가에 그 낱말이 있나」 로 보면 설명 문장에
      이름이 한 번 나오는 것만으로 통과한다 — 2026-10-26 에 일부러 깨 보고 알았다
      (요구 줄에서 `pyyaml` 을 지웠는데 시험이 통과했다. 밑에 설명 줄이 있어서였다).
    """
    빠진것 = []
    for 이름, 길 in 적힌자리.items():
        assert 길.is_file(), "적힌 자리를 못 찾았다 — %s (%s)" % (이름, 길)
        줄들 = 길.read_text(encoding="utf-8").split(chr(10))
        모인줄 = [l for l in 줄들 if all(꾸 in l for 꾸 in 빈환경.보기패키지)]
        if not 모인줄:
            없는것 = [꾸 for 꾸 in 빈환경.보기패키지
                   if not any(꾸 in l for l in 줄들)]
            빠진것.append("%s — %s" % (이름, " · ".join(없는것) or "한 줄에 모여 있지 않다"))
    assert not 빠진것, (
        "깔 목록이 어긋난다 (한 줄에 %s 가 다 있어야 한다):" % " · ".join(빈환경.보기패키지)
        + chr(10) + "  " + (chr(10) + "  ").join(빠진것))


def test_빈환경_시험이_있고_무엇을_못_보는지_적혀_있다():
    """★ 「안 해 봤다」 를 숨기지 않는다 — 1차·2·3·4차는 이 시험으로 못 본다."""
    글 = (_뿌리 / "tools" / "빈환경_시험.py").read_text(encoding="utf-8")
    for 말 in ("claude", "codex", "안 해 봤다"):
        assert 말 in 글, "빈 환경 시험이 못 보는 자리를 적지 않았다 — %s" % 말
