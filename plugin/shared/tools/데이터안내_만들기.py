# -*- coding: utf-8 -*-
"""실무자용 **데이터 안내** 엑셀을 만든다.

★ 왜 (sky 2026-08-23)
  「최종 번들의 각 sheet 에 있는 데이터들을 조금 더 실무자 친화적으로 정리해 준
    파일이 있으면 좋겠음 … 데이터 스키마도 뭔가 복잡해 보인다는 의견이며,
    첨 보는 사람도 쉽게 이해할 수 있게, TEE 끼리는 묶어서 그룹핑해 준다거나」

  ★ 있는 사전(15_VoC_데이터사전_스키마)은 93칸을 **번호순**으로 늘어놓는다.
    처음 보는 사람은 `tee_time_score` 와 `tee_effort_score` 가
    한 덩어리라는 것을 모른다. 묶어 주면 보인다.

  ★★ 뜻은 **짐작하지 않는다.** 있는 사전에서 그대로 가져오고,
    묶음 이름과 「한 줄 설명」 만 새로 붙인다.

무엇을 만드나
  0_먼저_보기     14시트가 각각 무엇인가 · 언제 어느 시트를 여나
  1_칸_묶음별      raw_voc 89칸을 열네 묶음으로 (TEE 는 TEE 끼리, RC 는 RC 끼리)
  2_다른_시트_칸    나머지 시트의 칸

쓰기
    python 데이터안내_만들기.py [번들.xlsx]
"""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_여기 = Path(__file__).resolve().parent
ROOT = _여기.parent if _여기.name in ("스크립트", "scripts") else _여기

사전길 = ROOT / "15_VoC_데이터사전_스키마_v3.2_90컬럼.xlsx"

# ── 시트가 무엇인가 — 실무자 말로 ──────────────────────────────────
시트설명 = {
    "raw_voc": ("★ 판정 결과 전부",
                "댓글 한 줄이 한 행. 2차·3차를 거친 **최종 판정**이 여기 있습니다.",
                "무엇이든 원본이 궁금할 때"),
    "video_summary": ("영상별 묶음",
                      "영상 하나가 한 행. 그 영상에 댓글이 몇 개고 어떤 반응이었나.",
                      "어느 영상이 시끄러웠나 볼 때"),
    "inquiry_rows": ("물어본 것만",
                     "고객이 **질문한** 댓글만 골라 놓은 것.",
                     "무엇을 자주 묻는지 볼 때"),
    "improvement_priority": ("개선 우선순위",
                             "어느 주제를 먼저 고쳐야 하나 — 건수와 세기로 매긴 순위.",
                             "무엇부터 손댈지 정할 때"),
    "improvement_priority_comp": ("개선 우선순위 (경쟁사)",
                                  "같은 것을 경쟁사 얘기로 매긴 것.",
                                  "경쟁사와 견줄 때"),
    "improvement_evidence_and_ai": ("근거와 요약",
                                    "위 우선순위마다 실제 발화와 요약을 붙인 것.",
                                    "왜 그 순위인지 근거를 볼 때"),
    "수정로그_오류확정": ("2차가 고친 것",
                    "1차 엔진 판정을 2차 판독자가 고친 기록. 칸 단위로 한 줄씩.",
                    "무엇이 얼마나 고쳐졌나 볼 때"),
    "수정로그_재검토필요": ("사람이 볼 행 (같은 내용)",
                     "★사람이볼목록 과 같은 69행입니다. 이름이 옛것이라 헷갈립니다.",
                     "13번 시트를 보십시오"),
    "분리제안": ("쪼개자는 제안",
                "한 댓글에 여러 얘기가 섞여 있어 나누자고 한 것.",
                "한 줄에 여러 주제가 섞였을 때"),
    "기준서개정후보": ("2차가 올린 기준서 빈 곳",
                  "2차 판독자가 번들에 남긴 것만 담습니다. **비어 있어도 맞습니다** — "
                  "3차 것은 14번에 있습니다.",
                  "거의 볼 일 없음"),
    "구조적결함": ("2차가 올린 엔진 결함",
               "위와 같습니다. 비어 있어도 맞습니다.",
               "거의 볼 일 없음"),
    "판정불일치": ("형식 검사",
               "한 행 안에서 판정과 지적 심각도가 어긋난 것. "
               "**0 이면 어긋난 행이 없다는 뜻**입니다.",
               "거의 볼 일 없음"),
    "★사람이볼목록": ("★★ 4차에서 정할 것",
                 "감독자 둘이 서로 다르게 본 행. **사람이 정해야 합니다.**",
                 "★ 4차 회의에서 이것을 봅니다"),
    "★보정요청": ("★★ 회사가 정할 것",
               "담을 라벨이 없거나 두 라벨이 겹치는 것. 2차·3차에서 쌓인 전부.",
               "★ 4차 회의에서 이것을 봅니다"),
}

