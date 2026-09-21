# -*- coding: utf-8 -*-
"""총괄이 이미 정한 것을 「사람이볼목록」 에 옮긴다.

★ 왜 있는가 (sky 2026-08-26)
  「아까 총괄이랑 다 정리했던 것 같은데.. 그게 2판인데.. 갑자기 이렇게
    나온다고요? 작업은 한 건데 그냥 승인만 기다리는 건가」

  맞는 지적이었습니다. 세어 보니 **426행 전부** 총괄이 정해서
  `raw_voc` 의 `decided_by`·`decided_note` 에 근거까지 들어가 있었습니다.

      decided_by   총괄_최종 98 · 총괄_§7확장 67 · 총괄_구매축 50 · …
      decided_note §10 — 다음 세대를 기다린다는 구매 얘기다 · …

  그런데 `사람이볼목록` 의 `총괄_의견`·`총괄_근거` 는 **0/426 빈칸**이었습니다.

  ★★ 실무자에게는 「총괄이 아무것도 안 정했다」 로 보입니다.
    426행을 처음부터 다시 보게 됩니다 —
    「실무자의 개입을 최소화한다」 는 이 판의 목표와 정반대입니다.

★ 왜 build_master 가 못 채우나
  `build_master.py` 는 **2차 판독 번들**에서 목록을 다시 만듭니다
  (`base = dict(K[aid])`). 총괄 판정은 그 뒤에 붙습니다
  (총괄검수 · apply_sky · 4차 규칙). 그래서 거기서 채우면 언제나 빈칸입니다.

★ 그래서 **번들을 묶기 직전**에 이것이 돕니다.
  어느 도구가 정했든 상관없습니다 — `raw_voc` 에 남은 결과만 봅니다.

쓰기
    python 사람이볼목록_채우기.py
    python 사람이볼목록_채우기.py --확인만
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

csv.field_size_limit(10 ** 8)
_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기
M = ROOT / "s15_master"
F = ROOT / "_판독패키지" / "_결과" / "master_final"

_확인만 = "--확인만" in sys.argv


def 줄(표: str, 말: str) -> None:
    print("  %s %s" % (표, 말))


def _읽기(p):
    with io.open(p, encoding="utf-8-sig", newline="") as h:
        rd = csv.DictReader(h)
        return list(rd), (rd.fieldnames or [])


def 총괄이_정했나(누가: str) -> bool:
    """총괄이 정한 것만 옮긴다.

    판독자 합의(reader_agree)·감독 채택(judge_agree)은 이미 옆 칸에 그대로
    있으므로 여기 옮기면 같은 말을 두 번 하는 것이 된다.
    """
    누가 = (누가 or "").strip()
    return 누가.startswith("총괄") or 누가.startswith("sky_")


def main() -> int:
    raw길 = None
    for c in (F / "raw_voc.csv", M / "raw_voc.csv"):
        if c.exists():
            raw길 = c
            break
    if raw길 is None:
        줄("!", "raw_voc.csv 를 못 찾았습니다 — 통합을 먼저 돌리십시오")
        return 1

    목록길 = [p for p in (M / "사람이볼목록.csv", F / "사람이볼목록.csv")
             if p.exists()]
    if not 목록길:
        줄("!", "사람이볼목록.csv 가 없습니다 — 통합을 먼저 돌리십시오")
        return 1

    raw, _ = _읽기(raw길)
    판정 = {(r.get("atomic_id") or "").strip(): r for r in raw}
    줄("·", "raw_voc %d행 — %s" % (len(raw), raw길.parent.name))

    print("=" * 70)
    print("  총괄이 정한 것을 사람이볼목록에 옮깁니다")
    print("=" * 70)

    탈 = 0
    for p in 목록길:
        목록, 칸 = _읽기(p)
        if "총괄_의견" not in 칸:
            줄("!", "%s 에 총괄_의견 칸이 없습니다 — 넘어갑니다" % p.name)
            continue

        채움 = 이미 = 없음 = 사람몫 = 0
        for x in 목록:
            aid = (x.get("atomic_id") or "").strip()
            r = 판정.get(aid)
            if r is None:
                없음 += 1
                continue
            누가 = (r.get("decided_by") or "").strip()
            if not 총괄이_정했나(누가):
                사람몫 += 1
                continue
            새의견 = "%s → 라벨 %s" % (
                누가, (r.get("topic") or "").strip() or "(빈칸)")
            새근거 = (r.get("decided_note") or "").strip()
            if (x.get("총괄_의견") or "").strip() == 새의견 \
                    and (x.get("총괄_근거") or "").strip() == 새근거:
                이미 += 1
                continue
            x["총괄_의견"] = 새의견
            x["총괄_근거"] = 새근거
            채움 += 1

        어디 = p.parent.name + "/" + p.name
        줄("·", "%-34s %d행" % (어디, len(목록)))
        print("        총괄이 정해 옮긴 것   %5d" % 채움)
        if 이미:
            print("        이미 같은 값          %5d" % 이미)
        print("        ★ 사람이 정할 것      %5d" % 사람몫)
        if 없음:
            print("        raw_voc 에 없음       %5d" % 없음)
        탈 += 채움

        if 채움 and not _확인만:
            with io.open(p, "w", encoding="utf-8-sig", newline="") as h:
                w = csv.DictWriter(h, fieldnames=칸, extrasaction="ignore")
                w.writeheader()
                w.writerows(목록)

    print()
    if _확인만:
        print("  ── 확인만 ── %d행을 채울 참이었습니다. 아무것도 안 바꿨습니다."
              % 탈)
    elif 탈:
        print("  %d행을 채웠습니다 — 이어서 번들을 다시 묶으십시오." % 탈)
    else:
        print("  · 옮길 것이 없습니다 (이미 채워져 있거나 총괄 판정이 없습니다)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
