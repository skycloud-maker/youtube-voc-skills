"""Video-level summary tab."""

from __future__ import annotations

import json
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from src.dashboard60.charts import NEUTRAL_TEXT, stable_color
from src.dashboard60.data_contract import ensure_dashboard_columns, video_summary
from src.dashboard60.ui_cards import (
    badge,
    metric_card,
    persistent_expander,
    render_metric_grid,
    render_selectable_dataframe,
    render_table_download,
    section_title,
    task_card_html,
)


def _video_color_map(summary: pd.DataFrame) -> dict[str, str]:
    titles = summary["video_title"].replace("", pd.NA).fillna(summary["video_id"]).astype(str)
    return {title: stable_color(title) for title in titles.drop_duplicates()}


def _video_metric_chart(summary: pd.DataFrame, metric: str, title: str, color_map: dict[str, str]) -> alt.Chart:
    # ★ 여기서 또 자르지 않는다. 몇 개를 그릴지는 부르는 쪽이 정한다.
    #   head(15) 가 두 군데 있어, 20개를 넘겨도 이 함수가 다시 15로 잘랐다
    chart_frame = summary.copy()
    chart_frame["video_title"] = chart_frame["video_title"].replace("", pd.NA).fillna(chart_frame["video_id"])
    # ★ 영상 제목이 100자를 넘는다. 자르지 않으면 라벨이 그래프 폭을 통째로 먹어
    #   막대 그릴 자리가 남지 않는다 (sky 2026-08-20). 축에 쓸 짧은 이름을 따로 만든다
    chart_frame["축이름"] = chart_frame["video_title"].astype(str).map(
        lambda value: value if len(value) <= 24 else value[:23] + "…"
    )
    domain = list(color_map)
    # ★ 층이 둘(막대 + 값 글자)이면 EncodingSortField 가 안 먹는다.
    #   bar_chart 에서 이미 두 번 겪은 자리다. 순서를 목록으로 그대로 넘긴다
    row_sort = chart_frame.sort_values(metric, ascending=False)["축이름"].astype(str).tolist()
    y = alt.Y(
        "축이름:N",
        sort=row_sort,
        title=None,
        axis=alt.Axis(labelLimit=240, labelPadding=8),
    )
    # ★ 축은 0~100% 로 고정한다 (sky 2026-08-20).
    #   세 그래프가 나란히 있어, 축을 각자 맞추면 「문의율 50%」 와 「부정률 100%」 가
    #   같은 길이로 그려져 잘못 읽힌다. 빈 자리가 곧 정보다.
    # ★ 1.04 까지 넓힌 이유 — 100% 눈금선이 그림 오른쪽 테두리와 겹쳐 안 보였다.
    #   테마가 테두리를 그리지 않기 때문이다(configure_view(stroke=None))
    x = alt.X(
        f"{metric}:Q",
        title="비율",
        scale=alt.Scale(domain=[0, 1.04], nice=False),
        axis=alt.Axis(format="%", values=[0, 0.2, 0.4, 0.6, 0.8, 1.0]),
    )
    base = alt.Chart(chart_frame)
    bars = base.mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4).encode(
        y=y,
        x=x,
        # ★ 범례를 끈다. y축에 이름이 이미 있어 중복이고, 긴 제목이 공간을 다 먹는다
        color=alt.Color(
            "video_title:N",
            scale=alt.Scale(domain=domain, range=[color_map[item] for item in domain]),
            legend=None,
            title=None,
        ),
        tooltip=["video_title", "comment_count", alt.Tooltip(f"{metric}:Q", title=title, format=".1%")],
    )
    # ★ 막대 끝에 값을 적는다. 축이 100% 고정이라 문의율처럼 작은 값은
    #   막대만으로는 안 보인다 (중앙값 3.2%). 숫자가 있으면 읽힌다
    labels = base.mark_text(dx=6, align="left", fontSize=12, fontWeight="bold", color=NEUTRAL_TEXT).encode(
        y=alt.Y("축이름:N", sort=row_sort, title=None),
        x=alt.X(f"{metric}:Q", scale=alt.Scale(domain=[0, 1.04], nice=False), title="비율"),
        text=alt.Text(f"{metric}:Q", format=".1%"),
    )
    return (bars + labels).properties(
        # ★ 상한 620 이면 15개까지만 담긴다. 전체를 골라도 라벨이 눌렸다
        height=max(260, min(2400, 120 + len(chart_frame) * 42)),
        # ★ 여백은 「문의 유형 분포」(bar_chart 가로 갈래)와 같은 44 로 맞춘다
        padding={"top": 12, "bottom": 12, "left": 8, "right": 44},
    )


