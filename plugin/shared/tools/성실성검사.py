# -*- coding: utf-8 -*-
"""판독이 「실제로 원문을 읽고 한 것인지」를 회차끼리 견주어 본다.

★ 왜 있는가 (sky 2026-08-22)
  「2차판단 3차감독을 PoC 결과물처럼 정확히 잘 돌아가도록」

  로니 판독에서 한 판독자가 53회차 중 **44회차를 0초에** 채웠다.
  그런데 `check_submission.py` 는 전 회차를 「반려 0」 으로 통과시켰다.
  게이트가 있었는데 못 걸렀다 — **형식만 보고 성실성은 안 봤기 때문이다.**

  pilot(14회차)에서는 안 드러났다. 규모가 4배가 되자 드러났다.
  긴 작업은 뒤로 갈수록 얕아진다. 그것을 **자동으로** 잡아야 한다.

★ 무엇을 보나 — 회차끼리 견준다
  판독자 한 사람의 회차들은 서로 비슷해야 한다. 같은 사람이
  같은 기준으로 같은 종류의 데이터를 보기 때문이다.
  어떤 회차만 유독 다르면, 그 회차는 다르게 만들어진 것이다.

    ① 시각        시작과 종료가 같은 초인가 (0초 판독)
    ② 채움        rootcause 를 채운 비율이 다른 회차와 크게 다른가
    ③ 손댄 양     회차당 finding 수가 유독 적거나 많은가
    ④ 라벨 다양도  라벨 종수가 유독 적은가
    ⑤ 사유        판정 칸의 사유가 몇 가지 문장뿐인가 (규칙 스크립트 판정 — 2026-11-10)
    ⑥ 통째 인용    근거가 조각 본문을 통째로 붙인 것인가

  ★ 하나만 튀면 알림, 둘 이상 튀면 반려다.
    한 가지 잣대로 사람을 몰아붙이지 않는다 (오탐도 사고다).

쓰기
    python 성실성검사.py                    회차 파일을 스스로 찾는다
    python 성실성검사.py <판정.md> ...       고른 것만

이상이 있으면 종료코드 1.
"""

from __future__ import annotations

import glob
import os
import re
import statistics
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent if _HERE.name in ("스크립트", "scripts") else _HERE

시각무늬 = re.compile(r"- 시작: (\S+ \S+).*?\n- 종료: (\S+ \S+)", re.S)
필드무늬 = re.compile(r'"field"')
원인무늬 = re.compile(r'"field"\s*:\s*"rootcause_cause"\s*,\s*\n\s*"current"\s*:\s*"[^"]*"\s*,\s*\n\s*"proposed"\s*:\s*"([^"]*)"')
라벨무늬 = re.compile(r'"field"\s*:\s*"topic"\s*,\s*\n\s*"current"\s*:\s*"[^"]*"\s*,\s*\n\s*"proposed"\s*:\s*"([^"]+)"')
# ★ 근거(quote)는 원문에서 따온 말이다. 행마다 달라야 정상이다 (2026-08-23).
#   같은 말을 돌려 쓰면 원문을 안 읽고 틀로 찍은 것이다.
근거무늬 = re.compile(r'"quote"\s*:\s*"([^"]{4,})"')

# ★ 판정 칸의 사유(reason)도 행마다 달라야 정상이다 (sky 2026-11-10).
#   실측 판(LG 로봇청소기)에서 한 판독자가 **규칙 스크립트로** 판정했다 —
#   판정 칸 730줄의 사유가 9가지 문장뿐이었고 (회차별 고유율 6.7~9.8%),
#   근거(quote)는 조각 본문을 통째로 붙여 「근거 돌려 씀」 검사를 피해 갔다.
#   그런데 이 검사는 통과시켰다. 원문을 읽은 판독자는 같은 판에서 47~75% 였다.
#   근거 칸 · 본문 · 요약 글은 뺀다 — 「라벨을 바꿨으니 근거도 바꾼다」 는 같은 말이 정상이다.
사유뺄칸 = {"atomic_voc", "voc_cleaned", "atomic_voc_summary", "tee_summary", "rootcause_summary"}
사유_최소줄 = 30        # 판정 칸 사유가 이보다 적으면 보지 않는다 (작은 회차의 헛경보 막기)
사유_고유_하한 = 0.20   # 실측 — 읽은 판독자 47~75% · 규칙 스크립트 6.7~9.8%
통째_상한 = 0.60        # 근거가 조각 본문 통째인 비율 — 실측 읽은 판독자 2~12% · 규칙 스크립트 42~90%


