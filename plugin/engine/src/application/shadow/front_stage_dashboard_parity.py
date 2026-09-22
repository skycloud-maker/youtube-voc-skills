"""Canonical Front Stage dashboard dataset and parity helpers.

This module is intentionally small and deterministic.  Stage 7's purpose is
not to improve analysis quality, but to make the validation pipeline and the
Dashboard view read the same schema and aggregation logic.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


CANONICAL_FRONT_STAGE_SCHEMA_VERSION = "front-stage-dashboard-v1"
CANONICAL_FRONT_STAGE_PARSER_VERSION = "openai-front-stage-parser-v1"
CANONICAL_FRONT_STAGE_DATA_SOURCE = "canonical_front_stage"

OUTPUT_JSONL = "raw_voc_openai_outputs.jsonl"
RAW_RESPONSE_JSONL = "raw_voc_openai_raw_responses.jsonl"
DASHBOARD_DATASET_CSV = "raw_voc_dashboard_dataset.csv"
TOPIC_DISTRIBUTION_CSV = "raw_voc_topic_distribution.csv"
REPORT_MD = "raw_voc_dashboard_report.md"
METADATA_JSON = "dashboard_parity_metadata.json"

DASHBOARD_FIELDS: tuple[str, ...] = (
    "source_id",
    "raw_row_index",
    "parent_voc_id",
    "atomic_id",
    "atomic_index",
    "comment_relation",
    "original_voc",
    "analysis_text",
    "topic",
    "atomic_voc",
    "product",
    "product_tags",
    "product_additional_info",
    "competitor_brand_tags",
    "brand",
    "market",
    "language",
    "cej",
    "status",
    "review_required",
    "topic_evidence",
    "atomic_evidence",
    "product_evidence",
    "competitor_evidence",
    "cej_evidence",
    "source_context_summary",
    "trace_summary",
    "confidence_topic",
    "confidence_atomic",
    "confidence_product",
    "confidence_competitor",
    "confidence_cej",
    "video_id",
    "video_title",
    "video_url",
)

TOPIC_DISTRIBUTION_FIELDS: tuple[str, ...] = (
    "rank",
    "topic",
    "count",
    "share",
    "cumulative_share",
)

PARITY_COMPARE_FIELDS: tuple[str, ...] = (
    "source_id",
    "atomic_id",
    "atomic_index",
    "topic",
    "atomic_voc",
    "product",
    "competitor_brand_tags",
    "brand",
    "market",
    "language",
    "cej",
    "status",
    "review_required",
)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:  # pandas/numpy NaN
            return ""
    except Exception:
        pass
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def json_dumps(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return safe_text(value)


def list_text(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        return "; ".join(safe_text(item) for item in value if safe_text(item))
    if isinstance(value, tuple):
        return "; ".join(safe_text(item) for item in value if safe_text(item))
    return safe_text(value)


def dict_value(value: Any, key: str) -> str:
    if isinstance(value, Mapping):
        return safe_text(value.get(key, ""))
    return ""


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    input_path = Path(path)
    if not input_path.exists():
        return rows
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                decoded = json.loads(line)
                if isinstance(decoded, dict):
                    rows.append(decoded)
    return rows


def write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=False))
            handle.write("\n")


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    input_path = Path(path)
    if not input_path.exists():
        return []
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: str | Path, fields: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    field_list = list(fields)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_list, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: safe_text(row.get(field, "")) for field in field_list})


def flatten_front_stage_row(row: Mapping[str, Any]) -> dict[str, str]:
    context = row.get("source_context")
    evidence = row.get("source_evidence")
    trace = row.get("trace")
    confidence = row.get("confidence")

    if not isinstance(context, Mapping):
        context = {}
    if not isinstance(evidence, Mapping):
        evidence = {}
    if not isinstance(trace, Mapping):
        trace = {}
    if not isinstance(confidence, Mapping):
        confidence = {}

    status = safe_text(row.get("status")) or "review_required"
    topic = safe_text(row.get("topic")) or "N/A"
    review_required = _review_required(
        status=status,
        topic=topic,
        evidence=evidence,
        confidence=confidence,
    )

    return {
        "source_id": safe_text(row.get("source_id")),
        "raw_row_index": safe_text(row.get("raw_row_index") or context.get("raw_row_index")),
        "parent_voc_id": safe_text(row.get("parent_voc_id")),
        "atomic_id": safe_text(row.get("atomic_id")),
        "atomic_index": safe_text(row.get("atomic_index")),
        "comment_relation": safe_text(row.get("comment_relation") or context.get("comment_relation")),
        "original_voc": safe_text(row.get("original_voc")),
        "analysis_text": safe_text(row.get("analysis_text")),
        "topic": topic,
        "atomic_voc": safe_text(row.get("atomic_voc")),
        "product": safe_text(row.get("product")) or "N/A",
        "product_tags": list_text(row.get("product_tags")),
        "product_additional_info": list_text(row.get("product_additional_info")),
        "competitor_brand_tags": list_text(row.get("competitor_brand_tags")),
        "brand": safe_text(row.get("brand")) or "unknown",
        "market": safe_text(row.get("market")) or "unknown",
        "language": safe_text(row.get("language")) or "unknown",
        "cej": safe_text(row.get("cej")) or "N/A",
        "status": status,
        "review_required": review_required,
        "topic_evidence": dict_value(evidence, "topic"),
        "atomic_evidence": dict_value(evidence, "atomic"),
        "product_evidence": dict_value(evidence, "product"),
        "competitor_evidence": dict_value(evidence, "competitor"),
        "cej_evidence": dict_value(evidence, "cej"),
        "source_context_summary": json_dumps(context),
        "trace_summary": json_dumps(trace),
        "confidence_topic": safe_text(confidence.get("topic", "")),
        "confidence_atomic": safe_text(confidence.get("atomic", "")),
        "confidence_product": safe_text(confidence.get("product", "")),
        "confidence_competitor": safe_text(confidence.get("competitor", "")),
        "confidence_cej": safe_text(confidence.get("cej", "")),
        "video_id": safe_text(row.get("video_id") or context.get("video_id")),
        "video_title": safe_text(row.get("video_title") or context.get("video_title")),
        "video_url": safe_text(row.get("video_url") or context.get("video_url")),
    }


def _review_required(*, status: str, topic: str, evidence: Mapping[str, Any], confidence: Mapping[str, Any]) -> str:
    if status in {"review_required", "context_missing"}:
        return "Y"
    if topic in {"", "N/A"} and status != "scope_excluded":
        return "Y"
    if safe_text(evidence.get("topic")) in {"", "N/A"} and status == "normal":
        return "Y"
    low_confidence_count = 0
    for key in ("topic", "atomic", "product", "cej"):
        try:
            numeric = float(confidence.get(key, 0.0))
        except (TypeError, ValueError):
            numeric = 0.0
        if numeric < 0.55:
            low_confidence_count += 1
    return "Y" if low_confidence_count >= 3 and status == "normal" else "N"


def flatten_front_stage_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [flatten_front_stage_row(row) for row in rows]


def build_topic_distribution(flat_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    row_list = list(flat_rows)
    total = len(row_list)
    counter = Counter(safe_text(row.get("topic")) or "N/A" for row in row_list)
    cumulative = 0
    output: list[dict[str, str]] = []
    for rank, (topic, count) in enumerate(counter.most_common(), start=1):
        cumulative += count
        output.append(
            {
                "rank": str(rank),
                "topic": topic,
                "count": str(count),
                "share": f"{count / (total or 1):.1%}",
                "cumulative_share": f"{cumulative / (total or 1):.1%}",
            }
        )
    return output


def prompt_hash(prompt_path: str | Path) -> str:
    path = Path(prompt_path)
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def file_hash(path: str | Path) -> str:
    input_path = Path(path)
    if not input_path.exists():
        return ""
    return hashlib.sha256(input_path.read_bytes()).hexdigest()[:16]


def build_parity_metadata(
    *,
    prompt_path: str | Path | None = None,
    model: str = "",
    run_source: str = "unknown",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "data_source": CANONICAL_FRONT_STAGE_DATA_SOURCE,
        "schema_version": CANONICAL_FRONT_STAGE_SCHEMA_VERSION,
        "parser_version": CANONICAL_FRONT_STAGE_PARSER_VERSION,
        "model": safe_text(model),
        "run_source": safe_text(run_source),
        "prompt_path": safe_text(prompt_path),
        "prompt_hash": prompt_hash(prompt_path) if prompt_path else "",
    }
    if extra:
        metadata.update(dict(extra))
    return metadata


def write_dashboard_artifacts(
    *,
    out_dir: str | Path,
    openai_outputs: Iterable[Mapping[str, Any]],
    raw_responses: Iterable[Mapping[str, Any]] | None = None,
    prompt_path: str | Path | None = None,
    model: str = "",
    run_source: str = "unknown",
    report_text: str = "",
) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    openai_rows = [dict(row) for row in openai_outputs]
    dashboard_rows = flatten_front_stage_rows(openai_rows)
    topic_rows = build_topic_distribution(dashboard_rows)
    metadata = build_parity_metadata(
        prompt_path=prompt_path,
        model=model,
        run_source=run_source,
        extra={
            "openai_output_rows": len(openai_rows),
            "dashboard_rows": len(dashboard_rows),
            "unique_topics": len(topic_rows),
            "review_required_rows": sum(1 for row in dashboard_rows if row.get("review_required") == "Y"),
            "na_topic_rows": sum(1 for row in dashboard_rows if row.get("topic") in {"", "N/A"}),
        },
    )
    paths = {
        "openai_outputs": out / OUTPUT_JSONL,
        "raw_responses": out / RAW_RESPONSE_JSONL,
        "dashboard_dataset": out / DASHBOARD_DATASET_CSV,
        "topic_distribution": out / TOPIC_DISTRIBUTION_CSV,
        "report": out / REPORT_MD,
        "metadata": out / METADATA_JSON,
    }
    write_jsonl(paths["openai_outputs"], openai_rows)
    write_jsonl(paths["raw_responses"], raw_responses or [])
    write_csv(paths["dashboard_dataset"], DASHBOARD_FIELDS, dashboard_rows)
    write_csv(paths["topic_distribution"], TOPIC_DISTRIBUTION_FIELDS, topic_rows)
    paths["metadata"].write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report_text:
        paths["report"].write_text(report_text, encoding="utf-8")
    elif not paths["report"].exists():
        paths["report"].write_text("# Canonical Front Stage Dashboard Report\n", encoding="utf-8")
    return paths


def rebuild_dashboard_artifacts_from_outputs(
    *,
    source_dir: str | Path,
    out_dir: str | Path,
    prompt_path: str | Path | None = None,
    model: str = "",
    run_source: str = "dashboard_rebuild",
) -> dict[str, Path]:
    source = Path(source_dir)
    openai_rows = read_jsonl(source / OUTPUT_JSONL)
    raw_response_rows = read_jsonl(source / RAW_RESPONSE_JSONL)
    report_text = ""
    report_path = source / REPORT_MD
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
    return write_dashboard_artifacts(
        out_dir=out_dir,
        openai_outputs=openai_rows,
        raw_responses=raw_response_rows,
        prompt_path=prompt_path,
        model=model,
        run_source=run_source,
        report_text=report_text,
    )


def compare_csv_rows(
    reference_rows: list[Mapping[str, Any]],
    candidate_rows: list[Mapping[str, Any]],
    *,
    key_fields: tuple[str, ...] = ("source_id", "atomic_id", "atomic_index"),
    compare_fields: tuple[str, ...] = PARITY_COMPARE_FIELDS,
) -> list[dict[str, str]]:
    def key(row: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(safe_text(row.get(field)) for field in key_fields)

    ref_map = {key(row): row for row in reference_rows}
    cand_map = {key(row): row for row in candidate_rows}
    all_keys = sorted(set(ref_map) | set(cand_map))
    mismatches: list[dict[str, str]] = []
    for row_key in all_keys:
        ref = ref_map.get(row_key)
        cand = cand_map.get(row_key)
        if ref is None:
            mismatches.append({"key": "|".join(row_key), "field": "__row__", "reference": "", "candidate": "extra_row", "status": "extra"})
            continue
        if cand is None:
            mismatches.append({"key": "|".join(row_key), "field": "__row__", "reference": "missing_row", "candidate": "", "status": "missing"})
            continue
        for field in compare_fields:
            ref_value = safe_text(ref.get(field))
            cand_value = safe_text(cand.get(field))
            if ref_value != cand_value:
                mismatches.append(
                    {
                        "key": "|".join(row_key),
                        "field": field,
                        "reference": ref_value,
                        "candidate": cand_value,
                        "status": "mismatch",
                    }
                )
    return mismatches


def compare_topic_distribution(
    reference_rows: list[Mapping[str, Any]],
    candidate_rows: list[Mapping[str, Any]],
) -> list[dict[str, str]]:
    ref_map = {safe_text(row.get("topic")): row for row in reference_rows}
    cand_map = {safe_text(row.get("topic")): row for row in candidate_rows}
    mismatches: list[dict[str, str]] = []
    for topic in sorted(set(ref_map) | set(cand_map)):
        ref = ref_map.get(topic, {})
        cand = cand_map.get(topic, {})
        for field in ("count", "share", "cumulative_share"):
            ref_value = safe_text(ref.get(field))
            cand_value = safe_text(cand.get(field))
            if ref_value != cand_value:
                mismatches.append(
                    {
                        "key": topic,
                        "field": field,
                        "reference": ref_value,
                        "candidate": cand_value,
                        "status": "mismatch",
                    }
                )
    return mismatches
