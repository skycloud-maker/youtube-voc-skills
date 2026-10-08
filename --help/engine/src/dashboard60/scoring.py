"""Deterministic L1 improvement-task scoring for the 66-column dashboard.

This module intentionally performs no LLM/API calls. It ranks improvement
candidate clusters from already-materialized VoC rows.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


EXCLUDED_TOPICS = {"", "N/A", "미분류"}
IMPROVEMENT_ENTITY_ROLES = {"product_brand", "unknown"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _representative_key(row: pd.Series) -> str:
    source_id = _text(row.get("source_id"))
    original_voc = " ".join(_text(row.get("original_voc")).split())
    return source_id or original_voc


def _eligible_rows(frame: pd.DataFrame, *, include_competitors: bool = False) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    required = frame.copy()
    for column in (
        "status",
        "topic",
        "product_category",
        "entity_role",
        "tee_emotion_score",
        "tee_success_score",
        "rootcause_problem",
    ):
        if column not in required.columns:
            required[column] = ""
    topic = required["topic"].map(_text)
    status = required["status"].map(_text)
    entity_role = required["entity_role"].map(_text).replace("", "unknown")
    mask = (status != "scope_excluded") & (~topic.isin(EXCLUDED_TOPICS))
    if not include_competitors:
        mask &= entity_role.isin(IMPROVEMENT_ENTITY_ROLES)
    return required[mask].copy()


def _negative_intensity(frame: pd.DataFrame) -> pd.Series:
    emotion = _number(frame.get("tee_emotion_score", pd.Series(index=frame.index, dtype=float)))
    success = _number(frame.get("tee_success_score", pd.Series(index=frame.index, dtype=float)))
    return pd.concat([emotion, success, pd.Series(0, index=frame.index)], axis=1).min(axis=1)


def score_improvement_tasks(frame: pd.DataFrame, *, include_competitors: bool = False) -> pd.DataFrame:
    """Score product_category x topic clusters by severity and negative volume.

    priority_score = abs(mean_neg) * neg_count

    Sorting is priority_score DESC, rc_coverage DESC, n DESC.
    """

    eligible = _eligible_rows(frame, include_competitors=include_competitors)
    columns = [
        "product_category",
        "topic",
        "n",
        "neg_count",
        "neg_ratio",
        "mean_neg",
        "rc_coverage",
        "priority_score",
        # D-6 두 축 (sky 2026-08-16) — 기존 priority_score 는 그대로 두고 옆에 붙인다
        "volume_score",
        "severity_score",
        "worst_score",
        "volume_rank",
        "severity_rank",
        "combined_rank",
        "watch_axis",
    ]
    if eligible.empty:
        return pd.DataFrame(columns=columns)

    eligible["_negative_intensity"] = _negative_intensity(eligible)
    eligible["_has_rootcause_problem"] = ~eligible["rootcause_problem"].map(_text).isin({"", "N/A"})
    eligible["product_category"] = eligible["product_category"].map(_text)
    eligible["topic"] = eligible["topic"].map(_text)

    rows: list[dict[str, Any]] = []
    for (product_category, topic), group in eligible.groupby(["product_category", "topic"], dropna=False):
        n = int(len(group))
        neg_count = int((group["_negative_intensity"] < 0).sum())
        mean_neg = float(group["_negative_intensity"].mean()) if n else 0.0
        deep = group.loc[group["_negative_intensity"] < 0, "_negative_intensity"]
        severity_score = round(abs(float(deep.mean())), 3) if len(deep) else 0.0
        worst_score = round(abs(float(group["_negative_intensity"].min())), 3) if n else 0.0
        rc_coverage = float(group["_has_rootcause_problem"].mean()) if n else 0.0
        rows.append(
            {
                "product_category": product_category,
                "topic": topic,
                "n": n,
                "neg_count": neg_count,
                "neg_ratio": float(neg_count / n) if n else 0.0,
                "mean_neg": mean_neg,
                "rc_coverage": rc_coverage,
                "priority_score": abs(mean_neg) * neg_count,
                # 축 A — 얼마나 많은 사람이 말했나
                "volume_score": neg_count,
                # 축 B — 화난 사람은 얼마나 화났나. 부정인 행만 평균낸다.
                #        mean_neg 를 쓰면 부정 아닌 행이 0 으로 섞여 희석된다
                "severity_score": severity_score,
                "worst_score": worst_score,
            }
        )

    result = pd.DataFrame(rows, columns=columns)
    # D-6 — 두 축 순위. 정렬 기준(priority_score)은 바꾸지 않는다
    for score_column, rank_column in (
        ("volume_score", "volume_rank"),
        ("severity_score", "severity_rank"),
    ):
        order = result.sort_values(
            [score_column, "n"], ascending=[False, False], kind="mergesort"
        ).index
        result.loc[order, rank_column] = range(1, len(order) + 1)
        result[rank_column] = result[rank_column].astype(int)
    # 종합 = 두 축 순위의 합. 작을수록 두 축 모두에서 위쪽이라는 뜻이다 (sky 2026-08-19)
    result["combined_rank"] = result["volume_rank"] + result["severity_rank"]
    # 어느 축으로든 상위 20 안에 들면 「봐야 할 것」 이다.
    # ★ 건수가 적다고 목록에서 내리지 않는다 (sky 2026-08-16)
    def _watch(row: pd.Series) -> str:
        axes = []
        if row["volume_rank"] <= 20:
            axes.append("건수")
        if row["severity_rank"] <= 20 and row["neg_count"] >= 1:
            axes.append("심각도")
        return " · ".join(axes)

    result["watch_axis"] = result.apply(_watch, axis=1) if len(result) else ""
    return result.sort_values(
        ["priority_score", "rc_coverage", "n"],
        ascending=[False, False, False],
        kind="mergesort",
    ).reset_index(drop=True)


def top_negative_vocs(
    frame: pd.DataFrame,
    product_category: str,
    topic: str,
    *,
    k: int = 3,
    include_competitors: bool = False,
) -> list[dict[str, Any]]:
    """Return de-duplicated representative negative VoCs for a scored cluster."""

    eligible = _eligible_rows(frame, include_competitors=include_competitors)
    if eligible.empty:
        return []
    eligible["product_category"] = eligible["product_category"].map(_text)
    eligible["topic"] = eligible["topic"].map(_text)
    subset = eligible[
        (eligible["product_category"] == _text(product_category))
        & (eligible["topic"] == _text(topic))
    ].copy()
    if subset.empty:
        return []

    subset["_negative_intensity"] = _negative_intensity(subset)
    subset = subset.sort_values(["_negative_intensity", "rootcause_problem"], ascending=[True, False])
    subset["_representative_key"] = subset.apply(_representative_key, axis=1)
    subset = subset[~subset["_representative_key"].duplicated(keep="first")]
    # D-4 — 개선과제 카드에서 문제·대상·원인을 함께 보여준다 (sky)
    for column in (
        "original_voc",
        "atomic_voc",
        "rootcause_problem",
        "rootcause_target",
        "rootcause_cause",
        "rootcause_summary",
    ):
        if column not in subset.columns:
            subset[column] = ""
    rows = []
    for _, row in subset.head(k).iterrows():
        rows.append(
            {
                "original_voc": _text(row.get("original_voc")),
                "atomic_voc": _text(row.get("atomic_voc")),
                "rootcause_problem": _text(row.get("rootcause_problem")),
                "rootcause_target": _text(row.get("rootcause_target")),
                "rootcause_cause": _text(row.get("rootcause_cause")),
                "rootcause_summary": _text(row.get("rootcause_summary")),
                "negative_intensity": float(row.get("_negative_intensity", 0) or 0),
            }
        )
    return rows
