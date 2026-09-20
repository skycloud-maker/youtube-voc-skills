# -*- coding: utf-8 -*-
"""2차(판독) 기준 정답을 만든다 — 섹션 4 · 결정 0002 와 같은 방식.

재료 (모두 기준 자리의 사본 — 옛 자리는 복사할 때만 읽었다)
  원본사본/꾸러미/VoC_2_2차판독/   옛 판독 꾸러미 zip 을 푼 것 (09-18 에 다시 만든 판)
  원본사본/판독A · 판독B/          2판 실제 판독 폴더 (Downloads\\VoC 판독 A · B)

★ 꾸러미 도구 가운데 **7개**에 옛 폴더를 부르는 대비책 경로가 있었다
  (apply_approved · build_bundle · check_selfcheck · check_submission · topic_registry · 엔진자리 · 자가점검).
  이 컴퓨터에는 옛 폴더가 있으므로 그대로 돌리면 옛 작업 폴더의 계약 검증 코드를 읽는다.
  그래서 아래 시나리오에서 **실제로 도는 6개**를 대비책 지운 판(plugin/shared/tools/)으로 바꿔 돌린다.
  자가점검.py 는 이 시나리오에서 돌지 않아 바꾸지 않았다 — 바꾸면 얼린 기준의 파일 해시가 달라진다.
  (지운 줄은 plugin/shared/출처_꾸러미.json 의 고친_이력)

시나리오
  2차데이터넣기   꾸러미 + 1차 결과 엑셀 → 데이터_넣기.py (판독대상 · 회차배치)
  2차번들A       꾸러미 + 판독A 의 판독대상·회차배치·s9_group·판정 53개 → 최종 번들 (claudecode)
  2차번들B       같은 방식 · 판독B (Codex)

쓰기
    python tests/baseline/기준_만들기_2차.py        없는 실행만 만든다 (두 번씩)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugin" / "shared"))
from paths import BASELINE, SHARED  # noqa: E402

꾸러미 = BASELINE / "원본사본" / "꾸러미" / "VoC_2_2차판독"
판독 = {"A": BASELINE / "원본사본" / "판독A", "B": BASELINE / "원본사본" / "판독B"}
엑셀이름 = "voc_dashboard_export_bundle (14).xlsx"
바꿀도구 = ["apply_approved.py", "build_bundle.py", "check_selfcheck.py",
          "check_submission.py", "topic_registry.py", "엔진자리.py"]
판독자 = {"A": "claudecode", "B": "Codex"}


def _꾸러미_깔기(뿌리: Path) -> None:
    shutil.copytree(꾸러미, 뿌리)
    for n in 바꿀도구:
        shutil.copyfile(SHARED / "tools" / n, 뿌리 / "스크립트" / n)


def _판독_얹기(뿌리: Path, 쪽: str) -> None:
    원 = 판독[쪽]
    for d in ("판독대상", "회차배치", "s9_group"):
        if (뿌리 / d).exists():
            shutil.rmtree(뿌리 / d)
        shutil.copytree(원 / d, 뿌리 / d)
    결과 = 뿌리 / "_판독패키지" / "_결과"
    for p in sorted((원 / "_판독패키지" / "_결과").glob("판독결과_full_*_%s.md" % 판독자[쪽])):
        shutil.copyfile(p, 결과 / p.name)


def _스킬로_깔기(뿌리: Path) -> None:
    """★ 새 도구 — 판독 스킬의 판독폴더_차리기.py 로 꾸러미 자리를 차린다 (후보)."""
    차리기도구 = SHARED.parent / "skills" / "reading-voc-comments" / "scripts" / "판독폴더_차리기.py"
    r = subprocess.run([sys.executable, "-B", str(차리기도구), str(뿌리)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"))
    if r.returncode:
        raise RuntimeError("판독폴더_차리기 실패:\n" + r.stdout + r.stderr)


def 차리기(이름: str, 뿌리: Path, 깔기=_꾸러미_깔기) -> list[str]:
    """뿌리에 돌리기 전 상태를 차리고, 돌릴 명령(스크립트 뒤 인자)을 돌려준다."""
    깔기(뿌리)
    if 이름 == "2차데이터넣기":
        shutil.copyfile(판독["A"] / 엑셀이름, 뿌리 / 엑셀이름)
        return ["스크립트/데이터_넣기.py", 엑셀이름, "--이름", "로니"]
    쪽 = 이름[-1]
    _판독_얹기(뿌리, 쪽)
    return ["스크립트/build_bundle.py",
            "_판독패키지/_결과/판독결과_full_*_%s.md" % 판독자[쪽],
            "--apply", "--product", "all", "--xlsx", "--out", "%s_bundle" % 판독자[쪽]]


실행들 = ("2차데이터넣기", "2차번들A", "2차번들B")
# 후보(스킬)와 얼린 기준을 맞댈 자리 — 판독 폴더 안 상대경로. 그 밖(지문 · 옛 판 문서)은 달라도 된다
볼자리 = {"2차데이터넣기": ("판독대상", "회차배치"),
         "2차번들A": ("_판독패키지/_결과/claudecode_bundle", "s9_group"),
         "2차번들B": ("_판독패키지/_결과/Codex_bundle", "s9_group")}


def 스킬로_차리기(이름: str, 뿌리: Path) -> list[str]:
    return 차리기(이름, 뿌리, 깔기=_스킬로_깔기)


def 차려서_돌리기(이름: str, 그릇: Path, 차리는법=차리기) -> int:
    뿌리 = 그릇 / "판독"
    명령 = 차리는법(이름, 뿌리)
    env = dict(os.environ, VOC_ENGINE=str(뿌리 / "engine"), VOC_CONTRACTS=str(뿌리 / "engine"),
               PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run([sys.executable, "-B", *명령], cwd=str(뿌리), env=env, text=True,
                       encoding="utf-8", errors="replace", capture_output=True)
    (그릇 / "실행기록.txt").write_text(
        "명령: %s\n종료코드: %d\n\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
        % (" ".join(명령), r.returncode, r.stdout, r.stderr), encoding="utf-8")
    print("  · %s — 종료코드 %d" % (그릇.name, r.returncode))
    return r.returncode


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    for 자리 in (꾸러미, *판독.values()):
        if not 자리.is_dir():
            print("  ✗ 재료를 못 찾았습니다 — %s" % 자리)
            return 1
    나쁨 = 0
    for 이름 in 실행들:
        for 번 in (1, 2):
            그릇 = BASELINE / "실행" / ("%s_%d" % (이름, 번))
            if 그릇.exists():
                print("  · %s — 이미 있어 건너뜁니다" % 그릇.name)
                continue
            그릇.mkdir(parents=True)
            나쁨 |= 차려서_돌리기(이름, 그릇) != 0
    return 1 if 나쁨 else 0


if __name__ == "__main__":
    sys.exit(main())
