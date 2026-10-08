# -*- coding: utf-8 -*-
"""최종 산출물 엑셀에서 **사내용 HTML 보고서 한 장**을 만든다 — 섹션 8.

★ 따르는 규율 (원문: `공통/65_개인정보_처리_기준_및_제출문안.md` · `공통/52_AX_FLEX_과제_제출본.md`)
  ① **원문 전량(`raw_voc`)과 식별자는 넣지 않는다** — 「제출에 필요하지 않고 위험은 가장 큼」(65 §2-2).
  ② **인용문은 남긴다.** 판정의 근거이고, 빼면 「왜 그렇게 판단했나」 를 보일 수 없다(65 §2-3).
     다만 사용자명 · 링크 · 이메일은 치운다(65 §2-1 — 링크는 `[링크 지움]` 으로).
  ③ **「했다」 가 아니라 「확인했다」** (65 §3) — 치운 뒤 **다시 훑어** 링크 0 · 이메일 0 · 사용자명 0 임을
     보고서 자신이 적는다. 0 이 아니면 보고서를 내지 않는다.
  ④ **숫자마다 출처를 붙인다** (sky 2026-10-08 「넣는다 — 다만 출처를 같이」).
     65 §4-4 가 겪은 것 — 함께 낸 자료끼리 숫자가 어긋나면 개인정보보다 **신뢰**가 먼저 깨진다.
     그래서 모든 수치 옆에 「어느 시트의 몇 행에서 나왔는지」 를 적는다.

★ 집계 기준은 **전량**이다. 대시보드는 「판정 충족도 Very High·High」 가 기본이라 화면 숫자가 더 적다 —
  그 차이를 보고서가 **글로 적는다**(65 §4-4 가 겪은 어긋남을 되풀이하지 않으려고).

쓰기
    python 보고서_만들기.py <최종데이터.xlsx> [낼자리.html]
    python 보고서_만들기.py <최종데이터.xlsx> --확인만      무엇을 담을지만 보여 준다
"""
from __future__ import annotations

import html
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ★ 넣지 않는 시트 — 65 §2-2 「통째로 뺀 시트」
안넣는시트 = {"raw_voc": "원문 전량 덤프 — 제출에 필요하지 않고 위험은 가장 큼",
          "inquiry_rows": "raw_voc 의 부분집합이라 중복"}
# 보고서에 쓰는 시트
쓰는시트 = ("★PL Issue", "improvement_priority", "video_summary", "★사람이볼목록", "0_차례")

_링크 = re.compile(r"https?://\S+")
_이메일 = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_사용자명 = re.compile(r"@[\w가-힣._-]{2,}")


def 치우기(글: str) -> tuple[str, Counter]:
    """링크 · 이메일 · 사용자명을 치운다. **몇 건을 치웠는지 같이 돌려준다** (65 §3 「확인했다」)."""
    셈 = Counter()
    if not 글:
        return "", 셈
    셈["이메일"] = len(_이메일.findall(글))
    글 = _이메일.sub("[메일 지움]", 글)
    셈["링크"] = len(_링크.findall(글))
    글 = _링크.sub("[링크 지움]", 글)
    셈["사용자명"] = len(_사용자명.findall(글))
    글 = _사용자명.sub("[이름 지움]", 글)
    return 글, 셈


def 남았나(글: str) -> Counter:
    """치운 뒤 **다시 훑는다** — 0 이어야 한다."""
    return Counter({"링크": len(_링크.findall(글)), "이메일": len(_이메일.findall(글)),
                    "사용자명": len(_사용자명.findall(글))})


def 읽기(엑셀: Path) -> dict:
    import openpyxl                                              # noqa: PLC0415
    wb = openpyxl.load_workbook(엑셀, data_only=True, read_only=True)
    표 = {}
    for 이름 in wb.sheetnames:
        if 이름 in 안넣는시트:
            continue
        ws = wb[이름]
        줄 = [[("" if v is None else str(v)) for v in r] for r in ws.iter_rows(values_only=True)]
        줄 = [r for r in 줄 if any(x for x in r)]
        if 줄:
            표[이름] = {"머리": 줄[0], "행": 줄[1:]}
    wb.close()
    return 표


def _h(x) -> str:
    return html.escape(str(x), quote=True)


