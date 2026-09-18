"""Video-level summary tab."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src.dashboard60.charts import stable_color
from src.dashboard60.data_contract import ensure_dashboard_columns, video_summary
from src.dashboard60.ui_cards import (
    badge,
    metric_card,
    persistent_expander,
    render_metric_grid,
    render_selectable_dataframe,
    section_title,
    task_card_html,
)


def _video_color_map(summary: pd.DataFrame) -> dict[str, str]:
    titles = summary["video_title"].replace("", pd.NA).fillna(summary["video_id"]).astype(str)
    return {title: stable_color(title) for title in titles.drop_duplicates()}


def _video_metric_chart(summary: pd.DataFrame, metric: str, title: str, color_map: dict[str, str]) -> alt.Chart:
    chart_frame = summary.head(15).copy()
    chart_frame["video_title"] = chart_frame["video_title"].replace("", pd.NA).fillna(chart_frame["video_id"])
    domain = list(color_map)
    return (
        alt.Chart(chart_frame)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            y=alt.Y("video_title:N", sort="-x", title=None, axis=alt.Axis(labelLimit=0)),
            x=alt.X(f"{metric}:Q", title="비율", axis=alt.Axis(format="%")),
            color=alt.Color(
                "video_title:N",
                scale=alt.Scale(domain=domain, range=[color_map[item] for item in domain]),
                legend=alt.Legend(
                    orient="bottom",
                    direction="horizontal",
                    columns=3,
                    title=None,
                    labelLimit=0,
                    symbolLimit=0,
                ),
                title=None,
            ),
            tooltip=["video_title", "comment_count", alt.Tooltip(f"{metric}:Q", title=title, format=".1%")],
        )
        .properties(height=max(260, min(620, 120 + len(chart_frame) * 42)), padding={"top": 12, "bottom": 12})
    )


def render(frame: pd.DataFrame) -> None:
    frame = ensure_dashboard_columns(frame)
    st.subheader("영상 분석 요약")
    st.caption("영상별 댓글 수, 긍정률, 부정률, 문의율과 대표 VoC를 66컬럼 결과에서 집계합니다.")
    st.caption("문의율은 감성(긍정/부정/중립)과 별도 축입니다. 부정적인 문의도 가능하므로 긍정률+부정률+문의율 합산이 100%를 넘을 수 있습니다.")
    total = len(frame)
    render_metric_grid(
        [
            metric_card("집계 Row", f"{total:,}", "현재 필터 기준", tone="blue"),
            metric_card("영상 수", f"{frame['video_id'].nunique() if total else 0:,}", "video_id 기준", tone="green"),
        ]
    )
    summary = video_summary(frame)
    if summary.empty:
        st.info("현재 필터 조건에서 영상 집계가 없습니다.")
        return

    section_title("영상별 리스트 카드", "부정률·긍정률·문의율을 함께 표시")
    top_videos = summary.head(4)
    video_cols = st.columns(2)
    for idx, (_, row) in enumerate(top_videos.iterrows()):
        positive_rate = float(row.get("positive_rate", 0) or 0)
        negative_rate = float(row.get("negative_rate", 0) or 0)
        inquiry_rate = float(row.get("inquiry_rate", 0) or 0)
        tone = "red" if negative_rate >= 0.3 else "green" if positive_rate >= 0.3 else "purple" if inquiry_rate >= 0.3 else "blue"
        title = str(row.get("video_title") or row.get("video_id") or "영상 미확인")
        card = task_card_html(
            title,
            [
                badge(f"댓글 {int(row.get('comment_count', 0) or 0):,}건"),
                badge(f"긍정 {positive_rate * 100:.1f}%", tone="positive" if positive_rate else "neutral"),
                badge(f"부정 {negative_rate * 100:.1f}%", tone="negative" if negative_rate else "neutral"),
                badge(f"문의 {inquiry_rate * 100:.1f}%", tone="warning" if inquiry_rate else "neutral"),
            ],
            str(row.get("representative_voc") or ""),
            tone=tone,
        )
        with video_cols[idx % 2]:
            st.markdown(card, unsafe_allow_html=True)
            if row.get("video_url"):
                st.link_button("영상 열기", str(row["video_url"]))

    chart_frame = summary.head(15).copy()
    chart_frame["video_title"] = chart_frame["video_title"].replace("", pd.NA).fillna(chart_frame["video_id"])
    color_map = _video_color_map(chart_frame)
    section_title("영상별 부정률", "범례 하단 가로 · 축약 없음")
    st.altair_chart(
        _video_metric_chart(chart_frame, "negative_rate", "부정률", color_map),
        width="stretch",
        key="video_negative_rate_chart",
    )
    section_title("영상별 긍정률", "범례 하단 가로 · 축약 없음")
    st.altair_chart(
        _video_metric_chart(chart_frame, "positive_rate", "긍정률", color_map),
        width="stretch",
        key="video_positive_rate_chart",
    )
    section_title("영상별 문의율", "범례 하단 가로 · 축약 없음")
    st.altair_chart(
        _video_metric_chart(chart_frame, "inquiry_rate", "문의율", color_map),
        width="stretch",
        key="video_inquiry_rate_chart",
    )

    display = summary.copy()
    for column in ("positive_rate", "negative_rate", "inquiry_rate"):
        display[column] = (display[column] * 100).round(1).astype(str) + "%"
    with persistent_expander("영상별 집계 테이블", key="video_summary_table_expander", expanded=True):
        video_columns = [
            "video_id",
            "video_title",
            "comment_count",
            "positive_rate",
            "negative_rate",
            "inquiry_rate",
            "representative_voc",
            "video_url",
        ]
        render_selectable_dataframe(
            display[video_columns],
            key="video_summary_table",
            default_columns=video_columns,
        )

    st.info("개선과제/전략 해석은 2차 분석 Agent 트랙에서 다룹니다. 이 탭은 영상 단위 현황 파악용입니다.")
