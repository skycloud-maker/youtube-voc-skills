# -*- coding: utf-8 -*-
"""1차 분석을 돌린다 — 어림(규모·비용)을 먼저 내고, **승인 없이는 돌지 않는다**.

★ 왜 스크립트인가 (2026-10-08 손으로 돌리면서 걸린 자리들)
  ① 설정 자리를 `YT_ANALYSIS_SETTINGS_PATH` 로 주지 않으면 엔진이 기본값(`provider: claude`)으로 돌아가
     댓글마다 호출이 실패하고 OpenAI 로 넘어간다 — 조용히 느려지고 기록이 경고로 뒤덮인다.
  ② `--out-dir` · `--run-id` 가 필수인데 빼먹기 쉽다.
  ③ 돈이 드는 일이라 **규모와 비용을 먼저 말하고 승인을 받아야** 한다 — 글로만 두면 지나친다.
  ④ 끝난 뒤 무엇을 확인해야 하는지가 어디에도 없었다.
  그래서 ①②④ 는 이 스크립트가 하고, ③ 은 `--승인` 없이는 **돌지 않는 것**으로 막는다.

쓰기
    python 1차_돌리기.py --검색어 "LG 로봇청소기" --영상 2 --댓글 10         ← 어림만 내고 멈춘다 (종료 2)
    python 1차_돌리기.py --검색어 "LG 로봇청소기" --영상 2 --댓글 10 --승인   ← 실제로 돌린다
    python 1차_돌리기.py --이름 <run-id> --확인만                            ← 이미 돌린 결과만 확인한다

★ 이 파일은 차린 1차 자리의 맨 위에 놓인다. 그 자리에서 돌린다 (옆에 engine/ 과 결과/ 가 있다).
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

자리 = Path(__file__).resolve().parent
엔진 = 자리 / "engine"
결과뿌리 = 자리 / "결과"
돌리개 = "scripts/run_dashboard60_youtube_collect_and_analyze.py"
설정 = "config/settings.yaml"
키들 = ("YOUTUBE_API_KEY", "OPENAI_API_KEY")

# ★ 어림의 바탕 — 2026-10-08 에 실제로 잰 한 번 (영상 5개 · 영상당 댓글 50개)
잰것 = {"영상": 5, "댓글": 50, "모은댓글": 494, "조각": 504, "분": 63, "달러": 1.0, "할당량": 108}

# ★ 드물게만 차는 칸 — 작은 규모에서는 통째로 비는 것이 **정상**이다 (2026-10-08 에 실제로 세어 정했다).
#   504행 실행에서 scope_exclusion_reason 16행(3.2%) · voc_residual 20행(4.0%) 만 찼고,
#   2판 1차 240행에서도 voc_residual 은 4행(1.7%) 뿐이었다.
#   그래서 62행 시험이 「전부 빈 칸」 으로 걸렸다 — 칸이 빈 것이 아니라 **내 기대가 틀렸다.**
#   이 둘은 조건이 맞는 행이 있을 때만 찬다: 제외된 행 · 조각을 떼고 남은 글이 있는 행.
드물게차는칸 = {
    "scope_exclusion_reason": "제외된 행에만 찬다 (status=scope_excluded)",
    "voc_residual": "조각을 떼고 남은 글이 있을 때만 찬다",
}


def 어림(영상: int, 댓글: int) -> dict:
    """잰 한 번에 비례해 어림한다. **어림이라고 말한다** — 실제 금액은 OpenAI 사용량 화면에서 봐야 한다."""
    몫 = (영상 * 댓글) / (잰것["영상"] * 잰것["댓글"])
    return {"모은댓글": round(잰것["모은댓글"] * 몫), "조각": round(잰것["조각"] * 몫),
            "분": max(2, round(잰것["분"] * 몫)), "달러": round(잰것["달러"] * 몫, 2),
            "할당량": 100 + round((잰것["할당량"] - 100) * 몫)}


def 키검사() -> list[str]:
    """없는 키 이름만 돌려준다 — **값은 읽지 않는다.**"""
    return [k for k in 키들 if not os.environ.get(k)]


def 확인(결과: Path) -> int:
    """돌린 결과를 확인한다. 하나라도 어긋나면 1, 볼 것을 못 찾으면 2."""
    csv자리 = 결과 / "voc_dashboard_dataset.csv"
    if not csv자리.is_file():
        print("  ✗ 못 찾음 — %s (돌지 않았거나 중간에 멈췄습니다. 통과가 아닙니다)" % csv자리)
        return 2
    sys.path.insert(0, str(엔진))
    from src.voc_rebuild import TARGET_COLUMNS                      # noqa: PLC0415
    줄들 = list(csv.DictReader(io.StringIO(csv자리.read_bytes().decode("utf-8-sig"))))
    칸 = list(줄들[0]) if 줄들 else []
    빠짐 = [c for c in TARGET_COLUMNS if c not in 칸]
    덧붙임 = [c for c in 칸 if c not in TARGET_COLUMNS]
    전부빈 = [c for c in 칸 if c not in 드물게차는칸 and all(not (r.get(c) or "") for r in 줄들)]
    드문것이_빈것 = [c for c in 드물게차는칸 if c in 칸 and all(not (r.get(c) or "") for r in 줄들)]
    번들 = 결과 / "voc_dashboard_export_bundle.xlsx"
    영상 = len({r.get("video_id", "") for r in 줄들})
    제외 = sum(1 for r in 줄들 if (r.get("status") or "") == "scope_excluded")
    print("  조각 %d개 · 영상 %d개 · 제외 %d행" % (len(줄들), 영상, 제외))
    print("  칸 %d개 (계약 %d) · 빠진 칸 %s · 덧붙은 칸 %s · 전부 빈 칸 %s"
          % (len(칸), len(TARGET_COLUMNS), 빠짐 or "없음", 덧붙임 or "없음", 전부빈 or "없음"))
    for c in 드문것이_빈것:
        # 결함이 아니다 — 작은 규모에서는 조건이 맞는 행이 없을 수 있다. 다만 **말은 한다.**
        print("  · %s 가 통째로 비었습니다 — %s (작은 규모에서는 정상)" % (c, 드물게차는칸[c]))
    print("  번들 엑셀 — %s" % ("있습니다" if 번들.is_file() else "✗ 없습니다"))
    기록 = 결과 / "실행기록.txt"
    경고 = 0
    if 기록.is_file():
        경고 = 기록.read_text(encoding="utf-8", errors="replace").count("Primary(claude) 실패")
        print("  Primary(claude) 실패 경고 — %d건" % 경고)
        if 경고:
            # ★ 크게 실패한다 — 결과 자체는 OpenAI 가 낸 것이어서 쓸 수 있지만, 설정이 안 먹었다는 뜻이다.
            #   `1차_돌리기.py --승인` 으로 돌렸으면 0 이어야 한다 (설정 자리를 자동으로 주므로).
            print("     ✗ 설정(config/settings.yaml)이 안 먹었습니다 — 헛호출이 %d번 났습니다." % 경고)
            print("       이 스크립트로 돌리지 않았거나 YT_ANALYSIS_SETTINGS_PATH 가 빠졌습니다.")
    if 빠짐 or 덧붙임 or 전부빈 or 경고 or not 번들.is_file() or not 줄들:
        print("  ✗ 확인에서 어긋난 것이 있습니다 — 위를 보십시오.")
        return 1
    print("  ✓ 1차 결과가 온전합니다. 2차로 넘기려면 판독 폴더에서:")
    print('      python 스크립트/데이터_넣기.py "%s"' % 번들)
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--검색어", default="")
    p.add_argument("--영상", type=int, default=2)
    p.add_argument("--댓글", type=int, default=10)
    p.add_argument("--이름", default="")
    p.add_argument("--승인", action="store_true")
    p.add_argument("--확인만", action="store_true")
    a = p.parse_args()
    이름 = a.이름 or ("1차_" + datetime.now().strftime("%Y%m%d_%H%M"))
    결과 = 결과뿌리 / 이름

    if a.확인만:
        return 확인(결과)
    if not a.검색어:
        print("  ✗ --검색어 가 필요합니다. 실행조건은 99_1차_실행조건_원문.md 를 읽고 사람에게 받으십시오.")
        return 2
    없는키 = 키검사()
    if 없는키:
        print("  ✗ 환경변수에 키가 없습니다 — %s" % " · ".join(없는키))
        print("     저장소의 tools/키_환경변수에_넣기.ps1 로 넣을 수 있습니다.")
        print("     ★ 환경변수는 **새로 켠 창에만** 들어옵니다 — 넣은 뒤 이 창을 다시 켜야 보입니다.")
        print("     (값은 보지 않습니다. 있는지만 봅니다.)")
        return 2
    e = 어림(a.영상, a.댓글)
    print("  규모 — 검색어 「%s」 · 영상 %d개 · 영상당 댓글 %d개" % (a.검색어, a.영상, a.댓글))
    print("  어림 — 모을 댓글 %d개 → 조각 %d개 · 약 %d분 · 대략 $%.2f · YouTube 할당량 %d / 하루 10,000"
          % (e["모은댓글"], e["조각"], e["분"], e["달러"], e["할당량"]))
    print("  ★ 어림입니다 (2026-10-08 에 잰 한 번에 비례). 실제 금액은 OpenAI 사용량 화면에서 봐야 합니다.")
    if not a.승인:
        print("  ─ 돌리지 않았습니다. 이 숫자를 사람에게 말하고 승인을 받은 뒤 `--승인` 을 붙여 다시 돌리십시오.")
        return 2

    결과.mkdir(parents=True, exist_ok=True)
    기록 = 결과 / "실행기록.txt"
    명령 = [sys.executable, "-B", 돌리개, "--keyword", a.검색어,
          "--max-videos", str(a.영상), "--comments-per-video", str(a.댓글),
          "--out-dir", str(결과), "--run-id", 이름]
    환경 = dict(os.environ, YT_ANALYSIS_SETTINGS_PATH=설정, PYTHONIOENCODING="utf-8",
              PYTHONDONTWRITEBYTECODE="1")
    print("  돌립니다 — 기록은 %s" % 기록)
    with io.open(기록, "w", encoding="utf-8") as f:
        r = subprocess.run(명령, cwd=str(엔진), stdout=f, stderr=subprocess.STDOUT, env=환경)
    print("  엔진 종료코드 %d" % r.returncode)
    if r.returncode:
        print("  ✗ 돌다가 멈췄습니다 — 기록의 끝을 보십시오. 결과를 지어내지 마십시오.")
        return 1
    return 확인(결과)


if __name__ == "__main__":
    sys.exit(main())
