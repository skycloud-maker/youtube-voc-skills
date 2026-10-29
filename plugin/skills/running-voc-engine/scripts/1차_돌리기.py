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
# ★ 결과는 **엔진 본래 자리**에 쓴다 (2026-10-08 섹션 7 ④ 에서 고쳤다).
#   대시보드가 `outputs/voc_dashboard_60/*/voc_dashboard_dataset.csv` 를 스스로 찾아 띄우기 때문이다
#   (`src/dashboard60/data_contract.py:294 latest_dataset`). 전에는 `<자리>/결과/` 에 썼더니
#   1차를 돌려도 대시보드가 「Dataset not found」 로 떴다 — 사람이 손으로 옮겨야 했다.
결과뿌리 = 엔진 / "outputs" / "voc_dashboard_60"
돌리개 = "scripts/run_dashboard60_youtube_collect_and_analyze.py"
설정 = "config/settings.yaml"
키들 = ("YOUTUBE_API_KEY", "OPENAI_API_KEY")

# ── 실행조건 칸 — 원문의 칸을 **엔진 옵션에 그대로** 잇는다 (2026-10-22 재점검) ──────────
#
# ★ 왜 생겼나 (sky 2026-10-22)
#   전에는 네 칸(검색어 · 영상 · 댓글 · 이름)만 받았다. 원문
#   (`99_1차_실행조건_원문.md`)에는 스물두 칸이 있는데 나머지는 **엔진 기본값으로 조용히**
#   떨어졌다. 그래서 국가·언어·게시일·대댓글을 바꿔 돌릴 길이 없었다.
#   sky 가 가른 기준 — 「특정 채널 ID 같이 특정하는 것이나, 분석 최대 행 수 · 묶음 크기
#   등과 같은 분석의 원활을 위해 임의로 1회 분석을 조절하는 용도의 데이터나 분석 모델에
#   따른 변형을 주기 위한 선택은 필수가 아닐 수도 있겠으나 그 외에는 필수」.
#
# 칸 = (이름, 엔진옵션, 기본값, 꼭_묻나, 설명)
#   꼭_묻나 True  — AI 가 **사람에게 반드시 묻는다.** 지어내지 않는다.
#   꼭_묻나 False — 묻지 않고 기본값으로 둔다. 사람이 말하면 그대로 넘긴다.
조건칸 = (
    ("검색어",   "--keyword",                 "",     True,
     "맨 윗줄 키워드. ★ AND 일 때는 **이것으로만 검색**하고 나머지는 글자로 걸러낸다"),
    ("키워드들", "--keywords",                "",     True,
     "여러 줄을 `|` 로 잇는다 (예: 로봇청소기|LG 로봇청소기|로니). 비우면 검색어 하나로 본다"),
    ("결합",     "--keyword-mode",            "OR",   True,
     "OR — 키워드마다 따로 검색해 합친다 (순서 상관없음) · "
     "AND — **맨 윗줄로만 검색**하고 나머지는 그 영상의 제목·설명·채널명·태그에서 글자로 찾는다. "
     "키워드마다 검색해 교집합을 내는 것이 **아니다** — 맨 윗줄이 모수를 정한다. "
     "자세한 기준은 `키워드결합_OR_AND_기준.md` (엔진 코드에서 확인해 적은 것)"),
    ("최소매칭", "--and-min-keyword-matches", "",     False,
     "AND 이고 키워드가 셋 이상일 때만. 비우면 「모든 키워드 포함」"),
    ("시작일",   "--published-after",         "",     True,
     "영상 게시일 범위 시작 (YYYY-MM-DD). 비우면 게시일 제한 없음"),
    ("종료일",   "--published-before",        "",     True,
     "영상 게시일 범위 종료 (YYYY-MM-DD). 비우면 제한 없음"),
    ("국가",     "--region",                  "KR",   True,
     "ISO 3166-1 alpha-2 (KR · US · JP · GB). 검색 관련성에 영향을 주지만 엄격한 국가 필터는 아니다"),
    ("언어",     "--language",                "ko",   True,
     "ISO 639-1 (ko · en · ja). 검색 관련성에 영향을 주지만 댓글 언어를 엄격히 걸러내지는 않는다"),
    ("영상",     "--max-videos",              "2",    True,
     "1~500"),
    ("댓글",     "--comments-per-video",      "10",   True,
     "1~2,000 · **0 = 가능한 모두** (양을 모르니 어림을 낼 수 없다)"),
    ("대댓글",   "--include-replies",         "true", True,
     "true / false. 대시보드 기본값도 true 다"),
    ("채널",     "--channel-id",              "",     False,
     "`UC…` 특정 채널 영상만. 비우면 키워드 검색 전체"),
    ("최대행",   "--limit",                   "",     False,
     "분석 최대 행 수 (비움/0 = 전체, 최대 10,000). ★ 한 번에 처리할 양을 줄여 중간에 끊기는 것을 막는 칸"),
    ("묶음",     "--batch-size",              "5",    False,
     "이 건수마다 **중간 저장**한다. 끊겨도 여기까지는 남는다 (1~50)"),
    ("대기초",   "--timeout-seconds",         "120",  False,
     "한 묶음 최대 대기 시간(초). 넘기면 그 묶음을 실패로 보고 다음으로 넘어간다 (30~300)"),
    ("모델",     "--model",                   "",     False,
     "비워 두면 기본값. 보통 비워 둔다"),
)
꼭묻는칸 = tuple(이름 for 이름, _, _, 꼭, _ in 조건칸 if 꼭)
최댓값 = {"영상": 500, "댓글": 2000, "최대행": 10000, "묶음": 50, "대기초": 300}


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