def 판정행들(글: str) -> list[dict]:
    """판정 파일에서 행(dict)을 꺼낸다 — ```json 배열과 한 줄 JSON 둘 다 읽는다."""
    import json as _json
    행 = []
    for m in re.finditer(r"```json\s*\n(.*?)\n```", 글, re.S):
        try:
            v = _json.loads(m.group(1))
        except ValueError:
            continue
        행 += v if isinstance(v, list) else [v]
    for 줄 in 글.splitlines():
        줄 = 줄.strip()
        if 줄.startswith("{") and '"findings"' in 줄:
            try:
                행.append(_json.loads(줄))
            except ValueError:
                pass
    return [r for r in 행 if isinstance(r, dict)]


def 사유재기(글: str) -> dict:
    사유 = []
    인용 = 통째 = 0
    for r in 판정행들(글):
        본 = str(r.get("atomic_voc") or "").strip()
        for x in r.get("findings") or []:
            if not isinstance(x, dict):
                continue
            칸 = str(x.get("field") or "")
            q = str(x.get("quote") or "").strip()
            if q and len(본) >= 20:
                인용 += 1
                통째 += q == 본
            if 칸.endswith("_evidence") or 칸 in 사유뺄칸 or 칸.startswith("structure"):
                continue
            사유.append(str(x.get("reason") or "").strip())
    return {"사유": len(사유), "사유가짓": len(set(사유)),
            "최다사유": max((사유.count(s) for s in set(사유)), default=0),
            "인용": 인용, "통째": 통째}


def 회차재기(길: Path) -> dict:
    글 = 길.read_text(encoding="utf-8", errors="replace")
    # ★ 판독자가 적은 시각은 못 믿는다 (2026-08-23).
    #   `시작 07:20:27 → 종료 07:20:28` 처럼 1초로 적어도 통과했다.
    #   파일이 실제로 쓰인 시각은 못 속인다.
    쓰인때 = 길.stat().st_mtime
    m = 시각무늬.search(글)
    원인 = 원인무늬.findall(글)
    채운것 = [x for x in 원인 if x and x.upper() != "N/A"]
    라벨 = 라벨무늬.findall(글)
    근거 = 근거무늬.findall(글)
    걸린분 = None
    if m:
        try:
            from datetime import datetime as _dt
            _a = _dt.strptime(m.group(1)[:19], "%Y-%m-%d %H:%M:%S")
            _b = _dt.strptime(m.group(2)[:19], "%Y-%m-%d %H:%M:%S")
            걸린분 = (_b - _a).total_seconds() / 60
        except Exception:
            걸린분 = None
    return {
        "이름": 길.stem,
        "0초": bool(m) and m.group(1)[:19] == m.group(2)[:19],
        "시각있음": bool(m),
        "걸린분": 걸린분,
        "finding": len(필드무늬.findall(글)),
        "원인": len(원인),
        "원인채움": len(채운것),
        "라벨종수": len(set(라벨)),
        "분리": len(re.findall(r"structure\.split", 글)),
        "제외": int((re.search(r"제외\s+(\d+)", 글) or [0, 0])[1] or 0),
        "대상": int((re.search(r"대상\s+(\d+)\s*행", 글) or [0, 0])[1] or 0),
        "근거": len(근거),
        "근거고유율": (len(set(근거)) / len(근거)) if 근거 else None,
        "쓰인때": 쓰인때,
        **사유재기(글),
    }


