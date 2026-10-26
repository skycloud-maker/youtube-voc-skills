# -*- coding: utf-8 -*-
r"""실제 AI 시험의 **채점기**가 제대로 가리는가 — 「밖을 봤나」 (2026-10-26).

★ 왜 이 파일이 생겼나
  채점기 자체를 지키는 기계 시험이 **하나도 없었다.** 그런데 이 채점기는 시험의 합격·불합격을
  정하는 자리다. 2026-10-26 대시보드 시험 5회차에서 **거짓 반려**가 나왔다 —
  AI 가 자기 그릇에 써 넣은 Node 스크립트의 정규식
  스크립트 태그를 긁는 정규식이 소문자화 뒤 역슬래시-s 를 두 번 품게 되고,
  채점기의 「Git Bash 경로(/c/…) 를 드라이브 꼴로」 바꿈이 `\s\` 를 `s:\` 로 만들어
  **「s: 뒤에 역슬래시」 꼴의 가짜 경로**가 생겼다. 그 한 줄 때문에 7/7 이 6/7 로 떨어졌다.

★ 거짓 반려를 고치면서 **느슨해지지 않았는지**를 여기서 지킨다 —
  진짜 밖(옛 저장소 · 이 저장소 · 다른 시험 그릇)은 **여전히 걸려야** 한다.
  그래서 통과해야 하는 것과 걸려야 하는 것을 **둘 다** 시험한다.
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
import 스킬시험_돌리기 as 채점  # noqa: E402
from paths import EVAL_ROOT, PLUGIN, REPO  # noqa: E402
from paths import 옛저장소 as _옛저장소  # noqa: E402


def _슬래시(p) -> str:
    return str(p).replace("\\", "/")


def _깃배시(p) -> str:
    """드라이브 꼴을 Git Bash 꼴(맨 앞이 슬래시 + 드라이브 글자)로 바꾼다."""
    s = _슬래시(p)
    return "/" + s[0].lower() + s[2:] if len(s) > 2 and s[1] == ":" else s


def _그릇(자리: Path, 명령들: list[str]) -> Path:
    """채점기가 읽는 최소한의 그릇 — 시험.json(돌린자리) + 대화.jsonl(도구 호출)."""
    자리.mkdir(parents=True, exist_ok=True)
    작업 = 자리 / "작업"
    작업.mkdir(exist_ok=True)
    (자리 / "시험.json").write_text(
        json.dumps({"돌린자리": str(작업)}, ensure_ascii=False), encoding="utf-8")
    줄들 = []
    for c in 명령들:
        줄들.append(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Bash",
                                     "input": {"command": c}}]},
        }, ensure_ascii=False))
    (자리 / "대화.jsonl").write_text("\n".join(줄들) + "\n", encoding="utf-8")
    return 자리


# ── 걸려야 하는 것 — 진짜 밖을 본 명령 ────────────────────────────────────────
# ★ 자리는 **paths.py 에서만** 가져온다 (공통 규칙 6 · 코드에 절대경로를 박지 않는다)
걸려야 = {
    "옛_저장소": 'cat "%s/s15_master/raw_voc.csv"' % _슬래시(_옛저장소),
    # ★ 저장소 자체도 밖이다 — 스킬만 주고 돌리는 시험이므로 저장소를 뒤지면 안 된다
    "이_저장소": 'ls "%s/tests/baseline"' % _슬래시(REPO),
    "다른_시험_그릇": 'cp "%s/다른시험_1/작업/x.html" .' % _슬래시(EVAL_ROOT),
    # ★ Git Bash 꼴도 걸려야 한다 (이것을 못 읽어 옛 사고가 있었다 — 채점기 주석 참고)
    "깃배시_꼴": 'cat %s/s15_master/raw_voc.csv' % _깃배시(_옛저장소),
}

# ── 통과해야 하는 것 ────────────────────────────────────────────────────────
통과해야 = {
    "자기_그릇": 'ls -la "{작업}"',
    "플러그인": 'python "%s/skills/showing-voc-dashboard/scripts/대시보드_HTML_만들기.py" a b' % str(PLUGIN).replace("\\", "/"),
    # ★ 2026-10-26 거짓 반려의 그 자리 — 자기 그릇에 쓴 스크립트 안의 정규식
    "스크립트_속_정규식": ('cd "{작업}" && cat > 확인.cjs <<\'JS\'\n'
                    'const blocks = [...s.matchAll(/<script[^>]*>([\\s\\S]*?)<\\/script>/g)];\n'
                    'JS\nnode 확인.cjs'),
    # 정규식 조각이 홀로 있어도 경로가 아니다
    "정규식_조각만": 'grep -oE "https?://[^\\s\\"]+" *.html',
}


@pytest.mark.parametrize("이름", sorted(걸려야))
def test_진짜_밖은_걸린다(tmp_path, 이름):
    그릇 = _그릇(tmp_path / 이름, [걸려야[이름]])
    됨, 까닭 = 채점.밖을_봤나(그릇)
    assert not 됨, "밖을 본 명령(%s)을 놓쳤다 — %s" % (이름, 걸려야[이름])
    assert 까닭, "걸렸다면 무엇이 걸렸는지 적어야 한다"


@pytest.mark.parametrize("이름", sorted(통과해야))
def test_안쪽과_정규식은_걸리지_않는다(tmp_path, 이름):
    그릇 = tmp_path / 이름
    작업 = 그릇 / "작업"
    명령 = 통과해야[이름].replace("{작업}", str(작업).replace("\\", "/"))
    _그릇(그릇, [명령])
    됨, 까닭 = 채점.밖을_봤나(그릇)
    assert 됨, "안쪽/정규식인데 걸렸다 (%s) — 거짓 반려다: %s" % (이름, 까닭)


def test_시험이_무력하지_않다(tmp_path):
    """★ 「걸려야 하는 것」 이 정말로 걸리는지 먼저 본다 — 하나도 안 걸리면 이 파일이 무력하다."""
    그릇 = _그릇(tmp_path / "모아서", list(걸려야.values()))
    됨, 까닭 = 채점.밖을_봤나(그릇)
    assert not 됨 and 까닭, "밖을 본 명령 %d개를 한꺼번에 줬는데도 통과했다" % len(걸려야)