def _수(값, 기본: int = 0) -> int:
    """글자를 숫자로. 못 읽으면 기본값 — 지어내지 않고 기본이라고 말한다."""
    try:
        return int(str(값).strip())
    except (TypeError, ValueError):
        return 기본


def 어림(영상: int, 댓글: int, 최대행: int = 0) -> dict:
    """잰 한 번에 비례해 어림한다. **어림이라고 말한다** — 실제 금액은 OpenAI 사용량 화면에서 봐야 한다.

    ★ 2026-10-22 재점검에서 두 가지를 셈에 넣었다.
      ① 「댓글 = 0」 은 **가능한 모두 수집**이다. 양을 모르니 숫자로 말하지 않는다
         (`모름: True`). 모르는 것을 어림이라고 말하면 승인이 거짓이 된다.
      ② 「최대행」 을 걸면 분석하는 조각이 거기서 끊긴다 — 시간과 돈도 그만큼이다.
         수집(할당량)은 줄지 않는다. 둘을 갈라 센다.
    """
    if 댓글 <= 0:
        return {"모름": True, "모은댓글": 0, "조각": 0, "분석조각": 0,
                "분": 0, "달러": 0.0, "할당량": 0}
    몫 = (영상 * 댓글) / (잰것["영상"] * 잰것["댓글"])
    조각 = round(잰것["조각"] * 몫)
    분석조각 = min(조각, 최대행) if 최대행 and 최대행 > 0 else 조각
    쪽 = (분석조각 / 잰것["조각"]) if 잰것["조각"] else 0
    return {"모름": False,
            "모은댓글": round(잰것["모은댓글"] * 몫), "조각": 조각, "분석조각": 분석조각,
            "분": max(2, round(잰것["분"] * 쪽)), "달러": round(잰것["달러"] * 쪽, 2),
            "할당량": 100 + round((잰것["할당량"] - 100) * 몫)}


def 키검사() -> list[str]:
    """없는 키 이름만 돌려준다 — **값은 읽지 않는다.**"""
    return [k for k in 키들 if not os.environ.get(k)]


