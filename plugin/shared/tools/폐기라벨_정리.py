# -*- coding: utf-8 -*-
"""폐기된 라벨 이름을 지금 이름으로 바꾼다 — **기록 시트까지.**

★ 왜 있는가 (sky 2026-08-26)
  「구매의사/이탈」 → 「구매의사」 로 이름을 바꾸기로 하고 `raw_voc` 은 바꿨는데,
  기록 시트에는 옛 이름이 5,740곳 남아 있었습니다.

      수정로그_오류확정   5,534  (사유 4,838 · 제안값 693 · 원본값 3)
      수정로그_재검토필요    168
      분리제안              38

  실무자가 로그를 열면 **지금은 없는 라벨**을 봅니다.
  판정이 바뀌는 것이 아니라 **같은 라벨의 새 이름**을 적는 것입니다.

★★ 이 도구는 「담당자→총괄」 사고와 **똑같은 종류의 작업**입니다.
  그때는 용어를 일괄로 밀다가 **실제 댓글 본문**을 덮었습니다
  (93_오류발견대장 참조). 그래서 이 도구는 세 겹으로 막습니다.

  ① 원문 계열 칸은 **절대** 안 건드린다 (아래 원문칸)
  ② 백업 파일(`…전_날짜_시각.csv`)은 **절대** 안 건드린다 —
     그것은 「그때 이랬다」 를 남긴 되돌리기 지점이다
  ③ 끝나면 `원문대조검사.py` 를 돌려 원문이 그대로인지 확인하라고 말한다

★ 무엇을 바꾸나 — `check_selfcheck.py` 의 `DEAD_TOPIC` 과 같은 목록입니다.
  거기는 「이 값이 남았나」 를 보는 검사이고, 여기는 그것을 고치는 자리입니다.

쓰기
    python 폐기라벨_정리.py
    python 폐기라벨_정리.py --확인만
"""
from __future__ import annotations

import csv
import io
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

# 옛 이름 → 지금 이름  (check_selfcheck.DEAD_TOPIC 과 짝)
바꿀것 = {
    "구매의사/이탈": "구매의사",
    "주거 수납/공간": "공간 활용성",
    # ★ sky 2026-08-26 — 곰팡이는 냄새의 원인 중 하나라 같은 축이다.
    #   두 이름이 나란히 있으면 판독자마다 다르게 고른다 (「기타」 5종과 같은 문제).
    "위생/냄새(곰팡이)": "위생/냄새",
}

# ★★ 절대 손대지 않는 칸 — 사람이 쓴 글이 그대로 들어 있는 자리
원문칸 = {
    "original_voc", "voc_cleaned", "atomic_voc", "parent_voc",
    "topic_evidence", "cej_evidence", "tee_emotion_evidence",
    "rootcause_evidence", "근거_원문", "근거인용", "원문", "quote",
}

# 백업 파일 — 되돌리기 지점이라 안 건드린다
_백업 = re.compile(r"전_20\d{6}_\d{4}\.csv$")

볼자리 = ("_판독패키지/_결과/master_final", "s15_master", "_최종결과", "_인계")

_확인만 = "--확인만" in sys.argv


def 줄(표: str, 말: str) -> None:
    print("  %s %s" % (표, 말))


def main() -> int:
    print("=" * 70)
    print("  폐기 라벨 정리 — 기록 시트의 옛 이름을 지금 이름으로")
    print("=" * 70)
    for 옛, 새 in 바꿀것.items():
        print("     「%s」 → 「%s」" % (옛, 새))
    print()

    바꾼파일 = 0
    바꾼칸 = 0
    지킨것 = []
    건너뜀 = 0

    for 자리 in 볼자리:
        d = ROOT / 자리
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.csv")):
            if _백업.search(p.name):
                건너뜀 += 1
                continue
            with io.open(p, encoding="utf-8-sig", newline="") as h:
                rd = csv.DictReader(h)
                머리 = rd.fieldnames or []
                행 = list(rd)
            if not 머리:
                continue

            셈 = {}
            for r in 행:
                for c in 머리:
                    v = r.get(c)
                    if not v:
                        continue
                    for 옛, 새 in 바꿀것.items():
                        if 옛 not in v:
                            continue
                        if c in 원문칸:
                            # ★ 원문 칸이다. 세어서 보여만 주고 안 바꾼다
                            지킨것.append((p.name, c, 옛))
                            continue
                        r[c] = v = v.replace(옛, 새)
                        셈[c] = 셈.get(c, 0) + 1

            if not 셈:
                continue
            바꾼파일 += 1
            바꾼칸 += sum(셈.values())
            줄("·", "%s / %s" % (자리.split("/")[-1], p.name))
            for c, n in sorted(셈.items(), key=lambda z: -z[1]):
                print("        %-24s %6d" % (c[:24], n))
            if not _확인만:
                with io.open(p, "w", encoding="utf-8-sig", newline="") as h:
                    w = csv.DictWriter(h, fieldnames=머리,
                                       extrasaction="ignore")
                    w.writeheader()
                    w.writerows(행)

    print()
    줄("·", "백업 파일 %d개는 손대지 않았습니다 (되돌리기 지점입니다)" % 건너뜀)
    if 지킨것:
        줄("★", "원문 칸에서 발견 %d곳 — **안 바꿨습니다**" % len(지킨것))
        for 이름, c, 옛 in 지킨것[:6]:
            print("        %s / %s / %s" % (이름, c, 옛))
    print()
    if _확인만:
        print("  ── 확인만 ── 파일 %d개 · %d곳을 바꿀 참이었습니다."
              % (바꾼파일, 바꾼칸))
        print("     아무것도 안 바꿨습니다.")
    elif 바꾼칸:
        print("  파일 %d개 · %d곳을 바꿨습니다." % (바꾼파일, 바꾼칸))
        print("  ★ 이어서 하십시오")
        print("     python 원문대조검사.py      원문이 그대로인지 확인")
        print("     python 시트_붙이기.py       번들에 다시 붙이기")
    else:
        print("  · 바꿀 것이 없습니다 — 폐기 라벨이 남아 있지 않습니다")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
