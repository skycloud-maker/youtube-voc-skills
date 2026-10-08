"""Improvement-task prioritization tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard60.l2_narrative import api_key_available, summarize_task
from src.dashboard60.data_contract import ensure_dashboard_columns
from src.dashboard60.scoring import score_improvement_tasks, top_negative_vocs
from src.dashboard60.ui_cards import badge, persistent_expander, section_title, task_card_html


DISPLAY_COLUMNS = {
    "product_category": "제품군",
    "topic": "이유 Topic",
    "n": "볼륨",
    "neg_count": "부정 건수",
    "neg_ratio": "부정률",
    "mean_neg": "평균 부정강도",
    "rc_coverage": "Root Cause 커버리지",
    "priority_score": "우선순위 점수",
    # D-6 두 축 (sky 2026-08-16)
    "volume_rank": "건수축 순위",
    "severity_score": "심각도(화난 사람 평균)",
    "severity_rank": "심각도축 순위",
    "combined_rank": "종합 순위합",
    "watch_axis": "봐야 하는 축",
}

# D-6 — 카드를 어느 축으로 줄 세울지 (sky 2026-08-19)
#   ★ 기본값은 기존 「우선순위 점수」 그대로다. 1차 동결 화면을 바꾸지 않는다.
SORT_AXES: dict[str, tuple[list[str], list[bool], str]] = {
    "우선순위 점수 (기존)": (
        ["priority_score", "rc_coverage", "n"],
        [False, False, False],
        "|평균 부정강도| x 부정 건수 → RC커버리지 → 볼륨",
    ),
    "종합 (두 축 순위합)": (
        ["combined_rank", "priority_score"],
        [True, False],
        "건수축 순위 + 심각도축 순위가 작은 것부터. 두 축 모두에서 위쪽인 것이 앞에 온다",
    ),
    "건수축": (
        ["volume_rank"],
        [True],
        "부정 건수가 많은 것부터. 넓게 퍼진 문제",
    ),
    "심각도축": (
        ["severity_rank"],
        [True],
        "화난 사람의 평균 강도가 큰 것부터. 건수를 보지 않는다 — 깊게 아픈 문제",
    ),
}
SORT_AXIS_STATE_KEY = "dashboard60_improvement_sort_axis"
SORT_AXIS_WIDGET_KEY = "_dashboard60_improvement_sort_axis"

AI_NARRATIVE_STATE_KEY = "dashboard60_improvement_ai_narrative_enabled"
AI_NARRATIVE_WIDGET_KEY = "_dashboard60_improvement_ai_narrative_enabled"
AI_TOP_N_STATE_KEY = "dashboard60_improvement_ai_top_n"
AI_TOP_N_WIDGET_KEY = "_dashboard60_improvement_ai_top_n"


def _restore_persistent_widget(widget_key: str, state_key: str, default: object) -> None:
    """Restore a widget whose tab is conditionally omitted on another rerun."""

    if state_key not in st.session_state:
        st.session_state[state_key] = default
    st.session_state[widget_key] = st.session_state[state_key]


def _store_persistent_widget(widget_key: str, state_key: str) -> None:
    st.session_state[state_key] = st.session_state.get(widget_key)


def _score_badges(row: pd.Series) -> list[str]:
    neg_count = int(row["neg_count"])
    neg_ratio = float(row["neg_ratio"])
    mean_neg = float(row["mean_neg"])
    return [
        badge(f"볼륨 {int(row['n']):,}건"),
        badge(f"부정 {neg_count:,}건", tone="negative" if neg_count else "neutral"),
        badge(f"부정률 {neg_ratio * 100:.1f}%", tone="negative" if neg_ratio else "neutral"),
        badge(f"평균 부정강도 {mean_neg:.2f}", tone="negative" if mean_neg < 0 else "neutral"),
        badge(f"RC 커버리지 {float(row['rc_coverage']) * 100:.1f}%"),
        badge(f"우선점수 {float(row['priority_score']):.2f}", tone="warning"),
        # D-6 — 두 축을 카드에서도 보이게 한다
        badge(
            f"건수축 {int(row['volume_rank'])}위 · 심각도축 {int(row['severity_rank'])}위"
            f" · 종합 {int(row['combined_rank'])}",
            tone="neutral",
        ),
    ]


def _display_score_table(scored: pd.DataFrame) -> pd.DataFrame:
    display = scored.copy()
    display["neg_ratio"] = (display["neg_ratio"] * 100).round(1).astype(str) + "%"
    display["mean_neg"] = display["mean_neg"].round(2)
    display["rc_coverage"] = (display["rc_coverage"] * 100).round(1).astype(str) + "%"
    display["priority_score"] = display["priority_score"].round(2)
    if "severity_score" in display.columns:
        display["severity_score"] = display["severity_score"].round(2)
    return display.rename(columns=DISPLAY_COLUMNS)


# 화면 카드로 보여 주는 개수. 내려받는 파일의 「구분」 칸도 이 값을 쓴다
CARD_TOP_N = 10


def _safe_axis_name(axis: str) -> str:
    """정렬축 이름을 파일 이름에 쓸 수 있게 다듬는다."""

    keep = [c for c in axis if c.isalnum() or c in "()_-"]
    return ("".join(keep) or "정렬").strip("_")


def _download_score_table(scored: pd.DataFrame, sort_axis: str) -> pd.DataFrame:
    """내려받을 전체 후보 표.

    ★ 화면 표와 다른 점 (sky 2026-08-20)
      ① 순위와 「구분」(Top N / 그 밖) 칸을 앞에 붙인다.
         받는 사람이 무엇이 카드에 떴고 무엇이 안 떴는지 알아야 한다.
      ② 어느 정렬축으로 뽑았는지 칸에 적는다.
         축을 바꾸면 Top 도 바뀌므로, 나중에 파일만 보고도 알 수 있어야 한다.
    """

    table = _display_score_table(scored).copy()
    table.insert(0, "구분", [
        f"Top {CARD_TOP_N}" if index < CARD_TOP_N else "그 밖"
        for index in range(len(table))
    ])
    table.insert(0, "순위", range(1, len(table) + 1))
    table["정렬축"] = sort_axis
    return table


def _rootcause_block(example: dict) -> None:
    """대표 VoC 하나를 읽을 수 있게 편다 (D-4).

    ★ 표로 두면 못 읽는다. RC 서술은 한 문장이 길다.
    """

    original = str(example.get("original_voc") or "").strip()
    if original:
        st.markdown(f"> {original}")
    problem = str(example.get("rootcause_problem") or "").strip()
    target = str(example.get("rootcause_target") or "").strip()
    cause = str(example.get("rootcause_cause") or "").strip()
    if not (problem or target or cause):
        st.caption("이 VoC 에는 RootCause 가 채워져 있지 않습니다.")
        return
    columns = st.columns(3)
    for column, (label, value) in zip(
        columns, (("문제 현상", problem), ("개선 대상", target), ("근본 원인", cause))
    ):
        with column:
            st.markdown(f"**{label}**")
            st.write(value or "—")


def render(frame: pd.DataFrame) -> None:
    frame = ensure_dashboard_columns(frame)
    st.subheader("개선 방향성")
    st.caption(
        "L1 결정론 스코어링입니다. 군집은 product_category × topic, "
        "우선순위는 |평균 부정강도| × 부정 건수이며 LLM 호출 없이 계산됩니다."
    )
    st.caption(
        "RC 커버리지 = 군집 VoC 중 Root Cause가 정의된 비율입니다. "
        "높을수록 원인/대상이 드러나 실행 가능한 개선과제로 전환하기 쉽다는 뜻입니다."
    )

    scored = score_improvement_tasks(frame)
    if scored.empty:
        st.info("현재 필터 조건에서 개선과제 후보 군집이 없습니다.")
        return

    _restore_persistent_widget(AI_NARRATIVE_WIDGET_KEY, AI_NARRATIVE_STATE_KEY, False)
    ai_narrative_enabled = st.toggle(
        "AI 서술 생성",
        key=AI_NARRATIVE_WIDGET_KEY,
        on_change=_store_persistent_widget,
        args=(AI_NARRATIVE_WIDGET_KEY, AI_NARRATIVE_STATE_KEY),
        help=(
            "기본 OFF입니다. ON일 때만 상위 개선과제에 대한 LLM 요약/제안을 생성합니다. "
            "L1 점수와 순위는 바꾸지 않습니다."
        ),
    )
    ai_narrative_top_n = 5
    if ai_narrative_enabled:
        _restore_persistent_widget(AI_TOP_N_WIDGET_KEY, AI_TOP_N_STATE_KEY, 5)
        ai_narrative_top_n = int(
            st.number_input(
                "AI 서술 대상 Top N",
                min_value=1,
                max_value=10,
                step=1,
                key=AI_TOP_N_WIDGET_KEY,
                on_change=_store_persistent_widget,
                args=(AI_TOP_N_WIDGET_KEY, AI_TOP_N_STATE_KEY),
                help="비용 보호를 위해 상위 N개 군집만 생성합니다. 같은 입력은 파일 캐시를 재사용합니다.",
            )
        )

    _restore_persistent_widget(
        SORT_AXIS_WIDGET_KEY, SORT_AXIS_STATE_KEY, next(iter(SORT_AXES))
    )
    sort_axis = st.radio(
        "정렬 축",
        list(SORT_AXES),
        horizontal=True,
        key=SORT_AXIS_WIDGET_KEY,
        on_change=_store_persistent_widget,
        args=(SORT_AXIS_WIDGET_KEY, SORT_AXIS_STATE_KEY),
        help=(
            "건수축은 넓게 퍼진 문제, 심각도축은 깊게 아픈 문제를 앞에 세웁니다. "
            "★ 건수가 적다는 이유로 목록에서 빠지는 군집은 없습니다. 순서만 달라집니다."
        ),
    )
    sort_columns, sort_ascending, sort_note = SORT_AXES[sort_axis]
    scored = scored.sort_values(
        sort_columns, ascending=sort_ascending, kind="mergesort"
    ).reset_index(drop=True)
    st.caption(f"정렬: {sort_axis} — {sort_note}")

    section_title("먼저 볼 것 Top 3", sort_note)
    top_cols = st.columns(3)
    for idx, (_, row) in enumerate(scored.head(3).iterrows()):
        examples = top_negative_vocs(frame, str(row["product_category"]), str(row["topic"]), k=1)
        preview = examples[0]["original_voc"] if examples else ""
        tone = "red" if idx == 0 else "orange" if idx == 1 else "purple"
        with top_cols[idx]:
            st.markdown(
                task_card_html(
                    f"#{idx + 1} {row['product_category']} × {row['topic']}",
                    _score_badges(row),
                    preview,
                    tone=tone,
                ),
                unsafe_allow_html=True,
            )

    section_title("개선과제 후보 카드", "상위 10개 · 대표 부정 VoC preview")
    for rank, (_, row) in enumerate(scored.head(10).iterrows(), start=1):
        examples = top_negative_vocs(frame, str(row["product_category"]), str(row["topic"]), k=3)
        preview = examples[0]["original_voc"] if examples else "대표 부정 VoC 없음"
        with st.container(border=True):
            st.markdown(
                task_card_html(
                    f"#{rank} {row['product_category']} × {row['topic']}",
                    _score_badges(row),
                    preview,
                    tone="red" if rank <= 3 else "blue",
                ),
                unsafe_allow_html=True,
            )
            # D-4 — 카드 겉면에 「무엇을 고칠까」 를 한 줄 띄운다.
            #   라벨과 건수만 보이면 현업이 움직일 수 없다 (sky)
            headline = str((examples[0] if examples else {}).get("rootcause_problem") or "").strip()
            if headline:
                st.markdown(f"**고칠 것** &nbsp; {headline}", unsafe_allow_html=True)
            else:
                st.caption("이 묶음의 대표 VoC 에는 RootCause 가 없습니다.")
            with persistent_expander(
                f"대표 부정 VoC {len(examples)}건 · 문제·대상·원인",
                key=f"improvement_evidence_{rank}",
                expanded=False,
            ):
                if examples:
                    for order, example in enumerate(examples, start=1):
                        if order > 1:
                            st.divider()
                        st.caption(f"대표 VoC {order} · 부정강도 {example.get('negative_intensity', 0):.1f}")
                        _rootcause_block(example)
                else:
                    st.caption("대표 부정 VoC가 없습니다.")

    # ★ 119행 표를 화면에서 뺐다 (sky 2026-08-20).
    #   상위 10개는 이미 위에서 카드로 보고 있고, 나머지는 「있다」 는 것만
    #   알면 되지 화면에서 훑을 일이 아니었다. 화면만 길어졌다.
    #   → 내려받아 엑셀에서 본다. Top 에 들었는지도 칸으로 붙인다.
    #
    #   번들(improvement_priority 시트)에도 같은 표가 있지만,
    #   ① Top 구분이 없고 ② 지금 걸린 필터·정렬축이 반영되지 않는다.
    section_title(
        "전체 개선과제 후보",
        f"{len(scored)}개 · 내려받아서 봅니다 (화면 카드는 상위 {CARD_TOP_N}개)",
    )
    st.caption(
        f"지금 정렬축 「{sort_axis}」 기준입니다. **정렬축을 바꾸면 Top {CARD_TOP_N} 도 바뀝니다.** "
        "사이드바 필터도 그대로 반영됩니다."
    )
    st.download_button(
        f"⬇  전체 개선과제 후보 {len(scored)}개 내려받기 (CSV)",
        data=_download_score_table(scored, sort_axis).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"개선과제후보_{_safe_axis_name(sort_axis)}_{len(scored)}개.csv",
        mime="text/csv",
        width="stretch",
    )

    if not ai_narrative_enabled:
        return

    if not api_key_available():
        st.warning(
            "AI 서술 생성에 필요한 OPENAI_API_KEY를 찾지 못했습니다. "
            "Streamlit Secrets 또는 로컬 환경변수에 키를 설정하면 사용할 수 있습니다. L1 우선순위 결과는 그대로 유효합니다."
        )
        return

    st.markdown("#### AI 서술 요약 (Top N, 선택 실행)")
    st.caption(
        "요약은 L1 상위 군집을 실무자가 빠르게 이해하도록 실제 VoC/rootcause 근거만 한국어로 압축한 본문입니다. "
        "제안은 접힌 'AI 제안(실험)' 섹션에 분리 표시하며 검토 전 가설로 취급합니다."
    )
    for rank, (_, row) in enumerate(scored.head(ai_narrative_top_n).iterrows(), start=1):
        vocs = top_negative_vocs(frame, str(row["product_category"]), str(row["topic"]), k=3)
        narrative = summarize_task(row, vocs, k=3)
        with st.container(border=True):
            st.markdown(
                f"**#{rank} {row['product_category']} × {row['topic']}** "
                f"(볼륨 {int(row['n'])}, 부정 {int(row['neg_count'])}, 우선점수 {row['priority_score']:.2f})"
            )
            if narrative.get("error"):
                st.warning(f"AI 서술 생성 실패(L1 결과는 유효): {narrative['error']}")
                continue
            summary = narrative.get("summary")
            if summary:
                st.write(summary)
            else:
                st.info("AI 요약이 비어 있습니다. L1 결과와 대표 VoC는 그대로 유효합니다.")
            if narrative.get("cached"):
                st.caption("cached")
            suggestions = narrative.get("suggestions") or []
            with persistent_expander(
                "🧪 AI 제안(실험) — 검토 필요",
                key=f"improvement_ai_suggestions_{rank}",
                expanded=False,
            ):
                if not suggestions:
                    st.caption("생성된 제안이 없습니다.")
                for item in suggestions:
                    st.markdown(f"- {item}")
