# 원문 — 대시보드 「새로 분석 돌리기」 입력 칸 (코드 그대로)

> 이 파일은 **요약이 아니다.** 원본 코드의 해당 줄을 한 글자도 바꾸지 않고 옮겼다.
> `running-voc-engine` 스킬의 실행조건서는 이 원문의 칸·기본값·안내문을 하나도 빼지 않는다.
>
> 원본: `C:\codex_live_merge\src\dashboard60\analysis_runner.py` (마지막 커밋 8117810 2026-08-20 17:53:20 +0900)

## 80–97줄 · 상수 — 최댓값·칸 이름·국가/언어 도움말

```python
MIN_ANALYZED_RESULT_COLUMNS = 50
AUTO_REFRESH_INTERVAL_MS = 5_000
RUN_STATE_FILENAME = "dashboard_run_state.json"
MAX_YOUTUBE_VIDEOS = 500
MAX_COMMENTS_PER_VIDEO = 2_000
MAX_ANALYSIS_ROWS = 10_000
VIDEO_COUNT_LABEL = f"영상 수 (최대 {MAX_YOUTUBE_VIDEOS}개)"
COMMENT_COUNT_LABEL = f"영상당 댓글 수 (최대 {MAX_COMMENTS_PER_VIDEO}건)"
ANALYSIS_LIMIT_LABEL = f"분석 최대 행 수 (0=전체, 최대 {MAX_ANALYSIS_ROWS:,}건)"
REGION_HELP_TEXT = (
    "YouTube search.list의 regionCode에 전달되는 ISO 3166-1 alpha-2 국가코드입니다. "
    "예: 한국 KR, 미국 US, 일본 JP, 영국 GB. 검색 결과의 지역 관련성에 영향을 주지만 엄격한 국가 필터는 아닙니다."
)
LANGUAGE_HELP_TEXT = (
    "YouTube search.list의 relevanceLanguage에 전달되는 ISO 639-1 언어코드입니다. "
    "예: 한국어 ko, 영어 en, 일본어 ja. 검색 관련성에 영향을 주지만 댓글 언어를 엄격히 걸러내지는 않습니다. "
    "자주 쓰는 조합: 한국 KR/ko, 미국 US/en, 일본 JP/ja, 영국 GB/en."
)
```

## 1300–1534줄 · 입력 칸 화면 — 안내 팝업 · 결합 방식 안내 · 입력 유형 · YouTube 수집 조건

