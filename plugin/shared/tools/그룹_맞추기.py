# -*- coding: utf-8 -*-
"""`topic_group` 을 `topic` 에서 다시 계산한다 — 정본 매핑대로.

★ 왜 있는가 (2026-08-26)
  `topic_group` 은 **파생 칸**입니다. `topic` 이 정해지면 따라옵니다.
  그런데 `topic` 을 바꾼 주체가 `topic_group` 을 같이 안 고쳤습니다.

      reader_agree (1차 라벨 그대로)     0 / 1,555   0.0%   안 어긋남
      judge_agree  (3차 감독이 바꿈)   215 /   794  27.1%
      총괄_*        (총괄이 바꿈)       139 /   252  55.2%
      sky          (사람이 바꿈)       462 /   462  100.0%  ← 전부 빈칸

  ★★ **파생 칸을 갱신하는 자리가 없었습니다.**
    「사람이볼목록의 총괄_의견이 빈칸이던 것」 과 정확히 같은 결함입니다.

★ 왜 중요한가 — 대시보드 필터가 이 칸을 씁니다 (28번 D-1).
  같은 라벨이 여러 묶음에 흩어지면 집계가 그만큼 틀립니다.

★ 정본은 `s9_group/topic_group_map.json` 의 `topic_to_group` 입니다.
  이 도구는 **판단하지 않습니다.** 매핑에 없는 라벨은 손대지 않고 알려만 줍니다 —
  어느 묶음에 넣을지는 사람이 정할 일입니다.

쓰기
    python 그룹_맞추기.py
    python 그룹_맞추기.py --확인만
"""
from __future__ import annotations

import collections
import csv
import io
import json
import re
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

미판정 = {"", "N/A", "미분류"}
_확인만 = "--확인만" in sys.argv


def 줄(표: str, 말: str) -> None:
    print("  %s %s" % (표, 말))


def _매핑():
    """정본 매핑을 찾는다 — 이 판 안이 먼저, 없으면 뿌리."""
    for c in (ROOT / "s9_group" / "topic_group_map.json",
              ROOT.parent / "s9_group" / "topic_group_map.json"):
        if c.exists():
            j = json.loads(c.read_text(encoding="utf-8"))
            return (j.get("topic_to_group") or {}), c
    return {}, None


def main() -> int:
    매핑, 어디 = _매핑()
    print("=" * 70)
    print("  topic_group 을 topic 에서 다시 계산합니다")
    print("=" * 70)
    if not 매핑:
        줄("!", "topic_group_map.json 을 못 찾았습니다")
        return 1
    줄("·", "정본 매핑 %d개 — %s" % (len(매핑), 어디.parent.name + "/" + 어디.name))

    # ★ 가장 나중 판을 본다 (2026-08-26).
    #   뿌리에서 돌면 1판(동결된 기록)을 보게 되는데, 1판은 그 판의 라벨
    #   이름으로 남겨 두는 것이 맞다. 고칠 대상은 **지금 판**이다.
    #   원문대조검사.py 와 같은 규칙이다.
    자리 = ROOT
    _판 = sorted((d for d in ROOT.iterdir()
                 if d.is_dir() and re.fullmatch(r"_\d+판", d.name)
                 and (d / "_판독패키지" / "_결과" / "master_final"
                      / "raw_voc.csv").is_file()),
                key=lambda d: int(d.name[1:-1]))
    if _판:
        자리 = _판[-1]
        줄("·", "가장 나중 판 — %s" % 자리.name)

    길 = [p for p in (자리 / "_판독패키지" / "_결과" / "master_final"
                     / "raw_voc.csv",
                     자리 / "s15_master" / "raw_voc.csv") if p.exists()]
    if not 길:
        줄("!", "raw_voc.csv 를 못 찾았습니다")
        return 1

    탈 = 0
    고칠것전체 = 0
    for p in 길:
        with io.open(p, encoding="utf-8-sig", newline="") as h:
            rd = csv.DictReader(h)
            칸 = rd.fieldnames or []
            행 = list(rd)
        if "topic_group" not in 칸:
            줄("!", "%s 에 topic_group 칸이 없습니다" % p.name)
            continue

        고침 = collections.Counter()
        없는라벨 = collections.Counter()
        그대로 = 0
        for r in 행:
            t = (r.get("topic") or "").strip()
            g = (r.get("topic_group") or "").strip()
            if t in 미판정:
                # ★ topic 이 미판정이면 묶음도 「미판정」 이다 (2026-08-26).
                #   28번 D-1 ③ — 「미판정」(미분류·N/A)은 표시하되
                #   개선 우선순위 집계에서 뺀다. 묶음은 topic 을 굴린 값이므로
                #   topic 이 집계에서 빠지면 묶음도 빠져야 한다.
                #   실제로 topic 이 N/A 인데 묶음은 「제품 전반」 인 행이 162개 있었다
                #   — 그 행들은 정본 ③ 을 어기고 묶음 집계에 들어가고 있었다.
                바른 = "미판정"
                if g != 바른:
                    고침[(g or "(빈칸)", 바른)] += 1
                    r["topic_group"] = 바른
                else:
                    그대로 += 1
                continue
            바른 = 매핑.get(t)
            if 바른 is None:
                없는라벨[t] += 1
                continue
            if g == 바른:
                그대로 += 1
                continue
            고침[(g or "(빈칸)", 바른)] += 1
            r["topic_group"] = 바른

        전 = sum(고침.values())
        고칠것전체 += 전
        줄("·", "%s — %d행" % (p.parent.name + "/" + p.name, len(행)))
        print("        이미 맞음      %5d" % 그대로)
        print("        고칠 것        %5d" % 전)
        for (옛, 새), n in 고침.most_common(8):
            print("           %-14s → %-14s %5d" % (옛[:14], 새[:14], n))
        if 없는라벨:
            print("        ★ 매핑에 없어 손대지 않은 라벨 %d종 · %d행"
                  % (len(없는라벨), sum(없는라벨.values())))
            for t, n in 없는라벨.most_common(8):
                print("           %-30s %5d" % (t[:30], n))
            탈 += len(없는라벨)

        if 전 and not _확인만:
            with io.open(p, "w", encoding="utf-8-sig", newline="") as h:
                w = csv.DictWriter(h, fieldnames=칸, extrasaction="ignore")
                w.writeheader()
                w.writerows(행)

    print()
    if _확인만:
        # ★ 검사로 쓸 때는 어긋난 것이 있으면 **반드시 종료코드 1** 이어야 한다
        #   (2026-08-26). 0 을 돌려주면 마무리 도구가 통과로 읽는다.
        if 고칠것전체:
            print("  ✗ topic_group 이 topic 과 어긋난 행이 %d 개 있습니다."
                  % 고칠것전체)
            print("    python 그룹_맞추기.py 로 맞추십시오.")
        else:
            print("  · topic_group 이 topic 과 다 맞습니다.")
    else:
        print("  ★ 이어서 xlsx 를 다시 만들고 시트를 붙이십시오.")
    if 탈:
        print("  ★ 매핑에 없는 라벨이 있습니다 —")
        print("    s9_group/topic_group_map.json 에 넣을지 사람이 정하십시오.")
    print("=" * 70)
    return 1 if (탈 or (_확인만 and 고칠것전체)) else 0


if __name__ == "__main__":
    sys.exit(main())
