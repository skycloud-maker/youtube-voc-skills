# -*- coding: utf-8 -*-
"""지켜보며 이어 돌리는 도구가 **헛돌지 않는가** (2026-10-30).

★ 왜 이 시험이 있나 — 이 도구는 **돈을 쓰는 것을 되풀이** 띄운다.

  2026-10-30 에 2판 통째 재현을 돌려 보니 판독자가 53회차 중 10회차만 하고
  스스로 넘겼다. 그래서 다시 띄워 이어 가야 하는데, **진행이 없을 때도 다시
  띄우면 같은 자리에서 돈만 쓴다.** 판독A 한 바퀴가 **139분 · $50.22**(실측)였으므로
  헛바퀴 한 번이 그만큼이다.

  그래서 재는 것은 하나다 — **늘어난 것이 없으면 한 바퀴만 돌고 멈추는가.**
  돈을 안 쓰고 재려고 돌리개 자리를 **가짜**로 갈아 끼우고, 가짜가 **몇 번 불렸는지**
  센다. 「멈췄다」 가 아니라 **「한 번만 불렸다」** 를 봐야 한다.
"""
from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
sys.path.insert(0, str(REPO / "tools"))


@pytest.fixture()
def 도구():
    m = importlib.import_module("통째돌림_지켜보기")
    return importlib.reload(m)


def _판차리기(자리: Path, 끝난=("1차",)) -> Path:
    자리.mkdir(parents=True, exist_ok=True)
    (자리 / "상태.json").write_text(
        json.dumps({"끝난단계": list(끝난), "소견": []}, ensure_ascii=False),
        encoding="utf-8", newline="\n")
    return 자리


def _가짜돌리개(자리: Path, 본문: str) -> Path:
    """돌리개 흉내 — 세는 자리(`센다.txt`)에 한 줄 적고, 본문이 하는 일을 한다."""
    쪽 = 자리 / "가짜돌리개.py"
    쪽.write_text(
        "import sys, json, io\n"
        "from pathlib import Path\n"
        "판 = Path(sys.argv[1])\n"
        "센다 = 판 / '센다.txt'\n"
        "센다.write_text((센다.read_text(encoding='utf-8') if 센다.is_file() else '') + 'x\\n',"
        " encoding='utf-8')\n"
        + 본문 + "\n",
        encoding="utf-8", newline="\n")
    return 쪽


def _불린수(판: Path) -> int:
    쪽 = 판 / "센다.txt"
    return len([c for c in 쪽.read_text(encoding="utf-8").splitlines() if c]) if 쪽.is_file() else 0


def test_진행을_무늬로_센다(도구, tmp_path):
    """이름을 박지 않는다 — claude·codex 가 결과 이름을 다르게 낸다."""
    판 = _판차리기(tmp_path / "판", ("1차", "2차준비"))
    (판 / "판독A" / "_판독패키지" / "_결과").mkdir(parents=True)
    for i in (1, 2, 3):
        (판 / "판독A" / "_판독패키지" / "_결과" / ("판독결과_full_%02d_claudecode.md" % i)).write_text("x", encoding="utf-8")
    (판 / "판독B").mkdir()
    (판 / "판독B" / "판독결과_full_01_codex.md").write_text("x", encoding="utf-8")
    (판 / "총괄" / "감독1").mkdir(parents=True)
    (판 / "총괄" / "감독1" / "감독결과_s13_01.md").write_text("x", encoding="utf-8")
    r = 도구.진행_세기(판)
    assert r["끝난단계"] == ["1차", "2차준비"]
    assert r["판독"] == 4, "판독결과를 %d개로 셌다 — 4개여야 한다 (폴더가 달라도 센다)" % r["판독"]
    assert r["감독"] == 1


def test_늘어난게_없으면_한_바퀴만_돌고_멈춘다(도구, tmp_path, capsys):
    """★ 이것이 알맹이다. 헛바퀴 한 번이 **139분 · $50.22**(실측)다."""
    판 = _판차리기(tmp_path / "판")
    도구.돌리개 = _가짜돌리개(tmp_path, "raise SystemExit(2)")   # 아무것도 안 늘린다
    코드 = 도구.지켜보기(판, 최대=5, 깨끗=False)
    assert 코드 == 1, "진행이 없는데 종료코드 %d 로 끝났다 — 1 이어야 한다" % 코드
    assert _불린수(판) == 1, ("돌리개를 %d 번 띄웠다 — **한 번**이어야 한다. "
                           "헛바퀴마다 돈이 나간다." % _불린수(판))
    말 = capsys.readouterr().out
    assert "늘어난 것이 없습니다" in 말, 말
    assert "돈만 씁니다" in 말, "돈이 나간다는 것을 안 말했다 — 사람이 그냥 다시 돌린다\n%s" % 말


