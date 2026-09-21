# -*- coding: utf-8 -*-
"""★PL(Product Liability) Issue — 안전·위생을 건수와 무관하게 전량 뽑는다.

★ sky 결정 2026-08-25 (4차 실무자 회의)
  「안전이나 위생 관련된 내용은 매우 중요하게 여기기 때문에,
    이 문제에 관해서는 **건수 상관없이 모두 노출**되도록 별도 tab 을 만들었으면 함」

★ 새 집계가 아니라 **별도 뷰**다 (기준서 §11).
  개선우선순위에서 빼지 않는다. 그대로 두고 보기만 따로 만든다.
  그래서 중복 계산이 없다.

★ 범위는 지금 둘뿐이다. 넓힐 때는 기준서 §11 에 적고 여기를 고친다.
    안전(화재·감전·누수)
    위생/냄새

★ 왜 「건수와 무관」 인가 — 안전·위생은 한 건이라도 회사가 봐야 한다.
  개선우선순위는 건수·부정 강도로 줄을 세우니 한 건짜리는 아래로 내려간다.
  거기서 묻히지 않게 **거르지 않고 통째로** 보여 주는 자리다.

쓰기
    python PL이슈_뽑기.py
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

csv.field_size_limit(10 ** 8)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기
번들 = ROOT / "_판독패키지" / "_결과" / "master_final"

# ★ 기준서 §11 과 짝을 맞춘다. 여기만 고치면 안 된다 — 문서도 함께
PL라벨 = ("안전(화재·감전·누수)", "위생/냄새")

# 실무자가 보는 칸 — 89칸을 다 주면 아무도 안 본다
낼칸 = [
    ("갈래", None),                 # 안전 / 위생 — 맨 앞에 둔다
    ("topic", "라벨"),
    ("product_category", "제품군"),
    ("atomic_voc", "무슨 말인가"),
    ("original_voc", "원문 전체"),
    ("cej", "여정 단계"),
    ("sentiment_dir", "긍부정"),
    ("tee_emotion_score", "감정 강도"),
    ("voc_total_score", "VoC 점수"),
    ("rootcause_problem", "무엇이 문제인가"),
    ("rootcause_cause", "왜 그런가"),
    ("entity_role", "누구 얘기인가"),
    ("video_title", "영상"),
    ("video_url", "영상 주소"),
    ("atomic_id", "행 번호"),
]


def main() -> int:
    길 = 번들 / "raw_voc.csv"
    if not 길.exists():
        print("  raw_voc.csv 를 못 찾았습니다 — %s" % 길)
        return 1

    with io.open(길, encoding="utf-8-sig", newline="") as h:
        행 = list(csv.DictReader(h))

    뽑은것 = []
    for x in 행:
        t = (x.get("topic") or "").strip()
        if t not in PL라벨:
            continue
        # ★ 제외된 행은 담지 않는다 — 분모 밖이라 개선과제가 될 수 없다
        if (x.get("status") or "") != "normal":
            continue
        한줄 = {"갈래": "안전" if t.startswith("안전") else "위생"}
        for 칸, 보일이름 in 낼칸:
            if 칸 == "갈래":
                continue
            한줄[보일이름] = " ".join(str(x.get(칸) or "").split())
        뽑은것.append(한줄)

    # ★ 안전을 먼저, 그다음 감정 강도가 센 것부터
    def 셈(v):
        try:
            return -abs(float(v or 0))
        except (TypeError, ValueError):
            return 0.0

    뽑은것.sort(key=lambda r: (r["갈래"] != "안전", 셈(r.get("감정 강도"))))

    낼곳 = 번들 / "PL이슈.csv"
    머리 = ["갈래"] + [보일 for 칸, 보일 in 낼칸 if 칸 != "갈래"]
    with io.open(낼곳, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=머리)
        w.writeheader()
        w.writerows(뽑은것)

    안전 = sum(1 for r in 뽑은것 if r["갈래"] == "안전")
    print("  ★PL Issue — %d행 (안전 %d · 위생 %d)"
          % (len(뽑은것), 안전, len(뽑은것) - 안전))
    print("     %s" % 낼곳)
    print()
    print("  ★ 건수로 거르지 않았습니다. 안전·위생은 한 건이라도 봅니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
