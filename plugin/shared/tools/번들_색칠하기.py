# -*- coding: utf-8 -*-
"""최종 번들에 **안내와 같은 색**을 칠한다.

★ 왜 (sky 2026-08-23)
  「최종 번들 파일에도 같은 색으로 주요 봐야할 데이터들에 대해 반영하셨나요?」

  ★ 안 했다. 그런데 **같은 문제다.**
    안내에서 89칸을 위아래로 훑기 힘들다고 했는데,
    번들에서는 그 89칸을 **옆으로** 훑어야 한다. 더 힘들다.

  안내와 **같은 색**을 쓴다. 그래야 둘이 이어진다 —
  안내에서 「TEE 는 빨강」 을 보고 번들에서 빨간 칸을 찾으면 된다.

무엇을 하나
  · raw_voc 머리줄을 묶음 색으로 칠한다 (89칸)
  · 틀을 고정한다 — 옆으로 밀어도 머리줄과 atomic_id 가 남는다
  · 시트 탭에 색을 준다 — ★ 두 시트가 눈에 띄게
  · 시트마다 머리줄을 굵게 하고 걸러 볼 수 있게(필터) 한다

★ 데이터는 **한 글자도 건드리지 않는다.** 꾸밈만 바꾼다.

쓰기
    python 번들_색칠하기.py [번들.xlsx]
"""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

# ★ 안내(데이터안내_만들기.py)와 **같은 색**이어야 한다.
#   한쪽만 고치면 둘이 어긋난다 — 고칠 때는 둘 다 고친다.
묶음색 = [
    ("2E5F8A", "D9E7F2"), ("4A7C59", "DCEAE0"), ("8A5A2E", "F2E6D9"),
    ("6B4A8A", "E7DCF2"), ("2E7D8A", "D9EFF2"), ("8A2E5F", "F2D9E7"),
    ("7D8A2E", "EFF2D9"), ("A03030", "F5DCDC"), ("30609A", "DCE6F5"),
    ("5A5A5A", "E8E8E8"), ("8A6B2E", "F2EAD9"), ("2E8A6B", "D9F2EA"),
    ("6B6B8A", "E4E4F0"), ("8A3E2E", "F2E0D9"),
]

묶음 = [
    ("① 이 줄이 무엇인가",
     ["source_id", "raw_row_index", "parent_voc_id", "comment_relation",
      "atomic_id", "atomic_index", "split_origin_atomic_id"]),
    ("② 고객이 한 말",
     ["original_voc", "voc_cleaned", "voc_residual", "atomic_voc",
      "atomic_voc_summary", "source_context_summary"]),
    ("③ 무슨 얘기인가",
     ["topic_provisional", "topic", "topic_evidence", "topic_score",
      "topic_group", "secondary_topic_source"]),
    ("④ 제품·브랜드",
     ["reference_brand", "product_tags", "product_additional_info",
      "competitor_brand_tags", "competitor_product_tags",
      "competitor_product_additional_info", "brand", "market", "language",
      "product_category", "product_category_source"]),
    ("⑤ 고객 여정",
     ["cej", "cej_evidence", "cej_group"]),
    ("⑥ 물어본 것",
     ["inquiry_flag", "inquiry_type", "inquiry_type_raw"]),
    ("⑦ 원하는 것",
     ["need_signal_flag", "need_signal_type", "need_signal_type_raw"]),
    ("⑧ TEE",
     ["tee_time_score", "tee_time_evidence", "tee_effort_score",
      "tee_effort_evidence", "tee_emotion_score", "tee_emotion_evidence",
      "tee_success_score", "tee_success_evidence", "tee_summary"]),
    ("⑨ RC",
     ["rootcause_problem", "rootcause_target", "rootcause_cause",
      "rootcause_summary", "rootcause_score"]),
    ("⑩ 믿을 만한가",
     ["confidence_rating", "confidence_topic", "confidence_cej",
      "confidence_inquiry", "confidence_need_signal",
      "confidence_entity_role", "confidence_score", "confidence_gate",
      "voc_total_score"]),
    ("⑪ 쓰나 버리나",
     ["status", "validity", "scope_exclusion_reason", "na_class",
      "entity_role", "sentiment_dir", "proposal_flag"]),
    ("⑫ 어느 영상",
     ["video_id", "video_title", "video_url"]),
    ("⑬ 대시보드가 만든 칸",
     ["market_display", "brand_display", "competitor_brand_display_tags",
      "review_queue", "trace_summary"]),
    ("⑭ 2차·3차가 남긴 것",
     ["qc_status_summary", "qc_rule_ids", "qc_verdict", "qc_finding_count",
      "qc_entity", "qc_confidence", "qc_criteria_uncovered",
      "qc_structural_defect", "review_required", "review_reason",
      "decided_by", "decided_note"]),
]