# ── 칸 묶음 — TEE 는 TEE 끼리, RC 는 RC 끼리 ────────────────────────
#   (묶음이름, 한 줄 설명, [칸…])
묶음들 = [
    ("① 이 줄이 무엇인가", "어느 댓글의 어느 조각인지 가리키는 번호들. 판정 내용은 아닙니다.",
     ["source_id", "raw_row_index", "parent_voc_id", "comment_relation",
      "atomic_id", "atomic_index", "split_origin_atomic_id"]),

    ("② 고객이 한 말", "원문과, 분석하려고 다듬은 말. **근거를 볼 때 여기를 봅니다.**",
     ["original_voc", "voc_cleaned", "voc_residual", "atomic_voc",
      "atomic_voc_summary", "source_context_summary"]),

    ("③ 무슨 얘기인가 (주제)", "이 말이 어느 주제인가. **가장 많이 보는 칸입니다.**",
     ["topic_provisional", "topic", "topic_evidence", "topic_score",
      "topic_group", "secondary_topic_source"]),

    ("④ 어느 제품·브랜드 얘기인가", "자사인지 경쟁사인지, 어떤 제품인지.",
     ["reference_brand", "product_tags", "product_additional_info",
      "competitor_brand_tags", "competitor_product_tags",
      "competitor_product_additional_info", "brand", "market", "language",
      "product_category", "product_category_source"]),

    ("⑤ 고객 여정 (CEJ)", "사기 전인지, 쓰는 중인지, 고장 났을 때인지 — 어느 길목의 말인가.",
     ["cej", "cej_evidence", "cej_group"]),

    ("⑥ 물어본 것인가 (Inquiry)", "질문인가 아닌가, 어떤 종류의 질문인가.",
     ["inquiry_flag", "inquiry_type", "inquiry_type_raw"]),

    ("⑦ 원하는 것이 있는가 (Need)", "「이런 게 있으면 좋겠다」 는 신호인가.",
     ["need_signal_flag", "need_signal_type", "need_signal_type_raw"]),

    ("⑧ TEE — 얼마나 애먹었나", "고객이 겪은 수고를 **넷으로 나눠** 잽니다 — "
     "시간(Time) · 수고(Effort) · 감정(Emotion) · 해냈나(Success). "
     "점수와 그 근거가 짝을 이룹니다.",
     ["tee_time_score", "tee_time_evidence", "tee_effort_score",
      "tee_effort_evidence", "tee_emotion_score", "tee_emotion_evidence",
      "tee_success_score", "tee_success_evidence", "tee_summary"]),

    ("⑨ RC — 왜 그런가 (원인)", "무엇이 문제고(problem), 무엇 때문이며(cause), "
     "어디를 고쳐야 하나(target). **개선 과제를 뽑는 자리입니다.**",
     ["rootcause_problem", "rootcause_target", "rootcause_cause",
      "rootcause_summary", "rootcause_score"]),

    ("⑩ 얼마나 믿을 만한가", "판정마다 붙은 확신도. 낮으면 사람이 다시 봅니다.",
     ["confidence_rating", "confidence_topic", "confidence_cej",
      "confidence_inquiry", "confidence_need_signal",
      "confidence_entity_role", "confidence_score", "confidence_gate",
      "voc_total_score"]),

    ("⑪ 이 행을 쓰나 버리나", "분석에 쓰는 행인지, 뺀 행인지, 왜 뺐는지.",
     ["status", "validity", "scope_exclusion_reason", "na_class",
      "entity_role", "sentiment_dir", "proposal_flag"]),

    ("⑫ 어느 영상에서 왔나", "그 댓글이 달린 영상.",
     ["video_id", "video_title", "video_url"]),

    ("⑬ 대시보드가 만든 칸", "화면에 보여 주려고 대시보드가 따로 만든 것. "
     "판정 내용이 아닙니다.",
     ["market_display", "brand_display", "competitor_brand_display_tags",
      "review_queue", "trace_summary"]),

    ("⑭ 2차·3차가 남긴 것", "판독자와 감독자가 남긴 자국 — 무엇을 고쳤고 누가 정했나. "
     "**★review_required = Y 인 행이 4차에서 볼 69행입니다.**",
     ["qc_status_summary", "qc_rule_ids", "qc_verdict", "qc_finding_count",
      "qc_entity", "qc_confidence", "qc_criteria_uncovered",
      "qc_structural_defect", "review_required", "review_reason",
      "decided_by", "decided_note"]),
]

