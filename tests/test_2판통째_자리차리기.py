# -*- coding: utf-8 -*-
"""2판을 통째로 다시 돌릴 **들어가는 자리**가 맞는가 (2026-10-30).

★ 왜 이 시험이 있나 — sky 2026-10-30 「3번 돌려주세요, 2판 통째로」

  $460 이 드는 실행의 **입구**다. 입구가 어긋나면 돈을 쓰고 나서야 안다 —
  돌리개가 1차 번들을 **못 찾으면** 2차준비에서 멈추고, 번들을 엉뚱한 자리에
  놓으면 **옛 1차가 아닌 것**으로 돌아 버린다. 둘 다 돈을 쓴 뒤에 드러난다.

  그래서 **돈 안 드는 `--확인만` 으로 실제 돌리개에게 물어본다** — 1차를 건너뛰는가,
  갖춤새가 됐다고 하는가. 자리 이름을 시험에 두 벌로 적지 않는다(공통 규칙 6):
  **돌리개가 쓰는 길이 맞는지는 돌리개가 대답한다.**
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
REPO = _여기.parent
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "plugin" / "shared"))

돌리개 = REPO / "plugin" / "skills" / "coordinating-voc-pipeline" / "scripts" / "한줄_돌리기.py"


@pytest.fixture(scope="module")
def 도구():
    import importlib
    return importlib.import_module("2판통째_자리차리기")


@pytest.fixture(scope="module")
def 차린자리(도구, tmp_path_factory):
    if not Path(도구._기본번들).is_file():
        pytest.skip("옛 2판 1차 번들이 없다 — %s" % 도구._기본번들)
    판 = tmp_path_factory.mktemp("2판통째") / "판"
    r = 도구.차리기(판, Path(도구._기본번들), Path(도구._기본메타), False)
    return {"판": 판, "결과": r, "도구": 도구}


def test_옛_1차_결과를_그대로_앉혔다(차린자리):
    """★ 「앉혔다」 가 아니라 **몇 행인가**를 본다. 빈 파일도 「있다」 는 통과한다."""
    쟨것 = 차린자리["결과"]["쟨것"]
    assert 쟨것["행"] == 6336, "옛 2판 1차는 6,336행이다 — %d행을 앉혔다" % 쟨것["행"]
    assert 쟨것["영상"] == 65, "영상 65개여야 한다 — %d개" % 쟨것["영상"]
    assert 쟨것["칸"] == 74, "1차 번들 raw_voc 는 74칸이다 — %d칸" % 쟨것["칸"]
    놓인것 = Path(차린자리["결과"]["번들자리"])
    assert 놓인것.is_file(), "못 찾음: %s" % 놓인것
    assert 놓인것.stat().st_size == Path(차린자리["도구"]._기본번들).stat().st_size, \
        "앉힌 번들의 크기가 원본과 다르다 — 복사가 온전하지 않다"


def test_영상메타를_1차_결과_옆에_놓았다(차린자리):
    """★ 옆에 없으면 판독자는 **꾸러미 견본**을 보고 판단한다 — 2판 재현이 아니게 된다.

    (`데이터_넣기.영상메타_갈아끼우기` 는 1차 결과 **옆**만 본다.)
    """
    메타 = Path(차린자리["결과"]["번들자리"]).parent / "7_영상메타.csv"
    assert 메타.is_file(), "1차 결과 옆에 7_영상메타.csv 가 없다 — %s" % 메타
    assert "놓았습니다" in 차린자리["결과"]["메타말"], 차린자리["결과"]["메타말"]


def test_옛_최종을_먼저_세어_둔다(차린자리):
    """끝나고 댈 **분모**다. 지금 못 찾으면 돌린 뒤에 알게 된다."""
    옛것 = 차린자리["결과"]["옛것"]
    assert 옛것["행"] == 6846 and 옛것["칸"] == 89, \
        "옛 2판 최종은 6,846행 · 89칸이다 — 행 %d · 칸 %d" % (옛것["행"], 옛것["칸"])


def test_행이_늘어나는_것을_알고_있다(차린자리):
    """★ 1차 6,336 → 최종 6,846. **510행이 뒤에서 늘어난다** (3차 D 분리 · 4차 반영).

    이 숫자를 모르고 돌리면 「행이 안 맞는다」 를 결함으로 읽는다.
    """
    늘어남 = 차린자리["결과"]["옛것"]["행"] - 차린자리["결과"]["쟨것"]["행"]
    assert 늘어남 == 510, "늘어나는 행이 510이 아니다 — %d" % 늘어남


def test_상태에_1차가_끝났다고_적었다(차린자리):
    상태 = json.loads((차린자리["판"] / "상태.json").read_text(encoding="utf-8"))
    assert 상태["끝난단계"] == ["1차"], 상태["끝난단계"]
    assert 상태["조건"]["이름"] == 차린자리["도구"].이름
    assert "다시 모으지 않았습니다" in 상태["기록"]["1차"], \
        "1차를 왜 다시 안 돌렸는지 기록에 없다 — 이어받는 사람이 모른다"
    assert not 상태.get("승인"), "자리만 차리면서 **승인까지** 적어 두면 안 된다 (돈 관문이 사라진다)"


def test_돌던_판을_말없이_덮지_않는다(차린자리, 도구):
    """★ 덮으면 **돈을 쓴 진행이 사라진다.** 크게 실패해야 한다."""
    with pytest.raises(SystemExit) as e:
        도구.차리기(차린자리["판"], Path(도구._기본번들), Path(도구._기본메타), False)
    말 = str(e.value)
    assert "이미 돌던 판이 있습니다" in 말 and "--덮어쓰기" in 말, 말
    assert "1차" in 말, "무슨 단계까지 돌았는지 안 말했다 — 사람이 판단할 수 없다\n%s" % 말


def test_없는_번들이면_멈춘다(도구, tmp_path):
    with pytest.raises(SystemExit) as e:
        도구.차리기(tmp_path / "판", tmp_path / "없는것.xlsx", Path(도구._기본메타), False)
    assert "못 찾았습니다" in str(e.value)


def test_raw_voc_가_아니면_멈춘다(도구, tmp_path):
    """★ 「못 찾음」 을 「없음」 으로 돌려주지 않는다 — 엉뚱한 엑셀을 앉히면 안 된다."""
    import openpyxl
    가짜 = tmp_path / "가짜.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "엉뚱한시트"
    wb.save(가짜)
    with pytest.raises(SystemExit) as e:
        도구.번들_세기(가짜)
    assert "raw_voc" in str(e.value)


def test_열쇠칸이_없으면_멈춘다(도구, tmp_path):
    import openpyxl
    가짜 = tmp_path / "열쇠없음.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "raw_voc"
    ws.append(["video_id", "comment_text"])      # atomic_id 가 없다
    ws.append(["v1", "말"])
    wb.save(가짜)
    with pytest.raises(SystemExit) as e:
        도구.번들_세기(가짜)
    assert "atomic_id" in str(e.value)


def test_열쇠가_겹치면_멈춘다(도구, tmp_path):
    """atomic_id 가 유일하지 않으면 **대조의 열쇠로 쓸 수 없다.**"""
    import openpyxl
    가짜 = tmp_path / "겹침.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "raw_voc"
    ws.append(["atomic_id", "video_id"])
    ws.append(["a1", "v1"])
    ws.append(["a1", "v1"])
    wb.save(가짜)
    with pytest.raises(SystemExit) as e:
        도구.번들_세기(가짜)
    assert "유일하지 않습니다" in str(e.value)


def test_돌리개가_1차를_건너뛰고_갖춤새가_된다고_말한다(차린자리):
    """★ 이것이 알맹이다 — **실제 돌리개에게** 돈 안 드는 `--확인만` 으로 물어본다.

    자리 이름을 시험에 두 벌로 적지 않는다. 돌리개가 그 자리에서 번들을 찾는지는
    돌리개가 대답한다.
    """
    환경 = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run([sys.executable, str(돌리개), str(차린자리["판"]), "--확인만"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(REPO), env=환경, timeout=600)
    말 = (r.stdout or "") + (r.stderr or "")
    assert r.returncode == 0, "`--확인만` 이 종료 %d 로 끝났다 —\n%s" % (r.returncode, 말[-2000:])
    assert "이미 끝난 단계: 1차" in 말, "1차를 건너뛰지 않는다 — 돈을 또 쓴다\n%s" % 말[-1500:]
    assert "갖춤새 — 다 됐습니다" in 말, "갖춤새가 모자라다고 한다\n%s" % 말[-1500:]
    assert "아무것도 돌리지 않았고 돈도 쓰지 않았습니다" in 말, 말[-800:]


def test_확인만은_아무것도_쓰지_않는다(차린자리):
    """`--확인만` 뒤에도 끝난단계가 ["1차"] 그대로여야 한다."""
    상태 = json.loads((차린자리["판"] / "상태.json").read_text(encoding="utf-8"))
    assert 상태["끝난단계"] == ["1차"], "미리보기가 상태를 건드렸다 — %s" % 상태["끝난단계"]


def test_진행메모가_이어받을_것을_담았다():
    """★ 며칠 걸리는 실행이다. 대화가 끊기면 **이 글 하나로** 이어받아야 한다."""
    글 = (REPO / "docs" / "진행_2판통째.md").read_text(encoding="utf-8")
    # ★ 드라이브 문자는 시험에 적지 않는다 (절대경로는 paths.py 에만 · 가드가 실제로 잡았다)
    for 꼭 in ("voc_2판통째", "--승인 --깨끗", "상태.json", "6,336", "6,846",
              "510", "--4차반영", "옛판_결과대조.py"):
        assert 꼭 in 글, "진행 메모에 `%s` 가 없다 — 이어받는 사람이 모른다" % 꼭
    assert "1차는 다시 돌리지 않는다" in 글, "1차를 왜 안 돌리는지 메모에 없다"


def test_돌리개가_정말_여기서_번들을_찾는다(차린자리):
    """★ `--확인만` 은 2차준비에서 **번들을 찾아보지 않고** 지나간다 (확인만이면 바로 돌아간다).

    그래서 위의 `--확인만` 시험만으로는 **자리가 맞는지 모른다.** 돈을 쓴 뒤에야 안다.
    여기서는 돌리개 **원문에서 자리 식을 읽어** 와 그 자리에 파일이 정말 있는지 본다 —
    자리를 시험에 두 벌로 적지 않으면서, 돌리개가 자리를 바꾸면 **크게 실패**한다.
    """
    import re
    원문 = 돌리개.read_text(encoding="utf-8")
    m = re.search(r'_가장새것\(\(판((?:\s*/\s*(?:"[^"]+"|조건\["이름"\]))+)\)\.glob\(\s*\n?\s*"([^"]+)"',
                  원문)
    assert m, ("돌리개에서 1차 번들을 찾는 식을 **못 찾았다.** 못 찾음은 통과가 아니다 — "
               "식이 바뀌었으면 이 시험과 `tools/2판통째_자리차리기.py` 를 같이 보라.")
    조각 = re.findall(r'"([^"]+)"|조건\["이름"\]', m.group(1))
    자리 = 차린자리["판"]
    for 조 in 조각:
        자리 = 자리 / (조 if 조 else 차린자리["도구"].이름)
    걸린것 = sorted(자리.glob(m.group(2)))
    assert 걸린것, ("돌리개가 1차 번들을 찾는 자리에 아무것도 없다 — %s · %s\n"
                  "  돈을 쓰고 2차준비에서 멈춘다." % (자리, m.group(2)))
    assert len(걸린것) == 1, "번들이 %d개다 — 어느 것으로 갈지 모른다: %s" % (
        len(걸린것), [q.name for q in 걸린것])
    assert 걸린것[0] == Path(차린자리["결과"]["번들자리"]), \
        "앉힌 자리와 돌리개가 찾는 자리가 다르다 — 앉힘 %s · 찾음 %s" % (
            차린자리["결과"]["번들자리"], 걸린것[0])
