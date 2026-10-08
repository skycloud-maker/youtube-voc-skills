# -*- coding: utf-8 -*-
"""대시보드(09-07 최신판)를 **저장소 밖 엔진 사본**에서 띄운다 — 섹션 7 ④.

★ 왜 저장소 밖인가 — 대시보드는 자기 폴더 아래에 쓴다 (업로드 받은 파일 · `outputs/` ·
  `dashboard_run_state.json` · `exact_reanalysis/`). 저장소 안(`plugin/engine/`)에서 띄우면
  엔진 지문검사(`tests/test_engine.py`)가 깨진다. 1차 실행과 같은 까닭이다 (2026-10-08 에 겪었다).

★ 자리가 없으면 `running-voc-engine` 스킬의 차리기로 **새로 차린다** — 엔진 한 벌과
  `config/settings.yaml`(provider: openai)이 같이 들어간다. 같은 코드 한 벌을 쓴다.

쓰기
    python tools/대시보드_띄우기.py                      기본 자리에 차려서 띄운다
    python tools/대시보드_띄우기.py <자리> [포트]         자리를 정해 띄운다
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin" / "shared"))
sys.path.insert(0, str(REPO / "plugin" / "shared" / "lib"))
import 일차자리  # noqa: E402
from paths import DASHBOARD_ROOT  # noqa: E402

기본자리 = DASHBOARD_ROOT      # ★ 자리는 paths.py 한 곳에서만 정한다 (공통 규칙 6)


def 띄우기(자리: Path, 포트: int = 8501) -> int:
    엔진 = 자리 / "engine"
    # ★ 띄울 때마다 차리기를 돌린다 — 없으면 차리고, **낡은 사본이 있으면 갈아 끼운다**(2026-10-08).
    #   대시보드는 사람이 보는 화면이라 옛 코드로 뜨면 알아채기 어렵다. 1차 자리와 달리 묻지 않고 맞춘다.
    차림, 그대로, 낡음 = 일차자리.차리기(자리, REPO / "plugin" / "shared", REPO / "plugin" / "engine",
                                 REPO / "plugin" / "skills" / "running-voc-engine" / "scripts", 새로=True)
    if 차림:
        print("  자리를 차렸습니다 — %s (차림 %d · 그대로 %d)" % (자리, 차림, 그대로))
    if 낡음:
        print("  · 낡은 사본 %d개를 갈아 끼웠습니다: %s" % (len(낡음), ", ".join(낡음[:5])))
    print("  띄웁니다 — %s (포트 %d)" % (엔진, 포트))
    환경 = dict(os.environ, YT_ANALYSIS_SETTINGS_PATH="config/settings.yaml",
              PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
                           "--server.port", str(포트), "--server.headless", "true",
                           "--browser.gatherUsageStats", "false"],
                          cwd=str(엔진), env=환경).returncode


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "/?"):
        print(__doc__)           # ★ 2026-10-08 — 전에는 `--help` 를 **자리 이름으로 보고 대시보드를 띄웠다**
        return 0
    자리 = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else 기본자리
    포트 = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    return 띄우기(자리, 포트)


if __name__ == "__main__":
    sys.exit(main())
