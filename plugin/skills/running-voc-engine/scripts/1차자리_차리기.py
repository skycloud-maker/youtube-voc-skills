# -*- coding: utf-8 -*-
"""1차 실행 자리를 차린다 — 저장소 **밖**에 엔진 사본과 설정을 둔다.

    <1차자리>/0_먼저_읽으십시오.md · 99_1차_실행조건_원문.md · engine/ · engine/config/settings.yaml · 결과/

★ 왜 밖인가 — 1차 엔진은 결과를 **자기 폴더 아래**(`data/` · `outputs/`)에 쓴다. 저장소 안에서 돌리면
  엔진 지문검사가 깨진다 (2026-10-08 실제로 겪었다).
★ 차리는 일은 공통 한 벌(`shared/lib/일차자리.py`)이 한다 — 모듈 이름은 숫자로 시작할 수 없어 「일차자리」 다.
★ 이미 있는 파일은 **건드리지 않는다.** 중간에 다시 돌려도 안전하다.

쓰기
    python <이 스킬>/scripts/1차자리_차리기.py <1차자리>
    예) python .../1차자리_차리기.py "<원하는 자리>/VoC_1차"
"""
from __future__ import annotations

import sys
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]


def _찾기(이름: str) -> Path:
    """스킬 안 사본 → 플러그인 옆 한 벌 차례로 찾는다 (낱개로 꾸리면 스킬 안에 들어 있다)."""
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름


공통 = _찾기("shared")
엔진 = _찾기("engine")
sys.path.insert(0, str(공통 / "lib"))
import 일차자리 as 자리모듈  # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    자리 = Path(sys.argv[1]).resolve()
    차림, 그대로 = 자리모듈.차리기(자리, 공통, 엔진, Path(__file__).resolve().parent)
    print("  1차 실행 자리 — %s" % 자리)
    print("  차림 %d개 · 이미 있어 그대로 둠 %d개" % (차림, 그대로))
    print("  다음 — %s 를 읽고 그 차례대로 한다" % 자리모듈.안내문이름)
    return 0


if __name__ == "__main__":
    sys.exit(main())
