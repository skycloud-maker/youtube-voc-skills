# -*- coding: utf-8 -*-
"""sky 가 정한 것 중 점검서에 안 들어간 것을 찾는다.

★ 왜 있는가 (sky 2026-08-22)
  「당신이 전에 한거 또 하고 실수하고 뭔가 보기로했는데 안보고 넘어간다던지
    그런 위험을 없애려고 하는겁니다」

  점검서(`96`)를 손으로 쓰면 **내가 빠뜨린 것은 영영 안 들어간다.**
  내 기억이 잣대가 되면 안 된다 — 지문검사와 같은 이치다.

  그래서 대화 원본에서 **sky 가 정한 것으로 보이는 말**을 뽑아,
  점검서에 그 내용이 있는지 대조한다. 없으면 알려 준다.

★ 이 도구는 판단하지 않는다. **후보만 내놓는다.**
  무엇을 점검서에 넣을지는 사람이 정한다. 자동으로 넣으면 쓰레기가 쌓인다.

쓰기
    python 점검서_빠진것.py              최근 대화에서 찾는다
    python 점검서_빠진것.py --하루        오늘 것만
    python 점검서_빠진것.py --개수 40     몇 개까지 볼지 (기본 25)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent if _HERE.name in ("스크립트", "scripts") else _HERE
점검서 = ROOT / "96_작업전_점검서.md"

# sky 가 「정하는」 말투 — 이런 말이 든 발언을 후보로 본다
정하는말 = re.compile(
    r"하기로|하지\s*마|하지마|안\s*하기로|정하|정합니다|합시다|하시죠|"
    r"동결|규칙|기준|바꾸|고치|빼|넣|권장|필수|반드시|절대|"
    r"할래요|할게요|해주세요|해야|말고|대신")

# 이런 말만 있으면 그냥 물음이지 결정이 아니다
그냥물음 = re.compile(r"^\s*(뭐|왜|어떻게|어디|누가|언제|무슨|어느|그럼|근데)[^\.]*\?\s*$")


def 대화찾기() -> Path | None:
    집 = Path.home() / ".claude" / "projects"
    후보 = sorted(집.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return 후보[0] if 후보 else None


def 글만(내용) -> str:
    if isinstance(내용, str):
        return 내용
    if not isinstance(내용, list):
        return ""
    return "\n".join(칸.get("text") or "" for 칸 in 내용
                     if isinstance(칸, dict) and 칸.get("type") == "text")


def 낱말(글: str) -> set[str]:
    """대조용 — 두 글자 이상 한글·영문 낱말"""
    return {w for w in re.findall(r"[가-힣A-Za-z_][가-힣A-Za-z0-9_]{1,}", 글)
            if len(w) >= 2}


def main() -> int:
    길 = 대화찾기()
    if not 길:
        print("대화 기록을 못 찾았습니다.")
        return 1
    if not 점검서.exists():
        print("점검서가 없습니다: %s" % 점검서)
        return 1

    한도 = 25
    if "--개수" in sys.argv:
        자리 = sys.argv.index("--개수") + 1
        if 자리 < len(sys.argv) and sys.argv[자리].isdigit():
            한도 = int(sys.argv[자리])
    자를때 = datetime.now().astimezone() - timedelta(days=1) if "--하루" in sys.argv else None

    점검글 = 점검서.read_text(encoding="utf-8")
    점검낱말 = 낱말(점검글)

    후보 = []
    for 줄 in 길.read_text(encoding="utf-8", errors="replace").splitlines():
        줄 = 줄.strip()
        if not 줄.startswith("{"):
            continue
        try:
            쪽지 = json.loads(줄)
        except Exception:
            continue
        메시지 = 쪽지.get("message")
        if not isinstance(메시지, dict) or 메시지.get("role") != "user":
            continue
        글 = 글만(메시지.get("content")).strip()
        if not 글 or 글.startswith("〔") or len(글) < 8:
            continue
        if 그냥물음.match(글):
            continue
        if not 정하는말.search(글):
            continue

        때 = 쪽지.get("timestamp") or ""
        try:
            t = datetime.fromisoformat(때.replace("Z", "+00:00")).astimezone()
        except Exception:
            t = None
        if 자를때 and t and t < 자를때:
            continue

        # 점검서에 이 발언의 알맹이가 얼마나 담겼나
        말낱말 = 낱말(글)
        말낱말 = {w for w in 말낱말 if len(w) >= 3}      # 흔한 두 글자는 뺀다
        if not 말낱말:
            continue
        담긴율 = len(말낱말 & 점검낱말) / len(말낱말)
        후보.append((담긴율, t, 글))

    후보.sort(key=lambda x: x[0])

    print("=" * 72)
    print("  점검서에 안 들어간 것으로 보이는 sky 의 말")
    print("=" * 72)
    print("  대화 원본 : %s" % 길.name[:20])
    print("  점검서    : %s (%.1f KB)" % (점검서.name, 점검서.stat().st_size / 1024))
    print("  찾은 후보 : %d개 — 담긴 정도가 낮은 순으로 %d개만 봅니다"
          % (len(후보), min(한도, len(후보))))
    print()
    print("  ★ 이 도구는 판단하지 않습니다. 무엇을 넣을지는 사람이 정합니다.")
    print()

    for 율, t, 글 in 후보[:한도]:
        때글 = t.strftime("%m-%d %H:%M") if t else "??"
        한줄 = " ".join(글.split())
        print("  [%3.0f%% 담김] %s  %s" % (100 * 율, 때글, 한줄[:96]))
        if len(한줄) > 96:
            print("                            %s" % 한줄[96:200])
    print()
    print("=" * 72)
    print("  담긴 정도가 낮다고 반드시 빠뜨린 것은 아닙니다 —")
    print("  이미 끝난 일이거나 그때뿐인 말일 수 있습니다. 눈으로 고르십시오.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
