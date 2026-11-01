# -*- coding: utf-8 -*-
"""「빠진 것을 찾는 도구」 둘이 살아 있고 정말 잡는가 (2026-10-29).

★ 왜 이 시험이 있나 — sky 물음 2026-10-29
    「왜 누락이 계속 생기는지 모르겠네요」
    「안해도되는 후보면 햇갈리게 왜 말을 해주는거세요? 하라고 얘기한거아니에요?」

  옛 꾸러미 114개를 전량 보니, 옛 저장소에는 관리 도구가 **일곱**이 있었고
  우리는 **다섯만** 원문으로 기록했다. 고르지 않은 둘이 하필
  **「빠진 것을 찾는 도구」** 였다 —

    문서_한말_검사.py   문서들이 같은 것을 **같은 말로** 적고 있나
    점검서_빠진것.py    sky 가 정한 것이 글에 **다 들어갔나**

  **빠진 것을 찾는 도구가 빠지면 그 뒤로는 빠진 것이 안 보인다.**
  그 둘의 규칙을 `tools/문서_한말_검사.py` · `tools/정한것_빠진것.py` 로 다시 지었다.

★ **가드는 돌리는 자리에 둔다.** 도구를 지어 놓고 아무도 안 돌리면 2주를 간다.
  그래서 이 시험이 **매번 실제로 돌린다** — 글이 어긋나면 시험이 깨진다.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
한말 = REPO / "tools" / "문서_한말_검사.py"
빠진것 = REPO / "tools" / "정한것_빠진것.py"
옛도구 = REPO / "docs" / "sources" / "옛관리도구"
옛결정 = REPO / "docs" / "sources" / "옛결정"


def _돌리기(도구: Path, *인자: str):
    r = subprocess.run([sys.executable, str(도구), *인자], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(REPO))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _불러오기(도구: Path):
    spec = importlib.util.spec_from_file_location(도구.stem, 도구)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ── 도구가 있고, 지금 글에서 통과하는가 ────────────────────────────

def test_두_도구가_있다():
    for p in (한말, 빠진것):
        assert p.is_file(), ("못 찾음: %s — 「빠진 것을 찾는 도구」 가 또 빠졌다.\n"
                             "  옛 저장소에서 이것이 빠져 누락이 안 보였다 (docs/옛꾸러미_대장.md)" % p)


def test_지금_글은_같은_말을_한다():
    """★ 이것이 이 시험의 알맹이다. **글이 어긋나면 깨진다.**

    깨졌다는 것은 ① 낡은 말이 정본 글에 남았거나 ② 이번에 정한 것이 어느 글에
    안 들어갔거나 ③ 판 번호가 어긋났거나 ④ 센 수와 적힌 수가 다르다는 뜻이다.
    넷 다 그냥 넘길 일이 아니다 — 고치고 다시 돌린다.
    """
    코드, 말 = _돌리기(한말)
    assert 코드 == 0, "문서_한말_검사 가 어긋난 곳을 찾았다 —\n%s" % 말[-2500:]
    assert "글이 다 같은 말을 합니다" in 말, 말[-800:]


def test_한말검사가_다섯_갈래를_다_본다():
    코드, 말 = _돌리기(한말)
    for 꼭 in ("① 센 수", "② 판 번호", "③ 더 이상 사실이 아닌 말",
             "④ 이번에 정한 것", "⑤ 같은 이름의 글"):
        assert 꼭 in 말, "「%s」 갈래가 출력에 없다 — 검사가 줄었나 보라" % 꼭


# ── 일부러 틀리게 — 정말 잡는가 ──────────────────────────────────

def test_낡은_말을_넣으면_잡는다(tmp_path):
    """★ 새 검사기는 일부러 틀리게 만들어 정말 잡는지 한 번 본다 (공통 규칙 4-3)."""
    쪽 = REPO / "docs" / "지금_어디인가.md"
    원래 = 쪽.read_bytes()
    try:
        쪽.write_bytes(원래 + "\n\n판독자가 받는 csv 는 74칸이다.\n".encode("utf-8"))
        코드, 말 = _돌리기(한말)
        assert 코드 == 1, "낡은 말을 넣었는데 통과했다 — 검사기가 안 잡는다\n%s" % 말[-1200:]
        assert "74칸" in 말, 말[-800:]
    finally:
        쪽.write_bytes(원래)
    코드, _ = _돌리기(한말)
    assert 코드 == 0, "되돌린 뒤에도 실패한다 — 되돌리기가 안 됐다"


def test_있어야_할_말을_지우면_잡는다():
    쪽 = REPO / "docs" / "옛꾸러미_대장.md"
    원래 = 쪽.read_text(encoding="utf-8")
    표 = "까닭 없이 무늬를 더하지 않는다"
    assert 표 in 원래, "못 찾음: %s — 지울 말이 없다" % 표
    try:
        쪽.write_text(원래.replace(표, "(지웠다)"), encoding="utf-8", newline="\n")
        코드, 말 = _돌리기(한말)
        assert 코드 == 1, "있어야 할 말을 지웠는데 통과했다\n%s" % 말[-1200:]
    finally:
        쪽.write_text(원래, encoding="utf-8", newline="\n")


def test_판_번호가_어긋나면_잡는다():
    """★ 2026-11-02 — 보는 글을 옮겼다. 전에는 `메일_붙일_것.md` 머리를 봤는데,
    그 글은 **2026-10-29 에 보낸 기록**이 되어 머리를 「그때 판은 2.0.12 였습니다」 (지난 일)로
    고쳤다. 지금 판을 대는 자리는 `docs/지금_어디인가.md` 머리 한 곳이다."""
    쪽 = REPO / "docs" / "지금_어디인가.md"
    원래 = 쪽.read_text(encoding="utf-8")
    표 = "> 적은 날 2026-11-02 · 판 "
    assert 표 in 원래, (
        "못 찾음: 머리의 「적은 날 … 판」 줄 — 그 줄이 없으면 한말 검사 ② 가 "
        "**볼 줄이 없어진다.** 날짜를 고쳤으면 이 시험의 `표` 도 같이 고친다")
    i = 원래.index(표)
    끝 = 원래.index("\n", i)
    try:
        쪽.write_text(원래[:i] + 표 + "9.9.9" + 원래[끝:], encoding="utf-8", newline="\n")
        코드, 말 = _돌리기(한말)
        assert 코드 == 1, "판 번호를 9.9.9 로 바꿨는데 통과했다\n%s" % 말[-1200:]
        assert "9.9.9" in 말, 말[-800:]
    finally:
        쪽.write_text(원래, encoding="utf-8", newline="\n")


def test_판_번호를_말하는_줄이_없으면_크게_실패한다():
    """★ 「못 찾음」 은 통과가 아니다 — 2026-11-02 에 **실제로 일어났다.**

    세 글의 머리를 「… 였습니다」 (지난 일)로 고쳤더니 ② 가 볼 줄이 **0개**가 되었는데도
    「머리에 적힌 판이 다 2.0.13 다」 라고 찍고 **통과**했다. 검사 안 한 것을 통과로 보여 줬다.
    """
    쪽 = REPO / "docs" / "지금_어디인가.md"
    원래 = 쪽.read_text(encoding="utf-8")
    표 = "> 적은 날 2026-11-02 · 판 "
    assert 표 in 원래, "못 찾음: 머리의 「적은 날 … 판」 줄"
    try:
        # 「적은 날」 을 지워 ② 가 볼 줄을 **0개**로 만든다 (그날 일어난 것과 같은 꼴)
        쪽.write_text(원래.replace(표, "> 그때 판은 "), encoding="utf-8", newline="\n")
        코드, 말 = _돌리기(한말)
        assert 코드 == 1, ("볼 줄이 0개인데 통과했다 — 검사 안 한 것을 통과로 보여 준다\n%s"
                         % 말[-1500:])
        assert "한 줄도 못 찾았습니다" in 말, 말[-1500:]
    finally:
        쪽.write_text(원래, encoding="utf-8", newline="\n")


def test_센_수와_다른_수를_적으면_잡는다():
    쪽 = REPO / "docs" / "지금_어디인가.md"
    원래 = 쪽.read_bytes()
    try:
        쪽.write_bytes(원래 + "\n\n아직 안 본 것 **77**개가 남았다.\n".encode("utf-8"))
        코드, 말 = _돌리기(한말)
        assert 코드 == 1, "센 수와 다른 수를 적었는데 통과했다\n%s" % 말[-1200:]
    finally:
        쪽.write_bytes(원래)


def test_셀_것을_못_찾으면_크게_실패한다(tmp_path, monkeypatch):
    """★ 「못 찾음」 을 「없음」 으로 돌려주지 않는다."""
    m = _불러오기(한말)
    monkeypatch.setattr(m, "REPO", tmp_path)
    with pytest.raises(SystemExit) as e:
        m._센수()
    assert "못 찾음" in str(e.value), str(e.value)
    with pytest.raises(SystemExit) as e:
        m._판()
    assert "못 찾음" in str(e.value), str(e.value)


def test_대화를_못_찾으면_크게_실패한다(tmp_path):
    """★ 빈 폴더를 가리키면 「빠진 것 없음」 이 아니라 종료코드 1 이어야 한다."""
    빈 = tmp_path / "없는대화"
    빈.mkdir()
    코드, 말 = _돌리기(빠진것, "--대화자리", str(빈))
    assert 코드 == 1, "대화를 못 찾았는데 0 으로 끝났다 — 검사 안 한 것을 숨긴다\n%s" % 말[-800:]
    assert "검사를 못 했습니다" in 말, 말[-800:]


def test_정한것_빠진것이_후보를_낸다(tmp_path):
    """가짜 대화 하나를 주면 그 말을 후보로 올리는가 — 실제 경로를 태운다."""
    자리 = tmp_path / "대화"
    자리.mkdir()
    말 = ("앞으로 보라색 꾸러미는 절대 쓰지 않기로 정합니다. 대신 노란색 꾸러미를 "
         "기본으로 바꾸고, 담당자 자리에서만 색칠하도록 규칙을 고쳐주세요.")
    쪽지 = {"timestamp": "2026-10-29T12:00:00Z",
           "message": {"role": "user", "content": [{"type": "text", "text": 말}]}}
    (자리 / "a.jsonl").write_text(json.dumps(쪽지, ensure_ascii=False) + "\n", encoding="utf-8")
    코드, 낸말 = _돌리기(빠진것, "--대화자리", str(자리))
    assert 코드 == 0, 낸말[-900:]
    assert "보라색" in 낸말, "넣어 준 말이 후보로 안 올라왔다 —\n%s" % 낸말[-900:]
    assert "판단하지 않습니다" in 낸말, "「후보만 낸다」 는 말이 빠졌다 (옛 도구의 규율이다)"


def test_사람이_쓴_말이_아닌_것은_안_올린다(tmp_path):
    """★ 돌려 보니 다른 세션이 보낸 쪽지가 「sky 의 말」 로 올라왔다 — 그래서 뺀다."""
    자리 = tmp_path / "대화"
    자리.mkdir()
    가짜 = ("Another Claude session sent a message: 보라색 꾸러미를 절대 쓰지 않기로 "
          "정하고 노란색으로 바꾸는 규칙을 고쳐주세요 담당자 자리에서만 색칠하도록")
    쪽지 = {"timestamp": "2026-10-29T12:00:00Z",
           "message": {"role": "user", "content": [{"type": "text", "text": 가짜}]}}
    (자리 / "a.jsonl").write_text(json.dumps(쪽지, ensure_ascii=False) + "\n", encoding="utf-8")
    코드, 낸말 = _돌리기(빠진것, "--대화자리", str(자리))
    assert 코드 == 0, 낸말[-900:]
    assert "보라색" not in 낸말, "사람이 쓴 말이 아닌 것을 후보로 올렸다\n%s" % 낸말[-900:]


# ── 원문이 지문과 함께 기록돼 있는가 ───────────────────────────────

def test_옛_관리도구_일곱이_지문과_함께_기록돼_있다():
    """★ 다섯만 기록해서 둘이 빠졌다. 이제 일곱이고, 그 수가 줄면 깨진다."""
    출처p = 옛도구 / "출처.json"
    assert 출처p.is_file(), "못 찾음: %s" % 출처p
    출처 = json.loads(출처p.read_text(encoding="utf-8"))
    파일 = 출처["파일"]
    assert len(파일) >= 7, ("옛 관리 도구 기록이 %d개다 — 일곱이어야 한다.\n"
                            "  `python tools/옛꾸러미_가져오기_총괄.py --기록만` 을 돌리십시오" % len(파일))
    for 꼭 in ("문서_한말_검사.py", "점검서_빠진것.py"):
        assert 꼭 in 파일, "%s 가 기록에 없다 — 또 빠졌다" % 꼭
        p = 옛도구 / 꼭
        assert p.is_file(), "못 찾음: %s" % p
        # 원본은 CRLF 였을 수 있어 지문이 다를 수 있다 — 두 꼴을 다 댄다
        본문 = p.read_bytes()
        지문들 = {hashlib.sha256(본문).hexdigest(),
                hashlib.sha256(본문.replace(b"\n", b"\r\n")).hexdigest()}
        assert 파일[꼭] in 지문들, "%s 의 지문이 기록과 다르다 — 원문이 바뀌었나 보라" % 꼭


def test_안하기로_한_것이_원문째로_기록돼_있다():
    출처p = 옛결정 / "출처.json"
    assert 출처p.is_file(), ("못 찾음: %s — 「안 하기로 한 것」 원문이 없다.\n"
                             "  이 글이 없어서 2026-10-29 에 이미 버린 안을 다시 들고 왔다" % 출처p)
    파일 = json.loads(출처p.read_text(encoding="utf-8"))["파일"]
    이름 = "91_결정사항_안하기로_한_것.md"
    assert 이름 in 파일, "%s 가 기록에 없다" % 이름
    p = 옛결정 / 이름
    assert p.is_file(), "못 찾음: %s" % p
    본문 = p.read_bytes()
    지문들 = {hashlib.sha256(본문).hexdigest(),
            hashlib.sha256(본문.replace(b"\n", b"\r\n")).hexdigest()}
    assert 파일[이름] in 지문들, "원문 지문이 기록과 다르다"
    # 축약하지 않았나 — 옛 글의 네 건이 다 들어 있는가
    글 = p.read_text(encoding="utf-8")
    for 꼭 in ("시험 실패 11개", "E-2 다주제 분할", "잔존 19건", "review_required"):
        assert 꼭 in 글, "원문에서 「%s」 가 빠졌다 — 축약했나 보라" % 꼭


def test_안하기로_한_것이_사는_자리가_원문을_가리킨다():
    """★ 기록만 두면 아무도 안 읽는다. 사는 자리가 그것을 가리켜야 한다."""
    p = REPO / "docs" / "decisions" / "0010-안-하기로-한-것.md"
    assert p.is_file(), "못 찾음: %s" % p
    글 = p.read_text(encoding="utf-8")
    assert "sources/옛결정/91_결정사항_안하기로_한_것.md" in 글, "원문을 가리키지 않는다"
    assert "여기에 그 내용을 옮겨 적지 않는다" in 글, "축약 금지 규칙을 적지 않았다"
    assert "없애면 의도를 무시하고 역행하는거 같아서요" in 글, "sky 말이 그대로 안 적혀 있다"
