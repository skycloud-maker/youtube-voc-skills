# -*- coding: utf-8 -*-
"""총괄 스킬로 차린 자리에서 3차 도구를 돌린다 — 얼린 3차 기준과 맞대기 위한 후보 (섹션 5 · 2026-09-21).

얼린 기준(섹션 2)은 옛 2판 **사본 전체**에서 돌렸다. 여기서는 총괄 스킬의 `총괄자리_차리기` 로 차린 자리에
같은 **입력**만 얹어 같은 도구를 돌린다. 도구가 만든 결과(`볼자리`)가 같으면, 차린 자리가 3차에 모자람이 없다는 뜻이다.

입력 (기준 자리 원본사본/2판 에서 — 얼린 기준과 같은 것)
  3차준비    2차 번들 둘 · _인계/보정요청.csv
  3차마무리  + s13_judge · _총괄만(정답지) · 감독결과 28개 · _감독폴더
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugin" / "shared"))
from paths import BASELINE, PLUGIN  # noqa: E402

원본 = BASELINE / "원본사본" / "2판"
차리기도구 = PLUGIN / "skills" / "coordinating-voc-pipeline" / "scripts" / "총괄자리_차리기.py"
도구 = {"3차준비": "3차_준비.py", "3차마무리": "3차_마무리.py"}
입력 = {
    "3차준비": ["_판독패키지/_결과/claudecode_bundle", "_판독패키지/_결과/Codex_bundle", "_인계/보정요청.csv"],
    "3차마무리": ["_판독패키지/_결과/claudecode_bundle", "_판독패키지/_결과/Codex_bundle", "_인계/보정요청.csv",
               "s13_judge", "_총괄만", "_감독폴더", "_판독패키지/_결과/감독결과_*.md"],
}
# 도구가 만든 결과 — 얼린 기준과 맞댈 자리
볼자리 = {
    "3차준비": ("s13_judge", "_총괄만", "_인계"),
    "3차마무리": ("s15_master", "_판독패키지/_결과/master_final", "_최종결과", "_인계"),
}


def 차려서_돌리기(이름: str, 그릇: Path, 엔진: Path | None = None) -> int:
    """엔진 — 주지 않으면 차린 자리의 engine/ (플러그인 엔진). 얼린 기준과 맞댈 때는 기준 자리의 엔진 사본을 준다:
    엑셀 번들 시트는 엔진이 만드는데, 얼린 기준은 섹션 2 엔진 사본(옛 live_merge)으로 만들었다 (2026-09-21 확인)."""
    총괄 = 그릇 / "총괄"
    r = subprocess.run([sys.executable, "-B", str(차리기도구), str(총괄), "2판"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"))
    if r.returncode:
        raise RuntimeError("총괄자리_차리기 실패:\n" + r.stdout + r.stderr)
    판 = 총괄 / "2판"
    for 자리 in 입력[이름]:
        if "*" in 자리:
            for p in sorted(원본.glob(자리)):
                q = 판 / p.relative_to(원본)
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, q)
            continue
        p, q = 원본 / 자리, 판 / 자리
        q.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if p.is_dir() else shutil.copyfile)(p, q)
    env = dict(os.environ, VOC_ENGINE=str(엔진 or (판 / "engine")), PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run([sys.executable, "-B", str(판 / 도구[이름])], cwd=str(판), env=env,
                       text=True, encoding="utf-8", errors="replace", capture_output=True)
    (그릇 / "실행기록.txt").write_text("도구: %s\n종료코드: %d\n\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
                                   % (도구[이름], r.returncode, r.stdout, r.stderr), encoding="utf-8")
    return r.returncode
