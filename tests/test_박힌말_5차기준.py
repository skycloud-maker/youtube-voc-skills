# -*- coding: utf-8 -*-
"""옛 관리 도구 둘(박힌말_검사 · 5차기준_검사)의 규칙을 시험으로 옮겼다 (섹션 6 · sky 2026-09-21 「새 방식으로 대신한다」).

★ 규칙은 **한 벌** — 기록해 둔 옛 도구 원문(`docs/sources/옛관리도구/`)에서 무늬 · 봐주기 · 알고두는것을 그대로 불러 쓴다.
  여기에 무늬를 베껴 적지 않는다 (같은 것이 두 벌이 되지 않게).
★ 보는 범위도 손으로 적지 않는다 — 옛 도구가 겪은 것: 「목록을 손으로 유지하면 반드시 빠진다 (이미 다섯이 빠진 적이 있다)」.
  실무자 · AI 에게 가는 도구는 꾸러미 목록(`shared/lib/꾸러미.py`)에서, 글은 스킬 폴더에서 뽑는다.
  원래 범위(늘 쓰는 글 = 프롬프트 · 60 · 61 가이드 · 배포 안내, 그리고 꾸러미에 실리는 도구)에 SKILL.md 를 더했다 —
  이제 SKILL.md 가 AI 에게 가는 지시문이다. 기준서(standards)는 원래도 보지 않았다 (제품군을 나열하는 것이 제 일이다).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "plugin"
옛자리 = REPO / "docs" / "sources" / "옛관리도구"
sys.path.insert(0, str(PLUGIN / "shared" / "lib"))
import 꾸러미  # noqa: E402


def _불러오기(이름: str):
    spec = importlib.util.spec_from_file_location("옛_" + 이름, 옛자리 / (이름 + ".py"))
    m = importlib.util.module_from_spec(spec)
    옛argv, sys.argv = sys.argv, [str(옛자리 / (이름 + ".py"))]
    try:
        spec.loader.exec_module(m)
    finally:
        sys.argv = 옛argv
    return m


박힌말 = _불러오기("박힌말_검사")
오차 = _불러오기("5차기준_검사")


def 나가는_글() -> list[Path]:
    글 = sorted(PLUGIN.glob("skills/*/SKILL.md")) + sorted(PLUGIN.glob("skills/*/references/0_붙여넣을_*.md"))
    글 += [PLUGIN / "shared" / "guides" / n for n in ("60_2차판독_실무자_사용가이드.md", "61_3차감독_실무자_사용가이드.md")]
    return 글


def 나가는_도구() -> list[Path]:
    return sorted({PLUGIN / "shared" / "tools" / n for n in 꾸러미._판독도구 + 꾸러미._감독도구})


def test_볼_것을_찾았다():
    # ★ 못 찾음은 통과가 아니다
    글, 도구 = 나가는_글(), 나가는_도구()
    없음 = [str(p) for p in 글 + 도구 if not p.is_file()]
    assert not 없음, 없음
    assert len(글) >= 7 and len(도구) >= 20, (len(글), len(도구))


def test_나가는_글과_도구에_이번_데이터에만_맞는_말이_없다():
    걸림 = [(p.relative_to(REPO).as_posix(), *x) for p in 나가는_글() + 나가는_도구() for x in 박힌말.보기(p)]
    assert not 걸림, "박힌 말 (옛 박힌말_검사 규칙):\n" + "\n".join(map(str, 걸림[:20]))


def test_나가는_도구에_이_컴퓨터_경로가_없다():
    걸림 = []
    for p in 나가는_도구():
        if p.name in 박힌말.경로봐줌:
            continue
        for n, 줄 in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if 줄.lstrip().startswith("#"):
                continue
            for 무늬, 왜 in 박힌말.박힌경로:
                if 무늬 in 줄:
                    걸림.append((p.name, n, 줄.strip()[:60], 왜))
                    break
    assert not 걸림, 걸림[:10]


def _5차_볼파일() -> list[Path]:
    out = []
    for p in PLUGIN.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in (".md", ".py"):
            continue
        rel = p.relative_to(PLUGIN).parts
        if "engine" == rel[0] or 오차.안봄_폴더 & set(rel) or p.name in 오차.안봄_파일:
            continue
        out.append(p)
    return out


def _5차_걸림(파일들) -> list:
    걸림 = []
    for p in 파일들:
        for n, 줄 in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if 오차.금지문장.search(줄):
                continue
            for 무늬, 왜, _ in 오차.규칙:
                if 무늬.search(줄):
                    걸림.append((p.relative_to(REPO).as_posix() if REPO in p.parents else p.name, n, 줄.strip()[:70], 왜))
    return 걸림


def test_5차기준_감독자는_판정까지_차수_사이는_총괄():
    파일들 = _5차_볼파일()
    assert len(파일들) > 50, len(파일들)
    걸림 = _5차_걸림(파일들)
    assert not 걸림, "5차 기준을 어긴 곳:\n" + "\n".join(map(str, 걸림[:20]))


def test_5차기준_감독_꾸러미에_총괄_도구가_없다():
    for 이름 in 오차.감독자꾸러미_금지:
        assert 이름 not in 꾸러미._감독도구, 이름


# ── ★ 일부러 틀리게 — 검사가 정말 잡는가 ─────────────────────────────
@pytest.mark.parametrize("줄, 무엇", [
    ("판독 대상은 1,570행입니다", "행 수를 박음"),
    ("로봇청소기 댓글만 봅니다", "제품군을 박음"),
    ("자사 제품만 라벨을 붙입니다", "자사/남의 것을 가름"),
])
def test_박힌말을_일부러_넣으면_잡는다(tmp_path, 줄, 무엇):
    p = tmp_path / "시험.md"
    p.write_text("# 지시\n\n\n%s\n\n\n" % 줄, encoding="utf-8")
    assert [x for x in 박힌말.보기(p) if x[0] == 무엇], 박힌말.보기(p)


def test_도구에_결과폴더를_박으면_잡는다(tmp_path):
    p = tmp_path / "시험.py"
    p.write_text("x = 1\n\n\nopen('master_final/raw_voc.csv')\n\n\n", encoding="utf-8")
    assert 박힌말.보기(p), "도구에 박힌 작업 폴더 이름을 못 잡았다"


def test_5차기준을_일부러_어기면_잡는다(tmp_path):
    p = tmp_path / "시험.md"
    p.write_text("감독이 끝나면\n    python build_master.py\n두 감독자를 합칩니다\n", encoding="utf-8")
    assert len(_5차_걸림([p])) == 2, _5차_걸림([p])
    p.write_text("❌ 두 감독자를 합치지 않는다\n", encoding="utf-8")       # 금지 문장은 어긴 것이 아니다
    assert not _5차_걸림([p])
