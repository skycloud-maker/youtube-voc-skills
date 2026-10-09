# -*- coding: utf-8 -*-
"""글자가 깨졌거나 라벨 이름에 오타가 있는지 — `plugin/shared/tools/글자_점검.py` 를 지킨다.

★ 왜 — sky 2026-10-09 「모든 글자들에 이상하게 깨져서 들어가거나,, 오타가 들어가거나,,
  그런 오류 없는지 한번 점검해볼 필요도 있겠네요,,, 신뢰를 실뢰라고 쓴다거나..
  아까 그런 경우가 불러오는 경우에 일시적으로 발생한 오류인지,, 전체적인 저장에서
  오류가 발생한건지... 모르니까요..」

  그날 나온 「실뢰」 는 **내가 질문을 쓰다 틀린 것**이고 데이터는 멀쩡했다. 그래도 전수로
  재 본 적이 없어서 점검기를 만들었다. ★ 라벨이 한 글자 틀리면 집계가 **조용히 둘로 갈린다** —
  「제조사 신뢰/품질」 과 「제조사 실뢰/품질」 은 사람 눈에 거의 같아 보인다.

★ 여기서 지키는 것
  ① 점검기가 **진짜 깨짐을 잡는가** (일부러 만들어 넣어 본다)
  ② 점검기가 **사람이 쓴 말을 안 잡는가** (`ㅋㅋ` · `ㅜㅜ` · 정규식 글자묶음)
  ③ 저장소의 기준서·도구·대장이 지금 깨끗한가
★ 「못 찾음」 은 통과가 아니다 — 볼 파일이 0개면 점검기가 2 로 끝낸다.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_뿌리 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
sys.path.insert(0, str(_뿌리 / "plugin" / "shared" / "tools"))
from paths import SHARED  # noqa: E402

점검기 = SHARED / "tools" / "글자_점검.py"


def _돌리기(터: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-B", str(점검기), str(터)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def test_점검기가_있다():
    assert 점검기.is_file(), "글자_점검.py 가 없다 — %s" % 점검기


@pytest.mark.parametrize("이름,파일,글", [
    # ① 라벨 한 글자 오타 — 2026-10-09 에 sky 가 걱정한 바로 그 꼴
    ("라벨오타", "raw_voc.csv", "atomic_id,topic\na,제조사 실뢰/품질\n"),
    # ② 치환문자 — 바이트가 이미 사라진 깨짐 (되살릴 수 없다)
    ("치환문자", "메모.md", "가전" + chr(0xFFFD) + "제품\n"),
    # ③ 한자 섞임 — UTF-8 글을 cp949 로 읽었을 때 나오는 꼴 (「以묎뎅」 = 「중국」)
    ("한자섞임", "메모.md", "以묎뎅 로봇청소기\n"),
    # ④ 자모가 음절 **사이에** 끼어듦
    ("자모섞임", "메모.md", "제조사 신ㄹ뢰 품질\n"),
    # ⑤ 제어문자 — 역슬래시+v 가 세로탭 한 글자로 바뀐 꼴
    ("제어문자", "메모.md", "자리 Temp" + chr(11) + "oc 입니다\n"),
])
def test_일부러_틀린_것을_잡는다(tmp_path, 이름, 파일, 글):
    (tmp_path / 파일).write_text(글, encoding="utf-8-sig" if 파일.endswith(".csv") else "utf-8",
                                newline="\n")
    코드, 말 = _돌리기(tmp_path)
    assert 코드 == 1, "%s 를 못 잡았다 (종료 %d)\n%s" % (이름, 코드, 말[-800:])
    assert ("[%s]" % 이름) in 말, "%s 로 알리지 않았다:\n%s" % (이름, 말[-800:])


def test_사람이_쓴_자모는_안_잡는다(tmp_path):
    """★ 처음 짰을 때 `아닌가ㅋㅋ` · `"ㅂ니다"` · 정규식 `가-힣ㄱ-ㅎㅏ-ㅣ` 가 줄줄이 걸렸다.

    거짓 경보가 쌓이면 아무도 안 돌린다 — 그래서 여기서 못 박는다.
    """
    (tmp_path / "메모.md").write_text(
        '아닌가ㅋㅋ 대참사ㅠㅠ 안되나요ㅜㅜ ㅉㅉ ㄹㅇ "ㅂ니다" 가-힣ㄱ-ㅎㅏ-ㅣ\n',
        encoding="utf-8", newline="\n")
    코드, 말 = _돌리기(tmp_path)
    assert 코드 == 0, "사람이 쓴 자모를 깨짐으로 본다:\n%s" % 말[-900:]


def test_자유기술_칸을_라벨로_보지_않는다(tmp_path):
    """`rootcause_problem` 은 문장이 들어가는 칸이다 (check_selfcheck 의 FREE 목록).

    ★ 처음에는 그 칸도 라벨로 봐서 **문장 60종**이 「정본에 없는 라벨」 로 나왔다.
    """
    (tmp_path / "raw_voc.csv").write_text(
        "atomic_id,topic,rootcause_problem\n"
        "a,제조사 신뢰/품질,LG 에 대한 신뢰가 구매 전환으로 이어진다.\n",
        encoding="utf-8-sig", newline="\n")
    코드, 말 = _돌리기(tmp_path)
    assert 코드 == 0, "자유기술 문장을 라벨로 본다:\n%s" % 말[-900:]
    assert "LG 에 대한 신뢰" not in 말, "자유기술 문장을 새 라벨로 알린다:\n%s" % 말[-600:]


def test_볼_파일이_0개면_실패한다(tmp_path):
    """「못 찾음」 은 통과가 아니다 — 검사 안 한 것을 숨기지 않는다."""
    코드, 말 = _돌리기(tmp_path)
    assert 코드 == 2, "볼 파일이 없는데 통과로 끝낸다 (종료 %d)" % 코드
    assert "0개" in 말


def test_기준서와_도구와_대장이_깨끗하다():
    """★ 실제 자리를 본다 — 만든 표가 아니라 저장소의 기준서·도구·대장이다."""
    for 터 in (SHARED / "standards", SHARED / "tools", SHARED / "registry", SHARED / "common"):
        if not 터.is_dir():
            continue
        코드, 말 = _돌리기(터)
        assert 코드 == 0, "%s 에 깨진 글자나 라벨 오타가 있다:\n%s" % (터.name, 말[-1500:])


def test_엔진의_깨진_파일은_알려진_둘뿐이다():
    """★ 2026-10-09 — 엔진 동결 사본에 **옛 프로젝트에서 넘어온 깨짐**이 둘 있다.

    우리가 만든 것이 아니라 복사해 온 사본에 원래 있던 것이다. 지금은 고치지 않고
    **수가 늘지 않는 것**만 지킨다 (엔진을 고치면 `출처_엔진.json` 의 지문과
    `test_engine` 이 함께 움직여야 한다 — 사람이 정할 일이다).

      engine/voc-classifier/src/classifier.py          cp949 로 읽어 저장한 꼴 (되살릴 수 있다)
      engine/src/application/shadow/semantic_sidecar.py  치환문자가 박혀 있다 (되살릴 수 없다)
    """
    엔진 = SHARED.parent / "engine"
    if not 엔진.is_dir():
        pytest.skip("엔진 사본이 없다")
    코드, 말 = _돌리기(엔진)
    # ★ 윈도 경로의 `C:` 때문에 콜론으로 먼저 자르면 안 된다 (처음에 그래서 「C」 가 나왔다).
    #   `/engine/` 뒤를 떼고 **그 다음에** 줄번호 콜론을 뗀다.
    걸린파일 = set()
    for l in 말.splitlines():
        if not l.strip().startswith("["):
            continue
        길 = l.split("] ", 1)[-1].replace(chr(92), "/")
        if "/engine/" not in 길:
            continue
        뒤 = 길.split("/engine/", 1)[1]
        걸린파일.add(뒤.split(":", 1)[0].strip())
    알려진것 = {"voc-classifier/src/classifier.py",
             "src/application/shadow/semantic_sidecar.py"}
    새것 = {x for x in 걸린파일 if x not in 알려진것}
    assert not 새것, "엔진에 **새로** 깨진 파일이 생겼다 — %s" % sorted(새것)
    assert 걸린파일 == 알려진것, \
        ("알려진 깨짐이 사라졌거나 바뀌었다 — 고쳤으면 이 시험과 docs 를 같이 고친다.\n"
         "  지금: %s\n  알려진 것: %s" % (sorted(걸린파일), sorted(알려진것)))