# ★ 사전 정의가 너무 짧은 칸에만 쉬운 말을 붙인다 (2026-08-23).
#   「★시간 비용」 · 「검토 필요」 는 처음 보는 사람에게 아무 말도 아니다.
#   ★ 지어내지 않는다 — 레이어·값범위에서 나오는 것만 적는다.
쉬운말 = {
    "tee_time_score": "고객이 **시간**을 얼마나 뺏겼나. 음수일수록 나쁩니다.",
    "tee_effort_score": "고객이 **품**을 얼마나 들였나. 음수일수록 나쁩니다.",
    "tee_emotion_score": "고객 **기분**이 어땠나. 음수는 화남, 양수는 좋음.",
    "tee_success_score": "고객이 하려던 것을 **해냈나**. 음수면 못 했다는 뜻.",
    "tee_summary": "위 넷을 한 문장으로 묶은 것.",
    "tee_time_evidence": "그 점수를 준 근거 — 실제 발화에서 뽑은 대목.",
    "tee_effort_evidence": "그 점수를 준 근거 — 실제 발화에서 뽑은 대목.",
    "tee_emotion_evidence": "그 점수를 준 근거 — 실제 발화에서 뽑은 대목.",
    "tee_success_evidence": "그 점수를 준 근거 — 실제 발화에서 뽑은 대목.",
    "review_required": "★ **Y 이면 사람이 봐야 하는 행**입니다. 4차에서 볼 69행이 이것.",
    "review_reason": "왜 사람이 봐야 하는지 한 줄로.",
    "decided_by": "누가 정했나 — 판독자 합의인지, 감독자가 정했는지.",
    "decided_note": "감독자가 그렇게 정한 까닭.",
    "topic": "★ 이 말이 **무슨 얘기인가**. 가장 많이 보는 칸입니다.",
    "topic_provisional": "1차 엔진이 먼저 붙였던 주제 (고쳐지기 전).",
    "topic_evidence": "그 주제로 본 근거 — 실제 발화에서 뽑은 대목.",
    "topic_group": "주제를 더 크게 묶은 것 (여러 주제가 한 묶음).",
    "secondary_topic_source": "2차에서 주제가 바뀌었으면 무엇 때문에 바뀌었나.",
    "atomic_voc": "★ **판정 대상이 되는 말.** 근거를 볼 때 여기를 봅니다.",
    "voc_cleaned": "댓글 전체를 다듬은 것 (여러 조각으로 나뉘기 전).",
    "original_voc": "고객이 쓴 **원문 그대로**.",
    "atomic_id": "★ 이 줄의 **고유 번호**. 다른 파일과 맞출 때 이것으로 짝짓습니다.",
    "cej": "고객 여정 어디쯤인가 — 사기 전 · 사는 중 · 쓰는 중 · 고장 났을 때.",
    "cej_group": "위를 더 크게 묶은 것.",
    "status": "이 행을 분석에 쓰나 안 쓰나.",
    "validity": "판정이 쓸 만한가.",
    "scope_exclusion_reason": "뺐다면 왜 뺐나.",
    "confidence_rating": "판정을 얼마나 믿을 만한가 (높음/보통/낮음).",
    "sentiment_dir": "좋게 말했나 나쁘게 말했나.",
    "product_category": "어느 제품군 얘기인가 (세탁기·로봇청소기…).",
    "rootcause_problem": "무엇이 **문제**인가.",
    "rootcause_cause": "**왜** 그런가.",
    "rootcause_target": "**어디를** 고쳐야 하나.",
    "rootcause_summary": "위 셋을 한 문장으로.",
    "inquiry_flag": "질문인가 아닌가 (Y/N).",
    "need_signal_flag": "「이런 게 있으면」 하는 바람인가 (Y/N).",
    "qc_verdict": "2차 판독자가 이 행을 어떻게 봤나.",
    "qc_finding_count": "이 행에서 지적한 것이 몇 개인가.",
}


