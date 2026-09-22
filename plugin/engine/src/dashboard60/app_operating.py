"""Greenfield operating dashboard for the 66-column VoC dataset.

Run:
    streamlit run src/dashboard60/app_operating.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from src.config import load_yaml_settings_optional
from src.dashboard60 import dataset_state
from src.dashboard60.analysis_runner import render_analysis_runner
from src.dashboard60.data_contract import DEFAULT_CONFIDENCE_LEVELS, FILTER_TOPIC_GROUP_KEY, TOPIC_GROUP_VALUE_KEY, brand_filter_options, apply_filters, latest_dataset, load_metadata, load_voc60_dataset, topic_group_filter_options
from src.dashboard60.privacy import mask_frame_for_display
from src.dashboard60.gating import (
    CONFIDENCE_KEY,
    REVIEW_ONLY_KEY,
    apply_operating_gates,
    render_gating_controls,
)
from src.dashboard60.ui_cards import inject_card_css
from src.dashboard60.views import improvement, inquiry, overview, pl_issue, video


TAB_OVERVIEW = "VoC 현황"
TAB_VIDEO = "분석 영상 정보"
TAB_INQUIRY = "문의 속 니즈"
TAB_IMPROVEMENT = "개선 방향성"
# ★ 안전·위생은 건수와 무관하게 전량 본다 (sky 2026-08-25 · 2차 기준서 §11)
TAB_PL = "★ PL Issue"
OPERATING_TABS = [TAB_OVERVIEW, TAB_VIDEO, TAB_INQUIRY, TAB_IMPROVEMENT, TAB_PL]
DATASET_SESSION_KEY = "dashboard60_dataset_path"
DATASET_WIDGET_KEY = "dashboard60_dataset_path_input"
ACTIVE_TAB_KEY = "dashboard60_active_tab"
FILTER_PRODUCT_KEY = "dashboard60_filter_products"
FILTER_BRAND_KEY = "dashboard60_filter_brands"
FILTER_MARKET_KEY = "dashboard60_filter_markets"
FILTER_CEJ_KEY = "dashboard60_filter_cejs"
FILTER_SENTIMENT_KEY = "dashboard60_filter_sentiments"
# D-1 — 영역(topic_group) 필터 키는 data_contract 에 두었다.
#        개요 탭 그래프도 같은 키를 봐야 하기 때문이다 (순환 import 회피)
SENTIMENT_OPTIONS = ["긍정", "부정", "중립"]


def _reset_filters() -> None:
    """모든 필터를 처음 상태로 (sky 2026-08-20).

    ★ on_click 콜백에서 부른다. 콜백은 다음 실행에서 위젯이 만들어지기 전에
      돌기 때문에, 「위젯이 생긴 뒤에는 그 키를 못 바꾼다」 는 규칙에 걸리지 않는다.
    """

    for key in (
        FILTER_PRODUCT_KEY,
        FILTER_BRAND_KEY,
        FILTER_MARKET_KEY,
        FILTER_CEJ_KEY,
        FILTER_TOPIC_GROUP_KEY,
        TOPIC_GROUP_VALUE_KEY,
    ):
        st.session_state[key] = []
    st.session_state[FILTER_SENTIMENT_KEY] = list(SENTIMENT_OPTIONS)
    st.session_state[CONFIDENCE_KEY] = list(DEFAULT_CONFIDENCE_LEVELS)
    st.session_state[REVIEW_ONLY_KEY] = False


def _commit_dataset_path_from_widget() -> None:
    st.session_state[DATASET_SESSION_KEY] = st.session_state.get(DATASET_WIDGET_KEY, "")


def _options(series: pd.Series) -> list[str]:
    return sorted(str(value) for value in series.dropna().unique() if str(value).strip())


def _render_active_tab(
    frame: pd.DataFrame,
    active_tab: str,
    *,
    group_source: pd.DataFrame | None = None,
    scope_source: pd.DataFrame | None = None,
) -> None:
    # ★ 화면에 그릴 때만 사람으로 이어지는 값을 가린다 (sky 2026-08-20).
    #   대시보드는 실무자 전원이 본다. 판정을 확인하려면 원문은 보여야 하지만,
    #   원문에 섞인 YouTube 호출명(@…)은 분석에 쓰는 값이 아니면서
    #   계정을 바로 가리킨다. 실측: original_voc 77행, atomic_voc 14행.
    #   ★ 여기가 네 뷰 전부로 가는 유일한 길목이라 빠뜨릴 자리가 없다.
    #   ★ 산출물은 안 탄다 — export_bundle 은 디스크에서 읽은 프레임을 쓴다.
    frame = mask_frame_for_display(frame)
    group_source = mask_frame_for_display(group_source) if group_source is not None else None
    scope_source = mask_frame_for_display(scope_source) if scope_source is not None else None
    if active_tab == TAB_OVERVIEW:
        overview.render(frame, group_source=group_source, scope_source=scope_source)
    elif active_tab == TAB_VIDEO:
        video.render(frame)
    elif active_tab == TAB_INQUIRY:
        inquiry.render(frame)
    elif active_tab == TAB_IMPROVEMENT:
        improvement.render(frame)
    elif active_tab == TAB_PL:
        pl_issue.render(frame)


def _normalize_active_tab_state() -> None:
    if st.session_state.get(ACTIVE_TAB_KEY) not in OPERATING_TABS:
        st.session_state[ACTIVE_TAB_KEY] = TAB_OVERVIEW


def _store_topic_group_value() -> None:
    """사이드바에서 고른 값을 「값 키」에 되돌려 쓴다 (D-1b).

    ★ 개요 탭 그래프는 이 값 키만 본다. 위젯 키는 안 건드린다.
    """

    st.session_state[TOPIC_GROUP_VALUE_KEY] = list(
        st.session_state.get(FILTER_TOPIC_GROUP_KEY) or []
    )


def _sanitize_multiselect_state(key: str, options: list[str]) -> None:
    if key not in st.session_state:
        return
    allowed = set(options)
    current = st.session_state.get(key)
    if not isinstance(current, list):
        st.session_state[key] = []
        return
    st.session_state[key] = [value for value in current if value in allowed]


def _render_dataset_path_control() -> None:
    with st.expander("⚙️ 고급 옵션 · 데이터셋 경로", expanded=False):
        st.text_input(
            "66컬럼 CSV 경로",
            key=DATASET_WIDGET_KEY,
            on_change=_commit_dataset_path_from_widget,
        )
        st.caption("개발/디버깅용 설정입니다. 분석 결과 CSV 경로를 직접 바꿀 때만 사용하세요.")


def _advanced_options_enabled() -> bool:
    """Keep developer-only dataset controls out of the operator UI by default."""

    return os.environ.get("DASHBOARD60_SHOW_ADVANCED", "").strip().lower() in {"1", "true", "yes", "on"}


def _지금_지문(frame) -> tuple:
    """지금 화면에 올라온 데이터의 행수와 지문."""
    import hashlib

    if frame is None or "atomic_id" not in getattr(frame, "columns", []):
        return 0, ""
    ids = [str(x) for x in frame["atomic_id"].tolist()]
    return len(ids), hashlib.sha256(
        "\n".join(ids).encode("utf-8")).hexdigest()[:16]


def _편향_머리에(frame=None) -> None:
    """「이 데이터를 믿어도 되나」 — 제목 바로 아래에 둔다.

    ★ sky 2026-08-25 「제일 위 … 바로 보이게 하는 게 낫지 않을까요」
      어느 탭을 보든 **먼저** 알아야 하는 것이라 맨 위에 둔다.
      PL 탭 안에 넣었더니 PL 을 보는 사람만 보게 됐다.

    ★ 판정을 되돌리지 않는다. 「쟀고 이렇더라」 를 보여 줄 뿐이다.
    """
    import csv as _csv

    후보 = [
        Path("outputs/voc_secondary/_판독패키지/_결과/master_final/편향검사.csv"),
    ]
    길 = next((x for x in 후보 if x.exists()), None)
    if 길 is None:
        return
    try:
        with open(길, encoding="utf-8-sig", newline="") as h:
            행 = [r for r in _csv.reader(h) if any(r)]
    except OSError:
        return
    if len(행) < 2:
        return

    # ★ 언제 · 몇 행을 잰 것인가 (2026-08-25)
    #   안 보여 주면 다른 판 데이터를 올려도 옛 수치가 그대로 뜬다.
    머릿값 = {r[0]: (r[1] if len(r) > 1 else "") for r in 행 if r}
    잰날 = 머릿값.get("잰_날짜", "")
    잰행 = 머릿값.get("잰_대상_행수", "")

    # ★★ 지금 데이터와 맞는가 — 안 맞으면 **아예 안 보여 준다** (sky 2026-08-25)
    #   「지금 데이터 것이 아닙니다」 라고 사람에게 견주라고 떠넘기지 않는다.
    #   맞출 수 없으면 없는 것으로 친다.
    잰지문 = 머릿값.get("잰_데이터_지문", "")
    _n, _지문 = _지금_지문(frame)
    if not 잰지문 or not _지문 or 잰지문 != _지문:
        return
    시작 = next((i for i, r in enumerate(행) if r and r[0] == "감독자"), 0)
    머리 = 행[시작]
    몸 = [r for r in 행[시작 + 1:] if len(r) == len(머리)]
    쪽지 = [r for r in 행[시작 + 1:] if r and str(r[0]).startswith("★")]
    못쟀다 = any(r and str(r[0]).startswith("(못 쟀") for r in 몸)
    if 못쟀다:
        st.caption("🔎 편향검사 — **재지 못했습니다.** "
                   "판독자 둘의 결과가 한 자리에 섞여 있어 가릴 수 없었습니다.")
        return

    # 한 줄 요약을 제목 옆에 — 열지 않아도 보이게
    나쁨 = [r for r in 몸 if "★" in str(r[-1])]
    눈여겨 = [r for r in 몸 if "!" in str(r[-1])]
    if 나쁨:
        st.caption("🔎 **편향검사 — 사람이 판단해야 합니다** "
                   "(%s). 아래를 펴 보십시오." 
                   % " · ".join("%s %s" % (r[0], r[2]) for r in 나쁨))
    elif 눈여겨:
        st.caption("🔎 편향검사 — 눈여겨볼 것이 있습니다 (%s). 그대로 써도 됩니다."
                   % " · ".join("%s %s" % (r[0], r[2]) for r in 눈여겨))
    elif 몸:
        st.caption("🔎 **편향검사 통과** — 3차 감독이 자기 답을 %s 골랐습니다. "
                   "치우침 없음(40~60%%)."
                   % " · ".join("%s %s" % (r[0], r[2]) for r in 몸))

    with st.expander("이 데이터를 믿어도 되나 — 편향검사", expanded=False):
        st.caption(
            "2차 판독자 둘의 답을 A·B 로 가린 채 3차 감독이 골랐습니다. "
            "감독이 **자기 답을 얼마나 골랐는지** 를 총괄이 잰 결과입니다."
        )
        if 몸:
            st.dataframe(pd.DataFrame(몸, columns=머리),
                         width="stretch", hide_index=True)
        if 잰날 or 잰행:
            st.caption("잰 때 %s · 잰 대상 %s행" % (잰날 or "?", 잰행 or "?"))
        st.caption("**자** — 40~60% 치우침 없음 · 60~70% 눈여겨보되 그대로 "
                   "· 70% 넘으면 사람이 판단 · 둘 다 70% 넘으면 3차를 다시")
        for r in 쪽지:
            st.caption("· ".join(x for x in r if x))


def _deployment_commit_short() -> str:
    """Return the deployed git commit hash without blocking dashboard startup."""

    for env_name in ("STREAMLIT_GIT_COMMIT", "GITHUB_SHA", "COMMIT_SHA", "SOURCE_VERSION"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value[:7]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=2,
            check=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def main() -> None:
    st.set_page_config(page_title="YouTube VoC 분석 대시보드", page_icon="📊", layout="wide")
    inject_card_css()
    load_yaml_settings_optional()

    # ★ 「VoC 65」 는 개발 중 컬럼 수를 딴 이름이었다. 실무자에게는 뜻이 없다 (sky 2026-08-20)
    st.title("YouTube VoC 분석 대시보드")
    st.caption(f"배포 커밋: `{_deployment_commit_short()}`")
    st.caption(
        "YouTube 영상 댓글을 분석해 개선 포인트를 찾는 화면입니다. "
        "제품군 · 이유 topic · 감성을 나누어 보고, RootCause 까지 이어 봅니다."
    )

    # ★ 기본으로 열리는 자료 (sky 2026-08-20).
    #   2차 판독을 마친 pilot 최종본이다 — 1,698행. 최종 번들과 같은 자료다
    #   (atomic_id 1,698개가 전부 겹치는 것으로 대조 확인).
    #   전에는 151행짜리 시험용 fixture 가 기본이라, 화면을 처음 여는 사람이
    #   실제 결과가 아닌 것을 보고 있었다.
    default_candidates = [
        Path("outputs/voc_dashboard_60/voc2nd_pilot/voc_dashboard_dataset.csv"),
        # 위 파일이 없을 때 돌아갈 자리 — 예전 기본값
        Path(
            "outputs/voc_dashboard_60/taxonomy_redesign_live_robot_150_positive_aspect_20260731/voc_dashboard_dataset.csv"
        ),
    ]
    default_dataset = next(
        (path for path in default_candidates if path.exists()),
        latest_dataset(min_rows=10) or Path("outputs/voc_round7_120/voc_engine_output.csv"),
    )
    if DATASET_SESSION_KEY not in st.session_state:
        # 세션이 비었다 — 처음 열었거나, 웹소켓이 끊겼다가 다시 붙었다.
        # 후자를 기본 데이터셋으로 되돌리면 「필터를 만졌더니 첫 데이터로
        # 바뀌었다」 로 보인다. 세션 밖에 남겨 둔 것을 먼저 찾는다.
        st.session_state[DATASET_SESSION_KEY] = dataset_state.choose(
            query=st.query_params.get(dataset_state.QUERY_KEY),
            saved=dataset_state.recall(),
            default=str(default_dataset),
        )
    if st.session_state.get(DATASET_WIDGET_KEY) != st.session_state[DATASET_SESSION_KEY]:
        st.session_state[DATASET_WIDGET_KEY] = st.session_state[DATASET_SESSION_KEY]
    dataset_text = st.session_state[DATASET_SESSION_KEY]

    dataset_path = Path(dataset_text)
    if not dataset_path.exists():
        st.error(f"Dataset not found: {dataset_path}")
        return
    # 위젯·1차 실행·이전 결과 불러오기·업로드가 각각 세션에 경로를 쓴다.
    # 어디서 왔든 여기를 지나므로, 남기는 일은 이 한 자리에서만 한다.
    dataset_state.remember(dataset_text)
    if st.query_params.get(dataset_state.QUERY_KEY) != dataset_text:
        st.query_params[dataset_state.QUERY_KEY] = dataset_text

    frame = load_voc60_dataset(dataset_path)
    metadata = load_metadata(dataset_path)
    if metadata:
        st.caption(
            " · ".join(
                part
                for part in [
                    f"schema={metadata.get('schema_version', '')}",
                    f"parser={metadata.get('parser_version', '')}",
                    f"model={metadata.get('model', '')}",
                ]
                if part and not part.endswith("=")
            )
        )

    product_options = _options(frame["product_category"])
    brands_options = brand_filter_options(frame)
    market_options = _options(frame["market_display"])
    cej_options = _options(frame["cej"])
    filter_keys = {
        "products": FILTER_PRODUCT_KEY,
        "brands": FILTER_BRAND_KEY,
        "markets": FILTER_MARKET_KEY,
        "cejs": FILTER_CEJ_KEY,
    }

    with st.sidebar:
        st.header("데이터")
        # ★ 챗봇을 화면에서 뗐다 (sky 2026-08-20).
        #   하는 일이 「유튜브 실행 파라미터 설정」 과 「필터 적용」 둘뿐인데,
        #   둘 다 바로 아래 「실행/불러오기」·「필터」 에 직접 UI 가 이미 있었다.
        #   같은 일로 가는 두 번째 입구였고 그 입구가 잘 동작하지 않았다.
        #   코드와 시험은 src/dashboard60/chatbot.py 에 그대로 남겨 두었다.
        with st.container(border=True):
            st.markdown("##### 실행/불러오기")
            st.caption("새 분석 실행과 저장된 결과 재사용 기능을 한곳에 모았습니다.")
            render_analysis_runner(dataset_session_key=DATASET_SESSION_KEY)
        if _advanced_options_enabled():
            _render_dataset_path_control()
        # ★ 필터를 한 묶음으로 합치고 안에서 두 층으로 나눈다 (sky 2026-08-20).
        #   전에는 「Confidence 필터」 묶음과 「필터」 묶음이 그냥 위아래로 붙어 있어
        #   왜 갈렸는지 화면에 없었다. 실제로 성격이 다르다 —
        #   「무엇을 볼까」(대상 범위)와 「어디까지 볼까」(품질 문턱).
        #   이름을 붙여 그 차이를 드러낸다.
        st.header("필터")
        _sanitize_multiselect_state(FILTER_PRODUCT_KEY, product_options)
        _sanitize_multiselect_state(FILTER_BRAND_KEY, brands_options)
        _sanitize_multiselect_state(FILTER_MARKET_KEY, market_options)
        _sanitize_multiselect_state(FILTER_CEJ_KEY, cej_options)
        _sanitize_multiselect_state(FILTER_SENTIMENT_KEY, SENTIMENT_OPTIONS)
        # ★ st.pills 에는 default 인자가 없다. 처음 한 번만 상태로 넣어 준다.
        #   전에는 multiselect 의 default=SENTIMENT_OPTIONS 가 하던 일이다
        if FILTER_SENTIMENT_KEY not in st.session_state:
            st.session_state[FILTER_SENTIMENT_KEY] = list(SENTIMENT_OPTIONS)

        st.markdown("##### 무엇을 볼까")
        products = st.multiselect(
            "제품군", product_options, default=[], key=FILTER_PRODUCT_KEY, placeholder="전체"
        )
        # D-1 — 영역(topic_group). topic 39종이 늘어서기 전에 9종으로 먼저 좁힌다
        topic_group_options = topic_group_filter_options(frame)
        topic_groups: list[str] = []
        if topic_group_options:
            # ★ 위젯을 만들기 「전에」 값 키의 내용을 위젯 키에 넣는다.
            #   만든 뒤에는 못 바꾸므로, 그래프가 바꾼 값이 여기서 반영된다
            allowed = set(topic_group_options)
            st.session_state[FILTER_TOPIC_GROUP_KEY] = [
                value
                for value in (st.session_state.get(TOPIC_GROUP_VALUE_KEY) or [])
                if value in allowed
            ]
            topic_groups = st.multiselect(
                "개선/강화 영역",
                topic_group_options,
                key=FILTER_TOPIC_GROUP_KEY,
                on_change=_store_topic_group_value,
                placeholder="전체",
                help=(
                    "topic 위 단계입니다. 영역으로 먼저 좁힌 뒤 topic 으로 파고듭니다. "
                    "긍정 사례도 있으므로 「개선 영역」이 아니라 「개선/강화 영역」입니다. "
                    "「VoC 현황」 탭의 맨 위 그래프에서 막대를 눌러도 여기가 바뀝니다."
                ),
            )
        brands = st.multiselect(
            "브랜드", brands_options, default=[], key=FILTER_BRAND_KEY, placeholder="전체"
        )
        markets = st.multiselect(
            "국가/시장", market_options, default=[], key=FILTER_MARKET_KEY, placeholder="전체"
        )
        cejs = st.multiselect(
            "고객 여정 단계(CEJ)",
            cej_options,
            default=[],
            key=FILTER_CEJ_KEY,
            placeholder="전체",
            help="고객이 제품을 알게 되고 사고 쓰기까지의 9단계입니다.",
        )
        # ★ 감성은 셋으로 고정이라 알약 버튼이 맞는다. 목록을 펼칠 이유가 없다
        sentiments = st.pills(
            "감성",
            SENTIMENT_OPTIONS,
            selection_mode="multi",
            key=FILTER_SENTIMENT_KEY,
        )
        sentiments = list(sentiments or [])

        st.divider()
        st.markdown("##### 어디까지 볼까")
        st.caption("믿을 만한 행만 볼지 정하는 자리입니다. 위 칸들과 성격이 다릅니다.")
        confidence_levels, review_required_only = render_gating_controls()

    dimension_filtered = apply_filters(
        frame,
        products=products,
        topic_groups=topic_groups,
        brands=brands,
        markets=markets,
        cejs=cejs,
        sentiments=sentiments,
        high_confidence_only=False,
        review_required_only=False,
    )

    filtered = apply_operating_gates(
        frame,
        products=products,
        topic_groups=topic_groups,
        brands=brands,
        markets=markets,
        cejs=cejs,
        sentiments=sentiments,
        confidence_levels=confidence_levels,
        review_required_only=review_required_only,
    )
    filtered.attrs["dimension_filtered_total"] = len(dimension_filtered)

    with st.sidebar:
        confidence_filtered = apply_filters(
            frame,
            products=products,
            topic_groups=topic_groups,
            brands=brands,
            markets=markets,
            cejs=cejs,
            sentiments=sentiments,
            high_confidence_only=False,
            confidence_levels=confidence_levels,
            review_required_only=False,
        )
        # ★ 지금 몇 개가 걸려 있는지, 되돌리려면 어디를 누르는지 (sky 2026-08-20)
        applied = sum(
            1
            for chosen in (products, topic_groups, brands, markets, cejs)
            if chosen
        )
        if sorted(sentiments) != sorted(SENTIMENT_OPTIONS):
            applied += 1
        if sorted(confidence_levels) != sorted(DEFAULT_CONFIDENCE_LEVELS):
            applied += 1
        if review_required_only:
            applied += 1

        st.divider()
        hidden_by_confidence = max(0, len(dimension_filtered) - len(confidence_filtered))
        if confidence_levels:
            # ★ 분모는 len(frame) 이 아니라 dimension_filtered 다.
            #   frame 에는 scope 제외 행이 들어 있어 화면에 절대 안 나온다
            st.markdown(
                f"**{len(filtered):,}행** 보는 중"
                f" · 「무엇을 볼까」 통과 {len(dimension_filtered):,}행"
                + (f" · 조건 {applied}개 적용" if applied else " · 조건 없음")
            )
            if hidden_by_confidence:
                st.caption(
                    f"판정 충족도 기준으로 {hidden_by_confidence:,}행이 빠졌습니다"
                    f" (선택: {', '.join(confidence_levels)})."
                )
        else:
            st.warning("판정 충족도를 하나도 고르지 않아 볼 행이 없습니다.")
        st.button(
            "필터 초기화",
            key="dashboard60_reset_filters",
            on_click=_reset_filters,
            width="stretch",
            disabled=not applied,
            help="모든 조건을 처음 상태(판정 충족도 Very High·High, 감성 전체)로 되돌립니다.",
        )

    if filtered.empty:
        st.warning(
            "현재 필터 결과가 비었습니다."
            " 사이드바에서 조건을 풀거나 「필터 초기화」 를 눌러 보세요."
        )

    # ★ 편향검사를 **탭 바로 위**에 둔다 (sky 2026-08-25)
    #   「각 tab들이 모여있는 그 바로 위나 바로 아래」
    #   제목 아래보다 여기가 「이 화면들을 믿어도 되나」 로 읽힌다.
    _편향_머리에(frame)

    _normalize_active_tab_state()
    active_tab = st.radio(
        "운영 탭",
        OPERATING_TABS,
        horizontal=True,
        label_visibility="collapsed",
        index=OPERATING_TABS.index(st.session_state[ACTIVE_TAB_KEY]),
        key=ACTIVE_TAB_KEY,
    )
    # D-1b — 영역 그래프는 「영역 필터만 뺀」 집합으로 그린다.
    #        지금 보는 영역만 그리면 다른 영역으로 옮겨갈 수가 없다
    group_source = apply_operating_gates(
        frame,
        products=products,
        topic_groups=[],
        brands=brands,
        markets=markets,
        cejs=cejs,
        sentiments=sentiments,
        confidence_levels=confidence_levels,
        review_required_only=review_required_only,
    )
    # ★ 제외 사유 그래프는 「제외행이 살아 있는」 자료가 필요하다.
    #   제품군·브랜드·국가만 걸고, confidence·영역·CEJ·감성은 걸지 않는다.
    #   제외행은 신뢰도가 낮고 영역이 미판정이라 그 조건을 걸면 다 사라진다
    scope_source = apply_filters(
        frame,
        products=products,
        brands=brands,
        markets=markets,
        high_confidence_only=False,
        include_scope_excluded=True,
    )
    _render_active_tab(
        filtered, active_tab, group_source=group_source, scope_source=scope_source
    )


if __name__ == "__main__":
    main()
