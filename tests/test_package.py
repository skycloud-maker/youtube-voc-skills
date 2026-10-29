# -*- coding: utf-8 -*-
"""꾸러미 재료와 판독 폴더 차리기 시험 (섹션 4 · 2026-09-21 교차점검에서 만들었다).

★ 왜 이제 만들었나 — `plugin/shared/출처_꾸러미.json` 이 「고치면 tests/test_package.py 가 실패한다」 고
  적어 두었는데 그 시험이 **없었다.** 기준서 8종만 지켜지고 도구 21 · 대장 4 · 안내서 4 · 엔진 28 등
  70개는 조용히 갈려도 아무도 몰랐다.

보는 것
  ① 출처 기록의 해시 = 지금 파일 (판독 70 + 감독 3 = 73개)
  ② 차림표의 재료가 모두 있고, 모두 출처 기록에 적혀 있다 (빠진 재료 · 안 쓰는 기록 0)
  ③ 폴더를 차리면 옛 꾸러미 모양이 된다 — 판독 84개 · 감독 68개(편향검사 뺌 · 섹션 5b 의 새 판 0_최신결정_먼저.md 더함 · 판독에는 최신결정_검사.py 도 · 섹션 7 ① 엔진은 도구가 부르는 것을 코드로 따라가 뽑는다) — 지문에 engine 이 들어간다
  ④ ★ 엔진을 한 줄 고치면 지문검사가 실패한다 (전에는 통과했다 — 그래서 여기서 지킨다)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(_여기.parent / "plugin" / "shared"))
from paths import BASELINE, PLUGIN, REPO, SHARED  # noqa: E402

스킬 = PLUGIN / "skills" / "reading-voc-comments"
sys.path.insert(0, str(스킬 / "scripts"))
import 판독폴더_차리기 as 차리기  # noqa: E402
sys.path.insert(0, str(PLUGIN / "skills" / "supervising-voc-disagreements" / "scripts"))
import 감독폴더_차리기 as 감독차리기  # noqa: E402
sys.path.insert(0, str(PLUGIN / "skills" / "coordinating-voc-pipeline" / "scripts"))
import 총괄자리_차리기 as 총괄차리기  # noqa: E402
import 꾸러미  # noqa: E402  (차리기 스크립트가 shared/lib 를 path 에 넣었다)

꾸러미출처 = json.loads((SHARED / "출처_꾸러미.json").read_text(encoding="utf-8"))
기준서출처 = json.loads((SHARED / "standards" / "출처.json").read_text(encoding="utf-8"))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_출처_기록이_실제_파일과_같다():
    파일 = 꾸러미출처["파일"]
    # 판독 70 (섹션 4) + 감독 3 + 총괄 19 (섹션 5) + 최신결정_검사 (섹션 5b) − 엔진 28 (섹션 7 ① 출처_엔진.json 으로)
    # + 99_1차_실행조건_원문 (섹션 7 ③) + 안내서 그림 6 (섹션 7a ③) + 제출 규율 원문 2 (섹션 8 — 52 · 65)
    # + 글자_점검.py (2026-10-09 — 깨진 글자 · 라벨 오타)
    # + 키워드결합_OR_AND_기준.md (2026-10-22 — sky 「or 와 and 의 조건을 명확하게」.
    #   엔진 코드를 읽어 적은 새 기준서 · 1차 자리에 같이 놓는다)
    assert len(파일) == 76, len(파일)
    없음 = [r for r in 파일 if not (REPO / r).is_file()]
    assert not 없음, "출처에 적힌 파일이 없다 — %s" % 없음[:5]
    어긋남 = [r for r, v in 파일.items() if _sha(REPO / r) != v["지금_sha256"]]
    assert not 어긋남, ("출처 기록과 다른 파일이 있다. 일부러 고쳤다면 `고친_이력` 에 이유를 적고 "
                     "`지금_sha256` 을 갱신하라 — %s" % 어긋남[:5])


def test_고친_이력이_있는_것만_원본과_다르다():
    for r, v in 꾸러미출처["파일"].items():
        같음 = v["원본_sha256"] == v["지금_sha256"]
        if v["고친_이력"]:
            assert not 같음, "%s — 고친_이력이 있는데 원본과 같다" % r
        else:
            # 줄바꿈만 LF 로 맞춘 것은 원본과 달라도 된다 — 글자는 같아야 한다
            if not 같음:
                원 = (REPO / r).read_bytes()
                assert b"\r\n" not in 원, "%s — 고친_이력 없이 달라졌다" % r


def test_차림표_재료가_모두_있고_출처에_적혀_있다():
    총괄재료 = 총괄차리기.총괄자리.판재료(총괄차리기.공통, 총괄차리기.엔진, 총괄차리기.판독 / "references",
                                총괄차리기.감독 / "references")
    대장 = [(p, "") for p in sorted((SHARED / "registry").glob("*.json"))]
    # ★ 1차 자리(섹션 7 ③)는 **공통 재료만** 넣는다 — 스킬 자신의 `1차_돌리기.py` 는 우리가 쓴 코드라
    #   공통 출처 기록에 없다(옛 저장소에서 온 것이 아니다). 그 파일이 실제로 복사되고 도는지는
    #   tests/test_build.py 의 `test_1차_스킬이_떨어진_자리에서_실행_자리를_차린다` 가 본다.
    sys.path.insert(0, str(SHARED / "lib"))
    import 일차자리                                        # noqa: E402,PLC0415
    일차재료 = 일차자리.재료(SHARED, REPO / "plugin" / "engine")
    # ★ 섹션 8 — 보고서 스킬이 읽는 규율 원문 둘. 이 둘은 **작업 폴더에 실리지 않고** 낱개 스킬의
    #   `shared/` 로만 간다 (보고서는 작업 폴더를 차리지 않고 최종 엑셀 하나만 받는다).
    #   그래도 「기록만 있고 아무도 안 쓰는 파일」 이 아니다 — 스킬이 읽는다. 그래서 여기에 적어 둔다.
    보고서재료 = [(SHARED / "common" / n, "") for n in
               ("52_AX_FLEX_과제_제출본.md", "65_개인정보_처리_기준_및_제출문안.md")]
    재료 = [Path(원) for 원, _ in (차리기.전체_차림표() + 감독차리기.전체_차림표() + 총괄재료
                                + 대장 + 일차재료 + 보고서재료)]
    없음 = [p for p in 재료 if not p.is_file()]
    assert not 없음, "차림표가 가리키는 재료가 없다 — %s" % [str(p) for p in 없음[:5]]
    엔진출처 = json.loads((REPO / "plugin" / "engine" / "출처_엔진.json").read_text(encoding="utf-8"))["파일"]
    적힌것 = (set(꾸러미출처["파일"]) | {("plugin/shared/standards/" + n) for n in 기준서출처["파일"]}
            | {("plugin/engine/" + n) for n in 엔진출처} | {"plugin/engine/출처_엔진.json"})   # 기록 파일 자신
    # 엔진 정본 전체(1차 실행 · 대시보드)는 폴더에 다 실리지 않는다 — 판독 · 감독 폴더는 꾸러미엔진 28개, 총괄 판 폴더는 전부
    쓰는것_엔진 = {"plugin/engine/" + n for n in 엔진출처}
    쓰는것 = {p.resolve().relative_to(REPO).as_posix() for p in 재료}
    assert not (쓰는것 - 적힌것), "출처 기록에 없는 재료를 쓴다 — %s" % sorted(쓰는것 - 적힌것)[:5]
    assert not (적힌것 - 쓰는것 - 쓰는것_엔진), "기록만 있고 아무도 안 쓰는 파일 — %s" % sorted(적힌것 - 쓰는것)[:5]


@pytest.fixture(scope="module")
def 차린폴더(tmp_path_factory):
    d = tmp_path_factory.mktemp("판독폴더")
    셈 = 차리기.차리기(d)
    assert not 셈["못찾음"], 셈["못찾음"]
    return d


def test_차리면_꾸러미와_같은_90개가_된다(차린폴더):
    파일 = [p for p in 차린폴더.rglob("*") if p.is_file()]
    assert len(파일) == 90, len(파일)          # 옛 꾸러미 80 + 새 판 + 최신결정_검사.py + 엔진 +2 (섹션 7 ①) + 안내서 그림 6 (섹션 7a ③ — 옛 꾸러미부터 빠져 깨져 있었다)
    for 자리 in ("스크립트/자가점검.py", "판독패키지/1a_기준문서_정본_1부.md", "프롬프트/0_붙여넣을_프롬프트_도구형.md",
                "대장/지문.json", "0_먼저_읽으십시오.md", "engine/src/voc_rebuild/engine.py"):
        assert (차린폴더 / 자리).is_file(), 자리


def test_지문에_엔진이_들어간다(차린폴더):
    지문 = json.loads((차린폴더 / "대장" / "지문.json").read_text(encoding="utf-8"))
    엔진 = [k for k in 지문["지문"] if k.startswith("engine/")]
    assert len(엔진) == 27, len(엔진)          # 엔진 .py — 섹션 7 ① 전 25 (도구가 부르는 것을 따라가 뽑는다)
    assert 지문["파일수"] == len(지문["지문"]) == 67, 지문["파일수"]


def _지문검사(폴더: Path) -> int:
    env = dict(os.environ, VOC_ENGINE=str(폴더 / "engine"), PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return subprocess.run([sys.executable, "-B", "스크립트/지문검사.py"], cwd=폴더, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace").returncode


def test_엔진을_고치면_지문검사가_잡는다(차린폴더, tmp_path):
    # ★ 일부러 틀리게 — 2026-09-21 전에는 여기서 통과했다 (지문이 engine 을 안 떴다)
    사본 = tmp_path / "고친폴더"
    shutil.copytree(차린폴더, 사본)
    assert _지문검사(사본) == 0, "고치기 전에는 통과해야 한다"
    p = 사본 / "engine" / "src" / "voc_rebuild" / "engine.py"
    p.write_bytes(p.read_bytes() + b"\n# TAMPERED\n")
    assert _지문검사(사본) == 1, "엔진을 고쳤는데 지문검사가 통과했다"
    도구 = 사본 / "스크립트" / "성실성검사.py"
    도구.write_bytes(도구.read_bytes() + b"\n# TAMPERED\n")
    assert _지문검사(사본) == 1


# ── 감독 꾸러미 (섹션 5) ────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def 감독폴더(tmp_path_factory):
    d = tmp_path_factory.mktemp("감독폴더")
    셈 = 감독차리기.차리기(d)
    assert not 셈["못찾음"], 셈["못찾음"]
    return d


def test_감독폴더는_74개이고_편향검사가_없다(감독폴더):
    파일 = [p for p in 감독폴더.rglob("*") if p.is_file()]
    assert len(파일) == 74, len(파일)          # 옛 감독 꾸러미 66개 − 편향검사.py + 새 판 + 엔진 +2 (섹션 7 ①) + 안내서 그림 6 (섹션 7a ③)
    assert not (감독폴더 / "스크립트" / "편향검사.py").exists(), "감독 폴더에 편향검사가 있다 (98: 아예 없다)"
    assert (감독폴더 / "프롬프트" / "0_붙여넣을_프롬프트_감독.md").is_file()


def test_감독폴더에_정답지와_감독입력을_만들지_않는다(감독폴더):
    # ★ 익명화 — 감독자가 A·B 가 누구인지 알면 편든다. 입력은 총괄이 넣는다
    for 금지 in ("s13_judge", "_총괄만", "ab_mapping.json", "스크립트/make_judge_input.py",
               "스크립트/build_master.py", "스크립트/3차_준비.py", "스크립트/3차_마무리.py"):
        assert not (감독폴더 / 금지).exists(), 금지
    assert not list(감독폴더.rglob("ab_mapping*")), "정답지가 들어갔다"
    assert not list(감독폴더.rglob("*_bundle")), "2차 번들이 들어갔다"


def test_감독폴더_안내문은_옛_꾸러미와_적어_둔_것만_다르다(감독폴더):
    옛 = BASELINE / "원본사본" / "꾸러미" / "VoC_3_3차감독" / "0_먼저_읽으십시오.md"
    assert 옛.is_file(), "옛 감독 꾸러미 사본을 못 찾았다 — %s" % 옛
    a = 옛.read_text(encoding="utf-8").splitlines()
    b = (감독폴더 / "0_먼저_읽으십시오.md").read_text(encoding="utf-8").splitlines()
    새판 = [x for x in b if "0_최신결정_먼저.md" in x]
    assert len(새판) == 1, 새판          # 섹션 5b 의 새 판 — 옛 꾸러미에 없던 한 줄
    # 섹션 7 ① — engine/ 줄은 이제 도구가 부르는 엔진 파일을 코드로 따라가 뽑은 목록이다 (옛 꾸러미와 다르다 · 그 목록과 같아야 한다)
    엔진줄 = [x.strip() for x in b if x.strip().startswith("engine/")]
    assert 엔진줄 == ["engine/" + n for n in 꾸러미.꾸러미엔진(PLUGIN / "engine")], 엔진줄[:5]
    # 섹션 7a ③ — 안내서 63 이 가리키는 그림 6개를 안내서 옆에 넣었다 (옛 꾸러미부터 빠져 깨져 있었다)
    그림줄 = [x for x in b if "가이드/캡쳐/" in x]
    assert len(그림줄) == 6, 그림줄
    # ★ 2026-10-29 — 네 번째로 밝힌 차이. 글이 다른 이름으로 가리키는 자리를 안내문 끝에 적는다
    #   (판독A 가 실제 판독에서 걸렸다 · test_안내문이_이름_어긋난_자리를_다_밝힌다 가 속을 지킨다).
    #   시험 이름을 「한 줄과 한 줄만」 에서 「적어 둔 것만」 으로 바꿨다 — 차이가 이미 넷이다.
    #   ★ 줄 내용으로 빼면 안 된다 — 빈 줄과 ``` 는 앞쪽에도 있다. **자리로** 자른다.
    # ★ 2026-10-29 (같은 날 둘째) — **다섯 번째** 차이. 칸 사슬 절을 그 앞에 적는다
    #   (판독A 가 「74칸인데 계약은 66칸」 이라고 적었다 · 둘 다 사실이었다).
    #   절이 둘이 되었으므로 **먼저 오는 자리**에서 자른다. 하나라도 없으면 실패한다.
    머리들 = ["## " + 꾸러미.칸사슬_절이름, "## ★ 글이 다른 이름으로 가리키는 자리"]
    for 머리 in 머리들:
        assert b.count(머리) == 1, "그 절이 하나가 아니다 — %s (%d개)" % (머리, b.count(머리))
    끊은자리 = min(b.index(머리) for 머리 in 머리들)
    assert 끊은자리 == b.index(머리들[0]), "칸 사슬 절이 이름 대응 절보다 뒤에 있다"
    assert len(b) - 끊은자리 >= 8, b[끊은자리:]
    앞쪽 = b[:끊은자리]
    if 앞쪽 and 앞쪽[-1] == "":
        앞쪽 = 앞쪽[:-1]          # 머리글 앞의 빈 줄 하나 — 마크다운이 그래야 한다
    옛것 = [x for x in a if "편향검사.py" not in x and not x.strip().startswith("engine/")]
    assert 옛것 == [x for x in 앞쪽 if x not in 새판 and x not in 그림줄
                  and not x.strip().startswith("engine/")]


def test_감독폴더_지문에_엔진이_들어가고_엔진을_고치면_잡는다(감독폴더, tmp_path):
    지문 = json.loads((감독폴더 / "대장" / "지문.json").read_text(encoding="utf-8"))
    assert sum(1 for k in 지문["지문"] if k.startswith("engine/")) == 27      # 엔진 .py — 섹션 7 ① 전 25
    사본 = tmp_path / "고친감독폴더"
    shutil.copytree(감독폴더, 사본)
    assert _지문검사(사본) == 0
    p = 사본 / "engine" / "src" / "voc_rebuild" / "schema.py"
    p.write_bytes(p.read_bytes() + b"\n# TAMPERED\n")
    assert _지문검사(사본) == 1


# ── 총괄 자리 (섹션 5) ───────────────────────────────────────────────────────────
def test_총괄자리는_도구_42개와_감독꾸러미를_갖춘다(tmp_path):
    셈 = 총괄차리기.차리기(tmp_path / "총괄", "시험판")
    assert not 셈["못찾음"], 셈["못찾음"]
    판 = tmp_path / "총괄" / "시험판"
    도구 = sorted(p.name for p in 판.glob("*.py"))
    # 41 + 최신결정_검사.py(섹션 5b) + 글자_점검.py(2026-10-09 · 깨짐·라벨 오타)
    assert len(도구) == 43, len(도구)
    for 옛관리 in ("마무리_이력정리.py", "정본_맞추기.py", "make_zip.py", "박힌말_검사.py", "5차기준_검사.py"):
        assert 옛관리 not in 도구, "옛 관리 도구가 들어갔다 — %s (sky: 새 방식으로 대신)" % 옛관리
    assert (tmp_path / "총괄" / "s9_group" / "topic_group_map.json").is_file(), "대장은 판 폴더의 부모에"
    assert not (판 / "s9_group").exists(), "판 폴더 안에는 대장이 없다 (2판이 그랬다)"
    import zipfile
    with zipfile.ZipFile(판 / "_배포" / "VoC_3_3차감독.zip") as z:
        이름 = [n for n in z.namelist() if not n.endswith("/")]
    assert len(이름) == 74 and "스크립트/편향검사.py" not in 이름, "감독 꾸러미는 감독 스킬과 한 벌이어야 한다"
    assert 셈["차림"] > 0 and 총괄차리기.차리기(tmp_path / "총괄", "시험판")["차림"] == 0, "다시 돌리면 아무것도 덮지 않는다"


def test_1차가_만든_영상메타가_판독폴더에_앉는다(차린폴더, tmp_path):
    """★ 2026-09-22 에 알게 되어 2026-10-08 에 고친 자리 (섹션 7).

    꾸러미에 든 `7_영상메타.csv` 는 **옛 판의 영상 21개**짜리다. 판독자는 `video_id` 로 조인해
    제목 · 태그 · 설명 · 채널을 보므로, 이 판의 영상이 없으면 **제목만 보고 판독**하게 된다
    (2판 240행의 영상 18개 중 16개가 없었다). 1차가 판마다 만들고, `데이터_넣기.py` 가 갈아 끼운다.
    여기서는 ① 갈아 끼우는가 ② **없으면 조용히 넘어가지 않는가** 둘을 본다.
    """
    sys.path.insert(0, str(SHARED / "tools"))
    import 데이터_넣기                                     # noqa: PLC0415

    # ★ 2026-10-28 — **사본에서** 한다. 갈아끼우기가 이제 `대장/지문.json` 을 다시 뜨고
    #   `대장/지문_이력.json` 을 만들므로, module 범위인 `차린폴더` 를 더럽히면
    #   뒤에 오는 시험이 파일 수를 세다 틀린다.
    사본 = tmp_path / "판독폴더사본"
    shutil.copytree(차린폴더, 사본)
    자리 = 사본 / "판독패키지" / "7_영상메타.csv"
    옛내용 = 자리.read_bytes()
    옛대장 = json.loads((사본 / "대장" / "지문.json").read_text(encoding="utf-8"))
    assert _지문검사(사본) == 0, "갈아 끼우기 전에는 통과해야 한다"

    # ① 없으면 그대로 두고 **말한다** (「못 찾음」 을 「없음」 으로 넘기지 않는다)
    빈자리 = tmp_path / "빈곳"
    빈자리.mkdir()
    말2 = 데이터_넣기.영상메타_갈아끼우기(빈자리 / "번들.xlsx", 사본)
    assert "없습니다" in 말2 and "제목만" in 말2, 말2
    assert 자리.read_bytes() == 옛내용

    # ② 1차 결과 옆에 있으면 갈아 끼운다
    원본 = tmp_path / "번들.xlsx"
    원본.write_bytes(b"x")                                # 이 시험은 갈아끼우기만 본다
    (tmp_path / "7_영상메타.csv").write_text(
        "video_id,video_title,video_tags,video_description,channel_title,published_at,atomic_rows"
        + chr(10) + "aaa,제목,,,채널,2026-01-01,3" + chr(10), encoding="utf-8-sig")
    말 = 데이터_넣기.영상메타_갈아끼우기(원본, 사본)
    assert "갈아 끼웠습니다" in 말 and "영상 1개" in 말, 말
    assert 자리.read_bytes() != 옛내용
    assert "aaa" in 자리.read_text(encoding="utf-8-sig")

    # ③ ★ 갈아 끼운 **뒤에도 지문검사가 통과해야 한다** (2026-10-28 · sky ㉯).
    #   전에는 여기서 반려가 났다 — 꾸러미가 **견본**의 지문을 떠 두는데
    #   갈아끼우기가 설계대로 그것을 이 판의 것으로 바꾸기 때문이다.
    #   그래서 **실제 1차를 돌린 판은 모두 판독이 헛반려됐다** (깨끗한 판 1, 판독A·판독B 둘 다).
    #   옛 시험 그릇은 견본을 그대로 쓰므로 갈리지 않아 이것을 한 번도 못 잡았다.
    assert "다시 떴습니다" in 말, 말
    assert _지문검사(사본) == 0, "갈아 끼운 뒤 지문검사가 반려했다 — 판독이 헛반려된다"

    # ④ 다시 뜬 사실이 **이력에 남아야** 한다 — 덮어쓴 것을 숨기지 않는다
    이력 = json.loads((사본 / "대장" / "지문_이력.json").read_text(encoding="utf-8"))
    assert 이력 and 이력[-1]["바뀐것"] == ["판독패키지/7_영상메타.csv"], 이력
    assert 이력[-1]["바뀐파일수"] == 1, 이력
    assert "데이터_넣기" in 이력[-1]["누가"], 이력
    새대장 = json.loads((사본 / "대장" / "지문.json").read_text(encoding="utf-8"))
    assert 새대장["뜬날"] == 옛대장["뜬날"], "뜬날을 오늘로 바꾸면 「처음부터 이랬다」 로 보인다"
    assert 새대장["다시뜬횟수"] == len(이력)
    assert 새대장["파일수"] == 옛대장["파일수"], "칸 수가 달라졌다 — 한 칸만 다시 떠야 한다"
    달라진것 = [k for k, v in 새대장["지문"].items() if 옛대장["지문"].get(k) != v]
    assert 달라진것 == ["판독패키지/7_영상메타.csv"], 달라진것


def test_지문을_다시_안_뜨면_판독이_헛반려된다(차린폴더, tmp_path):
    """★ 일부러 틀리게 — 2026-10-28 **전의 모습**을 되살려 정말 잡히는지 본다.

    갈아 끼운 뒤 대장의 그 칸을 **옛 견본 지문으로 되돌린다.** 그것이 고치기 전 모습이다.
    이때 지문검사가 반려해야 한다 — 반려하지 않으면 ③ 의 통과가 아무것도 재지 않은 것이다.
    """
    sys.path.insert(0, str(SHARED / "tools"))
    import 데이터_넣기                                     # noqa: PLC0415

    사본 = tmp_path / "되돌린폴더"
    shutil.copytree(차린폴더, 사본)
    원본 = tmp_path / "번들.xlsx"
    원본.write_bytes(b"x")
    (tmp_path / "7_영상메타.csv").write_text(
        "video_id,video_title,video_tags,video_description,channel_title,published_at,atomic_rows"
        + chr(10) + "bbb,딴제목,,,채널,2026-01-01,3" + chr(10), encoding="utf-8-sig")

    대장 = 사본 / "대장" / "지문.json"
    옛해시 = json.loads(대장.read_text(encoding="utf-8"))["지문"]["판독패키지/7_영상메타.csv"]
    데이터_넣기.영상메타_갈아끼우기(원본, 사본)
    assert _지문검사(사본) == 0

    적힌것 = json.loads(대장.read_text(encoding="utf-8"))
    assert 적힌것["지문"]["판독패키지/7_영상메타.csv"] != 옛해시, "다시 뜨지도 않았다"
    적힌것["지문"]["판독패키지/7_영상메타.csv"] = 옛해시        # ← 고치기 전 모습
    대장.write_text(json.dumps(적힌것, ensure_ascii=False, indent=1), encoding="utf-8")
    assert _지문검사(사본) == 1, "견본 지문을 되돌렸는데 지문검사가 통과했다 — 아무것도 안 재고 있다"


def test_안내서가_가리키는_그림이_다_있다(차린폴더):
    """★ 섹션 7a ③ (2026-10-08) — 안내서 63 의 그림 6개가 **옛 꾸러미부터 빠져 있어** 전부 깨져 있었다.

    글(`![…](캡쳐/01_전체화면.png)`)만 있고 파일이 없으면 실무자는 빈 자리를 본다.
    안내서 **바로 옆**에 있어야 그 상대경로가 맞는다 — 자리가 어긋나도 여기서 드러난다.
    ★ 가리키는 그림을 하나도 못 찾으면 그것도 실패다 (「못 찾음」 은 「없음」 이 아니다).
    """
    import re
    가이드 = 차린폴더 / "가이드"
    assert 가이드.is_dir(), "가이드 폴더가 없다"
    모두, 없음 = 0, []
    for 안내 in sorted(가이드.glob("*.md")):
        for g in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", 안내.read_text(encoding="utf-8")):
            if g.startswith(("http://", "https://")):
                continue
            모두 += 1
            if not (안내.parent / g).is_file():
                없음.append("%s → %s" % (안내.name, g))
    assert 모두 >= 6, "안내서가 가리키는 그림을 못 찾았다 (무늬가 안 맞나) — %d개" % 모두
    assert not 없음, "안내서가 가리키는 그림이 없다 — %s" % 없음[:5]


# ── 글이 다른 이름으로 가리키는 자리 (2026-10-29) ──────────────────────────────
_낱말 = "A-Za-z0-9가-힣_"
_가리키는무늬 = re.compile(
    "(?<![" + _낱말 + "./-])"
    "([" + _낱말 + "][" + _낱말 + "-]{1,30})/"
    "([" + _낱말 + "./-]{1,60}[.](?:json|csv|md|py|xlsx|txt|docx|png))")


def _어긋난이름(폴더: Path) -> set:
    """폴더의 글이 가리키는 자리 가운데 **그 파일이 다른 폴더 이름으로 들어 있는 것**.

    ★ 일부러 `꾸러미.이름대응()` 을 부르지 않는다 — 같은 함수로 재면 자기 답을 자기가 채점한다.
      여기서 따로 센 것이 안내문에 **다 적혀 있는지**만 본다.
    """
    있는것: dict = {}
    for q in 폴더.rglob("*"):
        if q.is_file() and "__pycache__" not in q.parts:
            있는것.setdefault(q.name, []).append(q.relative_to(폴더).as_posix())
    본것 = set()
    for 글 in sorted(폴더.rglob("*.md")):
        if 글.relative_to(폴더).parts[:1] == ("engine",):
            continue
        for m in _가리키는무늬.finditer(글.read_text(encoding="utf-8", errors="replace")):
            말한자리, 뒤 = m.group(1), m.group(2)
            if (폴더 / 말한자리 / 뒤).is_file() or (글.parent / 말한자리 / 뒤).is_file():
                continue
            자리들 = 있는것.get(뒤.rsplit("/", 1)[-1])
            if not 자리들:
                continue
            본것.add((말한자리, 자리들[0].rsplit("/", 1)[0]))
    return 본것


def _이름절(폴더: Path) -> str:
    글 = (폴더 / "0_먼저_읽으십시오.md").read_text(encoding="utf-8")
    i = 글.find("## ★ 글이 다른 이름으로 가리키는 자리")
    assert i >= 0, "안내문에 「글이 다른 이름으로 가리키는 자리」 절이 없다"
    return 글[i:]


@pytest.mark.parametrize("스킬이름", ["reading-voc-comments", "supervising-voc-disagreements"])
def test_스킬이_이름대응_절을_읽으라고_시킨다(스킬이름):
    """★ 2026-10-29 — 이름 대응을 안내문에 **적어 놓기만 하면 장식이다.**

    판독·감독 스킬의 `SKILL.md` 는 단계 3 에서 `판독패키지/0_최신결정_먼저.md` 를,
    단계 4 에서 프롬프트를 읽으라고 한다. `0_먼저_읽으십시오.md` 는 **읽으라고 하지 않았다** —
    그러니 판독자 AI 가 그 절을 볼 길이 없었다. 적어 놓고 안 읽히면 ③ 은 고쳐진 것이 아니다.
    그래서 단계 3-2 를 넣었고, 이 시험이 **그 단계가 사라지지 않게** 지킨다.
    ★ 절 이름은 안내문을 만드는 `꾸러미.readme()` 가 쓰는 것과 **같은 글자**여야 한다 —
      한쪽만 바뀌면 스킬이 없는 절을 가리킨다.
    """
    글 = (PLUGIN / "skills" / 스킬이름 / "SKILL.md").read_text(encoding="utf-8")
    절이름 = "★ 글이 다른 이름으로 가리키는 자리"
    assert "0_먼저_읽으십시오.md" in 글, "안내문을 읽으라는 말이 없다"
    assert 절이름 in 글, "가리킬 절 이름이 없다 — %s" % 절이름
    # 안내문을 만드는 쪽이 정말 그 이름으로 적는가 (두 자리가 어긋나면 없는 절을 가리킨다)
    만든것 = 꾸러미.readme("2_2차판독", 꾸러미.SPEC["2_2차판독"], ["보기.md"],
                       [("s9_group", "대장", ["topic_group_map.json"])])
    assert ("## " + 절이름) in 만든것, "안내문이 그 이름으로 절을 적지 않는다"


@pytest.mark.parametrize("어느", ["판독", "감독"])
def test_안내문이_이름_어긋난_자리를_다_밝힌다(차린폴더, 감독폴더, 어느):
    """★ 2026-10-29 — 작게 한 번 돌려 보고 나왔다. 판독A(claude)가 **실제 판독 중에** 걸렸다.

    기준 문서 셋이 대장을 `s9_group/topic_group_map.json` 으로 가리키는데 꾸러미에 들어가는
    자리는 `대장/topic_group_map.json` 이다. 그 어긋남으로 반려 1건과 계약 위반 24행이 났고,
    판독자는 자기가 맞춰도 될지 sky 에게 물어야 했다.

    원문은 고치지 않고(공통 규칙 7) 사본도 만들지 않고(공통 규칙 6) **안내문에 대응을 적는** 길을
    골랐으므로, 이 시험이 그 안내문이 **빠짐없이** 적혔는지 지킨다.
    ★ 하나도 못 찾으면 그것도 실패다 — 「못 찾음」 은 「없음」 이 아니다.
    """
    폴더 = 차린폴더 if 어느 == "판독" else 감독폴더
    찾은것 = _어긋난이름(폴더)
    assert len(찾은것) >= 3, "어긋난 이름을 못 찾았다 (무늬가 안 맞나) — %s" % sorted(찾은것)
    절 = _이름절(폴더)
    안적힌것 = [(ㄱ, ㄴ) for ㄱ, ㄴ in sorted(찾은것)
              if ("%s/" % ㄱ) not in 절 or ("%s/" % ㄴ if ㄴ else "./") not in 절]
    assert not 안적힌것, "안내문이 안 밝힌 이름 어긋남 — %s" % 안적힌것
    assert "s9_group/" in 절 and "대장/" in 절, "판독A 가 걸렸던 그 어긋남이 안 적혔다"
    # ★ 가리킨 쪽이 **정말 있는지**도 본다 — 없는 자리를 적으면 안내문이 거짓말을 한다
    for 줄 in 절.splitlines():
        if "->" not in 줄:
            continue
        오른쪽 = 줄.split("->", 1)[1].strip().rstrip("/")
        if 오른쪽 in ("", "."):
            continue
        assert (폴더 / 오른쪽).is_dir(), "안내문이 없는 자리를 가리킨다 — %s" % 오른쪽


def test_플러그인_판번호가_변경이력_맨_위와_같다():
    """★ 2026-10-26 — 2.0.0 동결 때 `plugin.json` 을 **안 고쳤다.** 판 번호가 `1.0.0` 그대로였고
    설명에 든 스킬도 **다섯**이었다 (대시보드가 빠졌다). 지키는 시험이 없어 아무도 몰랐다.

    `plugin.json` 은 Claude Code 가 이 꾸러미를 **알아보는 자리**다. 거기 적힌 판 번호가
    변경 이력의 맨 위와 다르면, 받은 사람은 옛 판을 쓰면서 새 판이라고 믿는다.
    """
    d = json.loads((REPO / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    줄들 = (REPO / "CHANGELOG.md").read_text(encoding="utf-8").split(chr(10))
    맨위 = next((s for s in 줄들 if s.startswith("## ")), "")
    번호 = 맨위[3:].split(" ")[0].strip()
    assert 번호, "CHANGELOG 맨 위에서 판 번호를 못 읽었다 — %r" % 맨위
    assert d.get("version") == 번호, (
        "plugin.json 판 번호 %r 가 변경 이력 맨 위 %r 와 다르다" % (d.get("version"), 번호))


def test_플러그인_설명이_든_스킬을_하나도_빠뜨리지_않는다():
    """설명은 사람이 「무엇이 들었나」 를 보는 자리다. 빠지면 그 스킬은 없는 셈이 된다."""
    d = json.loads((REPO / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    설명 = d.get("description", "")
    있는스킬 = sorted(p.name for p in (REPO / "plugin" / "skills").iterdir()
                  if p.is_dir() and (p / "SKILL.md").is_file())
    빠진것 = [s for s in 있는스킬 if s not in 설명]
    assert not 빠진것, "plugin.json 설명에 빠진 스킬 — %s" % 빠진것


def test_PL이슈_뽑기가_열_누락을_0건으로_돌려주지_않는다(tmp_path):
    """★ 2026-10-28 독립 점검 F07 — 「안전·위생이 0 건」 과 「분류할 열이 없다」 는 다르다.

    고치기 전 — `topic`·`status` 가 없으면 아래 고리가 **모든 행을 건너뛰어**
    머리만 있는 `PL이슈.csv` 를 만들고 **종료코드 0** 으로 끝났다 (실측).
    PL 이슈는 제품 안전 건이다 — 조용히 0 이 되어선 안 된다.

    ★ 이 구멍은 **옛 도구에도 있었다.** 옛 `PL이슈_뽑기.py` 76·80줄에 같은 코드가 있고
      우리 파일은 줄바꿈만 빼고 바이트가 같았다(고친 이력 0) — 옮기다 깨진 것이 아니라
      물려받은 것이다. 옛 실제 데이터는 89칸을 다 갖고 있어 터지지 않았다 (PL 213행).

    ★ 이 도구는 cwd 가 아니라 **자기 파일 위치**로 ROOT 를 잡는다. 그래서 사본을
      `<자리>/스크립트/` 에 두고 거기서 돌린다.
    """
    도구 = REPO / "plugin" / "shared" / "tools" / "PL이슈_뽑기.py"
    칸 = ["atomic_id", "topic", "status", "product_category", "atomic_voc",
         "original_voc", "cej", "sentiment_dir", "tee_emotion_score",
         "voc_total_score", "rootcause_problem", "rootcause_cause",
         "entity_role", "video_title", "video_url"]

    def 돌리기(머리줄: str, 줄들: list[str]):
        자리 = tmp_path / ("판_%d" % len(list(tmp_path.iterdir())))
        (자리 / "스크립트").mkdir(parents=True)
        사본 = 자리 / "스크립트" / 도구.name
        shutil.copyfile(도구, 사본)
        번들 = 자리 / "_판독패키지" / "_결과" / "master_final"
        번들.mkdir(parents=True)
        (번들 / "raw_voc.csv").write_text(
            머리줄 + chr(10) + chr(10).join(줄들) + chr(10),
            encoding="utf-8", newline=chr(10))
        r = subprocess.run([sys.executable, str(사본)], cwd=str(자리),
                           capture_output=True, text=True, encoding="utf-8")
        return r, 번들 / "PL이슈.csv"

    # ① 열이 없다 — 멈춰야 한다
    r, 낸것 = 돌리기("atomic_id,wrong_column", ["a-1,x", "a-2,y"])
    assert r.returncode != 0, (
        "열이 없는데 종료코드 0 으로 끝났다 — 「0 건」 과 구분되지 않는다:\n" + r.stdout)
    assert "꼭 필요한 열이 없습니다" in r.stdout, r.stdout
    assert not 낸것.exists(), "열이 없는데 PL이슈.csv 를 만들었다 (머리만 있는 0건 파일)"

    # ② 열이 있다 — 전처럼 돌아야 한다 (헛경보가 아님을 함께 확인한다)
    def 한줄(라벨, 상태):
        값 = {"atomic_id": "a-1", "topic": 라벨, "status": 상태,
             "tee_emotion_score": "3", "voc_total_score": "7"}
        return ",".join(값.get(c, "x") for c in 칸)

    r2, 낸것2 = 돌리기(",".join(칸),
                    [한줄("안전(화재·감전·누수)", "normal"),
                     한줄("위생/냄새", "normal"),
                     한줄("안전(화재·감전·누수)", "scope_excluded")])
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert 낸것2.exists(), "정상 입력인데 PL이슈.csv 를 안 만들었다"
    줄수 = len(낸것2.read_text(encoding="utf-8-sig").rstrip().split(chr(10)))
    assert 줄수 == 3, "안전 1 · 위생 1 이 뽑혀 머리까지 3줄이어야 한다 — %d줄" % 줄수


def test_3차마무리가_PL실패를_보고도_안_멈추지_않는다():
    """★ 2026-10-28 독립 점검 F07 — 실패 코드를 받고도 그냥 다음으로 갔다.

    시트_붙이기는 `PL이슈.csv` 가 없으면 「못 찾았습니다」 하고 조용히 건너뛴다.
    그래서 PL 뽑기가 실패하면 **★PL Issue 시트가 빠진 번들**이 「다 됐다」 로 나갔다.
    코드를 읽어 **그 자리에 멈추는 구문이 있는지** 본다.
    """
    글 = (REPO / "plugin" / "shared" / "tools" / "3차_마무리.py").read_text(encoding="utf-8")
    자리 = 글.find('_달리기("PL이슈_뽑기.py")')
    assert 자리 > 0, "PL이슈_뽑기 를 부르는 자리를 못 찾았다 — 못 찾음은 통과가 아니다"
    뒤 = 글[자리:자리 + 700]
    assert "if 코드" in 뒤, "PL 뽑기 실패를 보고도 멈추지 않는다 (종료코드를 안 본다)"
    assert "return 코드" in 뒤, "실패 코드를 그대로 돌려주지 않는다"
# ── 칸이 몇 개인가 — 판독자가 잣대를 못 받았다 (2026-10-29) ────────────────────────────


def _칸들():
    """파생·사이드카·계약 칸을 **세 자리에서 각각 긁어** 돌려준다."""
    sys.path.insert(0, str(PLUGIN / "engine"))
    from src.voc_rebuild import TARGET_COLUMNS                      # noqa: PLC0415
    sys.path.insert(0, str(SHARED / "tools"))
    import 데이터_넣기                                                # noqa: PLC0415
    return (list(TARGET_COLUMNS), 꾸러미.파생칸(PLUGIN / "engine"),
            꾸러미.사이드카칸(SHARED), list(데이터_넣기.SEC_COLS),
            꾸러미.분류글_칸수(SHARED))


def test_파생칸을_손으로_적지_않고_엔진에서_센다():
    """★ 안내문의 숫자가 **엔진과 어긋나지 않게** 한다.

    파생 칸은 `data_contract.materialize_dashboard_columns` 가 만든다. 엔진이 아홉째
    파생 칸을 만들면 안내문의 「파생 8칸」 이 거짓이 된다 — 그때 이 시험이 **실패해야 한다.**
    사이드카도 `데이터_넣기.SEC_COLS` **한 자리**에서만 정한다 (같은 것이 두 벌 금지).
    """
    계약, 파생, 사이드카, SEC, 분류칸 = _칸들()
    assert len(계약) == 66, "계약 칸이 66이 아니다 — %d" % len(계약)
    assert 사이드카 == SEC, "사이드카를 두 자리에서 다르게 적었다 — %s / %s" % (사이드카, SEC)
    assert len(파생) >= 5, "파생 칸을 못 셌다 — %s (못 찾음은 통과가 아니다)" % 파생
    겹침 = [c for c in 파생 + 사이드카 if c in 계약]
    assert not 겹침, "계약 밖이라던 칸이 계약 안에 있다 — %s" % 겹침


def test_파생칸을_못_세면_크게_실패한다(tmp_path):
    """★ 「못 찾음」 을 빈 목록으로 돌려주면 안내문이 **조용히 빈 절**을 적는다."""
    with pytest.raises(SystemExit):
        꾸러미.파생칸(tmp_path)                       # 엔진이 없는 자리
    with pytest.raises(SystemExit):
        꾸러미.사이드카칸(tmp_path)                    # 도구가 없는 자리
    # 빈 목록을 주면 절을 적지 않고 멈춘다 (빈 절을 적어 「알려 줬다」 가 되면 안 된다)
    with pytest.raises(SystemExit):
        꾸러미.칸사슬_절([], ["na_class"], 71)
    with pytest.raises(SystemExit):
        꾸러미.칸사슬_절(["validity"], ["na_class"], 0)
    with pytest.raises(SystemExit):
        꾸러미.분류글_칸수(tmp_path)                    # 분류 글이 없는 자리


@pytest.mark.parametrize("어느", ["판독", "감독"])
def test_안내문이_칸_사슬을_다_밝힌다(차린폴더, 감독폴더, 어느):
    """★ 2026-10-29 — 판독A 가 「1차 데이터가 74칸인데 계약은 66칸」 이라고 적었다.

    **둘 다 사실이었다.** 칸은 차수마다 늘어난다 — 1차 csv 66(계약) → 번들 74(+파생 8)
    → 판독자 79(+사이드카 5) → 최종 89(+2·3차 10). 칸이 틀린 것이 아니라 **잣대를 못 준
    것**이었다. 그리고 파생 8칸 중 7개는 기준 문서 어디에도 없어서, 판독자는 **보라는 말도
    보지 말라는 말도 없는 칸 7개**를 받고 있었다.
    → 그래서 안내문에 사슬과 **칸 이름 전부**를 적는다. 하나라도 빠지면 이 시험이 실패한다.
    """
    작업 = 차린폴더 if 어느 == "판독" else 감독폴더
    글 = (작업 / "0_먼저_읽으십시오.md").read_text(encoding="utf-8")
    i = 글.find("## " + 꾸러미.칸사슬_절이름)
    assert i >= 0, "안내문에 칸 사슬 절이 없다 — %s" % 꾸러미.칸사슬_절이름
    절 = 글[i:]
    계약, 파생, 사이드카, _, 분류칸 = _칸들()
    # ① 사슬의 네 수가 **센 것과 같은가** (손으로 적은 수가 아니다)
    for 수 in (len(계약), len(계약) + len(파생), len(계약) + len(파생) + len(사이드카)):
        assert "%d칸" % 수 in 절, "사슬에 %d칸 이 없다" % 수
    # ② 칸 이름이 **하나도 빠지지 않았는가**
    빠진것 = [c for c in 파생 + 사이드카 if c not in 절]
    assert not 빠진것, "안내문이 계약 밖 칸을 다 적지 않았다 — %s" % 빠진것
    # ③ 「보지 않는다」 와 「계약 위반이 아니다」 를 말하는가
    assert "보지 않습니다" in 절, "파생 칸을 보지 말라는 말이 없다"
    assert "계약 위반" in 절, "칸 수가 많아도 계약 위반이 아니라는 말이 없다"


@pytest.mark.parametrize("스킬이름", ["reading-voc-comments", "supervising-voc-disagreements"])
def test_스킬이_칸사슬_절을_읽으라고_시킨다(스킬이름):
    """★ 적어 놓기만 하면 장식이다 — 이름 대응 때와 **같은 병**을 막는다.

    절 이름은 안내문을 만드는 `꾸러미.칸사슬_절이름` 과 **같은 글자**여야 한다.
    한쪽만 바뀌면 스킬이 없는 절을 가리킨다.
    """
    글 = (PLUGIN / "skills" / 스킬이름 / "SKILL.md").read_text(encoding="utf-8")
    assert 꾸러미.칸사슬_절이름 in 글, "칸 사슬 절을 가리키지 않는다 — %s" % 꾸러미.칸사슬_절이름
    assert "계약 위반" in 글, "칸 수가 많아도 계약 위반이 아니라는 말이 없다"


def test_1차_확인이_어느_파일의_칸인지_찍는다():
    """★ 전에는 「칸 66개 (계약 66)」 만 찍어 **무엇을 본 것인지** 알 수 없었다.

    그래서 판독자가 번들 엑셀(74칸)과 이 출력(66칸)을 부딪히게 읽었다.
    """
    글 = (PLUGIN / "skills" / "running-voc-engine" / "scripts" / "1차_돌리기.py").read_text(
        encoding="utf-8")
    assert "csv자리.name" in 글, "어느 파일의 칸인지 찍지 않는다"
    assert "번들 엑셀 raw_voc" in 글, "번들 쪽 칸이 더 많다는 말이 없다"
    assert "계약 위반" in 글, "칸 수가 많아도 계약 위반이 아니라는 말이 없다"

