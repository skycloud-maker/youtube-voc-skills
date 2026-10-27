# -*- coding: utf-8 -*-
r"""실제 AI 시험이 **순수하게 스킬만으로** 돌았는지 재는 자리를 지킨다 (2026-10-27).

★ 왜 이 파일이 생겼나 (sky 2026-10-27)
  「지금 여기서는 순수하게 skill 만으로 돌아가는지.. 아니면 이전에 꾸러미와 과거 경험을
  활용해서 더 자세하게 돌릴지를 모르지 않나요?」 — **몰랐다.** 그래서 쟀고, 이렇게 나왔다.

  claude 시험은 **내 컴퓨터 설정을 그대로 물려받아** 돌고 있었다 —
    · 전역 CLAUDE.md(공통 작업규칙)가 들어갔다. 아이에게 물으니 「옛 저장소는 변화 0」 ·
      「축약 금지」 · 「건드림 / 안 건드림 / 확인할 것」 을 **문장째로 옮겨 적었다.**
    · 내 훅이 돌았다 — 모든 claude 기록의 첫 사건이 `SessionStart` 훅이다.
    · 보인 것이 스킬 50개 · 슬래시 87개 · 플러그인 3개였다 (우리 스킬은 그중 6개).
  **쓴 것**은 깨끗했다 — 73그릇 전량에서 남의 스킬·MCP·웹·서브에이전트 호출이 0이었다.
  codex 쪽도 깨끗했다 — `~/.codex/AGENTS.md` 가 0바이트고, 쓴 것이 네 종류뿐이었다.

  받는 사람 컴퓨터엔 그 규칙도 훅도 없다. 그래서 **앞으로는 깃발로 끄고 돌리고**,
  그릇 자신이 「어떻게 돌았나」 를 말하게 적는다. 이 파일은 그 재는 자리를 지킨다.

★ 여기서 재지 **않는** 것 — 모델이 학습으로 아는 것. 끌 수 없고 셀 수도 없다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
_뿌리 = _여기.parent
sys.path.insert(0, str(_여기 / "evals"))
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
import 스킬시험_돌리기 as 공용  # noqa: E402
from paths import PLUGIN  # noqa: E402

돌리개들 = sorted((_여기 / "evals").glob("*_돌리기.py"))


def _그릇(자리: Path, *, 누구: str = "claude", 깃발: list | None = None, 훅: bool = False,
        mcp: tuple = (), 스킬: list | None = None, init: bool = True,
         호출: tuple = (), 코덱스것: tuple = ()) -> Path:
    """채점기가 읽는 최소한의 그릇을 짓는다 — 시험.json + 대화.jsonl."""
    자리.mkdir(parents=True, exist_ok=True)
    (자리 / "작업").mkdir(exist_ok=True)
    (자리 / "시험.json").write_text(json.dumps(
        {"누구": 누구, "시험": "아무거나", "종료코드": 0, "돌린자리": str(자리 / "작업"),
         "깃발": list(공용.깨끗한깃발) if 깃발 is None else 깃발},
        ensure_ascii=False), encoding="utf-8")
    줄들 = []
    if 훅:
        줄들.append(json.dumps({"type": "system", "subtype": "hook_started",
                              "hook_name": "SessionStart:startup", "hook_event": "SessionStart"},
                             ensure_ascii=False))
    if init:
        줄들.append(json.dumps({
            "type": "system", "subtype": "init", "model": "claude-opus-5",
            "skills": ["youtube-voc:reading-voc-comments", "dataviz"] if 스킬 is None else 스킬,
            "mcp_servers": [{"name": n, "status": "connected"} for n in mcp],
            "plugins": [{"name": "youtube-voc"}],
        }, ensure_ascii=False))
    for 이름, 입 in 호출:
        줄들.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": 이름, "input": 입}]}}, ensure_ascii=False))
    for 종류 in 코덱스것:
        줄들.append(json.dumps({"type": "item.completed", "item": {"type": 종류}},
                             ensure_ascii=False))
    (자리 / "대화.jsonl").write_text("\n".join(줄들) + "\n", encoding="utf-8")
    return 자리


# ── ① 깃발이 한 자리에서 정해지고, 그 자리만 claude 를 띄운다 ────────────────────────
def test_깨끗한_깃발이_정해져_있다():
    assert "--setting-sources" in 공용.깨끗한깃발, 공용.깨끗한깃발
    assert "--strict-mcp-config" in 공용.깨끗한깃발, 공용.깨끗한깃발


def test_claude_명령이_깨끗한_깃발을_싣는다():
    명령 = 공용.claude_명령("claude")
    for 깃 in 공용.깨끗한깃발:
        assert 깃 in 명령 or 깃 == "", "깃발이 빠졌다 — %s / %s" % (깃, 명령)
    assert "--plugin-dir" in 명령 and str(PLUGIN) in 명령, 명령
    # 낱개는 플러그인을 주지 않는다 (스킬 폴더 하나만 주는 시험이다)
    assert "--plugin-dir" not in 공용.claude_명령("claude-낱개")
    # 끌 수도 있어야 한다 — 옛 방식과 대 보려면 필요하다
    assert "--strict-mcp-config" not in 공용.claude_명령("claude", 깨끗=False)


def test_claude_를_띄우는_자리가_한_곳이다():
    """★ 2026-10-27 까지 돌리개 **여섯 곳**에 같은 줄이 박혀 있었다 (공통 규칙 6).

    깃발 하나를 더하려면 여섯 곳을 고쳐야 했고, 그래서 하나도 안 들어가 있었다.
    """
    박힌것 = [p.name for p in 돌리개들 if 'which("claude")' in p.read_text(encoding="utf-8")]
    assert 박힌것 == ["스킬시험_돌리기.py"], (
        "claude 명령을 짜는 자리가 또 생겼다 — %s (claude_명령 을 쓴다)" % 박힌것)


def test_돌리개_여섯이_공통항목을_다_본다():
    빠진것 = []
    for p in 돌리개들:
        글 = p.read_text(encoding="utf-8")
        if "기대항목" not in 글:
            continue
        if "공통항목" not in 글 or "공통채점" not in 글:
            빠진것.append(p.name)
    assert not 빠진것, "공통항목·공통채점을 안 쓰는 돌리개가 있다 — %s" % 빠진것
    assert len(공용.공통항목) == 3, 공용.공통항목


# ── ② 깨끗하지 **않은** 자리는 걸려야 한다 ──────────────────────────────────────────
더럽혀보기 = {
    "깃발없이_돌렸다": {"깃발": []},
    "훅이_돌았다": {"훅": True},
    "MCP가_붙어있었다": {"mcp": ("claude.ai Google Drive",)},
    "무엇이_보였는지_모른다": {"init": False},
    "우리_스킬이_안_보였다": {"스킬": ["dataviz", "pdf"]},
}


@pytest.mark.parametrize("이름", sorted(더럽혀보기))
def test_더러운_자리는_걸린다(tmp_path, 이름):
    그릇 = _그릇(tmp_path / 이름, **더럽혀보기[이름])
    됨, 까닭 = 공용.자리가_깨끗했나(그릇)
    assert not 됨, "더러운 자리(%s)를 놓쳤다" % 이름
    assert 까닭, "걸렸다면 무엇이 걸렸는지 적어야 한다"


def test_깨끗한_자리는_통과한다(tmp_path):
    그릇 = _그릇(tmp_path / "깨끗")
    됨, 까닭 = 공용.자리가_깨끗했나(그릇)
    assert 됨, "깨끗한 자리인데 걸렸다 — 거짓 반려다: %s" % 까닭


def test_codex는_깃발이_아니라_쓴_것으로_본다(tmp_path):
    """codex 는 init 사건을 내지 않는다. 물려받을 글도 없다 (AGENTS.md 0바이트)."""
    그릇 = _그릇(tmp_path / "codex", 누구="codex", 깃발=[], init=False)
    됨, _ = 공용.자리가_깨끗했나(그릇)
    assert 됨, "codex 를 claude 기준으로 재면 늘 실패한다"


def test_누가_돌렸는지_없으면_실패다(tmp_path):
    """★ 「못 찾음」 은 통과가 아니다."""
    그릇 = tmp_path / "빈것"
    (그릇 / "작업").mkdir(parents=True)
    (그릇 / "시험.json").write_text("{}", encoding="utf-8")
    (그릇 / "대화.jsonl").write_text("", encoding="utf-8")
    됨, 까닭 = 공용.자리가_깨끗했나(그릇)
    assert not 됨 and 까닭


# ── ③ 우리 스킬 **밖의 것을 썼나** ─────────────────────────────────────────────────
썼으면_걸려야 = {
    "남의_스킬": {"호출": (("Skill", {"skill": "closing-a-section"}),)},
    "MCP_도구": {"호출": (("mcp__26fb4fae__read_file_content", {"id": "x"}),)},
    "웹": {"호출": (("WebFetch", {"url": "https://example.com"}),)},
    "서브에이전트": {"호출": (("Task", {"prompt": "해 줘"}),)},
    "codex_낯선_것": {"누구": "codex", "init": False, "코덱스것": ("mcp_tool_call",)},
}

써도_되는것 = {
    "우리_스킬": {"호출": (("Skill", {"skill": "youtube-voc:reading-voc-comments"}),)},
    "셸과_파일": {"호출": (("Bash", {"command": "ls"}), ("Read", {"file_path": "a.csv"}))},
    "codex_셸": {"누구": "codex", "init": False,
               "코덱스것": ("command_execution", "agent_message", "file_change", "todo_list")},
}


@pytest.mark.parametrize("이름", sorted(썼으면_걸려야))
def test_밖의_것을_쓰면_걸린다(tmp_path, 이름):
    그릇 = _그릇(tmp_path / 이름, **썼으면_걸려야[이름])
    됨, 까닭 = 공용.밖의것을_썼나(그릇)
    assert not 됨, "밖의 것을 쓴 것(%s)을 놓쳤다" % 이름
    assert 까닭


@pytest.mark.parametrize("이름", sorted(써도_되는것))
def test_안쪽_도구는_걸리지_않는다(tmp_path, 이름):
    그릇 = _그릇(tmp_path / 이름, **써도_되는것[이름])
    됨, 까닭 = 공용.밖의것을_썼나(그릇)
    assert 됨, "안쪽 도구인데 걸렸다 (%s) — 거짓 반려다: %s" % (이름, 까닭)


def test_시험이_무력하지_않다(tmp_path):
    """★ 걸려야 하는 것을 한꺼번에 줘도 통과하면 이 파일이 무력하다."""
    호출 = tuple(c for v in 썼으면_걸려야.values() for c in v.get("호출", ()))
    그릇 = _그릇(tmp_path / "모아서", 호출=호출, 깃발=[], 훅=True, mcp=("드라이브",))
    됨1, 까1 = 공용.밖의것을_썼나(그릇)
    됨2, 까2 = 공용.자리가_깨끗했나(그릇)
    assert not 됨1 and 까1, "밖의 것 %d 개를 줬는데도 통과했다" % len(호출)
    assert not 됨2 and 까2, "더러운 자리인데 통과했다"


# ── ④ 그릇 자신이 「어떻게 돌았나」 를 말한다 ───────────────────────────────────────
def test_격리_마치기가_깃발을_적는다():
    글 = (_여기 / "evals" / "스킬시험_돌리기.py").read_text(encoding="utf-8")
    assert "깃발=list(돌린깃발)" in 글, (
        "시험.json 에 깃발을 안 적으면 그릇이 「어떻게 돌았나」 를 말할 수 없다")


def test_한줄흐름과_시험이_같은_깃발을_쓴다():
    """★ 같은 값이 두 벌 있다 — 한 줄 돌리개는 **낱개로 꾸려도 돌아야** 해서 시험 하네스를
    불러올 수 없다. 그래서 사본을 두고 **검사기가 원본과 대 본다** (공통 규칙 6).
    """
    길 = (_뿌리 / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts" / "한줄_돌리기.py")
    sys.path.insert(0, str(길.parent))
    import 한줄_돌리기 as 흐름  # noqa: PLC0415
    assert tuple(흐름.깨끗한깃발) == tuple(공용.깨끗한깃발), (
        "한 줄 흐름과 시험의 깨끗한 깃발이 어긋났다 — %s / %s" % (흐름.깨끗한깃발, 공용.깨끗한깃발))
    assert 흐름.깨끗하게 is False, "평소에는 꺼져 있어야 한다 — 받는 사람 설정은 그 사람 것이다"
    글 = 길.read_text(encoding="utf-8")
    assert "--깨끗" in 글 and "명령 += list(깨끗한깃발)" in 글, "깃발을 정해만 두고 안 싣는다"


def test_규칙자리_면제는_그_규칙을_준_시험에서만_산다(tmp_path):
    """★ 깨끗한 깃발로 돌리면 전역 작업규칙을 **주지 않는다** — 그런데도 그 자리를 열었다면 밖이다.

    깃발 없이 돌린 옛 그릇에서는 그 자리가 **지시의 출처**였으므로 면제였다 (2026-10-20).
    면제를 통째로 두면 깨끗한 시험에서 밖을 보는 길이 하나 열린 채로 남는다.
    ★ 경로는 `tmp_path` 로 짓는다 — 코드에 절대경로를 박지 않는다 (`tests/test_no_old_paths.py`).
    """
    그밖 = tmp_path / "바깥" / "_공통_작업규칙" / "손대지말것_전역.txt"
    호출 = (("Bash", {"command": 'cat "%s"' % str(그밖).replace(chr(92), "/")}),)
    깨끗한것 = _그릇(tmp_path / "깨끗한시험", 호출=호출)
    됨, 까닭 = 공용.밖을_봤나(깨끗한것)
    assert not 됨 and 까닭, "규칙을 주지도 않았는데 그 자리를 연 것을 놓쳤다"
    옛것 = _그릇(tmp_path / "옛시험", 깃발=[], 호출=호출)
    됨, 까닭 = 공용.밖을_봤나(옛것)
    assert 됨, "옛 그릇에서는 지시의 출처였다 — 거짓 반려다: %s" % 까닭


def test_아이가_본것이_셀_수_있는_것을_돌려준다(tmp_path):
    그릇 = _그릇(tmp_path / "본것", mcp=("드라이브",), 훅=True,
              스킬=["youtube-voc:reading-voc-comments", "dataviz", "pdf"])
    본것 = 공용.아이가_본것(그릇)
    assert 본것["확인됨"] and 본것["훅돌았나"]
    assert 본것["스킬수"] == 3 and 본것["우리스킬"] == ["youtube-voc:reading-voc-comments"]
    assert 본것["남의스킬"] == ["dataviz", "pdf"] and 본것["MCP"] == ["드라이브"]
    assert 본것["모델"] == "claude-opus-5"
