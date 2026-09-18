"""Improvement-task prioritization tab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard60.l2_narrative import api_key_available, summarize_task
from src.dashboard60.data_contract import ensure_dashboard_columns
from src.dashboard60.scoring import score_improvement_tasks, top_negative_vocs
from src.dashboard60.ui_cards import badge, persistent_expander, render_selectable_dataframe, section_title, task_card_html


DISPLAY_COLUMNS = {
    "product_category": "제품군",
    "topic": "이유 Topic",
    "n": "볼륨",
    "neg_count": "부정 건수",
    "neg_ratio": "부정률",
    "mean_neg": "평균 부정강도",
    "rc_coverage": "Root Cause 커버리지",
    "priority_score": "우선순위 점수",
}

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


def _format_task(row: pd.Series) -> str:
    return (
        f"{row['product_category']} × {row['topic']} "
        f"(볼륨 {int(row['n'])}, 부정 {int(row['neg_count'])}, 점수 {row['priority_score']:.2f})"
    )


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
    ]


def _display_score_table(scored: pd.DataFrame) -> pd.DataFrame:
    display = scored.copy()
    display["neg_ratio"] = (display["neg_ratio"] * 100).round(1).astype(str) + "%"
    display["mean_neg"] = display["mean_neg"].round(2)
    display["rc_coverage"] = (display["rc_coverage"] * 100).round(1).astype(str) + "%"
    display["priority_score"] = display["priority_score"].round(2)
    return display.rename(columns=DISPLAY_COLUMNS)


def render(frame: pd.DataFrame) -> None:
    frame = ensure_dashboard_columns(frame)
    st.subheader("개선과제 우선순위")
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

    section_title("먼저 볼 것 Top 3", "우선순위 점수 → RC커버리지 → 볼륨")
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
            with persistent_expander(
                "대표 부정 VoC / Root Cause 근거",
                key=f"improvement_evidence_{rank}",
                expanded=False,
            ):
                if examples:
                    evidence = pd.DataFrame(examples).rename(
                        columns={
                            "original_voc": "원문",
                            "rootcause_problem": "Root Cause 문제",
                            "rootcause_summary": "Root Cause 요약",
                            "negative_intensity": "부정강도",
                        }
                    )
                    render_selectable_dataframe(
                        evidence,
                        key=f"improvement_card_evidence_{rank}",
                    )
                else:
                    st.caption("대표 부정 VoC가 없습니다.")

    section_title("전체 개선과제 후보 테이블", "정렬과 수치 검증용")
    with persistent_expander("전체 표 보기", key="improvement_full_table", expanded=False):
        render_selectable_dataframe(
            _display_score_table(scored),
            key="improvement_score_table",
        )

    section_title("대표 부정 VoC / Root Cause 드릴다운")
    options = [_format_task(row) for _, row in scored.iterrows()]
    selected = st.selectbox("드릴다운할 개선과제 후보", options)
    selected_index = options.index(selected)
    selected_row = scored.iloc[selected_index]
    examples = top_negative_vocs(
        frame,
        str(selected_row["product_category"]),
        str(selected_row["topic"]),
        k=3,
    )
    if not examples:
        st.info("대표 부정 VoC가 없습니다.")
    else:
        render_selectable_dataframe(
            pd.DataFrame(examples).rename(
                columns={
                    "original_voc": "원문",
                    "rootcause_problem": "Root Cause 문제",
                    "rootcause_summary": "Root Cause 요약",
                    "negative_intensity": "부정강도",
                }
            ),
            key="improvement_negative_drilldown",
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