def 영상메타_만들기(결과: Path, 줄들: list[dict]) -> Path | None:
    """판독자가 쓰는 `7_영상메타.csv` 를 **이 판의 영상으로** 만든다.

    ★ 왜 (2026-09-22 섹션 5b 에서 알게 된 것 · 섹션 7 에서 고치기로 했다)
      꾸러미에 들어 있던 `7_영상메타.csv` 는 영상 21개짜리 **옛 판 것**이라, 2판 240행의 영상 18개 중
      16개가 거기에 없었다. 판독자는 `video_id` 로 조인해 제목 · 태그 · 설명 · 채널을 보는데
      (판독 프롬프트 「영상 메타  판독패키지\\7_영상메타.csv  video_id 로 조인」),
      없으면 **제목만 보고 판독**하게 된다. 판마다 1차가 만들어야 한다.

    칸은 옛 파일과 같게 둔다 — video_id · video_title · video_tags · video_description ·
    channel_title · published_at · atomic_rows (그 영상에서 나온 조각 수).
    """
    표 = 결과.parent.parent.parent / "data" / "processed" / 결과.name / "videos_normalized.parquet"
    if not 표.is_file():
        print("  · 영상 표를 못 찾아 7_영상메타.csv 를 만들지 못했습니다 — %s" % 표)
        return None
    import pandas as pd                                           # noqa: PLC0415
    v = pd.read_parquet(표).fillna("")
    셈: dict = {}
    for r in 줄들:
        셈[r.get("video_id", "")] = 셈.get(r.get("video_id", ""), 0) + 1
    낼것 = 결과 / "7_영상메타.csv"
    with io.open(낼것, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "video_title", "video_tags", "video_description",
                    "channel_title", "published_at", "atomic_rows"])
        for _, r in v.iterrows():
            태그 = r["tags"]
            태그 = " ".join(map(str, 태그)) if not isinstance(태그, str) else 태그
            w.writerow([r["video_id"], r["title"], 태그, r["description"],
                        r["channel_title"], r["published_at"], 셈.get(r["video_id"], 0)])
    print("  · 7_영상메타.csv 를 만들었습니다 — 영상 %d개 (판독자가 video_id 로 조인한다)" % len(v))
    return 낼것


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
    메타 = 영상메타_만들기(결과, 줄들)
    # ★ 2026-10-29 — 전에는 「칸 66개 (계약 66)」 만 찍었다. **무엇을 본 것인지 안 찍혀서**
    #   판독자가 번들 엑셀(74칸)을 세고 「74칸인데 계약은 66칸」 이라고 적었다. 둘 다 사실이었다.
    #   칸은 차수마다 늘어난다 — 1차 csv 66(계약) → 번들 74(+파생 8) → 판독자 79(+사이드카 5)
    #   → 최종 89(+2·3차 10). 그래서 **어느 파일의 칸인지**와 번들 쪽 수를 같이 찍는다.
    print("  칸 %d개 (계약 %d) · 빠진 칸 %s · 덧붙은 칸 %s · 전부 빈 칸 %s"
          % (len(칸), len(TARGET_COLUMNS), 빠짐 or "없음", 덧붙임 or "없음", 전부빈 or "없음"))
    print("     ↑ 이 칸 수는 **%s** 의 것입니다 (계약을 재는 자리)" % csv자리.name)
    print("     번들 엑셀 raw_voc 는 이보다 많습니다 — 대시보드가 계산하는 파생 칸이 붙습니다.")
    print("     판독자가 받는 csv 는 거기에 2차가 채울 사이드카까지 붙습니다.")
    print("     **계약은 맨 앞 %d칸**이고, 뒤에 붙는 칸은 계약 밖입니다 —" % len(TARGET_COLUMNS))
    print("     칸 수가 %d개가 아니라고 「계약 위반」 이 아닙니다." % len(TARGET_COLUMNS))
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
    if 빠짐 or 덧붙임 or 전부빈 or 경고 or 메타 is None or not 번들.is_file() or not 줄들:
        print("  ✗ 확인에서 어긋난 것이 있습니다 — 위를 보십시오.")
        return 1
    print("  ✓ 1차 결과가 온전합니다. 2차로 넘기려면 판독 폴더에서:")
    print('      python 스크립트/데이터_넣기.py "%s"' % 번들)
    print("  대시보드는 이 결과를 스스로 찾습니다 (outputs/voc_dashboard_60 아래에 있습니다).")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    p = argparse.ArgumentParser(add_help=True)
    # ★ 깃발을 `조건칸` 에서 만든다 — 칸을 늘릴 때 두 곳을 고치지 않는다 (공통 규칙 6).
    for 칸이름, _옵션, 기본, 꼭, 설명 in 조건칸:
        p.add_argument("--" + 칸이름, default=기본,
                       help=("[꼭 묻는다] " if 꼭 else "[선택] ") + 설명)
    p.add_argument("--이름", default="")
    p.add_argument("--승인", action="store_true")
    p.add_argument("--확인만", action="store_true")
    a = p.parse_args()
    # 최댓값을 넘으면 **돌리지 않는다** — 엔진이 조용히 깎는 것보다 여기서 말하는 쪽이 낫다
    넘은것 = ["%s %s (최대 %d)" % (칸, getattr(a, 칸), 끝)
            for 칸, 끝 in 최댓값.items() if _수(getattr(a, 칸, ""), 0) > 끝]
    if 넘은것:
        print("  ✗ 최댓값을 넘었습니다 — %s" % " · ".join(넘은것))
        print("     최댓값은 99_1차_실행조건_원문.md 의 상수에 있습니다.")
        return 2
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
        # ★ 2026-10-29 — 전에는 「저장소의 tools/키_환경변수에_넣기.ps1」 이라고 찍었다.
        #   그 파일은 **꾸러미에 없다.** 받는 사람은 없는 파일을 찾게 된다.
        #   넣는 명령은 꾸러미 안 `0_빈컴퓨터에서_무엇을_깔까.md` §③ 에 있다.
        print("     넣는 법은 `0_빈컴퓨터에서_무엇을_깔까.md` 의 §③ 에 있습니다"
              " (꾸러미를 푼 폴더 뿌리에 있습니다).")
        print("     ★ 환경변수는 **새로 켠 창에만** 들어옵니다 — 넣은 뒤 이 창을 다시 켜야 보입니다.")
        print("     (값은 보지 않습니다. 있는지만 봅니다.)")
        return 2
    영상수, 댓글수, 최대행 = _수(a.영상, 2), _수(a.댓글, 10), _수(a.최대행, 0)
    e = 어림(영상수, 댓글수, 최대행)
    print("  규모 — 검색어 「%s」 · 영상 %d개 · 영상당 댓글 %s"
          % (a.검색어, 영상수, "가능한 모두" if 댓글수 <= 0 else "%d건" % 댓글수))
    print("  조건 — %s" % " · ".join(
        "%s %s" % (칸, getattr(a, 칸) or "(없음)")
        for 칸, _o, _기, _꼭, _설 in 조건칸 if 칸 not in ("검색어", "영상", "댓글")))
    if e["모름"]:
        print("  ★ 어림을 낼 수 없습니다 — 「댓글 = 0(가능한 모두)」 은 양을 모릅니다.")
        print("     돈이 얼마나 들지 모르는 채로 승인받지 않습니다. 댓글 수를 정해 주시거나,")
        print("     「최대행」 으로 분석할 양을 묶어 주십시오.")
        if not a.승인:
            return 2
    else:
        꼬리 = ("" if e["분석조각"] == e["조각"]
              else " (그중 **%d개만 분석** — 최대행 %d)" % (e["분석조각"], 최대행))
        print("  어림 — 모을 댓글 %d개 → 조각 %d개%s · 약 %d분 · 대략 $%.2f · YouTube 할당량 %d / 하루 10,000"
              % (e["모은댓글"], e["조각"], 꼬리, e["분"], e["달러"], e["할당량"]))
        print("  ★ 어림입니다 (2026-10-08 에 잰 한 번에 비례). 실제 금액은 OpenAI 사용량 화면에서 봐야 합니다.")
    if not a.승인:
        print("  ─ 돌리지 않았습니다. 이 숫자를 사람에게 말하고 승인을 받은 뒤 `--승인` 을 붙여 다시 돌리십시오.")
        return 2

    결과.mkdir(parents=True, exist_ok=True)
    기록 = 결과 / "실행기록.txt"
    # ★ 2026-10-22 — 전에는 네 칸만 넘겼다. 나머지는 엔진 기본값으로 **조용히** 떨어졌다.
    #   이제 `조건칸` 을 그대로 잇는다. 빈 칸은 넘기지 않아 엔진 기본값이 그대로 산다.
    명령 = [sys.executable, "-B", 돌리개, "--out-dir", str(결과), "--run-id", 이름]
    for 칸이름, 옵션, _기본, _꼭, _설명 in 조건칸:
        값 = str(getattr(a, 칸이름, "") or "").strip()
        if 값 == "":
            continue
        if 칸이름 == "키워드들":
            쪼갠것 = [x.strip() for x in 값.replace(";", "|").replace(chr(10), "|").split("|")
                   if x.strip()]
            if 쪼갠것:
                명령 += [옵션] + 쪼갠것
        else:
            명령 += [옵션, 값]
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
