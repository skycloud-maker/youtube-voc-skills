"""Data contract helpers for the 66-column VoC operating dashboard."""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Iterable

import pandas as pd
from pandas.errors import EmptyDataError

from src.voc_rebuild import TARGET_COLUMNS


SCHEMA_VERSION = "voc-66col-v2.9"
PARSER_VERSION = "voc-rebuild-engine"

CEJ_VALUES = [
    "인지",
    "탐색",
    "결정",
    "구매",
    "배송",
    "사용준비",
    "사용",
    "관리",
    "교체",
    "해당없음",
]

DEFAULT_CONFIDENCE_LEVELS = ["Very High", "High"]
CONFIDENCE_LEVELS = ["Very High", "High", "Medium", "Low"]
CONFIDENCE_PASS_VALUES = set(DEFAULT_CONFIDENCE_LEVELS)
SCOPE_EXCLUSION_REASONS = [
    "empty",
    "operator_notice",
    "channel_request",
    "channel_feedback",
    "out_of_scope_product",
    "no_analytic_value",
    "unresolvable_reply",
]
SCOPE_EXCLUSION_REASON_LABELS = {
    "empty": "빈 댓글/정제 후 내용 없음",
    "operator_notice": "운영자 공지·제휴 링크",
    "channel_request": "채널/리뷰 요청",
    "channel_feedback": "채널/영상 피드백",
    "out_of_scope_product": "분석 대상 밖 제품",
    "no_analytic_value": "분석 가치 낮은 잡담/반응",
    "unresolvable_reply": "부모 맥락으로도 해소 불가",
}
MARKET_DISPLAY_MAP = {
    "KR": "한국",
    "Korea": "한국",
    "한국": "한국",
    "국내": "한국",
    "대한민국": "한국",
    "N/A": "N/A",
    "": "N/A",
}

DERIVED_COLUMNS_DEFAULTS = {
    "sentiment_dir": "중립",
    "market_display": "N/A",
    "brand_display": "",
    "competitor_brand_display_tags": "",
    "cej_group": "해당없음",
    "validity": "무효",
    "confidence_gate": False,
    "review_queue": False,
}
BRAND_SYNONYM_MAP = {
    "china": "중국 브랜드",
    "chinese": "중국 브랜드",
    "chinese brand": "중국 브랜드",
    "chinese brands": "중국 브랜드",
    "chinese product": "중국 브랜드",
    "chinese products": "중국 브랜드",
    "중공": "중국 브랜드",
    "중국": "중국 브랜드",
    "중국 브랜드": "중국 브랜드",
    "중국브랜드": "중국 브랜드",
    "중국 회사": "중국 브랜드",
    "중국회사": "중국 브랜드",
    "중국 기업": "중국 브랜드",
    "중국기업": "중국 브랜드",
    "중국 제품": "중국 브랜드",
    "중국제품": "중국 브랜드",
    "중국산": "중국 브랜드",
    "roborock": "로보락",
    "Roborock": "로보락",
    "ROBOROCK": "로보락",
    "ecovacs": "에코백스",
    "Ecovacs": "에코백스",
    "ECOVACS": "에코백스",
    "dreame": "드리미",
    "Dreame": "드리미",
    "DREAME": "드리미",
    "xiaomi": "샤오미",
    "Xiaomi": "샤오미",
    "XIAOMI": "샤오미",
    "narwal": "나르왈",
    "Narwal": "나르왈",
    "NARWAL": "나르왈",
    "picea": "피세아",
    "Picea": "피세아",
    "PICEA": "피세아",
    "피세아": "피세아",
}
CHINA_BRAND_GROUP_MEMBERS = {
    "중국 브랜드",
    "로보락",
    "에코백스",
    "드리미",
    "샤오미",
    "나르왈",
    "피세아",
}

# Kept for backward compatibility only. The operating dashboard displays and
# filters canonical CEJ 9-stage values, not this unapproved 5-group proposal.
CEJ_GROUP_MAP = {
    "인지": "인지/탐색",
    "탐색": "인지/탐색",
    "결정": "결정/구매",
    "구매": "결정/구매",
    "배송": "배송/사용준비",
    "사용준비": "배송/사용준비",
    "사용": "사용",
    "관리": "관리/교체",
    "교체": "관리/교체",
    "해당없음": "해당없음",
    "N/A": "해당없음",
    "": "해당없음",
}


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _market_display(value: object) -> str:
    text = _safe_text(value)
    return MARKET_DISPLAY_MAP.get(text, text or "N/A")


