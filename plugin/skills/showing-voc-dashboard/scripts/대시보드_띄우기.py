# -*- coding: utf-8 -*-
"""대시보드 화면을 **저장소 밖 자리**에서 띄운다 — 여섯 번째 스킬 (2026-10-20).

★ 왜 저장소 밖인가 (2026-10-08 에 실제로 겪었다)
  대시보드는 자기 폴더 아래에 쓴다 (올린 파일 · `outputs/` · `dashboard_run_state.json` ·
  `exact_reanalysis/`). 저장소 안(`plugin/engine/`)에서 띄우면 엔진 지문검사가 깨진다.
  그래서 **자리를 반드시 받고**, 그 자리가 플러그인·저장소 안이면 **멈춘다**.

★ 자리가 없으면 차린다 — 엔진 한 벌과 `config/settings.yaml`(provider: openai)이 같이 들어간다.
  엔진 기본값은 primary 가 Claude 인데 Anthropic 키가 없으면 댓글마다 호출이 실패한다
  (2026-10-08 실행에서 530회 전부). 그래서 자리마다 그 설정이 있어야 한다.

★ 이미 차려진 자리의 **낡은 사본은 묻지 않고 갈아 끼운다.** 차리기는 「이미 있는 파일은
  건드리지 않는다」 라서 스킬을 고쳐도 옛 자리는 옛 코드로 뜬다. 사람이 **보는 화면**이라
  옛 코드로 떠도 알아채기 어렵다. 결과(`outputs/`)는 건드리지 않는다.

★ 띄울 자료가 없으면 **띄우지 않는다.** 빈 화면을 띄워 놓고 됐다고 하지 않는다.
  1차 결과나 최종 산출물 가운데 무엇이 필요한지 말한다.

쓰기
    python <이 스킬>/scripts/대시보드_띄우기.py <자리>
    python <이 스킬>/scripts/대시보드_띄우기.py <자리> --최종 <최종엑셀>    최종본을 앉히고 띄운다
    python <이 스킬>/scripts/대시보드_띄우기.py <자리> --포트 8502
    python <이 스킬>/scripts/대시보드_띄우기.py <자리> --차리기만            차리고 띄우지는 않는다

종료코드
    0  띄웠다 (사람이 끄면 0)        1  막혔다 (무엇이 막혔는지 말한다)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(스킬.parents[1] / "shared" / "lib"))
sys.path.insert(0, str(스킬 / "shared" / "lib"))


def _찾기(이름: str) -> Path:
    """스킬 안 사본 → 플러그인 옆 한 벌 (낱개로 꾸리면 스킬 안에 들어 있다)."""
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름


def _저장소_안인가(자리: Path) -> str:
    """자리가 플러그인·스킬 안이면 그 까닭을 돌려준다 (빈 글자면 괜찮다)."""
    for 막을곳 in (스킬.parents[1], 스킬):            # 플러그인 뿌리 · 이 스킬
        try:
            자리.relative_to(막을곳)
        except ValueError:
            continue
        return ("자리가 플러그인 안입니다 (%s). 대시보드는 자기 폴더 아래에 쓰므로 "
                "엔진 사본이 더러워집니다 — **저장소 밖**의 빈 폴더를 주십시오." % 막을곳)
    return ""


def _띄울자료가_있나(엔진자리: Path) -> list[Path]:
    """대시보드가 스스로 찾는 **한 겹** 자리의 자료들 (`latest_dataset` 과 같은 무늬)."""
    뿌리 = 엔진자리 / "outputs" / "voc_dashboard_60"
    if not 뿌리.is_dir():
        return []
    return sorted(뿌리.glob("*/voc_dashboard_dataset.csv"), key=lambda p: p.stat().st_mtime)


def 띄우기(자리: Path, 포트: int = 8501, 최종: Path | None = None, 차리기만: bool = False) -> int:
    막힘 = _저장소_안인가(자리)
    if 막힘:
        print("  ✗ %s" % 막힘)
        return 1
    try:
        import 일차자리                                        # noqa: PLC0415
    except ImportError as e:
        print("  ✗ 공통 라이브러리를 못 불렀습니다 — %s" % e)
        print("     `shared/lib/일차자리.py` 가 스킬 안이나 플러그인 옆에 있어야 합니다.")
        return 1

    # ★ 돌릴 때마다 차리기를 돌린다 — 없으면 차리고, 낡은 사본이 있으면 갈아 끼운다.
    #   스킬 스크립트는 넘기지 않는다 (1차 돌리개는 이 자리에 필요 없다).
    차림, 그대로, 낡음 = 일차자리.차리기(자리, _찾기("shared"), _찾기("engine"), None, 새로=True)
    if 차림:
        print("  · 자리를 차렸습니다 — %s (차림 %d · 그대로 %d)" % (자리, 차림, 그대로))
    if 낡음:
        print("  · 낡은 사본 %d개를 갈아 끼웠습니다: %s" % (len(낡음), ", ".join(낡음[:5])))

    엔진자리 = 자리 / "engine"
    if 최종 is not None:
        앉히개 = Path(__file__).resolve().parent / "최종본_앉히기.py"
        코드 = subprocess.run([sys.executable, "-B", str(앉히개), str(자리), str(최종)],
                            env=dict(os.environ, PYTHONIOENCODING="utf-8",
                                     PYTHONDONTWRITEBYTECODE="1")).returncode
        if 코드:
            print("  ✗ 최종본을 못 앉혔습니다 — 위를 보십시오. 화면을 띄우지 않습니다.")
            return 1

    자료들 = _띄울자료가_있나(엔진자리)
    if not 자료들:
        print("  ✗ 띄울 자료가 없습니다 — 화면을 띄우지 않습니다.")
        print("     대시보드는 engine/outputs/voc_dashboard_60/<이름>/voc_dashboard_dataset.csv 를 찾습니다.")
        print("     둘 중 하나를 주십시오 —")
        print("       ① 1차 결과가 든 자리 (1차를 돌리면 거기에 떨어집니다)")
        print("       ② 4차까지 거친 **최종 엑셀** — `--최종 <엑셀>` 로 주면 앉혀서 띄웁니다")
        return 1
    print("  · 띄울 자료 %d개 — 가장 새 것: %s" % (len(자료들), 자료들[-1].parent.name))
    if 차리기만:
        print("  · 차리기만 했습니다 — 띄우지 않았습니다.")
        return 0

    print("  띄웁니다 — %s (포트 %d)" % (엔진자리, 포트))
    print("    브라우저에서 http://localhost:%d 를 엽니다. 끄려면 Ctrl+C." % 포트)
    환경 = dict(os.environ, YT_ANALYSIS_SETTINGS_PATH="config/settings.yaml",
              PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    try:
        return subprocess.run([sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
                               "--server.port", str(포트), "--server.headless", "true",
                               "--browser.gatherUsageStats", "false"],
                              cwd=str(엔진자리), env=환경).returncode
    except FileNotFoundError:
        print("  ✗ streamlit 을 못 찾았습니다 — python -m pip install streamlit")
        return 1


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    인자 = sys.argv[1:]
    # ★ 2026-10-08 — `--help` 를 **자리 이름으로 보고** 저장소 안에 `--help/` 폴더를 만들어
    #   엔진 157개를 복사했고 커밋까지 됐다. 그래서 도움말을 **맨 먼저** 가린다.
    if not 인자 or 인자[0] in ("-h", "--help", "/?"):
        print(__doc__)
        return 0 if 인자 else 1
    포트, 최종, 차리기만 = 8501, None, False
    남은 = []
    i = 0
    while i < len(인자):
        x = 인자[i]
        if x == "--포트" and i + 1 < len(인자):
            포트 = int(인자[i + 1]); i += 2
        elif x == "--최종" and i + 1 < len(인자):
            최종 = Path(인자[i + 1]).resolve(); i += 2
        elif x == "--차리기만":
            차리기만 = True; i += 1
        elif x.startswith("--"):
            print("  ✗ 모르는 가름말입니다: %s" % x)      # 자리 이름으로 보지 않는다
            print(__doc__)
            return 1
        else:
            남은.append(x); i += 1
    if not 남은:
        print("  ✗ 자리를 주십시오 — 저장소 밖의 빈 폴더입니다.")
        print(__doc__)
        return 1
    return 띄우기(Path(남은[0]).resolve(), 포트, 최종, 차리기만)


if __name__ == "__main__":
    sys.exit(main())
