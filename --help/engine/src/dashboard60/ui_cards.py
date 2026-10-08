"""Small visual helpers for the dashboard60 card layout.

The helpers in this module are intentionally presentation-only. They do not
change the 66-column data contract, L1 scoring, or L2 narrative behavior.
"""

from __future__ import annotations

from html import escape
from typing import Any, Iterable

import pandas as pd
import streamlit as st


TONE_CLASS = {
    "blue": "tone-blue",
    "green": "tone-green",
    "orange": "tone-orange",
    "purple": "tone-purple",
    "red": "tone-red",
    "gray": "tone-gray",
}


def _store_expander_state(widget_key: str, state_key: str) -> None:
    st.session_state[state_key] = bool(st.session_state.get(widget_key, False))


def persistent_expander(label: str, *, key: str, expanded: bool = False, **kwargs: Any):
    """Return an expander whose open state survives conditional tab rendering."""

    state_key = f"{key}_expanded"
    widget_key = f"_{key}_expanded"
    if state_key not in st.session_state:
        st.session_state[state_key] = bool(expanded)
    st.session_state[widget_key] = bool(st.session_state[state_key])
    return st.expander(
        label,
        expanded=bool(st.session_state[state_key]),
        key=widget_key,
        on_change=_store_expander_state,
        args=(widget_key, state_key),
        **kwargs,
    )