# ★ 묶음마다 다른 색 (sky 2026-08-23)
#   「색으로 구분되있는게 아니다보니 쭉 넘기다보면 경계도 좀 없어서 보기 힘들고요」
#   ★ 진한 색은 묶음 머리줄, 연한 색은 그 아래 칸들 — 같은 계열로 짝지어
#     경계가 저절로 보이게 한다. 열넷이라 색을 돌려 쓴다.
묶음색 = [
    ("2E5F8A", "D9E7F2"),   # ① 파랑
    ("4A7C59", "DCEAE0"),   # ② 초록
    ("8A5A2E", "F2E6D9"),   # ③ 갈색
    ("6B4A8A", "E7DCF2"),   # ④ 보라
    ("2E7D8A", "D9EFF2"),   # ⑤ 청록
    ("8A2E5F", "F2D9E7"),   # ⑥ 자주
    ("7D8A2E", "EFF2D9"),   # ⑦ 연두
    ("A03030", "F5DCDC"),   # ⑧ TEE — 빨강 (눈에 띄게)
    ("30609A", "DCE6F5"),   # ⑨ RC  — 파랑 (눈에 띄게)
    ("5A5A5A", "E8E8E8"),   # ⑩ 회색
    ("8A6B2E", "F2EAD9"),   # ⑪ 황토
    ("2E8A6B", "D9F2EA"),   # ⑫ 민트
    ("6B6B8A", "E4E4F0"),   # ⑬ 남회색
    ("8A3E2E", "F2E0D9"),   # ⑭ 벽돌
]


# 꾸밈
파 = "1F4E79"
연파 = "DCE6F1"
연회 = "F2F2F2"
테 = Side(style="thin", color="BFBFBF")
칸테 = Border(left=테, right=테, top=테, bottom=테)


def 머리쓰기(ws, 이름들, 너비들):
    for i, (n, w) in enumerate(zip(이름들, 너비들), 1):
        c = ws.cell(row=1, column=i, value=n)
        c.font = Font(name="맑은 고딕", bold=True, size=10, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=파)
        c.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
        c.border = 칸테
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"