# ★ 고를 수 있는 정렬 축. video_summary 가 본래 쓰던 순서를 첫 항목으로 둔다
VIDEO_CARD_SORTS = {
    "부정률 높은 순": ["negative_rate", "inquiry_rate", "comment_count"],
    "문의율 높은 순": ["inquiry_rate", "negative_rate", "comment_count"],
    "댓글 많은 순": ["comment_count", "negative_rate", "inquiry_rate"],
}


# 표에 쓸 한국어 칸이름. 봐야 할 것을 왼쪽에 두는 순서와 짝이다
VIDEO_TABLE_HEADERS = {
    "video_title": "영상 제목",
    "comment_count": "댓글 수",
    "negative_count": "부정 건수",
    "negative_rate": "부정률",
    "inquiry_count": "문의 건수",
    "inquiry_rate": "문의율",
    "positive_count": "긍정 건수",
    "positive_rate": "긍정률",
    "main_product_category": "주요 제품군",
    "main_product_note": "제품군 구성",
    "main_product_hint": "추정 제품",
    "main_brand": "주요 브랜드",
    "main_brand_note": "브랜드 구성",
    "video_url": "링크",
    "video_id": "영상 ID",
}


def _breakdown(value: object) -> list[tuple[str, int]]:
    """집계해 둔 「이름·건수」 쌍을 되읽는다."""

    try:
        pairs = json.loads(str(value or "[]"))
    except (TypeError, ValueError):
        return []
    return [(str(name), int(number)) for name, number in pairs]


def _pretty_name(name: str) -> str:
    """화면에 데이터 값을 그대로 두지 않는다 (sky 2026-08-20)."""

    text = str(name or "").strip()
    return "미상" if text in ("", "N/A", "nan", "none", "None") else text


def _subject_rows(row) -> int:
    """이 카드의 파란 박스가 몇 줄을 쓰는가 — 좌우 칸 중 많은 쪽."""

    return max(
        len(_breakdown(row.get("main_product_breakdown"))) or 1,
        len(_breakdown(row.get("main_brand_breakdown"))) or 1,
    )


def _subject_html(row, line_count: int | None = None) -> str:
    """파란 박스 — 왼쪽 제품군, 오른쪽 브랜드 (sky 2026-08-20).

    ★ 첫 줄이 주요, 그 아래로 나머지를 한 줄씩 적는다.
      「그 외 N종」 은 무엇인지 알 수 없어 쓸모가 없었다.
    ★ 분모(전체 댓글 수)는 카드 위 배지에 이미 있어 건수만 적는다.
    ★ preview_html 로 넘기므로 값은 여기서 직접 escape 한다.
    """

    hint = _pretty_name(row.get("main_product_hint")) if str(row.get("main_product_hint") or "").strip() else ""
    columns = []
    for label, key, is_product in (
        ("주요 제품군", "main_product_breakdown", True),
        ("주요 브랜드", "main_brand_breakdown", False),
    ):
        pairs = _breakdown(row.get(key))
        if not pairs:
            body = '<div class="d60-subject-sub">판정되지 않음</div>'
        else:
            rows_html = []
            for index, (name, number) in enumerate(pairs):
                text = _pretty_name(name)
                if index == 0 and is_product and hint:
                    text += f" (추정 {hint})"
                style = "d60-subject-main" if index == 0 else "d60-subject-sub"
                rows_html.append(
                    f'<div class="{style}" title="{escape(text)}">'
                    f'{escape(text)} {number:,}건</div>'
                )
            body = "".join(rows_html)
        columns.append(
            f'<div class="d60-subject-col">'
            f'<div class="d60-subject-label">{escape(label)}</div>{body}</div>'
        )
    # ★ 같은 행 두 카드에 같은 줄 수를 주면 박스 높이가 맞는다.
    #   라벨 16 + 아래여백 4 + 줄 수 × 20 + 위아래 패딩 20 + 테두리 2
    rows = line_count or _subject_rows(row)
    height = 42 + rows * 20
    return (
        f'<div class="d60-subject" style="min-height:{height}px">'
        f'{"".join(columns)}</div>'
    )


