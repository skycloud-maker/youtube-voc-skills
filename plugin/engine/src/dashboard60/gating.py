"""Confidence and human-review gating controls."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard60.data_contract import CONFIDENCE_LEVELS, DEFAULT_CONFIDENCE_LEVELS, apply_filters


# ★ 실무자가 읽을 말로 고쳤다 (sky 2026-08-20).
#   전에는 엔진 내부 규칙(Topic+TEE 같은)을 그대로 옮겨 놓았다.
#   값 자체(Very High·High…)는 영어로 둔다 — 산출물 엑셀과 표의
#   「신뢰도」 칸에 그대로 나가서, 화면만 바꾸면 대조할 때 어긋난다.
CONFIDENCE_HELP_TEXT = (
    "판정이 맞을 확률이 아님. 그 행에 정보가 얼마나 채워졌는지(정보 충족도)입니다. "
    "Very High 는 문제·개선 대상·원인까지 다 있는 행, High 는 감정·노력까지 있는 행, "
    "Medium 은 주제만 잡힌 행, Low 는 주제도 못 잡은 행입니다. "
    "정확히는 Topic 없음=Low / Topic만=Medium / Topic+TEE=High / "
    "Topic+TEE+RootCause 완결=Very High. 기본값은 Very High·High 입니다."
)


CONFIDENCE_KEY = "dashboard60_confidence_levels"
REVIEW_ONLY_KEY = "dashboard60_review_required_only"


def render_gating_controls() -> tuple[list[str], bool]:
    """어디까지 믿을 수 있는 행을 볼지 정하는 자리 (sky 2026-08-20).

    ★ 알약 버튼으로 바꿨다. 항목이 넷으로 고정이라 목록을 펼칠 이유가 없고,
      지금 무엇이 켜졌는지 한눈에 보인다.
    """

    if CONFIDENCE_KEY not in st.session_state:
        st.session_state[CONFIDENCE_KEY] = list(DEFAULT_CONFIDENCE_LEVELS)
    selected_confidence = st.pills(
        "판정 충족도",
        CONFIDENCE_LEVELS,
        selection_mode="multi",
        key=CONFIDENCE_KEY,
        help=CONFIDENCE_HELP_TEXT,
    )
    review_required_only = st.toggle(
        "사람 검토가 필요한 행만",
        value=False,
        key=REVIEW_ONLY_KEY,
        help="2차 판독에서 사람이 직접 봐야 한다고 표시한 행입니다(review_required).",
    )
    return list(selected_confidence or []), review_required_only


def apply_operating_gates(
    frame: pd.DataFrame,
    *,
    products: list[str],
    brands: list[str],
    topic_groups: list[str] | None = None,
    markets: list[str],
    cejs: list[str],
    sentiments: list[str],
    confidence_levels: list[str],
    review_required_only: bool,
) -> pd.DataFrame:
    return apply_filters(
        frame,
        products=products,
        topic_groups=topic_groups,
        brands=brands,
        markets=markets,
        cejs=cejs,
        sentiments=sentiments,
        high_confidence_only=False,
        confidence_levels=confidence_levels,
        review_required_only=review_required_only,
    )
