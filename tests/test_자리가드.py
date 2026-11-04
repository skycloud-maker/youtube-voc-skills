# -*- coding: utf-8 -*-
"""일하는 자리가 **저장소 안이면 멈추는가** (결정 0013 의 가드 · 2026-11-04).

★ 왜 이 시험이 있나 — 결정 0013 으로 **AI 가 자리를 제안**하게 됐다. 사람이 안 보고
  「네」 하면 저장소 안이 자리로 잡힐 수 있고, 그러면 1차 엔진이 결과를 저장소에 쏟는다.
  게다가 폴더 꾸러미장은 꾸러미를 **저장소에서 바로 읽으므로** 읽히는 중인 폴더에
  결과를 붓는 꼴이 된다.

★ 이 시험은 **두 가지를 따로** 본다. 둘째가 빠지면 ㉥ 과 같은 일이 난다 —
  **함수는 있는데 아무도 안 불러서** 가드가 없는 것과 같았던 일.
  ① 가드 함수가 정말 가리는가 (안 → 막는다 · 밖 → 통과)
  ② **문 다섯이 그 함수를 실제로 부르는가**
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
플러그인 = REPO / "plugin"
가드쪽 = 플러그인 / "shared" / "lib" / "자리_가드.py"

# ── 가드를 **부르고 있어야 하는** 문 다섯 ──────────────────────────────────────
문들 = {
    "한줄_돌리기.py": 플러그인 / "skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py",
    "총괄자리_차리기.py": 플러그인 / "skills/coordinating-voc-pipeline/scripts/총괄자리_차리기.py",
    "판독폴더_차리기.py": 플러그인 / "skills/reading-voc-comments/scripts/판독폴더_차리기.py",
    "감독폴더_차리기.py": 플러그인 / "skills/supervising-voc-disagreements/scripts/감독폴더_차리기.py",
    "1차자리_차리기.py": 플러그인 / "skills/running-voc-engine/scripts/1차자리_차리기.py",
}


def _가드():
    assert 가드쪽.is_file(), "가드가 **없다** — %s" % 가드쪽
    규 = importlib.util.spec_from_file_location("자리_가드_시험", 가드쪽)
    m = importlib.util.module_from_spec(규)
    규.loader.exec_module(m)
    return m


# ── ① 가드 함수가 정말 가리는가 ───────────────────────────────────────────────

def test_꾸러미뿌리를_찾는다():
    뿌리 = _가드().꾸러미뿌리(가드쪽)
    assert 뿌리 == 플러그인, "꾸러미 뿌리를 %s 로 봤다 — plugin/ 이어야 한다" % 뿌리


@pytest.mark.parametrize("안쪽", [
    "plugin",
    "plugin/shared",
    "plugin/skills/coordinating-voc-pipeline",
    "dist",
    "dist/판",
    "docs",
    "tests",
    ".",                      # 저장소 뿌리 그 자체
])
def test_저장소_안이면_막는다(안쪽):
    m = _가드()
    자리 = (REPO / 안쪽).resolve()
    괜찮, 말들 = m.자리_확인(자리, "판자리", 뿌리=플러그인)
    assert not 괜찮, "**막아야 하는데 통과했다** — %s" % 자리
    글 = "\n".join(말들)
    assert "저장소 안" in 글, "왜 막혔는지 말하지 않는다:\n%s" % 글
    assert str(자리) in 글, "어느 자리가 걸렸는지 안 찍는다:\n%s" % 글
    assert "이렇게 하십시오" in 글, "무엇을 하라는 말이 없다:\n%s" % 글


@pytest.mark.parametrize("밖쪽", ["VoC_판/연-월_검색어", "VoC/판1", "어딘가/판"])
def test_저장소_밖이면_통과한다(밖쪽, tmp_path):
    """★ 경로를 **글로 박지 않는다** — `tests/test_no_old_paths.py` 가 막는다
    (`paths.py` 밖에 절대경로를 두지 않는다). 그래서 `tmp_path` 로 만든다."""
    자리 = tmp_path / 밖쪽
    괜찮, 말들 = _가드().자리_확인(자리, "판자리", 뿌리=플러그인)
    assert 괜찮, "**밖인데 막았다** — %s\n%s" % (자리, "\n".join(말들))
    assert 말들 == [], "밖인데 군말이 붙었다 — %s" % 말들


@pytest.mark.parametrize("울쪽", [
    "plugin",                                        # 보통 쓰는 꼴
    ".claude/worktrees/어떤작업자리",                   # 작업 폴더(worktree)로 돌릴 때
    ".claude/worktrees/어떤작업자리/plugin",
])
def test_권하는_자리가_저장소_안이_아니다(울쪽):
    """「저장소 밖으로 가라」 면서 **저장소 안을 권하면** 안 된다 (2026-11-04 실제로 그랬다)."""
    m = _가드()
    울 = (REPO / 울쪽).resolve()
    권 = m.권할자리(울)
    assert not m._안에있나(권, 울), "권한 자리가 **울 안**이다 — 울 %s · 권 %s" % (울, 권)
    assert not any(x.lower() == ".claude" for x in 권.parts), (
        "`.claude` 아래를 권했다 — 울 밖으로 보이지만 저장소 안이다. 권 %s" % 권)


def test_막는_말에_권하는_자리가_저장소_안이_아니다():
    """사람이 실제로 보는 **그 말 속의 자리**까지 본다."""
    m = _가드()
    괜찮, 말들 = m.자리_확인((플러그인 / "판1").resolve(), "판자리", 뿌리=플러그인)
    assert not 괜찮
    권줄 = [l for l in 말들 if "이렇게 하십시오" in l]
    assert 권줄, "무엇을 하라는 줄이 없다"
    assert ".claude" not in 권줄[0], "권하는 말에 `.claude` 아래 자리가 들었다 — %s" % 권줄[0]
    assert str(플러그인).lower() not in 권줄[0].lower(), (
        "권하는 말이 꾸러미 폴더 안을 가리킨다 — %s" % 권줄[0])


def test_저장소_바로_위는_막는다():
    """저장소 뿌리는 꾸러미 뿌리의 **위 한 칸**이다 — 거기까지 막아야 한다."""
    괜찮, _ = _가드().자리_확인(REPO.resolve(), "판자리", 뿌리=플러그인)
    assert not 괜찮, "저장소 뿌리(%s)를 통과시켰다" % REPO


def test_대소문자가_달라도_막는다(tmp_path):
    """윈도는 대소문자를 가리지 않는다 — 폴더 이름이 `PLUGIN` 이든 `plugin` 이든 같은 자리다.

    ★ **디스크에 없는 자리로 잰다** — 받는 분 컴퓨터에서 자리가 아직 없을 때가 이 경우다
      (처음 돌릴 때 자리를 새로 만든다). 있는 자리는 윈도 `Path.resolve()` 가 대소문자를
      스스로 고쳐 버려 이 길을 태우지 못한다.

    ★ 이것을 **무엇이 지키나** — 가드가 따로 소문자로 맞추지 않는다. 윈도 `pathlib` 이
      경로를 대소문자 가리지 않고 비교한다. 2026-11-04 에 일부러 `str(...).lower()` 를
      빼 봤더니 **시험이 그대로 통과**해서 그 줄이 쓸모없음을 알았고, 리눅스에서는
      오히려 틀린 답을 만들기에 지웠다. 이 시험은 **그 동작이 사라지지 않게** 지킨다.
    """
    m = _가드()
    없는곳 = tmp_path / "없는저장소_가드시험"
    없는뿌리 = 없는곳 / "plugin"
    자리 = 없는곳 / "PLUGIN" / "판1"
    assert not 없는뿌리.exists(), "시험이 기대한 것과 달리 그 자리가 **있다**"
    괜찮, _ = m.자리_확인(자리, "판자리", 뿌리=없는뿌리)
    assert not 괜찮, "대소문자만 다르게 적으면 **빠져나간다** — %s" % 자리

    # 위 한 칸(저장소 뿌리)도 대소문자를 가리지 않아야 한다
    괜찮, _ = m.자리_확인(없는곳 / "판1", "판자리", 뿌리=없는뿌리)
    assert not 괜찮, "저장소 뿌리를 대소문자로 빠져나간다"


def test_뿌리를_못_찾으면_조용히_통과하지_않는다(tmp_path):
    """「못 찾음」 을 「없음」 으로 돌려주지 않는다 — 조용히 통과하면 검사한 척이 된다."""
    m = _가드()
    빈곳 = tmp_path / "아무것도없는곳"
    빈곳.mkdir()
    assert m.꾸러미뿌리(빈곳) is None, (
        "plugin.json 도 SKILL.md 도 없는 자리에서 뿌리를 찾았다고 한다")

    # 못 찾는 경우를 **실제로 태운다**
    막아야, 울, 왜 = m.저장소안인가(빈곳 / "판", 찾는자리=빈곳)
    assert not 막아야 and 울 is None
    assert "확인하지 못했습니다" in 왜, "못 찾았다는 말을 안 한다 — %r" % 왜

    괜찮, 말들 = m.자리_확인(빈곳 / "판", "판자리", 찾는자리=빈곳)
    assert 괜찮, "못 찾았는데 막았다"
    assert any("확인하지 못했습니다" in l for l in 말들), (
        "**조용히 통과했다** — 못 찾았다는 말이 없다. 검사한 척이 된다:\n%s" % 말들)

    # 이 저장소에서는 뿌리를 찾으므로 통과하고 군말이 없다
    괜찮, 말들 = m.자리_확인(tmp_path / "판", "판자리")
    assert 괜찮 and 말들 == [], "뿌리를 찾았는데 군말이 붙었다 — %s" % 말들


def test_낱개로_꾸린_스킬에서도_울을_찾는다(tmp_path):
    """낱개 꾸러미(claude.ai 쪽 zip)에는 `plugin.json` 이 **없다** — `SKILL.md` 로 찾는다.

    ★ 2026-11-04 — 이 길이 없어서 **낱개 꾸러미에서는 가드가 아예 일하지 못했다.**
      「못 찾았다」 고 말하고 그냥 통과했다. `tests/test_build.py` 의 낱개 시험 넷이
      그것을 드러냈다 (「못 찾」 이 화면에 나왔다).
    """
    m = _가드()
    스킬 = tmp_path / "풀린곳" / "running-voc-engine"
    (스킬 / "shared" / "lib").mkdir(parents=True)
    (스킬 / "SKILL.md").write_text("# 스킬", encoding="utf-8")
    가드사본 = 스킬 / "shared" / "lib" / "자리_가드.py"
    가드사본.write_text("# 자리만 흉내 낸다", encoding="utf-8")

    assert m.꾸러미뿌리(가드사본) == 스킬, (
        "낱개 꾸러미에서 울을 **%s** 로 봤다 — 스킬 뿌리(%s)여야 한다"
        % (m.꾸러미뿌리(가드사본), 스킬))

    # 스킬 안과 그 위 한 칸은 막고, 그 밖은 통과해야 한다
    for 안 in (스킬, 스킬 / "판1", 스킬.parent, 스킬.parent / "판1"):
        괜찮, _ = m.자리_확인(안, "1차자리", 찾는자리=가드사본)
        assert not 괜찮, "낱개 꾸러미 안(%s)을 통과시켰다" % 안
    괜찮, 말들 = m.자리_확인(tmp_path / "1차자리", "1차자리", 찾는자리=가드사본)
    assert 괜찮, "낱개 꾸러미 밖인데 막았다 — %s" % "\n".join(말들)


def test_빠져나갈_깃발이_없다():
    """깃발이 있으면 AI 가 조용히 지나간다. 이것은 취향이 아니라 규칙이다."""
    글 = 가드쪽.read_text(encoding="utf-8")
    assert "빠져나갈 깃발을 두지 않는다" in 글, "왜 깃발이 없는지 적어 두지 않았다"

    인자글 = "".join(re.findall(r"def\s+자리_확인[^(]*\(([^)]*)\)", 글, re.S)).lower()
    나쁜 = [x for x in ("force", "override", "allow_inside", "강제", "무시") if x in 인자글]
    assert not 나쁜, "가드 함수에 빠져나갈 깃발이 있다 — %s" % 나쁜


# ── ② 문 다섯이 **실제로 부르는가** ───────────────────────────────────────────

@pytest.mark.parametrize("이름", sorted(문들))
def test_문이_가드를_부른다(이름):
    쪽 = 문들[이름]
    assert 쪽.is_file(), "%s 가 없다 — %s" % (이름, 쪽)
    글 = 쪽.read_text(encoding="utf-8")
    assert "import 자리_가드" in 글, (
        "%s 가 가드를 **들여오지 않는다.**\n"
        "  자리를 받는 문은 모두 `자리_가드.자리_확인하고_멈추기` 를 불러야 한다 — "
        "한 문만 열려 있으면 가드가 없는 것과 같다." % 이름)
    assert "자리_가드.자리_확인하고_멈추기" in 글, (
        "%s 가 가드를 들여오기만 하고 **부르지 않는다.**\n"
        "  ㉥ 에서 겪은 것과 같은 꼴이다 — 함수는 있는데 아무도 안 불러서 "
        "가드가 없는 것과 같았다." % 이름)


def test_가드가_자리를_받은_바로_뒤에_온다():
    """`resolve()` 로 자리를 만든 뒤 **다른 일을 하기 전에** 막아야 한다."""
    쪽 = 문들["한줄_돌리기.py"]
    줄들 = 쪽.read_text(encoding="utf-8").splitlines()
    받은줄 = [i for i, l in enumerate(줄들) if "판 = Path(a.판자리).resolve()" in l]
    assert len(받은줄) == 1, "판자리를 받는 줄이 %d개다 — 손으로 본다" % len(받은줄)
    i = 받은줄[0]
    뒤 = "\n".join(줄들[i + 1:i + 12])
    assert "자리_가드.자리_확인하고_멈추기" in 뒤, (
        "판자리를 받은 뒤 **열 줄 안에** 가드가 없다. 가드보다 먼저 도는 일이 있으면\n"
        "틀린 자리로 이미 무언가 했을 수 있다:\n%s" % 뒤)
