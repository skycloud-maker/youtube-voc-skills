# -*- coding: utf-8 -*-
"""최종 산출물을 **대시보드가 스스로 찾는 자리**에 앉힌다 (2026-10-20).

★ 왜 이 도구가 있나 (sky 2026-10-20 — 「대시보드 스킬을 더한다 (여섯 번째)」)
  대시보드는 `outputs/voc_dashboard_60/<이름>/voc_dashboard_dataset.csv` 를 **스스로 찾아** 띄운다
  (`src/dashboard60/data_contract.py:294 latest_dataset` — glob 이 `*/voc_dashboard_dataset.csv` 라
  **한 겹**이다). 1차 결과가 바로 거기에 떨어지므로 1차는 자동으로 뜬다.

  그런데 **4차까지 거친 최종 엑셀은 그 자리에 없다.** 사람이 대시보드의
  「결과 파일 올려서 보기」 패널에 올리고 「이 파일로 화면 바꾸기」 를 **한 번 더 눌러야** 바뀐다
  (그 패널이 쓰는 `outputs/voc_dashboard_60/app_runs/<id>/` 는 **두 겹**이라 스스로 못 찾는다).
  그 두 번의 클릭을 없애려고, 최종본을 1차와 **같은 한 겹 자리**에 앉힌다.

★ 판별은 **엔진의 함수를 그대로 쓴다** — 다시 만들지 않는다 (공통 규칙 6).
  `_read_analyzed_result_file` (xlsx 면 raw_voc 시트) · `_validate_analyzed_result_frame`
  (필수 칸 다섯 · 66칸 매칭 수). 우리가 따로 판별하면 대시보드와 기준이 갈린다.

쓰기
    python <이 스킬>/scripts/최종본_앉히기.py <자리> <최종엑셀> [--이름 <폴더이름>]

종료코드
    0  앉혔다        1  막혔다 (무엇이 막혔는지 말한다)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

스킬 = Path(__file__).resolve().parents[1]


def _찾기(이름: str) -> Path:
    """스킬 안 사본 → 플러그인 옆 한 벌 (낱개로 꾸리면 스킬 안에 들어 있다)."""
    for d in (스킬 / 이름, 스킬.parents[1] / 이름):
        if d.is_dir():
            return d
    return 스킬.parents[1] / 이름


def _엔진것_불러오기(엔진자리: Path):
    """엔진의 판별 함수를 불러온다. 못 불러오면 **왜 못 불렀는지** 말하고 멈춘다."""
    if str(엔진자리) not in sys.path:
        sys.path.insert(0, str(엔진자리))
    try:
        from src.dashboard60.analysis_runner import (          # noqa: PLC0415
            _read_analyzed_result_file, _validate_analyzed_result_frame)
        from src.voc_rebuild.schema import TARGET_COLUMNS      # noqa: PLC0415
    except ImportError as e:
        print("  ✗ 엔진의 판별 함수를 못 불렀습니다 — %s" % e)
        print("     이 도구는 대시보드와 **같은 기준**으로 판별합니다 (따로 만들지 않습니다).")
        print("     대시보드를 띄우려면 streamlit · pandas · openpyxl 이 있어야 합니다:")
        print("       python -m pip install streamlit pandas openpyxl")
        return None
    return _read_analyzed_result_file, _validate_analyzed_result_frame, TARGET_COLUMNS


def 앉히기(자리: Path, 최종: Path, 이름: str = "") -> int:
    if not 최종.is_file():
        print("  ✗ 최종 산출물을 못 찾았습니다 — %s" % 최종)
        print("     (「못 찾음」 은 통과가 아닙니다 — 빈 화면을 띄우지 않습니다)")
        return 1
    엔진자리 = 자리 / "engine"
    if not (엔진자리 / "src" / "dashboard60").is_dir():
        print("  ✗ 자리가 아직 안 차려졌습니다 — %s" % 엔진자리)
        print("     먼저 대시보드_띄우기.py 를 돌리면 자리를 차립니다.")
        return 1
    것 = _엔진것_불러오기(엔진자리)
    if 것 is None:
        return 1
    읽기, 보기, 목표칸 = 것

    try:
        표 = 읽기(최종)
    except Exception as e:                                     # noqa: BLE001 — 엔진이 내는 말을 그대로 전한다
        print("  ✗ 최종 산출물을 못 읽었습니다 — %s: %s" % (type(e).__name__, e))
        return 1
    됐나, 말 = 보기(표)
    if not 됐나:
        print("  ✗ 분석 완료본으로 보기 어렵습니다 — %s" % 말)
        print("     (대시보드와 같은 기준입니다. 1차 66칸을 거친 파일이어야 합니다)")
        return 1

    # ★ 빈 칸을 채우고 **남는 칸은 뒤에 붙인다** — 업로드 패널이 하는 것과 같은 순서다.
    #   최종본은 89칸(1차 66 + 2·3차가 더한 것)이라 남는 칸이 있다. 버리지 않는다.
    for 칸 in 목표칸:
        if 칸 not in 표.columns:
            표[칸] = ""
    남는칸 = [c for c in 표.columns if c not in 목표칸]
    이름 = 이름 or (최종.stem + "_최종")
    받을곳 = 엔진자리 / "outputs" / "voc_dashboard_60" / 이름
    받을곳.mkdir(parents=True, exist_ok=True)
    자료 = 받을곳 / "voc_dashboard_dataset.csv"
    표[[*목표칸, *남는칸]].to_csv(자료, index=False, encoding="utf-8-sig")

    이제 = datetime.now(timezone.utc).isoformat()
    (받을곳 / "metadata.json").write_text(json.dumps({
        "schema_version": "voc-final-after-4th",
        "parser_version": "showing-voc-dashboard/최종본_앉히기",
        "data_source": "showing_voc_dashboard_final_bundle",
        "created_at": 이제,
        "output_rows": int(len(표)),
        "source_filename": 최종.name,
        "input": {"final_bundle": str(최종)},
        "주석": ("4차까지 거친 최종본이다. 대시보드가 latest_dataset 으로 스스로 찾는 **한 겹** 자리에 두었다 — "
               "사람이 「결과 파일 올려서 보기」 에서 두 번 누르지 않아도 된다."),
    }, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    print("  · 앉혔습니다 — %s" % 자료)
    print("    %d행 · 칸 %d (목표 %d + 더한 것 %d)" % (len(표), len(목표칸) + len(남는칸), len(목표칸), len(남는칸)))
    print("    대시보드는 이 자리를 **스스로 찾습니다** (가장 새 것부터).")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    인자 = sys.argv[1:]
    # ★ 2026-10-08 — 띄우개에 `--help` 를 줬더니 그것을 **자리 이름으로 보고** 폴더를 만들었다.
    #   같은 일이 나지 않게 도움말을 먼저 가린다.
    if not 인자 or 인자[0] in ("-h", "--help", "/?"):
        print(__doc__)
        return 0 if 인자 else 1
    이름 = ""
    if "--이름" in 인자:
        i = 인자.index("--이름")
        이름 = 인자[i + 1] if len(인자) > i + 1 else ""
        인자 = 인자[:i] + 인자[i + 2:]
    if len(인자) < 2:
        print("  ✗ 자리와 최종 산출물을 둘 다 주십시오.")
        print(__doc__)
        return 1
    return 앉히기(Path(인자[0]).resolve(), Path(인자[1]).resolve(), 이름)


if __name__ == "__main__":
    sys.exit(main())