def _render_video_detail(frame: pd.DataFrame, event) -> None:
    """고른 영상 한 개를 읽을 수 있게 편다 (sky 2026-08-20).

    ★ 태그·설명은 표 안에서는 못 읽는다. 가로로 긴 칸이기 때문이다.
      카드에 접혀 있던 「이 영상은 무엇을 다루나」 와 같은 내용을 여기서도 준다.
    ★ 제품군·브랜드는 카드와 같은 두 박스로 보여준다. 형태가 다르면
      같은 내용을 두 가지 모양으로 읽게 된다 (sky 2026-08-20).
    """

    try:
        rows = list(event.selection.rows)
    except AttributeError:
        rows = []
    if not rows:
        st.caption("위 표에서 영상을 하나 고르면 그 영상의 제품군·브랜드와 태그·설명을 여기서 읽습니다.")
        return
    position = int(rows[0])
    if position >= len(frame):
        return
    row = frame.iloc[position]
    st.markdown(f"### {row.get('video_title') or row.get('video_id') or '영상 미확인'}")
    # ★ 비율 옆에 건수를 같이 적는다. 카드와 같은 규칙이다 (sky 2026-08-20)
    st.caption(
        f"댓글 {int(row.get('comment_count', 0) or 0):,}건"
        f" · 부정 {int(row.get('negative_count', 0) or 0):,}건 {row.get('negative_rate', '')}"
        f" · 문의 {int(row.get('inquiry_count', 0) or 0):,}건 {row.get('inquiry_rate', '')}"
        f" · 긍정 {int(row.get('positive_count', 0) or 0):,}건 {row.get('positive_rate', '')}"
    )
    # ★ 카드와 같은 두 박스를 쓴다
    st.markdown(_subject_html(row), unsafe_allow_html=True)
    st.divider()
    description = str(row.get("video_description") or "").strip()
    tags = str(row.get("video_tags") or "").strip()
    left, right = st.columns(2)
    with left:
        st.markdown("**영상 설명**")
        st.write(description or "기록된 설명이 없습니다.")
    with right:
        st.markdown("**태그**")
        st.write(tags or "기록된 태그가 없습니다.")
    if row.get("video_url"):
        st.link_button("영상 열기", str(row["video_url"]))


