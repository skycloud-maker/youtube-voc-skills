# -*- coding: utf-8 -*-
"""기준 정답을 한 번 만든다 — 옛 2판 도구의 **사본**을 저장소 밖 기준 자리에서 돌린다.

★ 결정 0002 (sky 2026-09-18): 옛 결과 파일은 그 뒤 코드가 바뀌고 사람이 고쳐 써서
  기준으로 못 쓴다. 그래서 옛 도구(최신판)와 입력을 복사해 **사본을** 돌리고,
  그 결과를 기준 정답으로 얼린다. 옛 폴더는 복사만 했고 여기서는 읽지도 않는다.

★ 옛 폴더를 막는 것
  - 엔진은 VOC_ENGINE 으로 사본(기준자리/engine)을 가리킨다.
    옛 도구는 이것이 없을 때만 옛 엔진 자리로 간다.
  - PYTHONDONTWRITEBYTECODE=1 — 어디에도 캐시를 쓰지 않는다.
  - 돌리기 전·후 옛 폴더 상태 대조는 따로 한다 (진행 기록 참고).

★ 두 번씩 돌린다 — 두 번이 다른 자리는 기준에서 빼야 하므로 먼저 안다.

쓰기
    python tests/baseline/기준_만들기.py            없는 실행만 만든다
기준 자리의 `실행/` 아래에 이미 있는 것은 덮지 않는다 (얼린 기준을 지키려고).
"""
from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugin" / "shared"))
from paths import BASELINE  # noqa: E402

원본 = BASELINE / "원본사본" / "2판"
엔진 = BASELINE / "engine"

# 도구가 **만들어 낼** 것 — 돌리기 전 상태로 되돌리려고 사본에서 뺀다 (2판 기준 상대경로)
_공통제외 = [
    "s15_master",
    "_판독패키지/_결과/master_final",
    "_판독패키지/_결과/분리재지정_01_총괄확정.md",   # 08-26 17:05 — 통합(09:47) 뒤에 생김
    "_최종결과",
    "_인계/편향검사.md",
    "_인계/보정요청_논의본.md",
    "0_결과는_어디_있나.md",
    "_라벨바꾸기전_*",       # 08-26 16:59 백업 — 두 실행 뒤에 생겼고 raw_voc.csv 가 있어 2차 번들로 잡힌다
    "__pycache__",
]
실행들 = {
    # 3차_준비 (원래 08-25 23:08) — 2차 번들 둘 → 갈린 행 · 익명화 · 회차 · 감독 폴더
    "3차준비": ("3차_준비.py", _공통제외 + [
        "s13_judge", "_총괄만", "_감독폴더",
        "_판독패키지/_결과/감독결과_*.md",
    ]),
    # 3차_마무리 (원래 08-26 09:47) — 감독결과 28개 + 매핑 → 통합 ~ _최종결과
    "3차마무리": ("3차_마무리.py", _공통제외),
}


def _뺄것(제외: list[str]):
    def ignore(dirpath: str, names: list[str]) -> set[str]:
        rel = Path(dirpath).relative_to(원본).as_posix()
        rel = "" if rel == "." else rel + "/"
        return {n for n in names
                if any(fnmatch.fnmatch(rel + n, pat) for pat in 제외)}
    return ignore


def 한번(이름: str, 번: int) -> int:
    그릇 = BASELINE / "실행" / ("%s_%d" % (이름, 번))
    if 그릇.exists():
        print("  · %s — 이미 있어 건너뜁니다 (얼린 기준은 덮지 않습니다)" % 그릇.name)
        return 0
    return 차려서_돌리기(이름, 그릇)


def 차려서_돌리기(이름: str, 그릇: Path) -> int:
    """`그릇/2판` 에 돌리기 전 상태를 차리고 도구를 돌린다. 시험도 이것을 쓴다.

    ★ 그릇의 부모에는 다른 2판이 없어야 한다 — 도구가 부모 폴더까지 뒤진다.
    """
    도구, 제외 = 실행들[이름]
    뿌리 = 그릇 / "2판"
    shutil.copytree(원본, 뿌리, ignore=_뺄것(제외))
    env = dict(os.environ, VOC_ENGINE=str(엔진), PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run([sys.executable, "-B", str(뿌리 / 도구)], cwd=str(뿌리),
                       env=env, text=True, encoding="utf-8", errors="replace",
                       capture_output=True)
    (그릇 / "실행기록.txt").write_text(
        "도구: %s\n종료코드: %d\n\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
        % (도구, r.returncode, r.stdout, r.stderr), encoding="utf-8")
    print("  · %s — 종료코드 %d" % (그릇.name, r.returncode))
    return r.returncode


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    for 자리, 뜻 in ((원본, "옛 2판 사본"), (엔진 / "src" / "voc_rebuild", "엔진 사본")):
        if not 자리.is_dir():
            print("  ✗ %s 을 못 찾았습니다 — %s" % (뜻, 자리))
            return 1
    if "codex" in str(BASELINE).lower():
        print("  ✗ 기준 자리가 옛 폴더 안입니다 — %s" % BASELINE)
        return 1
    나쁨 = 0
    for 이름 in 실행들:
        for 번 in (1, 2):
            나쁨 |= 한번(이름, 번) != 0
    return 1 if 나쁨 else 0


if __name__ == "__main__":
    sys.exit(main())
