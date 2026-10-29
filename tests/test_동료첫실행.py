# -*- coding: utf-8 -*-
"""동료가 **빈 컴퓨터에서 처음 돌릴 때** 받는 안내가 맞는가 (2026-10-29).

★ 왜 이 시험이 있나 — sky 2026-10-29 「네, ② 먼저 하고 ③은 나중에」

  상용화의 관문을 **② 작은 규모 실무**로 잡았고, 그 관문은 하나다 —
  **동료 한 명이 회사 컴퓨터에서 `--확인만` 을 한 번 돌리는 것.**
  그래서 그 첫 실행을 **빈 컴퓨터를 흉내 내어** 여기서 밟아 본다.

  실제로 밟아 보니 **거기서 막혔다.** 갖춤새가 모자란다고 멈추면서
  **꾸러미에 없는 파일 둘**을 보라고 했다 —

    · `dist/판/0_빈컴퓨터에서_무엇을_깔까.md`  → 그 글은 **푼 폴더 뿌리**에 있다.
                                               `dist/판/` 폴더는 꾸러미에 없다
    · `tools/키_환경변수에_넣기.ps1`           → **`.ps1` 이 꾸러미에 한 개도 없다**

  동료는 없는 파일을 찾다 멈춘다. 그래서 ⓐ 로 고쳤다 —
  경로를 박지 않고 `_깔까글()` 이 **찾아서** 찍고, 키 넣는 명령은
  꾸러미 안 `0_빈컴퓨터에서_무엇을_깔까.md` §③ 에 적었다.

★ **찍은 안내 경로가 꾸러미 안에 정말 있는지** 본다. 그것이 이 시험의 알맹이다 —
  코드가 「무엇을 보라」 고 말할 수 있으면, 그 무엇이 **있어야** 한다.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
판zip = REPO / "dist" / "판" / "Ver2_한줄흐름.zip"
돌리개안 = "Ver2_한줄흐름/plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py"
키이름 = ("YOUTUBE_API_KEY", "OPENAI_API_KEY")


def _빈컴퓨터_환경() -> dict:
    """키도 `claude`·`codex` 명령도 **없는** 환경 — 동료의 회사 컴퓨터를 흉내 낸다.

    ★ 키 **값은 읽지 않는다.** 그냥 넘겨주지 않을 뿐이다 (sky 규칙).

    ★ 2026-10-29 — 처음에는 윈도 폴더 절대경로를 기본값으로 적었다가
      `tests/test_no_old_paths.py` 에 걸렸다. **그 가드가 맞다** — 절대경로는
      `paths.py` 에서만 정한다. 예외 목록을 넓히지 않고(그건 물어야 하는 일이다)
      **환경에서 받아** 쓰고, 없으면 흉내를 낼 수 없으니 건너뛴다.
    """
    뿌리 = os.environ.get("SYSTEMROOT") or os.environ.get("SystemRoot")
    if not 뿌리:
        pytest.skip("SYSTEMROOT 가 없다 — 이 흉내는 윈도우에서만 낸다")
    파 = Path(sys.executable).parent
    길 = [str(파), str(파 / "Scripts"), str(Path(뿌리) / "System32"), 뿌리]
    env = {"PATH": os.pathsep.join(길), "SYSTEMROOT": 뿌리,
           "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", ""),
           "TEMP": os.environ.get("TEMP", ""), "TMP": os.environ.get("TMP", ""),
           "USERPROFILE": os.environ.get("USERPROFILE", ""),
           "PYTHONIOENCODING": "utf-8"}
    return {k: v for k, v in env.items() if v}


@pytest.fixture(scope="module")
def 첫실행(tmp_path_factory):
    if not 판zip.is_file():
        pytest.skip("dist/판 을 아직 안 묶었다 — `python tools/판_묶기.py` 뒤에 돈다")
    자리 = tmp_path_factory.mktemp("동료")
    with zipfile.ZipFile(판zip) as z:
        z.extractall(자리)
    판 = 자리 / "판1"
    판.mkdir()
    r = subprocess.run([sys.executable, str(자리 / 돌리개안), str(판), "--확인만"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(자리), env=_빈컴퓨터_환경())
    말 = (r.stdout or "") + (r.stderr or "")
    assert 말.strip(), "아무것도 안 찍었다 — 동료는 무엇을 할지 모른다"
    return {"자리": 자리, "뿌리": 자리 / "Ver2_한줄흐름", "코드": r.returncode, "말": 말}


def test_빈_컴퓨터에서는_멈추고_무엇이_모자란지_말한다(첫실행):
    """★ 조용히 통과하면 더 나쁘다 — 돈을 쓰기 전에 멈춰야 한다."""
    assert 첫실행["코드"] == 2, ("빈 컴퓨터에서 종료코드 %d 로 끝났다 — 2 여야 한다.\n%s"
                               % (첫실행["코드"], 첫실행["말"][-1500:]))
    말 = 첫실행["말"]
    for 꼭 in ("claude", "codex"):
        assert "`%s` 명령이 이 컴퓨터에 없습니다" % 꼭 in 말, "「%s 명령이 없다」 를 안 말했다" % 꼭
    for k in 키이름:
        assert k in 말, "키 이름 %s 를 안 말했다" % k
    assert "돈을 쓰기 전에" in 말, "돈 쓰기 전에 멈춘다는 말이 없다"


def test_키_값을_찍지_않는다(첫실행):
    """★ 키는 **이름만** 본다 (sky 규칙). 값이 섞여 나오면 그것이 가장 나쁘다."""
    말 = 첫실행["말"]
    for 꼴 in (r"sk-[A-Za-z0-9_-]{16,}", r"AIza[A-Za-z0-9_-]{20,}"):
        걸림 = re.findall(꼴, 말)
        assert not 걸림, "키 꼴이 출력에 섞였다 — %d건" % len(걸림)


def test_가리킨_안내가_꾸러미_안에_정말_있다(첫실행):
    """★ 이것이 알맹이다. 「무엇을 보라」 고 말했으면 그 무엇이 **있어야** 한다.

    2026-10-29 에 `dist/판/0_빈컴퓨터에서_무엇을_깔까.md` 와
    `tools/키_환경변수에_넣기.ps1` 을 가리켰고 **둘 다 꾸러미에 없었다.**
    """
    말, 자리, 뿌리 = 첫실행["말"], 첫실행["자리"], 첫실행["뿌리"]
    # 글 파일처럼 보이는 토막만 본다 (명령·절대경로는 뺀다)
    토막 = re.findall(r"[\w가-힣/\\.§_-]+\.(?:md|ps1|json|example)", 말)
    본것, 없는것 = [], []
    for t in sorted(set(토막)):
        쪽 = t.strip("`·").replace("\\", "/")
        if ":" in 쪽 or 쪽.startswith("/"):
            continue                      # 절대경로 (코덱스 파이썬 등) — 꾸러미 밖이 맞다
        본것.append(쪽)
        if not ((자리 / 쪽).exists() or (뿌리 / 쪽).exists()):
            없는것.append(쪽)
    assert 본것, "안내 파일을 하나도 안 가리켰다 — 동료는 무엇을 볼지 모른다"
    assert not 없는것, (
        "첫 실행이 **꾸러미에 없는 파일**을 보라고 한다 — %s"
        " (가리킨 것 전부: %s)"
        " 동료는 거기서 막힌다. 경로를 박지 말고 찾아서 찍으십시오." % (없는것, 본것))


def test_없는_ps1_을_가리키지_않는다(첫실행):
    """`.ps1` 은 꾸러미에 담지 않는다 (옛 저장소 경로가 기본값으로 박혀 있다).

    담지 않기로 했으면 **가리키지도 않아야** 한다.
    """
    말, 뿌리 = 첫실행["말"], 첫실행["뿌리"]
    담긴ps1 = list(뿌리.rglob("*.ps1"))
    assert not 담긴ps1, "꾸러미에 .ps1 이 담겼다 — %s" % [str(q) for q in 담긴ps1]
    assert ".ps1" not in 말, "꾸러미에 없는 `.ps1` 을 가리킨다 —\n%s" % 말[-1200:]
    assert "dist/판" not in 말 and "dist\\판" not in 말, \
        "우리 저장소의 `dist/판/` 을 가리킨다 — 받는 사람에게는 없는 자리다"


def test_안내가_키_넣는_명령을_적는다(첫실행):
    """★ 「환경변수로 넣으십시오」 만 적으면 동료는 **어떻게** 넣는지 모른다.

    `.ps1` 을 안 담는 대신 **명령을 안내에 적는다.** 적혀 있는지 본다.
    """
    안내 = 첫실행["뿌리"] / "0_빈컴퓨터에서_무엇을_깔까.md"
    assert 안내.is_file(), "못 찾음: %s" % 안내
    글 = 안내.read_text(encoding="utf-8")
    assert "setx YOUTUBE_API_KEY" in 글, "윈도우에서 키를 넣는 명령이 없다"
    assert "export YOUTUBE_API_KEY" in 글, "mac·linux 에서 키를 넣는 명령이 없다"
    assert "새로 켠 창" in 글, "환경변수가 새 창에만 들어온다는 말이 없다"
    # 값을 글에 적지 말라는 경고가 같이 있어야 한다
    assert "키를 이 꾸러미 안의 파일에 적지 마십시오" in 글, "키를 꾸러미에 적지 말라는 말이 없다"


def test_갖춤새가_모자라면_어림보다_깔_것을_먼저_말한다(첫실행):
    """★ 처음에는 「갖춤새가 모자라도 어림은 보여야 한다」 고 시험을 적었다 — **틀렸다.**

    돌려 보니 돌리개는 갖춤새에서 **먼저 멈춘다**(종료 2). 어림은 갖춘 뒤에 나온다.
    그게 맞는 동작이다 — 돌릴 수 없는 판의 값을 먼저 들이밀 까닭이 없고,
    동료가 할 일은 「무엇을 깔까」 하나다. 그래서 **시험을 고쳤다** (코드가 아니라).
    """
    말 = 첫실행["말"]
    assert "갖추지 못한 것이 있어 여기서 멈춥니다" in 말, "왜 멈췄는지 안 말했다"
    assert "깔 것과 키 넣는 법" in 말, "무엇을 깔지 가리키지 않았다"
    assert "같은 명령을 그대로 다시" in 말, "갖춘 뒤 무엇을 하라는 말이 없다"


def test_어림은_1차_밖_비용도_같이_말한다(첫실행):
    """★ 1차 값만 보여 주면 **돈을 작게 보이게** 한다 — 2·3차가 더 크다.

    갖춤새가 모자라면 어림이 안 찍히므로, 어림을 내는 자리를 **직접 불러** 본다.
    """
    import importlib.util
    import io
    import contextlib
    돌리개 = 첫실행["자리"] / 돌리개안
    spec = importlib.util.spec_from_file_location("한줄_꾸러미", 돌리개)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    그릇 = io.StringIO()
    with contextlib.redirect_stdout(그릇):
        m.어림_말하기({"영상": "5", "댓글": "50"})
    말 = 그릇.getvalue()
    assert "어림" in 말 and "$" in 말, "어림을 못 냈다 —\n%s" % 말
    assert "판독자 둘 · 감독자 둘 · 총괄을 띄우는 값이 **따로** 듭니다" in 말, \
        "1차 밖에 돈이 더 든다는 말이 없다 — 어림을 작게 보이게 하면 안 된다\n%s" % 말
    assert "어림입니다" in 말, "어림이라고 밝히지 않았다 (잰 값처럼 읽힌다)"
