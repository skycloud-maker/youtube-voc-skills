# -*- coding: utf-8 -*-
"""기준서 · 택소노미 · Enum 은 `plugin/shared/standards/` 에 **한 벌만** 있는가 (섹션 3).

★ 왜 — 옛 저장소에서 같은 기준서가 이름 둘(`1a_` · `21a_`)로 13벌까지 퍼졌고,
  한 벌만 고쳐 판이 갈렸다 (2026-09-18 에 5벌을 맞췄다). 이름만 보고 짝을 찾던 옛 검사기는
  이름이 다른 쌍둥이를 「짝 없음」 으로 보고 조용히 넘어갔다.

보는 것
  ① 기록과 같은가 — `출처.json` 의 해시와 지금 파일이 같다. 고쳤으면 이유를 적고 해시를 갱신한다.
  ② 한 벌인가 — 저장소 어디에도 같은 내용 · 앞 번호만 다른 같은 이름의 파일이 없다.
  ③ 줄바꿈이 LF 한 가지인가.
  ④ 기준 정답이 이 기준서로 만들어졌는가 — 기준 자리의 2판 사본 `_판독패키지` 와 같다.
     기준서를 고치면 여기서 멈춘다: 기준 정답을 다시 만들지 정한 뒤 넘어간다.
★ 「못 찾음」 은 통과가 아니다 — 기준서가 0개거나 기준 자리가 없으면 실패한다.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import BASELINE, REPO, SHARED  # noqa: E402

기준서 = SHARED / "standards"
출처 = json.loads((기준서 / "출처.json").read_text(encoding="utf-8"))
# 한 벌 검사에서 빼는 자리 — 생성물(dist/)은 섹션 6 의 조립 검사가 원본과 대조한다
안보는곳 = {".git", "dist", "__pycache__", ".pytest_cache", ".claude"}


def _문서들() -> list[Path]:
    return sorted(p for p in 기준서.iterdir() if p.is_file() and p.name != "출처.json")


def 뿌리이름(이름: str) -> str:
    """앞 번호를 뗀 이름 — `21a_기준문서_정본_1부.md` → `기준문서_정본_1부.md`"""
    return re.sub(r"^\d+[a-z]?_", "", 이름)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_기준서가_있다():
    # 원래 8 + 새 판 0_최신결정_먼저.md (섹션 5b)
    assert len(_문서들()) == len(출처["파일"]) == 9, [p.name for p in _문서들()]


@pytest.mark.parametrize("이름", sorted(출처["파일"]))
def test_기록과_같다(이름):
    p = 기준서 / 이름
    assert p.is_file(), "기준서를 못 찾았다 — %s" % p
    b = p.read_bytes()
    assert b"\r" not in b, "줄바꿈이 LF 한 가지가 아니다 — %s" % 이름
    assert _sha(b) == 출처["파일"][이름]["지금_sha256"], (
        "%s 가 기록과 다르다. 일부러 고쳤다면 출처.json 의 `고친_이력` 에 이유를 적고 "
        "`지금_sha256` 을 갱신하라." % 이름)


def test_옛_기준서는_8개_새_판은_하나():
    옛것 = [n for n, v in 출처["파일"].items() if v["원본_sha256"]]
    새것 = [n for n, v in 출처["파일"].items() if not v["원본_sha256"]]
    assert len(옛것) == 8 and 새것 == ["0_최신결정_먼저.md"], (옛것, 새것)
    assert 출처["파일"]["0_최신결정_먼저.md"].get("새로_씀"), "새 판은 왜 새로 썼는지 적는다"


def test_이름이_다른_쌍둥이를_알아본다():
    # 검사기를 먼저 시험한다 — 옛 검사기가 놓친 바로 그 경우
    assert 뿌리이름("21a_기준문서_정본_1부.md") == 뿌리이름("1a_기준문서_정본_1부.md")
    assert 뿌리이름("25_판정대상_컬럼분류.md") == 뿌리이름("6_판정대상_컬럼분류.md")
    assert 뿌리이름("2_택소노미.md") != 뿌리이름("9_택소노미_2차확장.md")


def test_저장소에_한_벌만_있다():
    원이름 = {뿌리이름(p.name): p.name for p in _문서들()}
    원내용 = {_sha(p.read_bytes()): p.name for p in _문서들()}
    본것, 걸림 = 0, []
    for p in REPO.rglob("*"):
        rel = p.relative_to(REPO)
        if not p.is_file() or 안보는곳 & set(rel.parts) or p.parent == 기준서:
            continue
        본것 += 1
        if 뿌리이름(p.name) in 원이름:
            걸림.append("이름 쌍둥이: %s  ↔ %s" % (rel.as_posix(), 원이름[뿌리이름(p.name)]))
        b = p.read_bytes().replace(b"\r\n", b"\n")
        if _sha(b) in 원내용:
            걸림.append("내용 쌍둥이: %s  ↔ %s" % (rel.as_posix(), 원내용[_sha(b)]))
    assert 본것 > 0, "훑은 파일이 0개 — 통과가 아니다"
    assert not 걸림, "기준서 사본이 저장소에 또 있다 — plugin/shared/standards/ 를 가리킬 것:\n" + "\n".join(걸림)


# 옛 저장소에서 온 기준서만 — 새 판(원본_sha256 이 없는 것)은 기준 정답을 만들 때 없었다
@pytest.mark.parametrize("이름", sorted(n for n, v in 출처["파일"].items() if v["원본_sha256"]))
def test_기준_정답이_이_기준서로_만들어졌다(이름):
    사본 = BASELINE / "원본사본" / "2판" / "_판독패키지" / 이름
    assert 사본.is_file(), "기준 자리의 기준서를 못 찾았다 — %s" % 사본
    assert 사본.read_bytes().replace(b"\r\n", b"\n") == (기준서 / 이름).read_bytes(), (
        "%s 가 기준 정답을 만들 때 쓴 판과 다르다. 기준 정답을 다시 만들지(tests/baseline/기준_만들기.py) "
        "정한 뒤 이 시험을 고친다." % 이름)