def test_진행이_있으면_이어_돌린다(도구, tmp_path, capsys):
    """판독결과가 하나씩 늘면 계속 띄운다 — 실제 판독자가 그렇게 조금씩 넘긴다."""
    판 = _판차리기(tmp_path / "판")
    도구.돌리개 = _가짜돌리개(tmp_path, (
        "n = len(list(판.rglob('판독결과_*')))\n"
        "(판 / ('판독결과_full_%02d.md' % (n + 1))).write_text('x', encoding='utf-8')\n"
        "raise SystemExit(2)\n"))
    코드 = 도구.지켜보기(판, 최대=4, 깨끗=False)
    assert 코드 == 2, "한도를 다 쓰면 2 여야 한다 — %d" % 코드
    assert _불린수(판) == 4, "한도 4 인데 %d 번 띄웠다" % _불린수(판)
    assert 도구.진행_세기(판)["판독"] == 4
    assert "이어갑니다" in capsys.readouterr().out


def test_끝단계에_닿으면_끝낸다(도구, tmp_path, capsys):
    판 = _판차리기(tmp_path / "판")
    도구.돌리개 = _가짜돌리개(tmp_path, (
        "import json\n"
        "(판 / '상태.json').write_text(json.dumps("
        "{'끝난단계': ['1차','2차준비','2차판독','총괄검수1','3차준비','3차감독','3차마무리','아웃풋1'],"
        " '소견': []}, ensure_ascii=False), encoding='utf-8')\n"
        "raise SystemExit(0)\n"))
    코드 = 도구.지켜보기(판, 최대=9, 깨끗=False)
    assert 코드 == 0, 코드
    assert _불린수(판) == 1, "끝났는데 %d 번 띄웠다" % _불린수(판)
    말 = capsys.readouterr().out
    assert "아웃풋1` 까지 끝났습니다" in 말 and "--4차반영" in 말, \
        "끝난 뒤 무엇을 할지 안 말했다 — 사람이 멈춘다\n%s" % 말


def test_멈춤_파일이_있으면_한_번도_안_띄운다(도구, tmp_path, capsys):
    """★ sky 가 세울 수 있어야 한다 — 돌고 있는 것을 멈추는 길."""
    판 = _판차리기(tmp_path / "판")
    (판 / 도구.멈춤이름).write_text("", encoding="utf-8")
    도구.돌리개 = _가짜돌리개(tmp_path, "raise SystemExit(2)")
    코드 = 도구.지켜보기(판, 최대=5, 깨끗=False)
    assert 코드 == 0 and _불린수(판) == 0, "멈춤 파일이 있는데 %d 번 띄웠다" % _불린수(판)
    assert "사람이 세웠습니다" in capsys.readouterr().out


def test_진짜_종료코드를_기록에_적는다(도구, tmp_path):
    """★ 2026-10-30 — 셸에서 `코드=$?` 로 적으려다 **한글 변수 이름**이라 실패해
    기록에 `$코드` 가 글자 그대로 남았다. 진짜 종료코드를 잃었다. 다시 그러지 않게 본다.
    """
    판 = _판차리기(tmp_path / "판")
    도구.돌리개 = _가짜돌리개(tmp_path, "print('무언가 찍는다'); raise SystemExit(7)")
    코드 = 도구.한바퀴(판, False, 판 / "돌린기록.txt")
    assert 코드 == 7, "진짜 종료코드를 못 받았다 — %d" % 코드
    글 = io.open(판 / "돌린기록.txt", encoding="utf-8").read()
    assert "진짜 종료코드 7" in 글, "기록에 종료코드 7 이 없다 —\n%s" % 글
    assert "$" not in 글.split("진짜 종료코드")[1][:10], "종료코드 자리에 글자 그대로 남았다"
    assert "무언가 찍는다" in 글, "돌리개가 찍은 것이 기록에 안 들어갔다"


def test_상태가_없는_자리는_거절한다(도구, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["x", str(tmp_path / "없는판")])
    with pytest.raises(SystemExit) as e:
        도구.main()
    assert "상태.json 이 없습니다" in str(e.value)


def test_한도가_0이면_거절한다(도구, tmp_path, monkeypatch):
    판 = _판차리기(tmp_path / "판")
    monkeypatch.setattr(sys, "argv", ["x", str(판), "--최대", "0"])
    with pytest.raises(SystemExit) as e:
        도구.main()
    assert "1 이상" in str(e.value)
