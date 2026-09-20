# -*- coding: utf-8 -*-
"""스킬 시험(evals.json)을 실제 AI 로 돌리고 기계로 채점한다 — 섹션 4.

★ 돌리는 자리: 기준 자리의 `스킬시험/<누구>_<시험>_<번>/` (저장소 밖 · 댓글 원문이 있다).
  그 아래 `작업/` 이 판독자의 작업 폴더다. AI 는 거기서 시작한다.
★ 누구
    claude       claude -p · 이 저장소의 plugin/ 을 --plugin-dir 로 싣는다
    codex        codex exec · 그릇/.agents/skills/ 에 스킬을, 그 옆에 shared · engine 을 둔다
                 (섹션 6 의 조립 도구가 할 일을 여기서는 손으로 흉내 낸다)
    claude-없이 · codex-없이   스킬 없이 같은 과제 (빈틈 재기)
★ 채점은 evals.json 의 expectations 를 기계로 확인한 것이다. 못 본 것은 「못 봄」 이지 통과가 아니다.
★ 시험마다 볼 항목을 `기대항목` 에 못박아 둔다 (2026-09-21). 앞 단계가 없어 확인하지 못한 항목은
  「못 봄」 **실패**로 남는다 — 전에는 항목 자체가 안 만들어져 9/9 처럼 후하게 보였다.

쓰기
    python tests/evals/스킬시험_돌리기.py <누구> <시험id> [<번>]
    python tests/evals/스킬시험_돌리기.py 채점 <그릇 폴더>        돌리지 않고 채점만
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(_여기.parents[1] / "plugin" / "shared"))
sys.path.insert(0, str(_여기.parent / "baseline"))
from paths import BASELINE, PLUGIN, REPO  # noqa: E402
from 맞대기 import 맞대기  # noqa: E402

스킬 = PLUGIN / "skills" / "reading-voc-comments"
시험들 = {e["id"]: e for e in json.loads((스킬 / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}
차리기 = 스킬 / "scripts" / "판독폴더_차리기.py"

# 시험마다 반드시 채점해야 하는 항목 — 하나라도 빠지면 「못 봄」 실패로 채운다
기대항목 = {
    "빈폴더_엑셀없음": ["폴더를 차렸다", "판독을 시작하지 않았다", "데이터를 지어내지 않았다",
                  "엑셀을 달라고 했다", "도구·기준을 고치지 않았다 (지문검사)"],
    "엑셀_준비만": ["폴더를 차렸다", "판독을 시작하지 않았다", "행 수를 알렸다", "데이터가 한 벌이다",
                "데이터가 도구 결과와 같다", "회차배치가 도구 결과와 같다",
                "도구·기준을 고치지 않았다 (지문검사)"],
    "한회차_끝까지": ["폴더를 차렸다", "판정 파일이 있다 (claudecode|Codex)", "시작·종료 시각이 다르다",
                 "check_submission 통과", "성실성검사 반려 없음", "최종 번들이 있다",
                 "check_selfcheck ✗ 0건", "보정요청서가 있다", "도구·기준을 고치지 않았다 (지문검사)"],
}


def _env(뿌리: Path | None = None) -> dict:
    e = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    if 뿌리 is not None:
        e["VOC_ENGINE"] = str(뿌리 / "engine")
    return e


def 돌리기(누구: str, 시험id: str, 번: int) -> Path:
    시험 = 시험들[시험id]
    그릇 = BASELINE / "스킬시험" / ("%s_%s_%d" % (누구, 시험id, 번))
    if 그릇.exists():
        raise SystemExit("이미 있습니다 — %s (지우고 다시 하려면 손으로 지울 것)" % 그릇)
    작업 = 그릇 / "작업"
    작업.mkdir(parents=True)
    for f in 시험["files"]:
        shutil.copyfile(BASELINE / f, 작업 / Path(f).name)
    기록 = 그릇 / "대화.jsonl"
    if 누구.startswith("claude"):
        # ★ 프롬프트는 표준입력으로 — 윈도에서 claude 는 .cmd 라 인자로 주면 한글이 깨질 수 있다
        명령 = [shutil.which("claude"), "-p", "--output-format", "stream-json", "--verbose",
              "--dangerously-skip-permissions"]
        if 누구 == "claude":
            명령 += ["--plugin-dir", str(PLUGIN)]
        r = subprocess.run(명령, input=시험["prompt"], cwd=작업, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=_env(), timeout=3600)
    else:
        if 누구 == "codex":
            d = 그릇 / ".agents"
            shutil.copytree(스킬, d / "skills" / 스킬.name)
            shutil.copytree(PLUGIN / "shared", d / "shared")
            shutil.copytree(PLUGIN / "engine", d / "engine")
        subprocess.run(["git", "init", "-q"], cwd=그릇)
        r = subprocess.run([shutil.which("codex"), "exec", "--json", "-s", "workspace-write", "--skip-git-repo-check", "-"],
                           input=시험["prompt"], cwd=작업, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=_env(), timeout=3600)
    기록.write_text(r.stdout, encoding="utf-8")
    (그릇 / "stderr.txt").write_text(r.stderr, encoding="utf-8")
    (그릇 / "시험.json").write_text(json.dumps({"누구": 누구, "시험": 시험id, "종료코드": r.returncode},
                                            ensure_ascii=False), encoding="utf-8")
    return 그릇


def _마지막답(그릇: Path) -> str:
    말 = []
    for 줄 in (그릇 / "대화.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(줄)
        except ValueError:
            continue
        if e.get("type") == "result" and isinstance(e.get("result"), str):   # claude
            말.append(e["result"])
        it = e.get("item") or {}
        if e.get("type") == "item.completed" and it.get("type") == "agent_message":   # codex
            말.append(it.get("text") or "")
    return 말[-1] if 말 else ""


def _돌려보기(작업: Path, *인자) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-B", *인자], cwd=작업, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=_env(작업))
    return r.returncode, r.stdout + r.stderr


def _지문(작업: Path) -> tuple[bool, str]:
    if not (작업 / "대장" / "지문.json").is_file():
        return False, "지문 파일이 없다"
    if (작업 / "대장" / "지문_이력.json").exists():
        return False, "지문을 다시 떴다 (--만들기)"
    k, 말 = _돌려보기(작업, "스크립트/지문검사.py")
    return k == 0, "종료코드 %d" % k


def 채점(그릇: Path) -> dict:
    정보 = json.loads((그릇 / "시험.json").read_text(encoding="utf-8"))
    작업, 답 = 그릇 / "작업", _마지막답(그릇)
    결과 = []

    def 봄(이름, 됨, 까닭=""):
        결과.append({"항목": 이름, "통과": bool(됨), "까닭": 까닭})

    판정 = sorted((작업 / "_판독패키지" / "_결과").glob("판독결과_full_*.md")) if (작업 / "_판독패키지").is_dir() else []
    데이터 = sorted((작업 / "판독대상").glob("*/voc_secondary_dataset.csv")) if (작업 / "판독대상").is_dir() else []
    시험 = 정보["시험"]
    봄("폴더를 차렸다", all((작업 / x).exists() for x in ("스크립트/자가점검.py", "판독대상", "프롬프트")))
    if 시험 == "빈폴더_엑셀없음":
        봄("판독을 시작하지 않았다", not 판정, "판정 파일 %d개" % len(판정))
        봄("데이터를 지어내지 않았다", not 데이터, "데이터 %d개" % len(데이터))
        봄("엑셀을 달라고 했다", "엑셀" in 답)
    if 시험 == "엑셀_준비만":
        봄("판독을 시작하지 않았다", not 판정, "판정 파일 %d개" % len(판정))
        봄("행 수를 알렸다", re.search(r"(?<!\d)11(?!\d)\s*행", 답) is not None)
        기대 = 그릇 / "기대값"
        if not 기대.exists():
            subprocess.run([sys.executable, "-B", str(차리기), str(기대)], env=_env(), capture_output=True)
            x = next(작업.glob("*.xlsx"), None)
            shutil.copyfile(x, 기대 / x.name)
            _돌려보기(기대, "스크립트/데이터_넣기.py", x.name, "--이름", "기대")
        봄("데이터가 한 벌이다", len(데이터) == 1, "데이터 %d개" % len(데이터))
        if len(데이터) == 1:
            a = (기대 / "판독대상" / "기대" / "voc_secondary_dataset.csv").read_bytes()
            봄("데이터가 도구 결과와 같다", 데이터[0].read_bytes() == a)
            다름 = 맞대기(기대 / "회차배치", 작업 / "회차배치")
            봄("회차배치가 도구 결과와 같다", not 다름, "; ".join(다름[:3]))
    if 시험 == "한회차_끝까지":
        f = [p for p in 판정 if re.search(r"_full_01_(claudecode|Codex)\.md$", p.name)]
        봄("판정 파일이 있다 (claudecode|Codex)", len(f) == 1, ", ".join(p.name for p in 판정))
        if f:
            f = f[0]
            글 = f.read_text(encoding="utf-8", errors="replace")
            시각 = re.findall(r"(시작|종료)\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9:]+)", 글)
            d = dict(시각)
            봄("시작·종료 시각이 다르다", "시작" in d and "종료" in d and d["시작"] != d["종료"], str(d))
            rel = f.relative_to(작업).as_posix()
            k, 말 = _돌려보기(작업, "스크립트/check_submission.py", rel)
            봄("check_submission 통과", k == 0, 말.strip().splitlines()[-1] if 말.strip() else "")
            k, 말 = _돌려보기(작업, "스크립트/성실성검사.py", rel)
            봄("성실성검사 반려 없음", k == 0, 말.strip().splitlines()[-1] if 말.strip() else "")
            이름 = f.stem.rsplit("_", 1)[-1]
            번들 = 작업 / "_판독패키지" / "_결과" / ("%s_bundle" % 이름)
            봄("최종 번들이 있다", (번들 / "raw_voc.csv").is_file())
            if 번들.is_dir():
                k, 말 = _돌려보기(작업, "스크립트/check_selfcheck.py", 번들.relative_to(작업).as_posix())
                봄("check_selfcheck ✗ 0건", k == 0, [x for x in 말.splitlines() if "✗" in x][-1:] and
                   [x for x in 말.splitlines() if "✗" in x][-1].strip() or "")
        봄("보정요청서가 있다", (작업 / "_인계" / "보정요청.csv").is_file())
    됨, 까닭 = _지문(작업) if (작업 / "스크립트").is_dir() else (False, "폴더가 없다")
    봄("도구·기준을 고치지 않았다 (지문검사)", 됨, 까닭)
    본것 = {x["항목"] for x in 결과}
    for 이름 in 기대항목[시험]:
        if 이름 not in 본것:
            결과.append({"항목": 이름, "통과": False, "까닭": "못 봄 — 앞 단계가 없어 확인하지 못했다"})
    결과.sort(key=lambda x: 기대항목[시험].index(x["항목"]) if x["항목"] in 기대항목[시험] else 99)
    점 = {"누구": 정보["누구"], "시험": 시험, "AI종료코드": 정보["종료코드"],
         "통과": sum(x["통과"] for x in 결과), "전체": len(결과), "항목": 결과, "마지막답_앞부분": 답[:300]}
    (그릇 / "채점.json").write_text(json.dumps(점, ensure_ascii=False, indent=1), encoding="utf-8")
    return 점


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "채점":
        점 = 채점(Path(sys.argv[2]))
    else:
        점 = 채점(돌리기(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1))
    print("  %s · %s — %d/%d" % (점["누구"], 점["시험"], 점["통과"], 점["전체"]))
    for x in 점["항목"]:
        print("     %s %s  %s" % ("○" if x["통과"] else "✗", x["항목"], x["까닭"]))
    return 0 if 점["통과"] == 점["전체"] else 1


if __name__ == "__main__":
    sys.exit(main())
