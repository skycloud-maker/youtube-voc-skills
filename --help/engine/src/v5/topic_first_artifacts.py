"""Public artifact contract helpers for topic-first V5 outputs."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from .common import CONTRACT_VERSION

EVIDENCE_SIGNAL_ARTIFACT = "evidence_signal"
TOPIC_CANDIDATE_ARTIFACT = "topic_candidate"
ARTIFACT_SCHEMA_VERSION = "topic-first-artifacts.v1"

SCORE_COMPONENT_COLUMNS = [
    "frequency_count",
    "coverage_pct",
    "negative_or_mixed_weight",
    "importance_signal",
    "rank_score",
    "ranking_penalty",
    "cohesion_ratio",
    "signal_density",
    "insufficient_evidence",
    "top_quality_pass",
]

TOPIC_CANDIDATE_REQUIRED_COLUMNS = [
    "artifact_schema_version",
    "source_contract_version",
    "run_id",
    "topic_rank",
    "topic_id",
    "topic_label",
    "display_topic_label",
    "topic_key",
    "product_semantic_id",
    "journey_stage",
    "judgment_axis",
    "polarity_group",
    "signature",
    "frequency_count",
    "coverage_pct",
    "negative_or_mixed_weight",
    "importance_signal",
    "rank_score",
    "ranking_penalty",
    "cohesion_ratio",
    "signal_density",
    "insufficient_evidence",
    "top_quality_pass",
    "top_exclusion_reason",
    "representative_count",
    "support_count",
    "example_count",
    "representative_comment_ids",
    "supporting_comment_ids",
    "example_texts",
    "example_signal_texts",
    "score_components",
    "score_components_json",
]

EVIDENCE_SIGNAL_REQUIRED_COLUMNS = [
    "artifact_schema_version",
    "source_contract_version",
    "run_id",
    "signal_id",
    "comment_id",
    "video_id",
    "topic_id",
    "signal_text",
    "signal_type",
    "split_rule",
    "journey_stage",
    "judgment_axis",
    "polarity",
    "weight",
    "product_semantic_id",
]


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _json_scalar(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    if hasattr(value, "tolist"):
        try:
            converted = value.tolist()
            if isinstance(converted, list):
                return [str(item) for item in converted if str(item)]
        except Exception:
            pass
    scalar = _json_scalar(value)
    if scalar is None:
        return []
    text = str(scalar).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item)]
    except Exception:
        pass
    return [text]


def _ordered_unique(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _score_components_json(row: pd.Series) -> str:
    payload = {
        column: _json_scalar(row.get(column))
        for column in SCORE_COMPONENT_COLUMNS
        if column in row.index
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _text_or_default(value: Any, default: str) -> str:
    scalar = _json_scalar(value)
    if scalar is None:
        return default
    text = str(scalar).strip()
    return text if text else default


def _topic_product_label(product_semantic_id: Any) -> str:
    raw = _text_or_default(product_semantic_id, "unknown")
    if "cat:" not in raw:
        return raw
    category = raw.split("cat:", 1)[1].split("|", 1)[0].strip()
    return category or "unknown"


def _topic_label(row: pd.Series) -> str:
    signature = _text_or_default(row.get("signature"), "")
    if not signature:
        signature = _text_or_default(row.get("v5_simple_signature"), "general")
    parts = [
        _topic_product_label(row.get("product_semantic_id")),
        _text_or_default(row.get("journey_stage"), "unknown_stage"),
        _text_or_default(row.get("judgment_axis"), "unknown_axis"),
        _text_or_default(row.get("polarity_group"), "neutral"),
        signature,
    ]
    return " / ".join(part for part in parts if part)


def _comment_text_lookup(comment_context: pd.DataFrame) -> dict[str, str]:
    if comment_context.empty or not {"comment_id", "raw_text"}.issubset(comment_context.columns):
        return {}
    return dict(
        zip(
            comment_context["comment_id"].astype(str),
            comment_context["raw_text"].fillna("").astype(str),
        )
    )


def _topic_support_maps(signal_units: pd.DataFrame) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    if signal_units.empty or "topic_id" not in signal_units.columns:
        return {}, {}

    support_ids: dict[str, list[str]] = {}
    signal_examples: dict[str, list[str]] = {}
    for topic_id, group in signal_units.groupby(signal_units["topic_id"].astype(str), sort=False):
        ordered_ids: list[str] = []
        seen_ids: set[str] = set()
        for raw_id in group.get("comment_id", pd.Series("", index=group.index)).astype(str):
            if raw_id and raw_id not in seen_ids:
                seen_ids.add(raw_id)
                ordered_ids.append(raw_id)
        support_ids[str(topic_id)] = ordered_ids

        if "signal_text" in group.columns:
            signal_examples[str(topic_id)] = _ordered_unique(
                [text for text in group["signal_text"].fillna("").astype(str).tolist() if text]
            )[:3]
        else:
            signal_examples[str(topic_id)] = []
    return support_ids, signal_examples


def _representatives_in_support(representative_ids: list[str], support_ids: list[str]) -> list[str]:
    support_set = set(support_ids)
    return [comment_id for comment_id in _ordered_unique(representative_ids) if comment_id in support_set]


def _example_texts_for_topic(
    *,
    representative_ids: list[str],
    support_ids: list[str],
    text_lookup: dict[str, str],
    fallback_signal_texts: list[str],
    limit: int = 3,
) -> list[str]:
    ordered_comment_ids = _ordered_unique(representative_ids + support_ids)
    examples: list[str] = []
    seen_texts: set[str] = set()
    for comment_id in ordered_comment_ids:
        text = text_lookup.get(comment_id, "").strip()
        if text and text not in seen_texts:
            seen_texts.add(text)
            examples.append(text)
        if len(examples) >= limit:
            return examples

    for text in fallback_signal_texts:
        clean_text = str(text).strip()
        if clean_text and clean_text not in seen_texts:
            seen_texts.add(clean_text)
            examples.append(clean_text)
        if len(examples) >= limit:
            break
    return examples


def _ensure_columns(frame: pd.DataFrame, columns: list[str], defaults: dict[str, Any] | None = None) -> pd.DataFrame:
    output = frame.copy()
    defaults = defaults or {}
    for column in columns:
        if column not in output.columns:
            value = defaults.get(column, pd.NA)
            if isinstance(value, list):
                output[column] = [list(value) for _ in range(len(output))]
            else:
                output[column] = value
    ordered = [column for column in columns if column in output.columns]
    remaining = [column for column in output.columns if column not in ordered]
    return output[ordered + remaining].copy()


def build_evidence_signal_artifact(*, run_id: str, v5_outputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    signal_units = v5_outputs.get("v5_signal_units", pd.DataFrame()).copy()
    if signal_units.empty:
        return _empty_frame(EVIDENCE_SIGNAL_REQUIRED_COLUMNS)

    signal_units["artifact_schema_version"] = ARTIFACT_SCHEMA_VERSION
    signal_units["source_contract_version"] = CONTRACT_VERSION
    signal_units["run_id"] = str(run_id or "")
    return _ensure_columns(signal_units, EVIDENCE_SIGNAL_REQUIRED_COLUMNS)


def build_topic_candidate_artifact(*, run_id: str, v5_outputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    ranked = v5_outputs.get("v5_topic_ranked", pd.DataFrame()).copy()
    topics = v5_outputs.get("v5_topics", pd.DataFrame()).copy()
    representatives = v5_outputs.get("v5_topic_representatives", pd.DataFrame()).copy()
    signal_units = v5_outputs.get("v5_signal_units", pd.DataFrame()).copy()
    comment_context = v5_outputs.get("v5_comment_context", pd.DataFrame()).copy()

    if ranked.empty or topics.empty:
        return _empty_frame(TOPIC_CANDIDATE_REQUIRED_COLUMNS)

    merged = ranked.merge(topics, on="topic_id", how="left")
    if not representatives.empty:
        representative_cols = [
            column
            for column in ["topic_id", "representative_comment_ids", "alignment_score", "selection_reason"]
            if column in representatives.columns
        ]
        if "topic_id" in representative_cols:
            merged = merged.merge(representatives[representative_cols], on="topic_id", how="left")

    support_ids, signal_examples = _topic_support_maps(signal_units)
    text_lookup = _comment_text_lookup(comment_context)
    merged["artifact_schema_version"] = ARTIFACT_SCHEMA_VERSION
    merged["source_contract_version"] = CONTRACT_VERSION
    merged["run_id"] = str(run_id or "")
    merged["topic_rank"] = range(1, len(merged) + 1)
    merged["topic_label"] = merged.apply(_topic_label, axis=1)
    merged["display_topic_label"] = merged["topic_label"]
    merged["supporting_comment_ids"] = merged["topic_id"].astype(str).map(lambda topic_id: support_ids.get(topic_id, []))
    if "representative_comment_ids" not in merged.columns:
        merged["representative_comment_ids"] = [[] for _ in range(len(merged))]
    else:
        merged["representative_comment_ids"] = merged["representative_comment_ids"].map(_as_list)
    merged["representative_comment_ids"] = merged.apply(
        lambda row: _representatives_in_support(
            _as_list(row.get("representative_comment_ids")),
            _as_list(row.get("supporting_comment_ids")),
        ),
        axis=1,
    )
    merged["example_signal_texts"] = merged["topic_id"].astype(str).map(lambda topic_id: signal_examples.get(topic_id, []))
    merged["example_texts"] = merged.apply(
        lambda row: _example_texts_for_topic(
            representative_ids=_as_list(row.get("representative_comment_ids")),
            support_ids=_as_list(row.get("supporting_comment_ids")),
            text_lookup=text_lookup,
            fallback_signal_texts=_as_list(row.get("example_signal_texts")),
        ),
        axis=1,
    )
    merged["support_count"] = merged["supporting_comment_ids"].map(len)
    merged["representative_count"] = merged["representative_comment_ids"].map(len)
    merged["example_count"] = merged["example_texts"].map(len)
    merged["score_components_json"] = merged.apply(_score_components_json, axis=1)
    merged["score_components"] = merged["score_components_json"]

    defaults = {
        "frequency_count": 0,
        "coverage_pct": 0.0,
        "negative_or_mixed_weight": 0.0,
        "importance_signal": 0.0,
        "rank_score": 0.0,
        "ranking_penalty": 1.0,
        "cohesion_ratio": 0.0,
        "signal_density": 0.0,
        "insufficient_evidence": False,
        "top_quality_pass": False,
        "top_exclusion_reason": "",
        "representative_comment_ids": [],
        "supporting_comment_ids": [],
        "example_texts": [],
        "example_signal_texts": [],
    }
    return _ensure_columns(merged, TOPIC_CANDIDATE_REQUIRED_COLUMNS, defaults=defaults)


def build_topic_first_artifacts(*, run_id: str, v5_outputs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Build public topic-first artifacts from raw V5 pipeline outputs."""
    return {
        EVIDENCE_SIGNAL_ARTIFACT: build_evidence_signal_artifact(run_id=run_id, v5_outputs=v5_outputs),
        TOPIC_CANDIDATE_ARTIFACT: build_topic_candidate_artifact(run_id=run_id, v5_outputs=v5_outputs),
    }
