# -*- coding: utf-8 -*-
"""총괄 자리를 차린다 — 옛 `voc_secondary/` 와 그 안의 판 폴더 모양 그대로.

    <총괄자리>/s9_group/       대장
    <총괄자리>/<판이름>/        ★ 총괄 도구 42개가 도는 자리 · 기준서 · 프롬프트 · 엔진 · 감독 꾸러미 zip

★ 차리는 일은 공통 한 벌(`shared/lib/총괄자리.py` · `꾸러미.py`)이 한다. 감독 꾸러미 zip 은 감독 스킬과 같은 코드로 만든다.
★ 이미 있는 파일은 **건드리지 않는다.** 판 중간에 다시 돌려도 안전하다.

쓰기
    python <이 스킬>/scripts/총괄자리_차리기.py <총괄자리> <판이름>
    예) python .../총괄자리_차리기.py "<원하는 자리>/VoC_총괄" 3판
"""
from __future__ import annotations

import sys
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]


def _찾기(이름: str) -> Path:
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름


def _옆스킬(이름: str) -> Path:
    """판독·감독 스킬의 references — 플러그인 안에서는 옆 스킬, 낱개로 꾸리면 이 스킬 안 skills/<이름>."""
    for d in (스킬 / "skills" / 이름, 스킬.parent / 이름):
        if d.is_dir():
            return d
    return 스킬.parent / 이름


공통 = _찾기("shared")
엔진 = _찾기("engine")
판독 = _옆스킬("reading-voc-comments")
감독 = _옆스킬("supervising-voc-disagreements")
sys.path.insert(0, str(공통 / "lib"))
import 자리_가드  # noqa: E402
import 총괄자리  # noqa: E402


def 차리기(총괄: Path, 판이름: str) -> dict:
    return 총괄자리.차리기(Path(총괄), 판이름, 공통, 엔진, 판독 / "references", 감독 / "references", 감독 / "assets")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    총괄자리 = Path(sys.argv[1]).resolve()
    # ★ 2026-11-04 — **저장소 안이면 여기서 멈춘다** (결정 0013 의 가드).
    자리_가드.자리_확인하고_멈추기(총괄자리, "총괄자리")
    셈 = 차리기(총괄자리, sys.argv[2])
    print("  총괄 자리 — %s" % 셈["판"])
    print("  차림 %d개 · 이미 있어 그대로 둠 %d개" % (셈["차림"], 셈["이미있음"]))
    if "감독꾸러미_파일수" in 셈:
        print("  감독 꾸러미 zip — %d개 (감독 스킬과 같은 한 벌)" % 셈["감독꾸러미_파일수"])
    if 셈["못찾음"]:
        print("  ✗ 재료를 못 찾았습니다 %d개 — 스킬이 온전하지 않습니다:" % len(셈["못찾음"]))
        for x in 셈["못찾음"][:10]:
            print("     · %s" % x)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
