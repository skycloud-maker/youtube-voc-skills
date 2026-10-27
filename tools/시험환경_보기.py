# -*- coding: utf-8 -*-
"""얼린 시험 그릇들이 **어떤 자리에서** 돌았나 한눈에 본다 (2026-10-27).

★ 왜 (sky 2026-10-27) — 「순수하게 skill 만으로 돌아가는지 모르지 않나요?」
  옛 그릇의 채점표는 **동결**이라 다시 쓰지 않는다. 대신 기록을 **읽어서** 말한다.
  앞으로 돌리는 시험은 채점기가 직접 본다 (`스킬시험_돌리기.공통채점`).

★ 읽기만 한다 — 그릇을 고치지 않는다.

쓰기
    python tools/시험환경_보기.py            한 줄 요약 + 더러운 그릇 목록
    python tools/시험환경_보기.py --전부      그릇마다 한 줄
"""
from __future__ import annotations

import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
_뿌리 = _여기.parent
sys.path.insert(0, str(_뿌리 / "tests" / "evals"))
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
import 스킬시험_돌리기 as 공용  # noqa: E402
from paths import BASELINE  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    전부 = "--전부" in sys.argv
    자리 = BASELINE / "스킬시험"
    if not 자리.is_dir():
        print("  ✗ 시험 그릇 자리를 못 찾았습니다 — %s (못 찾음은 통과가 아니다)" % 자리)
        return 1
    그릇들 = [p for p in sorted(자리.iterdir()) if (p / "시험.json").is_file()]
    if not 그릇들:
        print("  ✗ 그릇이 없습니다 — %s" % 자리)
        return 1

    깨끗, 더러움, 밖썼음 = [], [], []
    print("=" * 78)
    print("  시험 그릇 %d개 — 어떤 자리에서 돌았나" % len(그릇들))
    print("=" * 78)
    for g in 그릇들:
        본것 = 공용.아이가_본것(g)
        맑, 까닭 = 공용.자리가_깨끗했나(g)
        썼됨, 썼까닭 = 공용.밖의것을_썼나(g)
        (깨끗 if 맑 else 더러움).append(g.name)
        if not 썼됨:
            밖썼음.append((g.name, 썼까닭))
        if 전부:
            print("  %s %-44s 스킬 %-4s 훅 %-5s MCP %s"
                  % ("○" if 맑 else "✗", g.name[:44],
                     본것["스킬수"] if 본것["확인됨"] else "?",
                     "돌음" if 본것["훅돌았나"] else "없음",
                     ", ".join(본것["MCP"]) or "없음"))
    print("\n  깨끗한 자리에서 돈 것 — %d / %d" % (len(깨끗), len(그릇들)))
    if 더러움:
        print("  ✗ 내 설정을 물려받은 것 — %d개" % len(더러움))
        for 이름 in 더러움[:6]:
            print("     · %s" % 이름)
        if len(더러움) > 6:
            print("     … 그리고 %d개 더" % (len(더러움) - 6))
    print("\n  우리 스킬 밖의 것을 **쓴** 것 — %d개" % len(밖썼음))
    for 이름, 까닭 in 밖썼음[:6]:
        print("     ✗ %s — %s" % (이름, 까닭))
    print("\n  ★ 여기서 못 보는 것 — 모델이 학습으로 아는 것. 끌 수도 셀 수도 없다.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
