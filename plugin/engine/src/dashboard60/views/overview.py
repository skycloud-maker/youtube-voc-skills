"""VoC overview and drilldown tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard60.charts import SENTIMENT_COLORS, bar_chart
from src.dashboard60.data_contract import ensure_dashboard_columns, scope_exclusion_reason_distribution, topic_distribution
from src.dashboard60.ui_cards import (
    metric_card,
    persistent_expander,
    ratio_rows,
    render_metric_grid,
    render_selectable_dataframe,
    section_title,
)


def _render_metric_cards(frame: pd.DataFrame) -> None:
    total = len(frame)
    inquiry_count = int((frame["inquiry_flag"].fillna("").str.upper() == "Y").sum()) if total else 0
    review_count = int(frame["review_queue"].sum()) if total else 0
    valid_count = int((frame["validity"] == "유효").sum()) if total else 0
    render_metric_grid(
        [
            metric_card("VoC Rows", f"{total:,}", "현재 필터 기준", tone="blue"),
            metric_card("유효 Row", f"{valid_count:,}", f"{(valid_count / total * 100):.1f}%" if total else "0.0%", tone="green"),
            metric_card("문의 비율", f"{(inquiry_count / total * 100):.1f}%" if total else "0.0%", f"{inquiry_count:,}건", tone="purple"),
            metric_card("사람검토 큐", f"{review_count:,}", "review_required=Y", tone="orange"),
            metric_card("제품군 수", f"{frame['product_category'].nunique() if total else 0:,}", "product_category", tone="blue"),
            metric_card("Reason Topic 수", f"{frame['topic'].nunique() if total else 0:,}", "제품·감성 분리", tone="green"),
        ]
    )


def _ratio_payload(series: pd.Series, *, tone_map: dict[str, str] | None = None) -> list[tuple[str, int, float, str]]:
    counts = series.fillna("N/A").replace("", "N/A").value_counts()
    total = int(counts.sum()) or 1
    tone_map = tone_map or {}
    return [(str(label), int(count), float(count / total), tone_map.get(str(label), "")) for label, count in counts.items()]


def render(frame: pd.DataFrame) -> None:
    frame = ensure_dashboard_columns(frame)
    st.subheader("VoC 개요/드릴다운")
    st.caption("topic은 제품군·감성과 분리된 이유 라벨이며, 감성은 TEE/S 기반 sentiment_dir로 별도 표시합니다.")
    _render_metric_cards(frame)
    c1, c2 = st.columns(2)
    with c1:
        section_title("Reason Topic 분포", "상위 15개")
        topic_dist = topic_distribution(frame).head(15)
        st.altair_chart(
            bar_chart(topic_dist, "topic", title="Reason Topic 분포", color="topic"),
            width="stretch",
            key="overview_topic_distribution_chart",
        )
        st.markdown(
            ratio_rows(
                [
                    (str(row["topic"]), int(row["count"]), float(row["share"]), "")
                    for _, row in topic_dist.head(8).iterrows()
                ]
            ),
            unsafe_allow_html=True,
        )
    with c2:
        section_title("감성 분포", "TEE/S 기반 긍정·부정·중립")
        sentiment = frame["sentiment_dir"].value_counts().rename_axis("sentiment_dir").reset_index(name="count")
        st.altair_chart(
            bar_chart(sentiment, "sentiment_dir", title="감성(긍/부/중)", color="sentiment_dir", color_map=SENTIMENT_COLORS),
            width="stretch",
            key="overview_sentiment_distribution_chart",
        )
        st.markdown(
            ratio_rows(_ratio_payload(frame["sentiment_dir"], tone_map={"긍정": "긍정", "부정": "부정", "중립": "중립"})),
            unsafe_allow_html=True,
        )
    c3, c4 = st.columns(2)
    with c3:
        section_title("CEJ 9단계", "데이터사전 v2.7 기준")
        cej = frame["cej"].fillna("해당없음").replace("", "해당없음").value_counts().rename_axis("cej").reset_index(name="count")
        st.altair_chart(
            bar_chart(cej, "cej", title="CEJ 9단계", color="cej"),
            width="stretch",
            key="overview_cej_distribution_chart",
        )
        st.markdown(ratio_rows(_ratio_payload(frame["cej"])), unsafe_allow_html=True)
    with c4:
        section_title("문의 Flag", "질문형 VoC 비율")
        inquiry = (
            frame["inquiry_flag"]
            .fillna("N")
            .replace("", "N")
            .str.upper()
            .value_counts()
            .reindex(["Y", "N"], fill_value=0)
            .rename_axis("inquiry_flag")
            .reset_index(name="count")
        )
        st.altair_chart(
            bar_chart(inquiry, "inquiry_flag", title="문의 비율", color="inquiry_flag"),
            width="stretch",
            key="overview_inquiry_distribution_chart",
        )
        st.markdown(ratio_rows(_ratio_payload(frame["inquiry_flag"].fillna("N").replace("", "N").str.upper())), unsafe_allow_html=True)

    section_title("Scope 제외 사유", "scope_exclusion_reason 7종 전체 표시")
    scope_reasons = scope_exclusion_reason_distribution(frame)
    st.altair_chart(
        bar_chart(
            scope_reasons,
            "reason_label",
            title="Scope 제외 사유별 건수",
            color="scope_exclusion_reason",
        ),
        width="stretch",
        key="overview_scope_exclusion_chart",
    )
    render_selectable_dataframe(
        scope_reasons.rename(
            columns={
                "scope_exclusion_reason": "사유 코드",
                "reason_label": "사유 설명",
                "count": "건수",
            }
        ),
        key="overview_scope_exclusion_reasons",
    )

    section_title("VoC 드릴다운", "표에서 행을 고르고 Evidence / Trace에서 근거를 확인")
    display_columns = [
        "source_id",
        "raw_row_index",
        "product_category",
        "topic",
        "sentiment_dir",
        "cej",
        "entity_role",
        "rootcause_summary",
        "tee_time_score",
        "tee_effort_score",
        "tee_emotion_score",
        "tee_success_score",
        "confidence_rating",
        "review_required",
        "atomic_voc_summary",
    ]
    if "source_run" in frame.columns:
        display_columns.insert(2, "source_run")
    render_selectable_dataframe(
        frame[display_columns],
        key="overview_voc_drilldown",
        default_columns=display_columns,
    )

    with persistent_expander("Evidence / Trace 상세", key="overview_evidence_trace"):
        detail_columns = [
            "source_id",
            "original_voc",
            "atomic_voc",
            "product_category",
            "topic",
            "topic_evidence",
            "cej_evidence",
            "tee_time_evidence",
            "tee_effort_evidence",
            "tee_emotion_evidence",
            "tee_success_evidence",
            "rootcause_problem",
            "rootcause_target",
            "rootcause_cause",
            "trace_summary",
        ]
        if "source_run" in frame.columns:
            detail_columns.insert(1, "source_run")
        render_selectable_dataframe(
            frame[detail_columns],
            key="overview_evidence_trace",
            default_columns=detail_columns,
        )
