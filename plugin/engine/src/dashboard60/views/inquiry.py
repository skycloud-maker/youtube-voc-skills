"""Inquiry and information-access insight tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard60.charts import bar_chart
from src.dashboard60.data_contract import ensure_dashboard_columns, inquiry_rows
from src.dashboard60.ui_cards import (
    badge,
    metric_card,
    persistent_expander,
    ratio_rows,
    render_metric_grid,
    render_selectable_dataframe,
    section_title,
    task_card_html,
)


INQUIRY_TYPE_LABELS = {
    "feature_spec": "기능/스펙 문의",
    "purchase_path_link": "구매경로/링크 문의",
    "product_comparison": "제품 비교 문의",
    "other_question": "기타 질문",
    "none": "해당없음",
    "N/A": "해당없음",
    "": "해당없음",
}

NEED_SIGNAL_TYPE_LABELS = {
    "feature_need": "기능 니즈",
    "trust_safety_need": "신뢰/안전 니즈",
    "environment_fit_need": "사용환경 적합 니즈",
    "purchase_confidence_need": "구매확신 니즈",
    "none": "해당없음",
    "N/A": "해당없음",
    "": "해당없음",
}


def _display_label(value: object, mapping: dict[str, str]) -> str:
    text = str(value or "").strip()
    return mapping.get(text, text or "해당없음")


def _ratio_payload(series: pd.Series) -> list[tuple[str, int, float, str]]:
    counts = series.fillna("해당없음").replace("", "해당없음").value_counts()
    total = int(counts.sum()) or 1
    return [(str(label), int(count), float(count / total), "") for label, count in counts.items()]


def render(frame: pd.DataFrame) -> None:
    frame = ensure_dashboard_columns(frame)
    st.subheader("문의/정보접근 인사이트")
    inquiry = inquiry_rows(frame).copy()
    for column in ("inquiry_type", "need_signal_type"):
        if column not in inquiry.columns:
            inquiry[column] = pd.Series(dtype="object")
    inquiry["inquiry_type_display"] = inquiry["inquiry_type"].map(lambda value: _display_label(value, INQUIRY_TYPE_LABELS))
    inquiry["need_signal_type_display"] = inquiry["need_signal_type"].map(
        lambda value: _display_label(value, NEED_SIGNAL_TYPE_LABELS)
    )
    total = len(frame)
    inquiry_count = len(inquiry)
    render_metric_grid(
        [
            metric_card("문의형 VoC", f"{inquiry_count:,}", f"{(inquiry_count / total * 100):.1f}%" if total else "0.0%", tone="purple"),
            metric_card("문의 제품군 수", f"{inquiry['product_category'].nunique() if inquiry_count else 0:,}", "product_category", tone="blue"),
            metric_card("문의 Topic 수", f"{inquiry['topic'].nunique() if inquiry_count else 0:,}", "reason topic", tone="green"),
        ]
    )

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        section_title("문의 유형", "문의 목적별 분포")
        inquiry_type = (
            inquiry["inquiry_type_display"]
            .fillna("해당없음")
            .replace("", "해당없음")
            .value_counts()
            .rename_axis("문의 유형")
            .reset_index(name="count")
        )
        if inquiry.empty:
            st.info("현재 필터 조건에서 문의형 VoC가 없습니다.")
        else:
            st.altair_chart(
                bar_chart(inquiry_type, "문의 유형", title="문의 유형 분포", color="문의 유형"),
                width="stretch",
                key="inquiry_type_chart",
            )
            st.markdown(ratio_rows(_ratio_payload(inquiry["inquiry_type_display"])), unsafe_allow_html=True)
    with chart_col2:
        section_title("니즈 신호 유형", "고객이 원하는 것의 유형")
        need_type = (
            inquiry["need_signal_type_display"]
            .fillna("해당없음")
            .replace("", "해당없음")
            .value_counts()
            .rename_axis("니즈 신호 유형")
            .reset_index(name="count")
        )
        if inquiry.empty:
            st.info("현재 필터 조건에서 문의형 VoC가 없습니다.")
        else:
            st.altair_chart(
                bar_chart(need_type, "니즈 신호 유형", title="니즈 신호 유형 분포", color="니즈 신호 유형"),
                width="stretch",
                key="inquiry_need_type_chart",
            )
            st.markdown(ratio_rows(_ratio_payload(inquiry["need_signal_type_display"])), unsafe_allow_html=True)

    section_title("대표 문의 카드", "실무자가 먼저 읽을 문의형 VoC")
    preview = inquiry.head(6)
    if preview.empty:
        st.info("현재 필터 조건에서 문의형 VoC가 없습니다.")
    else:
        cols = st.columns(2)
        for idx, (_, row) in enumerate(preview.iterrows()):
            title = str(row.get("topic") or "N/A")
            preview_text = str(row.get("atomic_voc_summary") or row.get("original_voc") or "")
            with cols[idx % 2]:
                st.markdown(
                    task_card_html(
                        title,
                        [
                            badge(str(row.get("product_category") or "제품군 미확인")),
                            badge(str(row.get("cej") or "CEJ 미확인")),
                            badge(str(row.get("confidence_rating") or "confidence 미확인")),
                        ],
                        preview_text,
                        tone="purple",
                    ),
                    unsafe_allow_html=True,
                )

    columns = [
        "source_id",
        "original_voc",
        "atomic_voc_summary",
        "product_category",
        "topic",
        "cej",
        "inquiry_type_display",
        "need_signal_type_display",
        "sentiment_dir",
        "confidence_rating",
        "review_required",
    ]
    with persistent_expander("문의형 VoC 전체 테이블", key="inquiry_all_table_expander", expanded=True):
        render_selectable_dataframe(
            inquiry[columns].rename(
                columns={
                    "source_id": "source_id",
                    "original_voc": "원문",
                    "atomic_voc_summary": "Atomic 요약",
                    "product_category": "제품군",
                    "topic": "이유 Topic",
                    "cej": "CEJ",
                    "inquiry_type_display": "문의 유형",
                    "need_signal_type_display": "니즈 신호 유형",
                    "sentiment_dir": "감성",
                    "confidence_rating": "신뢰도",
                    "review_required": "사람검토",
                }
            ),
            key="inquiry_all_table",
        )
