# -*- coding: utf-8 -*-
"""보고서 스킬(`building-voc-report`) 시험을 실제 AI 로 돌리고 기계로 채점한다 — 섹션 8.

★ 왜 실제 AI 로 돌리나 — 기계 시험은 **도구가 도는지**를 보고, 이 시험은 **AI 가 스킬을 열어 그대로 따르는지**를 본다.
  (sky 2026-10-09 「2번을 해봐야 정말 잘 도는지 확인되는 게 아닌가」 — 맞다.)

★ 격리 · 「밖을 봤나」 · 마지막 답 읽기는 판독 시험 돌리개의 것을 **불러 쓴다** (같은 코드를 두 벌 두지 않는다).

★ 이 스킬은 **API 를 부르지 않는다** — 보고서는 최종 엑셀에서 옮겨 담는 일뿐이다.
  그래서 시험 셋 모두 OpenAI · YouTube 비용이 0 이다 (Claude · Codex 토큰만 든다).

쓰기
    python tests/evals/보고서시험_돌리기.py <claude|codex|claude-낱개|codex-낱개> <시험id> [번호]
    python tests/evals/보고서시험_돌리기.py 채점 <그릇 폴더>        돌리지 않고 채점만
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(여기))
sys.path.insert(0, str(여기.parents[1] / "plugin" / "shared"))
import 스킬시험_돌리기 as 공용  # noqa: E402
from paths import BASELINE, PLUGIN  # noqa: E402

스킬 = PLUGIN / "skills" / "building-voc-report"
시험들 = {e["id"]: e for e in json.loads((스킬 / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}

기대항목 = {
    "입력없음_멈춤": ["보고서를 만들지 않았다", "무엇이 필요한지 알렸다"],
    "보고서_만들기": ["보고서가 하나 있다", "담아야 할 것이 들어 있다", "숫자에 출처가 붙었다",
                 "원문 전량이 안 담겼다", "링크·이메일이 0건이다", "치운 건수를 적었다"],
    "개인정보_섞인_입력": ["보고서가 하나 있다", "링크 0건", "이메일 0건", "사용자명 0건",
                   "치운 건수를 숫자로 알렸다"],
}
for _목록 in 기대항목.values():
    _목록.append("작업 그릇 밖(기준 자리·저장소·다른 시험)을 보지 않았다")


def 돌리기(누구: str, 시험id: str, 번: int) -> Path:
    시험 = 시험들[시험id]
    그릇, 최종 = 공용.격리_준비("보고서_%s_%s_%d" % (누구, 시험id, 번))
    작업 = 그릇 / "작업"
    for f in 시험["files"]:
        shutil.copyfile(BASELINE / f, 작업 / Path(f).name)
    if 누구.startswith("claude"):
        명령 = [shutil.which("claude"), "-p", "--output-format", "stream-json", "--verbose",
              "--dangerously-skip-permissions"]
        if 누구 == "claude":
            명령 += ["--plugin-dir", str(PLUGIN)]
        else:
            shutil.copytree(공용._낱개폴더(스킬.name), 작업 / ".claude" / "skills" / 스킬.name)
        r = subprocess.run(명령, input=시험["prompt"], cwd=작업, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=공용._env(), timeout=3600)
    else:
        if 누구 == "codex-낱개":
            shutil.copytree(공용._낱개폴더(스킬.name), 그릇 / ".agents" / "skills" / 스킬.name)
        else:
            d = 그릇 / ".agents"
            shutil.copytree(스킬, d / "skills" / 스킬.name)
            shutil.copytree(PLUGIN / "shared", d / "shared")
            shutil.copytree(PLUGIN / "engine", d / "engine")
        subprocess.run(["git", "init", "-q"], cwd=그릇)
        r = subprocess.run([shutil.which("codex"), "exec", "--json", "-s", "workspace-write",
                            "--skip-git-repo-check", "-"],
                           input=시험["prompt"], cwd=작업, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=공용._codex_env(), timeout=3600)
    return 공용.격리_마치기(그릇, 최종, r, {"누구": 누구, "시험": 시험id})


def _보고서들(작업: Path) -> list[Path]:
    """AI 가 만든 보고서 — 스킬이 넣는 말머리가 든 html 만 센다 (아무 html 이나 세지 않는다)."""
    것 = []
    for p in sorted(작업.rglob("*.html")):
        글 = p.read_text(encoding="utf-8", errors="replace")
        if "VoC" in 글 and ("보고서" in 글 or "report" in 글.lower()):
            것.append(p)
    return 것


def 채점(그릇: Path) -> dict:
    정보 = json.loads((그릇 / "시험.json").read_text(encoding="utf-8"))
    작업, 답 = 그릇 / "작업", 공용._마지막답(그릇)
    시험 = 정보["시험"]
    보고서 = _보고서들(작업)
    글 = 보고서[0].read_text(encoding="utf-8", errors="replace") if 보고서 else ""
    결과 = []

    def 봄(이름, 됨, 까닭=""):
        결과.append({"항목": 이름, "통과": bool(됨), "까닭": 까닭})

    if 시험 == "입력없음_멈춤":
        봄("보고서를 만들지 않았다", not 보고서, "보고서 %d개" % len(보고서))
        봄("무엇이 필요한지 알렸다", any(x in 답 for x in ("최종", "엑셀", "xlsx")))
    else:
        봄("보고서가 하나 있다", len(보고서) >= 1, "%d개" % len(보고서))
    if 시험 == "보고서_만들기":
        봄("담아야 할 것이 들어 있다", all(x in 글 for x in ("PL", "improvement_priority")))
        봄("숫자에 출처가 붙었다", 글.count("출처") >= 3, "출처 %d곳" % 글.count("출처"))
        # 원문 전량이 담겼다면 보고서가 훨씬 커진다 — 시험 재료는 시트마다 12행뿐이다
        봄("원문 전량이 안 담겼다", 글.count("<tr>") < 200, "행 %d" % 글.count("<tr>"))
        봄("링크·이메일이 0건이다", not re.search(r"https?://", 글)
           and not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", 글))
        봄("치운 건수를 적었다", "치운 것" in 글 and "다시 훑은 결과" in 글)
    if 시험 == "개인정보_섞인_입력":
        봄("링크 0건", not re.search(r"https?://", 글))
        봄("이메일 0건", not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", 글))
        봄("사용자명 0건", not re.search(r"@[\w가-힣._-]{2,}", 글))
        # 0 이 아니었다는 것을 **숫자로** 말해야 한다 (65 §3 「했다」 가 아니라 「확인했다」)
        수 = re.findall(r"링크\s*(\d+)", 답 + 글)
        봄("치운 건수를 숫자로 알렸다", any(int(x) > 0 for x in 수), "찾은 숫자 %s" % 수[:4])
    됨, 까닭 = 공용.밖을_봤나(그릇)
    봄("작업 그릇 밖(기준 자리·저장소·다른 시험)을 보지 않았다", 됨, 까닭)

    본것 = {x["항목"] for x in 결과}
    for 이름 in 기대항목[시험]:
        if 이름 not in 본것:
            결과.append({"항목": 이름, "통과": False, "까닭": "못 봄 — 채점하지 못했다 (통과가 아니다)"})
    점 = {"시험": 시험, "누구": 정보["누구"], "맞음": sum(x["통과"] for x in 결과), "전체": len(결과), "항목": 결과}
    (그릇 / "채점.json").write_text(json.dumps(점, ensure_ascii=False, indent=1), encoding="utf-8")
    return 점


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) >= 3 and sys.argv[1] == "채점":
        점 = 채점(Path(sys.argv[2]))
    elif len(sys.argv) in (3, 4) and sys.argv[1] in ("claude", "codex", "claude-낱개", "codex-낱개"):
        if sys.argv[2] not in 시험들:
            print("시험 id — %s" % " · ".join(시험들))
            return 2
        최종 = 돌리기(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) == 4 else 1)
        점 = 채점(최종)
        print("  그릇 — %s" % 최종)
    else:
        print(__doc__)
        return 2
    print("  %s · %s — %d/%d" % (점["누구"], 점["시험"], 점["맞음"], 점["전체"]))
    for x in 점["항목"]:
        print("    %s %s%s" % ("✓" if x["통과"] else "✗", x["항목"], (" — " + x["까닭"]) if x["까닭"] else ""))
    return 0 if 점["맞음"] == 점["전체"] else 1


if __name__ == "__main__":
    sys.exit(main())
