# -*- coding: utf-8 -*-
"""최종 번들을 **사람이 보기 좋게** 다듬는다 — 총괄 자리에서 한 번.

★ 왜 (sky 2026-08-24)
  「이 변경사항은 3차가 끝난 뒤에 AI작업자(당신)가 색칠도구와 함께
    바꾸는 작업으로 할까요?」

  ★ 맞습니다. 다만 한 가지만 바로잡습니다 —
    통합·검사·보정요청·논의본은 **`3차_마무리` 가 자동으로** 합니다.
    총괄이 하는 것은 **그 뒤 꾸미기**입니다.
    그래서 꾸미는 일을 이 도구 하나로 묶습니다.

무엇을 하나
  ① 시트 순서를 **먼저 볼 것부터**로 바꾼다
  ② 묶음 색을 칠한다 (안내와 같은 색)
  ③ 데이터 안내(VoC_데이터_안내.xlsx)를 다시 만든다

★ 판독자 꾸러미에 넣지 않는다. 꾸밈은 판독자가 할 일이 아니다.
★ 데이터는 한 글자도 건드리지 않는다.

쓰기
    python 번들_마무리꾸미기.py [번들.xlsx]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import openpyxl

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

# ★ 시트 차례 — 먼저 볼 것부터 (sky 2026-08-24 동의)
#   raw_voc 는 **1번에 그대로 둔다.** 대시보드가 이름으로 찾지만,
#   못 찾으면 첫 시트를 읽는 되돌림장치가 있다 —
#   1번에 두면 그 장치가 걸려도 맞는 것을 읽는다.
차례 = [
    # ★ 첫 장 — 무엇을 어디서 보는지 (sky 2026-08-26)
    "0_차례",
    # ★ raw_voc 는 2번으로 내린다. 대시보드는 **이름으로** 찾으므로 자리가 무관하다.
    #   사람이 열어 볼 장이 아니라 기계가 읽는 장이다.
    "raw_voc",
    # ── 여기부터 주로 볼 것 ──
    "★PL Issue",            # 안전·위생 전량 (기준서 §11)
    "★사람이볼목록",           # 행 하나 관점 — 총괄도 못 정한 것
    "★보정요청",              # 규칙 관점 — 실무자와 설계자가 같이 정한다
    "수정로그_재검토필요",        # 참고 — 총괄이 이렇게 고쳤다 (필수 아님)
    # ── 대시보드와 함께 보면 좋은 것 ──
    "video_summary",
    "inquiry_rows",
    "improvement_priority",
    "improvement_priority_comp",
    "improvement_evidence_and_ai",
    # ── 결정된 이력. 열 일 거의 없음 ──
    "분리제안",
    "편향검사",
    "기준서개정후보",
    "구조적결함",
    "판정불일치",
    "수정로그_오류확정",          # 72,530행 — 가장 안 본다
]


def _번들찾기() -> Path | None:
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        return p if p.exists() else None
    d = ROOT / "_판독패키지" / "_결과" / "master_final"
    hits = sorted(d.glob("*.xlsx")) if d.is_dir() else []
    return hits[0] if hits else None


def 차례바꾸기(길: Path) -> bool:
    w = openpyxl.load_workbook(길)
    있는것 = list(w.sheetnames)
    바랄것 = [s for s in 차례 if s in 있는것]
    남은것 = [s for s in 있는것 if s not in 바랄것]   # 차례에 없는 것은 뒤로
    새차례 = 바랄것 + 남은것

    if 새차례 == 있는것:
        print("  시트 차례 — 이미 그대로입니다")
        return False

    w._sheets = [w[s] for s in 새차례]
    w.save(길)
    print("  시트 차례를 바꿨습니다")
    for i, s in enumerate(새차례, 1):
        표 = "★" if s.startswith("★") else " "
        옛 = 있는것.index(s) + 1
        print("     %s %2d. %-28s (전 %d번)" % (표, i, s, 옛))
    if 남은것:
        print("     ★ 차례에 없던 시트 %d개는 뒤로 두었습니다 — %s"
              % (len(남은것), " · ".join(남은것)))
    return True


def _달리기(도구: str, *인자: str) -> int:
    p = _여기 / 도구
    if not p.exists():
        print("  %s 를 못 찾았습니다" % 도구)
        return 1
    r = subprocess.run([sys.executable, str(p), *인자], cwd=str(ROOT),
                       text=True, encoding="utf-8", capture_output=True)
    for x in (r.stdout or "").rstrip().splitlines():
        print("  " + x)
    if r.returncode:
        print((r.stderr or "")[-400:])
    return r.returncode


def main() -> int:
    길 = _번들찾기()
    if not 길:
        print("  최종 번들을 못 찾았습니다 — 자리를 알려 주십시오")
        print("    python 번들_마무리꾸미기.py <번들.xlsx>")
        return 1

    print("=" * 70)
    print("  번들 마무리 꾸미기 — %s" % 길.name)
    print("=" * 70)

    print()
    print("① 시트 차례")
    차례바꾸기(길)

    print()
    print("② 묶음 색")
    if _달리기("번들_색칠하기.py", str(길)):
        return 1

    print()
    print("③ 데이터 안내")
    _달리기("데이터안내_만들기.py", str(길))

    print()
    print("=" * 70)
    print("  끝났습니다.")
    print("  ★ 데이터는 건드리지 않았습니다 — 꾸밈만 바꿨습니다.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
