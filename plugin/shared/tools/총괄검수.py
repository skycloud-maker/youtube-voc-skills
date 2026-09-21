# -*- coding: utf-8 -*-
"""총괄 검수 — 감독 둘이 어긋난 것을 갈래로 나누고 판정 자리를 차린다 (축1 ③).

★ 왜 (sky 2026-08-26)
  「총괄이 검수를 통해 4차 실무자가 볼 것을 줄인다」
  1판에는 없던 단계다. 2판에서 680행을 0행으로 줄인 자리다.

★ 사람이 하는 것 — **판정 그 자체.** 문맥을 봐야 한다.
  기계로 밀지 않는다. 4차 때 §8 후보 72행 중 45행이 오탐이었다.

★ 이 도구가 하는 것 — 사람이 판정하기 **쉽게 차려 놓는다.**
  ① 갈래 나누기      근거가 원문의 다른 대목을 가리키면 「나눌 것」
                     같은 대목이면 「이름만 다름」
  ② 규칙 후보 뽑기    되풀이되는 라벨 쌍 · 제외 사유 무리
  ③ 판정 자리 만들기  수정로그 틀에 2차·3차 판단을 미리 붙여 둔다
  ④ 남은 것 세기

쓰기
    python 총괄검수.py <2차번들1> <2차번들2>
    python 총괄검수.py <2차번들1> <2차번들2> --확인만
"""
from __future__ import annotations

import collections
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
M = ROOT / "s15_master"
R = ROOT / "_판독패키지" / "_결과"

_확인만 = "--확인만" in sys.argv
_반영 = "--반영" in sys.argv


def 줄(표: str, 말: str) -> None:
    print("  %s %s" % (표, 말))


def _읽기(p: Path) -> list:
    if not p.exists():
        return []
    with io.open(p, encoding="utf-8-sig", newline="") as h:
        return list(csv.DictReader(h))


def _번들찾기() -> list:
    """argv 로 받거나, _결과 밑에서 raw_voc.csv 를 가진 폴더를 찾는다."""
    준것 = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(준것) >= 2:
        골 = []
        for a in 준것[:2]:
            p = Path(a)
            골.append(p if p.is_absolute() else (R / a))
        return 골
    후보 = [d for d in sorted(R.glob("*"))
            if d.is_dir() and (d / "raw_voc.csv").exists()
            and d.name not in ("master_final",)]
    return 후보


def _값(r: dict) -> str:
    if not r:
        return ""
    if str(r.get("status") or "") == "scope_excluded":
        return "제외 (%s)" % (r.get("scope_exclusion_reason") or "")
    return "라벨 %s" % (r.get("topic") or "")


def _자리(원: str, 인용: str):
    """근거 인용이 원문 어디를 가리키나 (공백을 지우고 찾는다)."""
    t = re.sub(r"\s+", "", 인용 or "")
    if not t:
        return None
    k = 원.find(t)
    return (k, k + len(t)) if k >= 0 else None