def 튀는가(값: float, 무리: list[float], 아래로만: bool = True) -> bool:
    """무리에서 크게 벗어나는가. 중앙값의 절반 아래면 튄다고 본다."""

    if len(무리) < 4:
        return False
    중앙 = statistics.median(무리)
    if 중앙 <= 0:
        return False
    if 아래로만:
        return 값 < 중앙 * 0.4
    return 값 < 중앙 * 0.4 or 값 > 중앙 * 2.5



def 감독자_얕아짐(파일: list) -> list[str]:
    """3차 감독이 뒤로 갈수록 얕아졌는지 본다.

    ★ 반려하지 않는다 — 알림이다.
      LLM 에게 시간은 사람만큼 곧은 신호가 아니다. 숫자만 정확히 내민다.
      사람이 보고 판단한다 (오탐도 사고다).
    """
    import datetime as _dt
    import json as _json
    import re as _re

    잰것 = []
    for p in sorted(파일):
        if "감독결과_" not in p.name:
            continue
        글2 = p.read_text(encoding="utf-8", errors="replace")
        m시 = _re.search(r"시작:\s*([\d\-: ]+)", 글2)
        m종 = _re.search(r"종료:\s*([\d\-: ]+)", 글2)
        분 = None
        if m시 and m종:
            try:
                _f = "%Y-%m-%d %H:%M:%S"
                분 = (_dt.datetime.strptime(m종.group(1).strip(), _f)
                     - _dt.datetime.strptime(m시.group(1).strip(), _f)
                     ).total_seconds() / 60
            except ValueError:
                분 = None
        판정 = []
        for 줄2 in 글2.splitlines():
            줄2 = 줄2.strip()
            if 줄2.startswith("{") and '"verdict"' in 줄2:
                try:
                    판정.append(_json.loads(줄2))
                except Exception:                            # noqa: BLE001
                    pass
        C = sum(1 for r in 판정 if r.get("verdict") == "C")
        빈C = sum(1 for r in 판정
                 if r.get("verdict") == "C" and not (r.get("why") or "").strip())
        잰것.append((p.name, 분, len(판정), C, 빈C))

    if len(잰것) < 4:
        return []

    말 = []
    처음 = [x[1] for x in 잰것[:2] if x[1]]
    기준 = sum(처음) / len(처음) if 처음 else None
    for 이름, 분, n, C, 빈C in 잰것:
        까닭 = []
        if 기준 and 분 is not None and 분 < 기준 * 0.4:
            까닭.append("처음 두 회차(%.1f분)의 40%% 미만 — %.1f분" % (기준, 분))
        if n and C == 0:
            까닭.append("제3의 답(C)을 하나도 안 냄")
        if 빈C:
            까닭.append("C 인데 까닭이 없음 %d건" % 빈C)
        if len(까닭) >= 2:
            말.append("%s — %s" % (이름, " · ".join(까닭)))
    return 말


def 적힌시각_누적(파일: list) -> str:
    """적힌 시각이 회차마다 늘어나면(=누적이면) 그렇게 말한다.

    ★ 거짓이 아니라 **읽는 사람이 오해하는** 값이다 (2026-08-23).
      한 판독자는 1.6분, 다른 판독자는 47분 — 나란히 놓으면 판단을 그르친다.
    """
    import datetime as _dt
    import re as _re

    잰것 = []
    for p in sorted(파일):
        글2 = p.read_text(encoding="utf-8", errors="replace")
        m시 = _re.search(r"시작:\s*([\d\-: ]+)", 글2)
        m종 = _re.search(r"종료:\s*([\d\-: ]+)", 글2)
        if not (m시 and m종):
            continue
        try:
            _f = "%Y-%m-%d %H:%M:%S"
            잰것.append((_dt.datetime.strptime(m종.group(1).strip(), _f)
                       - _dt.datetime.strptime(m시.group(1).strip(), _f)
                       ).total_seconds() / 60)
        except ValueError:
            continue

    if len(잰것) < 4:
        return ""
    오름 = sum(1 for a, b in zip(잰것, 잰것[1:]) if b > a)
    if 오름 < len(잰것) - 2:
        return ""
    return ("적힌 시각이 회차마다 늘어납니다 (%.1f분 → %.1f분) — "
            "누적으로 적은 것 같습니다.\n"
            "     한 회차에 든 시간은 위의 「파일이 쓰인 간격」 을 보십시오."
            % (잰것[0], 잰것[-1]))

