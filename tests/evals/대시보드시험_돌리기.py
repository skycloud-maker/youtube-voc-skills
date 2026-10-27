# -*- coding: utf-8 -*-
"""대시보드 스킬(`showing-voc-dashboard`) 시험을 실제 AI 로 돌리고 기계로 채점한다 (2026-10-20).

★ 왜 실제 AI 로 돌리나 — 기계 시험은 **도구가 도는지**를 보고, 이 시험은
  **AI 가 스킬을 열어 그대로 따르는지**를 본다.

★ 격리 · 「밖을 봤나」 · 마지막 답 읽기는 판독 시험 돌리개의 것을 **불러 쓴다**
  (같은 코드를 두 벌 두지 않는다 — 공통 규칙 6).

★ 이 스킬은 **API 를 부르지 않는다** — 이미 나온 최종 산출물을 보여 주는 일뿐이다.
  그래서 시험 셋 모두 OpenAI · YouTube 비용이 0 이다 (Claude · Codex 토큰만 든다).

쓰기
    python tests/evals/대시보드시험_돌리기.py <claude|codex|claude-낱개|codex-낱개> <시험id> [번호]
    python tests/evals/대시보드시험_돌리기.py 채점 <그릇 폴더>        돌리지 않고 채점만
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

스킬 = PLUGIN / "skills" / "showing-voc-dashboard"
시험들 = {e["id"]: e for e in json.loads((스킬 / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}

기대항목 = {
    "입력없음_멈춤": ["아무것도 만들지 않았다", "무엇이 필요한지 알렸다"],
    "HTML_만들기": ["살펴보기용·공유용 두 장이 있다", "탭 다섯이 다 있다",
                 "바깥 자원(CDN)이 0개다", "공유용에 원문 전량이 없다",
                 # ★ 2026-10-26 sky 결정 — 식별자를 지우지 않고 **가명**으로 바꾼다
                 "공유용의 유튜브 댓글 id 가 가명이다",
                 "치운 건수와 다시 훑은 결과를 적었다"],
    "최종본을_앉힌다": ["한 겹 자리에 voc_dashboard_dataset.csv 가 있다", "metadata.json 이 있다",
                  "행 수가 원본과 같다", "저장소를 더럽히지 않았다"],
}
for _목록 in 기대항목.values():
    _목록.extend(공용.공통항목)

링크 = re.compile(r"https?://\S+")
탭이름 = ("VoC 현황", "개선 방향성", "문의 속 니즈", "PL Issue", "분석 영상 정보")


def 돌리기(누구: str, 시험id: str, 번: int) -> Path:
    시험 = 시험들[시험id]
    그릇, 최종 = 공용.격리_준비("대시보드_%s_%s_%d" % (누구, 시험id, 번))
    작업 = 그릇 / "작업"
    for f in 시험["files"]:
        원 = BASELINE / f
        받 = 작업 / Path(f).name
        if 원.is_dir():
            shutil.copytree(원, 작업 / Path(f).name)
        else:
            받.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(원, 받)
    if 누구.startswith("claude"):
        명령 = 공용.claude_명령(누구)
        if 누구 != "claude":
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


def _대시보드HTML들(작업: Path) -> list[Path]:
    """AI 가 만든 대시보드 HTML — 스킬이 넣는 탭 이름이 든 것만 센다 (아무 html 이나 세지 않는다)."""
    것 = []
    for p in sorted(작업.rglob("*.html")):
        글 = p.read_text(encoding="utf-8", errors="replace")
        if sum(1 for t in 탭이름 if t in 글) >= 3:
            것.append(p)
    return 것


def 채점(그릇: Path) -> dict:
    정보 = json.loads((그릇 / "시험.json").read_text(encoding="utf-8"))
    작업, 답 = 그릇 / "작업", 공용._마지막답(그릇)
    시험 = 정보["시험"]
    html들 = _대시보드HTML들(작업)
    결과 = []

    def 봄(이름, 됨, 까닭=""):
        결과.append({"항목": 이름, "통과": bool(됨), "까닭": 까닭})

    밖안봄, 걸린것 = 공용.밖을_봤나(그릇)

    if 시험 == "입력없음_멈춤":
        봄("아무것도 만들지 않았다", not html들, "html %d개" % len(html들))
        봄("무엇이 필요한지 알렸다", any(k in 답 for k in ("최종", "엑셀", "1차")),
          답[-120:].replace(chr(10), " "))
    elif 시험 == "HTML_만들기":
        봄("살펴보기용·공유용 두 장이 있다", len(html들) >= 2,
          " · ".join(p.name for p in html들[:4]))
        글들 = [p.read_text(encoding="utf-8", errors="replace") for p in html들]
        봄("탭 다섯이 다 있다", any(all(t in g for t in 탭이름) for g in 글들))
        봄("바깥 자원(CDN)이 0개다",
          all(not re.search(r'(?:src|href)="https?://', g) for g in 글들))
        공유 = [g for p, g in zip(html들, 글들) if "공유" in p.name]
        # ★ 꼬리말이 「원문 전량을 뺐습니다(original_voc · …)」 로 **뺀 칸 이름을 적는다**.
        #   그 글자를 원문으로 세면 거짓 반려가 된다 (2026-10-20 실측). 표의 **칸 머리**를 본다.
        def _표머리에_원문이(글: str) -> bool:
            import re as _re
            머리 = " ".join(_re.findall(r"<th[^>]*>([^<]*)</th>", 글))
            return any(c in 머리 for c in ("original_voc", "parent_voc", "voc_cleaned"))
        봄("공유용에 원문 전량이 없다",
          bool(공유) and not any(_표머리에_원문이(g) for g in 공유),
          "공유용 %d장" % len(공유))
        # ★ 공유용의 유튜브 댓글 id 는 **가명**이어야 한다 (sky 2026-10-26).
        #   ★ 「살펴보기에는 있나」 를 먼저 본다 — 자료에 id 가 없으면 이 항목은 **그냥 참**이 되어
        #     아무것도 지키지 않는다 (2026-10-23 에 기계 시험에서 그 함정을 겪었다).
        유튜브id = re.compile(r"Ug[A-Za-z0-9_.-]{15,}")
        살펴 = [g for p, g in zip(html들, 글들) if "공유" not in p.name]
        봄("공유용의 유튜브 댓글 id 가 가명이다",
          bool(공유) and bool(살펴) and any(유튜브id.search(g) for g in 살펴)
          and not any(유튜브id.search(g) for g in 공유)
          and all("댓글#" in g for g in 공유),
          "살펴보기 id %d곳 · 공유용 id %d곳"
          % (sum(len(유튜브id.findall(g)) for g in 살펴),
             sum(len(유튜브id.findall(g)) for g in 공유)))
        봄("치운 건수와 다시 훑은 결과를 적었다",
          bool(공유) and all("다시 훑은" in g for g in 공유))
    elif 시험 == "최종본을_앉힌다":
        자료 = sorted(작업.rglob("outputs/voc_dashboard_60/*/voc_dashboard_dataset.csv"))
        봄("한 겹 자리에 voc_dashboard_dataset.csv 가 있다", bool(자료),
          " · ".join(p.parent.name for p in 자료[:3]))
        봄("metadata.json 이 있다", bool(자료) and (자료[0].parent / "metadata.json").is_file())
        # ★ 「못 찾음」 은 통과가 아니다 — 자료가 없으면 행 수도 못 본다
        같나 = False
        if 자료:
            import csv as _csv
            with open(자료[0], encoding="utf-8-sig", newline="") as h:
                n = sum(1 for _ in _csv.DictReader(h))
            원본 = next(iter(작업.glob("*.xlsx")), None)
            if 원본 is not None:
                try:
                    import pandas as pd
                    같나 = len(pd.read_excel(원본, sheet_name="raw_voc", keep_default_na=False)) == n
                except Exception:                              # noqa: BLE001
                    같나 = False
        봄("행 수가 원본과 같다", 같나)
        봄("저장소를 더럽히지 않았다", 밖안봄, 걸린것)

    공용.공통채점(그릇, 봄)
    통과 = sum(1 for x in 결과 if x["통과"])
    점수 = {"시험": 시험, "누구": 정보.get("누구"), "통과": 통과, "전체": len(결과), "항목": 결과}
    (그릇 / "채점.json").write_text(json.dumps(점수, ensure_ascii=False, indent=1), encoding="utf-8")
    return 점수


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    if sys.argv[1] == "채점":
        점수 = 채점(Path(sys.argv[2]).resolve())
    else:
        누구, 시험id = sys.argv[1], sys.argv[2]
        번 = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        if 시험id not in 시험들:
            print("모르는 시험 id — 쓸 수 있는 것: %s" % " · ".join(시험들))
            return 1
        점수 = 채점(돌리기(누구, 시험id, 번))
    print("%s · %s — %d/%d" % (점수["누구"], 점수["시험"], 점수["통과"], 점수["전체"]))
    for x in 점수["항목"]:
        print("   %s %s%s" % ("✓" if x["통과"] else "✗", x["항목"],
                            ("   — " + x["까닭"][:70]) if x["까닭"] else ""))
    return 0 if 점수["통과"] == 점수["전체"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
