# -*- coding: utf-8 -*-
"""옛 2판의 **사람 4차 결정**을 우리 판의 「아웃풋1_회의에서_정할것」 에 넣는다 (2026-11-01).

★ 왜 이 도구가 있나 — sky 2026-11-01 —
  「이미 2판 만들 때 데이터가 있으니 **사람이 4차에서 판단해서 준 결과값도 그대로
    있을 거고**.. 그거 대조해서 skill 만 넣었을 때 이전과 동일하게 매 단계에서 …
    최종 2판 결과물과 거의 동일한? 혹은 백프로? 결과가 나오는 skill 인지를 기준으로」

  그리고 「**매번 4차는 사람이 한 게 없어서 임의로 테스트로 넣습니다** 이런 것만 하고」
  라고 지적했다. 그래서 이 도구는 **짐작으로 채우는 칸이 하나도 없다.**
  옛 2판에서 사람이 실제로 적은 값과 **맞물리는 것만** 넣고, 나머지는 **손대지 않는다.**

★ 내가 틀렸던 것 — 「옛 4차 사람 결정이 비어 있다」 고 적었는데 틀렸다.
  `_판독패키지/_결과/master_final/분리제안.csv` 한 폴더만 보고 그랬다.
  사람 결정은 **`s15_master/`** 에 있었다 (아래 두 파일).

넣는 규칙 — **이 둘만** 넣는다

  ① 감독_분리제안.csv  (옛 254행 · 승인상태 전부 「✅ 총괄 확정 …」)
       우리 행의 `origin_atomic_id` 가 옛 254 에 있을 때만 적는다.
         옛 문구에 「과분리를 합친다」  → **반려**  (사람이 「나누지 말라」 고 정했다)
         그 밖의 ✅ 총괄 확정          → **승인**  (나눈다 · 두 안 중 골랐다 ·
                                        자르는 자리만 다름 · 두 감독이 같게 나눴다)
       ★ 조각(segments)은 **우리 감독이 낸 것**을 쓴다. 사람이 정한 것은
         「이 행을 나눌지」 이고, 조각을 어떻게 자를지는 그 판의 감독이 낸 것이다.
         옛 조각을 끌어오면 **옛 AI 판정을 섞는 것**이 되어 재는 것이 흐려진다.

  ② 수정로그_오류확정.csv · 수정로그_재검토필요.csv
       옛 `수정로그_4차규칙_2판.csv` (637행 · 사람이 정한 규칙 적용)와
       **(atomic_id, field) 가 같고 우리 `제안값` 이 옛 `새값` 과 같을 때만** 승인한다.
       옛 `field` 는 `status/topic` 처럼 둘이 붙어 있을 수 있어 `/` 로 가른다.
       ★ 같은 (atomic_id, field) 에 승인이 둘 되지 않게 한다 — 돌리개가
         「어느 쪽이 들어갔는지 사람이 알 수 없다」 며 멈춘다. 첫 하나만 승인, 나머지 반려.

손대지 않는 것 (사람이 옛 2판에서 **정하지 않았다**)

  · 분리제안.csv (판독자가 낸 것)  — 옛 264행 전부 「사람 최종 승인 대기」 였다
  · 보정요청.csv                  — 옛 3행 전부 「대기」 였다
  · 위 ①② 에서 맞물리지 않은 행   — 빈칸으로 둔다 (= 보류 · 반영 안 됨)

쓰기 —
    python tools/4차_사람결정_넣기.py <판자리> --확인만     셈만 한다 (아무것도 안 쓴다)
    python tools/4차_사람결정_넣기.py <판자리>              넣는다 (넣기 전 사본을 남긴다)
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin" / "shared"))
import paths                                                       # noqa: E402

옛자리 = paths.BASELINE / "원본사본" / "2판" / "s15_master"
_옛분리 = "감독_분리제안.csv"
_옛규칙 = "수정로그_4차규칙_2판.csv"
_합친다 = "과분리를 합친다"
_병합표시 = "MERGE"
_확정표시 = "✅ 총괄 확정"
_수정로그들 = ("수정로그_오류확정.csv", "수정로그_재검토필요.csv")


def 읽기(p: Path) -> list[dict]:
    with io.open(p, encoding="utf-8-sig", newline="") as h:
        return list(csv.DictReader(h))


def 쓰기(p: Path, 줄들: list[dict], 칸들: list[str]) -> None:
    with io.open(p, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=칸들)
        w.writeheader()
        for r in 줄들:
            w.writerow(r)


def 표기_풀기(필드말: str, 새값: str) -> list[tuple[str, str]]:
    """옛 수정로그의 표기를 **(칸, 그 칸에 들어갈 값)** 목록으로 푼다.

    ★ 2026-11-01 — 처음에는 `field` 를 `/` 로 가르고 **같은 `새값` 을 두 칸에 다** 댔다.
      틀렸다. 옛 수정로그는 `field` 에 `status/topic` 처럼 **쌍**을 적고, `새값` 에는
      **한 값을 이 표기로** 적는다 (옛 자료에서 읽은 것이다 — 짐작이 아니다) —

          새값이 `제외(operator_notice)` 꼴  → status=scope_excluded ·
                                              scope_exclusion_reason=operator_notice ·
                                              topic=N/A
          그 밖(라벨 이름)                   → topic=<그 이름> · status=normal

      그래서 `status` 칸의 제안값 `scope_excluded` 가 옛 `새값` 과 글자로 같을 수가
      없었고, 사람이 「제외」 로 정한 **18행을 내가 반려로 떨어뜨렸다.**
      총괄 AI 가 그것을 찾아 `4차반영_사슬구멍_status.csv` 에 적어 주었다.
    """
    칸들 = [c.strip() for c in 필드말.split("/") if c.strip()]
    값 = (새값 or "").strip()
    m = re.match(r"^제외\((.+)\)$", 값)
    out: list[tuple[str, str]] = []
    if m:
        사유 = m.group(1).strip()
        if "status" in 칸들 or "topic" in 칸들:
            out += [("status", "scope_excluded"),
                    ("scope_exclusion_reason", 사유),
                    ("topic", "N/A")]
    else:
        if "topic" in 칸들:
            out.append(("topic", 값))
        if "status" in 칸들:
            out.append(("status", "normal"))
    for c in 칸들:
        if c not in ("status", "topic"):
            out.append((c, 값))
    return out


def 옛결정_읽기() -> tuple[dict, dict]:
    """옛 2판에서 **사람이 적은 것**을 읽는다. 없으면 멈춘다 — 못 찾음은 통과가 아니다."""
    분 = 옛자리 / _옛분리
    규 = 옛자리 / _옛규칙
    for q in (분, 규):
        if not q.is_file():
            raise SystemExit(
                "옛 2판의 사람 4차 결정을 못 찾았습니다 — %s\n"
                "  ★ 못 찾음은 통과가 아닙니다. 이 파일 없이는 「사람 결정을 넣었다」 고\n"
                "    말할 수 없습니다. 기준 자리를 확인하십시오: %s" % (q, 옛자리))

    분리 = {}
    for r in 읽기(분):
        말 = (r.get("승인상태") or "").strip()
        if _확정표시 not in 말:
            continue                                   # 사람이 확정하지 않은 것은 안 쓴다
        분리[(r.get("origin_atomic_id") or "").strip()] = 말

    규칙 = {}
    for r in 읽기(규):
        aid = (r.get("atomic_id") or "").strip()
        if not aid:
            continue
        for 칸, 값 in 표기_풀기(r.get("field") or "", r.get("새값") or ""):
            규칙.setdefault((aid, 칸), set()).add(값)
    return 분리, 규칙


def 분리_넣기(쪽: Path, 분리: dict, 쓸까: bool) -> Counter:
    c = Counter()
    줄들 = 읽기(쪽)
    칸들 = list(줄들[0].keys()) if 줄들 else []
    for r in 줄들:
        키 = (r.get("origin_atomic_id") or "").strip()
        c["우리 행"] += 1
        if 키 not in 분리:
            c["사람이 안 정함 — 그대로 둔다"] += 1
            continue
        if _합친다 in 분리[키]:
            r["승인상태"] = "반려"
            c["반려 (사람이 합치라고 정했다)"] += 1
        elif (r.get("segments") or "").strip().strip(chr(34)) == _병합표시:
            # ★ 2026-11-01 — 감독이 「합쳐야 한다」 로 낸 것이다 (segments 가 "MERGE").
            #   `apply_split.py` 에는 **병합을 하는 코드가 없다** (merge 를 찾으면 0건).
            #   그래서 승인해도 사슬이 아무것도 못 한다. 조용히 넘기지 않고
            #   반려로 두고 **셈에 따로 적어** 사람이 보게 한다.
            r["승인상태"] = "반려"
            c["★ 반려 — 감독이 「합쳐야」 라 했으나 사슬에 병합 코드가 없다"] += 1
        else:
            r["승인상태"] = "승인"
            c["승인 (사람이 나누라고 정했다)"] += 1
    if 쓸까 and 줄들:
        쓰기(쪽, 줄들, 칸들)
    return c


def 수정로그_넣기(쪽: Path, 규칙: dict, 이미승인: set, 쓸까: bool) -> Counter:
    c = Counter()
    줄들 = 읽기(쪽)
    if not 줄들:
        return c
    칸들 = list(줄들[0].keys())
    for r in 줄들:
        c["우리 행"] += 1
        aid = (r.get("atomic_id") or "").strip()
        칸 = (r.get("field") or "").strip()
        제안 = (r.get("제안값") or "").strip()
        값들 = 규칙.get((aid, 칸))
        if not 값들:
            c["사람 결정에 없는 수정 — 그대로 둔다"] += 1
            continue
        if 제안 not in 값들:
            r["승인상태"] = "반려"
            c["반려 (사람이 정한 값과 다르다)"] += 1
            continue
        if (aid, 칸) in 이미승인:
            r["승인상태"] = "반려"
            c["반려 (같은 칸에 이미 승인이 있다)"] += 1
            continue
        r["승인상태"] = "승인"
        이미승인.add((aid, 칸))
        c["★ 승인 (사람이 정한 값과 같다)"] += 1
    if 쓸까:
        쓰기(쪽, 줄들, 칸들)
    return c


def 분리재지정_만들기(판: Path, 이름: str, 쓸까: bool) -> tuple[int, int]:
    """승인된 분리를 `apply_split.py` 가 읽는 모양으로 적는다.

    ★ 머리말에 **자동 생성**임과 원본을 적는다 — 옛 2판의 같은 파일이 그랬다.
      조각은 **우리 감독이 낸 `segments`** 를 그대로 쓴다 (옛 조각을 끌어오지 않는다).
    """
    쪽 = 판 / "아웃풋1_회의에서_정할것" / "감독_분리제안.csv"
    낼곳 = 판 / "총괄" / 이름 / "_판독패키지" / "_결과" / "분리재지정_01_사람결정.md"
    줄들 = [r for r in 읽기(쪽) if (r.get("승인상태") or "").strip() == "승인"]
    적은것, 못적은것 = [], 0
    for r in 줄들:
        try:
            조각 = json.loads(r.get("segments") or "")
        except Exception:
            못적은것 += 1
            continue
        if not isinstance(조각, list) or not 조각:
            못적은것 += 1
            continue
        적은것.append({"atomic_id": (r.get("origin_atomic_id") or "").strip(),
                     "split": 조각,
                     "why": (r.get("why") or "")[:400]})
    if 쓸까 and 적은것:
        낼곳.parent.mkdir(parents=True, exist_ok=True)
        with io.open(낼곳, "w", encoding="utf-8", newline="\n") as h:
            h.write("# 총괄이 확정한 분리·병합 — apply_split 이 읽습니다\n\n")
            h.write("★ 자동 생성입니다. 손으로 고치지 마십시오.\n")
            h.write("  원본은 `아웃풋1_회의에서_정할것/감독_분리제안.csv` 의 승인된 행입니다.\n")
            h.write("  승인 판정은 **옛 2판에서 사람이 확정한 것**을 그대로 옮긴 것입니다\n")
            h.write("  (`tools/4차_사람결정_넣기.py` · %s).\n\n"
                    % datetime.now().strftime("%Y-%m-%d %H:%M"))
            for o in 적은것:
                h.write(json.dumps(o, ensure_ascii=False) + "\n\n")
    return len(적은것), 못적은것


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("판자리")
    p.add_argument("--이름", default="2판통째")
    p.add_argument("--확인만", action="store_true", help="셈만 한다 — 아무것도 안 쓴다")
    a = p.parse_args()
    판 = Path(a.판자리).resolve()
    회의 = 판 / "아웃풋1_회의에서_정할것"
    if not 회의.is_dir():
        raise SystemExit("회의 자리가 없습니다 (%s) — 아웃풋1 까지 끝난 판이어야 합니다" % 회의)
    쓸까 = not a.확인만

    분리, 규칙 = 옛결정_읽기()
    print("=" * 74)
    print("  옛 2판의 **사람 4차 결정**을 넣습니다 — %s" % 판)
    print("  읽은 곳: %s" % 옛자리)
    print("    감독_분리제안 확정 %d행 · 4차규칙 (atomic_id,field) %d자리"
          % (len(분리), len(규칙)))
    print("  %s" % ("★ --확인만 — 아무것도 쓰지 않습니다" if a.확인만 else "넣습니다 (사본을 먼저 남깁니다)"))
    print("=" * 74)

    if 쓸까:
        때 = datetime.now().strftime("%Y%m%d_%H%M")
        보관 = 판 / ("_4차넣기전_%s" % 때)
        보관.mkdir(parents=True, exist_ok=True)
        for 이름 in (_옛분리,) + _수정로그들:
            q = 회의 / 이름
            if q.is_file():
                shutil.copy2(q, 보관 / 이름)
        최종 = 판 / "총괄" / a.이름 / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv"
        if 최종.is_file():
            shutil.copy2(최종, 보관 / "raw_voc_3차최종.csv")
        print("  · 넣기 전 사본을 남겼습니다 — %s" % 보관)

    print("\n── ① 감독_분리제안.csv")
    c1 = 분리_넣기(회의 / _옛분리, 분리, 쓸까)
    for k, n in c1.most_common():
        print("     %-34s %5d" % (k, n))

    이미승인: set = set()
    for 이름 in _수정로그들:
        q = 회의 / 이름
        if not q.is_file():
            print("\n── ② %s — 없습니다" % 이름)
            continue
        print("\n── ② %s" % 이름)
        c2 = 수정로그_넣기(q, 규칙, 이미승인, 쓸까)
        for k, n in c2.most_common():
            print("     %-34s %5d" % (k, n))

    print("\n── ③ 분리재지정 파일 (apply_split 이 읽는 것)")
    적은, 못적은 = 분리재지정_만들기(판, a.이름, 쓸까)
    print("     적은 행 %d · 조각을 못 읽은 행 %d" % (적은, 못적은))
    if 못적은:
        print("     ★ 조각을 못 읽은 행이 있습니다 — segments 가 JSON 이 아닙니다. 봐야 합니다.")
    if c1.get("★ 반려 — 감독이 「합쳐야」 라 했으나 사슬에 병합 코드가 없다"):
        print()
        print("  ★★ 사슬의 구멍 — 3차 감독의 **병합(MERGE) 판정 %d건**을 4차가 못 받습니다."
              % c1["★ 반려 — 감독이 「합쳐야」 라 했으나 사슬에 병합 코드가 없다"])
        print("     `plugin/shared/tools/apply_split.py` 에 merge 를 다루는 코드가 없습니다")
        print("     (`grep merge` 0건). 나누기만 하고 합치기는 사람 손으로 가야 합니다.")

    print("\n" + "=" * 74)
    if a.확인만:
        print("  아무것도 쓰지 않았습니다. 넣으려면 --확인만 을 떼십시오.")
    else:
        print("  넣었습니다. 다음 —")
        print('    python plugin/skills/coordinating-voc-pipeline/scripts/한줄_돌리기.py "%s" --4차반영'
              % 판)
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
