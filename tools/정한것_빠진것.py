# -*- coding: utf-8 -*-
"""sky 가 정한 것 중 **글에 안 들어간 것**을 찾는다 (2026-10-29).

★ 왜 있는가 — 옛 저장소에 `점검서_빠진것.py` 가 있었다. sky 2026-08-22 —
    「당신이 전에 한거 또 하고 실수하고 뭔가 보기로했는데 안보고 넘어간다던지
      그런 위험을 없애려고 하는겁니다」

  그 도구가 적어 둔 까닭을 그대로 옮긴다 —

  > 점검서(`96`)를 손으로 쓰면 **내가 빠뜨린 것은 영영 안 들어간다.**
  > 내 기억이 잣대가 되면 안 된다 — 지문검사와 같은 이치다.
  >
  > 그래서 대화 원본에서 **sky 가 정한 것으로 보이는 말**을 뽑아,
  > 점검서에 그 내용이 있는지 대조한다. 없으면 알려 준다.
  >
  > ★ 이 도구는 판단하지 않는다. **후보만 내놓는다.**
  >   무엇을 점검서에 넣을지는 사람이 정한다. 자동으로 넣으면 쓰레기가 쌓인다.

  **그 도구가 새 저장소로 안 왔다.** 옛 관리 도구 일곱 중 다섯만 기록했고,
  고르지 않은 둘이 하필 「빠진 것을 찾는 도구」 였다
  (`docs/옛꾸러미_대장.md` · `docs/기준서개정후보.md` 후보 3).
  그래서 sky 가 2026-10-29 에 「왜 누락이 계속 생기는지 모르겠네요」 라고 물었다.

  원문은 `docs/sources/옛관리도구/점검서_빠진것.py` 에 지문과 함께 있다.

`tools/옛꾸러미_대장.py` 와 무엇이 다른가
----------------------------------------
  옛꾸러미_대장   **옛 꾸러미의 파일**이 왔나를 센다 (파일 단위)
  이 도구          **sky 가 대화에서 정한 말**이 글에 들어갔나를 본다 (말 단위)

  **다른 누락이다.** 파일이 다 와도 「sky 가 그때 정한 한 줄」 은 여전히 빠질 수 있다.

적는 자리 — 옛 저장소는 점검서 한 장이었지만 여기는 여럿이다
    docs/decisions/*.md · docs/지금_어디인가.md · docs/progress.md · CHANGELOG.md
  그 넷을 **합쳐** 대조한다 (어느 하나에 들어 있으면 적힌 것으로 본다).

★ **못 찾으면 종료코드 1** — 대화 기록이나 적는 자리를 못 찾으면 검사를 못 한 것이다.
  그것을 「빠진 것 없음」 으로 돌려주지 않는다.

★ 경로를 이 파일에 박지 않는다 — 대화 기록 자리는 `--대화자리` 로 주거나
  `VOC_대화기록` 환경변수로 가리킨다. 기본은 이 컴퓨터의 Claude Code 기록 자리다.

쓰기
    python tools/정한것_빠진것.py                 최근 대화에서 찾는다
    python tools/정한것_빠진것.py --하루          오늘 것만
    python tools/정한것_빠진것.py --개수 40       몇 개까지 볼지 (기본 25)
    python tools/정한것_빠진것.py --대화자리 <폴더>
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin" / "shared"))
from paths import REPO  # noqa: E402

# sky 가 「정하는」 말투 — 이런 말이 든 발언을 후보로 본다 (옛 도구의 무늬 그대로)
정하는말 = re.compile(
    r"하기로|하지\s*마|하지마|안\s*하기로|정하|정합니다|합시다|하시죠|"
    r"동결|규칙|기준|바꾸|고치|빼|넣|권장|필수|반드시|절대|"
    r"할래요|할게요|해주세요|해야|말고|대신")

# 이런 말만 있으면 그냥 물음이지 결정이 아니다 (옛 도구 그대로)
그냥물음 = re.compile(r"^\s*(뭐|왜|어떻게|어디|누가|언제|무슨|어느|그럼|근데)[^\.]*\?\s*$")

# 뜻 있는 낱말이 이만큼은 돼야 결정으로 본다 — 재서 정했다 (위 주석 참조)
_낱말문턱 = 8


def 적는자리() -> list[Path]:
    글 = [REPO / "CHANGELOG.md", REPO / "docs" / "지금_어디인가.md", REPO / "docs" / "progress.md"]
    글 += sorted((REPO / "docs" / "decisions").glob("*.md"))
    return [p for p in 글 if p.is_file()]


def 대화찾기(준자리: str | None) -> list[Path]:
    """이 저장소의 대화 기록만 본다 — 다른 프로젝트의 기록을 끌어오지 않는다."""
    집 = Path(준자리 or os.environ.get("VOC_대화기록") or (Path.home() / ".claude" / "projects"))
    if not 집.is_dir():
        return []
    if list(집.glob("*.jsonl")):
        return sorted(집.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    # ★ 이 저장소 이름으로 시작하는 폴더만 — 다른 일의 대화를 섞으면 후보가 쓰레기가 된다
    후보: list[Path] = []
    for d in 집.iterdir():
        if d.is_dir() and d.name.startswith("C-----youtube-voc-skills"):
            후보 += list(d.glob("*.jsonl"))
    return sorted(후보, key=lambda p: p.stat().st_mtime, reverse=True)


def 글만(내용) -> str:
    if isinstance(내용, str):
        return 내용
    if not isinstance(내용, list):
        return ""
    return "\n".join(칸.get("text") or "" for 칸 in 내용
                     if isinstance(칸, dict) and 칸.get("type") == "text")


def 낱말(글: str) -> set[str]:
    """대조용 — 두 글자 이상 한글·영문 낱말 (옛 도구 그대로)"""
    return {w for w in re.findall(r"[가-힣A-Za-z_][가-힣A-Za-z0-9_]{1,}", 글)
            if len(w) >= 2}


def main(인자: list) -> int:
    준자리 = None
    if "--대화자리" in 인자:
        i = 인자.index("--대화자리") + 1
        준자리 = 인자[i] if i < len(인자) else None
    길들 = 대화찾기(준자리)
    if not 길들:
        print("못 찾음: 이 저장소의 대화 기록이 없다 — **검사를 못 했습니다.**")
        print("  `--대화자리 <폴더>` 로 가리키거나 `VOC_대화기록` 을 정하십시오.")
        return 1
    자리들 = 적는자리()
    if len(자리들) < 3:
        print("못 찾음: 적는 자리를 %d개밖에 못 찾았다 — **검사를 못 했습니다.**" % len(자리들))
        return 1

    한도 = 25
    if "--개수" in 인자:
        i = 인자.index("--개수") + 1
        if i < len(인자) and 인자[i].isdigit():
            한도 = int(인자[i])
    자를때 = datetime.now().astimezone() - timedelta(days=1) if "--하루" in 인자 else None

    적힌낱말: set = set()
    for p in 자리들:
        적힌낱말 |= 낱말(p.read_text(encoding="utf-8", errors="replace"))

    후보 = []
    본줄 = 0
    for 길 in 길들[:6]:          # 가장 최근 대화 몇 벌만 본다
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
            if not 글 or 글.startswith(("〔", "<", "[")) or len(글) < 8:
                continue
            # ★ 사람이 쓴 말이 아닌 것은 뺀다 — 돌려 보니 다른 세션이 보낸 쪽지와
            #   하네스가 넣은 알림이 「sky 의 말」 로 올라왔다.
            if any(x in 글 for x in ("system-reminder", "task-notification",
                                     "agent-message", "Another Claude session",
                                     "ci-monitor-event", "pasted_content")):
                continue
            if 그냥물음.match(글) or not 정하는말.search(글):
                continue
            본줄 += 1
            때 = 쪽지.get("timestamp") or ""
            try:
                t = datetime.fromisoformat(때.replace("Z", "+00:00")).astimezone()
            except Exception:
                t = None
            if 자를때 and t and t < 자를때:
                continue
            말낱말 = {w for w in 낱말(글) if len(w) >= 3}      # 흔한 두 글자는 뺀다
            # ★ 낱말이 적은 짧은 지시는 뺀다. 재서 정한 문턱이다 (2026-10-29) —
            #   문턱이 없으면 「네 섹션 2 진행해주세요」 류가 **낱말이 적어 0% 담김**으로
            #   맨 위에 올라와, 위 열두 개가 전부 그런 말이었다. 쓸모가 없는 출력이다.
            #   4개·6개·8개를 다 돌려 보고 8개에서 실제 결정이 맨 위로 올라왔다
            #   (남은 것 98 → 87 → 79개). 결정은 길다 — 조건과 까닭이 같이 오기 때문이다.
            if len(말낱말) < _낱말문턱:
                continue
            담긴율 = len(말낱말 & 적힌낱말) / len(말낱말)
            후보.append((담긴율, t, " ".join(글.split())))

    # 같은 말이 여러 대화에 겹쳐 들어오면 한 번만 본다
    본것: set = set()
    고른것 = []
    for 율, t, 글 in sorted(후보, key=lambda x: x[0]):
        if 글 in 본것:
            continue
        본것.add(글)
        고른것.append((율, t, 글))

    print("=" * 72)
    print("  글에 안 들어간 것으로 보이는 sky 의 말")
    print("=" * 72)
    print("  대화 기록  : %d벌 (본 것 %d벌)" % (len(길들), min(6, len(길들))))
    print("  적는 자리  : %d개 — %s" % (len(자리들), " · ".join(p.name for p in 자리들[:4])))
    print("  정하는 말  : %d개 · 그 중 다른 말 %d개 — 담긴 정도가 낮은 순으로 %d개"
          % (본줄, len(고른것), min(한도, len(고른것))))
    print()
    print("  ★ 이 도구는 판단하지 않습니다. 무엇을 적을지는 sky 가 정합니다.")
    print()
    for 율, t, 글 in 고른것[:한도]:
        때글 = t.strftime("%m-%d %H:%M") if t else "??"
        print("  [%3.0f%% 담김] %s  %s" % (100 * 율, 때글, 글[:92]))
        if len(글) > 92:
            print("                            %s" % 글[92:200])
    print()
    print("=" * 72)
    print("  담긴 정도가 낮다고 반드시 빠뜨린 것은 아닙니다 —")
    print("  이미 끝난 일이거나 그때뿐인 말일 수 있습니다. 눈으로 고르십시오.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
