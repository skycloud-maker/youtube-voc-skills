# -*- coding: utf-8 -*-
"""감독자가 한 회차만 꺼내 읽는다.

★ 왜 (2026-08-23)
  Codex 가 3차를 시작하지 못하고 멈췄다.

      「원문을 화면에 출력하지 않고 읽을 수단이 없어 감독자는 시작하지 않았습니다」

  ★ 규칙이 과했다. 판정하려면 읽어야 한다.
    「화면에 찍지 마라」 는 **되풀이해 찍지 마라** 는 뜻인데,
    「읽지 마라」 로 읽혔다. 읽을 수단을 안 줬으니 그렇게 읽는 것이 맞다.

  2차에는 도구가 대신 읽어 주었다. 3차에는 그 도구가 없었다.
  ★ 규칙만 적고 수단을 안 주면 사람(과 판독자)은 멈춘다.

쓰기
    python 스크립트/감독_읽기.py 01          한 회차를 꺼낸다
    python 스크립트/감독_읽기.py             회차 목록만 보여 준다

무엇을 하나
    s13_judge/judge_NN_ids.txt 의 행만 골라
    `_작업중/judge_NN_읽을것.md` 로 낸다. 판정에 필요한 칸만 담는다.

    ★ 이 파일을 **한 번 읽고** 판정한다. 다시 찍지 않는다.
      회차가 끝나면 이 파일은 지워도 된다.
"""
from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

입력 = ROOT / "s13_judge" / "judge_input.csv"
배치집 = ROOT / "s13_judge"
낼곳 = ROOT / "_작업중"

# 판정에 필요한 칸만 — 나머지는 안 꺼낸다
# ★ 새 칸을 함께 꺼낸다 (2026-08-25).
#   갈래·물음·형제조각 이 없으면 ③④ 를 판정할 수가 없다 —
#   「한쪽만 쪼갰다」 는 형제 조각을 봐야 맞는지 알 수 있기 때문이다.
#   ★ make_judge_input 에 칸을 넣고 이 도구를 안 고쳤었다.
칸 = ["atomic_id", "product", "atomic_voc", "voc_cleaned",
     "original_voc", "parent_voc", "video_title", "이_원문의_조각수",
     "갈래", "물음", "형제조각", "A", "B"]


def 회차들() -> list[Path]:
    return sorted(배치집.glob("judge_*_ids.txt"))


def main() -> int:
    if not 입력.exists():
        print("  감독 입력이 없습니다 — %s" % 입력)
        return 1

    목록 = 회차들()
    고른것 = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not 고른것:
        print("=" * 70)
        print("  회차 %d개" % len(목록))
        print("=" * 70)
        for p in 목록:
            번호 = p.stem.replace("judge_", "").replace("_ids", "")
            n = sum(1 for x in p.read_text(encoding="utf-8").splitlines() if x.strip())
            # ★ 판정은 `_판독패키지/_결과/` 에 쌓인다 (2026-08-23).
            #   `_결과` 만 보다가 끝난 회차를 하나도 표시 못 했다 —
            #   이어받는 판독자가 어디부터 할지 이 표로 판단한다.
            _낸곳 = ROOT / "_판독패키지" / "_결과"
            끝난것 = (list(_낸곳.glob("감독결과_%s_*.md" % 번호))
                    if _낸곳.is_dir() else [])
            print("  judge_%-4s %4d행   %s"
                  % (번호, n, "끝남" if 끝난것 else ""))
        print()
        print("  꺼내기 —  python 스크립트/감독_읽기.py 01")
        return 0

    번호 = 고른것[0].zfill(2)
    배치 = 배치집 / ("judge_%s_ids.txt" % 번호)
    if not 배치.exists():
        print("  그런 회차가 없습니다 — %s" % 배치.name)
        return 1

    골라낼 = {x.strip() for x in batch_lines(배치) if x.strip()}
    with io.open(입력, encoding="utf-8-sig", newline="") as h:
        모두 = {r["atomic_id"]: r for r in csv.DictReader(h)}

    뽑은 = [모두[i] for i in 골라낼 if i in 모두]
    없는 = len(골라낼) - len(뽑은)

    낼곳.mkdir(exist_ok=True)
    길 = 낼곳 / ("judge_%s_읽을것.md" % 번호)
    L = ["# judge_%s — 읽고 판정할 것 (%d행)" % (번호, len(뽑은)), ""]
    L.append("> ★ 이 파일을 **한 번 읽고** 판정하십시오. 다시 화면에 찍지 마십시오.")
    L.append("> 회차가 끝나면 지워도 됩니다.")
    L.append("")
    for r in 뽑은:
        L.append("## %s" % r.get("atomic_id", ""))
        L.append("")
        # ★ 갈래·물음을 **맨 앞에** 놓는다 (2026-08-26).
        #   무엇을 묻는지 모르고 답부터 보면 ①②처럼 A·B 중 고르게 된다.
        _갈래 = (r.get("갈래") or "").strip()
        if _갈래:
            L.append("- **갈래** : %s" % _갈래)
            L.append("- **물음** : %s" % (r.get("물음") or ""))
        L.append("- 제품 : %s" % (r.get("product") or "-"))
        L.append("- 판정할 말 : %s" % (r.get("atomic_voc") or ""))
        _전체 = (r.get("voc_cleaned") or "")
        if _전체 and _전체 != (r.get("atomic_voc") or ""):
            L.append("- 댓글 전체 : %s" % _전체)
        # ★ 원문·부모댓글 — 분리가 맞는지 보려면 있어야 한다
        _원문 = (r.get("original_voc") or "")
        if _원문 and _원문 != _전체 and _원문 != (r.get("atomic_voc") or ""):
            L.append("- 원문 전체 : %s" % _원문)
        if (r.get("parent_voc") or "").strip():
            L.append("- 부모 댓글 : %s" % r.get("parent_voc"))
        if (r.get("video_title") or "").strip():
            L.append("- 영상 : %s" % r.get("video_title"))
        # ★ 형제조각 — ③④ 는 이것 없이는 판단할 수가 없다
        if (r.get("형제조각") or "").strip():
            L.append("- 이 원문의 조각 %s개 : %s"
                     % (r.get("이_원문의_조각수") or "?", r.get("형제조각")))
        L.append("- A : %s" % (r.get("A") or ""))
        L.append("- B : %s" % (r.get("B") or ""))
        L.append("")
    길.write_text("\n".join(L), encoding="utf-8")

    print("=" * 70)
    print("  judge_%s — %d행을 꺼냈습니다" % (번호, len(뽑은)))
    if 없는:
        print("  ★ %d행은 입력에 없습니다" % 없는)
    print()
    print("  읽을 파일 : _작업중/judge_%s_읽을것.md" % 번호)
    print()
    print("  ★ 이 파일을 한 번 읽고 판정하십시오.")
    print("    읽은 것을 화면에 되풀이해 찍지 마십시오 — 쌓이면 막힙니다.")
    print("=" * 70)
    return 0


def batch_lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


if __name__ == "__main__":
    sys.exit(main())
