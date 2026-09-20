# -*- coding: utf-8 -*-
"""꾸러미 재료와 판독 폴더 차리기 시험 (섹션 4 · 2026-09-21 교차점검에서 만들었다).

★ 왜 이제 만들었나 — `plugin/shared/출처_꾸러미.json` 이 「고치면 tests/test_package.py 가 실패한다」 고
  적어 두었는데 그 시험이 **없었다.** 기준서 8종만 지켜지고 도구 21 · 대장 4 · 안내서 4 · 엔진 28 등
  70개는 조용히 갈려도 아무도 몰랐다.

보는 것
  ① 출처 기록의 해시 = 지금 파일 (70개)
  ② 차림표의 재료가 모두 있고, 모두 출처 기록에 적혀 있다 (빠진 재료 · 안 쓰는 기록 0)
  ③ 폴더를 차리면 옛 꾸러미와 같은 80개가 되고, 지문에 engine 이 들어간다
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
from paths import PLUGIN, REPO, SHARED  # noqa: E402

스킬 = PLUGIN / "skills" / "reading-voc-comments"
sys.path.insert(0, str(스킬 / "scripts"))
import 판독폴더_차리기 as 차리기  # noqa: E402

꾸러미출처 = json.loads((SHARED / "출처_꾸러미.json").read_text(encoding="utf-8"))
기준서출처 = json.loads((SHARED / "standards" / "출처.json").read_text(encoding="utf-8"))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_출처_기록이_실제_파일과_같다():
    파일 = 꾸러미출처["파일"]
    assert len(파일) == 70, len(파일)
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
    재료 = [Path(원) for 원, _ in 차리기.전체_차림표()]
    없음 = [p for p in 재료 if not p.is_file()]
    assert not 없음, "차림표가 가리키는 재료가 없다 — %s" % [str(p) for p in 없음[:5]]
    적힌것 = set(꾸러미출처["파일"]) | {("plugin/shared/standards/" + n) for n in 기준서출처["파일"]}
    쓰는것 = {p.resolve().relative_to(REPO).as_posix() for p in 재료}
    assert not (쓰는것 - 적힌것), "출처 기록에 없는 재료를 쓴다 — %s" % sorted(쓰는것 - 적힌것)[:5]
    assert not (적힌것 - 쓰는것), "기록만 있고 아무도 안 쓰는 파일 — %s" % sorted(적힌것 - 쓰는것)[:5]


@pytest.fixture(scope="module")
def 차린폴더(tmp_path_factory):
    d = tmp_path_factory.mktemp("판독폴더")
    셈 = 차리기.차리기(d)
    assert not 셈["못찾음"], 셈["못찾음"]
    return d


def test_차리면_꾸러미와_같은_80개가_된다(차린폴더):
    파일 = [p for p in 차린폴더.rglob("*") if p.is_file()]
    assert len(파일) == 80, len(파일)
    for 자리 in ("스크립트/자가점검.py", "판독패키지/1a_기준문서_정본_1부.md", "프롬프트/0_붙여넣을_프롬프트_도구형.md",
                "대장/지문.json", "0_먼저_읽으십시오.md", "engine/src/voc_rebuild/engine.py"):
        assert (차린폴더 / 자리).is_file(), 자리


def test_지문에_엔진이_들어간다(차린폴더):
    지문 = json.loads((차린폴더 / "대장" / "지문.json").read_text(encoding="utf-8"))
    엔진 = [k for k in 지문["지문"] if k.startswith("engine/")]
    assert len(엔진) == 25, len(엔진)
    assert 지문["파일수"] == len(지문["지문"]) == 63, 지문["파일수"]


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