def _split_tag_values(value: object) -> list[str]:
    text = _safe_text(value)
    if not text or text in {"N/A", "[]"}:
        return []
    text = text.strip("[]")
    parts = re.split(r"[,;/|]", text)
    cleaned = []
    for part in parts:
        item = part.strip().strip("'\"").strip()
        if item and item not in {"N/A", "[]"}:
            cleaned.append(item)
    return cleaned


def _normalize_brand_display(value: object) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    normalized_space = re.sub(r"\s+", " ", text)
    compact = normalized_space.replace(" ", "")
    lower = normalized_space.lower()
    for key in (normalized_space, compact, lower):
        if key in BRAND_SYNONYM_MAP:
            return BRAND_SYNONYM_MAP[key]
    return normalized_space





# ``entity_role`` 이 담는 값. 브랜드 이름이 아니라 **역할** 이름이다.
ENTITY_ROLE_VALUES = frozenset(
    {"product_brand", "competitor_brand", "creator_channel", "unknown"}
)


def _brand_display(row: object) -> str:
    """브랜드 필터가 쓸 「이 말이 자사 얘기인가」.

    왜 이렇게 하나
    --------------
    ``brand`` 칸의 사전 정의는 「원문 표기 브랜드」 인데, 실제로는
    ``reference_brand`` (자사 = LG) 를 그대로 받는다. 6,846행 중 6,387행이 LG 다.
    그대로 필터에 쓰면 **LG 를 고를 때 전체의 93% 가 딸려 온다** —
    「중국산 청소기 카메라 조심」 처럼 LG 가 한 글자도 안 나오는 말까지.
    LG 하나가 다른 브랜드를 전부 먹어서 필터가 사실상 안 걸렸다.

    ``entity_role`` 이 「누구 얘기인가」 를 이미 담고 있다 (데이터사전 34번 —
    「주체 구분(자사/경쟁/채널/불명). 개선 우선순위 집계 라우팅 축」).
    그 축을 그대로 쓴다.

        product_brand      자사 얘기        → brand 를 쓴다
        competitor_brand   경쟁사 얘기      → 빈칸. 경쟁사 태그 칸이 따로 잡는다
        creator_channel    채널·리뷰어 얘기  → 빈칸. 브랜드 얘기가 아니다
        unknown            불명            → 빈칸. 모르면 아무 브랜드도 아니다

    ★ ``entity_role`` 이 아예 없거나 비어 있으면 **옛 동작 그대로** ``brand`` 를 쓴다.
      그 축이 없는 데이터셋에서까지 값을 지우면 안 된다.

    ★ ``brand`` 에 역할 이름이 새어 들어간 275행(`unknown` 200 · `creator_channel` 75)
      은 어느 경우든 빈칸으로 만든다. 브랜드 이름 칸에 역할 이름이 들어가면
      사이드바 목록에 「creator_channel 브랜드」 가 뜬다 (E-2).

    남는 값
    -------
    LG 필터가 6,392행 → 3,160행이 된다. 빠지는 3,232행 중 **96% 는 원문에
    LG 표기가 아예 없다.** 나머지 4%(115행)는 LG 를 말하지만 역할이
    채널·불명인 행이라 같이 빠진다 — 그 값은 감수한다.
    원본 ``brand`` 칸은 건드리지 않는다. 여기서 만드는 것은 화면용 파생 칸이다.
    """
    brand = _normalize_brand_display(row.get("brand"))
    if brand in ENTITY_ROLE_VALUES:
        brand = ""
    role = _safe_text(row.get("entity_role"))
    if not role:
        return brand
    return brand if role == "product_brand" else ""


def _normalize_brand_tags_display(value: object) -> str:
    values = [_normalize_brand_display(item) for item in _split_tag_values(value)]
    deduped = []
    seen: set[str] = set()
    for item in values:
        if item and item not in seen:
            deduped.append(item)
            seen.add(item)
    return ", ".join(deduped)


def _expand_brand_filter_values(values: Iterable[str]) -> set[str]:
    expanded: set[str] = set()
    for value in values:
        normalized = _normalize_brand_display(value)
        if not normalized:
            continue
        expanded.add(normalized)
        compact = normalized.replace(" ", "")
        if "중국" in normalized or "중국" in compact:
            expanded.update(CHINA_BRAND_GROUP_MEMBERS)
    return expanded


