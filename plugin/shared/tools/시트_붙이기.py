# -*- coding: utf-8 -*-
"""최종 xlsx 에 **사람이 볼 것**을 시트로 붙인다.

★ 왜 (sky 2026-08-23)
  「판정불일치가 사람이볼목록 69행이 나와야 되는 것이 아닌지?」

  ★ 좋은 물음이었고, 재 보니 이렇습니다.
      · 69행은 있다 — 그런데 `수정로그_재검토필요` 라는 이름 아래 있다.
        그 이름으로는 아무도 「사람이 정할 행」 인 줄 모른다.
      · `판정불일치` 는 다른 것이다 — 한 행 안에서 verdict 와 finding 심각도가
        어긋난 것을 잡는 형식 검사다. 0 이 맞다.
      · `기준서개정후보`·`구조적결함` 이 0 인데 보정요청은 8건이다.
        3차 감독은 판정 파일에 적었고, 그 시트는 2차 번들 것만 담는다.
        **xlsx 만 보는 사람은 보정 요청을 통째로 못 본다.**

  ★ 파일이 여럿으로 흩어지면 사람은 하나만 본다.
    받는 사람이 열 파일 하나에 다 있어야 한다.

쓰기
    python 스크립트/시트_붙이기.py
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

번들 = ROOT / "_판독패키지" / "_결과" / "master_final"

# 붙일 것 — (시트 이름, 어디서 가져오나, 없어도 되나)
붙일것 = [
    ("★사람이볼목록", ROOT / "s15_master" / "사람이볼목록.csv", False),
    ("★보정요청", ROOT / "_인계" / "보정요청.csv", False),
    # ★ 안전·위생은 건수와 무관하게 전량 본다 (sky 2026-08-25 · 기준서 §11)
    #   개선우선순위에서 빼지 않는다 — 별도 뷰라 중복 계산이 없다
    ("★PL Issue", ROOT / "_판독패키지" / "_결과" / "master_final" / "PL이슈.csv", False),
    # ★ 「쟀다」 는 사실이 보여야 믿을 수 있다 (sky 2026-08-25)
    #   md 는 총괄만 본다. 실무자는 xlsx 를 본다.
    ("편향검사", ROOT / "_판독패키지" / "_결과" / "master_final" / "편향검사.csv", True),
]


def main() -> int:
    xl = sorted(번들.glob("*.xlsx"))
    if not xl:
        print("  최종 xlsx 를 못 찾았습니다 — %s" % 번들)
        return 1

    try:
        import openpyxl
    except ImportError:
        print("  openpyxl 이 없습니다 — python -m pip install openpyxl")
        return 1

    책 = openpyxl.load_workbook(xl[0])
    붙인것 = []
    for 이름, 길, 없어도됨 in 붙일것:
        if not Path(길).exists():
            if not 없어도됨:
                print("  ! %s 를 못 찾았습니다 — %s" % (이름, 길))
            continue
        if 이름 in 책.sheetnames:
            del 책[이름]
        장 = 책.create_sheet(이름)
        with io.open(길, encoding="utf-8-sig", newline="") as h:
            n = 0
            for r in csv.reader(h):
                장.append([str(x)[:32000] for x in r])
                n += 1
        붙인것.append((이름, max(n - 1, 0)))

    책.save(xl[0])
    print("  붙였습니다 — %s" % xl[0].name)
    for 이름, n in 붙인것:
        print("     %-14s %5d행" % (이름, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
