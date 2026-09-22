"""Reusable charts for the greenfield 66-column dashboard."""

from __future__ import annotations

import hashlib
import textwrap

import altair as alt
import pandas as pd


LG_RED = "#A50034"
LG_RED_DARK = "#7A0026"
NEUTRAL_TEXT = "#2b2f33"
NEUTRAL_MUTED = "#6b7280"
NEUTRAL_GRID = "#e5e7eb"
POSITIVE_GREEN = "#2FAE73"
WARNING_AMBER = "#D97706"
AXIS_LABEL_SEPARATOR = "|"

SENTIMENT_COLORS = {
    "\uae0d\uc815": POSITIVE_GREEN,
    "\ubd80\uc815": LG_RED,
    "\uc911\ub9bd": "#94a3b8",
}

DEFAULT_PALETTE = [
    LG_RED,
    LG_RED_DARK,
    "#C94F76",
    "#E9B8C8",
    "#475569",
    "#64748b",
    "#94a3b8",
    POSITIVE_GREEN,
    "#0F766E",
    WARNING_AMBER,
    "#8B5CF6",
    "#0891B2",
]


def _chart_height(frame: pd.DataFrame, *, min_height: int = 340, row_px: int = 26, max_height: int = 720) -> int:
    """Return a roomy chart height so titles, labels, and legends do not collide."""

    rows = max(1, len(frame))
    return min(max_height, max(min_height, 220 + rows * row_px))


def stable_color(value: object) -> str:
    """Return a deterministic dashboard color for a categorical value."""

    text = str(value or "")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(DEFAULT_PALETTE)
    return DEFAULT_PALETTE[index]


def wrap_axis_label(value: object, *, width: int = 7, max_lines: int = 4) -> str:
    """Wrap long categorical labels into bounded horizontal lines for Vega axes."""

    text = " ".join(str(value or "").split())
    if not text:
        return ""
    friendly = text.replace("/", "/ ")
    lines = textwrap.wrap(
        friendly,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
        replace_whitespace=True,
        drop_whitespace=True,
    ) or [text]
    if len(lines) > max_lines:
        lines = [*lines[: max_lines - 1], " ".join(lines[max_lines - 1 :])]
    return AXIS_LABEL_SEPARATOR.join(line.strip() for line in lines if line.strip())


# 이보다 항목이 많으면 가로 막대로 눕힌다. 세로로 두면 한글 라벨이 서로 겹쳐 못 읽는다.
# ★ 8 로 두었더니 8종짜리 「문의 유형」 이 세로로 남아 겹쳤다 (sky 2026-08-20).
#   반쪽 칸에서는 5종만 넘어도 한글이 안 들어간다. 5 로 낮춘다.
ROTATE_LABEL_THRESHOLD = 5


def _should_rotate(frame: pd.DataFrame) -> bool:
    return len(frame) > ROTATE_LABEL_THRESHOLD


def _prepare_axis_frame(frame: pd.DataFrame, x: str) -> tuple[pd.DataFrame, str]:
    prepared = frame.copy()
    axis_field = "__axis_label"
    if x not in prepared.columns:
        prepared[axis_field] = ""
        return prepared, axis_field
    # ★ 눕힌 라벨은 줄바꿈하지 않는다. 눕힌 여러 줄은 오히려 더 읽기 어렵다
    if _should_rotate(prepared):
        prepared[axis_field] = prepared[x].astype(str)
    else:
        prepared[axis_field] = prepared[x].map(wrap_axis_label)
    return prepared, axis_field


def _wrapped_axis(rotate: bool = False) -> alt.Axis:
    if rotate:
        return alt.Axis(
            # ★ -40 으로는 한글 라벨이 길어 여전히 겹친다. 세워서 확실히 떼어 놓는다
            labelAngle=-90,
            labelAlign="right",
            labelBaseline="middle",
            labelLimit=0,
            labelOverlap=False,
            labelPadding=6,
        )
    return alt.Axis(
        labelAngle=0,
        labelAlign="center",
        labelBaseline="top",
        labelLimit=0,
        labelOverlap=False,
        labelExpr=f"split(datum.label, '{AXIS_LABEL_SEPARATOR}')",
        labelLineHeight=13,
        labelPadding=10,
    )


def _bottom_padding(frame: pd.DataFrame, x: str) -> int:
    if frame.empty or x not in frame.columns:
        return 48
    if _should_rotate(frame):
        # 눕힌 라벨은 글자 길이만큼 아래로 내려온다. 가장 긴 것에 맞춘다
        longest = max((len(str(value)) for value in frame[x].dropna()), default=4)
        return max(72, min(150, 40 + int(longest * 6.2)))
    max_lines = max(
        (str(value).count(AXIS_LABEL_SEPARATOR) + 1 for value in frame[x].dropna().map(wrap_axis_label)),
        default=1,
    )
    return max(56, min(104, 28 + max_lines * 18))