def main() -> int:
    골라진 = [a for a in sys.argv[1:] if not a.startswith("--")]
    if 골라진:
        파일 = [Path(p) for p in 골라진 if Path(p).exists()]
    else:
        # ★ 3차 감독 결과도 본다 (2026-08-23).
        #   `판독결과_full_*` 만 보다가 3차에서는 아무것도 못 찾았다.
        #   2차에서 얕은 판독을 잡아낸 것이 이 전체 검사였다 — 3차에도 있어야 한다.
        _바탕 = ROOT / "_판독패키지" / "_결과"
        파일 = [Path(p) for 무늬 in ("판독결과_full_*.md", "감독결과_*.md")
              for p in sorted(glob.glob(str(_바탕 / 무늬)))]

    if not 파일:
        print("판정 파일을 못 찾았습니다.")
        print("  찾은 자리: %s" % (ROOT / "_판독패키지" / "_결과"))
        print("  찾는 이름: 판독결과_full_*.md · 감독결과_*.md")
        return 1

    # ★ 인자 없이 부르면 폴더 전체를 본다 (sky 2026-08-22).
    #   그 사실을 밝히지 않으면, 아직 안 고친 옛 회차가 반려로 나올 때
    #   판독자가 「내가 방금 한 것이 잘못됐다」 고 읽고 멈춘다. 실제로 그랬다.
    if not 골라진:
        print("※ 인자를 안 주셔서 **폴더에 있는 회차 전부**를 봅니다.")
        print("   아직 다시 하지 않은 회차가 있으면 그것도 반려로 나옵니다.")
        print("   방금 한 회차만 보시려면 그 파일을 인자로 주십시오 —")
        print("     python 성실성검사.py \"<판정 파일>\"")
        print()

    # 판독자별로 나눈다 — 대소문자를 가리지 않는다
    묶음: dict[str, list[Path]] = {}
    for 길 in 파일:
        조각 = 길.stem.split("_")
        이름 = 조각[-1].lower() if len(조각) >= 4 else "알수없음"
        묶음.setdefault(이름, []).append(길)

    나쁨 = 0
    판박이 = 0
    for 판독자, 파일들 in sorted(묶음.items()):
        잰것 = [회차재기(p) for p in sorted(파일들)]
        print("=" * 74)
        print("  %s — %d회차" % (판독자, len(잰것)))
        print("=" * 74)

        findings = [r["finding"] for r in 잰것]
        채움률 = [(r["원인채움"] / r["원인"]) if r["원인"] else -1 for r in 잰것]
        성한채움 = [x for x in 채움률 if x >= 0]
        라벨들 = [r["라벨종수"] for r in 잰것]

        # ★ 0초는 견줄 것이 아니다 (sky 2026-08-22).
        #   처음엔 「회차끼리 견주어 튀는 것」 만 잡게 했더니, 53회차 중
        #   44회차가 0초일 때 **그 0초가 기준이 되어** 안 걸렸다.
        #   다수결로는 못 잡는다. 사람이 원문 120행을 읽고 판정하는 데
        #   0초는 있을 수 없다 — 이것은 그 자체로 반려다.
        의심 = []
        for r, f, c in zip(잰것, findings, 채움률):
            까닭 = []
            if r["시각있음"] and r["0초"]:
                까닭.append("★시작=종료(0초)")
            if 튀는가(f, findings):
                까닭.append("finding 유독 적음(%d)" % f)
            if c >= 0 and 성한채움 and 튀는가(c, 성한채움):
                까닭.append("원인 채운 비율 낮음(%.0f%%)" % (100 * c))
            # ★ 제외가 많은 회차는 라벨이 적은 것이 당연하다 (2026-08-23).
            #   실측 — full_51 은 120행 중 116행이 제외였다 (딴 영상 댓글).
            #   분석 대상이 4행인데 라벨 4종이면 오히려 다양한 것이다.
            #   그걸 「얕게 함」 으로 보고 두 번이나 다시 하게 만들었다.
            분석대상 = max((r.get("대상") or 0) - (r.get("제외") or 0), 0)
            if 분석대상 >= 20 and 튀는가(r["라벨종수"], 라벨들):
                까닭.append("라벨 종수 적음(%d, 분석대상 %d행)"
                           % (r["라벨종수"], 분석대상))

            # ★★ 여러 신호가 **함께** 주저앉으면 반려한다 (2026-08-23).
            #   시간 하나로는 못 가른다 — 2분 58초인데 제대로 한 회차가 있었고
            #   2분 09초인데 얕은 회차가 있었다. 갈린 것은 「알맹이」 였다.
            #   실측 — 제대로 한 구간 분리 105·원인채움 252·근거고유 19.6%
            #          얕은 구간   분리   0·원인채움   0·근거고유  8.5%
            얕음 = []
            # 판독자가 적은 시각 — 1분 미만이면 있을 수 없다
            #   (0초만 잡다가 1초짜리를 놓쳤다. 2026-08-23)
            if r["걸린분"] is not None and r["걸린분"] < 1:
                얕음.append("★적힌 시각이 1분 미만(%.0f초)" % (60 * r["걸린분"]))
            elif r["걸린분"] is not None and r["걸린분"] < 3:
                얕음.append("3분 미만(%.1f분)" % r["걸린분"])
            if r["원인"] and r["원인채움"] == 0 and 분석대상 >= 20:
                얕음.append("원인을 하나도 안 채움")
            if r["근거고유율"] is not None and r["근거고유율"] < 0.30:
                얕음.append("근거를 돌려 씀(고유 %.0f%%)" % (100 * r["근거고유율"]))
            # ★ 분리 판정이 있으면 얕게 한 것이 아니다 (2026-08-23).
            #   분리는 「이 댓글에 주제가 둘이다」 를 알아본 것이라
            #   원문을 읽어야만 나온다. 틀로는 못 찍는다.
            #   실제로 겪었다 — full_09 는 2분 58초에 분리 17건이었는데
            #   시간과 근거 고유율만 보고 반려했다. 헛경보다.
            if r.get("분리", 0) > 0:
                얕음 = []

            if len(얕음) >= 2:
                까닭.append("★얕게 함 — " + " · ".join(얕음))

            # ★ 사유가 판에 박힘 — 그 하나로 반려다 (sky 2026-11-10).
            #   분리가 있어도 봐준다 — 규칙 스크립트도 분리 줄을 찍을 수 있다.
            if r["사유"] >= 사유_최소줄 and r["사유가짓"] / r["사유"] < 사유_고유_하한:
                까닭.append("★사유가 판에 박힘 — 판정 %d줄에 사유 %d가지(%.0f%%) · "
                           "한 문장이 %d줄. 원문을 읽지 않고 규칙으로 찍은 것으로 보입니다"
                           % (r["사유"], r["사유가짓"], 100 * r["사유가짓"] / r["사유"],
                              r["최다사유"]))
            if r["인용"] >= 사유_최소줄 and r["통째"] / r["인용"] > 통째_상한:
                까닭.append("근거가 조각 본문 통째(%d/%d)" % (r["통째"], r["인용"]))

            if 까닭:
                의심.append((r["이름"], 까닭))

        # ★ 로 시작하는 까닭은 그 하나만으로 반려다. 나머지는 둘 이상 모여야 한다
        반려 = [(n, k) for n, k in 의심
                if any(x.startswith("★") for x in k) or len(k) >= 2]
        알림 = [(n, k) for n, k in 의심 if (n, k) not in 반려]

        # ★ 파일이 쓰인 간격 — 판독자가 못 속이는 값
        때들 = sorted(r["쓰인때"] for r in 잰것 if r.get("쓰인때"))
        간격 = [(때들[i + 1] - 때들[i]) / 60 for i in range(len(때들) - 1)]
        간격 = [x for x in 간격 if 0 < x < 300]
        고유율들 = [r["근거고유율"] for r in 잰것 if r["근거고유율"] is not None]
        분들 = [r["걸린분"] for r in 잰것 if r["걸린분"] is not None]
        print("  회차 평균 — finding %.0f · 라벨 %.0f종%s%s%s"
              % (statistics.mean(findings) if findings else 0,
                 statistics.mean(라벨들) if 라벨들 else 0,
                 " · 원인 채움 %.0f%%" % (100 * statistics.mean(성한채움))
                 if 성한채움 else "",
                 " · 근거 고유 %.0f%%" % (100 * statistics.mean(고유율들))
                 if 고유율들 else "",
                 " · %.1f분" % statistics.mean(분들) if 분들 else ""))
        if 간격:
            print("  파일이 쓰인 간격 %.1f분 (판독자가 못 속이는 값)"
                  % statistics.mean(간격))
        print()

        if 반려:
            나쁨 += len(반려)
            판박이 += sum(1 for _n, k in 반려 if any(x.startswith("★사유가 판에 박힘") for x in k))
            print("  ★ 반려 %d회차 — 다른 회차와 뚜렷이 다릅니다" % len(반려))
            for 이름, 까닭 in 반려[:12]:
                print("     %-30s %s" % (이름[:30], " · ".join(까닭)))
            if len(반려) > 12:
                print("     … 그 밖 %d회차" % (len(반려) - 12))
            print()
        if 알림:
            print("  ! 한 가지만 튄 회차 %d개 (막지는 않습니다)" % len(알림))
            for 이름, 까닭 in 알림[:5]:
                print("     %-30s %s" % (이름[:30], 까닭[0]))
            print()
        if not 의심:
            print("  · 회차끼리 고릅니다. 유독 다른 회차가 없습니다.")
            print()

    print("=" * 74)
    if 나쁨:
        print("  ★ %d회차가 다른 회차와 뚜렷이 다릅니다." % 나쁨)
        print()
        if 판박이:
            print("  ★ 사유가 판에 박힌 회차가 있습니다 — 규칙 스크립트로 판정한 것으로 보입니다.")
            print("    판정 칸(라벨 · 점수 · 제외 · 원인 …)은 원문을 한 줄씩 읽고 정해야 합니다.")
            print("    스크립트는 형식 · 대조 · 세기 같은 기계적 처리와 후보 찾기에만 씁니다.")
            print()
        print("  판독자에게 **그 회차만 다시 하라**고 하십시오.")
        print("  긴 판독은 뒤로 갈수록 얕아집니다 — 판독자를 탓할 일이 아니라,")
        print("  한 번에 너무 많이 시킨 것입니다. 회차를 나눠 여러 번에 걸쳐 하십시오.")
        print("=" * 74)
        return 1
    _누적 = 적힌시각_누적(파일)
    if _누적:
        print("  ! %s" % _누적)
        print()
    _얕 = 감독자_얕아짐(파일)
    if _얕:
        print("  ! 뒤로 갈수록 얕아졌을 수 있습니다 (막지는 않습니다)")
        for _x in _얕:
            print("     %s" % _x)
        print()
    print("  성실성 이상 없음")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