# 시트 탭 색 — ★ 두 시트는 사람이 볼 것이라 눈에 띄게
탭색 = {
    "raw_voc": "2E5F8A",
    "★사람이볼목록": "C00000",
    "★보정요청": "C00000",
    "improvement_priority": "4A7C59",
    "improvement_priority_comp": "4A7C59",
    "improvement_evidence_and_ai": "4A7C59",
}


def main() -> int:
    길 = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if 길 is None:
        d = ROOT / "_판독패키지" / "_결과" / "master_final"
        hits = sorted(d.glob("*.xlsx")) if d.is_dir() else []
        길 = hits[0] if hits else None
    if not 길 or not Path(길).exists():
        print("  최종 번들을 못 찾았습니다 — 자리를 알려 주십시오")
        return 1

    print("  여는 중입니다 — %s (조금 걸립니다)" % Path(길).name)
    w = openpyxl.load_workbook(길)

    # 칸 → 묶음 번호
    어느묶음 = {}
    for i, (이름, 칸들) in enumerate(묶음):
        for k in 칸들:
            어느묶음[k] = i

    # ── raw_voc 머리줄 색칠 ────────────────────────────────────────
    if "raw_voc" in w.sheetnames:
        ws = w["raw_voc"]
        머리 = [ws.cell(row=1, column=i).value for i in range(1, ws.max_column + 1)]
        못칠한것 = []
        for i, k in enumerate(머리, 1):
            k = str(k or "")
            번 = 어느묶음.get(k)
            if 번 is None:
                못칠한것.append(k)
                진, 연 = "808080", "EEEEEE"
                이름 = "?"
            else:
                진, 연 = 묶음색[번 % len(묶음색)]
                이름 = 묶음[번][0]
            c = ws.cell(row=1, column=i)
            c.fill = PatternFill("solid", fgColor=진)
            c.font = Font(name="맑은 고딕", bold=True, size=9, color="FFFFFF")
            c.alignment = Alignment(vertical="center", horizontal="center",
                                    wrap_text=True)
            # ★ 그 칸이 어느 묶음인지 메모로 남긴다 — 마우스를 얹으면 보인다
            try:
                from openpyxl.comments import Comment
                c.comment = Comment("%s\n\n칸: %s" % (이름, k), "VoC 안내")
            except Exception:                                # noqa: BLE001
                pass
            ws.column_dimensions[get_column_letter(i)].width = max(
                12, min(28, len(k) + 4))
        ws.row_dimensions[1].height = 34
        # ★ 옆으로 밀어도 머리줄과 앞 다섯 칸(atomic_id 까지)이 남는다
        ws.freeze_panes = "F2"
        ws.auto_filter.ref = "A1:%s1" % get_column_letter(ws.max_column)
        print("  raw_voc — %d칸 칠했습니다%s"
              % (len(머리),
                 (" · ★못 칠한 칸 %d개: %s" % (len(못칠한것), " · ".join(못칠한것)))
                 if 못칠한것 else ""))

    # ── 다른 시트 — 머리줄 굵게 · 틀고정 · 필터 ────────────────────
    for s in w.sheetnames:
        ws = w[s]
        if s in 탭색:
            ws.sheet_properties.tabColor = 탭색[s]
        if s == "raw_voc":
            continue
        if ws.max_row < 1 or ws.max_column < 1:
            continue
        진 = 탭색.get(s, "5A5A5A")
        for i in range(1, ws.max_column + 1):
            c = ws.cell(row=1, column=i)
            if c.value is None:
                continue
            c.fill = PatternFill("solid", fgColor=진)
            c.font = Font(name="맑은 고딕", bold=True, size=9, color="FFFFFF")
            c.alignment = Alignment(vertical="center", horizontal="center",
                                    wrap_text=True)
            ws.column_dimensions[get_column_letter(i)].width = max(
                12, min(30, len(str(c.value)) + 4))
        ws.row_dimensions[1].height = 30
        ws.freeze_panes = "A2"
        if ws.max_row > 1:
            ws.auto_filter.ref = "A1:%s1" % get_column_letter(ws.max_column)

    print("  저장하는 중입니다")
    w.save(길)
    print("  칠했습니다 — %s" % Path(길).name)
    print("     ★ 안내(VoC_데이터_안내.xlsx)와 같은 색입니다")
    print("     ★ 머리줄에 마우스를 얹으면 어느 묶음인지 나옵니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