def _brand_matches(value: object, selected: set[str]) -> bool:
    normalized = _normalize_brand_display(value)
    if not normalized:
        return False
    compact = normalized.replace(" ", "").lower()
    for candidate in selected:
        normalized_candidate = _normalize_brand_display(candidate)
        candidate_compact = normalized_candidate.replace(" ", "").lower()
        if not candidate_compact:
            continue
        if compact == candidate_compact or candidate_compact in compact or compact in candidate_compact:
            return True
    return False


def brand_filter_options(frame: pd.DataFrame) -> list[str]:
    """Return self/creator/unknown brands plus competitor tags for the sidebar."""

    values: set[str] = set()
    brand_column = "brand_display" if "brand_display" in frame.columns else "brand"
    competitor_column = "competitor_brand_display_tags" if "competitor_brand_display_tags" in frame.columns else "competitor_brand_tags"
    if brand_column in frame.columns:
        values.update(_safe_text(value) for value in frame[brand_column].dropna().unique())
    if competitor_column in frame.columns:
        for value in frame[competitor_column].dropna().unique():
            values.update(_split_tag_values(value))
    normalized_values = {_normalize_brand_display(value) for value in values if value}
    if normalized_values.intersection(CHINA_BRAND_GROUP_MEMBERS):
        normalized_values.update({"중국 브랜드", "중국 제품"})
    return sorted(value for value in normalized_values if value)