```python
def _render_compact_guide(topic: str) -> None:
    with st.popover("ⓘ", help="입력/채널/모델 가이드"):
        if topic == "input_type":
            st.markdown(
                """
                **입력 유형 가이드**

                - **이미 정리된 폴더**: 앞서 수집·정리해 둔 폴더를 분석합니다 (`comments_normalized.parquet` 가 있는 폴더).
                - **원본 파일 올리기**: 아직 분석하지 않은 댓글 파일(CSV/XLSX)을 올려 분석합니다.
                - **YouTube 에서 새로 모으기**: 키워드로 댓글을 새로 모아 바로 분석합니다.
                - **이전 분석 결과 불러오기**는 아래 별도 섹션에서 CSV/6-Sheet Excel을 업로드하며, 재분석하지 않습니다.
                """
            )
        elif topic == "channel_id":
            st.markdown(
                """
                **채널 ID**

                특정 채널 영상만 수집하고 싶을 때 입력합니다. 비워두면 키워드 검색 전체에서 영상을 찾습니다.
                채널 ID는 YouTube 채널 URL/페이지 소스/API 조회에서 확인할 수 있는 `UC...` 형식 값입니다.
                """
            )
        elif topic == "model":
            st.markdown(
                """
                **모델**

                비워두면 엔진 기본 모델을 사용합니다. 모델을 바꾸면 비용·속도·분류 품질이 달라질 수 있으므로
                운영 검증이 끝난 모델만 입력하는 것을 권장합니다.
                """
            )


def _keyword_mode_note(mode: str, keywords: list[str]) -> str:
    """고른 방식이 실제로 어떻게 도는지 한 줄로 (sky 2026-08-20).

    ★ 「맨 윗줄이 무엇을 모을지 정합니다」 는 결과만 말하고 과정을 안 말했다.
      왜 순서가 중요한지가 안 와닿는다.
      「A 로 찾고 → 그 안에서 B 가 있는 것만」 이 실제 동작이면서 잘 읽힌다.
    """

    if str(mode).upper() != "AND":
        return "키워드마다 따로 찾아 결과를 합칩니다. 적는 순서는 상관없습니다."
    if not keywords:
        return "위에서 아래로 범위를 좁혀 갑니다. 넓은 말을 위에 적으십시오."
    if len(keywords) == 1:
        return f"「{keywords[0]}」 로 찾습니다. 아래에 말을 더 적으면 그 안에서 더 좁혀 갑니다."

    steps = [f"「{keywords[0]}」 로 찾고"]
    for word in keywords[1:]:
        steps.append(f"그중 「{word}」 가 있는 것만")
    return (
        " → ".join(steps)
        + " 남깁니다. (두 번째 줄부터는 영상의 제목·설명·채널명·태그에서 찾습니다)"
    )


def _source_controls() -> tuple[str, Path | None, dict[str, Any]]:
    label_cols = st.columns([0.88, 0.12])
    with label_cols[0]:
        st.markdown("**입력 유형**")
    with label_cols[1]:
        _render_compact_guide("input_type")
    source_type_label = st.radio(
        "입력 유형",
        ["이미 정리된 폴더", "원본 파일 올리기", "YouTube 에서 새로 모으기"],
        horizontal=False,
        label_visibility="collapsed",
    )
    if source_type_label.startswith("이미"):
        processed_text = st.text_input(
            "폴더 경로",
            value="",
            placeholder="예: data/processed/<run_id>",
            help="comments_normalized.parquet와 videos_normalized.parquet가 있는 폴더입니다.",
        )
        source_path = Path(processed_text).expanduser() if _safe_text(processed_text) else None
        return "processed", source_path, {}

    if source_type_label.startswith("원본"):
        uploaded = st.file_uploader(
            "분석 전 원본 파일",
            type=["csv", "xlsx", "xls", "parquet"],
            help="아직 분석하지 않은 댓글 파일입니다. 분석이 끝난 파일은 「결과 파일 올려서 보기」 로 가세요.",
        )
        source_path = None
        if uploaded is not None:
            upload_bytes = uploaded.getvalue()
            upload_sig = f"{getattr(uploaded, 'name', '')}:{len(upload_bytes)}"
            if st.session_state.get(SESSION_UPLOAD_SIG_KEY) != upload_sig:
                source_path = _save_uploaded_file(uploaded)
                st.session_state[SESSION_UPLOAD_SIG_KEY] = upload_sig
                st.session_state[SESSION_UPLOAD_PATH_KEY] = str(source_path)
            else:
                source_path = Path(st.session_state.get(SESSION_UPLOAD_PATH_KEY, ""))
            st.success(f"업로드 저장: `{source_path}`")
        return "raw", source_path, {}

    youtube_params: dict[str, Any] = {}
    keywords_text = st.text_area(
        "검색 키워드",
        value="LG 로봇청소기 로니",
        help=(
            "한 줄에 하나씩 적습니다.\n\n"
            "★ AND 로 묶으면 위에서 아래로 범위를 좁혀 갑니다.\n"
            "그래서 넓은 말을 위에, 좁은 말을 아래에 적으십시오.\n\n"
            "예:  로봇청소기 → LG 로봇청소기 → 로니"
        ),
        height=88,
    )
    youtube_params["keywords_text"] = keywords_text
    youtube_params["keywords"] = _parse_keyword_terms(keywords_text)
    youtube_params["keyword_mode"] = st.selectbox(
        "키워드 결합",
        ["OR", "AND"],
        index=0,
        # ★ 적혀 있던 AND 설명이 실제와 달랐다 (sky 2026-08-20).
        #   "키워드별 개별 검색 후 공통" 이라 되어 있었으나,
        #   실제로는 첫 키워드로 한 번만 검색하고 나머지는 영상 정보에서 글자로 찾는다
        #   (ingest_pipeline.py 의 _search_keyword_intersection · _keyword_matches_video_metadata)
        help=(
            "OR — 키워드마다 따로 검색해서 결과를 합칩니다. 중복 영상은 하나로 칩니다.\n\n"
            "AND — 맨 윗줄 키워드로만 검색합니다. 아랫줄 키워드는 그 결과 영상의 "
            "제목·설명·채널명·태그에 그 말이 들어 있는지로 걸러냅니다.\n"
            "★ 그래서 맨 윗줄을 무엇으로 적느냐가 결과를 좌우합니다."
        ),
    )
    youtube_params["and_min_keyword_matches"] = None
    # ★ 안내는 여기 한 곳에만 둔다 (sky 2026-08-20).
    #   고른 방식에 따라 말이 달라지므로 나눠 두면 오히려 헷갈린다
    st.caption(_keyword_mode_note(youtube_params["keyword_mode"], youtube_params["keywords"]))
    if youtube_params["keyword_mode"] == "AND" and len(youtube_params["keywords"]) >= 3:
        and_match_mode = st.selectbox(
            "AND 키워드 매칭 방식",
            ["모든 키워드 포함", "최소 N개 키워드 포함"],
            index=0,
            help=(
                "모든 키워드 포함 — 아랫줄 말이 전부 들어 있어야 남깁니다.\n"
                "최소 N개 — 그중 N개만 들어 있어도 남깁니다. 너무 적게 잡힐 때 씁니다."
            ),
        )
        if and_match_mode == "최소 N개 키워드 포함":
            youtube_params["and_min_keyword_matches"] = int(
                st.number_input(
                    "최소 매칭 키워드 수",
                    min_value=2,
                    max_value=max(2, len(youtube_params["keywords"]) - 1),
                    value=max(2, len(youtube_params["keywords"]) - 1),
                    step=1,
                    help="예: 세 줄 중 두 줄이 제목·설명·채널명·태그에 잡히면 남깁니다.",
                )
            )
    if youtube_params["keywords"]:
        st.caption("검색 태그: " + " · ".join(f"`{term}`" for term in youtube_params["keywords"]))
    date_cols = st.columns(2)
    with date_cols[0]:
        published_after_date = st.date_input(
            "영상 게시일 범위(시작)",
            value=None,
            help="지정하지 않으면 게시일 제한 없이 검색합니다.",
        )
    with date_cols[1]:
        published_before_date = st.date_input(
            "영상 게시일 범위(종료)",
            value=None,
            help="지정하지 않으면 게시일 제한 없이 검색합니다.",
        )
    youtube_params["published_after"] = _youtube_published_boundary(published_after_date)
    youtube_params["published_before"] = _youtube_published_boundary(published_before_date, end_of_day=True)
    youtube_params["region"] = st.text_input(
        "국가/시장 코드",
        value="KR",
        help=REGION_HELP_TEXT,
    )
    youtube_params["language"] = st.text_input(
        "언어 코드",
        value="ko",
        help=LANGUAGE_HELP_TEXT,
    )
    all_videos = st.checkbox(
        f"검색 가능한 영상 최대 범위(최대 {MAX_YOUTUBE_VIDEOS}개)",
        value=False,
        help="YouTube 검색 API가 반환하는 범위 안에서 최대 500개까지 탐색합니다.",
    )
    requested_videos = st.number_input(
        VIDEO_COUNT_LABEL,
        min_value=1,
        max_value=MAX_YOUTUBE_VIDEOS,
        value=2,
        step=1,
        disabled=all_videos,
    )
    youtube_params["max_videos"] = MAX_YOUTUBE_VIDEOS if all_videos else int(requested_videos)
    all_comments = st.checkbox(
        "각 영상의 댓글 가능한 모두 수집 (댓글 수 0과 동일)",
        value=False,
        help="YouTube API가 제공하는 모든 commentThreads 페이지를 끝까지 순회합니다.",
    )
    requested_comments = st.number_input(
        COMMENT_COUNT_LABEL,
        min_value=1,
        max_value=MAX_COMMENTS_PER_VIDEO,
        value=10,
        step=10,
        disabled=all_comments,
    )
    youtube_params["comments_per_video"] = 0 if all_comments else int(requested_comments)
    youtube_params["include_replies"] = st.checkbox("대댓글 포함", value=True)
    channel_cols = st.columns([0.88, 0.12])
    with channel_cols[0]:
        youtube_params["channel_id"] = st.text_input("채널 ID(선택)", value="")
    with channel_cols[1]:
        _render_compact_guide("channel_id")
    quota = _estimate_youtube_quota_for_keywords(
        max_videos=int(youtube_params["max_videos"]),
        comments_per_video=int(youtube_params["comments_per_video"]),
        include_replies=bool(youtube_params["include_replies"]),
        keyword_count=len(youtube_params["keywords"]) or 1,
        keyword_mode=str(youtube_params["keyword_mode"]),
        and_min_keyword_matches=youtube_params.get("and_min_keyword_matches"),
    )
    st.caption(
        "예상 YouTube quota: "
        f"{quota['total_units']} units "
        f"(search {quota['search.list']}, videos {quota['videos.list']}, "
        f"comments {quota['commentThreads.list']}, replies {quota['comments.list']})"
    )
    if all_videos or all_comments:
        st.warning(
            "가능한 모두 수집은 영상/댓글 수에 따라 1시간 이상 걸릴 수 있고 YouTube/OpenAI 비용이 크게 늘 수 있습니다. "
            "실행 전 quota와 분석 최대 행수를 꼭 확인하세요."
        )
    if not _resolve_youtube_api_key():
        st.warning("YOUTUBE_API_KEY가 감지되지 않았습니다. Streamlit Secrets 또는 환경변수에 추가해야 직접 수집을 실행할 수 있습니다.")
    return "youtube", None, youtube_params
```