def _color_encoding(
    frame: pd.DataFrame,
    color: str | None,
    color_map: dict[str, str] | None,
    *,
    show_legend: bool = True,
) -> alt.Color | alt.value:
    if not color or color not in frame.columns:
        return alt.value(LG_RED)
    domain = [str(value) for value in frame[color].dropna().unique()]
    if color_map:
        range_values = [color_map.get(value, LG_RED) for value in domain]
    else:
        range_values = [stable_color(value) for value in domain]
    return alt.Color(
        f"{color}:N",
        scale=alt.Scale(domain=domain, range=range_values),
        # ★ 가로 막대는 축에 이름이 이미 있다. 범례를 또 그리면 세로 공간만 먹는다
        legend=(
            alt.Legend(
                orient="bottom",
                direction="horizontal",
                columns=2,
                title=None,
                labelLimit=0,
                symbolLimit=0,
            )
            if show_legend
            else None
        ),
        title=None,
    )


def _apply_lg_theme(chart):
    """Apply the dashboard LG visual theme to reusable Altair charts."""

    return (
        chart.configure_view(stroke=None)
        .configure_axis(
            labelColor=NEUTRAL_MUTED,
            titleColor=NEUTRAL_MUTED,
            gridColor=NEUTRAL_GRID,
            gridOpacity=0.65,
            domain=False,
            tickColor=NEUTRAL_GRID,
            labelFontSize=12,
            titleFontSize=12,
        )
        .configure_legend(
            labelColor=NEUTRAL_MUTED,
            titleColor=NEUTRAL_MUTED,
            orient="bottom",
            direction="horizontal",
            labelLimit=0,
            symbolLimit=0,
        )
        .configure_title(color=NEUTRAL_TEXT, fontSize=15, fontWeight="bold")
        .configure(background="transparent")
    )


def bar_chart_height(frame: pd.DataFrame) -> int:
    """이 자료로 그리면 높이가 얼마나 필요한가.

    ★ 같은 행에 놓인 두 그래프의 높이를 맞추려고 밖으로 뺐다 (sky 2026-08-19).
      부르는 쪽에서 둘 중 큰 값을 골라 양쪽에 같이 준다.
    """

    if _should_rotate(frame):
        # 한 줄에 34px — 라벨이 서로 닿지 않는 최소치
        return max(260, 34 * len(frame) + 40)
    return _chart_height(frame)


def bar_chart(
    frame: pd.DataFrame,
    x: str,
    y: str = "count",
    title: str = "",
    *,
    sort: str = "-y",
    color: str | None = None,
    color_map: dict[str, str] | None = None,
    height: int | None = None,
) -> alt.Chart:
    if frame.empty:
        frame = pd.DataFrame({x: [], y: []})
    chart_frame, axis_field = _prepare_axis_frame(frame, x)
    base = alt.Chart(chart_frame)
    horizontal = _should_rotate(frame)
    color_encoding = _color_encoding(frame, color, color_map, show_legend=not horizontal)
    tooltip = list(frame.columns)

    if horizontal:
        # ★ 항목이 많으면 가로 막대로 눕힌다 (sky 2026-08-19).
        #   반쪽 칸 355px 에 15종이면 한 칸이 약 20px 다. 한글 라벨은 어떤 각도로도
        #   그 안에 안 들어간다. 눕히면 왼쪽에서 오른쪽으로 그냥 읽혀 겹칠 일이 없다.
        # ★ 두 번 실패한 자리다 — EncodingSortField 도, sort="-x" 도 안 먹었다.
        #   층이 둘(막대 + 숫자 글자)이라 한쪽 축 설정만으로는 정렬이 안 잡힌다.
        #   그래서 순서를 목록으로 그대로 넘긴다.
        row_sort = (
            chart_frame.sort_values(y, ascending=False)[x].astype(str).tolist()
            if x in chart_frame.columns and y in chart_frame.columns
            else "-x"
        )
        bars = base.mark_bar(cornerRadiusTopRight=5, cornerRadiusBottomRight=5).encode(
            y=alt.Y(
                f"{x}:N",
                sort=row_sort,
                title=None,
                # ★ labelOverlap 을 안 끄면 항목이 9종을 넘는 순간 Vega 가
                #   한 칸 걸러 하나씩 라벨을 지운다. 「니즈 신호 유형」 9종이
                #   라벨 5개만 보였던 원인이다 (sky 2026-08-20)
                axis=alt.Axis(labelLimit=0, labelPadding=8, labelOverlap=False),
            ),
            x=alt.X(f"{y}:Q", title="count", axis=alt.Axis(labelLimit=0)),
            color=color_encoding,
            tooltip=tooltip,
        )
        labels = base.mark_text(dx=7, fontSize=12, fontWeight="bold", color=NEUTRAL_TEXT).encode(
            y=alt.Y(f"{x}:N", sort=row_sort, title=None),
            x=alt.X(f"{y}:Q", title="count"),
            text=alt.Text(f"{y}:Q", format=",.0f"),
        )
        properties = {
            # 범례가 없으니 막대 한 줄에 충분히 준다
            "height": height or bar_chart_height(frame),
            # 숫자 글자가 막대 오른쪽으로 나가므로 오른쪽을 넉넉히 둔다
            "padding": {"top": 18, "bottom": 28, "left": 12, "right": 44},
        }
    else:
        bars = base.mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
            x=alt.X(
                f"{axis_field}:N",
                sort=sort,
                title=None,
                axis=_wrapped_axis(),
            ),
            y=alt.Y(f"{y}:Q", title="count", axis=alt.Axis(labelLimit=0)),
            color=color_encoding,
            tooltip=tooltip,
        )
        labels = base.mark_text(dy=-7, fontSize=12, fontWeight="bold", color=NEUTRAL_TEXT).encode(
            x=alt.X(f"{axis_field}:N", sort=sort, title=None, axis=_wrapped_axis()),
            y=alt.Y(f"{y}:Q", title="count"),
            text=alt.Text(f"{y}:Q", format=",.0f"),
        )
        properties = {
            "height": height or bar_chart_height(frame),
            # ★ right 8 로는 마지막 막대·라벨이 가장자리에 붙거나 잘린다 (sky 2026-08-19)
            "padding": {"top": 18, "bottom": _bottom_padding(frame, x), "left": 12, "right": 28},
        }
    if title:
        properties["title"] = title
    return _apply_lg_theme((bars + labels).properties(**properties))