def render(frame: pd.DataFrame) -> None:
    frame = ensure_dashboard_columns(frame)
    st.subheader("분석 영상 정보")
    st.caption("영상별 댓글 수, 긍정률, 부정률, 문의율과 주요 제품군·브랜드를 66컬럼 결과에서 집계합니다.")
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

    # ★ 댓글 1~2건짜리 영상이 부정률 100% 로 카드 1위에 오고 있었다 (sky 2026-08-20).
    #   한 건으로 100% 는 비율이라 부를 수 없다. 하한을 5로 둔다.
    #   실측(영상 16개): 평균 32.9 를 쓰면 62% 가 잘린다. 쏠림이 심해 평균은
    #   커트라인으로 못 쓴다. 5 면 문제되는 것(1건·1건·1건·4건)만 걷힌다.
    # ★ 잘려 나간 것도 「혹시 뭐라도 있나」 볼 수 있어야 해서
    #   그것만 따로 보는 체크상자를 옆에 뒀다 (sky 2026-08-20)
    floor_col, only_col = st.columns([1, 2])
    with floor_col:
        min_comments = st.number_input(
            "최소 댓글 수",
            min_value=1,
            value=5,
            step=1,
            key="video_min_comments",
            help="댓글이 적으면 비율이 크게 흔들린다. 1건 중 1건이 부정이면 부정률 100% 다.",
        )
    thin = summary[summary["comment_count"] < int(min_comments)]
    with only_col:
        thin_only = st.checkbox(
            f"댓글 {int(min_comments)}건 미만인 영상만 보기 ({len(thin)}개)",
            key="video_thin_only",
            help="비율은 못 믿어도 내용은 볼 만할 수 있다. 잘려 나간 것을 확인하는 자리다.",
        )
    if thin_only:
        if thin.empty:
            st.info(f"댓글 {int(min_comments)}건 미만인 영상이 없습니다.")
            return
        st.warning(
            f"댓글 {int(min_comments)}건 미만인 영상 {len(thin)}개만 보고 있습니다."
            " 표본이 적어 비율은 믿을 수 없습니다 — 내용만 참고하세요."
        )
        summary = thin
    else:
        kept = summary[summary["comment_count"] >= int(min_comments)]
        if kept.empty:
            st.warning(f"댓글 {int(min_comments)}건 이상인 영상이 없습니다. 값을 낮춰 주세요.")
        else:
            if len(kept) < len(summary):
                st.caption(
                    f"영상 {len(kept)}개 / 전체 {len(summary)}개"
                    f" · 댓글 {int(min_comments)}건 미만 {len(thin)}개는 옆 상자로 따로 봅니다"
                )
            summary = kept

    # ★ 무엇을 몇 개 볼지 고를 수 있게 한다 (sky 2026-08-20).
    #   전에는 부정률 순 4개로 고정이었고, 그 기준이 화면에 적혀 있지도 않았다
    sort_choice, count_choice = st.columns([3, 1])
    with sort_choice:
        video_sort = st.selectbox(
            "카드 정렬 기준",
            list(VIDEO_CARD_SORTS),
            key="video_card_sort",
        )
    with count_choice:
        video_count = st.selectbox(
            "표시 개수",
            [4, 8, 12, "전체"],
            key="video_card_count",
        )
    ordered = summary.sort_values(VIDEO_CARD_SORTS[video_sort], ascending=False)
    top_videos = ordered if video_count == "전체" else ordered.head(int(video_count))
    section_title(
        "영상별 리스트 카드",
        f"{video_sort} · {len(top_videos)}개 표시 / 전체 {len(summary)}개"
        " · 카드 아래 줄은 그 영상 댓글에서 가장 많이 나온 제품군·브랜드",
    )
    # ★ min_height 어림값을 뺐다 (sky 2026-08-20).
    #   CSS 로 줄 수를 못 박은 뒤로는(제목 2줄·미리보기 3줄·배지 한 줄)
    #   카드 높이가 내용과 무관하게 같아진다. 어림값까지 얹으니 아래가 텅 비었다
    records = list(top_videos.iterrows())
    # ★ 같은 행 두 카드의 파란 박스 줄 수를 맞춘다 (sky 2026-08-20).
    #   항목 수가 달라 박스 높이가 어긋나고 있었다(실측 238 vs 247).
    #   한 항목이 한 줄이라 줄 수는 정확히 셀 수 있다 — 어림값이 아니다
    subject_lines: dict[int, int] = {}
    for start in range(0, len(records), 2):
        pair = records[start:start + 2]
        shared = max(_subject_rows(item) for _, item in pair)
        for offset in range(len(pair)):
            subject_lines[start + offset] = shared
    # ★ 행마다 st.columns 를 새로 만든다 (sky 2026-08-20).
    #   한 번 만들어 놓고 idx % 2 로 나눠 담으면 열마다 카드가 세로로 쌓여,
    #   카드 높이가 조금만 달라도 둘째 행부터 좌우가 어긋난다.
    #   행마다 만들면 다음 행은 늘 이전 행에서 가장 큰 것 아래에서 시작한다.
    video_cols = None
    for idx, (_, row) in enumerate(records):
        if idx % 2 == 0:
            video_cols = st.columns(2)
        positive_rate = float(row.get("positive_rate", 0) or 0)
        negative_rate = float(row.get("negative_rate", 0) or 0)
        inquiry_rate = float(row.get("inquiry_rate", 0) or 0)
        tone = "red" if negative_rate >= 0.3 else "green" if positive_rate >= 0.3 else "purple" if inquiry_rate >= 0.3 else "blue"
        title = str(row.get("video_title") or row.get("video_id") or "영상 미확인")
        card = task_card_html(
            title,
            [
                badge(f"댓글 {int(row.get('comment_count', 0) or 0):,}건"),
                # ★ 비율만 적으면 「부정 100%」 가 커 보이는데 실은 1건 중
                #   1건일 수 있다. 건수를 앞에 같이 적는다 (sky 2026-08-20)
                badge(f"긍정 {int(row.get('positive_count', 0) or 0):,}건 {positive_rate * 100:.1f}%", tone="positive" if positive_rate else "neutral"),
                badge(f"부정 {int(row.get('negative_count', 0) or 0):,}건 {negative_rate * 100:.1f}%", tone="negative" if negative_rate else "neutral"),
                badge(f"문의 {int(row.get('inquiry_count', 0) or 0):,}건 {inquiry_rate * 100:.1f}%", tone="warning" if inquiry_rate else "neutral"),
            ],
            tone=tone,
            preview_html=_subject_html(row, subject_lines.get(idx)),
        )
        with video_cols[idx % 2]:
            st.markdown(card, unsafe_allow_html=True)
            # D-7 — 이 영상이 무엇을 다룬 영상인지. 댓글만 보면 맥락을 모른다 (sky)
            description = str(row.get("video_description") or "").strip()
            tags = str(row.get("video_tags") or "").strip()
            # ★ 값이 없어도 접이식을 그린다. 안 그리면 그 열만 짧아져
            #   다음 행 카드가 위로 당겨진다 (sky 2026-08-20)
            with persistent_expander(
                "이 영상은 무엇을 다루나",
                key=f"video_context_{idx}",
                expanded=False,
            ):
                if description:
                    st.markdown("**영상 설명**")
                    st.write(description)
                if tags:
                    st.markdown("**태그**")
                    st.write(tags)
                if not description and not tags:
                    st.caption("이 영상에는 기록된 설명·태그가 없습니다.")
            if row.get("video_url"):
                st.link_button("영상 열기", str(row["video_url"]))

    # ★ 그래프도 카드의 「표시 개수」 를 따른다 (sky 2026-08-20).
    #   15개로 박혀 있어 카드와 다른 영상을 보여줄 수 있었다
    chart_frame = top_videos.copy()
    chart_frame["video_title"] = chart_frame["video_title"].replace("", pd.NA).fillna(chart_frame["video_id"])
    color_map = _video_color_map(chart_frame)
    # ★ 상위 15개만 그린다. 화면에 그 말이 없으면 영상이 늘었을 때
    #   빠진 것을 모른 채 본다 (sky 2026-08-20).
    # ★ 「어느 15개를 뽑았나」 와 「그 안에서 어떤 순서로 그리나」 는 다르다.
    #   뽑기는 부정률 순, 그리기는 각 그래프가 자기 값 순이다.
    #   앞의 것만 적었더니 긍정률 그래프에 「부정률 높은 순」 이라 붙었다
    chart_note = (
        f"{video_sort} {len(chart_frame)}개 영상 / 전체 {len(summary)}개"
        " · 막대는 각 그래프의 값이 큰 순"
    )
    section_title("영상별 부정률", chart_note)
    st.altair_chart(
        _video_metric_chart(chart_frame, "negative_rate", "부정률", color_map),
        width="stretch",
        key="video_negative_rate_chart",
    )
    section_title("영상별 긍정률", chart_note)
    st.altair_chart(
        _video_metric_chart(chart_frame, "positive_rate", "긍정률", color_map),
        width="stretch",
        key="video_positive_rate_chart",
    )
    section_title("영상별 문의율", chart_note)
    st.altair_chart(
        _video_metric_chart(chart_frame, "inquiry_rate", "문의율", color_map),
        width="stretch",
        key="video_inquiry_rate_chart",
    )

    display = summary.copy()
    for column in ("positive_rate", "negative_rate", "inquiry_rate"):
        display[column] = (display[column] * 100).round(1).astype(str) + "%"
    # ★ tab1 「개별 VoC 개선 포인트 체크」 와 같은 꼴로 맞춘다 (sky 2026-08-20).
    #   봐야 할 칸을 왼쪽으로 옮기고, 행을 고르면 아래에서 상세를 읽는다.
    #   video_id 는 사람이 읽는 값이 아니라 맨 뒤로 보낸다
    section_title(
        "영상별 집계 체크",
        f"행을 고르면 그 영상의 태그·설명과 대표 VoC 를 아래에서 읽습니다"
        f" · 위 카드·그래프는 상위 몇 개만, 이 표는 {len(summary)}개 전부",
    )
    video_columns = [
        "video_title",
        "comment_count",
        "negative_count",
        "negative_rate",
        "inquiry_count",
        "inquiry_rate",
        "positive_count",
        "positive_rate",
        "main_product_category",
        "main_product_hint",
        "main_product_note",
        "main_brand",
        "main_brand_note",
        "video_url",
        "video_id",
    ]
    table_frame = display[video_columns].rename(columns=VIDEO_TABLE_HEADERS)
    video_event = render_selectable_dataframe(
        table_frame,
        key="video_summary_table",
        default_columns=list(table_frame.columns),
        on_select="rerun",
        selection_mode="single-row",
    )
    render_table_download(
        table_frame,
        key="video_summary_table",
        label="영상별 집계 통째로 받기",
        file_stem="영상별집계",
    )
    with st.container(border=True):
        section_title("영상 상세", "고른 영상의 제품군·브랜드와 맥락")
        _render_video_detail(display, video_event)
