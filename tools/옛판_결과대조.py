# -*- coding: utf-8 -*-
"""우리 스킬이 낸 결과를 **옛 2판 최종**과 행·칸마다 댄다 — 「몇 % 같은가」 (2026-10-29).

★ 왜 이 도구가 있나 — sky 물음 2026-10-29

  > 「그냥 skill이 이전에 만들어놓은 1차 크롤링 및 분석부터 꾸러미 순서대로 2차 3차 4차
  >   최종까지 2판 기준으로 똑같이 나오기만 하면되는대요… 이미 2판 만들때 데이터가 있으니
  >   사람이 4차에서 판단해서 준 결과값도 그대로 있을거고.. 그거 대조해서 skill만 넣었을 때
  >   이전과 동일하게 매 단계에서(100프로 맞는게 아니고 일부 데이터 좀 차이가 생길수는
  >   있지만) 그 과정을 거쳐서 최종2판 결과물과 거의 동일한? 혹은 백프로?.. 결과가 나오는
  >   skill인지를 기준으로 skill을 완성본 만들어야하는데」

  **맞는 기준이다.** 단계마다 옛 도구를 돌려 만든 정답과 대는 장치는 이미 있다
  (`tests/test_baseline.py` · 얼린 정답 8개). 그런데 그 대조는 **AI 판정을 옛것으로
  고정**하고 **도구 부분만** 댄다. **한 줄로 통째로 돌려 최종을 옛것과 댄 적이 없다.**

  통째로 돌리면 2·3차 AI 가 새로 판정하므로 최종은 옛것과 **같을 수 없다.**
  그래서 묻는 것이 「같은가」 가 아니라 **「몇 % 같은가」** 이고, **그것이 정확도다.**
  **옛 2판 최종이 정답지다** — 내가 「채점할 정답지가 없다」 고 말해 온 것은 틀렸다.

★ 돈을 쓰기 전에 **이 장치가 맞게 세는지**부터 본다 (sky 2026-10-29 「장치 먼저 만들고
  돈 쓰기 전에 확인」). 그 확인은 `tests/test_옛판대조.py` 가 한다 — 옛것을 자기 자신과
  대어 100%가 나오는가 · 일부러 N 행을 바꾸면 **정확히 N 행**을 잡는가 · 행을 지우거나
  더하면 한쪽만 있는 것으로 세는가 · 열쇠나 칸이 없으면 **크게 실패**하는가.

무엇을 내나
-----------
  행   양쪽에 있는 `atomic_id` · 옛에만 · 새에만  (분리·병합이 생기면 여기 드러난다)
  칸   `6_판정대상_컬럼분류.md` 의 **A·B·C·D** 묶음마다 「같은 행 / 몇 %」
         A 원천 고정값   ← 여기가 다르면 **정확도가 아니라 결함**이다
         B 기계 계산
         C 참고
         D ★판정 대상   ← **이것이 정확도다**
       그 글이 **안 다루는 칸**(대시보드 파생 8 · 2·3·4차 판정 10 등)은 따로 센다.
       숨기지 않는다 — 안 다룬다는 것 자체가 `docs/기준서개정후보.md` 후보 1 이다.

★ 칸 묶음을 **손으로 적지 않는다** — 기준 글에서 긁는다. 다만 그 글에는
  **줄 그은 칸**(`~~product_category~~` · v1.1 삭제)과 **줄임말**(`+ 각 `_evidence``)이
  있다. 줄 그은 것은 뺀다. 데이터에 없는 이름은 **조용히 버리지 않고 찍는다.**

쓰기
    python tools/옛판_결과대조.py <새 결과 csv> [--옛 <옛 csv>] [--자세히] [--같아야]

    --옛      안 주면 `paths.py` 의 BASELINE 아래 옛 2판 최종을 쓴다
    --자세히   칸마다 다른 행을 열 개까지 보여 준다
    --같아야   100% 가 아니면 종료코드 1 (장치를 확인할 때 쓴다)
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import BASELINE, SHARED  # noqa: E402

열쇠 = "atomic_id"
_옛최종 = Path("_판독패키지") / "_결과" / "master_final" / "raw_voc.csv"
분류글 = SHARED / "standards" / "6_판정대상_컬럼분류.md"
묶음이름 = {"A": "A 원천 고정값", "B": "B 기계 계산", "C": "C 참고",
          "D": "D ★판정 대상"}


def 칸묶음() -> tuple[dict, dict]:
    """기준 글에서 A·B·C·D 묶음을 긁는다. 돌려주는 것 — (묶음, 글이_적은_칸수)."""
    if not 분류글.is_file():
        raise SystemExit("못 찾음: %s — 칸을 묶을 수 없다 (통과가 아니다)" % 분류글)
    글 = 분류글.read_text(encoding="utf-8")
    묶음: dict = {}
    적힌수: dict = {}
    쪽들 = re.split(r"(?m)^#\s+([ABCD])\.\s*(.*)$", 글)
    # 쪽들 = [머리, 'A', '제목', 본문, 'B', '제목', 본문, ...]
    for i in range(1, len(쪽들) - 2, 3):
        갈래, 제목, 본문 = 쪽들[i], 쪽들[i + 1], 쪽들[i + 2]
        본문 = re.split(r"(?m)^#\s", 본문)[0]
        m = re.search(r"\(([0-9]+)칸\)", 제목)
        적힌수[갈래] = int(m.group(1)) if m else 0
        난것 = []
        칸자리 = None            # 표에서 「컬럼」 이 몇 번째 칸인가
        for 줄 in 본문.splitlines():
            if not 줄.lstrip().startswith("|"):
                continue
            쪼갠것 = [c.strip() for c in 줄.strip().strip("|").split("|")]
            if 칸자리 is None:
                # ★ 표 머리에서 「컬럼」 자리를 찾는다. A·B·C 는 `| 컬럼 | 근거 |`,
                #   D 는 `| 축 | 컬럼 | 핵심 규칙 |` 이다.
                if "컬럼" in 쪼갠것:
                    칸자리 = 쪼갠것.index("컬럼")
                continue
            if all(set(c) <= set("-: ") for c in 쪼갠것):
                continue            # |---|---| 줄
            if 칸자리 >= len(쪼갠것):
                continue
            # ★ 2026-10-29 — 전에는 **줄 전체**에서 긁었다. 그래서 D 표의 「핵심 규칙」 칸에
            #   적힌 설명까지 칸 이름으로 읽었고, `confidence_rating`(「이것만 엔진 계산이다」 는
            #   **제외 설명**이다)이 B 와 D 에 **둘 다** 들어갔다. 「컬럼」 칸만 읽는다.
            #   C 에서는 trace 토큰 다섯(`e1_evidence_guard` 등)이 같은 식으로 섞여 들어왔다.
            칸글 = 쪼갠것[칸자리]
            # ★ 줄 그은 칸은 뺀다 — 그 글이 「삭제」 라고 적은 것이다
            깬줄 = re.sub(r"~~[^~]*~~", "", 칸글)
            이름들 = re.findall(r"`([A-Za-z_][A-Za-z0-9_*]*)`", 깬줄)
            # ★ `+ 각 `_evidence`` 처럼 **줄임말**로 적힌 줄이 있다. 그 줄의 `*_score` 에서 펴 준다.
            #   손으로 네 이름을 적지 않는다 — 적으면 그 글이 바뀔 때 여기가 낡는다.
            if "_evidence" in 이름들:
                편것 = [n[:-6] + "_evidence" for n in 이름들 if n.endswith("_score")]
                이름들 = [n for n in 이름들 if n != "_evidence"] + 편것
            for n in 이름들:
                # ★ `ENGINE_OWNED_COLUMNS` 처럼 **대문자 식별자**는 코드 묶음 이름이지 칸이 아니다
                if n.isupper():
                    continue
                if n not in 난것:
                    난것.append(n)
        묶음[갈래] = 난것
    if not 묶음:
        raise SystemExit("못 찾음: %s 에서 A·B·C·D 묶음을 하나도 못 긁었다" % 분류글.name)
    # ★ 한 칸이 두 묶음에 들면 그 글이 **스스로 어긋난 것**이다. 조용히 넘기지 않는다 —
    #   실제로 긁기 버그로 `confidence_rating` 이 B·D 에 둘 다 들어간 적이 있다 (2026-10-29).
    본데 = {}
    겹침 = {}
    for 갈래 in ("A", "B", "C", "D"):
        for n in 묶음.get(갈래, []):
            if n in 본데:
                겹침.setdefault(n, [본데[n]]).append(갈래)
            else:
                본데[n] = 갈래
    if 겹침:
        raise SystemExit("%s 에서 한 칸이 **두 묶음**에 들어 있다 — %s\n"
                         "  긁기가 틀렸거나 그 글이 스스로 어긋난 것이다. 고치고 다시 보십시오."
                         % (분류글.name, {k: " · ".join(v) for k, v in 겹침.items()}))
    return 묶음, 적힌수


def 읽기(쪽: Path) -> tuple[list, list]:
    if not 쪽.is_file():
        raise SystemExit("못 찾음: %s — 댈 수 없다 (통과가 아니다)" % 쪽)
    with 쪽.open(encoding="utf-8-sig", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        줄들 = list(r)
        머리 = list(r.fieldnames or [])
    if 열쇠 not in 머리:
        raise SystemExit("못 찾음: `%s` 칸이 %s 에 없다 — 행을 맞출 수 없다" % (열쇠, 쪽.name))
    빈것 = sum(1 for x in 줄들 if not (x.get(열쇠) or "").strip())
    if 빈것:
        raise SystemExit("`%s` 가 빈 행이 %s 에 %d개 — 행을 맞출 수 없다" % (열쇠, 쪽.name, 빈것))
    return 줄들, 머리


def 대조(옛쪽: Path, 새쪽: Path, 자세히: bool = False) -> dict:
    # ★ 2026-10-29 — 차례를 **옛 먼저**로 둔다. 전에는 `대조(새, 옛)` 이었고,
    #   「옛것과 새것을 댄다」 로 읽혀 시험에서 거꾸로 불렀다. 값만 다른 경우에는
    #   대칭이라 안 드러나고, **행을 지우거나 더한 경우에만** 드러났다.
    옛줄, 옛머리 = 읽기(옛쪽)
    새줄, 새머리 = 읽기(새쪽)
    묶음, 적힌수 = 칸묶음()

    새표 = {x[열쇠]: x for x in 새줄}
    옛표 = {x[열쇠]: x for x in 옛줄}
    양쪽 = [k for k in 옛표 if k in 새표]            # 옛 차례를 따른다
    옛에만 = [k for k in 옛표 if k not in 새표]
    새에만 = [k for k in 새표 if k not in 옛표]

    같은칸 = [c for c in 옛머리 if c in 새머리]
    옛칸만 = [c for c in 옛머리 if c not in 새머리]
    새칸만 = [c for c in 새머리 if c not in 옛머리]

    # 칸마다 「양쪽에 있는 행 중 값이 같은 행 수」
    칸결과 = {}
    보기 = {}
    for c in 같은칸:
        같다, 다른것 = 0, []
        for k in 양쪽:
            a = (옛표[k].get(c) or "").strip()
            b = (새표[k].get(c) or "").strip()
            if a == b:
                같다 += 1
            elif len(다른것) < 10:
                다른것.append((k, a[:60], b[:60]))
        칸결과[c] = 같다
        if 자세히 and 다른것:
            보기[c] = 다른것

    # 묶음마다 — 그 묶음의 칸이 **다 같은 행**의 수
    묶음결과 = {}
    묶은칸 = {}
    덮인칸: set = set()
    for 갈래 in ("A", "B", "C", "D"):
        이름들 = [n for n in 묶음.get(갈래, []) if n in 같은칸]
        묶은칸[갈래] = 이름들
        덮인칸 |= set(이름들)
        if not 이름들:
            묶음결과[갈래] = None
            continue
        같다 = sum(1 for k in 양쪽
                 if all((옛표[k].get(c) or "").strip() == (새표[k].get(c) or "").strip()
                        for c in 이름들))
        묶음결과[갈래] = 같다
    안덮인 = [c for c in 같은칸 if c not in 덮인칸]
    안덮인_같다 = (sum(1 for k in 양쪽
                   if all((옛표[k].get(c) or "").strip() == (새표[k].get(c) or "").strip()
                          for c in 안덮인)) if 안덮인 else None)

    # 글에 적힌 이름 중 **데이터에 없는 것** — 조용히 버리지 않는다
    데이터에없는 = {갈래: [n for n in 묶음.get(갈래, []) if n not in 옛머리 and n not in 새머리]
                for 갈래 in ("A", "B", "C", "D")}

    return {"새쪽": 새쪽, "옛쪽": 옛쪽, "새행": len(새줄), "옛행": len(옛줄),
            "양쪽": len(양쪽), "옛에만": 옛에만, "새에만": 새에만,
            "같은칸": 같은칸, "옛칸만": 옛칸만, "새칸만": 새칸만,
            "칸결과": 칸결과, "보기": 보기,
            "묶음결과": 묶음결과, "묶은칸": 묶은칸, "적힌수": 적힌수,
            "안덮인": 안덮인, "안덮인_같다": 안덮인_같다,
            "데이터에없는": 데이터에없는}


def _퍼센트(같다: int, 전체: int) -> str:
    return "—" if not 전체 else "%6.2f%%" % (100.0 * 같다 / 전체)


def 말하기(r: dict) -> None:
    n = r["양쪽"]
    print("=" * 76)
    print("  옛 2판 최종과 대조 — 열쇠 `%s`" % 열쇠)
    print("=" * 76)
    print("  옛  %s" % r["옛쪽"])
    print("  새  %s" % r["새쪽"])
    print()
    print("  행 — 옛 %d · 새 %d · **양쪽 %d** · 옛에만 %d · 새에만 %d"
          % (r["옛행"], r["새행"], n, len(r["옛에만"]), len(r["새에만"])))
    if r["옛에만"] or r["새에만"]:
        print("     ★ 한쪽만 있는 행은 **분리·병합이 달라졌다**는 뜻이다 (값 차이가 아니다)")
        if r["옛에만"]:
            print("       옛에만: %s%s" % (" · ".join(r["옛에만"][:5]),
                                        " …" if len(r["옛에만"]) > 5 else ""))
        if r["새에만"]:
            print("       새에만: %s%s" % (" · ".join(r["새에만"][:5]),
                                        " …" if len(r["새에만"]) > 5 else ""))
    print("  칸 — 옛 %d · 새 %d · 양쪽 %d · 옛칸만 %d · 새칸만 %d"
          % (len(r["칸결과"]) + len(r["옛칸만"]), len(r["칸결과"]) + len(r["새칸만"]),
             len(r["같은칸"]), len(r["옛칸만"]), len(r["새칸만"])))
    if r["옛칸만"]:
        print("     ★ 옛에만 있는 칸: %s" % " · ".join(r["옛칸만"]))
    if r["새칸만"]:
        print("     ★ 새에만 있는 칸: %s" % " · ".join(r["새칸만"]))
    print()
    print("  묶음마다 — 그 묶음의 칸이 **다 같은 행**")
    for 갈래 in ("A", "B", "C", "D"):
        같다 = r["묶음결과"][갈래]
        칸들 = r["묶은칸"][갈래]
        적힌 = r["적힌수"].get(갈래, 0)
        꼬리 = ""
        if 적힌 and len(칸들) != 적힌:
            # ★ 2026-10-29 — 이것은 **발견**이다. 기준 글의 **머리에 적힌 수가 그 글의 표와
            #   어긋난다** (v1.1·v1.2 에서 칸을 옮기고 더하면서 머리를 안 고쳤다).
            #   여기서 글을 고치지 않는다 — 원문 개정은 `docs/기준서개정후보.md` 후보 1 이다.
            꼬리 = ("  ★ 글 머리는 %d칸이라는데 그 글의 **표에는 %d칸**이다 (후보 1)"
                  % (적힌, len(칸들)))
        if 같다 is None:
            print("     %-14s 댈 칸이 없다%s" % (묶음이름[갈래], 꼬리))
            continue
        표 = "     %-14s %5d / %5d = %s  (칸 %d)%s" % (
            묶음이름[갈래], 같다, n, _퍼센트(같다, n), len(칸들), 꼬리)
        print(표)
        if 갈래 == "A" and 같다 != n:
            print("        ★ **원천이 다르다 — 이것은 정확도가 아니라 결함이다.**")
        if 갈래 == "D":
            print("        ↑ **이것이 정확도다** (2차·3차가 채우는 칸)")
    if r["안덮인"]:
        print("     %-14s %5s / %5d = %s  (칸 %d — 분류 글이 **안 다루는** 칸)"
              % ("(분류 밖)", r["안덮인_같다"], n, _퍼센트(r["안덮인_같다"], n), len(r["안덮인"])))
        print("        %s" % " · ".join(r["안덮인"]))
        print("        ↑ 대시보드 파생 · 2·3·4차 판정 칸이다 — `docs/기준서개정후보.md` 후보 1")
    못찾은 = {k: v for k, v in r["데이터에없는"].items() if v}
    if 못찾은:
        print()
        print("  ★ 기준 글에 적혀 있는데 **데이터에 없는 이름** (조용히 버리지 않는다)")
        for 갈래, 이름들 in 못찾은.items():
            print("     %s — %s" % (묶음이름[갈래], " · ".join(이름들)))
    print()
    다른칸 = sorted(((n - c, 이름) for 이름, c in r["칸결과"].items() if c != n), reverse=True)
    print("  칸마다 — 다른 행이 많은 순 (%d칸)" % len(다른칸))
    if not 다른칸:
        print("     · 모든 칸이 양쪽 행에서 값까지 같다")
    for 다름, 이름 in 다른칸[:25]:
        갈래 = next((g for g in "ABCD" if 이름 in r["묶은칸"][g]), "-")
        print("     [%s] %-32s 다른 행 %5d (%s)" % (갈래, 이름, 다름, _퍼센트(다름, n)))
        for k, a, b in r["보기"].get(이름, []):
            print("          %s  옛 %r / 새 %r" % (k, a, b))
    if len(다른칸) > 25:
        print("     … %d칸 더" % (len(다른칸) - 25))
    print("=" * 76)


def main(인자: list) -> int:
    if not 인자 or 인자[0].startswith("--"):
        print(__doc__.strip().splitlines()[-4].strip())
        print("  쓰기: python tools/옛판_결과대조.py <새 결과 csv> [--옛 <옛 csv>] [--자세히] [--같아야]")
        return 2
    새쪽 = Path(인자[0])
    옛쪽 = BASELINE / "원본사본" / "2판" / _옛최종
    if "--옛" in 인자:
        i = 인자.index("--옛") + 1
        if i >= len(인자):
            raise SystemExit("`--옛` 뒤에 자리를 주십시오")
        옛쪽 = Path(인자[i])
    r = 대조(옛쪽, 새쪽, 자세히="--자세히" in 인자)
    말하기(r)
    if "--같아야" in 인자:
        틀림 = (r["옛에만"] or r["새에만"] or r["옛칸만"] or r["새칸만"]
              or any(c != r["양쪽"] for c in r["칸결과"].values()))
        if 틀림:
            print("  ✗ `--같아야` 인데 다른 곳이 있다")
            return 1
        print("  · `--같아야` — 다른 곳이 없다")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
