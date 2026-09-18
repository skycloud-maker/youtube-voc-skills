# -*- coding: utf-8 -*-
"""판정 데이터의 원문이 **1차 원본과 글자까지 같은가**.

★ 왜 있는가 (2026-08-26)
  5차 동결에서 용어를 일괄로 밀었다 — 「담당자」→「총괄」.
  그 치환이 `raw_voc.csv` 의 **실제 댓글 본문**까지 덮었다.

    1판   오늘 LG 로니 사전 답사 「총괄」분이 다녀가셨고 …
    원본  오늘 LG 로니 사전 답사 「담당자」분이 다녀가셨고 …

  1판 raw_voc 에 「담당자」 는 **0행**이었다. 하나도 안 남기고 다 바뀌었다.
  그 훼손본이 GitHub 릴리스에 올라가 있었다.

★ 왜 `check_lineage.py` 로는 못 잡나 — **판 안에서만 보기 때문이다.**
  계보 검사는 「atomic 이 그 판의 original_voc 안에 있나」 를 본다.
  원문과 조각이 **같이** 치환되면 둘이 서로 맞으므로 그냥 통과한다.
  ★ 그래서 **판 밖**, 1차 원본까지 거슬러 견주는 검사가 따로 있어야 한다.

★ 어떻게 보나 — 단어를 짐작하지 않는다
  「총괄이 들었나」 같은 식으로 찾지 않는다. 그러면 **다음에 다른 단어를
  밀었을 때 또 못 잡는다.** 1차 원본과 통째로 견주고 다른 것을 전부 뽑는다.

★ @닉네임 제거는 결함이 아니다
  `voc_cleaned` 는 정제 단계에서 「@아무개 」 를 뗀다. 그것은 원래 하는 일이다.
  그래서 **`original_voc` 를 본다** — 이 칸은 손대지 않기로 한 칸이다
  (1차 계약 V-0-3 / L-1 — 원문은 한 글자도 바꾸지 않는다).

쓰기
    python 원문대조검사.py                  가장 나중 판을 본다
    python 원문대조검사.py _2판              그 판을 본다
    python 원문대조검사.py --전부            있는 판을 다 본다

다른 것이 하나라도 있으면 종료코드 1.
"""
from __future__ import annotations

import csv
import difflib
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


def 줄(표: str, 말: str) -> None:
    print("  %s %s" % (표, 말))


def 원본읽기() -> tuple[dict, list]:
    """1차 산출물에서 source_id → original_voc 를 모은다."""
    원본: dict[str, set] = {}
    쓴것 = []
    for p in sorted(ROOT.rglob("voc_secondary_dataset.csv")):
        try:
            with io.open(p, encoding="utf-8-sig", newline="") as h:
                rd = csv.DictReader(h)
                머리 = rd.fieldnames or []
                if "original_voc" not in 머리 or "source_id" not in 머리:
                    continue
                n = 0
                for r in rd:
                    sid = (r.get("source_id") or "").strip()
                    t = (r.get("original_voc") or "").strip()
                    if sid and t:
                        원본.setdefault(sid, set()).add(t)
                        n += 1
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
        if n:
            쓴것.append((p, n))
    return 원본, 쓴것


def 판찾기(고른것: str | None) -> list[Path]:
    """볼 판을 고른다 — 판마다 master_final/raw_voc.csv 가 있어야 한다."""
    자리 = []
    if 고른것:
        p = ROOT / 고른것 if not Path(고른것).is_absolute() else Path(고른것)
        자리.append(p)
    else:
        후보 = [ROOT]
        후보 += [d for d in ROOT.iterdir()
                if d.is_dir() and re.fullmatch(r"_\d+판", d.name)]
        자리 = 후보
    끝 = []
    for d in 자리:
        r = d / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv"
        if r.is_file():
            끝.append(d)
    return 끝


def 견주기(자리: Path, 원본: dict) -> list:
    r = 자리 / "_판독패키지" / "_결과" / "master_final" / "raw_voc.csv"
    with io.open(r, encoding="utf-8-sig", newline="") as h:
        rows = list(csv.DictReader(h))

    본것 = 없음 = 0
    다름: dict = {}
    for x in rows:
        sid = (x.get("source_id") or "").strip()
        t = (x.get("original_voc") or "").strip()
        if not sid or not t:
            continue
        후보 = 원본.get(sid)
        if 후보 is None:
            없음 += 1
            continue
        본것 += 1
        if t not in 후보:
            다름[(sid, t)] = sorted(후보)[0]

    이름 = 자리.name if 자리 != ROOT else "(뿌리 · 1판)"
    print()
    print("  ── %s ─────────────────────────────────" % 이름)
    줄("·", "대조한 행 %d · 원본에 없는 source_id %d" % (본것, 없음))
    if not 다름:
        줄("·", "원문이 1차 원본과 **글자까지 같습니다**")
        return []

    바뀐: dict = {}
    for (sid, 지금), 원 in 다름.items():
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, 원, 지금).get_opcodes():
            if op == "equal":
                continue
            키 = (원[i1:i2], 지금[j1:j2])
            바뀐[키] = 바뀐.get(키, 0) + 1

    줄("✗", "★ 원문이 바뀐 댓글 %d개" % len(다름))
    print("        바뀐 글자")
    for (전, 후), n in sorted(바뀐.items(), key=lambda z: -z[1])[:12]:
        print("          「%s」 → 「%s」   %d곳"
              % (전[:34] or "(없음)", 후[:34] or "(지워짐)", n))
    print("        보기")
    for (sid, 지금), 원 in sorted(다름.items())[:3]:
        print("          %s" % sid[:56])
        print("            원본  %s" % 원[:70].replace("\n", "⏎"))
        print("            지금  %s" % 지금[:70].replace("\n", "⏎"))
    return list(다름)


def main() -> int:
    인자 = [a for a in sys.argv[1:] if not a.startswith("--")]
    전부 = "--전부" in sys.argv

    print("=" * 70)
    print("  원문 대조 — 1차 원본과 글자까지 같은가")
    print("=" * 70)

    원본, 쓴것 = 원본읽기()
    if not 원본:
        줄("!", "1차 원본(voc_secondary_dataset.csv)을 못 찾았습니다")
        줄("", "  이 검사는 1차 산출물이 있어야 돌아갑니다. 건너뜁니다.")
        return 0
    줄("·", "1차 원본 %d개 파일 · 댓글 %d개" % (len(쓴것), len(원본)))

    자리들 = 판찾기(인자[0] if 인자 else None)
    if not 자리들:
        줄("!", "볼 판을 못 찾았습니다 (master_final/raw_voc.csv 가 없습니다)")
        return 0
    if not 전부 and not 인자:
        자리들 = [자리들[-1]]      # 가장 나중 판만

    탈 = 0
    for d in 자리들:
        탈 += len(견주기(d, 원본))

    print()
    print("=" * 70)
    if 탈:
        print("  ★ 원문이 바뀐 댓글이 %d개 있습니다." % 탈)
        print("    1차 계약 V-0-3 / L-1 — 원문은 한 글자도 바꾸지 않는다.")
        print("    용어를 일괄로 밀 때 데이터 파일이 딸려 들어갔는지 보십시오.")
    else:
        print("  · 원문이 1차 원본과 같습니다")
    print("=" * 70)
    return 1 if 탈 else 0


if __name__ == "__main__":
    sys.exit(main())
