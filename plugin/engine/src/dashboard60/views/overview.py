"""VoC overview and drilldown tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard60.charts import SENTIMENT_COLORS, bar_chart, bar_chart_height, group_pick_chart, stable_color
from src.dashboard60.data_contract import (
    TOPIC_GROUP_VALUE_KEY,
    ensure_dashboard_columns,
    scope_exclusion_reason_distribution,
    topic_distribution,
    topic_group_distribution,
)
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
            # D-5 — 2차가 나눈 행. 행 수가 늘어난 이유를 여기서 알 수 있어야 한다
            metric_card(
                "2차 분리 행",
                f"{int(_split_series(frame).sum()):,}",
                "한 댓글에 주제가 여럿이라 나눈 것",
                tone="purple",
            ),
        ]
    )


def _ratio_payload(series: pd.Series, *, tone_map: dict[str, str] | None = None) -> list[tuple[str, int, float, str]]:
    counts = series.fillna("N/A").replace("", "N/A").value_counts()
    total = int(counts.sum()) or 1
    tone_map = tone_map or {}
    return [(str(label), int(count), float(count / total), tone_map.get(str(label), "")) for label, count in counts.items()]


# 그래프가 직전에 무엇을 고르고 있었는지. 「바뀌었는가」를 판단하는 데만 쓴다
_LAST_PICK_KEY = "overview_topic_group_last_pick"


def _render_topic_group_picker(group_source: pd.DataFrame | None) -> None:
    """맨 위에 영역 그래프를 넓게 놓고, 막대를 누르면 필터가 걸리게 한다 (D-1b).

    sky 2026-08-19 — "그래프의 막대를 눌러도 개선/강화 영역의 필터가 동작하게끔…
    오히려 우측 필터보다 직관적으로 보고 싶은 걸 눌렀다가 원복시키는 버튼으로"

    ★ group_source 는 「영역 필터만 빼고」 나머지 필터를 적용한 집합이다.
      지금 보고 있는 영역만 그리면 다른 영역으로 옮겨갈 수가 없기 때문이다.
    """

    if group_source is None or "topic_group" not in group_source.columns:
        return
    dist = topic_group_distribution(group_source)
    if dist.empty:
        return
    selected = list(st.session_state.get(TOPIC_GROUP_VALUE_KEY) or [])
    now = " · ".join(selected) if selected else "전체"
    head, reset = st.columns([5, 1])
    with head:
        section_title(
            "개선/강화 영역",
            "막대를 누르면 그 영역만 봅니다.  ·  Shift+클릭으로 여러 영역을 함께 고릅니다."
            "  ·  사이드바 필터와 같은 값을 씁니다.  ·  지금: " + now,
        )
    with reset:
        if st.button(
            "전체 보기",
            key="overview_topic_group_reset",
            disabled=not selected,
            # ★ use_container_width 는 2025-12-31 자로 없어지는 이름이다.
            #   아직 돌지만 streamlit 을 올리면 화면이 깨진다 (sky 2026-08-20)
            width="stretch",
        ):
            st.session_state[TOPIC_GROUP_VALUE_KEY] = []
            # ★ 그래프가 들고 있는 선택도 같이 지운다.
            #   안 지우면 다음 실행에서 옛 선택을 다시 뱉어 필터가 되살아난다
            st.session_state.pop("overview_topic_group_chart", None)
            st.session_state.pop(_LAST_PICK_KEY, None)
            st.rerun()
    event = st.altair_chart(
        group_pick_chart(dist, selected),
        width="stretch",  # ★ use_container_width 는 없어지는 이름이다 (위 설명 참고)
        on_select="rerun",
        key="overview_topic_group_chart",
    )
    picked: list[str] = []
    try:
        picked = [
            str(item.get("topic_group"))
            for item in (event.selection.get("pick") or [])
            if item.get("topic_group")
        ]
    except AttributeError:
        picked = []
    # ★ 「고른 게 있는가」가 아니라 「그래프 선택이 바뀌었는가」로 판단한다.
    #   앞엣것으로 하면 Shift+클릭으로 전부 해제했을 때 아무 일도 안 일어난다.
    #   같은 값을 다시 넣고 rerun 하면 무한 반복이 되므로 직전값과 견준다.
    previous = st.session_state.get(_LAST_PICK_KEY)
    st.session_state[_LAST_PICK_KEY] = picked
    if previous is not None and sorted(picked) != sorted(previous):
        if sorted(picked) != sorted(selected):
            st.session_state[TOPIC_GROUP_VALUE_KEY] = picked
            st.rerun()


def _ratio_from_dist(dist: pd.DataFrame, field: str, color_map: dict[str, str] | None) -> list:
    """포션(비율 줄) 자료. 색을 위 막대와 똑같이 맞춘다 (sky 2026-08-19)."""

    total = int(dist["count"].sum()) or 1
    rows = []
    for _, row in dist.iterrows():
        label = str(row[field])
        color = (color_map or {}).get(label) or stable_color(label)
        rows.append((label, int(row["count"]), float(row["count"]) / total, color))
    return rows


def _render_chart_row(frame: pd.DataFrame, *, left: tuple, right: tuple) -> None:
    """같은 행 두 그래프를 같은 높이로 그리고, 포션은 접어 둔다.

    ★ 높이가 서로 달라 균형이 깨졌다 (sky 2026-08-19). 둘 중 큰 값을 양쪽에 같이 준다.
    ★ 포션이 길어 화면을 밀어내므로 접었다 펼 수 있게 한다.
    """

    shared_height = max(bar_chart_height(left[2]), bar_chart_height(right[2]))
    columns = st.columns(2)
    for column, (title, note, dist, field, chart_key, color_map) in zip(columns, (left, right)):
        with column:
            section_title(title, note)
            st.altair_chart(
                bar_chart(dist, field, title=title, color=field, color_map=color_map, height=shared_height),
                width="stretch",
                key=chart_key,
            )
            with persistent_expander(
                f"{title} — 비율 보기", key=f"{chart_key}_ratio", expanded=False
            ):
                st.markdown(
                    ratio_rows(_ratio_from_dist(dist, field, color_map)),
                    unsafe_allow_html=True,
                )


def _text_of(row, column: str) -> str:
    value = row.get(column) if hasattr(row, "get") else None
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "n/a", "미분류") else text


# rootcause_summary 값 앞에 붙는 등급. 원문에 무엇까지 적혀 있었는지를 뜻한다
#   L3 문제·대상·원인이 모두 원문에 있다      L2 원인 서술만 없다
#   L1 개선 대상이 원문에 없다                L0 결핍 서술이 없어 R14 Gate1 미통과
ROOTCAUSE_GRADE_NOTE = {
    "L3": "L3 · 문제·대상·원인이 모두 원문에 있다",
    "L2": "L2 · 원인 서술만 원문에 없다",
    "L1": "L1 · 개선 대상이 원문에 없다",
    "L0": "L0 · 원문에 결핍 서술이 없다",
}


def _split_origin(row) -> str:
    """이 행이 2차에서 나뉜 것이면 원행 id, 아니면 빈 문자열 (D-5)."""

    return _text_of(row, "split_origin_atomic_id")


def _split_series(frame: pd.DataFrame):
    """분리로 생긴 행인지 여부. 칸이 없으면 전부 False."""

    if "split_origin_atomic_id" not in frame.columns:
        return pd.Series(False, index=frame.index)
    text = frame["split_origin_atomic_id"].fillna("").astype(str).str.strip()
    return ~text.isin(("", "nan", "None", "N/A"))


def _rootcause_grade(row) -> str:
    summary = _text_of(row, "rootcause_summary")
    code = summary[:2] if summary[:2] in ROOTCAUSE_GRADE_NOTE else ""
    return ROOTCAUSE_GRADE_NOTE.get(code, "")


def _render_row_detail(frame: pd.DataFrame, event) -> None:
    """고른 행을 4층 구조로 읽게 한다 (D-3).

    영역 → 주제 → 요약문 → 근본원인. sky 가 정한 층이다 (CP-23).
    ★ 요약문(atomic_voc_summary)은 표에도 칸으로 있었지만, 가로로 긴 표에서
      33자짜리 문장을 읽기는 어렵다. 없던 것은 「읽을 수 있는 자리」였다.
    """

    rows = []
    try:
        rows = list(event.selection.rows)
    except AttributeError:
        rows = []
    if not rows:
        st.caption("위 표에서 행을 하나 고르면 그 VoC 의 요약문과 RootCause 를 여기서 읽습니다.")
        return
    position = int(rows[0])
    if position >= len(frame):
        return
    row = frame.iloc[position]

    head = " · ".join(
        value
        for value in (
            _text_of(row, "product_category"),
            _text_of(row, "topic_group"),
            _text_of(row, "topic"),
        )
        if value
    )
    grade = _rootcause_grade(row)
    st.markdown(f"### {head}" if head else "### (라벨 없음)")
    # D-5 — 나뉜 행이면 원행과의 관계를 알려준다
    origin = _split_origin(row)
    split_note = ""
    if origin:
        siblings = 0
        if "split_origin_atomic_id" in frame.columns:
            siblings = int((frame["split_origin_atomic_id"].fillna("").astype(str).str.strip() == origin).sum())
        split_note = f"2차 분리 · 원행 {origin}" + (f" · 형제 {siblings}개" if siblings > 1 else "")
    meta = [value for value in (grade, split_note, _text_of(row, "decided_by")) if value]
    if meta:
        st.caption("  ·  ".join(meta))

    # ★ 「요약문」 이라는 말을 박스 안에 넣는다. 밖에 두면 무엇의 제목인지 흐리다 (sky)
    summary = _text_of(row, "atomic_voc_summary")
    st.info(f"**요약문**\n\n{summary}" if summary else "**요약문**\n\n비어 있습니다.")

    # ★ topic_evidence(원문 근거)도 뺐다 (sky 2026-08-19).
    #   그것은 「주제」 를 고른 근거이지 RC 의 근거가 아니다. RC 에는 근거 칸이 없다.
    #   실제로 주제와 RC 가 서로 다른 대목을 가리키는 행이 있어 오히려 헷갈렸다.
    #   원문은 아래 「원문 보기」 에 그대로 있다.

    problem = _text_of(row, "rootcause_problem")
    target = _text_of(row, "rootcause_target")
    cause = _text_of(row, "rootcause_cause")
    if problem or target or cause:
        # ★ 「근본원인」 이라는 글자 대신 선을 긋는다. 아래 세 칸이 곧 그것이다 (sky)
        st.divider()
        cols = st.columns(3)
        # ★ 데이터사전 정의 그대로 쓴다. 내가 지어낸 「무엇이/어디가/왜」 는
        #   실제 내용과 어긋났다 (sky 2026-08-19)
        labelled = (("문제 현상", problem), ("개선 대상", target), ("근본 원인", cause))
        for column, (label, value) in zip(cols, labelled):
            with column:
                st.markdown(f"**{label}**")
                st.write(value or "—")
    else:
        st.divider()
        st.caption("이 행에는 RootCause 가 채워져 있지 않습니다.")

    with persistent_expander("원문 보기", key="overview_row_detail_source", expanded=False):
        # D-7 — 어떤 영상 밑에 달린 말인지. 댓글만 보면 맥락을 모른다 (sky 2026-08-19)
        video_title = _text_of(row, "video_title")
        video_description = _text_of(row, "video_description")
        if video_title or video_description:
            st.markdown("**어떤 영상 밑의 말인가**")
            if video_title:
                st.write(video_title)
            if video_description:
                st.caption(video_description[:200])
        atomic = _text_of(row, "atomic_voc")
        original = _text_of(row, "original_voc")
        if atomic and atomic != original:
            st.markdown("분리된 조각")
            st.write(atomic)
        st.markdown("원문")
        st.write(original or "—")


def render(
    frame: pd.DataFrame,
    *,
    group_source: pd.DataFrame | None = None,
    scope_source: pd.DataFrame | None = None,
) -> None:
    frame = ensure_dashboard_columns(frame)
    st.subheader("VoC 현황")
    st.caption("topic은 제품군·감성과 분리된 이유 라벨이며, 감성은 TEE/S 기반 sentiment_dir로 별도 표시합니다.")
    _render_metric_cards(frame)
    _render_topic_group_picker(group_source)
    _render_chart_row(
        frame,
        left=(
            "Reason Topic 분포",
            "상위 15개",
            topic_distribution(frame).head(15),
            "topic",
            "overview_topic_distribution_chart",
            None,
        ),
        right=(
            "감성 분포",
            "TEE/S 기반 긍정·부정·중립",
            frame["sentiment_dir"].value_counts().rename_axis("sentiment_dir").reset_index(name="count"),
            "sentiment_dir",
            "overview_sentiment_distribution_chart",
            SENTIMENT_COLORS,
        ),
    )
    _render_chart_row(
        frame,
        left=(
            "CEJ 9단계",
            "데이터사전 v2.7 기준",
            frame["cej"].fillna("해당없음").replace("", "해당없음").value_counts().rename_axis("cej").reset_index(name="count"),
            "cej",
            "overview_cej_distribution_chart",
            None,
        ),
        right=(
            "문의 Flag",
            "질문형 VoC 비율",
            (
                frame["inquiry_flag"]
                .fillna("N")
                .replace("", "N")
                .str.upper()
                .value_counts()
                .reindex(["Y", "N"], fill_value=0)
                .rename_axis("inquiry_flag")
                .reset_index(name="count")
            ),
            "inquiry_flag",
            "overview_inquiry_distribution_chart",
            None,
        ),
    )

    # ★ 이 그래프는 「제외된 행」을 센다. 그런데 위 화면에 오는 frame 에는
    #   제외행이 애초에 걸러져 없다. 그래서 무엇을 하든 0 이 나왔다 (sky 2026-08-19).
    #   제외 전 자료(scope_source)로 센다.
    scope_frame = scope_source if scope_source is not None else frame
    scope_reasons = scope_exclusion_reason_distribution(scope_frame)
    excluded_total = int(scope_reasons["count"].sum())
    section_title(
        "Scope 제외 사유",
        f"분석에서 빠진 {excluded_total:,}건이 왜 빠졌는지 봅니다"
        "  ·  제품군·브랜드·국가 필터만 반영합니다",
    )
    st.caption(
        "★ confidence 필터와 영역 필터는 일부러 걸지 않습니다. "
        "제외행은 본래 신뢰도가 낮고(513건 중 424건이 Low) 영역이 「미판정」이라, "
        "그 조건을 걸면 거의 다 사라져 왜 빠졌는지를 볼 수 없습니다."
    )
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
    # ★ 사유별 표는 뺐다. 칸이 3개뿐이라 위 막대그래프로 충분하다 (sky 2026-08-19)

    section_title(
        "개별 VoC 개선 포인트 체크",
        "행을 고르면 그 VoC 의 요약문과 RootCause 를 아래에서 읽습니다",
    )
    # ★ RC 를 왼쪽에 모은다. 「RC 가 있는 행」 을 눈으로 훑을 수 있어야 한다 (sky 2026-08-19)
    display_columns = [
        "rootcause_summary",
        "rootcause_problem",
        "rootcause_target",
        "rootcause_cause",
        "source_id",
        "raw_row_index",
        "product_category",
        "topic",
        "sentiment_dir",
        "cej",
        "entity_role",
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
    # D-5 — 분리 여부를 한 칸으로 만든다. 원본 데이터는 건드리지 않는다
    frame = frame.copy()
    frame["2차분리"] = _split_series(frame).map({True: "Y", False: ""})
    if "2차분리" not in display_columns:
        display_columns.insert(4, "2차분리")

    # ★ L 등급으로 거른다. rootcause_summary 값 앞에 붙어 있는 등급이다
    grade_series = frame["rootcause_summary"].fillna("").astype(str).str[:2]
    grade_series = grade_series.where(grade_series.isin(ROOTCAUSE_GRADE_NOTE), "")
    counts = grade_series.value_counts()
    grade_options = [
        f"{code} ({int(counts.get(code, 0))})"
        for code in ("L3", "L2", "L1", "L0")
        if int(counts.get(code, 0))
    ]
    if int(counts.get("", 0)):
        grade_options.append(f"등급 없음 ({int(counts.get('', 0))})")
    picked_grades = st.multiselect(
        "RootCause 등급으로 거르기",
        grade_options,
        default=[],
        key="overview_drilldown_grade",
        help=(
            "L3 문제·대상·원인이 모두 원문에 있다  ·  L2 원인 서술만 없다  ·  "
            "L1 개선 대상이 없다  ·  L0 원문에 결핍 서술이 없다. "
            "비워 두면 전부 봅니다."
        ),
    )
    # D-5 — 2차가 나눈 행만 골라 보기. 표 안에서 오른쪽으로 밀려 안 보이던 칸이라
    #   거르개를 옆에 둔다 (sky 2026-08-19)
    split_mask = _split_series(frame)
    split_only = st.checkbox(
        f"2차 분리 행만 보기 ({int(split_mask.sum())}건)",
        key="overview_drilldown_split_only",
        help="한 댓글에 주제가 여럿이라 2차에서 나눈 행입니다. 원행은 RootCause 상세에 나옵니다.",
    )
    table_frame = frame[split_mask] if split_only else frame
    if picked_grades:
        wanted = {value.split(" ")[0] for value in picked_grades}
        wanted = {"" if code == "등급" else code for code in wanted}
        table_frame = table_frame[grade_series.reindex(table_frame.index).isin(wanted)]
    if picked_grades or split_only:
        st.caption(f"{len(table_frame):,}행 / 전체 {len(frame):,}행")
    drilldown_frame = table_frame
    drilldown_event = render_selectable_dataframe(
        drilldown_frame[display_columns],
        key="overview_voc_drilldown",
        default_columns=display_columns,
        on_select="rerun",
        selection_mode="single-row",
    )
    # D-3 — 고른 행을 영역 → 주제 → 요약문 → 근본원인 순으로 읽게 한다
    with st.container(border=True):
        section_title("RootCause 상세", "고른 행의 요약문과 문제·대상·원인")
        _render_row_detail(drilldown_frame, drilldown_event)

    # ★ Evidence / Trace 넓은 표는 없앴다. 근거 칸은 위 「RootCause 상세」 의
    #   「근거 보기」 로 옮겼다 — 행 하나를 볼 때 읽는 것이기 때문이다 (sky 2026-08-19)