def _표만들기(머리: list, 행: list, 칸: list[str], 몇개: int = 12) -> str:
    """고른 칸만 간추려 표로. 칸 이름을 못 찾으면 그대로 알린다 (못 찾음 ≠ 없음)."""
    자리 = [머리.index(c) for c in 칸 if c in 머리]
    없는칸 = [c for c in 칸 if c not in 머리]
    if 없는칸:
        return '<p class="빠짐">✗ 이 표의 칸을 못 찾았습니다 — %s (있는 칸: %s)</p>' % (
            _h(" · ".join(없는칸)), _h(" · ".join(머리[:10])))
    쪽 = ["<table><thead><tr>" + "".join("<th>%s</th>" % _h(머리[i]) for i in 자리) + "</tr></thead><tbody>"]
    for r in 행[:몇개]:
        쪽.append("<tr>" + "".join("<td>%s</td>" % _h(r[i] if i < len(r) else "") for i in 자리) + "</tr>")
    쪽.append("</tbody></table>")
    if len(행) > 몇개:
        쪽.append('<p class="더">… 모두 %d행 (여기엔 %d행만 — 전부는 최종 엑셀에)</p>' % (len(행), 몇개))
    return "\n".join(쪽)


_CSS = """
body{font-family:'Malgun Gothic',system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1.2rem;
     line-height:1.65;color:#1a1a1a}
h1{border-bottom:3px solid #333;padding-bottom:.4rem}
h2{margin-top:2.4rem;border-left:5px solid #333;padding-left:.6rem}
table{border-collapse:collapse;width:100%;margin:.6rem 0;font-size:.92rem}
th,td{border:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}
th{background:#f2f2f2}
.출처{color:#555;font-size:.85rem;margin:.2rem 0 1rem}
.더{color:#777;font-size:.85rem}
.빠짐{color:#b00;font-weight:bold}
.확인{background:#f6f6f6;border:1px solid #ddd;padding:.7rem 1rem;margin:1rem 0}
.머리말{color:#444;background:#fafafa;border:1px solid #e0e0e0;padding:.8rem 1rem}
"""