def 반영하기() -> int:
    """채운 판정을 raw_voc 에 되돌려 넣고 수정로그를 남긴다.

    ★ 이 자리가 없어서 이번 판에는 사람이 임시 스크립트로 했다.
      §9(위생 이름 통일) 가 반영되지 않으면 PL Issue 의 위생이 0행이 된다.
    """
    import shutil
    import time

    자리표 = M / "총괄검수_판정자리.csv"
    if not 자리표.exists():
        줄("!", "총괄검수_판정자리.csv 가 없습니다 — 먼저 검수를 돌리십시오")
        return 1
    판정 = [x for x in _읽기(자리표) if (x.get("총괄_판정") or "").strip()]
    if not 판정:
        줄("!", "채워진 판정이 없습니다 — 총괄_판정 칸을 채운 뒤 돌리십시오")
        return 1

    raw = M / "raw_voc.csv"
    if not raw.exists():
        줄("!", "s15_master/raw_voc.csv 가 없습니다")
        return 1
    행 = _읽기(raw)
    칸 = list(행[0].keys())
    표 = {x["atomic_id"]: x for x in 행}

    if _확인만:
        print()
        print("  ── 확인만 ──────────────────────────────────────")
        print("     %d행을 반영할 참이었습니다. 아무것도 안 남겼습니다." % len(판정))
        return 0

    뒷 = raw.with_name("raw_voc_검수반영전_%s.csv" % time.strftime("%Y%m%d_%H%M"))
    shutil.copy2(raw, 뒷)

    로그, 못찾음 = [], 0
    for x in 판정:
        a = x["atomic_id"]
        r = 표.get(a)
        if not r:
            못찾음 += 1
            continue
        새값 = (x.get("총괄_판정") or "").strip()
        옛값 = ("제외(%s)" % (r.get("scope_exclusion_reason") or "")
                if r.get("status") == "scope_excluded" else (r.get("topic") or ""))
        if 새값.startswith("제외"):
            사유 = 새값[새값.find("(") + 1:새값.rfind(")")] if "(" in 새값 else "no_analytic_value"
            r["status"] = "scope_excluded"
            r["scope_exclusion_reason"] = 사유
            r["topic"] = "N/A"
        else:
            r["status"] = "normal"
            r["scope_exclusion_reason"] = ""
            r["topic"] = 새값
        r["decided_by"] = "총괄검수"
        r["decided_note"] = (x.get("근거") or "")[:300]
        로그.append({
            "atomic_id": a, "field": "topic/status", "옛값": 옛값, "새값": 새값,
            "규칙": x.get("규칙", ""), "근거": x.get("근거", ""),
            "승인상태": x.get("승인상태") or "총괄 판정 — 실무자 확인 요망",
            "원문": " ".join((x.get("atomic_voc") or "").split())[:140],
            "갈래": x.get("로그갈래(A/B/C)", ""),
            "갈래_설명": "",
            # ★ 2차·3차 판단을 함께 남긴다 — 「왜 이렇게 정했나」 를 보려면 있어야 한다
            "2차_판단": " | ".join(str(x.get(c) or "") for c in x if str(c).startswith("2차_")),
            "3차_판단": x.get("3차_판단", ""),
        })

    with io.open(raw, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=칸)
        w.writeheader()
        w.writerows(행)

    # ★ build_master 가 쓰는 **바로 그 파일**에 이어 쓴다 (2026-08-26에 고침).
    #   전에는 s15_master/ 에 따로 만들어 두 파일이 따로 놀았다.
    #   번들에 붙는 것은 master_final 쪽이라, 총괄 판정이 시트에 안 실렸다.
    로그길 = R / "master_final" / "수정로그_재검토필요.csv"
    로그길.parent.mkdir(parents=True, exist_ok=True)
    있 = _읽기(로그길)

    # ★ build_master 의 12칸을 지킨다 — 없애면 읽는 도구가 깨진다.
    #   그 뒤에 총괄 판정 칸을 **더한다.**
    기본칸 = ["source_id", "atomic_id", "atomic_voc", "field",
             "원본값", "제안값", "사유", "근거인용", "오류유형", "승인상태",
             "감독자1", "감독자2"]
    더한칸 = ["규칙", "근거", "갈래", "2차_판단", "3차_판단", "원문"]
    머리 = 기본칸 + 더한칸
    담을것 = []
    for x in 있:
        담을것.append({k: x.get(k, "") for k in 머리})
    for x in 로그:
        a = x["atomic_id"]
        담을것.append({
            "source_id": a.rsplit("-", 1)[0],
            "atomic_id": a,
            "atomic_voc": x.get("원문", ""),
            "field": "topic",
            "원본값": x.get("옛값", ""),
            "제안값": x.get("새값", ""),
            "사유": x.get("근거", ""),
            "근거인용": "",
            "오류유형": "총괄 판정",
            "승인상태": x.get("승인상태", ""),
            "감독자1": x.get("3차_판단", ""),
            "감독자2": "",
            "규칙": x.get("규칙", ""),
            "근거": x.get("근거", ""),
            "갈래": x.get("갈래", ""),
            "2차_판단": x.get("2차_판단", ""),
            "3차_판단": x.get("3차_판단", ""),
            "원문": x.get("원문", ""),
        })
    with io.open(로그길, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=머리, extrasaction="ignore")
        w.writeheader()
        w.writerows(담을것)

    print()
    줄("·", "%d행을 반영했습니다 (못 찾은 행 %d)" % (len(로그), 못찾음))
    줄("·", "원본 — %s" % 뒷.name)
    줄("·", "수정로그_재검토필요.csv — 모두 %d행 (%s)"
       % (len(담을것), 로그길.parent.name))
    줄("★", "PL Issue·개선우선순위를 다시 뽑으십시오 (3차_마무리 를 다시 돌리면 됩니다)")
    return 0


