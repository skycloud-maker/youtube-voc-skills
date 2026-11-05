# -*- coding: utf-8 -*-
"""꾸러미가 **정답지를 싣지 않는가** · 도구가 **대장 폴더를 스스로 찾는가** (2026-11-05 · 결정 1·2).

★ 왜 이 검사가 생겼나 — 2026-11-05 에 한 줄 흐름을 처음으로 **zip 을 푼 폴더**에서 끝까지
  돌려 보니(74분 · 종료 0) 판독A 가 둘을 보고했다.

  ① **정답지 오염** — 79행 중 최소 12행이 2판 시험 데이터와 같은 `atomic_id` 이고,
     그중 **8행은 최종 판정값이 판독 패키지의 `9_택소노미_2차확장` §20·§21 에 적혀 있었다.**
     판독자가 답을 들고 읽은 것이라, 그 판의 일치율 97.5% 는 **판독 실력 수치가 아니다.**
     (sky 「정답지 규율」 — 「정답지는 채점용이지 판독자에게 주는 대조표가 아니다」)
  ② **도구가 대장을 못 찾음** — 도구는 `s9_group/` 을 보는데 꾸러미에 실리는 자리 이름은
     `대장/` 이라, 판독자 둘이 **각자 바로가기(정션)를 만들어야** 판독이 돌아갔다.
     2026-10-29 에 고른 길은 「이름 대응을 **안내문에** 적는다」 였는데, 안내문만으로는
     **사람은 알아도 도구는 못 찾는다.**

  두 고침 모두 **사람이 돌려 봐야 드러나는 것**이라, 여기 심어 두지 않으면 다음 판에 또 샌다
  (sky 「가드는 돌리는 자리에」 — 시험이 있어도 아무도 안 돌리면 2주를 간다).

보는 것
  ① 판독 꾸러미의 기준서에 **유튜브 댓글 ID 가 0개**인가 — 가린 자리에 「덜어 냈다」 가 적혔는가
  ② 판정에 필요한 **규칙 문장은 그대로 남았는가** (가리개가 너무 많이 자르면 판독이 못 돈다)
  ③ 감독 꾸러미는 **전량 그대로**인가 — 감독자는 4차 결정을 알아야 한다
  ④ 저장소 원문은 **한 글자도 안 바뀌었는가**
  ⑤ 지문이 **실제로 넣은 글**과 맞는가 — 어긋나면 `지문검사.py` 가 「건드렸다」 고 헛외친다
  ⑥ 절 이름을 못 찾으면 **크게 실패하는가** — 조용히 넘어가면 정답지가 다시 실려 나간다
  ⑦ 판독·감독 꾸러미에 실리는 도구가 `대장/` · `s9_group/` 을 **둘 다** 찾는가
  ⑧ 총괄 자리에서 도는 도구는 **안 건드렸는가** — 거기 이름은 진짜 `s9_group` 이다
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import REPO, SHARED  # noqa: E402

정답지파일 = "9_택소노미_2차확장.md"
원문 = SHARED / "standards" / 정답지파일
_ID = re.compile(r"Ug[A-Za-z0-9_.-]{15,}")      # 유튜브 댓글 ID 꼴
_원문ID수 = 17                                   # 2026-11-05 에 실제로 센 수

# 판독·감독 꾸러미에 실려 나가는 도구 — 여기서는 폴더 이름이 `대장/` 이다
_고친도구 = ("build_bundle.py", "check_selfcheck.py", "check_submission.py", "topic_registry.py")
# 총괄 자리에서 도는 것 — 거기 이름은 진짜 `s9_group` 이다. 건드리면 안 된다
_안건드릴도구 = ("그룹_맞추기.py", "3차_준비.py", "3차_마무리.py")

도구자리 = SHARED / "tools"


def _꾸러미모듈():
    spec = importlib.util.spec_from_file_location("꾸러미_시험용", SHARED / "lib" / "꾸러미.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def 묶은것(tmp_path_factory):
    """판독·감독 꾸러미를 **진짜로 묶어** 돌려준다. 흉내 내지 않는다."""
    꾸러미 = _꾸러미모듈()
    엔진 = REPO / "plugin" / "engine"
    판독 = REPO / "plugin" / "skills" / "reading-voc-comments"
    감독 = REPO / "plugin" / "skills" / "supervising-voc-disagreements"
    d = tmp_path_factory.mktemp("정답지시험")
    셈1 = 꾸러미.차리기(d / "판독", "2_2차판독", SHARED, 엔진,
                      판독 / "references", 판독 / "assets")
    셈2 = 꾸러미.차리기(d / "감독", "3_3차감독", SHARED, 엔진,
                      감독 / "references", 감독 / "assets")
    for 이름, 셈 in (("판독", 셈1), ("감독", 셈2)):
        assert not 셈["못찾음"], "%s 꾸러미 재료를 못 찾았다 — %s" % (이름, 셈["못찾음"][:5])
    return {"판독": d / "판독", "감독": d / "감독", "셈판독": 셈1, "꾸러미": 꾸러미}


# ── ① ~ ② 판독 꾸러미 ─────────────────────────────────────────────────────────
def test_판독꾸러미에_댓글ID가_없다(묶은것):
    q = 묶은것["판독"] / "판독패키지" / 정답지파일
    assert q.is_file(), "못 찾음: 판독 꾸러미의 %s — 검사할 것이 없으면 통과가 아니다" % 정답지파일
    나온것 = _ID.findall(q.read_bytes().decode("utf-8"))
    assert not 나온것, ("판독 꾸러미에 댓글 ID 가 %d개 실렸다 — 판독자가 답을 보고 읽는다.\n  %s"
                       % (len(나온것), 나온것[:5]))


def test_판독꾸러미가_가린_사실을_적는다(묶은것):
    글 = (묶은것["판독"] / "판독패키지" / 정답지파일).read_bytes().decode("utf-8")
    assert 글.count("일부러 덜어 냈습니다") == 2, "가린 두 절에 가렸다는 말이 적혀 있어야 한다"
    assert "감독 꾸러미" in 글 and "저장소 원본" in 글, "전량이 어디 있는지 가리켜야 한다"


def test_판독꾸러미에_규칙은_그대로_있다(묶은것):
    """가리개가 너무 많이 자르면 판독이 못 돈다 — 규칙은 남아야 한다."""
    글 = (묶은것["판독"] / "판독패키지" / 정답지파일).read_bytes().decode("utf-8")
    for 있어야할것 in ("### 가름의 잣대 셋",
                     "## 20. 원산지·OEM 축",
                     "## 21. 같은 칸에"):
        assert 있어야할것 in 글, "규칙 「%s」 가 사라졌다 — 너무 많이 잘랐다" % 있어야할것


def test_묶는도구가_가린_절을_센다(묶은것):
    assert 묶은것["셈판독"].get("정답지가림") == 2, "두 절을 가렸다고 세어야 한다"


# ── ③ ~ ④ 감독 꾸러미 · 저장소 원문 ───────────────────────────────────────────
def test_감독꾸러미는_전량_그대로다(묶은것):
    """감독자는 갈린 행을 판정하는 자리라 4차 결정을 알아야 한다."""
    q = 묶은것["감독"] / "판독패키지" / 정답지파일
    assert q.is_file(), "못 찾음: 감독 꾸러미의 %s" % 정답지파일
    assert q.read_bytes() == 원문.read_bytes(), "감독 꾸러미는 저장소 원문과 바이트가 같아야 한다"


def test_저장소_원문은_안_바뀌었다():
    글 = 원문.read_bytes().decode("utf-8")
    나온것 = _ID.findall(글)
    assert len(나온것) == _원문ID수, (
        "원문의 댓글 ID 가 %d개다 — 센 값 %d개와 다르다.\n"
        "  기준서가 바뀌었으면 _원문ID수 를 고치기 전에 **가리개가 아직 맞는지** 확인해야 한다."
        % (len(나온것), _원문ID수))


# ── ⑤ 지문 ────────────────────────────────────────────────────────────────────
def test_지문이_실제로_넣은_글과_맞는다(묶은것):
    """지문을 원문에서 뜨면 실물과 어긋나 `지문검사.py` 가 「건드렸다」 고 헛외친다."""
    지문 = json.loads((묶은것["판독"] / "대장" / "지문.json")
                     .read_bytes().decode("utf-8"))["지문"]
    키 = "판독패키지/" + 정답지파일
    assert 키 in 지문, "못 찾음: 지문에 %s 가 없다 — 검사 대상이 없으면 통과가 아니다" % 키
    실물 = ((묶은것["판독"] / "판독패키지" / 정답지파일).read_bytes().decode("utf-8")
            .replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))
    assert 지문[키] == hashlib.sha256(실물).hexdigest()[:16], (
        "지문이 실제로 넣은 글과 다르다 — 지문검사가 헛외친다")


# ── ⑥ 일부러 틀리게 ───────────────────────────────────────────────────────────
def test_절을_못_찾으면_크게_실패한다(묶은것):
    """조용히 넘어가면 그때부터 정답지가 다시 실려 나간다."""
    with pytest.raises(SystemExit) as e:
        묶은것["꾸러미"].정답지_가리기("# 절이 하나도 없는 글\n\n본문뿐이다.\n")
    assert "못 찾음" in str(e.value), "못 찾았다는 것이 글에 드러나야 한다"


# ── ⑦ ~ ⑧ 대장 자리 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("이름", _고친도구)
def test_꾸러미_도구가_대장을_스스로_찾는다(이름):
    글 = (도구자리 / 이름).read_text(encoding="utf-8")
    assert "def 대장자리" in 글, "%s 에 대장자리() 가 없다" % 이름
    assert "os.path.join(BASE, 's9_group'" not in 글, (
        "%s 에 옛 꼴이 남았다 — 판독 폴더에서 못 찾는다" % 이름)


@pytest.mark.parametrize("이름", _안건드릴도구)
def test_총괄_도구는_안_건드렸다(이름):
    """총괄 자리에서는 폴더 이름이 **진짜 `s9_group`** 이다."""
    글 = (도구자리 / 이름).read_text(encoding="utf-8")
    assert "s9_group" in 글, "%s 에서 s9_group 이 사라졌다 — 총괄 자리가 깨진다" % 이름
    assert "def 대장자리" not in 글, "%s 는 총괄 자리에서 도는 것이라 고치면 안 된다" % 이름


@pytest.mark.parametrize("만들것,바라는것,있나", [
    (("대장",), "대장", True),                       # 새 판독·감독 폴더 — 여기만 바뀌어야 한다
    (("s9_group",), "s9_group", True),              # 총괄 자리 — 이름이 진짜 s9_group 이다
    (("s9_group", "대장"), "s9_group", True),        # ★ 둘 다 있다 — 아래 설명
    ((), "s9_group", False),                        # 둘 다 없다 — 일부러 틀리게 만든 자리
])
def test_대장자리가_네_자리에서_맞게_고른다(tmp_path, 만들것, 바라는것, 있나):
    """★ 「둘 다 있을 때 `s9_group` 이 이긴다」 가 이 검사의 핵심이다.

    2026-11-05 에 내가 순서를 거꾸로(`대장` 먼저) 넣었다가 얼린 2차 기준 시험 둘이
    떨어졌다 (`topic_group` 값 다름 · `계약위반.csv` 다름). 2판 판독 폴더를 되살려
    돌리는 그 시험에는 **둘 다 있다** — `대장/` 은 꾸러미가 깐 **처음 상태**이고
    `s9_group/` 은 **판독자가 판독하며 갱신한 살아 있는 대장**이다
    (`tests/baseline/기준_만들기_2차.py` 의 `_판독_얹기`). `대장` 을 먼저 보면
    판독자가 갱신한 것을 버린다.

    **이 고침은 찾는 자리를 「늘리기만」 해야 한다** — 전에 되던 자리는 하나도 바뀌면 안 된다.
    """
    (tmp_path / "스크립트").mkdir()
    for q in 도구자리.glob("*.py"):
        shutil.copy2(q, tmp_path / "스크립트" / q.name)
    for 폴더 in 만들것:
        (tmp_path / 폴더).mkdir()
        for n in ("topic_group_map.json", "secondary_topics.json",
                  "secondary_enums.json", "topic_registry.json"):
            (tmp_path / 폴더 / n).write_text(json.dumps({"topic_to_group": {}}),
                                            encoding="utf-8")
    코드 = ("import os, topic_registry as t, build_bundle as b\n"
            "for v in (t.SIDE_G, t.SIDE_T, t.REGISTRY, b.GROUP_MAP,\n"
            "          b.SECONDARY_TOPICS, b.SECONDARY_ENUMS):\n"
            "    print(os.path.basename(os.path.dirname(v)))\n"
            "print('있나', os.path.exists(t.SIDE_G))\n")
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", 코드],
                       cwd=str(tmp_path / "스크립트"), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, "도구를 못 불러왔다 — %s" % (r.stderr or "")[-400:]
    줄 = r.stdout.split()
    assert 줄[:6] == [바라는것] * 6, "여섯 자리가 다 `%s/` 여야 한다 — 나온 것 %s" % (바라는것, 줄[:6])
    assert 줄[-1] == str(있나), "파일이 있나 = %s 여야 한다" % 있나
