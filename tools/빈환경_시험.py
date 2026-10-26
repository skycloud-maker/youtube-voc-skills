# -*- coding: utf-8 -*-
"""빈 컴퓨터를 **흉내 내어** 설치 목록이 맞는지 밟아 본다 (2026-10-26).

★ 왜 (sky 2026-10-26) — 「완전 깨끗한 새 노트북에서 클로드로 skill 주고 돌리면 안된다는 것인가요?」
  실제 AI 시험은 **폴더만** 격리하고 파이썬은 이 컴퓨터 것을 썼다(`sys.executable`).
  그래서 pandas·openpyxl 이 이미 깔린 환경에서만 통과를 확인한 셈이다.
  `dist/판/0_빈컴퓨터에서_무엇을_깔까.md` 의 목록은 **코드를 보고 적은 것**이고 밟아 본 것이 아니다.

★ 무엇을 하나 — 패키지가 **하나도 없는** 가상환경을 새로 만들어 단계별로 돌린다.
    ① 아무것도 없을 때          → 도구가 **크게 실패**해야 한다 (조용히 통과하면 더 나쁘다)
    ② pandas · openpyxl 만     → 안내서가 「보기·만들기엔 이 둘」 이라 했다. 정말 되나
    ③ 엔진 requirements        → 목록이 풀리나 (`--dry-run` · 실제로 깔지는 않는다)

★ 할 수 없는 것 — `claude` · `codex` 명령과 API 키가 필요한 2·3·4차와 1차는 여기서 못 본다
  (명령은 가상환경 밖의 것이고, 키는 sky 가 넣는다). 그 자리는 「안 해 봤다」 로 남는다.

쓰기
    python tools/빈환경_시험.py [자리] [최종엑셀]      자리를 안 주면 paths.py 의 EMPTY_ENV_ROOT
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_여기 = Path(__file__).resolve().parent
_뿌리 = _여기.parent
sys.path.insert(0, str(_뿌리 / "plugin" / "shared"))
from paths import BASELINE, EMPTY_ENV_ROOT  # noqa: E402

# ★ 「보기·만들기」 에 필요한 꾸러미 — **여기 한 곳에서만** 정한다 (공통 규칙 6).
#   2026-10-26 빈 환경에서 밟아 확인한 목록이다. 안내서·도구 안내문이 이것과 같은지
#   tests/test_빈환경목록.py 가 대조한다.
보기패키지 = ("pandas", "openpyxl", "pyyaml")

보고서도구 = _뿌리 / "plugin" / "skills" / "building-voc-report" / "scripts" / "보고서_만들기.py"
대시보드도구 = _뿌리 / "plugin" / "skills" / "showing-voc-dashboard" / "scripts" / "대시보드_HTML_만들기.py"
엔진 = _뿌리 / "plugin" / "engine"
요구목록 = 엔진 / "requirements.txt"


def _돌리기(파이썬: Path, 인자: list[str], 자리: Path, 환경: dict | None = None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1", VOC_ENGINE=str(엔진))
    if 환경:
        env.update(환경)
    # ★ 빈 환경을 흉내 내려면 이 컴퓨터의 파이썬 경로가 새 들어오지 않게 해야 한다
    env.pop("PYTHONPATH", None)
    return subprocess.run([str(파이썬), *인자], cwd=str(자리), env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def _없는모듈(글: str) -> str:
    """ModuleNotFoundError 에서 모듈 이름만 뽑는다."""
    for 줄 in 글.splitlines():
        if "ModuleNotFoundError" in 줄 or "No module named" in 줄:
            return 줄.strip()[:120]
    return ""


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    자리 = Path(sys.argv[1]) if len(sys.argv) > 1 else EMPTY_ENV_ROOT
    # ★ 기본 입력은 **기준 자리의 옛 2판 최종 번들** — 얼린 보고서 기준과 같은 파일이다.
    #   자리·경로를 코드에 박지 않는다 (공통 규칙 6 · paths.py 에서만 정한다).
    입력 = (Path(sys.argv[2]) if len(sys.argv) > 2 else
           BASELINE / "원본사본" / "2판" / "_판독패키지" / "_결과" / "master_final"
           / "voc_dashboard_export_bundle_2차시험본.xlsx")
    if not 입력.is_file():
        print("  ✗ 시험 입력을 못 찾았습니다 — %s" % 입력)
        return 1
    if 자리.exists():
        shutil.rmtree(자리)
    (자리 / "작업").mkdir(parents=True)
    작업 = 자리 / "작업"
    shutil.copy2(입력, 작업 / 입력.name)
    엑셀 = 작업 / 입력.name

    print("=" * 70)
    print("  빈 환경 시험 — %s" % 자리)
    print("=" * 70)
    r = subprocess.run([sys.executable, "-m", "venv", str(자리 / "venv")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print("  ✗ 가상환경을 못 만들었습니다\n%s" % (r.stdout + r.stderr)[-800:])
        return 1
    py = 자리 / "venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = 자리 / "venv" / "bin" / "python"
    print("  · 빈 가상환경을 만들었습니다 — %s" % py)
    깔린것 = _돌리기(py, ["-m", "pip", "list", "--format=json"], 작업)
    try:
        목록 = [x["name"] for x in json.loads(깔린것.stdout or "[]")]
    except ValueError:
        목록 = ["(못 읽음)"]
    print("    깔린 것 — %s" % (", ".join(목록) or "없음"))

    낸것 = {}

    def 단계(이름: str, 말: str, r, 바람: str):
        좋 = (r.returncode == 0) if 바람 == "통과" else (r.returncode != 0)
        낸것[이름] = {"바람": 바람, "종료코드": r.returncode, "좋은가": 좋,
                   "없는모듈": _없는모듈(r.stdout + r.stderr)}
        print("\n  [%s] %s" % ("○" if 좋 else "✗", 말))
        print("     종료코드 %d (바라던 것 — %s)" % (r.returncode, 바람))
        모 = 낸것[이름]["없는모듈"]
        if 모:
            print("     %s" % 모)
        if not 좋:
            print("     ↓ 끝 10줄")
            for l in (r.stdout + r.stderr).splitlines()[-10:]:
                print("       %s" % l[:150])

    # ── ① 아무것도 없을 때 — 크게 실패해야 한다 ──────────────────────────────
    단계("①보고서_빈환경", "아무것도 없을 때 보고서 도구",
       _돌리기(py, [str(보고서도구), str(엑셀), str(작업 / "보고서.html")], 작업), "막힘")
    단계("①대시보드_빈환경", "아무것도 없을 때 대시보드 도구",
       _돌리기(py, [str(대시보드도구), str(엑셀), str(작업 / "낸것1")], 작업), "막힘")

    # ── ② 안내서가 말한 둘만 깐다 ────────────────────────────────────────────
    print("\n  · pip install %s — 안내서가 적은 목록 그대로" % " ".join(보기패키지))
    r = _돌리기(py, ["-m", "pip", "install", "--quiet", *보기패키지], 작업)
    if r.returncode:
        print("    ✗ 설치가 막혔습니다 (인터넷?)\n%s" % (r.stdout + r.stderr)[-600:])
        return 1
    단계("②보고서_목록대로", "안내서 목록만으로 보고서 도구",
       _돌리기(py, [str(보고서도구), str(엑셀), str(작업 / "보고서.html")], 작업), "통과")
    단계("②대시보드_목록대로", "안내서 목록만으로 대시보드 도구",
       _돌리기(py, [str(대시보드도구), str(엑셀), str(작업 / "낸것2")], 작업), "통과")

    # ── ③ 엔진 설치 목록이 풀리나 (깔지는 않는다) ────────────────────────────
    if 요구목록.is_file():
        단계("③엔진목록", "엔진 requirements 가 풀리나 (--dry-run)",
           _돌리기(py, ["-m", "pip", "install", "--dry-run", "--quiet",
                      "-r", str(요구목록)], 작업), "통과")
    else:
        print("\n  [✗] 엔진 requirements.txt 가 없다 — %s" % 요구목록)
        낸것["③엔진목록"] = {"바람": "통과", "종료코드": -1, "좋은가": False, "없는모듈": "파일 없음"}

    (자리 / "결과.json").write_text(json.dumps(낸것, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    나쁨 = [k for k, v in 낸것.items() if not v["좋은가"]]
    print("\n" + "=" * 70)
    print("  바라던 대로 된 것 %d / %d" % (len(낸것) - len(나쁨), len(낸것)))
    if 나쁨:
        print("  ✗ 어긋난 자리 — %s" % ", ".join(나쁨))
    print("  ★ 여기서 못 본 것 — 1차(키 둘) · 2·3·4차(claude·codex 명령). 그 자리는 「안 해 봤다」 다.")
    print("=" * 70)
    return 1 if 나쁨 else 0


if __name__ == "__main__":
    sys.exit(main())
