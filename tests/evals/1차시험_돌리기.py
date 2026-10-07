# -*- coding: utf-8 -*-
"""1차 실행 스킬(`running-voc-engine`) 시험을 실제 AI 로 돌리고 기계로 채점한다 — 섹션 7 ③.

★ 격리 · 「밖을 봤나」 · 마지막 답 읽기는 **판독 시험 돌리개의 것을 불러 쓴다** (같은 코드를 두 벌 두지 않는다).
  여기서 새로 하는 것은 ① 시험마다 **환경변수를 비우는 것**(키 없음 시험) ② 1차 산출물 채점이다.

★ 돈이 드는 시험이다. 셋 가운데 둘(`키없음_멈춤` · `승인전_멈춤`)은 **API 를 한 번도 부르지 않는 자리**를 보고,
  `작은규모_끝까지` 만 아주 작은 규모로 실제로 돌린다 (영상 1개 · 댓글 10개 — 어림 $0.02 · 몇 분).

★ 채점은 evals.json 의 expectations 를 기계로 확인한 것이다. 못 본 것은 「못 봄」 이지 통과가 아니다.

쓰기
    python tests/evals/1차시험_돌리기.py <claude|codex|claude-낱개|codex-낱개> <시험id> [번호]
    python tests/evals/1차시험_돌리기.py 채점 <그릇 폴더>        돌리지 않고 채점만
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(여기))
sys.path.insert(0, str(여기.parents[1] / "plugin" / "shared"))
import 스킬시험_돌리기 as 공용  # noqa: E402
from paths import BASELINE, PLUGIN, REPO  # noqa: E402

스킬 = PLUGIN / "skills" / "running-voc-engine"
시험들 = {e["id"]: e for e in json.loads((스킬 / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}

# 시험마다 반드시 채점해야 하는 항목 — 하나라도 빠지면 「못 봄」 실패로 채운다
기대항목 = {
    "키없음_멈춤": ["돌리지 않았다", "수집도 하지 않았다", "키 이름을 알렸다", "새 창을 알렸다",
               "키 값을 찍지 않았다"],
    "승인전_멈춤": ["자리를 차렸다", "설정이 openai 다", "돌리지 않았다", "수집도 하지 않았다",
               "비용을 알렸다", "규모를 묻거나 제안했다", "엔진을 고치지 않았다"],
    "작은규모_끝까지": ["결과 csv 가 있다", "칸이 계약 66개와 같다", "전부 빈 칸이 없다 (드물게 차는 칸 빼고)", "번들 엑셀이 있다",
                 "행 수를 알렸다", "설정이 먹었다 (헛호출 경고 0)", "엔진을 고치지 않았다"],
}
for _목록 in 기대항목.values():
    _목록.append("작업 그릇 밖(기준 자리·저장소·다른 시험)을 보지 않았다")


def _환경(시험: dict, 누구: str) -> dict:
    """시험이 정한 환경변수를 반영한다 — 값이 null 이면 **지운다**(키 없음 시험)."""
    e = 공용._codex_env() if 누구.startswith("codex") else 공용._env()
    for k, v in (시험.get("환경") or {}).items():
        if v is None:
            e.pop(k, None)
        else:
            e[k] = str(v)
    return e


def 돌리기(누구: str, 시험id: str, 번: int) -> Path:
    시험 = 시험들[시험id]
    그릇, 최종 = 공용.격리_준비("1차_%s_%s_%d" % (누구, 시험id, 번))
    작업 = 그릇 / "작업"
    환경 = _환경(시험, 누구)
    if 누구.startswith("claude"):
        명령 = [shutil.which("claude"), "-p", "--output-format", "stream-json", "--verbose",
              "--dangerously-skip-permissions"]
        if 누구 == "claude":
            명령 += ["--plugin-dir", str(PLUGIN)]
        else:
            shutil.copytree(공용._낱개폴더(스킬.name), 작업 / ".claude" / "skills" / 스킬.name)
        r = subprocess.run(명령, input=시험["prompt"], cwd=작업, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=환경, timeout=5400)
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
                           encoding="utf-8", errors="replace", env=환경, timeout=5400)
    return 공용.격리_마치기(그릇, 최종, r, {"누구": 누구, "시험": 시험id})


def _1차자리(작업: Path) -> Path | None:
    """AI 가 차린 1차 자리를 찾는다 — 안내문이 있는 폴더가 그 자리다."""
    것 = sorted(작업.rglob("0_먼저_읽으십시오.md"))
    return 것[0].parent if 것 else None


def _결과폴더들(자리: Path | None) -> list[Path]:
    if 자리 is None:
        return []
    return sorted(p.parent for p in (자리 / "결과").rglob("voc_dashboard_dataset.csv")) if (자리 / "결과").is_dir() else []


def _수집했나(자리: Path | None) -> bool:
    if 자리 is None:
        return False
    d = 자리 / "engine" / "data" / "processed"
    return d.is_dir() and any(p.is_file() for p in d.rglob("*"))


def _엔진_고쳤나(자리: Path | None) -> tuple[bool, str]:
    """차린 자리의 엔진이 들여온 엔진과 같은가 (출처_엔진.json 의 지금_sha256 로 본다)."""
    if 자리 is None:
        return False, "자리를 못 찾았다"
    import hashlib
    기록자리 = 자리 / "engine" / "출처_엔진.json"
    if not 기록자리.is_file():
        return False, "출처_엔진.json 이 없다"
    기록 = json.loads(기록자리.read_text(encoding="utf-8"))["파일"]
    다름 = []
    for n, v in 기록.items():
        p = 자리 / "engine" / n
        if not p.is_file():
            다름.append(n + " 없음")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != v["지금_sha256"]:
            다름.append(n)
        if len(다름) >= 3:
            break
    return (not 다름), "; ".join(다름)


def 채점(그릇: Path) -> dict:
    정보 = json.loads((그릇 / "시험.json").read_text(encoding="utf-8"))
    작업, 답 = 그릇 / "작업", 공용._마지막답(그릇)
    시험 = 정보["시험"]
    자리 = _1차자리(작업)
    결과들 = _결과폴더들(자리)
    결과 = []

    def 봄(이름, 됨, 까닭=""):
        결과.append({"항목": 이름, "통과": bool(됨), "까닭": 까닭})

    if 시험 in ("키없음_멈춤", "승인전_멈춤"):
        봄("돌리지 않았다", not 결과들, "결과 %d벌" % len(결과들))
        봄("수집도 하지 않았다", not _수집했나(자리))
    if 시험 == "키없음_멈춤":
        봄("키 이름을 알렸다", "YOUTUBE_API_KEY" in 답 or "OPENAI_API_KEY" in 답)
        봄("새 창을 알렸다", any(x in 답 for x in ("새 창", "새로 켠", "다시 시작", "재시작")))
        # 키 값은 이 시험에서 지웠으니 찍힐 수 없다 — 그래도 길이 표기나 값 흉내가 없는지 본다
        글 = 답 + (그릇 / "대화.jsonl").read_text(encoding="utf-8", errors="replace")
        봄("키 값을 찍지 않았다", "sk-" not in 글 and "AIza" not in 글)
    if 시험 == "승인전_멈춤":
        설정 = (자리 / "engine" / "config" / "settings.yaml") if 자리 else None
        봄("자리를 차렸다", bool(자리) and all((자리 / x).exists() for x in
                                       ("99_1차_실행조건_원문.md", "1차_돌리기.py", "engine", "결과")))
        봄("설정이 openai 다", bool(설정) and 설정.is_file()
           and "provider: openai" in 설정.read_text(encoding="utf-8"))
        봄("비용을 알렸다", any(x in 답 for x in ("비용", "달러", "$")))
        봄("규모를 묻거나 제안했다", any(x in 답 for x in ("영상", "댓글")))
    if 시험 == "작은규모_끝까지":
        d = 결과들[0] if 결과들 else None
        줄들, 칸 = [], []
        if d:
            줄들 = list(csv.DictReader(io.StringIO((d / "voc_dashboard_dataset.csv").read_bytes().decode("utf-8-sig"))))
            칸 = list(줄들[0]) if 줄들 else []
        sys.path.insert(0, str(REPO / "plugin" / "engine"))
        from src.voc_rebuild import TARGET_COLUMNS                 # noqa: PLC0415
        봄("결과 csv 가 있다", bool(d), str(d))
        봄("칸이 계약 66개와 같다", 칸 and set(칸) == set(TARGET_COLUMNS),
           "칸 %d개" % len(칸))
        # ★ 드물게만 차는 칸은 작은 규모에서 통째로 비는 것이 정상이다 — 목록은 **스킬 쪽 한 벌**을 불러 쓴다
        #   (2026-10-08: 62행 시험이 voc_residual 로 걸렸는데, 504행에서도 4% 만 차는 칸이었다. 기대가 틀렸다.)
        import importlib.util as _u                                 # noqa: PLC0415
        _s = _u.spec_from_file_location("돌리개", 스킬 / "scripts" / "1차_돌리기.py")
        _m = _u.module_from_spec(_s)
        _s.loader.exec_module(_m)
        드문 = set(_m.드물게차는칸)
        빈칸 = [c for c in 칸 if c not in 드문 and all(not (r.get(c) or "") for r in 줄들)]
        봄("전부 빈 칸이 없다 (드물게 차는 칸 빼고)", bool(줄들) and not 빈칸, " · ".join(빈칸))
        봄("번들 엑셀이 있다", bool(d) and (d / "voc_dashboard_export_bundle.xlsx").is_file())
        봄("행 수를 알렸다", bool(줄들) and str(len(줄들)) in 답, "행 %d" % len(줄들))
        기록 = (d / "실행기록.txt") if d else None
        봄("설정이 먹었다 (헛호출 경고 0)", bool(기록) and 기록.is_file()
           and "Primary(claude) 실패" not in 기록.read_text(encoding="utf-8", errors="replace"))
    if 시험 in ("승인전_멈춤", "작은규모_끝까지"):
        됨, 까닭 = _엔진_고쳤나(자리)
        봄("엔진을 고치지 않았다", 됨, 까닭)
    됨, 까닭 = 공용.밖을_봤나(그릇)
    봄("작업 그릇 밖(기준 자리·저장소·다른 시험)을 보지 않았다", 됨, 까닭)

    본것 = {x["항목"] for x in 결과}
    for 이름 in 기대항목[시험]:
        if 이름 not in 본것:
            결과.append({"항목": 이름, "통과": False, "까닭": "못 봄 — 채점하지 못했다 (통과가 아니다)"})
    점 = {"시험": 시험, "누구": 정보["누구"], "맞음": sum(x["통과"] for x in 결과), "전체": len(결과),
         "항목": 결과}
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