def 만들기(엑셀: Path, 낼자리: Path) -> dict:
    """보고서를 만든다. 돌려주는 것 — 담은 것 · 치운 건수 · 다시 훑은 결과."""
    표 = 읽기(엑셀)
    치움 = Counter()
    쪽 = ['<!doctype html><html lang="ko"><meta charset="utf-8">',
         "<title>VoC 분석 보고서 (사내용)</title><style>%s</style>" % _CSS,
         "<h1>YouTube 고객 VoC 분석 보고서 <span style='font-size:.6em;color:#666'>(사내용)</span></h1>",
         '<div class="머리말">',
         "<p><b>원본</b> %s · <b>만든 날</b> %s</p>" % (_h(엑셀.name), datetime.now().strftime("%Y-%m-%d %H:%M")),
         "<p><b>숫자 읽는 법</b> — 이 보고서의 수치는 모두 <b>전량 기준</b>입니다. "
         "대시보드 화면은 「판정 충족도 Very High·High」 가 기본이라 <b>화면 건수가 더 적습니다</b>. "
         "둘은 다른 기준이지 틀린 것이 아닙니다. 표마다 어느 시트에서 나왔는지 적었습니다.</p>",
         "<p><b>안 담은 것</b> — " + " · ".join("<code>%s</code>(%s)" % (_h(k), _h(v))
                                            for k, v in 안넣는시트.items()) + "</p></div>"]

    담음 = []
    차례 = 표.get("0_차례")
    if 차례:
        쪽.append("<h2>이 판에 무엇이 있었나</h2>")
        쪽.append(_표만들기(차례["머리"], 차례["행"], [c for c in ("시트 이름", "무엇을 보는 자리인가", "누가 보나", "행")
                                              if c in 차례["머리"]], 몇개=20))
        쪽.append('<p class="출처">출처 — 최종 엑셀 [0_차례] %d행</p>' % len(차례["행"]))
        담음.append("0_차례")

    pl = 표.get("★PL Issue")
    if pl:
        갈래 = Counter(r[pl["머리"].index("갈래")] for r in pl["행"] if "갈래" in pl["머리"])
        쪽.append("<h2>★ PL 이슈 — 건수와 무관하게 전량</h2>")
        쪽.append("<p>모두 <b>%d행</b>%s</p>" % (len(pl["행"]),
                  (" (갈래별 " + " · ".join("%s %d" % (k, v) for k, v in 갈래.most_common()) + ")") if 갈래 else ""))
        행 = []
        for r in pl["행"]:
            r = list(r)
            for i, v in enumerate(r):
                v2, c = 치우기(v)
                r[i] = v2
                치움 += c
            행.append(r)
        쪽.append(_표만들기(pl["머리"], 행, [c for c in ("갈래", "라벨", "제품군", "무슨 말인가", "여정 단계")
                                      if c in pl["머리"]]))
        쪽.append('<p class="출처">출처 — 최종 엑셀 [★PL Issue] %d행 (전량)</p>' % len(pl["행"]))
        담음.append("★PL Issue")

    ip = 표.get("improvement_priority")
    if ip:
        쪽.append("<h2>개선 우선순위 — 건수와 부정 강도 두 축</h2>")
        쪽.append(_표만들기(ip["머리"], ip["행"], [c for c in ("product_category", "topic", "n", "neg_count", "neg_ratio")
                                      if c in ip["머리"]]))
        쪽.append('<p class="출처">출처 — 최종 엑셀 [improvement_priority] %d행</p>' % len(ip["행"]))
        담음.append("improvement_priority")

    vs = 표.get("video_summary")
    if vs:
        쪽.append("<h2>영상별 흐름</h2>")
        쪽.append(_표만들기(vs["머리"], vs["행"], [c for c in ("video_title", "comment_count", "positive_rate", "negative_rate")
                                      if c in vs["머리"]]))
        쪽.append('<p class="출처">출처 — 최종 엑셀 [video_summary] %d행</p>' % len(vs["행"]))
        담음.append("video_summary")

    # ★ 「했다」 가 아니라 「확인했다」 — 다시 훑는다 (65 §3)
    글전체 = "\n".join(쪽)
    남음 = 남았나(글전체)
    쪽.append('<div class="확인"><b>개인정보 처리 확인</b><br>'
             "치운 것 — 링크 %d건 · 이메일 %d건 · 사용자명 %d건<br>"
             "<b>다시 훑은 결과</b> — 링크 %d · 이메일 %d · 사용자명 %d (0 이어야 합니다)<br>"
             "원문 전량(<code>raw_voc</code>)과 식별자는 이 보고서에 담지 않았습니다.</div>"
             % (치움["링크"], 치움["이메일"], 치움["사용자명"],
                남음["링크"], 남음["이메일"], 남음["사용자명"]))
    쪽.append("</html>")
    낼자리.parent.mkdir(parents=True, exist_ok=True)
    낼자리.write_text("\n".join(쪽), encoding="utf-8", newline="\n")
    return {"담음": 담음, "치움": dict(치움), "남음": dict(남음), "낸자리": str(낼자리)}


def main() -> int:
    인자 = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not 인자:
        print(__doc__)
        return 2
    엑셀 = Path(인자[0])
    if not 엑셀.is_file():
        print("  ✗ 못 찾음 — %s (최종 산출물 엑셀을 주십시오)" % 엑셀)
        return 2
    if "--확인만" in sys.argv:
        표 = 읽기(엑셀)
        print("  담을 수 있는 시트: %s" % " · ".join(n for n in 쓰는시트 if n in 표))
        print("  안 담는 시트: %s" % " · ".join("%s(%s)" % (k, v) for k, v in 안넣는시트.items()))
        return 0
    낼자리 = Path(인자[1]) if len(인자) > 1 else 엑셀.parent / "VoC_분석보고서.html"
    셈 = 만들기(엑셀, 낼자리)
    print("  보고서 — %s" % 셈["낸자리"])
    print("  담은 것: %s" % (" · ".join(셈["담음"]) or "(없음)"))
    print("  치운 것 — 링크 %d · 이메일 %d · 사용자명 %d"
          % (셈["치움"].get("링크", 0), 셈["치움"].get("이메일", 0), 셈["치움"].get("사용자명", 0)))
    남 = 셈["남음"]
    print("  다시 훑은 결과 — 링크 %d · 이메일 %d · 사용자명 %d" % (남["링크"], 남["이메일"], 남["사용자명"]))
    if any(남.values()):
        print("  ✗ 아직 남아 있습니다 — 보고서를 내지 마십시오.")
        return 1
    if not 셈["담음"]:
        print("  ✗ 담을 시트를 하나도 못 찾았습니다 — 최종 산출물이 맞습니까? (못 찾음은 통과가 아닙니다)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
