# -*- coding: utf-8 -*-
"""번들 첫 장에 「0_차례」 를 만든다 — 무엇을 어디서 보는지.

★ sky 2026-08-26 — 「뭐를 위해 봐야되는지 모르면 많다고만 느낀다」

★ 시트 이름은 **바꾸지 않는다.**
  raw_voc 만 29개 파일이 참조한다. 이름을 바꾸면 하나만 놓쳐도 조용히 깨진다.
  이름은 그대로 두고 **차례에서 한국어로 풀어 준다.**

쓰기
    python 차례_만들기.py [번들.xlsx]
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

# 시트 이름 · 무엇을 보는 자리인가 · 누가 보나 · 지금 봐야 하나
차례 = [
    ("raw_voc", "판정 결과 전부 — 대시보드가 읽는 장", "기계", ""),
    ("★PL Issue", "안전·위생 전량. 건수와 무관하게 다 뽑는다", "회사", "★ 예"),
    ("★사람이볼목록", "행 하나 관점 — 총괄도 못 정한 것", "실무자", "★ 예"),
    ("★보정요청",
     "규칙 관점 — 「이런 발화를 담을 라벨이 없다」\n"
     "실무자와 시스템설계자가 같이 보고 정한다", "실무자+설계", "★ 예"),
    ("수정로그_재검토필요",
     "참고 — 총괄이 이렇게 고쳤습니다.\n"
     "이상한 것만 짚으시면 됩니다 (필수 아님)", "실무자", "참고"),
    ("video_summary", "영상별 묶음", "실무자", "참고"),
    ("inquiry_rows", "물어본 것만", "실무자", "참고"),
    ("improvement_priority", "개선 우선순위 (건수 × 부정 강도)", "실무자", "참고"),
    ("improvement_priority_comp", "개선 우선순위 — 경쟁사", "실무자", "참고"),
    ("improvement_evidence_and_ai", "근거와 요약", "실무자", "참고"),
    ("분리제안", "행을 쪼갠 이력", "기계", ""),
    ("편향검사", "3차 감독이 자기 편을 들었나", "총괄", ""),
    ("기준서개정후보",
     "검사 결과 — 0 이면 이상 없음\n(보정요청으로 이미 옮겨졌다)", "기계", ""),
    ("구조적결함",
     "검사 결과 — 0 이면 이상 없음\n(보정요청으로 이미 옮겨졌다)", "기계", ""),
    ("판정불일치", "형식 검사 — 0 이면 이상 없음", "기계", ""),
    ("수정로그_오류확정", "2차가 고친 것 전부 — 근거 보관", "기계", ""),
]

_경계 = {
    "★보정요청": "──── 여기까지 주로 볼 것 ────",
    "improvement_evidence_and_ai": "──── 대시보드와 함께 보면 좋은 것 ────",
}


def main() -> int:
    try:
        import openpyxl
    except ImportError:
        print("  openpyxl 이 없습니다")
        return 1

    준것 = [a for a in sys.argv[1:] if not a.startswith("--")]
    if 준것:
        p = Path(준것[0])
    else:
        골 = sorted((ROOT / "_판독패키지" / "_결과" / "master_final").glob("*.xlsx"))
        if not 골:
            print("  최종 xlsx 를 못 찾았습니다")
            return 1
        p = 골[0]

    if "--확인만" in sys.argv:
        # ★ xlsx 를 고치는 도구다. 확인만 일 때는 열지도 않는다 (2026-08-26).
        print("  ── 확인만 ── %s 의 시트 순서를 잡고 0_차례 를 넣을 참이었습니다."
              % p.name)
        print("     아무것도 안 바꿨습니다.")
        return 0

    wb = openpyxl.load_workbook(p)
    있는것 = set(wb.sheetnames)
    if "0_차례" in wb.sheetnames:
        wb.remove(wb["0_차례"])

    # ★ 차례를 만들면서 **시트 순서도 함께** 잡는다 (2026-08-26).
    #   번들_마무리꾸미기 도 순서를 잡지만 그것은 총괄이 마지막에 손으로 돌린다.
    #   3차_마무리 만 돌리고 끝내면 차례와 실제 순서가 어긋난다 — 실제로 그랬다.
    for _n, (_이름, _설, _누, _언) in enumerate(차례):
        if _이름 not in 있는것:
            continue
        _ws = wb[_이름]
        _지금 = wb.sheetnames.index(_이름)
        wb.move_sheet(_ws, offset=_n - _지금)

    ws = wb.create_sheet("0_차례", 0)
    ws.append(["순서", "시트 이름", "무엇을 보는 자리인가",
               "누가 보나", "지금 봐야 하나", "행"])

    n = 0
    for 이름, 설명, 누가, 언제 in 차례:
        if 이름 not in 있는것:
            continue
        n += 1
        ws.append([n, 이름, 설명, 누가, 언제, wb[이름].max_row - 1])
        if 이름 in _경계:
            ws.append(["", _경계[이름], "", "", "", ""])

    # ★ 차례에 없는 시트도 빠뜨리지 않는다 — 시트가 늘면 여기서 드러난다
    남은 = [s for s in wb.sheetnames
            if s != "0_차례" and s not in {x[0] for x in 차례}]
    for s in 남은:
        n += 1
        ws.append([n, s, "(차례에 아직 안 적힌 시트)", "", "", wb[s].max_row - 1])

    for 열, 너비 in (("A", 6), ("B", 30), ("C", 56),
                    ("D", 12), ("E", 14), ("F", 10)):
        ws.column_dimensions[열].width = 너비
    for 행 in ws.iter_rows(min_row=1, max_row=ws.max_row):
        for c in 행:
            c.alignment = openpyxl.styles.Alignment(vertical="top",
                                                    wrap_text=True)
    for c in ws[1]:
        c.font = openpyxl.styles.Font(bold=True)

    wb.save(p)
    print("  0_차례 를 만들었습니다 — 시트 %d개 · %s" % (n, p.name))
    if 남은:
        print("     ! 차례에 안 적힌 시트 %d개 — 차례_만들기.py 에 추가하십시오"
              % len(남은))
        for s in 남은:
            print("        %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
