# -*- coding: utf-8 -*-
"""얼린 시험 그릇들이 **어떤 자리에서** 돌았나 한눈에 본다 (2026-10-27).

★ 왜 (sky 2026-10-27) — 「순수하게 skill 만으로 돌아가는지 모르지 않나요?」
  옛 그릇의 채점표는 **동결**이라 다시 쓰지 않는다. 대신 기록을 **읽어서** 말한다.
  앞으로 돌리는 시험은 채점기가 직접 본다 (`스킬시험_돌리기.공통채점`).

★ 읽기만 한다 — 그릇을 고치지 않는다.

★ 한 줄 흐름이 띄운 판독자·감독자도 같은 눈으로 본다 (`--판`) — 시험만 깨끗하고
  실제 흐름이 더러우면 재 본 뜻이 없다. 기록 꼴이 같아서 같은 함수로 본다 (공통 규칙 6).

쓰기
    python tools/시험환경_보기.py            한 줄 요약 + 더러운 그릇 목록
    python tools/시험환경_보기.py --전부      그릇마다 한 줄
    python tools/시험환경_보기.py --판 <판자리>   한 줄 흐름이 띄운 자리들
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
_뿌리 = _여기.parent
sys.path.insert(0, str(_뿌리 / "tests" / "evals"))
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
import 스킬시험_돌리기 as 공용  # noqa: E402
from paths import BASELINE  # noqa: E402


내전역스킬 = ("building-agents", "building-skills", "closing-a-section",
          "researching-before-building", "scoping-a-change")


def 판보기(판: Path) -> int:
    """한 줄 흐름이 띄운 자리들 — 무엇이 보였나 · 밖의 것을 썼나. **읽기만** 한다."""
    기록 = 판 / "기록"
    if not 기록.is_dir():
        print("  ✗ 기록 자리가 없습니다 — %s (못 찾음은 통과가 아니다)" % 기록)
        return 1
    파일들 = sorted(기록.glob("*.jsonl"))
    if not 파일들:
        print("  ✗ 기록 파일이 없습니다 — %s" % 기록)
        return 1
    상태 = 판 / "상태.json"
    끝난 = []
    if 상태.is_file():
        끝난 = (json.loads(상태.read_text(encoding="utf-8")) or {}).get("끝난단계") or []
    print("=" * 78)
    print("  한 줄 흐름 — %s" % 판)
    print("  끝난 단계 — %s" % (" · ".join(끝난) or "없음"))
    print("=" * 78)
    흠 = []
    for 길 in 파일들:
        본것 = 공용.본것_기록에서(길)
        쓴것 = 공용.쓴것_기록에서(길)
        쪽 = "claude" if 본것["확인됨"] else "codex(또는 init 없음)"
        섞인것 = [s for s in 본것["남의스킬"] if any(x in s for x in 내전역스킬)]
        밖 = []
        for 어디, 이름, 입 in 쓴것:
            if 어디 == "codex":
                if 이름 and 이름 not in 공용._코덱스쓰는것:
                    밖.append("codex 낯선 것 %s" % 이름)
            elif 이름.startswith("mcp__") or 이름 in ("Task", "WebFetch", "WebSearch", "Artifact"):
                밖.append(이름)
            elif 이름 == "Skill" and not str((입 or {}).get("skill") or "").startswith(공용.우리스킬머리):
                밖.append("남의 스킬 %s" % (입 or {}).get("skill"))
        나쁨 = bool(본것["훅돌았나"] or 본것["MCP"] or 섞인것 or 밖)
        print("\n  [%s] %s  (%s · 쓴 것 %d개)" % ("✗" if 나쁨 else "○", 길.stem, 쪽, len(쓴것)))
        if 본것["확인됨"]:
            print("      보인 스킬 %d (우리 %d · 남의 %d) · 모델 %s"
                  % (본것["스킬수"], len(본것["우리스킬"]), len(본것["남의스킬"]), 본것["모델"]))
            print("      훅 %s · MCP %s · 내 전역 스킬 %s"
                  % ("돌았다" if 본것["훅돌았나"] else "없음",
                     ", ".join(본것["MCP"]) or "없음", ", ".join(섞인것) or "안 보였다"))
        else:
            print("      init 사건이 없다 — codex 이면 정상이다 (물려받을 글이 없다)")
        if 밖:
            print("      ✗ 밖의 것을 썼다 — %s" % "; ".join(sorted(set(밖))[:4]))
        if 나쁨:
            흠.append(길.stem)
    print("\n" + "=" * 78)
    print("  깨끗한 자리 %d / %d" % (len(파일들) - len(흠), len(파일들)))
    if 흠:
        print("  ✗ 어긋난 자리 — %s" % ", ".join(흠))
    print("  ★ 여기서 못 보는 것 — 모델이 학습으로 아는 것.")
    print("=" * 78)
    return 1 if 흠 else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if "--판" in sys.argv:
        i = sys.argv.index("--판")
        if i + 1 >= len(sys.argv):
            print("  ✗ --판 뒤에 판자리를 주십시오")
            return 1
        return 판보기(Path(sys.argv[i + 1]))
    전부 = "--전부" in sys.argv
    자리 = BASELINE / "스킬시험"
    if not 자리.is_dir():
        print("  ✗ 시험 그릇 자리를 못 찾았습니다 — %s (못 찾음은 통과가 아니다)" % 자리)
        return 1
    그릇들 = [p for p in sorted(자리.iterdir()) if (p / "시험.json").is_file()]
    if not 그릇들:
        print("  ✗ 그릇이 없습니다 — %s" % 자리)
        return 1

    깨끗, 더러움, 밖썼음 = [], [], []
    print("=" * 78)
    print("  시험 그릇 %d개 — 어떤 자리에서 돌았나" % len(그릇들))
    print("=" * 78)
    for g in 그릇들:
        본것 = 공용.아이가_본것(g)
        맑, 까닭 = 공용.자리가_깨끗했나(g)
        썼됨, 썼까닭 = 공용.밖의것을_썼나(g)
        (깨끗 if 맑 else 더러움).append(g.name)
        if not 썼됨:
            밖썼음.append((g.name, 썼까닭))
        if 전부:
            print("  %s %-44s 스킬 %-4s 훅 %-5s MCP %s"
                  % ("○" if 맑 else "✗", g.name[:44],
                     본것["스킬수"] if 본것["확인됨"] else "?",
                     "돌음" if 본것["훅돌았나"] else "없음",
                     ", ".join(본것["MCP"]) or "없음"))
    print("\n  깨끗한 자리에서 돈 것 — %d / %d" % (len(깨끗), len(그릇들)))
    if 더러움:
        print("  ✗ 내 설정을 물려받은 것 — %d개" % len(더러움))
        for 이름 in 더러움[:6]:
            print("     · %s" % 이름)
        if len(더러움) > 6:
            print("     … 그리고 %d개 더" % (len(더러움) - 6))
    print("\n  우리 스킬 밖의 것을 **쓴** 것 — %d개" % len(밖썼음))
    for 이름, 까닭 in 밖썼음[:6]:
        print("     ✗ %s — %s" % (이름, 까닭))
    print("\n  ★ 여기서 못 보는 것 — 모델이 학습으로 아는 것. 끌 수도 셀 수도 없다.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
