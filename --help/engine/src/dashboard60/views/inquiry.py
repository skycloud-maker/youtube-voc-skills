"""Inquiry and information-access insight tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard60.charts import bar_chart, bar_chart_height, stable_color
from src.dashboard60.data_contract import ensure_dashboard_columns, inquiry_rows
from src.dashboard60.ui_cards import (
    badge,
    metric_card,
    persistent_expander,
    ratio_rows,
    render_metric_grid,
    render_selectable_dataframe,
    render_table_download,
    section_title,
    task_card_html,
)


# ★ 여기 있던 사전 복사본을 지웠다 (sky 2026-08-20).
#   두 벌이 따로 놀며 둘 다 허용값의 3분의 1만 담고 있었다.
#   사전은 inquiry_labels.py 한 곳에만 둔다.
from src.dashboard60.inquiry_labels import (  # noqa: E402
    INQUIRY_TYPE_LABELS,
    NEED_SIGNAL_TYPE_LABELS,
)


def _display_label(value: object, mapping: dict[str, str]) -> str:
    text = str(value or "").strip()
    return mapping.get(text, text or "해당없음")


def _ratio_payload(series: pd.Series) -> list[tuple[str, int, float, str]]:
    counts = series.fillna("해당없음").replace("", "해당없음").value_counts()
    total = int(counts.sum()) or 1
    return [(str(label), int(count), float(count / total), "") for label, count in counts.items()]


# ★ 고를 수 있는 정렬 축. 대표 VoC 선정과 같은 축을 첫 항목으로 둔다
INQUIRY_CARD_SORTS = {
    "우선 검토 순": ["review_queue", "topic_score"],
    "VoC 총점 높은 순": ["voc_total_score", "topic_score"],
    "Topic 점수 높은 순": ["topic_score", "voc_total_score"],
}


# ★ 봐야 할 것을 왼쪽으로. source_id 는 사람이 읽는 값이 아니라 맨 뒤다
INQUIRY_TABLE_COLUMNS = [
    "inquiry_type_display",
    "need_signal_type_display",
    "atomic_voc_summary",
    "product_category",
    "topic",
    "cej",
    "sentiment_dir",
    "confidence_rating",
    "review_required",
    "original_voc",
    "source_id",
]

INQUIRY_TABLE_HEADERS = {
    "inquiry_type_display": "문의 유형",
    "need_signal_type_display": "니즈 신호 유형",
    "atomic_voc_summary": "Atomic 요약",
    "product_category": "제품군",
    "topic": "이유 Topic",
    "cej": "CEJ",
    "sentiment_dir": "감성",
    "confidence_rating": "신뢰도",
    "review_required": "사람검토",
    "original_voc": "원문",
    "source_id": "source_id",
}


def _render_inquiry_detail(frame: pd.DataFrame, event) -> None:
    """고른 문의 한 건을 읽을 수 있게 편다 (sky 2026-08-20).

    ★ 원문은 표 안에서 못 읽는다. 가로로 긴 칸이기 때문이다.
      tab1 「RootCause 상세」 와 같은 자리·같은 순서로 둔다.
    """

    try:
        rows = list(event.selection.rows)
    except AttributeError:
        rows = []
    if not rows:
        st.caption("위 표에서 행을 하나 고르면 그 문의의 원문과 판정 근거를 여기서 읽습니다.")
        return
    position = int(rows[0])
    if position >= len(frame):
        return
    row = frame.iloc[position]
    st.markdown(f"### {row.get('topic') or 'Topic 미확인'}")
    st.caption(
        f"{row.get('product_category') or '제품군 미확인'}"
        f" · {row.get('cej') or 'CEJ 미확인'}"
        f" · 신뢰도 {row.get('confidence_rating') or '미확인'}"
    )
    summary_text = str(row.get("atomic_voc_summary") or "").strip()
    if summary_text:
        st.info(summary_text)
    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown("**문의 유형**")
        st.write(str(row.get("inquiry_type_display") or "해당없음"))
    with right:
        st.markdown("**니즈 신호 유형**")
        st.write(str(row.get("need_signal_type_display") or "해당없음"))
    with persistent_expander("원문 보기", key="inquiry_detail_source", expanded=False):
        st.write(str(row.get("original_voc") or "원문이 없습니다."))


def _render_ratio_block(field: str, dist: pd.DataFrame, key: str) -> None:
    """비율을 접이식 안에 넣고 색을 위 그래프와 맞춘다 (sky 2026-08-20).

    ★ 1번 탭과 같은 형태로 통일한다. 색은 같은 출처(stable_color)에서 가져온다.
    """

    total = int(dist["count"].sum()) or 1
    rows = [
        (str(row[field]), int(row["count"]), float(row["count"]) / total, stable_color(str(row[field])))
        for _, row in dist.iterrows()
    ]
    with persistent_expander(f"{field} — 비율 보기", key=key, expanded=False):
        st.markdown(ratio_rows(rows), unsafe_allow_html=True)


def render(frame: pd.DataFrame) -> None:
    frame = ensure_dashboard_columns(frame)
    st.subheader("문의 속 니즈")
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

    # ★ 같은 행 두 그래프의 높이를 맞춘다 (sky 2026-08-20). 1번 탭과 같은 방식.
    #   집계를 열 만들기 「전에」 해야 둘의 필요 높이를 견줄 수 있다
    def _counts(column: str, label: str):
        return (
            inquiry[column]
            .fillna("해당없음")
            .replace("", "해당없음")
            .value_counts()
            .rename_axis(label)
            .reset_index(name="count")
        )

    inquiry_type = _counts("inquiry_type_display", "문의 유형")
    need_type = _counts("need_signal_type_display", "니즈 신호 유형")
    shared_chart_height = max(bar_chart_height(inquiry_type), bar_chart_height(need_type))
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        section_title("문의 유형", "문의 목적별 분포")
        if inquiry.empty:
            st.info("현재 필터 조건에서 문의형 VoC가 없습니다.")
        else:
            st.altair_chart(
                bar_chart(
                    inquiry_type,
                    "문의 유형",
                    title="문의 유형 분포",
                    color="문의 유형",
                    height=shared_chart_height,
                ),
                width="stretch",
                key="inquiry_type_chart",
            )
            _render_ratio_block("문의 유형", inquiry_type, "inquiry_type_ratio")
    with chart_col2:
        section_title("니즈 신호 유형", "고객이 원하는 것의 유형")
        if inquiry.empty:
            st.info("현재 필터 조건에서 문의형 VoC가 없습니다.")
        else:
            st.altair_chart(
                bar_chart(
                    need_type,
                    "니즈 신호 유형",
                    title="니즈 신호 유형 분포",
                    color="니즈 신호 유형",
                    height=shared_chart_height,
                ),
                width="stretch",
                key="inquiry_need_type_chart",
            )
            _render_ratio_block("니즈 신호 유형", need_type, "inquiry_need_ratio")

    # ★ 전에는 정렬이 아예 없었다. inquiry_rows 는 걸러내기만 하므로
    #   head(6) 은 「원본 순서 앞 6개」 였다 (sky 2026-08-20).
    #   기준을 새로 지어내지 않고, 대시보드가 대표 VoC 를 고를 때 이미 쓰는
    #   축(review_queue·topic_score)을 그대로 가져왔다
    sort_choice, count_choice = st.columns([3, 1])
    with sort_choice:
        card_sort = st.selectbox(
            "카드 정렬 기준",
            list(INQUIRY_CARD_SORTS),
            key="inquiry_card_sort",
        )
    with count_choice:
        card_count = st.selectbox(
            "표시 개수",
            [6, 12, 20, "전체"],
            key="inquiry_card_count",
        )
    sort_columns = [column for column in INQUIRY_CARD_SORTS[card_sort] if column in inquiry.columns]
    ordered = inquiry.sort_values(sort_columns, ascending=False) if sort_columns else inquiry
    preview = ordered if card_count == "전체" else ordered.head(int(card_count))
    section_title(
        "대표 문의 카드",
        f"{card_sort} · {len(preview)}개 표시 / 문의형 전체 {len(inquiry)}건"
        " · 카드 하나가 VoC 「한 건」 이다 (같은 주제를 묶은 것이 아님)",
    )
    if preview.empty:
        st.info("현재 필터 조건에서 문의형 VoC가 없습니다.")
    else:
        # ★ min_height 어림값을 뺐다 (sky 2026-08-20). 영상 탭과 같은 이유 —
        #   CSS 가 줄 수를 못 박고 있어 어림값은 흰 여백만 만든다
        records = list(preview.iterrows())
        # ★ 행마다 st.columns 를 새로 만든다 (sky 2026-08-20).
        #   한 번 만들어 놓고 idx % 2 로 나눠 담으면 열마다 카드가 세로로 쌓여,
        #   카드 높이가 조금만 달라도 둘째 행부터 좌우가 어긋난다.
        #   행마다 만들면 다음 행은 늘 이전 행에서 가장 큰 것 아래에서 시작한다.
        cols = None
        for idx, (_, row) in enumerate(records):
            if idx % 2 == 0:
                cols = st.columns(2)
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

    # ★ 이 탭의 주제는 문의 유형·니즈 유형인데 표에서는 일곱째·여덟째 칸이었고,
    #   맨 앞은 사람이 읽지 않는 source_id 였다 (sky 2026-08-20).
    #   주제를 왼쪽으로 올리고 식별자는 맨 뒤로 보낸다
    section_title(
        "문의형 VoC 체크",
        f"행을 고르면 그 문의의 원문과 판정 근거를 아래에서 읽습니다"
        f" · 위 카드는 고른 기준으로 몇 건만, 이 표는 {len(inquiry)}건 전부",
    )
    type_options = sorted(inquiry["inquiry_type_display"].dropna().unique())
    picked_types = st.multiselect(
        "문의 유형으로 거르기",
        type_options,
        default=[],
        key="inquiry_table_type_filter",
        help="비워 두면 전부 봅니다.",
    )
    table_source = inquiry[inquiry["inquiry_type_display"].isin(picked_types)] if picked_types else inquiry
    if picked_types:
        st.caption(f"{len(table_source):,}건 / 문의형 전체 {len(inquiry):,}건")
    table_frame = table_source[INQUIRY_TABLE_COLUMNS].rename(columns=INQUIRY_TABLE_HEADERS)
    inquiry_event = render_selectable_dataframe(
        table_frame,
        key="inquiry_all_table",
        default_columns=list(table_frame.columns),
        on_select="rerun",
        selection_mode="single-row",
    )
    render_table_download(
        table_frame,
        key="inquiry_all_table",
        label="문의형 VoC 통째로 받기",
        file_stem="문의형VoC",
        note=(
            "지금 걸린 사이드바 필터와 「문의 유형으로 거르기」 가 그대로 반영됩니다. "
            "화면에서 숨긴 칸도 전부 들어갑니다. "
            "사용자명·이메일·링크는 가려진 판본입니다."
        ),
    )
    with st.container(border=True):
        section_title("문의 상세", "고른 행의 원문과 판정 근거")
        _render_inquiry_detail(table_source, inquiry_event)