def 줄쓰기(ws, r, 값들, 굵게=False, 채움=None, 글자색=None):
    for i, v in enumerate(값들, 1):
        c = ws.cell(row=r, column=i, value=v)
        c.font = Font(name="맑은 고딕", size=10, bold=굵게,
                      color=글자색 or "1A1A1A")
        c.alignment = Alignment(vertical="top", wrap_text=True)
        c.border = 칸테
        if 채움:
            c.fill = PatternFill("solid", fgColor=채움)


def main() -> int:
    번들길 = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if 번들길 is None:
        for c in (ROOT / "_판독패키지" / "_결과" / "master_final",):
            hits = sorted(c.glob("*.xlsx")) if c.is_dir() else []
            if hits:
                번들길 = hits[0]
                break
    if not 번들길 or not Path(번들길).exists():
        print("  최종 번들을 못 찾았습니다 — 자리를 알려 주십시오")
        print("    python 데이터안내_만들기.py <번들.xlsx>")
        return 1

    if not 사전길.exists():
        print("  데이터사전을 못 찾았습니다 — %s" % 사전길)
        return 1

    # 사전에서 뜻을 가져온다 (짐작하지 않는다)
    사w = openpyxl.load_workbook(사전길, read_only=True)
    사행 = list(사w["데이터 사전"].iter_rows(values_only=True))
    머리i = next(i for i, r in enumerate(사행)
               if r and any(str(x or "").strip() == "컬럼명" for x in r))
    사머리 = [str(x or "").strip() for x in 사행[머리i]]
    i컬, i정 = 사머리.index("컬럼명"), 사머리.index("정의")
    i곳 = 사머리.index("만드는 곳") if "만드는 곳" in 사머리 else None
    사전 = {}
    for r in 사행[머리i + 1:]:
        if r and str(r[i컬] or "").strip():
            사전[str(r[i컬]).strip()] = (
                str(r[i정] or "").strip(),
                str(r[i곳] or "").strip() if i곳 is not None else "")

    # 번들에서 시트·칸·예시값
    bw = openpyxl.load_workbook(번들길, read_only=True)
    시트 = {}
    보기 = {}
    for s in bw.sheetnames:
        it = bw[s].iter_rows(values_only=True)
        try:
            머리 = [str(x or "") for x in next(it)]
        except StopIteration:
            머리 = []
        n = 0
        표본 = []
        for r in it:
            n += 1
            if len(표본) < 40:
                표본.append(r)
        시트[s] = (머리, n)
        if s == "raw_voc":
            for i, c in enumerate(머리):
                값 = ""
                for r in 표본:
                    v = str(r[i] or "").strip() if i < len(r) else ""
                    if v and v not in ("N/A", "nan"):
                        값 = v[:60]
                        break
                보기[c] = 값

    out = openpyxl.Workbook()

    # ── 0_먼저_보기 ────────────────────────────────────────────────
    ws = out.active
    ws.title = "0_먼저_보기"
    머리쓰기(ws, ["번호", "시트 이름", "무엇인가", "무슨 내용인가",
                "언제 보나", "행", "칸"],
           [6, 26, 22, 62, 26, 9, 7])
    r = 2
    for i, s in enumerate(bw.sheetnames, 1):
        머리, n = 시트[s]
        짧, 설명, 언제 = 시트설명.get(s, ("", "", ""))
        별 = s.startswith("★")
        줄쓰기(ws, r, [i, s, 짧, 설명, 언제, n, len(머리)],
             굵게=별, 채움=연파 if 별 else None)
        ws.row_dimensions[r].height = 34
        r += 1

    r += 1
    ws.cell(row=r, column=2, value="★ 4차 회의에서 볼 것").font = Font(
        name="맑은 고딕", bold=True, size=11, color=파)
    r += 1
    for x in ("13번 ★사람이볼목록 — 감독자 둘이 갈려 사람이 정할 행",
              "14번 ★보정요청 — 담을 라벨이 없어 회사가 정할 것",
              "함께 여십시오 — 보정요청_논의본.md (실제 발화와 고를 수 있는 길이 적혀 있습니다)"):
        ws.cell(row=r, column=2, value="· " + x).font = Font(name="맑은 고딕", size=10)
        r += 1
    r += 1
    묶음자리행 = r                    # ★ 아래에서 채운다 (1_칸_묶음별 을 만든 뒤)
    r += 2 + len(묶음들)

    ws.cell(row=r, column=2,
            value="★ 10·11·12 번이 비어 있어도 틀린 것이 아닙니다.").font = Font(
        name="맑은 고딕", bold=True, size=10)
    r += 1
    ws.cell(row=r, column=2,
            value="   10·11 은 2차가 번들에 남긴 것만 담고, 3차 것은 14번에 있습니다. "
                  "12 는 형식 검사라 0 이면 어긋난 행이 없다는 뜻입니다.").font = Font(
        name="맑은 고딕", size=10)

    # ── 1_칸_묶음별 ────────────────────────────────────────────────
    ws2 = out.create_sheet("1_칸_묶음별")
    머리쓰기(ws2, ["묶음", "칸 이름", "쉬운 말 (안내용)", "사전의 정의",
                "어떤 값이 들어가나", "이 판의 예시"],
           [24, 28, 46, 44, 26, 30])
    r = 2
    담긴칸 = set()
    자리표 = []                      # ★ 어느 묶음이 몇 행인지 — 0_먼저_보기 에 싣는다
    for 번, (이름, 설명, 칸들) in enumerate(묶음들):
        진, 연 = 묶음색[번 % len(묶음색)]
        머리행 = r
        c = ws2.cell(row=r, column=1, value=이름)
        c.font = Font(name="맑은 고딕", bold=True, size=11, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=진)
        c.alignment = Alignment(vertical="center", wrap_text=True)
        d = ws2.cell(row=r, column=2, value=설명)
        d.font = Font(name="맑은 고딕", size=10, bold=True, color=진)
        d.alignment = Alignment(vertical="center", wrap_text=True)
        d.fill = PatternFill("solid", fgColor=연)
        ws2.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
        for i in range(1, 7):
            cc = ws2.cell(row=r, column=i)
            cc.border = 칸테
            if i > 1:
                cc.fill = PatternFill("solid", fgColor=연)
        ws2.row_dimensions[r].height = 32
        r += 1
        for k in 칸들:
            담긴칸.add(k)
            뜻, 곳 = 사전.get(k, ("(사전에 없습니다)", ""))
            # ★ A열에 묶음 이름을 **모든 행에** 채운다 — 그래야 필터로 고를 수 있다
            줄쓰기(ws2, r, [이름, k, 쉬운말.get(k, ""), 뜻, 곳,
                          보기.get(k, "")], 채움=연)
            ws2.cell(row=r, column=1).font = Font(
                name="맑은 고딕", size=9, color=진)
            ws2.cell(row=r, column=2).font = Font(
                name="맑은 고딕", size=10, bold=True, color="1A1A1A")
            ws2.row_dimensions[r].height = 26
            r += 1
        자리표.append((이름, 머리행, r - 1, len(칸들), 진))
        r += 1

    ws2.auto_filter.ref = "A1:F%d" % (r - 1)   # ★ 묶음으로 걸러 볼 수 있게

    빠진 = [c for c in 시트["raw_voc"][0] if c not in 담긴칸]
    if 빠진:
        c = ws2.cell(row=r, column=1, value="⑮ 아직 묶지 못한 칸")
        c.font = Font(name="맑은 고딕", bold=True, size=11, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="C00000")
        r += 1
        for k in 빠진:
            뜻, 곳 = 사전.get(k, ("(사전에 없습니다)", ""))
            줄쓰기(ws2, r, ["", k, 쉬운말.get(k, ""), 뜻, 곳,
                          보기.get(k, "")])
            r += 1

    # ── 2_다른_시트_칸 ─────────────────────────────────────────────
    ws3 = out.create_sheet("2_다른_시트_칸")
    머리쓰기(ws3, ["시트", "칸 이름", "사전의 정의", "어떤 값이 들어가나"],
           [24, 30, 62, 28])
    r = 2
    시트자리 = []
    for 번, s in enumerate(bw.sheetnames):
        if s == "raw_voc":
            continue
        진, 연 = 묶음색[번 % len(묶음색)]
        머리, n = 시트[s]
        if not 머리:
            continue
        c = ws3.cell(row=r, column=1, value=s)
        c.font = Font(name="맑은 고딕", bold=True, size=11, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=진)
        c.alignment = Alignment(vertical="center", wrap_text=True)
        머리행3 = r
        d = ws3.cell(row=r, column=2,
                     value="%s — %d행 · %d칸"
                           % (시트설명.get(s, ("", "", ""))[0], n, len(머리)))
        d.font = Font(name="맑은 고딕", size=10, bold=True)
        ws3.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        for i in range(1, 5):
            cc = ws3.cell(row=r, column=i)
            cc.border = 칸테
            if i > 1:
                cc.fill = PatternFill("solid", fgColor=연)
        r += 1
        for k in 머리:
            뜻, 곳 = 사전.get(k, ("", ""))
            줄쓰기(ws3, r, [s, k, 뜻, 곳], 채움=연)
            ws3.cell(row=r, column=1).font = Font(
                name="맑은 고딕", size=9, color=진)
            r += 1
        시트자리.append((s, 머리행3, r - 1))
        r += 1
    ws3.auto_filter.ref = "A1:D%d" % (r - 1)

    # ── 묶음 찾아보기 — 어느 묶음이 몇 행인지 (sky 2026-08-23) ──────
    #   ★ 89칸을 스크롤로 훑는 것은 사람이 못 할 일이다.
    rr = 묶음자리행
    t = ws.cell(row=rr, column=2, value="★ 묶음 찾아보기 — 「1_칸_묶음별」 시트에서")
    t.font = Font(name="맑은 고딕", bold=True, size=11, color=파)
    rr += 1
    for 이름, 시작, 끝, 개수, 진 in 자리표:
        a = ws.cell(row=rr, column=2, value=이름)
        a.font = Font(name="맑은 고딕", bold=True, size=10, color="FFFFFF")
        a.fill = PatternFill("solid", fgColor=진)
        a.border = 칸테
        b = ws.cell(row=rr, column=3, value="%d행 ~ %d행" % (시작, 끝))
        b.font = Font(name="맑은 고딕", size=10, bold=True)
        b.alignment = Alignment(horizontal="center")
        b.border = 칸테
        d = ws.cell(row=rr, column=4, value="칸 %d개" % 개수)
        d.font = Font(name="맑은 고딕", size=10)
        d.border = 칸테
        rr += 1
    ws.cell(row=rr, column=2,
            value="★ 그 시트 맨 위에서 A열을 걸러도(필터) 묶음만 볼 수 있습니다.").font = \
        Font(name="맑은 고딕", size=10, color="666666")

    낼곳 = ROOT / "_배포" / "VoC_데이터_안내.xlsx"
    낼곳.parent.mkdir(exist_ok=True)
    out.save(낼곳)
    print("  만들었습니다 — %s" % 낼곳.name)
    print("     0_먼저_보기      시트 %d개" % len(bw.sheetnames))
    print("     1_칸_묶음별      묶음 %d개 · 칸 %d개%s"
          % (len(묶음들), len(담긴칸),
             (" · ★못 묶은 칸 %d" % len(빠진)) if 빠진 else ""))
    print("     2_다른_시트_칸")
    return 0


if __name__ == "__main__":
    sys.exit(main())
