# -*- coding: utf-8 -*-
"""5차 동결 기준을 문서·도구가 어기고 있지 않은지 전수로 본다.

★ 왜 이 검사기가 있나 (2026-08-24)
  sky 「5차 동결기준으로 전체 프로젝트와 문서들이 다 인지하고 있는지」

  5차에서 「감독자는 판정까지만 · 차수 사이는 총괄이」 로 정했는데,
  정하고 나서 문서를 손으로 고쳤더니 **여섯 자리가 빠져 있었다.**

    61 가이드 §1   실무자가 make_judge_input 을 돌리라고 함
    61 가이드 §3   「두 감독자를 합칩니다 — build_master」
    감독자 프롬프트   97줄에서 「스스로 만들지 마라」, 109줄에서 「네가 돌린다」
    자가점검       없는 도구를 돌리라고 안내
    넘어가도_되나   「build_master.py 를 돌리십시오」
    62 · 64 · 95   같은 결

  ★ 「가드는 돌리는 자리에」 (sky) — 손으로 유지하는 목록은 반드시 빠진다.
    그래서 규칙을 코드로 적고, make_zip 이 꾸러미를 만들 때마다 돌린다.

쓰기
    python 5차기준_검사.py          # 어긴 곳을 찾는다
    python 5차기준_검사.py --조용   # 어긴 것이 있을 때만 말한다

어긴 것이 하나라도 있으면 종료코드 1.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent

# ── 보지 않을 곳 ───────────────────────────────────────────────────
#   ★ 대화 기록과 과거 제출본은 「그때 그랬다」 는 사실이다. 고치지 않는다.
#   ★ 총괄 자리 도구는 이 규칙의 **주체**다. 그것들이 build_master 를
#     부르는 것은 맞는 일이다.
안봄_폴더 = {"_작업이력", "_보관", "_되돌리기_20260821", "_배포",
             "__pycache__", "_결과", "_총괄만"}
안봄_파일 = {
    "5차기준_검사.py",              # 이 파일 자신 — 규칙 문장이 들어 있다
    "3차_준비.py", "3차_마무리.py",  # 총괄 자리 도구
    "번들_마무리꾸미기.py", "번들_색칠하기.py", "데이터안내_만들기.py",
    "make_judge_input.py", "build_master.py",  # 도구 자신
    "make_zip.py",                  # 무엇을 넣고 뺄지 적는 자리
    "박힌말_검사.py", "편향검사.py", "정본_맞추기.py",
    "92_동결운영규칙.md",           # 규칙을 적는 자리
    "93_오류발견대장.md",           # 겪은 것을 적는 자리
    "98_전체흐름_1차부터_4차까지.md",
    "52_AX_FLEX_과제_제출본.md",    # 제출본 — 그때 사실
    "90_변경원장_LEDGER.md",
}


def 볼파일들():
    for p in HERE.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".md", ".py"):
            continue
        if 안봄_폴더 & set(x for x in p.parts):
            continue
        if p.name in 안봄_파일:
            continue
        if p.name.startswith("대화_"):        # 대화 기록
            continue
        if p.name.startswith("채점지_"):
            continue
        yield p


# ── 규칙 ───────────────────────────────────────────────────────────
#   (무엇을 찾나, 왜 안 되나, 어떻게 고치나)
규칙 = (
    (
        # 「돌려라」 꼴로 나오는 것만 잡는다. 이름만 대는 것은 봐준다
        re.compile(r"^\s*(?:python|\$)\s+\S*make_judge_input\.py"),
        "감독자·실무자에게 make_judge_input 을 돌리라고 적혀 있다",
        "그 도구는 총괄 자리에만 있다. 「총괄에게 요청」 으로 바꾼다",
    ),
    (
        re.compile(r"^\s*(?:python|\$)\s+\S*build_master\.py"),
        "감독자·실무자에게 build_master 를 돌리라고 적혀 있다",
        "통합은 총괄이 3차_마무리.py 로 한다",
    ),
    (
        re.compile(r"^\s*(?:python|\$)\s+\S*apply_sky\.py"),
        "실무자에게 apply_sky 를 돌리라고 적혀 있다",
        "4차 반영은 총괄이 한다. 실무자는 채점만",
    ),
    (
        re.compile(r"(두|2)\s*감독자(을|를)?\s*(합|모)"),
        "「두 감독자를 합친다」 — 감독자가 통합하는 옛 방식이다",
        "감독자는 판정까지. 두 폴더를 그대로 총괄에게 넘긴다",
    ),
    (
        re.compile(r"ab_mapping\.json\s*(을|를)?\s*(주지|보여|열게)"),
        "ab_mapping 을 「주지 마라」 로 적혀 있다 — 이제 아예 넣지 않는다",
        "총괄이 _총괄만/ 에 둔다. 감독 폴더에 없는 것이 맞다",
    ),
)

# ★ 감독자 꾸러미에 들어가서는 안 되는 파일 (make_zip 과 짝을 맞춰 본다)
감독자꾸러미_금지 = ("make_judge_input.py", "build_master.py")

# ★ 「하지 마라」 고 적은 줄은 어긴 것이 아니다 (sky 규칙: 오탐도 사고다).
#   첫 판에 「❌ 두 감독자를 합치지 않는다」 를 위반으로 셌다 — 금지 문장인데.
#   오탐이 섞이면 아무도 이 검사기를 안 본다.
금지문장 = re.compile(
    r"❌|✗|않는다|않습니다|마십시오|마세요|마라|안 된다|안 됩니다|"
    r"하지 않|없는 것이 맞|넣지 않|여기 없다|옛 방식|예전에는"
)


def 규칙검사():
    걸린것 = []
    for p in 볼파일들():
        try:
            줄들 = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        for n, 줄 in enumerate(줄들, 1):
            if 금지문장.search(줄):        # 「하지 마라」 는 어긴 것이 아니다
                continue
            for 무늬, 왜, 어떻게 in 규칙:
                if 무늬.search(줄):
                    걸린것.append((p, n, 줄.strip()[:70], 왜, 어떻게))
    return 걸린것


def 꾸러미검사():
    """make_zip 이 감독자 꾸러미에 금지 도구를 다시 넣지 않았는지."""
    z = HERE / "make_zip.py"
    if not z.exists():
        return []
    글 = io.open(z, encoding="utf-8", errors="replace").read()
    # 3차 감독 꾸러미 조각만 떼어 본다
    m = re.search(r"'3_3차감독'\s*:\s*\{(.*?)\n    \}", 글, re.S)
    if not m:
        return []
    조각 = m.group(1)
    나쁨 = []
    for 이름 in 감독자꾸러미_금지:
        for 줄 in 조각.splitlines():
            if 이름 in 줄 and not 줄.lstrip().startswith("#"):
                나쁨.append("make_zip 의 3차 꾸러미에 %s 가 다시 들어갔다" % 이름)
    return 나쁨


def main() -> int:
    조용 = "--조용" in sys.argv
    걸린것 = 규칙검사()
    꾸러미 = 꾸러미검사()

    if not 걸린것 and not 꾸러미:
        if not 조용:
            print("5차 기준 — 어긴 곳이 없습니다")
            print("  (감독자는 판정까지 · 차수 사이는 총괄 · 익명화는 총괄이 만든다)")
        return 0

    print("★ 5차 기준을 어긴 곳이 %d군데 있습니다" % (len(걸린것) + len(꾸러미)))
    for 말 in 꾸러미:
        print("   ✗ %s" % 말)
    본것 = set()
    for p, n, 줄, 왜, 어떻게 in 걸린것:
        try:
            보일곳 = p.relative_to(HERE)
        except ValueError:
            보일곳 = p
        print()
        print("   ✗ %s:%d" % (보일곳, n))
        print("      %s" % 줄)
        if 왜 not in 본것:
            print("      왜   %s" % 왜)
            print("      고침 %s" % 어떻게)
            본것.add(왜)
    return 1


if __name__ == "__main__":
    sys.exit(main())
