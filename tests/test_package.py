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
    # + 99_1차_실행조건_원문 (섹션 7 ③ · docs/sources 에서 옮겨 왔다 — 1차 작업 폴더에 들어가므로 한 벌)
    assert len(파일) == 66, len(파일)
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
    재료 = [Path(원) for 원, _ in 차리기.전체_차림표() + 감독차리기.전체_차림표() + 총괄재료 + 대장 + 일차재료]
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


def test_차리면_꾸러미와_같은_84개가_된다(차린폴더):
    파일 = [p for p in 차린폴더.rglob("*") if p.is_file()]
    assert len(파일) == 84, len(파일)          # 옛 꾸러미 80 + 새 판 + 최신결정_검사.py + 엔진 +2 (섹션 7 ① — 옛 28개 자리 → 도구가 부르는 30개)
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


def test_감독폴더는_68개이고_편향검사가_없다(감독폴더):
    파일 = [p for p in 감독폴더.rglob("*") if p.is_file()]
    assert len(파일) == 68, len(파일)          # 옛 감독 꾸러미 66개 − 편향검사.py + 새 판 + 엔진 +2 (섹션 7 ①)
    assert not (감독폴더 / "스크립트" / "편향검사.py").exists(), "감독 폴더에 편향검사가 있다 (98: 아예 없다)"
    assert (감독폴더 / "프롬프트" / "0_붙여넣을_프롬프트_감독.md").is_file()


def test_감독폴더에_정답지와_감독입력을_만들지_않는다(감독폴더):
    # ★ 익명화 — 감독자가 A·B 가 누구인지 알면 편든다. 입력은 총괄이 넣는다
    for 금지 in ("s13_judge", "_총괄만", "ab_mapping.json", "스크립트/make_judge_input.py",
               "스크립트/build_master.py", "스크립트/3차_준비.py", "스크립트/3차_마무리.py"):
        assert not (감독폴더 / 금지).exists(), 금지
    assert not list(감독폴더.rglob("ab_mapping*")), "정답지가 들어갔다"
    assert not list(감독폴더.rglob("*_bundle")), "2차 번들이 들어갔다"


def test_감독폴더_안내문은_옛_꾸러미와_편향검사_한_줄과_새_판_한_줄만_다르다(감독폴더):
    옛 = BASELINE / "원본사본" / "꾸러미" / "VoC_3_3차감독" / "0_먼저_읽으십시오.md"
    assert 옛.is_file(), "옛 감독 꾸러미 사본을 못 찾았다 — %s" % 옛
    a = 옛.read_text(encoding="utf-8").splitlines()
    b = (감독폴더 / "0_먼저_읽으십시오.md").read_text(encoding="utf-8").splitlines()
    새판 = [x for x in b if "0_최신결정_먼저.md" in x]
    assert len(새판) == 1, 새판          # 섹션 5b 의 새 판 — 옛 꾸러미에 없던 한 줄
    # 섹션 7 ① — engine/ 줄은 이제 도구가 부르는 엔진 파일을 코드로 따라가 뽑은 목록이다 (옛 꾸러미와 다르다 · 그 목록과 같아야 한다)
    엔진줄 = [x.strip() for x in b if x.strip().startswith("engine/")]
    assert 엔진줄 == ["engine/" + n for n in 꾸러미.꾸러미엔진(PLUGIN / "engine")], 엔진줄[:5]
    옛것 = [x for x in a if "편향검사.py" not in x and not x.strip().startswith("engine/")]
    assert 옛것 == [x for x in b if x not in 새판 and not x.strip().startswith("engine/")]


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
    assert len(도구) == 42, len(도구)          # 41 + 최신결정_검사.py (섹션 5b)
    for 옛관리 in ("마무리_이력정리.py", "정본_맞추기.py", "make_zip.py", "박힌말_검사.py", "5차기준_검사.py"):
        assert 옛관리 not in 도구, "옛 관리 도구가 들어갔다 — %s (sky: 새 방식으로 대신)" % 옛관리
    assert (tmp_path / "총괄" / "s9_group" / "topic_group_map.json").is_file(), "대장은 판 폴더의 부모에"
    assert not (판 / "s9_group").exists(), "판 폴더 안에는 대장이 없다 (2판이 그랬다)"
    import zipfile
    with zipfile.ZipFile(판 / "_배포" / "VoC_3_3차감독.zip") as z:
        이름 = [n for n in z.namelist() if not n.endswith("/")]
    assert len(이름) == 68 and "스크립트/편향검사.py" not in 이름, "감독 꾸러미는 감독 스킬과 한 벌이어야 한다"
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

    자리 = 차린폴더 / "판독패키지" / "7_영상메타.csv"
    옛내용 = 자리.read_bytes()

    # ① 1차 결과 옆에 있으면 갈아 끼운다
    원본 = tmp_path / "번들.xlsx"
    원본.write_bytes(b"x")                                # 이 시험은 갈아끼우기만 본다
    (tmp_path / "7_영상메타.csv").write_text(
        "video_id,video_title,video_tags,video_description,channel_title,published_at,atomic_rows\n"
        "aaa,제목,,,채널,2026-01-01,3\n", encoding="utf-8-sig")
    말 = 데이터_넣기.영상메타_갈아끼우기(원본, 차린폴더)
    assert "갈아 끼웠습니다" in 말 and "영상 1개" in 말, 말
    assert 자리.read_bytes() != 옛내용
    assert "aaa" in 자리.read_text(encoding="utf-8-sig")

    # ② 없으면 그대로 두고 **말한다** (「못 찾음」 을 「없음」 으로 넘기지 않는다)
    자리.write_bytes(옛내용)
    빈자리 = tmp_path / "빈곳"
    빈자리.mkdir()
    말2 = 데이터_넣기.영상메타_갈아끼우기(빈자리 / "번들.xlsx", 차린폴더)
    assert "없습니다" in 말2 and "제목만" in 말2, 말2
    assert 자리.read_bytes() == 옛내용
