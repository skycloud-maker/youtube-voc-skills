"""★ PL(Product Liability) Issue — 안전·위생을 건수와 무관하게 전량 본다.

★ sky 결정 2026-08-25 (4차 실무자 회의)
  「안전이나 위생 관련된 내용은 매우 중요하게 여기기 때문에,
    이 문제에 관해서는 **건수 상관없이 모두 노출**되도록 별도 tab 을 만들었으면 함」

★ 새 집계가 아니라 **별도 뷰**다 (2차 기준서 §11).
  개선우선순위에서 빼지 않는다. 그대로 두고 보기만 따로 만든다 — 중복 계산이 아니다.

★ 왜 따로 보나 — 개선우선순위는 건수·부정 강도로 줄을 세운다.
  한 건짜리 안전 이슈는 거기서 아래로 내려가 묻힌다. 여기서는 거르지 않는다.

★★ 거르는 규칙이 세 곳에 있다. 넓힐 때는 **셋을 함께** 고친다.
      1) 2차 기준서 §11                      ← 단일 출처
      2) outputs/voc_secondary/PL이슈_뽑기.py  ← 번들 시트
      3) 이 파일                              ← 화면
    한쪽만 고치면 번들과 화면이 갈린다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard60.ui_cards import (
    metric_card,
    render_metric_grid,
    render_table_download,
    section_title,
)

# ★ 2차 기준서 §11 과 짝을 맞춘다
PL_TOPICS = ("안전(화재·감전·누수)", "위생/냄새")

# 실무자가 보는 칸 — 89칸을 다 주면 아무도 안 본다
_보일칸 = [
    ("topic", "라벨"),
    ("product_category", "제품군"),
    ("atomic_voc", "무슨 말인가"),
    ("cej", "여정 단계"),
    ("sentiment_dir", "긍부정"),
    ("tee_emotion_score", "감정 강도"),
    ("rootcause_problem", "무엇이 문제인가"),
    ("rootcause_cause", "왜 그런가"),
    ("video_title", "영상"),
    ("atomic_id", "행 번호"),
]


def _고르기(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or "topic" not in frame.columns:
        return pd.DataFrame()
    view = frame[frame["topic"].astype(str).isin(PL_TOPICS)]
    if "status" in view.columns:
        # ★ 제외된 행은 담지 않는다 — 분모 밖이라 개선과제가 될 수 없다
        view = view[view["status"].astype(str) == "normal"]
    return view


def render(frame: pd.DataFrame) -> None:
    section_title(
        "★ PL Issue — 안전·위생",
        "안전(화재·감전·누수) · 위생/냄새 를 **건수와 무관하게 전량** 봅니다. "
        "개선우선순위 집계에서 빼지 않습니다 — 보기만 따로 둔 자리입니다.",
    )

    view = _고르기(frame)
    if view.empty:
        st.success("지금 조건에서 안전·위생으로 잡힌 행이 없습니다.")
        return

    안전 = int((view["topic"].astype(str) == PL_TOPICS[0]).sum())
    위생 = len(view) - 안전
    render_metric_grid(
        [
            metric_card("전체", f"{len(view):,}", "건수로 거르지 않았습니다"),
            metric_card("안전(화재·감전·누수)", f"{안전:,}", "화재 · 감전 · 누수 · 폭발"),
            metric_card("위생/냄새", f"{위생:,}", "곰팡이 · 악취 · 세균"),
        ]
    )

    # ★ 「기대」 인지 「실사용」 인지 갈라 보여 준다 (2026-08-25)
    #   4차에서 실측하니 긍정 나열 23행의 실사용 경험 점수가 **0개**였다.
    #   안 가르면 써 보지도 않고 하는 걱정을 겪은 사고로 읽는다.
    if "cej" in view.columns:
        단계 = view["cej"].astype(str)
        겪음 = int(단계.isin(["사용", "관리", "교체"]).sum())
        st.caption(
            "★ **겪은 것 %d건 · 써 보기 전 걱정 %d건** — `cej` 가 사용·관리·교체면 "
            "실제로 겪은 것이고, 인지·탐색·결정이면 아직 써 보지 않은 걱정입니다. "
            "같은 안전 이슈라도 무게가 다릅니다." % (겪음, len(view) - 겪음)
        )

    # 안전을 먼저, 그다음 감정이 센 것부터
    보기 = view.copy()
    보기["_안전"] = (보기["topic"].astype(str) != PL_TOPICS[0]).astype(int)
    if "tee_emotion_score" in 보기.columns:
        보기["_감정"] = pd.to_numeric(
            보기["tee_emotion_score"], errors="coerce"
        ).abs().fillna(0)
    else:
        보기["_감정"] = 0
    보기 = 보기.sort_values(["_안전", "_감정"], ascending=[True, False])

    있는칸 = [(c, n) for c, n in _보일칸 if c in 보기.columns]
    표 = 보기[[c for c, _ in 있는칸]].rename(columns=dict(있는칸))
    st.dataframe(표, width="stretch", hide_index=True)
    render_table_download(
        표,
        key="pl_issue",
        label="PL Issue 통째로 받기",
        file_stem="PL이슈",
        note="안전·위생 전량입니다. 건수로 거르지 않았습니다.",
    )