## 1905–1959줄 · 분석 파라미터 칸 · 비용 확인 동의

```python
        source_type, source_path, youtube_params = _source_controls()

        st.markdown("##### 분석 파라미터")
        limit = st.number_input(
            ANALYSIS_LIMIT_LABEL,
            min_value=0,
            max_value=MAX_ANALYSIS_ROWS,
            value=20,
            step=5,
        )
        batch_size = st.number_input(
            "한 번에 묶어 처리할 건수",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
            help="이 건수마다 중간 저장합니다. 중간에 끊겨도 여기까지는 남습니다.",
        )
        timeout_seconds = st.number_input(
            "한 묶음 최대 대기 시간(초)",
            min_value=30,
            max_value=300,
            value=120,
            step=10,
            help="이 시간을 넘기면 그 묶음을 실패로 보고 다음으로 넘어갑니다.",
        )
        model_cols = st.columns([0.88, 0.12])
        with model_cols[0]:
            model = st.text_input(
                "모델", value="", placeholder="비워 두면 기본값", help="보통 비워 둡니다."
            )
        with model_cols[1]:
            _render_compact_guide("model")
        sample_across_videos = True
        run_suffix = st.text_input(
            "실행 이름",
            value="dashboard60_app_run",
            help="저장될 폴더 이름 앞부분입니다. 뒤에 날짜·시각이 자동으로 붙습니다.",
        )

        # ★ 비용 확인을 여기에도 둔다 (sky 2026-08-20).
        #   「같은 원문으로 다시 분석」 에는 있는데 여기에는 없었다.
        #   둘 다 똑같이 OpenAI 를 부르는데 더 큰 쪽(새 수집)이 무방비였다.
        run_confirmed = st.checkbox(
            "OpenAI API 로 분석하는 비용과 시간을 확인했습니다.",
            value=False,
            key="dashboard60_new_run_confirm",
            help="이미 분석한 것을 다시 보려면 「저장된 실행에서 고르기」 를 쓰세요. 그쪽은 비용이 들지 않습니다.",
        )
        if source_type == "youtube":
            disabled = run_is_active or not youtube_params.get("keywords") or not _resolve_youtube_api_key()
        else:
            disabled = run_is_active or source_path is None or not _safe_text(str(source_path))
        # ★ 기존 조건은 그대로 두고 한 항만 덧붙인다
        disabled = disabled or not run_confirmed
```

옮긴 줄 수: 308 (세 구간 합계)
