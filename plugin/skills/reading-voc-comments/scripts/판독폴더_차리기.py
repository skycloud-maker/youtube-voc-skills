# -*- coding: utf-8 -*-
"""2차 판독 작업 폴더를 차린다 — 옛 판독 꾸러미(VoC_2_2차판독.zip)를 푼 것과 같은 모양으로.

★ 왜 (sky 2026-09-18 결정 「폴더 차려 주고 원래 프롬프트 그대로」)
  판독 프롬프트(references/0_붙여넣을_프롬프트_도구형.md)와 도구들은 이 모양의 폴더를
  전제로 쓰였고, 그 모양에서 검증됐다. 모양을 그대로 차려 주면 한 글자도 고치지 않고 돈다.

★ 차리는 일은 공통 한 벌(`shared/lib/꾸러미.py`)이 한다 — 감독 스킬과 같은 코드다 (2026-09-21).
★ 이미 있는 파일은 **건드리지 않는다.** 없는 것만 채운다. 다시 돌려도 안전하다.

쓰기
    python <이 스킬>/scripts/판독폴더_차리기.py <작업 폴더>
끝나면 차린 것 · 이미 있던 것 · 못 찾은 재료 수를 알린다. 못 찾은 재료가 있으면 종료코드 1.
"""
from __future__ import annotations

import sys
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]
꾸러미이름 = "2_2차판독"


def _찾기(이름: str) -> Path:
    """공통 재료 자리 — 플러그인 안에서는 ../../<이름>, 낱개 스킬로 꾸리면 스킬 안 <이름>."""
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름          # 없으면 아래에서 「못 찾은 재료」 로 드러난다


공통 = _찾기("shared")
엔진 = _찾기("engine")
sys.path.insert(0, str(공통 / "lib"))
import 꾸러미  # noqa: E402
import 자리_가드  # noqa: E402


def 전체_차림표():
    return 꾸러미.전체_차림표(꾸러미이름, 공통, 엔진, 스킬 / "references", 스킬 / "assets")


def 차리기(작업: Path) -> dict:
    return 꾸러미.차리기(Path(작업), 꾸러미이름, 공통, 엔진, 스킬 / "references", 스킬 / "assets")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    작업 = Path(sys.argv[1]).resolve()
    # ★ 2026-11-04 — **저장소 안이면 여기서 멈춘다** (결정 0013 의 가드).
    자리_가드.자리_확인하고_멈추기(작업, "판독 폴더")
    셈 = 차리기(작업)
    print("  판독 폴더 — %s" % 작업)
    print("  차림 %d개 · 이미 있어 그대로 둠 %d개" % (셈["차림"], 셈["이미있음"]))
    if 셈["못찾음"]:
        print("  ✗ 재료를 못 찾았습니다 %d개 — 스킬이 온전하지 않습니다:" % len(셈["못찾음"]))
        for x in 셈["못찾음"][:10]:
            print("     · %s" % x)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
