# -*- coding: utf-8 -*-
"""보고서 기준을 한 번 만든다 — **우리** 보고서 스킬을 고정된 입력으로 돌려 얼린다.

★ 왜 다른 기준들과 방식이 다른가 (2026-10-26)
  다른 얼린 기준은 「옛 도구 사본을 돌려 만든 정답」 과 댄다 (결정 0002). 보고서는 그럴 수 없다 —
  **옛 저장소에 보고서 산출물이 하나도 없다** (0개 · 2026-10-23 실측). 섹션 8 에서 새로 지은 것이다.
  그래서 여기서 얼리는 것은 「기존과 같은가」 가 아니라 **「앞으로 안 변하는가」** 다 (회귀 방지).
  결정 0005 의 빈 칸 둘 중 손댈 수 있는 쪽이 이것이다.

★ 입력은 **고정된 것** 하나다 — 기준 자리의 옛 2판 최종 번들(6,846행 · 17시트).
  지문을 못 박아 두어 그 파일이 바뀌면 **여기서 먼저 멈춘다.**

★ 두 번 돌린다 — 두 번이 다른 자리는 기준에서 빼야 하므로 먼저 안다.
  실제로 다른 자리는 **「만든 날」 한 줄뿐**이다 (`보고서_만들기.py` 의 `datetime.now()`).
  시험은 그 한 줄만 자리표로 바꾸고 나머지를 전량 댄다.

쓰기
    python tests/baseline/보고서기준_만들기.py            없는 실행만 만든다
기준 자리의 `실행/` 아래에 이미 있는 것은 덮지 않는다 (얼린 기준을 지키려고).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
뿌리 = 여기.parents[1]
sys.path.insert(0, str(뿌리 / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

# ★ 입력 — 기준 자리의 옛 2판 최종 번들. 지문은 test_baseline.py 와 **같은 값**이어야 한다
입력상대 = "_판독패키지/_결과/master_final/voc_dashboard_export_bundle_2차시험본.xlsx"
입력지문 = "6e07c2281953a8c29a0d38ec7c1f499bd9a61d77b5a549c77734854cb7be0c3f"
도구 = 뿌리 / "plugin" / "skills" / "building-voc-report" / "scripts" / "보고서_만들기.py"
낼이름 = "VoC_분석보고서.html"


def _지문(p: Path) -> str:
    import hashlib                                             # noqa: PLC0415

    h = hashlib.sha256()
    with open(p, "rb") as f:
        for 조각 in iter(lambda: f.read(1 << 20), b""):
            h.update(조각)
    return h.hexdigest()


def 돌리기(그릇: Path) -> int:
    """`그릇` 에 보고서 한 장과 실행기록을 남긴다. 시험도 이것을 쓴다."""
    입력 = BASELINE / "원본사본" / "2판" / 입력상대
    if not 입력.is_file():
        print("  ✗ 입력을 못 찾았습니다 — %s" % 입력)
        return 1
    if _지문(입력) != 입력지문:
        print("  ✗ 입력이 바뀌었습니다 — 보고서 기준의 전제가 깨집니다: %s" % 입력)
        return 1
    그릇.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run([sys.executable, "-B", "-X", "utf8", str(도구),
                        str(입력), str(그릇 / 낼이름)],
                       cwd=str(뿌리), env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    (그릇 / "실행기록.txt").write_text(
        "도구: %s\n종료코드: %d\n\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
        % (도구.name, r.returncode, r.stdout, r.stderr), encoding="utf-8")
    print("  · %s — 종료코드 %d" % (그릇.name, r.returncode))
    return r.returncode


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if "codex" in str(BASELINE).lower():
        print("  ✗ 기준 자리가 옛 폴더 안입니다 — %s" % BASELINE)
        return 1
    나쁨 = 0
    for 번 in (1, 2):
        그릇 = BASELINE / "실행" / ("보고서_%d" % 번)
        if 그릇.exists():
            print("  · %s — 이미 있어 건너뜁니다 (얼린 기준은 덮지 않습니다)" % 그릇.name)
            continue
        나쁨 |= 돌리기(그릇) != 0
    return 1 if 나쁨 else 0


if __name__ == "__main__":
    sys.exit(main())