def group_pick_chart(frame: pd.DataFrame, selected: list[str] | None = None) -> alt.Chart:
    """개선/강화 영역 막대. 막대를 누르면 그 영역으로 필터가 걸린다 (D-1b).

    ★ 고른 영역은 진하게, 나머지는 흐리게 그린다. 지금 무엇을 보고 있는지
      그래프만 봐도 알 수 있어야 한다.
    ★ 층이 하나여야 Streamlit 의 클릭 선택이 안전하게 붙는다.
      숫자는 막대 위 글자 대신 tooltip 으로 준다.
    """

    if frame.empty:
        frame = pd.DataFrame({"topic_group": [], "count": []})
    picked = [value for value in (selected or []) if value]
    opacity = (
        alt.condition(
            alt.FieldOneOfPredicate(field="topic_group", oneOf=picked),
            alt.value(1.0),
            alt.value(0.28),
        )
        if picked
        else alt.value(1.0)
    )
    # ★ toggle 은 Vega 기본값과 같지만 코드에 드러내 둔다.
    #   Shift+클릭으로 여러 영역을 함께 고른다 (sky 2026-08-19)
    pick = alt.selection_point(
        fields=["topic_group"],
        name="pick",
        on="click",
        toggle="event.shiftKey",
    )
    bars = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
        .encode(
            x=alt.X("topic_group:N", sort="-y", title=None, axis=_wrapped_axis(_should_rotate(frame))),
            y=alt.Y("count:Q", title="count", axis=alt.Axis(labelLimit=0)),
            color=alt.Color("topic_group:N", legend=None),
            opacity=opacity,
            tooltip=[
                alt.Tooltip("topic_group:N", title="영역"),
                alt.Tooltip("count:Q", title="건수", format=",.0f"),
                alt.Tooltip("share:Q", title="비중", format=".1%"),
            ],
        )
        .add_params(pick)
        .properties(
            height=260,
            padding={
                "top": 18,
                "bottom": _bottom_padding(frame, "topic_group"),
                "left": 12,
                "right": 28,
            },
        )
    )
    return _apply_lg_theme(bars)


def percent_bar_chart(
    frame: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    *,
    color: str | None = None,
    color_map: dict[str, str] | None = None,
) -> alt.Chart:
    if frame.empty:
        frame = pd.DataFrame({x: [], y: []})
    chart_frame, axis_field = _prepare_axis_frame(frame, x)
    rotate = _should_rotate(frame)
    base = alt.Chart(chart_frame)
    bars = (
        base.mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
        .encode(
            x=alt.X(
                f"{axis_field}:N",
                sort="-y",
                title=None,
                axis=_wrapped_axis(rotate),
            ),
            y=alt.Y(f"{y}:Q", title="rate", axis=alt.Axis(format="%")),
            color=_color_encoding(frame, color, color_map),
            tooltip=list(frame.columns),
        )
    )
    labels = base.mark_text(dy=-7, fontSize=12, fontWeight="bold", color=NEUTRAL_TEXT).encode(
        x=alt.X(f"{axis_field}:N", sort="-y", title=None, axis=_wrapped_axis(rotate)),
        y=alt.Y(f"{y}:Q", title="rate", axis=alt.Axis(format="%")),
        text=alt.Text(f"{y}:Q", format=".1%"),
    )
    properties = {
        "height": _chart_height(frame),
        # ★ right 8 로는 마지막 막대·라벨이 가장자리에 붙거나 잘린다 (sky 2026-08-19)
        "padding": {"top": 18, "bottom": _bottom_padding(frame, x), "left": 12, "right": 28},
    }
    if title:
        properties["title"] = title
    return _apply_lg_theme((bars + labels).properties(**properties))