def main() -> int:
    print("=" * 74)
    print("  총괄 검수 — 실무자가 볼 것을 줄인다 (축1 ③)")
    print("=" * 74)
    if _반영:
        return 반영하기()

    목록 = _읽기(M / "사람이볼목록.csv")
    분리 = _읽기(M / "감독_분리제안.csv")
    if not 목록 and not 분리:
        줄("!", "사람이볼목록·감독_분리제안이 없습니다 — 통합을 먼저 돌리십시오")
        줄(" ", "   python build_master.py <번들1> <번들2>")
        return 1

    번들 = _번들찾기()
    if len(번들) < 2:
        줄("!", "2차 판독 번들 둘을 못 찾았습니다 — 자리를 짚어 주십시오")
        줄(" ", "   python 총괄검수.py <번들1> <번들2>")
        return 1
    A = {x["atomic_id"]: x for x in _읽기(번들[0] / "raw_voc.csv")}
    B = {x["atomic_id"]: x for x in _읽기(번들[1] / "raw_voc.csv")}
    이름1, 이름2 = 번들[0].name, 번들[1].name
    줄("·", "2차 번들 — %s %d행 · %s %d행" % (이름1, len(A), 이름2, len(B)))

    # ── ① 갈래 나누기 ────────────────────────────────────────────
    갈래 = collections.Counter()
    쌍 = collections.Counter()
    제외무리 = collections.Counter()
    행별 = {}
    for x in 목록:
        a = x["atomic_id"]
        r1, r2 = A.get(a), B.get(a)
        s1 = (r1 or {}).get("status") == "scope_excluded"
        s2 = (r2 or {}).get("status") == "scope_excluded"
        if s1 != s2:
            뺀 = r1 if s1 else r2
            k = "라벨 대 제외 · %s" % ((뺀 or {}).get("scope_exclusion_reason") or "?")
            제외무리[(뺀 or {}).get("scope_exclusion_reason") or "?"] += 1
            갈래["라벨 대 제외"] += 1
            행별[a] = "라벨 대 제외"
            continue
        if s1 and s2:
            갈래["둘 다 제외 (사유만 다름)"] += 1
            행별[a] = "둘 다 제외"
            continue
        t1 = ((r1 or {}).get("topic") or "").strip()
        t2 = ((r2 or {}).get("topic") or "").strip()
        쌍[tuple(sorted((t1, t2)))] += 1
        원 = re.sub(r"\s+", "", x.get("atomic_voc") or "")
        p1 = _자리(원, (r1 or {}).get("topic_evidence"))
        p2 = _자리(원, (r2 or {}).get("topic_evidence"))
        if not p1 or not p2:
            갈래["근거를 못 찾음"] += 1
            행별[a] = "근거를 못 찾음"
        elif min(p1[1], p2[1]) - max(p1[0], p2[0]) <= 0:
            갈래["★ 근거가 다른 대목 — 나눌 것"] += 1
            행별[a] = "★ 나눌 것"
        else:
            갈래["근거가 같은 대목 — 이름만 다름"] += 1
            행별[a] = "이름만 다름"

    print()
    print("  ① 사람이볼목록 %d행을 가르면" % len(목록))
    for k, n in 갈래.most_common():
        표 = "★" if k.startswith("★") else "·"
        줄(표, "%-36s %5d" % (k.lstrip("★ "), n))

    # ── ② 규칙 후보 ──────────────────────────────────────────────
    print()
    print("  ② 규칙으로 묶일 후보 — 되풀이되는 것부터")
    많은쌍 = [(t, n) for t, n in 쌍.most_common() if n >= 8]
    for (t1, t2), n in 많은쌍[:8]:
        줄("★", "%4d회   %s  ↔  %s" % (n, t1, t2))
    if not 많은쌍:
        줄("·", "8회 넘게 되풀이되는 라벨 쌍이 없습니다")
    for r, n in 제외무리.most_common(5):
        if n >= 8:
            줄("★", "%4d회   라벨 대 제외 — %s" % (n, r))

    # ── ③ 판정 자리 만들기 ───────────────────────────────────────
    낼 = M / "총괄검수_판정자리.csv"
    칸 = ["atomic_id", "갈래", "product_category", "atomic_voc", "original_voc",
          "2차_" + 이름1, "2차_" + 이름2, "3차_판단", "총괄_판정", "규칙", "근거",
          "승인상태", "로그갈래(A/B/C)"]
    if _확인만:
        print()
        print("  ── 확인만 ──────────────────────────────────────")
        print("     %s 를 만들 참이었습니다 (%d행)" % (낼.name, len(목록)))
        print("     아무것도 안 남겼습니다.")
        return 0

    # ★ 이미 채운 판정을 지킨다 (2026-08-26에 고침).
    #   마무리를 두 번 돌리면 판정 자리를 새로 만들어 채운 것이 날아갔다.
    #   실제로 360행을 채우고 반영한 뒤 다시 돌리니 통째로 비워졌다.
    _채운것 = {}
    if 낼.exists():
        for _x in _읽기(낼):
            if (_x.get("총괄_판정") or "").strip():
                _채운것[_x["atomic_id"]] = _x
    if _채운것:
        줄("·", "이미 채운 판정 %d행을 지킵니다" % len(_채운것))

    with io.open(낼, "w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=칸)
        w.writeheader()
        for x in 목록:
            a = x["atomic_id"]
            _옛 = _채운것.get(a) or {}
            w.writerow({
                "atomic_id": a,
                "갈래": 행별.get(a, ""),
                "product_category": x.get("product_category", ""),
                "atomic_voc": x.get("atomic_voc", ""),
                "original_voc": x.get("original_voc", ""),
                "2차_" + 이름1: _값(A.get(a)),
                "2차_" + 이름2: _값(B.get(a)),
                "3차_판단": " / ".join(
                    str(x.get(c) or "") for c in x if str(c).startswith("3차_")),
                "총괄_판정": _옛.get("총괄_판정", ""),
                "규칙": _옛.get("규칙", ""),
                "근거": _옛.get("근거", ""),
                "승인상태": _옛.get("승인상태", "대기"),
                "로그갈래(A/B/C)": _옛.get("로그갈래(A/B/C)", ""),
            })
    print()
    줄("·", "판정 자리를 만들었습니다 — %s (%d행)" % (낼.name, len(목록)))
    줄(" ", "   갈래·2차 판단 둘·3차 판단이 이미 채워져 있습니다.")
    줄(" ", "   총괄이 「총괄_판정 · 규칙 · 근거」 를 채우면 됩니다.")

    # ── ④ 남은 것 ────────────────────────────────────────────────
    print()
    print("  ④ 분리제안")
    for k, n in collections.Counter(
            (x.get("승인상태") or "?") for x in 분리).most_common():
        표 = "★" if "다르게" in k or "한쪽" in k else "·"
        줄(표, "%-46s %5d" % (k[:46], n))
    print()
    print("=" * 74)
    print("  ★ 기계로 밀지 마십시오. 되풀이되는 쌍이라도 문맥을 봐야 합니다.")
    print("    4차 때 §8 후보 72행 중 45행이 오탐이었습니다.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
