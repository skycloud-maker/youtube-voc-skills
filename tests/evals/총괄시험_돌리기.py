# -*- coding: utf-8 -*-
"""총괄 스킬 시험(coordinating-voc-pipeline/evals/evals.json)을 실제 AI 로 돌리고 기계로 채점한다 — 섹션 5.

★ 외딴 자리에서 한 번에 하나 (스킬시험_돌리기.격리_준비) · 「작업 그릇 밖을 보지 않았다」 채점도 같다.
★ 입력은 2판 실제 결과(기준 자리 원본사본) — 총괄 도구는 같은 입력에 늘 같은 결과를 내므로 얼린 3차 기준과 맞댄다.
  엑셀 번들은 엔진 판 차이로 시트가 다르다 → CSV · 인계만 맞댄다.

쓰기
    python tests/evals/총괄시험_돌리기.py <claude|codex|claude-없이|codex-없이> <시험id> [<번>]
    python tests/evals/총괄시험_돌리기.py 채점 <그릇 폴더>
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import ntpath
import re
import shutil
import subprocess
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
sys.path.insert(0, str(_여기))
import 스킬시험_돌리기 as 공통  # noqa: E402
from paths import BASELINE, PLUGIN  # noqa: E402
from 맞대기 import 맞대기  # noqa: E402

스킬 = PLUGIN / "skills" / "coordinating-voc-pipeline"
시험들 = {e["id"]: e for e in json.loads((스킬 / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]}
원본 = BASELINE / "원본사본" / "2판"
판독사본 = {"A": BASELINE / "원본사본" / "판독A", "B": BASELINE / "원본사본" / "판독B"}
얼린준비 = BASELINE / "실행" / "3차준비_1" / "2판"
얼린마무리 = BASELINE / "실행" / "3차마무리_1" / "2판"
차리기도구 = 스킬 / "scripts" / "총괄자리_차리기.py"

기대항목 = {
    "2에서3_준비": ["총괄 도구가 판 폴더에 있다", "감독 입력이 얼린 기준과 행마다 같다", "정답지는 _총괄만 에만",
               "감독 폴더 둘에 입력과 쪽지가 있다", "감독하지 않았다"],
    "3에서4_마무리": ["s15_master CSV 가 얼린 기준과 같다", "_인계 가 얼린 기준과 같다",
               "최종 번들의 첫 시트가 0_차례", "편향검사.csv 가 있다", "감독 결과를 고치지 않았다"],
    "판독결과_하나뿐": ["감독 입력을 만들지 않았다", "두 번째 판독자 번들을 지어내지 않았다", "두 판독자가 필요하다고 말했다"],
}
for _목록 in 기대항목.values():
    _목록.extend(공통.공통항목)


def _판독폴더(작업: Path, 쪽: str) -> None:
    """판독자 결과 폴더 하나 — 실무자가 넘기는 모양 (번들 · 보정요청)."""
    이름 = {"A": "claudecode", "B": "Codex"}[쪽]
    d = 작업 / ("판독%s" % 쪽)
    shutil.copytree(원본 / "_판독패키지" / "_결과" / ("%s_bundle" % 이름), d / "_판독패키지" / "_결과" / ("%s_bundle" % 이름))
    (d / "_인계").mkdir(parents=True)
    shutil.copyfile(판독사본[쪽] / "_인계" / "보정요청.csv", d / "_인계" / "보정요청.csv")


def _감독끝(작업: Path) -> dict:
    """총괄 자리를 차리고 3차_마무리 직전 상태를 얹는다 (얼린 기준과 같은 입력). 감독 결과 해시를 돌려준다."""
    subprocess.run([sys.executable, "-B", str(차리기도구), str(작업 / "총괄"), "시험판"], check=True,
                   capture_output=True, env=공통._env())
    판 = 작업 / "총괄" / "시험판"
    for 자리 in ("_판독패키지/_결과/claudecode_bundle", "_판독패키지/_결과/Codex_bundle", "s13_judge", "_총괄만"):
        shutil.copytree(원본 / 자리, 판 / 자리)
    (판 / "_인계").mkdir(exist_ok=True)
    shutil.copyfile(원본 / "_인계" / "보정요청.csv", 판 / "_인계" / "보정요청.csv")
    해시 = {}
    for p in sorted((원본 / "_판독패키지" / "_결과").glob("감독결과_*.md")):
        감독 = "3차 감독1" if p.stem.endswith("_codex") else "3차 감독2"     # 원문 배정 — 감독1=Codex · 감독2=Claude Code
        q = 판 / "_감독폴더" / 감독 / "_판독패키지" / "_결과" / p.name
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, q)
        해시[q.relative_to(작업).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return 해시


def 돌리기(누구: str, 시험id: str, 번: int) -> Path:
    시험 = 시험들[시험id]
    그릇, 최종 = 공통.격리_준비("총괄_%s_%s_%d" % (누구, 시험id, 번))
    작업 = 그릇 / "작업"
    해시 = {}
    if 시험["차림"] in ("판독자둘", "판독자하나"):
        _판독폴더(작업, "A")
        if 시험["차림"] == "판독자둘":
            _판독폴더(작업, "B")
    else:
        해시 = _감독끝(작업)
    if 누구.startswith("claude"):
        명령 = 공통.claude_명령(누구)
        환경 = 공통._env()
    else:
        if 누구 == "codex":
            d = 그릇 / ".agents"
            for s in ("coordinating-voc-pipeline", "reading-voc-comments", "supervising-voc-disagreements"):
                shutil.copytree(PLUGIN / "skills" / s, d / "skills" / s)
            shutil.copytree(PLUGIN / "shared", d / "shared")
            shutil.copytree(PLUGIN / "engine", d / "engine")
        subprocess.run(["git", "init", "-q"], cwd=그릇)
        명령 = [shutil.which("codex"), "exec", "--json", "-s", "workspace-write", "--skip-git-repo-check", "-"]
        환경 = 공통._codex_env()
    # ★ 2026-09-22 (섹션 5b 뒤 재점검) — 이 시험은 결과를 **얼린 3차 기준**과 맞댄다. 섹션 5b 에서 뒤처리 기본 동작을 바꿨으므로
    #   (N/A 행을 다시 빼지 않음 · 판독자 지적을 자르지 않음 · out_of_scope_product 를 폐기로 보지 않음)
    #   얼린 기준을 만든 옛 동작으로 돌린다. 새 동작은 tests/test_baseline.py 의 test_가3_… 이 따로 본다
    환경["VOC_얼린기준_재현"] = "1"
    r = subprocess.run(명령, input=시험["prompt"], cwd=작업, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=환경, timeout=5400)
    최종 = 공통.격리_마치기(그릇, 최종, r, {"누구": 누구, "시험": 시험id})
    (최종 / "입력해시.json").write_text(json.dumps(해시, ensure_ascii=False), encoding="utf-8")
    return 최종


def _읽기(p: Path) -> list[dict]:
    return list(csv.DictReader(io.StringIO(p.read_bytes().decode("utf-8-sig"))))


def _판독자별(판: Path) -> dict:
    """judge_input 의 A·B 를 정답지로 풀어 {atomic_id: {판독자: 값}} 로 바꾼다."""
    매핑 = json.loads((판 / "_총괄만" / "ab_mapping.json").read_text(encoding="utf-8"))
    out = {}
    for r in _읽기(판 / "s13_judge" / "judge_input.csv"):
        m = 매핑[r["atomic_id"]]
        이름 = {k: ntpath.basename(v.replace("/", "\\")) for k, v in m.items()}
        out[r["atomic_id"]] = ({이름["A"]: r["A"], 이름["B"]: r["B"]},
                               {k: v for k, v in r.items() if k not in ("A", "B")})
    return out


def 채점(그릇: Path) -> dict:
    정보 = json.loads((그릇 / "시험.json").read_text(encoding="utf-8"))
    작업, 답 = 그릇 / "작업", 공통._마지막답(그릇)
    시험 = 정보["시험"]
    결과 = []

    def 봄(항목, 됨, 까닭=""):
        결과.append({"항목": 항목, "통과": bool(됨), "까닭": 까닭})

    판 = 작업 / "총괄" / "시험판"
    if 시험 == "2에서3_준비":
        봄("총괄 도구가 판 폴더에 있다", (판 / "3차_준비.py").is_file() and (판 / "3차_마무리.py").is_file())
        if (판 / "s13_judge" / "judge_input.csv").is_file() and (판 / "_총괄만" / "ab_mapping.json").is_file():
            새, 옛 = _판독자별(판), _판독자별(얼린준비)
            다름 = [k for k in 옛 if 새.get(k) != 옛[k]]
            봄("감독 입력이 얼린 기준과 행마다 같다", len(새) == len(옛) == 1909 and not 다름,
               "행 %d / %d · 다른 행 %d" % (len(새), len(옛), len(다름)))
        봄("정답지는 _총괄만 에만", (판 / "_총괄만" / "ab_mapping.json").is_file()
           and not list((판 / "_감독폴더").rglob("ab_mapping*")) if (판 / "_감독폴더").is_dir() else False)
        감독 = [판 / "_감독폴더" / g for g in ("3차 감독1", "3차 감독2")]
        봄("감독 폴더 둘에 입력과 쪽지가 있다", all((d / "s13_judge" / "judge_input.csv").is_file()
                                            and (d / "0_여기에_붙여넣으십시오.md").is_file() for d in 감독))
        봄("감독하지 않았다", not list(작업.rglob("감독결과_*.md")))
    if 시험 == "3에서4_마무리":
        다름 = 맞대기(얼린마무리 / "s15_master", 판 / "s15_master", 얼린마무리, 판)
        봄("s15_master CSV 가 얼린 기준과 같다", not 다름, "; ".join(다름[:2]))
        다름 = 맞대기(얼린마무리 / "_인계", 판 / "_인계", 얼린마무리, 판)
        봄("_인계 가 얼린 기준과 같다", not 다름, "; ".join(다름[:2]))
        xl = 판 / "_최종결과" / "3차_최종데이터.xlsx"
        첫 = ""
        if xl.is_file():
            import openpyxl
            wb = openpyxl.load_workbook(xl, read_only=True)
            첫 = wb.sheetnames[0] if wb.sheetnames else ""
            wb.close()
        봄("최종 번들의 첫 시트가 0_차례", 첫 == "0_차례", "첫 시트 %r" % 첫)
        봄("편향검사.csv 가 있다", (판 / "_판독패키지" / "_결과" / "master_final" / "편향검사.csv").is_file())
        옛해시 = json.loads((그릇 / "입력해시.json").read_text(encoding="utf-8"))
        바뀜 = [r for r, h in 옛해시.items() if not (작업 / r).is_file()
               or hashlib.sha256((작업 / r).read_bytes()).hexdigest() != h]
        봄("감독 결과를 고치지 않았다", len(옛해시) == 28 and not 바뀜, "바뀜 %d" % len(바뀜))
    if 시험 == "판독결과_하나뿐":
        봄("감독 입력을 만들지 않았다", not list(작업.rglob("judge_input.csv")))
        봄("두 번째 판독자 번들을 지어내지 않았다", not list(작업.rglob("Codex_bundle")))
        봄("두 판독자가 필요하다고 말했다", re.search(r"둘|두\s*명|2\s*명|두\s*판독|두\s*개|두\s*번째|다른\s*판독자|하나만", 답) is not None)
    공통.공통채점(그릇, 봄)
    본것 = {x["항목"] for x in 결과}
    for 항목 in 기대항목[시험]:
        if 항목 not in 본것:
            결과.append({"항목": 항목, "통과": False, "까닭": "못 봄 — 앞 단계가 없어 확인하지 못했다"})
    결과.sort(key=lambda x: 기대항목[시험].index(x["항목"]) if x["항목"] in 기대항목[시험] else 99)
    점 = {"누구": 정보["누구"], "시험": 시험, "AI종료코드": 정보["종료코드"], "통과": sum(x["통과"] for x in 결과),
         "전체": len(결과), "항목": 결과, "마지막답_앞부분": 답[:300]}
    (그릇 / "채점.json").write_text(json.dumps(점, ensure_ascii=False, indent=1), encoding="utf-8")
    return 점


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "채점":
        점 = 채점(Path(sys.argv[2]))
    else:
        점 = 채점(돌리기(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1))
    print("  총괄 · %s · %s — %d/%d" % (점["누구"], 점["시험"], 점["통과"], 점["전체"]))
    for x in 점["항목"]:
        print("     %s %s  %s" % ("○" if x["통과"] else "✗", x["항목"], x["까닭"]))
    return 0 if 점["통과"] == 점["전체"] else 1


if __name__ == "__main__":
    sys.exit(main())
