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
import os
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
# ★ 2026-11-06 — 저장소 `tools/` 에서 꾸러미 안(총괄 스킬 `scripts/`)으로 옮겼다 (큰 판 길)
sys.path.insert(0, str(REPO / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts"))


@pytest.fixture()
def 도구():
    m = importlib.import_module("통째돌림_지켜보기")
    return importlib.reload(m)


def _판차리기(자리: Path, 끝난=("1차",), 승인=True) -> Path:
    자리.mkdir(parents=True, exist_ok=True)
    (자리 / "상태.json").write_text(
        json.dumps({"끝난단계": list(끝난), "소견": [], "승인": 승인}, ensure_ascii=False),
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


def test_AI기록을_바퀴마다_챙겨_둔다(도구, tmp_path):
    """★ 2026-10-30 — 돌리개가 `기록/판독A.jsonl` 을 **바퀴마다 덮는다.**

    다섯 바퀴를 돌고도 비용 기록이 한 바퀴 분량만 남아 「얼마 썼나」 를 못 셌다.
    240분 제한에 걸려 터진 바퀴는 아예 안 적힌다. 그래서 덮이기 전에 챙기는지 본다.
    """
    판 = _판차리기(tmp_path / "판")
    기록 = 판 / "기록"
    기록.mkdir()
    쪽 = 기록 / "판독A.jsonl"
    쪽.write_text("첫 바퀴", encoding="utf-8")

    assert 도구.기록_간수(판) == 1, "첫 바퀴 기록을 안 챙겼다"
    assert 도구.기록_간수(판) == 0, "같은 것을 두 번 챙겼다 — 바퀴마다 쌓이면 디스크가 찬다"

    import os
    import time
    쪽.write_text("둘째 바퀴 — 덮였다", encoding="utf-8")
    새때 = time.time() + 3600
    os.utime(쪽, (새때, 새때))
    assert 도구.기록_간수(판) == 1, "덮인 뒤의 기록을 안 챙겼다 — 첫 바퀴 것만 남는다"

    보관 = sorted(q.name for q in (기록 / 도구.기록보관).glob("*.jsonl"))
    assert len(보관) == 2, "보관된 것이 %s — 두 벌이어야 한다" % 보관
    글 = sorted((기록 / 도구.기록보관 / n).read_text(encoding="utf-8") for n in 보관)
    assert 글 == ["둘째 바퀴 — 덮였다", "첫 바퀴"], 글


def test_기록폴더가_없어도_안_터진다(도구, tmp_path):
    """1차만 끝난 자리에는 `기록/` 이 없을 수 있다."""
    판 = _판차리기(tmp_path / "판")
    assert 도구.기록_간수(판) == 0


# ── 2026-11-06 · 꾸러미 안으로 옮기며 더한 시험 (큰 판 길) ─────────────────────────

def test_돌리개를_같은_폴더에서_찾는다(도구):
    """실무자 컴퓨터에는 저장소가 없다 — 꾸러미를 푼 자리에서도 돌리개를 찾아야 한다."""
    assert 도구.돌리개.name == "한줄_돌리기.py"
    assert 도구.돌리개.parent == Path(도구.__file__).resolve().parent
    assert 도구.돌리개.is_file(), "옆에 돌리개가 없다 — %s" % 도구.돌리개


def test_승인을_스스로_붙이지_않는다(도구, tmp_path):
    """★ 옮기기 전에는 `--승인` 을 붙여 띄웠다. 꾸러미에서 그대로 두면 사람이 어림을
    한 번도 안 보고 돈이 나갈 수 있다. 돌리개가 받은 인자를 적게 해서 본다."""
    판 = _판차리기(tmp_path / "판")
    도구.돌리개 = _가짜돌리개(tmp_path, "(판 / '인자.txt').write_text(' '.join(sys.argv[1:]), encoding='utf-8')")
    도구.한바퀴(판, True, 판 / "돌린기록.txt")
    인자 = (판 / "인자.txt").read_text(encoding="utf-8")
    assert "--승인" not in 인자, "돌리개에 --승인 을 붙였다 — %s" % 인자
    assert "--깨끗" in 인자, "--깨끗 을 넘기지 않았다 — %s" % 인자


@pytest.mark.parametrize("상태글", [
    {"끝난단계": ["1차"], "소견": []},                      # 승인 기록 없음
    {"끝난단계": ["1차"], "소견": [], "승인": False},
    "{ 깨진 json",                                          # 못 읽음은 통과가 아니다
])
def test_사람이_승인한_기록이_없으면_한_번도_안_띄운다(도구, tmp_path, monkeypatch, 상태글):
    판 = tmp_path / "판"
    판.mkdir()
    (판 / "상태.json").write_text(상태글 if isinstance(상태글, str)
                                 else json.dumps(상태글, ensure_ascii=False), encoding="utf-8")
    도구.돌리개 = _가짜돌리개(tmp_path, "raise SystemExit(0)")
    monkeypatch.setattr(sys, "argv", ["x", str(판)])
    with pytest.raises(SystemExit) as e:
        도구.main()
    assert "승인한 기록이 없습니다" in str(e.value), e.value
    assert _불린수(판) == 0, "승인 기록이 없는데 돌리개를 띄웠다"


# ── 진짜 돌리개 + 가짜 판독자 ───────────────────────────────────────────────────
#   판독자는 실제로 **한 창에 몇 회차만 하고 스스로 넘긴다** (2026-10-30 실측 — 53회차 중 10).
#   가짜 판독자는 부를 때마다 판독결과를 하나 쓰고, **둘째 부름에서야** 번들을 낸다.
#   그러면 진짜 돌리개는 첫 부름 뒤에 「번들 0개」 로 멈추고(종료 1), 지켜보기가 다시 띄운다.
#   판독 폴더가 아닌 자리(총괄·감독)에서 불리면 아무것도 안 쓰고 실패한다 —
#   그 뒤로는 늘어날 것이 없으니 지켜보기가 **한 바퀴만 더 돌고 멈춰야** 한다.

_가짜판독 = r'''
import sys, json
from pathlib import Path
누구 = sys.argv[1]
sys.stdin.read()
여기 = Path.cwd()
with open(여기.parent / "불린판독.txt", "a", encoding="utf-8") as f:
    f.write("%s %s\n" % (여기.name, 누구))
if not 여기.name.startswith("판독"):
    print("판독 자리가 아니다", file=sys.stderr)
    raise SystemExit(3)
결과 = 여기 / "_판독패키지" / "_결과"
결과.mkdir(parents=True, exist_ok=True)
n = len(list(결과.glob("판독결과_*"))) + 1
(결과 / ("판독결과_full_%02d_%s.md" % (n, 누구))).write_text("x", encoding="utf-8")
if n >= 2:
    (결과 / "fake_bundle").mkdir(exist_ok=True)
    (결과 / "fake_bundle" / "raw_voc.csv").write_text("atomic_id\n", encoding="utf-8")
    말 = "다 했습니다"
else:
    말 = "full_%02d 까지 했습니다. 새 창에서 이어가 주십시오." % n
if 누구 == "claude":
    print(json.dumps({"type": "result", "result": 말}, ensure_ascii=False))
else:
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": 말}},
                     ensure_ascii=False))
'''


@pytest.mark.skipif(sys.platform != "win32", reason="가짜 명령을 .cmd 로 만든다")
def test_진짜_돌리개가_판독자가_넘길_때마다_이어_돌고_막히면_멈춘다(도구, tmp_path_factory, monkeypatch, capsys):
    가짜 = tmp_path_factory.mktemp("fakebin")          # .cmd 안의 경로는 ASCII 로 둔다
    (가짜 / "fake_reader.py").write_text(_가짜판독, encoding="utf-8")
    for 명령 in ("claude", "codex"):
        (가짜 / (명령 + ".cmd")).write_text(
            '@"%s" "%s" %s %%*\r\n' % (sys.executable, 가짜 / "fake_reader.py", 명령), encoding="ascii")
    monkeypatch.setenv("PATH", str(가짜) + os.pathsep + os.environ.get("PATH", ""))

    판 = tmp_path_factory.mktemp("pan")
    (판 / "상태.json").write_text(json.dumps(
        {"끝난단계": ["1차", "2차준비"], "소견": [], "승인": True,
         "조건": {"검색어": "시험", "영상": "1", "댓글": "5", "이름": "시험판"}},
        ensure_ascii=False), encoding="utf-8")
    (판 / "판독A").mkdir()
    (판 / "판독B").mkdir()

    코드 = 도구.지켜보기(판, 최대=10, 깨끗=False)
    말 = capsys.readouterr().out
    기록글 = (판 / "돌린기록.txt").read_text(encoding="utf-8")

    불린 = (판 / "불린판독.txt").read_text(encoding="utf-8").split()
    판독불림 = [불린[i] for i in range(0, len(불린), 2)]
    assert 판독불림.count("판독A") == 2 and 판독불림.count("판독B") == 2, (
        "판독자를 넘길 때마다 한 번씩 더 띄워야 한다 — %s\n%s" % (판독불림, 말))
    끝난 = 도구.진행_세기(판)["끝난단계"]
    assert "2차판독" in 끝난, "판독 둘이 번들을 냈는데 2차판독이 안 끝났다 — %s\n%s" % (끝난, 기록글[-3000:])
    assert 코드 == 1, "판독 뒤에 막혔으면 1 이어야 한다 — %d\n%s" % (코드, 말)
    assert "늘어난 것이 없습니다" in 말, 말
    assert "--승인" not in 기록글, "돌리개에 --승인 이 넘어갔다"
    assert "새 창에서 이어가" in 기록글, "판독자가 넘긴 말이 돌린기록에 없다 — 사람이 까닭을 못 본다"
    # 바퀴마다 덮이는 AI 기록을 챙겼나 — 판독A 두 번 · 판독B 두 번이 따로 남아야 한다
    보관 = list((판 / "기록" / 도구.기록보관).glob("*.jsonl"))
    assert len(보관) >= 2, "AI 기록을 바퀴마다 챙기지 않았다 — %s" % 보관
