# -*- coding: utf-8 -*-
"""조각이 원래 글을 빠짐없이 덮는가 — 2차 계약 L-3 을 3차에도 적용한다.

★ 왜 (2026-08-26)
  `D` 로 낸 조각이 **대표 문장만 오려 낸** 경우가 있었다.
  덮개율 가운데값 50% — 원래 글의 절반이 어느 조각에도 안 들어갔다.
  그 글은 통합할 때 **데이터에서 사라진다.** 잡담이 아니라 실제 VoC 였다.

★ 2차 판독에는 이 규칙이 있었다 (부록 L-3) — 그래서 덮개율이 100% 였다.
  3차 프롬프트에 안 옮겨서 생긴 일이다.

쓰기
    python 스크립트/조각덮개검사.py
    python 스크립트/조각덮개검사.py --자세히      낮은 행을 다 보여 준다
"""
import csv
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

csv.field_size_limit(10 ** 8)
_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

문턱 = 95          # 이 아래면 짚는다 (공백·문장부호 차이를 감안한 값)


def _판정들(자리):
    나옴 = {}
    for p in sorted(자리.glob("감독결과_*.md")):
        글 = p.read_text(encoding="utf-8", errors="replace")
        깊, 시작 = 0, None
        for i, c in enumerate(글):
            if c == "{":
                if 깊 == 0:
                    시작 = i
                깊 += 1
            elif c == "}" and 깊:
                깊 -= 1
                if 깊 == 0:
                    try:
                        j = json.loads(글[시작:i + 1])
                    except ValueError:
                        continue
                    if isinstance(j, dict) and j.get("atomic_id"):
                        나옴[j["atomic_id"]] = (j, p.name)
    return 나옴


def main() -> int:
    결과자리 = ROOT / "_판독패키지" / "_결과"
    입력길 = ROOT / "s13_judge" / "judge_input.csv"
    if not 결과자리.is_dir() or not 입력길.exists():
        print("  판정이나 입력을 못 찾았습니다 — 꾸러미 폴더에서 돌리십시오")
        return 1

    with 입력길.open(encoding="utf-8-sig", newline="") as h:
        입력 = {x["atomic_id"]: x for x in csv.DictReader(h)}
    판정 = _판정들(결과자리)
    if not 판정:
        print("  아직 판정 파일이 없습니다")
        return 0

    낮은것 = []
    잰것 = 0
    for aid, (j, 파일) in 판정.items():
        if str(j.get("verdict", "")).strip() != "D" or j.get("merge"):
            continue
        원 = re.sub(r"\s+", "", (입력.get(aid) or {}).get("atomic_voc") or "")
        if not 원:
            continue
        잰것 += 1
        덮 = sum(len(re.sub(r"\s+", "", s.get("atomic_voc") or ""))
                for s in (j.get("segments") or []))
        덮 += len(re.sub(r"\s+", "", str(j.get("residual") or "")))
        비 = 100.0 * 덮 / len(원)
        if 비 < 문턱:
            낮은것.append((비, aid, 파일, 원, j))

    print("=" * 70)
    print("  조각 덮개 검사 — D(쪼개라) %d건" % 잰것)
    print("=" * 70)
    if not 낮은것:
        print("  · 조각이 원래 글을 빠짐없이 덮습니다")
        print("=" * 70)
        return 0

    낮은것.sort()
    print("  ★ 원래 글을 %d%% 도 못 덮은 행 %d건" % (문턱, len(낮은것)))
    print("     이대로 두면 안 덮인 글이 **데이터에서 사라집니다.**")
    print()
    볼것 = 낮은것 if "--자세히" in sys.argv else 낮은것[:8]
    for 비, aid, 파일, 원, j in 볼것:
        print("   %3.0f%%  %s  (%s)" % (비, aid[:38], 파일))
        남 = " ".join(((입력.get(aid) or {}).get("atomic_voc") or "").split())
        for s in (j.get("segments") or []):
            t = " ".join((s.get("atomic_voc") or "").split())
            남 = 남.replace(t, "▮", 1)
        버린 = [x.strip() for x in 남.split("▮") if len(x.strip()) > 8]
        for b in 버린[:2]:
            print("          안 덮인 글  %s" % b[:74])
    if len(낮은것) > len(볼것):
        print("   … %d건 더 (--자세히 로 전부 봅니다)" % (len(낮은것) - len(볼것)))
    print()
    print("  ★ 고치는 법 — 조각을 다시 나누어 원래 글을 다 덮게 하십시오.")
    print("     어느 주제에도 안 들어가는 나머지는 \"residual\" 에 적으십시오.")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())
