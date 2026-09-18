# -*- coding: utf-8 -*-
"""보정 요청을 **회의에서 같이 보고 정할 수 있는 글**로 다듬는다.

★ 왜 (sky 2026-08-23)
  「통합 보정 요청본 — 언제 어느 시점에 어떤 의견으로 나왔고 뭘 봐야 하며,
    어떤 것들 중에서 선택할 수 있도록 선택지를 주거나 실무자와 같이
    판단할 수 있는 구체적인 의견을 기술해주고 그런 논의 보조용 파일이 되도록」

  csv 는 쌓아 두기엔 좋지만 **회의 자리에서 못 봅니다.**
  누가 언제 무엇 때문에 냈는지, 무엇을 정해야 하는지,
  고르면 몇 행이 움직이는지 — 그것이 한 장에 있어야 정할 수 있습니다.

무엇을 하나
  · 보정요청.csv 를 읽어 차수·건수 순으로 늘어놓는다
  · 대표 행의 **실제 원문**을 최종 데이터에서 찾아 붙인다
    (근거 없이 「이런 게 있습니다」 만 있으면 판단할 수 없다)
  · 갈래마다 **고를 수 있는 길**을 적는다
  · 정하면 몇 행이 움직이는지 센다

쓰기
    python 스크립트/보정요청_논의본.py
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

요청 = ROOT / "_인계" / "보정요청.csv"
최종 = ROOT / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv"
낼곳 = ROOT / "_인계" / "보정요청_논의본.md"

# 갈래마다 무엇을 정해야 하는지 — 고를 수 있는 길을 적어 둔다
길잡이 = {
    "기준서공백": (
        "담을 라벨이 없거나, 두 라벨이 같은 자리를 먹고 있습니다.",
        ["① 있는 라벨 하나로 **통일한다** — 어느 것으로 할지 정합니다",
         "② 라벨을 **새로 만든다** — 이름과 담을 범위를 정합니다",
         "③ 있는 라벨의 **범위를 넓힌다** — 어디까지 넓힐지 정합니다",
         "④ **분석에서 뺀다** — 볼 값어치가 없다고 보면 그렇게 정합니다"],
    ),
    "엔진결함": (
        "1차 분석엔진이 잘못 낸 것입니다. 판독자가 고칠 수 없습니다.",
        ["① 다음 판에 **엔진을 고친다** — 시스템 담당자 몫입니다",
         "② 2차에서 **손으로 바로잡는다** — 이번 판만 넘깁니다",
         "③ **그대로 둔다** — 영향이 작다고 보면 그렇게 정합니다"],
    ),
}


def _원문찾기() -> dict:
    if not 최종.exists():
        return {}
    with io.open(최종, encoding="utf-8-sig", newline="") as h:
        return {r["atomic_id"]: r for r in csv.DictReader(h)}


def main() -> int:
    if not 요청.exists():
        print("  보정요청.csv 가 없습니다 — handoff.py 를 먼저 돌리십시오")
        return 1

    with io.open(요청, encoding="utf-8-sig", newline="") as h:
        행 = list(csv.DictReader(h))
    if not 행:
        print("  보정 요청이 없습니다 — 낼 것이 없었습니다")
        return 0

    데이터 = _원문찾기()

    def 건수(r):
        s = str(r.get("건수") or "0")
        return int(s) if s.isdigit() else 0

    행.sort(key=건수, reverse=True)
    합 = sum(건수(r) for r in 행)

    L = ["# 보정 요청 — 같이 보고 정할 것", ""]
    L.append("> 2차 판독과 3차 감독에서 나온 것을 **한자리에** 모았습니다.")
    L.append("> 판독자가 스스로 못 정하고 **회사가 정해야** 하는 것들입니다.")
    L.append("")
    L.append("- 묶음 **%d개** · 걸린 행 **%s행**" % (len(행), "{:,}".format(합)))
    L.append("- 만든 때 — 이 파일은 `3차_마무리.py` 가 낼 때마다 새로 씁니다")
    L.append("")
    L.append("## 한눈에")
    L.append("")
    L.append("| | 언제 | 건수 | 무엇을 정해야 하나 |")
    L.append("|---|---|---|---|")
    for i, r in enumerate(행, 1):
        L.append("| %d | %s | %s | %s |"
                 % (i, (r.get("나온_회차") or "").split("(")[0].strip(),
                    "{:,}".format(건수(r)),
                    (r.get("무엇이_문제인가") or "").split("/", 1)[-1].strip()))
    L.append("")
    L.append("---")
    L.append("")

    for i, r in enumerate(행, 1):
        갈래 = (r.get("갈래") or "").strip()
        제목 = (r.get("무엇이_문제인가") or "").split("/", 1)[-1].strip()
        L.append("## %d. %s" % (i, 제목))
        L.append("")
        L.append("| | |")
        L.append("|---|---|")
        L.append("| **언제 나왔나** | %s |" % (r.get("나온_회차") or "-"))
        L.append("| **접수** | %s |" % (r.get("접수일") or "-"))
        L.append("| **걸린 행** | %s행 |" % "{:,}".format(건수(r)))
        L.append("| **갈래** | %s |" % (갈래 or "-"))
        L.append("")

        말 = (r.get("판독자_제안") or "").strip()
        if 말:
            L.append("**판독자가 본 것**")
            L.append("")
            L.append("> " + 말.replace("\n", " "))
            L.append("")

        # 대표 행의 실제 원문 — 근거 없이는 정할 수 없다
        ids = [x.strip() for x in (r.get("근거_atomic_id") or "").split("|")
               if x.strip()][:3]
        보기 = []
        for aid in ids:
            d = 데이터.get(aid)
            if not d:
                continue
            글 = (d.get("atomic_voc") or d.get("voc_cleaned") or "").strip()
            if 글:
                보기.append((aid, 글[:150], (d.get("topic") or "").strip()))
        if 보기:
            L.append("**무엇을 보고 판단하나 — 실제 발화**")
            L.append("")
            for aid, 글, tp in 보기:
                L.append("- 「%s」" % 글)
                L.append("  <sub>%s · 지금 라벨 `%s`</sub>" % (aid, tp or "없음"))
            L.append("")
        elif ids:
            L.append("**대표 행** — %s" % " · ".join("`%s`" % x for x in ids))
            L.append("")

        안내 = 길잡이.get(갈래)
        if 안내:
            L.append("**무엇을 정해야 하나**")
            L.append("")
            L.append(안내[0])
            L.append("")
            for x in 안내[1]:
                L.append("- %s" % x)
            L.append("")

        L.append("**정하면 이 자리에 적습니다**")
        L.append("")
        L.append("```")
        L.append("고른 길 :")
        L.append("까닭    :")
        L.append("정한 날 :          정한 사람 :")
        L.append("```")
        L.append("")
        L.append("---")
        L.append("")

    L.append("## 정한 뒤에 할 일")
    L.append("")
    L.append("1. 정한 것을 `_판독패키지/9_택소노미_2차확장.md` 에 적습니다.")
    L.append("   ★ 적히지 않은 라벨은 판독자마다 다르게 씁니다 —")
    L.append("   실제로 「제품 식별·사양」 이 232건 쓰이는데 기준서에 없어서")
    L.append("   판독자 둘이 129행 갈렸습니다.")
    L.append("2. `보정요청.csv` 의 `처리상태` 를 `반영` 으로 바꿉니다.")
    L.append("3. 다음 판부터 그 기준으로 판독합니다.")
    L.append("")

    낼곳.parent.mkdir(exist_ok=True)
    낼곳.write_text("\n".join(L), encoding="utf-8")
    print("  논의본을 만들었습니다 — %s" % 낼곳.name)
    print("  묶음 %d개 · 걸린 행 %s행" % (len(행), "{:,}".format(합)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
