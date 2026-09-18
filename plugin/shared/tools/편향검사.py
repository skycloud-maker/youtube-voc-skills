# -*- coding: utf-8 -*-
"""감독자가 **자기 편을 들었는지** 잰다.

★ 왜 (sky 2026-08-23)
  「각자 직접 만들어서 해도 되는 것인지? 편향 없이 진행이 되는 것인지?」

  ★ 익명화(A·B)는 완전한 방어가 아니다.
    감독자가 스스로 3차_준비 를 돌리면 매핑을 **만드는 주체**가 되고,
    만드는 코드도 폴더 안에 있다. 마음먹으면 알 수 있다 — 막을 수 없다.

  ★★ 막을 수 없으면 **잰다.**
    매핑을 아는 자리(총괄)에서 「감독자가 누구 것을 얼마나 골랐나」 를 센다.
    2차에서 자기가 판독한 쪽을 유독 많이 골랐으면 그것이 신호다.

  ★ 다만 **반려하지 않는다.** 자기 판독이 실제로 더 나았을 수도 있다.
    숫자만 정확히 내밀고 사람이 판단한다 (오탐도 사고다).

쓰기
    python 스크립트/편향검사.py
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기
R = ROOT / "_판독패키지" / "_결과"

# 이만큼 치우치면 눈여겨본다 — 반반(50%)에서 얼마나 벗어났나
눈여겨 = 0.10


def _번들주인(번들경로: str) -> str:
    """그 번들을 만든 판독자 이름 — **파일에서 읽는다.**

    ★ 폴더 이름으로 재면 안 된다 (2026-08-25).
      `final_v62` · `cc_final` 처럼 이름에 판독자가 안 들어간 폴더에서는
      전부 「남」 으로 세어 **조용히 0%** 를 낸다. 에러도 안 난다.
    """
    자리 = ROOT / str(번들경로).replace("/", os.sep)
    셈: dict = {}
    for 위 in (자리, 자리.parent, 자리.parent.parent):
        if not 위.is_dir():
            continue
        for q in 위.glob("판독결과_full_*_*.md"):
            m = re.match(r"판독결과_full_[^_]+_(.+)$", q.stem)
            if m:
                셈[m.group(1)] = 셈.get(m.group(1), 0) + 1
        if 셈:
            break
    if 셈:
        return max(셈.items(), key=lambda x: x[1])[0]
    # 못 읽으면 폴더 이름으로 되돌린다 (옛 방식)
    return os.path.basename(str(번들경로).rstrip("/\\"))


def 샜을만한자리(이름: str) -> list:
    """익명화가 샐 수 있었던 자리를 총괄 대신 본다.

    ★ sky 2026-08-25 — 「실무자가 바로 판독하기 어려우니 총괄이 확인하고 안내」
      「폴더를 열어 보십시오」 는 실무자에게 시킬 일이 아니다. 재서 알려 준다.
    """
    걸린것 = []
    # 그 감독자의 폴더를 찾는다 — 판정 파일이 있는 자리
    자리들 = set()
    for p in R.glob("감독결과_*_%s.md" % 이름):
        자리들.add(p.parent.parent.parent)
    for 자리 in 자리들:
        if not 자리.is_dir():
            continue
        번들 = [d for d in (자리 / "_판독패키지" / "_결과").glob("*")
                if d.is_dir() and (d / "raw_voc.csv").exists()]
        if 번들:
            걸린것.append("2차 번들이 폴더에 있습니다 (%d개) — %s"
                          % (len(번들), ", ".join(d.name for d in 번들[:3])))
        for 무늬, 말 in (("**/ab_mapping.json", "정답지(ab_mapping)가 폴더에 있습니다"),
                        ("**/make_judge_input.py",
                         "매핑을 만드는 코드가 폴더에 있습니다 — 돌리면 재현됩니다")):
            if list(자리.glob(무늬)):
                걸린것.append(말)
    return 걸린것


def 데이터지문() -> tuple:
    """지금 데이터가 무엇인지 — 행수와 지문.

    ★ 편향 결과가 **어느 데이터를 잰 것인지** 를 못박는다 (2026-08-25).
      화면이 이것으로 맞춰 보고, 안 맞으면 아예 안 보여 준다.
      「다르면 다른 판 성적입니다」 라고 사람에게 떠넘기지 않는다.
    """
    import csv as _csv
    import hashlib

    p = ROOT / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv"
    if not p.exists():
        return 0, ""
    try:
        with io.open(p, encoding="utf-8-sig", newline="") as h:
            ids = [r.get("atomic_id", "") for r in _csv.DictReader(h)]
    except OSError:
        return 0, ""
    지문 = hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()[:16]
    return len(ids), 지문


def _매핑() -> dict:
    for c in (ROOT / "_총괄만" / "ab_mapping.json",
              ROOT / "s13_judge" / "ab_mapping.json"):
        if c.exists():
            with io.open(c, encoding="utf-8") as h:
                return json.load(h)
    return {}


def main() -> int:
    MAP = _매핑()
    if not MAP:
        print("  정답지(ab_mapping.json)가 없어 편향을 잴 수 없습니다.")
        print("    총괄 자리에서만 잽니다 — 감독자 자리에서는 재지 않습니다.")
        return 0

    이름들 = {}
    for p in R.glob("감독결과_*.md"):
        m = re.match(r"감독결과_[^_]+_(.+)$", p.stem)
        if m:
            이름들.setdefault(m.group(1), []).append(p)
    if len(이름들) < 2:
        print("  감독자가 둘이어야 잽니다.")
        return 0

    print("=" * 70)
    print("  감독자가 자기 편을 들었는가")
    print("=" * 70)
    print("  ★ 익명화는 완전한 방어가 아닙니다. 막는 대신 잽니다.")
    print("    반반에서 %d%%p 넘게 치우치면 눈여겨봅니다." % int(눈여겨 * 100))
    print()

    말할것 = []
    표로남길것 = []
    셀것 = []

    # ★ 두 번들의 주인이 같게 읽히면 **가릴 수 없다** (2026-08-25).
    #   그때 숫자를 내면 100%/0% 같은 그럴듯한 거짓이 나온다.
    _주인들 = {_번들주인(v) for d in MAP.values() for v in d.values()}
    if len(_주인들) < 2:
        print("  ★ 누가 누구인지 가릴 수 없습니다 — 편향을 재지 않습니다.")
        print("     매핑이 가리키는 두 번들이 같은 주인으로 읽힙니다: %s"
              % (", ".join(sorted(_주인들)) or "(못 읽음)"))
        print()
        print("     왜 — 판독자 둘의 결과가 **한 자리에 섞여** 있으면")
        print("          어느 번들이 누구 것인지 가릴 수 없습니다.")
        print("          판독자마다 폴더가 따로 있어야 잽니다.")
        print()
        print("  ── 잴 수 있었다면 이 자로 봅니다 ──────────────────")
        print("     40 ~ 60%   치우침 없음        그대로 씁니다")
        print("     60 ~ 70%   ! 눈여겨봄          그대로 써도 됩니다")
        print("     70% 넘음    ★ 사람이 판단      익명화가 샜을 수 있습니다")
        print("     둘 다 70%  ★★ 다시 돌리기 권장")
        print("=" * 70)
        낼곳 = ROOT / "_인계" / "편향검사.md"
        낼곳.parent.mkdir(parents=True, exist_ok=True)
        io.open(낼곳, "w", encoding="utf-8", newline="").write(
            "# 편향검사 — 잴 수 없었습니다\n\n"
            "매핑이 가리키는 두 번들이 **같은 주인**으로 읽힙니다 (%s).\n\n"
            "판독자 둘의 결과가 한 자리에 섞여 있으면 어느 번들이 누구 것인지\n"
            "가릴 수 없습니다. 판독자마다 폴더가 따로 있어야 잽니다.\n\n"
            "★ 이럴 때 숫자를 내면 100%%/0%% 같은 **그럴듯한 거짓**이 나옵니다.\n"
            "  그래서 재지 않고 이 글을 남깁니다.\n\n"
            "## 잴 수 있었다면 이 자로 봅니다\n\n"
            "```\n"
            "40 ~ 60%%   치우침 없음        그대로 씁니다\n"
            "60 ~ 70%%   ! 눈여겨봄          그대로 써도 됩니다\n"
            "70%% 넘음    ★ 사람이 판단      익명화가 샜을 수 있습니다\n"
            "둘 다 70%%  ★★ 다시 돌리기 권장  감독의 뜻이 없어집니다\n"
            "```\n\n"
            "★ 반반(50%%)이 기준입니다. 감독은 두 답 중 하나를 고르므로\n"
            "  치우침이 없으면 자기 답과 남의 답이 반반쯤 나옵니다.\n"
            % (", ".join(sorted(_주인들)) or "못 읽음"))
        print("  → %s" % 낼곳)
        # ★ 못 쟀다는 것도 알려야 할 사실이다 (2026-08-25).
        #   csv 를 안 내면 화면에 옛 수치가 그대로 남는다.
        import csv as _csv
        from datetime import datetime as _dt
        표 = ROOT / "_판독패키지" / "_결과" / "master_final" / "편향검사.csv"
        표.parent.mkdir(parents=True, exist_ok=True)
        with io.open(표, "w", encoding="utf-8-sig", newline="") as h:
            w = _csv.writer(h)
            _행수, _지문 = 데이터지문()
            w.writerow(["잰_날짜", _dt.now().strftime("%Y-%m-%d %H:%M")])
            w.writerow(["잰_대상_행수", str(len(MAP))])
            w.writerow(["잰_데이터_행수", str(_행수)])
            w.writerow(["잰_데이터_지문", _지문])
            w.writerow([])
            w.writerow(["감독자", "자기 답을 고른 수", "자기 비율",
                        "남의 답을 고른 수", "제3의 답(C)", "판정"])
            w.writerow(["(못 쟀습니다)", "", "", "", "",
                        "두 번들이 같은 주인으로 읽힙니다 — 가릴 수 없습니다"])
        print("  → %s" % 표)
        return 0
    for 이름, 파일 in sorted(이름들.items()):
        셈 = {"자기": 0, "남": 0, "C": 0, "몰라": 0}
        for p in sorted(파일):
            for 줄 in p.read_text(encoding="utf-8", errors="replace").splitlines():
                줄 = 줄.strip()
                if not (줄.startswith("{") and '"verdict"' in 줄):
                    continue
                try:
                    j = json.loads(줄)
                except Exception:                            # noqa: BLE001
                    continue
                v = j.get("verdict")
                if v == "C":
                    셈["C"] += 1
                    continue
                m = MAP.get(j.get("atomic_id") or "")
                누구 = m.get(v) if isinstance(m, dict) else None
                if not 누구:
                    셈["몰라"] += 1
                    continue
                # ★ 경로 전체를 보면 안 된다 — 폴더 이름에 판독자 이름이
                #   들어 있어 전부 「자기」 로 세었다 (2026-08-23).
                주인 = _번들주인(누구)
                # ★ 이름이 서로를 담고 있으면 같은 사람으로 본다
                #   (claudecode ↔ claudecode_tool)
                같음 = (이름.lower() in 주인.lower()
                        or 주인.lower() in 이름.lower())
                셈["자기" if 같음 else "남"] += 1

        전 = 셈["자기"] + 셈["남"]
        if not 전:
            print("  %-14s 잴 수 있는 행이 없습니다" % 이름)
            continue
        비율 = 셈["자기"] / 전
        표 = "  " if abs(비율 - 0.5) <= 눈여겨 else "! "
        _줄 = ("  %s%-12s 자기 %5d (%.1f%%) · 남 %5d (%.1f%%) · C %d"
               % (표, 이름, 셈["자기"], 100 * 비율,
                  셈["남"], 100 * (1 - 비율), 셈["C"]))
        print(_줄)
        표로남길것.append(_줄)
        _판정 = ("치우침 없음" if abs(비율 - 0.5) <= 눈여겨
                 else ("★ 사람이 판단하십시오" if 비율 > 0.70 or 비율 < 0.30
                       else "! 눈여겨보십시오"))
        셀것.append([이름, 셈["자기"], "%.1f%%" % (100 * 비율),
                    셈["남"], 셈["C"], _판정])
        if 표 == "! ":
            말할것.append("%s — 자기 것을 %.1f%% 골랐습니다" % (이름, 100 * 비율))

    print()
    print("  ── 어느 범위면 괜찮은가 ─────────────────────────────")
    print("     40 ~ 60%   치우침 없음        그대로 씁니다")
    print("     60 ~ 70%   ! 눈여겨봄          그대로 써도 됩니다")
    print("                                  갈린 행 몇 개만 열어 보십시오")
    print("     70% 넘음    ★ 사람이 판단      익명화가 샜을 수 있습니다")
    print("     둘 다 70%%  ★★ 다시 돌리기 권장  감독의 뜻이 없어집니다")
    print("     ────────────────────────────────────────────────")
    print("     ★ 반반(50%)이 기준입니다. 감독은 두 답 중 하나를 고르므로")
    print("       치우침이 없으면 자기 답과 남의 답이 반반쯤 나옵니다.")
    print()
    print("=" * 70)
    if 말할것:
        print("  ! 눈여겨볼 것이 있습니다 (막지는 않습니다)")
        for x in 말할것:
            print("     · %s" % x)
        print()
        print("    자기 판독이 실제로 더 나았을 수도 있습니다.")
        print("    갈린 행을 몇 개 열어 보고 사람이 판단하십시오.")
    else:
        print("  치우침이 없습니다.")
    print("=" * 70)

    # ★ 파일로 남긴다 (sky 2026-08-25)
    #   「편향이 보였을 때 그걸 우리는 어디서 볼 수 있는 것인지?」
    #   3차_마무리가 도구 열한 개를 연달아 돌린다. 화면 출력은 스크롤로
    #   지나가고, 실무자는 _최종결과 폴더만 받으니 아예 못 본다.
    글 = ["# 편향검사 — 감독자가 자기 편을 들었는가", ""]
    글.append("> 익명화(A·B)는 완전한 방어가 아닙니다. 막을 수 없으면 **잽니다.**")
    글.append("> 매핑을 아는 자리(총괄)에서 「감독자가 누구 것을 얼마나 골랐나」 를 셉니다.")
    글.append("")
    글.append("```")
    for 줄 in 표로남길것:
        글.append(줄)
    글.append("```")
    글.append("")
    글.append("## 어떻게 읽나")
    글.append("")
    글.append("```")
    글.append("40~60%   치우침 없음 — 그대로 씁니다")
    글.append("          자기 답과 남의 답을 반반쯤 골랐다는 뜻입니다")
    글.append("")
    글.append("60~70%   ! 눈여겨봅니다 — **그대로 써도 됩니다**")
    글.append("          다만 갈린 행 몇 개를 열어 보십시오.")
    글.append("          자기 판독이 실제로 더 나았을 수도 있습니다")
    글.append("")
    글.append("70% 넘음  ★ 사람이 판단해야 합니다")
    글.append("          한쪽이 늘 자기 답을 골랐다면 익명화가 샜을 수 있습니다.")
    글.append("          그 감독자의 폴더에 2차 번들이나 ab_mapping 이")
    글.append("          들어가 있지 않은지 보십시오")
    글.append("")
    글.append("둘 다 70% 넘음  ★★ 3차를 다시 돌리는 것을 권합니다")
    글.append("          둘 다 자기 편을 들었으면 감독의 뜻이 없습니다")
    글.append("```")
    글.append("")
    글.append("★ **이 검사는 판정을 되돌리지 않습니다.** 숫자만 냅니다.")
    글.append("  총괄이 편향을 보정해서 번들을 만들지 **않습니다** —")
    글.append("  그러면 그것 자체가 또 하나의 편향입니다.")
    글.append("  사람이 보고 정합니다.")
    낼곳 = ROOT / "_인계" / "편향검사.md"
    낼곳.parent.mkdir(parents=True, exist_ok=True)
    io.open(낼곳, "w", encoding="utf-8", newline="").write("\n".join(글) + "\n")
    print("  → %s" % 낼곳)

    # ★ 번들 시트로 붙일 수 있게 csv 로도 낸다 (sky 2026-08-25)
    #   「이게 믿을만한 데이터다라는 걸 보여줄 수 있는 가시적임」
    #   md 는 총괄만 본다. 실무자는 xlsx 를 본다.
    import csv as _csv
    표 = ROOT / "_판독패키지" / "_결과" / "master_final" / "편향검사.csv"
    표.parent.mkdir(parents=True, exist_ok=True)
    with io.open(표, "w", encoding="utf-8-sig", newline="") as h:
        w = _csv.writer(h)
        # ★ 어느 데이터를 잰 것인지 함께 적는다 (2026-08-25).
        #   안 적으면 다른 판 데이터를 올려도 옛 수치가 그대로 뜬다.
        from datetime import datetime as _dt
        _행수, _지문 = 데이터지문()
        w.writerow(["잰_날짜", _dt.now().strftime("%Y-%m-%d %H:%M")])
        w.writerow(["잰_대상_행수", str(len(MAP))])
        w.writerow(["잰_데이터_행수", str(_행수)])
        w.writerow(["잰_데이터_지문", _지문])
        w.writerow([])
        w.writerow(["감독자", "자기 답을 고른 수", "자기 비율",
                    "남의 답을 고른 수", "제3의 답(C)", "판정"])
        for 행 in 셀것:
            w.writerow(행)
        w.writerow([])
        w.writerow(["★ 읽는 법", "40~60% 치우침 없음 · 60~70% 눈여겨 · "
                    "70% 넘으면 사람이 판단 · 둘 다 70% 넘으면 3차를 다시"])
        w.writerow(["★ 이 검사는", "판정을 되돌리지 않습니다. "
                    "총괄이 편향을 보정하지도 않습니다 — 그 자체가 또 편향입니다"])
    print("  → %s" % 표)

    # ★ 70%% 를 넘으면 다시 돌리는 길을 알려 준다 (안내만 — 사람이 정한다)
    넘음 = [x for x in 셀것 if x[5].startswith("★")]
    if 넘음:
        print()
        print("  ★ 70%%를 넘은 감독자가 있습니다 — 자로 보면 이렇습니다")
        print("       40~60%% 괜찮음 · 60~70%% 눈여겨 · 70%% 넘으면 사람이 판단")
        print("       ★ 둘 다 70%%를 넘었다면 다시 돌리시는 것을 권합니다")
        print()
        # ★ 총괄이 확인해야 할 것을 도구가 대신 본다 (sky 2026-08-25)
        print("     ── 익명화가 샜을 만한 자리를 대신 봤습니다 ──")
        본것 = False
        for 행 in 셀것:
            if not str(행[5]).startswith("★"):
                continue
            걸림 = 샜을만한자리(행[0])
            본것 = True
            if 걸림:
                print("     ✗ %s — 샐 수 있었습니다" % 행[0])
                for x in 걸림:
                    print("          · %s" % x)
                print("          ★ 이 경우 다시 돌리시는 것을 권합니다.")
            else:
                print("     · %s — 폴더에 2차 번들·정답지·만드는 코드가"
                      " **없습니다**" % 행[0])
                print("          샐 자리가 없었으므로, 자기 판독이 실제로")
                print("          더 나았을 수 있습니다. 갈린 행 몇 개를 보십시오.")
        if not 본것:
            print("     (넘은 감독자가 없습니다)")
        print()
        print("     다시 돌리시려면:")
        print("       python 3차_준비.py --다시돌리기")
        print("     앞 판은 _되돌린것/ 으로 옮겨 두고 견줄 수 있습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