def inject_card_css() -> None:
    """Install dashboard60 card styles on every Streamlit rerun.

    Streamlit rebuilds the DOM on widget interactions. A session-level
    "already loaded" guard can leave later rerenders without this CSS block,
    especially after radio-based navigation. Re-emitting this tiny style block
    keeps all four operating views consistently cardized.
    """
    st.markdown(
        """
        <style>
        :root {
            --lg-red: #A50034;
            --lg-red-dark: #7A0026;
            --lg-red-soft: #F9E8EE;
            --lg-red-line: #E9B8C8;
            --lg-neutral-bg: #F5F5F5;
            --d60-card-bg: #ffffff;
            --d60-panel-bg: #f8fafc;
            --d60-border: #e5e7eb;
            --d60-text: #2b2f33;
            --d60-muted: #6b7280;
            --d60-blue: #475569;
            --d60-green: #2FAE73;
            --d60-orange: #D97706;
            --d60-red: #A50034;
            --d60-purple: #8B5CF6;
            --d60-shadow: 0 12px 28px rgba(31, 41, 55, 0.08);
            --d60-shadow-soft: 0 7px 18px rgba(31, 41, 55, 0.055);
        }
        html, body, [class*="css"] {
            color: var(--d60-text);
        }
        .stApp {
            background: linear-gradient(180deg, #fbfbfc 0%, #f5f5f5 100%);
        }
        .block-container {
            padding-top: 2rem;
        }
        [data-testid="stMainBlockContainer"] h1,
        [data-testid="stMainBlockContainer"] h2,
        [data-testid="stMainBlockContainer"] h3,
        [data-testid="stMainBlockContainer"] h4 {
            color: #222222;
            letter-spacing: -0.018em;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"] {
            color: var(--d60-muted);
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f7f7f8 100%);
            border-right: 1px solid var(--d60-border);
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding-top: 1.1rem;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] h4,
        section[data-testid="stSidebar"] h5 {
            color: #222222;
            letter-spacing: -0.01em;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] {
            background: #ffffff;
            border: 1px solid var(--d60-border);
            border-radius: 13px;
            box-shadow: 0 5px 18px rgba(31, 41, 55, 0.05);
            overflow: hidden;
            margin-bottom: 0.65rem;
        }
        section[data-testid="stSidebar"] [data-testid="stExpander"] details > summary {
            color: #2f3337;
            font-weight: 800;
        }
        section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-color: #eadde2 !important;
            border-radius: 14px;
            box-shadow: 0 7px 20px rgba(31, 41, 55, 0.06);
            padding: 0.35rem 0.45rem 0.25rem;
        }
        section[data-testid="stSidebar"] [data-testid="stPopover"] button {
            border-color: var(--lg-red) !important;
            color: var(--lg-red) !important;
            background: #ffffff !important;
            font-weight: 900 !important;
            box-shadow: 0 6px 16px rgba(165, 0, 52, 0.12);
        }
        section[data-testid="stSidebar"] [data-testid="stPopover"] button:hover {
            background: var(--lg-red-soft) !important;
            border-color: var(--lg-red-dark) !important;
            color: var(--lg-red-dark) !important;
        }
        .stButton > button[kind="primary"],
        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: var(--lg-red) !important;
            border-color: var(--lg-red) !important;
            color: #ffffff !important;
            border-radius: 11px !important;
            font-weight: 900 !important;
            box-shadow: 0 7px 18px rgba(165, 0, 52, 0.20);
        }
        .stButton > button[kind="primary"]:hover,
        section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
            background: var(--lg-red-dark) !important;
            border-color: var(--lg-red-dark) !important;
        }
        section[data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
            border-radius: 10px !important;
            border-color: #e5e7eb !important;
            background: #ffffff !important;
            color: #333333 !important;
        }
        span[data-baseweb="tag"] {
            background-color: var(--lg-red-soft) !important;
            color: var(--lg-red-dark) !important;
            border: 1px solid rgba(165, 0, 52, 0.22) !important;
            border-radius: 999px !important;
            font-weight: 800 !important;
        }
        div[data-baseweb="select"] > div {
            border-radius: 10px !important;
            border-color: #e5e7eb !important;
        }
        div[data-baseweb="select"]:focus-within > div {
            border-color: var(--lg-red) !important;
            box-shadow: 0 0 0 1px var(--lg-red-soft) !important;
        }
        [data-testid="stMainBlockContainer"] div[role="radiogroup"] {
            background: #ffffff;
            border: 1px solid var(--d60-border);
            border-radius: 999px;
            padding: 5px;
            box-shadow: var(--d60-shadow-soft);
            width: fit-content;
            max-width: 100%;
        }
        [data-testid="stMainBlockContainer"] div[role="radiogroup"] label {
            border-radius: 999px !important;
            padding: 0.3rem 0.65rem !important;
            color: var(--d60-muted) !important;
            font-weight: 800 !important;
        }
        [data-testid="stMainBlockContainer"] div[role="radiogroup"] label:has(input:checked) {
            background: var(--lg-red) !important;
            color: #ffffff !important;
            box-shadow: 0 7px 16px rgba(165, 0, 52, 0.20);
        }
        [data-testid="stMainBlockContainer"] div[role="radiogroup"] label:has(input:checked) p,
        [data-testid="stMainBlockContainer"] div[role="radiogroup"] label:has(input:checked) span {
            color: #ffffff !important;
        }
        .d60-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
            gap: 14px;
            margin: 0.75rem 0 1.2rem;
        }
        .d60-metric-card, .d60-task-card, .d60-mini-card {
            position: relative;
            /* ★ 카드끼리 너무 붙어 보인다는 지적 (sky 2026-08-20) */
            margin-bottom: 18px;
            background: var(--d60-card-bg);
            border: 1px solid var(--d60-border);
            border-radius: 16px;
            padding: 18px 18px 16px;
            box-shadow: var(--d60-shadow);
            overflow: hidden;
        }
        .d60-metric-card::before, .d60-task-card::before {
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            top: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--lg-red) 0%, var(--lg-red-line) 100%);
        }
        .d60-metric-card.tone-blue::before, .d60-task-card.tone-blue::before { background: linear-gradient(90deg, var(--lg-red) 0%, #CBD5E1 100%); }
        .d60-metric-card.tone-green::before, .d60-task-card.tone-green::before { background: linear-gradient(90deg, var(--d60-green) 0%, #BDEAD3 100%); }
        .d60-metric-card.tone-orange::before, .d60-task-card.tone-orange::before { background: linear-gradient(90deg, var(--d60-orange) 0%, #FDE68A 100%); }
        .d60-metric-card.tone-red::before, .d60-task-card.tone-red::before { background: linear-gradient(90deg, var(--lg-red) 0%, #F4B4C7 100%); }
        .d60-metric-card.tone-purple::before, .d60-task-card.tone-purple::before { background: linear-gradient(90deg, var(--d60-purple) 0%, #DDD6FE 100%); }
        .d60-metric-label {
            color: var(--d60-muted);
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }
        .d60-metric-value {
            color: var(--d60-text);
            font-size: clamp(26px, 2.6vw, 36px);
            font-weight: 900;
            line-height: 1.12;
            margin-top: 8px;
        }
        .d60-metric-sub {
            color: var(--d60-muted);
            font-size: 12px;
            margin-top: 5px;
            min-height: 18px;
        }
        .d60-section-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin: 1.1rem 0 0.45rem;
        }
        .d60-section-title h4 {
            margin: 0;
            color: var(--d60-text);
            font-size: 16px;
            font-weight: 900;
        }
        .d60-pill, .d60-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            font-weight: 800;
            background: #eff6ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
            white-space: nowrap;
        }
        /* ★ 배지 4개가 한 줄에 3px 모자라 접히고 있었다 (sky 2026-08-20).
           접히면 그 카드만 30px 높아져 같은 행 짝과 바닥이 안 맞는다.
           실측: 칸폭 332px, 배지 합 335px. 좌우 여백을 2px씩 줄여 16px 확보한다.
           글자 크기는 안 건드린다 — 읽는 데 쓰는 값이다. */
        .d60-badge {
            padding: 4px 8px;
        }
        /* ★ 파란 박스를 좌(제품군)·우(브랜드) 두 칸으로 나눈다 (sky 2026-08-20).
           첫 줄이 주요, 그 아래로 나머지를 한 줄씩 적는다. */
        /* ★ 한 박스 안에 제품군과 브랜드가 붙어 있어 구분이 안 됐다.
           좌우 두 박스로 쪼갠다 (sky 2026-08-20). 위아래로 나누면
           카드 세로가 두 배가 되어 여러 장 볼 때 스크롤이 급증한다. */
        .d60-subject {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            /* 한 줄짜리 카드와 두 줄짜리 카드의 높이를 맞춘다 */
            min-height: 74px;
        }
        .d60-subject-col {
            min-width: 0;
            background: var(--d60-panel-bg);
            border: 1px solid var(--d60-border);
            border-radius: 12px;
            padding: 10px 12px;
        }
        /* 왼쪽(제품군)과 오른쪽(브랜드)의 라벨 색을 갈라 한눈에 구분되게 한다 */
        .d60-subject-col:first-child .d60-subject-label { color: #1d4ed8; }
        .d60-subject-col:last-child .d60-subject-label { color: #7c3aed; }
        .d60-subject-label {
            font-size: 11px;
            font-weight: 800;
            color: #64748b;
            line-height: 16px;
            margin-bottom: 4px;
        }
        /* ★ 한 항목을 한 줄로 못 박는다. 그래야 줄 수 = 항목 수가 되어
           파이썬에서 박스 높이를 정확히 계산할 수 있다 (sky 2026-08-20).
           이름이 길면 말줄임으로 잘리되 title 로 전문을 남긴다. */
        .d60-subject-main, .d60-subject-sub {
            line-height: 20px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .d60-subject-main {
            font-size: 13px;
            font-weight: 800;
            color: #1e293b;
        }
        .d60-subject-sub {
            font-size: 12px;
            color: #64748b;
        }
        .d60-badge.positive { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
        .d60-badge.negative { background: var(--lg-red-soft); color: var(--lg-red-dark); border-color: var(--lg-red-line); }
        .d60-badge.neutral { background: #f1f5f9; color: #475569; border-color: #e2e8f0; }
        .d60-badge.warning { background: #ffedd5; color: #9a3412; border-color: #fed7aa; }
        .d60-task-title {
            color: var(--d60-text);
            font-size: 17px;
            font-weight: 900;
            margin-bottom: 7px;
            /* ★ 줄 수를 못 박는다. 글자가 몇 줄로 접힐지는 브라우저가 정하므로
               파이썬에서 높이를 어림하면 짝이 어긋난다 (sky 2026-08-20) */
            line-height: 1.35;
            min-height: calc(2 * 1.35em);
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .d60-task-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 8px 0 10px;
            min-height: 30px;
        }
        .d60-preview {
            color: #334155;
            font-size: 13px;
            line-height: 1.55;
            background: var(--d60-panel-bg);
            border: 1px solid var(--d60-border);
            border-radius: 12px;
            padding: 10px 12px;
            /* ★ 3줄로 못 박는다. 넘치면 말줄임으로 잘린다 — 전문은 표에 있다 */
            min-height: calc(3 * 1.55em);
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .d60-ratio-row {
            margin: 8px 0 10px;
        }
        .d60-ratio-head {
            display: flex;
            justify-content: space-between;
            gap: 8px;
            color: var(--d60-text);
            font-size: 13px;
            font-weight: 800;
            margin-bottom: 4px;
        }
        .d60-ratio-track {
            height: 9px;
            background: #e2e8f0;
            border-radius: 999px;
            overflow: hidden;
        }
        .d60-ratio-fill {
            height: 100%;
            border-radius: 999px;
            background: var(--d60-blue);
        }
        .d60-ratio-fill.positive { background: var(--d60-green); }
        .d60-ratio-fill.negative { background: var(--d60-red); }
        .d60-ratio-fill.neutral { background: #94a3b8; }
        .d60-ratio-fill.warning { background: var(--d60-orange); }
        .d60-note {
            color: var(--d60-muted);
            font-size: 12px;
            line-height: 1.55;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stMainBlockContainer"] [data-testid="stExpander"] {
            background: #ffffff;
            border-color: var(--d60-border) !important;
            border-radius: 16px;
            box-shadow: var(--d60-shadow-soft);
            overflow: visible;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stExpander"] details > summary {
            color: var(--d60-text);
            font-weight: 900;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stVegaLiteChart"] {
            background: #ffffff;
            border: 1px solid var(--d60-border);
            border-radius: 16px;
            box-shadow: var(--d60-shadow-soft);
            padding: 18px 20px 14px;
            margin: 0.35rem 0 0.8rem;
            overflow-x: auto;
            overflow-y: visible;
            box-sizing: border-box;
            max-width: 100%;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 1rem 1.1rem;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stDataFrame"] {
            background: #ffffff;
            border: 1px solid var(--d60-border);
            border-radius: 16px;
            box-shadow: var(--d60-shadow-soft);
            padding: 14px;
            overflow: visible;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stDataFrame"] [data-testid="stElementToolbar"] {
            opacity: 1 !important;
            z-index: 1002 !important;
            pointer-events: auto !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stDataFrame"] [data-testid="stElementToolbarButtonContainer"] {
            z-index: 1003 !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stDataFrame"] [role="columnheader"] {
            color: var(--d60-text) !important;
            font-weight: 900 !important;
        }
        [data-testid="stMainBlockContainer"] .stAlert {
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: object, sub: str = "", *, tone: str = "blue") -> str:
    tone_class = TONE_CLASS.get(tone, TONE_CLASS["blue"])
    return (
        f'<div class="d60-metric-card {tone_class}">'
        f'<div class="d60-metric-label">{escape(str(label))}</div>'
        f'<div class="d60-metric-value">{escape(str(value))}</div>'
        f'<div class="d60-metric-sub">{escape(str(sub))}</div>'
        "</div>"
    )


def render_metric_grid(cards: Iterable[str]) -> None:
    st.markdown('<div class="d60-card-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def badge(label: str, *, tone: str = "neutral") -> str:
    cls = {
        "긍정": "positive",
        "부정": "negative",
        "중립": "neutral",
        "warning": "warning",
        "negative": "negative",
        "positive": "positive",
        "neutral": "neutral",
    }.get(tone, "neutral")
    return f'<span class="d60-badge {cls}">{escape(str(label))}</span>'


def section_title(title: str, note: str = "") -> None:
    note_html = f'<span class="d60-note">{escape(note)}</span>' if note else ""
    st.markdown(
        f'<div class="d60-section-title"><h4>{escape(title)}</h4>{note_html}</div>',
        unsafe_allow_html=True,
    )


def ratio_rows(rows: list[tuple[str, int, float, str]]) -> str:
    """가로 막대 비율 줄.

    ★ tone 자리에 「#RRGGBB」 색을 그대로 줄 수 있다 (sky 2026-08-19).
      위 그래프의 막대 색과 아래 포션 색을 맞추기 위해서다.
      긍정/부정/중립 같은 기존 이름도 그대로 받는다.
    """

    html = []
    for label, count, share, tone in rows:
        tone_text = str(tone or "")
        cls = {
            "긍정": "positive",
            "부정": "negative",
            "중립": "neutral",
            "warning": "warning",
        }.get(tone_text, "")
        color_style = ""
        if tone_text.startswith("#"):
            color_style = f"background:{escape(tone_text)};"
        pct = max(0.0, min(100.0, share * 100))
        html.append(
            '<div class="d60-ratio-row">'
            f'<div class="d60-ratio-head"><span>{escape(str(label))}</span>'
            f'<span>{count:,} · {pct:.1f}%</span></div>'
            '<div class="d60-ratio-track">'
            f'<div class="d60-ratio-fill {cls}" '
            f'style="width:{pct:.1f}%;{color_style}"></div>'
            "</div></div>"
        )
    return "".join(html)


def card_min_height(title: str, preview: str, badge_count: int = 0, *, width_chars: int = 26) -> int:
    """이 내용이면 카드가 대략 몇 px 필요한가 (2026-08-20).

    ★ 같은 행 두 카드의 높이를 맞추려고 밖으로 뺐다. 부르는 쪽에서 둘 중 큰 값을
      골라 양쪽에 같이 준다. 1번 탭 그래프에서 쓴 방식과 같다.
    ★ 픽셀을 정확히 알 수 없으니 어림한다. 모자라면 카드가 잘리는 것이 아니라
      min-height 를 넘겨 자연히 늘어난다.
    """

    import math

    # ★ 넉넉히 잡는다. 모자라면 한쪽만 min-height 를 넘겨 늘어나 짝이 어긋난다
    #   (sky 2026-08-20 실측: 같은 행이 188 vs 212 로 갈렸다).
    #   넘치면 흰 여백이 조금 생길 뿐이라 모자라는 것보다 낫다
    narrow = max(width_chars - 8, 6)
    title_lines = max(1, math.ceil(len(str(title or "")) / narrow))
    preview_lines = math.ceil(len(str(preview or "")) / narrow) if preview else 0
    badge_rows = max(1, math.ceil(max(badge_count, 1) / 2))
    return int(64 + title_lines * 32 + badge_rows * 44 + (preview_lines * 26 + 26 if preview else 0))


def task_card_html(
    title: str,
    badges: Iterable[str],
    preview: str = "",
    *,
    tone: str = "blue",
    min_height: int | None = None,
    preview_html: str = "",
) -> str:
    """preview_html 은 이미 짜 놓은 HTML 을 그대로 넣는 자리다 (sky 2026-08-20).

    ★ 기존 preview(문자열·escape)는 그대로 둔다. 문의 탭 카드가 쓰고 있다.
      부르는 쪽에서 값을 직접 escape 해서 넘겨야 한다.
    """

    tone_class = TONE_CLASS.get(tone, TONE_CLASS["blue"])
    badges_html = "".join(badges)
    if preview_html:
        body_html = preview_html
    else:
        body_html = f'<div class="d60-preview">{escape(preview)}</div>' if preview else ""
    style = f' style="min-height:{int(min_height)}px"' if min_height else ""
    return (
        f'<div class="d60-task-card {tone_class}"{style}>'
        f'<div class="d60-task-title">{escape(title)}</div>'
        f'<div class="d60-task-meta">{badges_html}</div>'
        f"{body_html}"
        "</div>"
    )


def render_table_download(
    frame: "pd.DataFrame",
    *,
    key: str,
    label: str,
    file_stem: str,
    note: str = "",
) -> None:
    """표 아래에 「이 표 통째로 받기」 버튼을 둔다.

    ★ 왜 따로 두나 (sky 2026-08-20)
      표 오른쪽 위 streamlit 기본 ⬇ 는 「보이는 칸만」 내려준다.
      칸을 숨겨 놓고 받으면 숨긴 칸이 빠진 파일을 받는다.
      이 버튼은 화면에서 무엇을 숨겼든 그 표의 전 칸을 준다.

    ★ 여기서 받는 것은 개인정보가 가려진 판본이다.
      화면으로 오는 자료는 mask_frame_for_display 를 이미 거쳤다.
    """

    if frame is None or frame.empty:
        return
    st.download_button(
        f"⬇  {label} ({len(frame):,}행 · {len(frame.columns)}칸)",
        data=frame.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{file_stem}_{len(frame)}행.csv",
        mime="text/csv",
        key=f"{key}_download",
        width="stretch",
    )
    st.caption(
        note or
        "지금 걸린 필터가 그대로 반영됩니다. 화면에서 숨긴 칸도 전부 들어갑니다. "
        "사용자명·이메일·링크는 가려진 판본입니다."
    )


def render_selectable_dataframe(
    frame: pd.DataFrame,
    *,
    key: str,
    default_columns: Iterable[str] | None = None,
    height: int | None = None,
    hide_index: bool = True,
    width: str = "stretch",
    caption: str = "표시할 컬럼을 선택할 수 있습니다. 숨긴 컬럼은 ‘전체 컬럼 복구’로 되돌립니다.",
    **kwargs: Any,
) -> Any:
    """Render a dataframe with a lightweight visible-column recovery control."""

    # ★ st.dataframe 의 반환을 그대로 돌려준다. 행 선택을 쓰려는 쪽만 받아 쓰면 된다.
    #   기존에 반환을 안 받던 곳은 아무 영향이 없다 (D-3, 2026-08-19)

    if frame is None:
        frame = pd.DataFrame()
    available_columns = [str(column) for column in frame.columns]
    default = [str(column) for column in (default_columns or available_columns) if str(column) in available_columns]
    if not default:
        default = available_columns
    # ★ Streamlit 은 위젯이 만들어진 뒤 그 위젯의 session_state 를 못 바꾸게 막는다.
    #   그래서 「숨긴 컬럼 전체 복구」 버튼은 위젯 키에 직접 쓰지 못한다.
    #   대신 대기표(pending)를 남기고, 위젯을 만들기 「전에」 그것을 소비한다.
    #   ★ 평소에는 절대 덮어쓰지 않는다. 조건 없이 덮었더니 사용자가 x 로 지운
    #     컬럼이 다음 실행에서 되살아났다 (sky 2026-08-19).
    state_key = f"{key}_columns"
    pending_key = f"{key}_columns_pending"
    reset_key = f"{key}_native_reset"
    if reset_key not in st.session_state:
        st.session_state[reset_key] = 0
    if pending_key in st.session_state:
        st.session_state[state_key] = st.session_state.pop(pending_key)
    elif state_key not in st.session_state:
        st.session_state[state_key] = default
    else:
        # 자료가 바뀌어 없어진 컬럼만 걷어낸다. 사용자가 고른 것은 건드리지 않는다
        kept = [column for column in st.session_state[state_key] if column in available_columns]
        if kept != st.session_state[state_key]:
            st.session_state[state_key] = kept or default
    selected = list(st.session_state.get(state_key) or default)
    with st.expander("표시 컬럼 숨김·복구", expanded=False):
        st.caption(caption)
        selected = st.multiselect(
            "표시 컬럼",
            available_columns,
            key=state_key,
        )
        st.caption("테이블 우측 상단 메뉴에서 숨긴 컬럼까지 초기화하려면 아래 버튼을 누르세요.")
        if st.button("숨긴 컬럼 전체 복구", key=f"{key}_restore_columns", width="stretch"):
            # ★ 위젯 키가 아니라 대기표에 쓴다. 다음 실행 맨 위에서 소비된다
            st.session_state[pending_key] = list(available_columns)
            st.session_state[reset_key] = int(st.session_state.get(reset_key, 0)) + 1
            st.rerun()
    display = frame.loc[:, selected] if selected else frame
    dataframe_kwargs: dict[str, Any] = {
        "width": width,
        "hide_index": hide_index,
        "key": f"{key}_dataframe_{st.session_state[reset_key]}",
        **kwargs,
    }
    if height is not None:
        dataframe_kwargs["height"] = height
    return st.dataframe(display, **dataframe_kwargs)