def latest_dataset(root: Path = Path("outputs/voc_dashboard_60"), *, min_rows: int = 1) -> Path | None:
    if not root.exists():
        return None
    candidates = sorted(root.glob("*/voc_dashboard_dataset.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in candidates:
        try:
            row_count = sum(1 for _ in candidate.open("r", encoding="utf-8-sig")) - 1
        except OSError:
            row_count = 0
        if row_count >= min_rows:
            return candidate
    return candidates[0] if candidates else None


def load_metadata(dataset_path: str | Path) -> dict:
    metadata_path = Path(dataset_path).parent / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_voc60_dataset(path: str | Path) -> pd.DataFrame:
    dataset_path = Path(path)
    try:
        frame = pd.read_csv(dataset_path, keep_default_na=False)
    except EmptyDataError:
        frame = pd.DataFrame()
    for column in TARGET_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    extra_columns = [column for column in frame.columns if column not in TARGET_COLUMNS]
    frame = frame[[*TARGET_COLUMNS, *extra_columns]]

    return materialize_dashboard_columns(frame)


def materialize_dashboard_columns(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Return a dashboard-safe frame with derived display/filter columns computed."""

    frame = ensure_dashboard_columns(frame)
    for column in (
        "topic_score",
        "tee_time_score",
        "tee_effort_score",
        "tee_emotion_score",
        "tee_success_score",
        "rootcause_score",
        "voc_total_score",
    ):
        frame[column] = _to_number(frame[column])

    frame["sentiment_dir"] = frame.apply(_sentiment_dir, axis=1)
    frame["market_display"] = frame["market"].map(_market_display)
    frame["brand_display"] = frame.apply(_brand_display, axis=1)
    frame["competitor_brand_display_tags"] = frame["competitor_brand_tags"].map(_normalize_brand_tags_display)
    frame["cej_group"] = frame["cej"].map(lambda value: CEJ_GROUP_MAP.get(_safe_text(value), "해당없음"))
    frame["validity"] = frame.apply(_validity, axis=1)
    frame["confidence_gate"] = frame["confidence_rating"].map(lambda value: _safe_text(value) in CONFIDENCE_PASS_VALUES)
    frame["review_queue"] = frame["review_required"].map(lambda value: _safe_text(value).upper() == "Y")
    return ensure_dashboard_columns(frame)


def ensure_dashboard_columns(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Return a dashboard-safe frame even when the source is empty or partial."""

    result = frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()
    for column in TARGET_COLUMNS:
        if column not in result.columns:
            result[column] = pd.Series(dtype="object")
    for column, default in DERIVED_COLUMNS_DEFAULTS.items():
        if column not in result.columns:
            result[column] = default
    return result


def _sentiment_dir(row: pd.Series) -> str:
    emotion = float(row.get("tee_emotion_score", 0) or 0)
    success = float(row.get("tee_success_score", 0) or 0)
    score = emotion if emotion != 0 else success
    if score > 0:
        return "긍정"
    if score < 0:
        return "부정"
    return "중립"


def _validity(row: pd.Series) -> str:
    topic = _safe_text(row.get("topic"))
    status = _safe_text(row.get("status"))
    if topic == "N/A" or status == "scope_excluded":
        return "무효"
    return "유효"


def apply_filters(
    frame: pd.DataFrame,
    *,
    products: Iterable[str] | None = None,
    topic_groups: Iterable[str] | None = None,
    brands: Iterable[str] | None = None,
    markets: Iterable[str] | None = None,
    cejs: Iterable[str] | None = None,
    sentiments: Iterable[str] | None = None,
    cej_groups: Iterable[str] | None = None,
    high_confidence_only: bool = True,
    confidence_levels: Iterable[str] | None = None,
    review_required_only: bool = False,
    include_scope_excluded: bool = False,
) -> pd.DataFrame:
    result = ensure_dashboard_columns(frame)
    if not include_scope_excluded:
        result = result[result["status"].fillna("").eq("normal")]
    selected_confidence = (
        {_safe_text(value) for value in confidence_levels if _safe_text(value)}
        if confidence_levels is not None
        else None
    )
    if selected_confidence is not None:
        result = result[result["confidence_rating"].fillna("").isin(selected_confidence)]
    elif high_confidence_only:
        result = result[result["confidence_gate"]]
    if review_required_only:
        result = result[result["review_queue"]]
    if products:
        selected = set(products)
        result = result[result["product_category"].fillna("").isin(selected)]
    if topic_groups and "topic_group" in result.columns:
        # D-1 — 영역 필터. topic 39종 대신 9종 영역으로 먼저 좁힌다
        selected = set(topic_groups)
        result = result[result["topic_group"].fillna("").isin(selected)]
    if brands:
        selected = _expand_brand_filter_values(brands)
        own_column = "brand_display" if "brand_display" in result.columns else "brand"
        competitor_column = "competitor_brand_display_tags" if "competitor_brand_display_tags" in result.columns else "competitor_brand_tags"
        own_brand = result[own_column].map(lambda value: _brand_matches(value, selected))
        competitor_brand = result[competitor_column].map(
            lambda value: any(_brand_matches(item, selected) for item in _split_tag_values(value))
        )
        result = result[own_brand | competitor_brand]
    if markets:
        selected = set(markets)
        market_column = "market_display" if "market_display" in result.columns else "market"
        result = result[result[market_column].fillna("").isin(selected)]
    if sentiments is not None:
        selected = {_safe_text(value) for value in sentiments if _safe_text(value)}
        result = result[result["sentiment_dir"].fillna("").isin(selected)]
    if cejs:
        selected = set(cejs)
        result = result[result["cej"].fillna("").isin(selected)]
    elif cej_groups:
        selected = set(cej_groups)
        result = result[result["cej_group"].isin(selected)]
    return result


# D-1 — 영역 필터의 session_state 키.
#   ★ 두 개로 나눈 이유 — Streamlit 은 위젯이 만들어진 뒤 그 위젯의 상태를
#     바꾸지 못하게 막는다. 사이드바 위젯이 먼저 생기므로, 나중에 그리는
#     개요 탭 그래프가 위젯 키에 직접 쓰면 예외가 난다.
#     그래서 「값」은 별도 키에 두고, 사이드바는 위젯을 만들기 전에 그 값을 읽어 넣는다.
TOPIC_GROUP_VALUE_KEY = "dashboard60_topic_groups_value"   # 진짜 값. 누구나 쓸 수 있다
FILTER_TOPIC_GROUP_KEY = "dashboard60_filter_topic_groups"  # 사이드바 위젯 전용


def topic_group_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    """영역별 건수. 값이 없는 행은 「미판정」으로 모은다."""

    if "topic_group" not in frame.columns or frame.empty:
        return pd.DataFrame(columns=["topic_group", "count", "share"])
    values = frame["topic_group"].fillna("").map(_safe_text).replace("", "미판정")
    counts = values.value_counts()
    total = int(counts.sum()) or 1
    return pd.DataFrame(
        {
            "topic_group": counts.index,
            "count": counts.values,
            "share": counts.values / total,
        }
    )


def topic_group_filter_options(frame: pd.DataFrame) -> list[str]:
    """영역 선택지. 데이터에 topic_group 칸이 없으면 빈 목록을 준다.

    ★ 빈 목록이면 화면에서 필터를 아예 안 그린다. 옛 번들도 그대로 열린다.
    """

    if "topic_group" not in frame.columns:
        return []
    values = {_safe_text(value) for value in frame["topic_group"].fillna("")}
    return sorted(value for value in values if value)


def topic_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    frame = ensure_dashboard_columns(frame)
    if frame.empty:
        return pd.DataFrame(columns=["topic", "count", "share"])
    counts = frame["topic"].fillna("N/A").replace("", "N/A").value_counts()
    total = counts.sum() or 1
    return pd.DataFrame({"topic": counts.index, "count": counts.values, "share": counts.values / total})


def scope_exclusion_reason_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Return scope_excluded counts for all canonical exclusion reasons.

    All seven Phase 0 reasons are emitted even when the count is zero, so missing
    or unused reason categories are visible in the operating dashboard.
    """

    frame = ensure_dashboard_columns(frame)
    scoped = frame[frame["status"].fillna("").eq("scope_excluded")].copy()
    reasons = scoped["scope_exclusion_reason"].fillna("").map(_safe_text) if not scoped.empty else pd.Series(dtype=str)
    counts = reasons.value_counts().to_dict()

    rows = [
        {
            "scope_exclusion_reason": reason,
            "reason_label": SCOPE_EXCLUSION_REASON_LABELS[reason],
            "count": int(counts.get(reason, 0)),
        }
        for reason in SCOPE_EXCLUSION_REASONS
    ]
    for reason, count in sorted(counts.items()):
        if reason and reason not in SCOPE_EXCLUSION_REASON_LABELS:
            rows.append(
                {
                    "scope_exclusion_reason": reason,
                    "reason_label": f"미등록/확인 필요: {reason}",
                    "count": int(count),
                }
            )
    return pd.DataFrame(rows, columns=["scope_exclusion_reason", "reason_label", "count"])


def video_summary(frame: pd.DataFrame) -> pd.DataFrame:
    frame = ensure_dashboard_columns(frame)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "video_id",
                "video_title",
                "video_url",
                "comment_count",
                "positive_rate",
                "negative_rate",
                "inquiry_rate",
                "representative_voc",
                # ★ 그 영상이 무엇에 대한 영상인가 (sky 2026-08-20)
                "positive_count",
                "negative_count",
                "inquiry_count",
                "main_product_category",
                "main_product_note",
                "main_product_breakdown",
                "main_product_hint",
                "main_brand",
                "main_brand_note",
                "main_brand_breakdown",
                # D-7 — 영상 맥락 (sky 2026-08-19)
                "video_tags",
                "video_description",
            ]
        )
    valid = frame[frame["validity"] == "유효"].copy()
    if valid.empty:
        valid = frame.copy()
    valid["is_positive"] = valid["sentiment_dir"].eq("긍정")
    valid["is_negative"] = valid["sentiment_dir"].eq("부정")
    valid["is_inquiry"] = valid["inquiry_flag"].fillna("").str.upper().eq("Y")
    # ★ D-7 — 영상 맥락. 칸이 없는 옛 번들에서도 깨지지 않게 먼저 채운다
    for column in ("video_tags", "video_description"):
        if column not in valid.columns:
            valid[column] = ""
        valid[column] = valid[column].fillna("").map(_safe_text)
    context = (
        valid.groupby("video_id", dropna=False)[["video_tags", "video_description"]]
        .agg(lambda values: next((v for v in values if v), ""))
    )
    grouped = (
        valid.groupby(["video_id", "video_title", "video_url"], dropna=False)
        .agg(
            comment_count=("source_id", "count"),
            positive_rate=("is_positive", "mean"),
            negative_rate=("is_negative", "mean"),
            inquiry_rate=("is_inquiry", "mean"),
            # ★ 비율만 있으면 「부정 100%」 가 커 보이는데 실은 1건 중 1건일 수
            #   있다. 건수를 같이 낸다 (sky 2026-08-20)
            positive_count=("is_positive", "sum"),
            negative_count=("is_negative", "sum"),
            inquiry_count=("is_inquiry", "sum"),
        )
        .reset_index()
    )
    representatives = []
    for _, row in grouped.iterrows():
        subset = valid[
            (valid["video_id"].fillna("") == _safe_text(row["video_id"]))
            & (valid["video_title"].fillna("") == _safe_text(row["video_title"]))
        ]
        subset = subset.sort_values(["review_queue", "topic_score"], ascending=[False, False])
        representatives.append(_safe_text(subset.iloc[0].get("atomic_voc_summary")) if not subset.empty else "")
    grouped["representative_voc"] = representatives
    # ★ 그 영상이 무엇에 대한 영상인지 (sky 2026-08-20).
    #   대표 VoC 는 동점이 많아 사실상 임의였다. 영상을 직관적으로 보는 데는
    #   「주로 다루는 제품군·브랜드」 가 낫다는 것이 sky 의 판단이다.
    #   기존 칸은 그대로 두고 칸을 더한다.
    brand_column = "brand_display" if "brand_display" in valid.columns else "brand"
    # 태그에서 떼어낼 브랜드 이름. 「LG」·「LG전자」 는 제품이 아니다
    brand_words = {
        _safe_text(value)
        for value in valid[brand_column].map(_safe_text).unique()
        if _safe_text(value)
    }
    brand_aliases = {word for word in brand_words}
    brand_aliases |= {f"{word}전자" for word in brand_words}
    brand_aliases |= {f"{word} 전자" for word in brand_words}

    def _product_hints(subset: pd.DataFrame) -> list[str]:
        """product_tags 에서 실제 제품명만 골라 많이 나온 순으로."""

        if "product_tags" not in subset.columns:
            return []
        counts: dict[str, int] = {}
        for raw in subset["product_tags"].map(_safe_text):
            for piece in raw.split(","):
                tag = piece.strip()
                if not tag or tag in brand_aliases:
                    continue
                # 「LG 스타일러」 → 「스타일러」 로 모아 센다
                for word in brand_aliases:
                    if tag.startswith(word) and len(tag) > len(word):
                        tag = tag[len(word):].strip()
                        break
                if not tag or tag in brand_aliases:
                    continue
                counts[tag] = counts.get(tag, 0) + 1
        return [name for name, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    main_product, main_product_note, main_product_breakdown = [], [], []
    main_brand, main_brand_note, main_brand_breakdown = [], [], []
    main_product_hint = []
    for _, row in grouped.iterrows():
        subset = valid[valid["video_id"].fillna("") == _safe_text(row["video_id"])]
        for column, names, notes, breakdowns in (
            ("product_category", main_product, main_product_note, main_product_breakdown),
            (brand_column, main_brand, main_brand_note, main_brand_breakdown),
        ):
            values = subset[column].map(_safe_text) if column in subset.columns else pd.Series(dtype="object")
            values = values[values != ""]
            counts = values.value_counts()
            if counts.empty:
                names.append("")
                notes.append("")
                breakdowns.append("[]")
                continue
            names.append(str(counts.index[0]))
            # ★ 「그 외 N종」 은 무엇인지 알 수 없어 쓸모가 없었다. 전부 적는다.
            #   분모(전체 댓글 수)는 카드 위 배지에 이미 있어 빼고 건수만 낸다 (sky 2026-08-20)
            pairs = [[str(name), int(number)] for name, number in counts.items()]
            breakdowns.append(json.dumps(pairs, ensure_ascii=False))
            notes.append(" · ".join(f"{name} {number:,}건" for name, number in pairs))
        # ★ 제품군이 「기타」 면 그것만으로는 무슨 영상인지 알 수 없다.
        #   product_tags 에 남은 실제 제품명을 보조로 붙인다
        hints = _product_hints(subset) if main_product[-1] in ("기타", "미분류", "") else []
        main_product_hint.append(", ".join(hints[:2]))
    grouped["main_product_category"] = main_product
    grouped["main_product_note"] = main_product_note
    grouped["main_product_breakdown"] = main_product_breakdown
    grouped["main_product_hint"] = main_product_hint
    grouped["main_brand"] = main_brand
    grouped["main_brand_note"] = main_brand_note
    grouped["main_brand_breakdown"] = main_brand_breakdown
    # D-7 — 영상 맥락을 붙인다. 없으면 빈 문자열이 되고 화면에서 알아서 감춘다
    for column in ("video_tags", "video_description"):
        grouped[column] = (
            grouped["video_id"].map(context[column]).fillna("")
            if column in context.columns
            else ""
        )
    return grouped.sort_values(["negative_rate", "inquiry_rate", "comment_count"], ascending=[False, False, False])


def inquiry_rows(frame: pd.DataFrame) -> pd.DataFrame:
    frame = ensure_dashboard_columns(frame)
    if frame.empty:
        return frame.copy()
    return frame[frame["inquiry_flag"].fillna("").str.upper().eq("Y")].copy()
