# -*- coding: utf-8 -*-
"""총괄 자리를 차린다 — 옛 `outputs/voc_secondary/` 와 그 안의 판 폴더(`_2판/`) 모양 그대로 (섹션 5 · 2026-09-21).

★ 모양
    <총괄자리>/
        s9_group/                 대장 4개 — 4차_반영 의 그룹_맞추기 가 판 폴더의 부모에서 찾는다 (옛 voc_secondary/s9_group)
        <판>/                     ★ 총괄 도구가 도는 자리 (옛 _2판)
            *.py                  총괄 도구 41개 (매 판 입구 5개에서 닿는 것 — 옛 관리 도구 4개는 뺐다, sky 결정)
            _판독패키지/            기준서 8 · 영상메타 · 판독/이어서/감독 프롬프트 · _기준/출력칸목록.txt
            공통/어휘.json
            15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx
            _배포/VoC_3_3차감독.zip  ★ 3차_준비 가 이것을 풀어 감독 폴더를 차린다 — 감독 스킬과 **같은 한 벌**(꾸러미.py)로 만든다
            _배포/VoC_데이터_안내.xlsx
            engine/
★ 판 폴더 안에는 s9_group 을 두지 않는다 — 2판이 그랬다. 3차 도구는 판 폴더 기준으로 대장을 찾고, 없으면 2차 번들의 값을
  그대로 쓴다 (2판 결과와 얼린 기준 모두 topic_group 빈 행 0 을 확인했다).
★ 이미 있는 파일은 건드리지 않는다. 다시 돌려도 안전하다.
"""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

import 꾸러미

_기준서 = 꾸러미._기준서


def 판재료(공통: Path, 엔진: Path, 판독참고: Path, 감독참고: Path) -> list:
    """(재료, 판 폴더 안 자리)."""
    return ([(p, p.name) for p in sorted((공통 / "tools").glob("*.py"))]
            + [(공통 / "standards" / n, "_판독패키지/" + n) for n in _기준서]
            + [(공통 / "data" / "7_영상메타.csv", "_판독패키지/7_영상메타.csv"),
               (판독참고 / "0_붙여넣을_프롬프트_도구형.md", "_판독패키지/0_붙여넣을_프롬프트_도구형.md"),
               (판독참고 / "0_붙여넣을_프롬프트_이어서.md", "_판독패키지/0_붙여넣을_프롬프트_이어서.md"),
               (감독참고 / "0_붙여넣을_프롬프트_감독.md", "_판독패키지/0_붙여넣을_프롬프트_감독.md"),
               (공통 / "common" / "출력칸목록.txt", "_판독패키지/_기준/출력칸목록.txt"),
               (공통 / "common" / "어휘.json", "공통/어휘.json"),
               (공통 / "common" / "15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx", "15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx"),
               (공통 / "common" / "VoC_데이터_안내.xlsx", "_배포/VoC_데이터_안내.xlsx")]
            + [(p, "engine/" + p.relative_to(엔진).as_posix()) for p in sorted(엔진.rglob("*"))
               if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")])


def 감독꾸러미_zip(낼곳: Path, 공통: Path, 엔진: Path, 감독참고: Path, 감독틀: Path) -> int:
    """감독 스킬과 같은 한 벌로 감독 폴더를 차린 뒤 zip 으로 묶는다. 담은 파일 수를 돌려준다."""
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "감독"
        셈 = 꾸러미.차리기(d, "3_3차감독", 공통, 엔진, 감독참고, 감독틀)
        if 셈["못찾음"]:
            raise FileNotFoundError("감독 꾸러미 재료를 못 찾았다 — %s" % 셈["못찾음"][:5])
        파일 = sorted(p for p in d.rglob("*") if p.is_file())
        낼곳.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(낼곳, "w", zipfile.ZIP_DEFLATED) as z:
            for p in 파일:
                z.write(p, p.relative_to(d).as_posix())
        return len(파일)


def 차리기(총괄자리: Path, 판이름: str, 공통: Path, 엔진: Path, 판독참고: Path, 감독참고: Path, 감독틀: Path) -> dict:
    총괄자리 = Path(총괄자리)
    판 = 총괄자리 / 판이름
    셈 = {"차림": 0, "이미있음": 0, "못찾음": [], "판": str(판)}
    for 원, 자리 in ([(공통 / "registry" / n, "../s9_group/" + n) for n in
                    ("topic_group_map.json", "secondary_topics.json", "secondary_enums.json", "topic_registry.json")]
                   + 판재료(공통, 엔진, 판독참고, 감독참고)):
        if not Path(원).is_file():
            셈["못찾음"].append(자리)
            continue
        q = (판 / 자리).resolve() if 자리.startswith("../") else 판 / 자리
        if q.exists():
            셈["이미있음"] += 1
            continue
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(원, q)
        셈["차림"] += 1
    zp = 판 / "_배포" / "VoC_3_3차감독.zip"
    if zp.exists():
        셈["이미있음"] += 1
    else:
        셈["감독꾸러미_파일수"] = 감독꾸러미_zip(zp, 공통, 엔진, 감독참고, 감독틀)
        셈["차림"] += 1
    return 셈
