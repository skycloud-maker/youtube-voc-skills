"""Build a 60-column VoC dashboard dataset with the voc_rebuild engine.

This is the greenfield dashboard generator for the v2.4 60-column contract.
It intentionally bypasses the legacy front-stage parser and calls
``src.voc_rebuild`` directly.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.dashboard60.export_bundle import BUNDLE_FILENAME, write_bundle_metadata_marker, write_export_bundle  # noqa: E402
from src.voc_rebuild import TARGET_COLUMNS, analyze_rows, assert_column_contract  # noqa: E402
from src.voc_rebuild.engine import DEFAULT_LLM_CONCURRENCY, write_csv, write_jsonl  # noqa: E402


SCHEMA_VERSION = "voc-66col-v2.9"
PARSER_VERSION = "voc-rebuild-engine"
DEFAULT_OUT_ROOT = ROOT / "outputs" / "voc_dashboard_60"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""

    # YouTube video metadata such as ``tags`` is naturally multi-valued and
    # may be restored from parquet as a list, numpy.ndarray, or Series.  Check
    # those shapes before ``pd.isna``: applying it to an array returns an
    # array of booleans that cannot be evaluated as a single condition.
    if isinstance(value, pd.Series):
        values = value.tolist()
    elif isinstance(value, (list, tuple)):
        values = list(value)
    elif getattr(value, "ndim", 0) > 0 and callable(getattr(value, "tolist", None)):
        converted = value.tolist()
        values = converted if isinstance(converted, list) else [converted]
    else:
        if pd.isna(value):
            return ""
        return str(value).strip()

    normalized = [_safe_text(item) for item in values]
    normalized = [item for item in normalized if item]
    if not normalized:
        return ""
    return ", ".join(normalized)


def _comment_text(record: dict[str, Any]) -> str:
    return (
        _safe_text(record.get("cleaned_text"))
        or _safe_text(record.get("text_original"))
        or _safe_text(record.get("text_display"))
        or _safe_text(record.get("original_voc"))
    )


def _record_source_id(record: dict[str, Any], index: int) -> str:
    return _safe_text(record.get("comment_id")) or _safe_text(record.get("source_id")) or str(index)


def _context_part(key: str, value: Any, *, max_chars: int = 240) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) > max_chars:
        text = f"{text[:max_chars]}..."
    return f"{key}={text}"


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def _clean_source_context_summary(value: Any) -> str:
    """Remove collection/search hints from analysis context summaries."""

    parts: list[str] = []
    for part in _safe_text(value).split("|"):
        stripped = part.strip()
        lowered = stripped.lower()
        if lowered.startswith("keyword=") or lowered.startswith("product="):
            continue
        if stripped:
            parts.append(stripped)
    return " | ".join(parts)


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, keep_default_na=False)
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, keep_default_na=False)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported input file type: {path}")


def _video_lookup(videos_path: Path | None) -> dict[str, dict[str, Any]]:
    if not videos_path:
        return {}
    videos = pd.read_parquet(videos_path)
    result: dict[str, dict[str, Any]] = {}
    for record in videos.to_dict(orient="records"):
        video_id = _safe_text(record.get("video_id"))
        if video_id:
            result[video_id] = record
    return result


def _rows_from_comments_parquet(comments_path: Path, videos_path: Path | None = None) -> list[dict[str, Any]]:
    comments = pd.read_parquet(comments_path)
    videos = _video_lookup(videos_path)
    records = comments.to_dict(orient="records")
    source_text_by_id = {
        _record_source_id(record, index): _comment_text(record)
        for index, record in enumerate(records, start=1)
    }
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        video_id = _safe_text(record.get("video_id"))
        video = videos.get(video_id, {})
        text = _comment_text(record)
        source_id = _record_source_id(record, index)
        is_reply = bool(record.get("is_reply"))
        parent_voc_id = _safe_text(record.get("parent_comment_id")) or _safe_text(record.get("thread_id"))
        parent_voc = ""
        if is_reply:
            parent_voc = source_text_by_id.get(parent_voc_id, "") if parent_voc_id and parent_voc_id != source_id else ""
            if not parent_voc:
                parent_voc = "<unavailable>"
        context_parts = [
            _context_part("video_title", video.get("title")),
            _context_part("parent_voc", parent_voc) if is_reply else "",
        ]
        rows.append(
            {
                "source_id": source_id,
                "raw_row_index": record.get("raw_row_index", index),
                "parent_voc_id": parent_voc_id,
                "comment_relation": "reply" if is_reply else "parent",
                "original_voc": text,
                "parent_voc": parent_voc,
                "market": _safe_text(video.get("region")) or _safe_text(record.get("market")) or _safe_text(record.get("language_detected")),
                "language": _safe_text(record.get("language_detected")),
                "video_id": video_id,
                "video_title": _safe_text(video.get("title")),
                "video_url": _safe_text(video.get("video_url")),
                "video_tags": _safe_text(video.get("tags")),
                "video_description": _safe_text(video.get("description")),
                "like_count": _safe_int(record.get("like_count")),
                "reply_count": _safe_int(record.get("reply_count")),
                "total_reply_count": _safe_int(record.get("total_reply_count")),
                "source_context_summary": " | ".join(
                    part
                    for part in context_parts
                    if part
                ),
            }
        )
    return rows


def _quality_sample_by_video(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    """Prefer high-engagement comments while keeping reply context intact."""

    for index, row in enumerate(rows):
        row.setdefault("_source_order", index)

    ranked = sorted(
        rows,
        key=lambda row: (
            -_safe_int(row.get("like_count")),
            -_safe_int(row.get("total_reply_count")),
            _safe_int(row.get("_source_order")),
        ),
    )

    if limit is None:
        return ranked

    by_source_id = {
        _safe_text(row.get("source_id")): row
        for row in rows
        if _safe_text(row.get("source_id"))
    }
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def is_reply(row: dict[str, Any]) -> bool:
        relation = _safe_text(row.get("comment_relation")).lower()
        if relation == "reply":
            return True
        if relation == "parent":
            return False
        return bool(row.get("is_reply"))

    def add_row(row: dict[str, Any]) -> bool:
        source_id = _safe_text(row.get("source_id"))
        if source_id and source_id in selected_ids:
            return False
        if len(selected) >= limit:
            return False
        selected.append(row)
        if source_id:
            selected_ids.add(source_id)
        return True

    for row in ranked:
        source_id = _safe_text(row.get("source_id"))
        if source_id and source_id in selected_ids:
            continue

        if is_reply(row):
            parent_id = _safe_text(row.get("parent_voc_id"))
            parent_row = by_source_id.get(parent_id)
            if not parent_id or parent_id == source_id or parent_row is None or is_reply(parent_row):
                continue
            if parent_id not in selected_ids and len(selected) + 2 > limit:
                continue
            if parent_id not in selected_ids:
                add_row(parent_row)
            add_row(row)
            continue

        add_row(row)

    return selected


def _build_reanalysis_parent_lookup(records: list[dict[str, Any]]) -> dict[str, str]:
    """Index original parent text by source id for exact reanalysis."""

    return {
        _safe_text(record.get("source_id")) or _safe_text(record.get("comment_id")): (
            _safe_text(record.get("original_voc"))
            or _safe_text(record.get("raw_voc"))
            or _safe_text(record.get("comment"))
            or _safe_text(record.get("text"))
            or _safe_text(record.get("cleaned_text"))
            or _safe_text(record.get("text_original"))
        )
        for record in records
        if _safe_text(record.get("source_id")) or _safe_text(record.get("comment_id"))
    }


def _rows_from_raw_file(path: Path) -> list[dict[str, Any]]:
    frame = _read_table(path)
    records = frame.to_dict(orient="records")
    source_text_by_id = _build_reanalysis_parent_lookup(records)
    rows: list[dict[str, Any]] = []
    reply_count = 0
    injected_count = 0
    unavailable_count = 0
    missing_parent_id_count = 0
    for index, record in enumerate(records, start=1):
        original = (
            _safe_text(record.get("original_voc"))
            or _safe_text(record.get("raw_voc"))
            or _safe_text(record.get("comment"))
            or _safe_text(record.get("text"))
            or _safe_text(record.get("cleaned_text"))
            or _safe_text(record.get("text_original"))
        )
        source_id = _safe_text(record.get("source_id")) or _safe_text(record.get("comment_id")) or str(index)
        parent_voc_id = _safe_text(record.get("parent_voc_id")) or _safe_text(record.get("parent_comment_id"))
        relation = _safe_text(record.get("comment_relation")) or ("reply" if record.get("is_reply") else "parent")
        is_reply = relation.lower() == "reply"
        parent_voc = ""
        review_required = _safe_text(record.get("review_required"))
        trace_summary = _safe_text(record.get("trace_summary"))
        if is_reply:
            reply_count += 1
            parent_voc = source_text_by_id.get(parent_voc_id, "") if parent_voc_id else ""
            if parent_voc:
                injected_count += 1
            else:
                parent_voc = "<unavailable>"
                unavailable_count += 1
                if not parent_voc_id:
                    missing_parent_id_count += 1
                    review_required = "Y"
                    marker = "reanalysis_parent_voc_id_missing"
                    trace_summary = f"{trace_summary}; {marker}" if trace_summary else marker
        context_parts = [
            _context_part("video_title", record.get("video_title")),
            _context_part("parent_voc", parent_voc) if is_reply else "",
        ]
        rows.append(
            {
                **record,
                "source_id": source_id,
                "raw_row_index": record.get("raw_row_index", index),
                "parent_voc_id": parent_voc_id,
                "comment_relation": relation,
                "original_voc": original,
                "video_tags": _safe_text(record.get("video_tags")),
                "video_description": _safe_text(record.get("video_description")),
                "parent_voc": parent_voc,
                "source_context_summary": " | ".join(part for part in context_parts if part),
                "review_required": review_required,
                "trace_summary": trace_summary,
            }
        )
    coverage = {
        "path": str(path),
        "reply_rows": reply_count,
        "parent_injected": injected_count,
        "unavailable": unavailable_count,
        "missing_parent_voc_id": missing_parent_id_count,
        "coverage_percent": round((injected_count / reply_count * 100.0) if reply_count else 100.0, 2),
    }
    print(json.dumps({"reanalysis_parent_coverage": coverage}, ensure_ascii=False), flush=True)
    if unavailable_count:
        print(json.dumps({"warning": "reanalysis parent coverage below 100%", **coverage}, ensure_ascii=False), flush=True)
    return rows


def _topic_distribution(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["rank", "topic", "count", "share", "cumulative_share"])
    frame = pd.DataFrame(rows)
    counts = frame["topic"].fillna("N/A").replace("", "N/A").value_counts(dropna=False)
    total = int(counts.sum()) or 1
    distribution = pd.DataFrame({"topic": counts.index, "count": counts.values})
    distribution.insert(0, "rank", range(1, len(distribution) + 1))
    distribution["share"] = distribution["count"] / total
    distribution["cumulative_share"] = distribution["share"].cumsum()
    return distribution


def _write_metadata(path: Path, *, args: argparse.Namespace, input_rows: int, output_rows: int) -> None:
    run_id = str(args.run_id or "")
    suffix = ""
    match = re.match(r"^(?P<suffix>.+?)_\d{8}_\d{6}$", run_id)
    if match:
        suffix = match.group("suffix")
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "data_source": "voc_rebuild_60col",
        "run_id": run_id,
        "run_suffix": suffix,
        "model": args.model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_rows": input_rows,
        "output_rows": output_rows,
        "batch_size": args.batch_size,
        "sample_across_videos": True,
        "input": {
            "processed_run_dir": str(args.processed_run_dir or ""),
            "comments_parquet": str(args.comments_parquet or ""),
            "videos_parquet": str(args.videos_parquet or ""),
            "raw_file": str(args.raw_file or ""),
        },
        "target_columns": TARGET_COLUMNS,
    }
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--processed-run-dir", type=Path)
    source.add_argument("--comments-parquet", type=Path)
    source.add_argument("--raw-file", type=Path, help="Raw VoC CSV/XLSX/Parquet input.")
    parser.add_argument("--videos-parquet", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--llm-concurrency", type=int, default=DEFAULT_LLM_CONCURRENCY)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument(
        "--sample-across-videos",
        action="store_true",
        help="Deprecated/no-op: quality sampling across videos is always applied.",
    )
    parser.add_argument("--resume", action="store_true", help="Reuse completed batch files in the output directory.")
    return parser


def _batch_path(out_dir: Path, batch_index: int) -> Path:
    return out_dir / "batches" / f"batch_{batch_index:04d}.jsonl"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_csv_incremental(path: Path, rows: list[dict[str, Any]]) -> None:
    assert_column_contract(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TARGET_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_progress(out_dir: Path, event: dict[str, Any]) -> None:
    event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    progress_path = out_dir / "progress.jsonl"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with progress_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False))
        handle.write("\n")
    print(json.dumps(event, ensure_ascii=False), flush=True)


def run(args: argparse.Namespace) -> Path:
    if args.processed_run_dir:
        comments_path = args.processed_run_dir / "comments_normalized.parquet"
        if not comments_path.exists():
            comments_path = args.processed_run_dir / "comments.parquet"
        videos_path = args.processed_run_dir / "videos_normalized.parquet"
        rows = _rows_from_comments_parquet(comments_path, videos_path if videos_path.exists() else None)
    elif args.comments_parquet:
        rows = _rows_from_comments_parquet(args.comments_parquet, args.videos_parquet)
    else:
        rows = _rows_from_raw_file(args.raw_file)

    rows = _quality_sample_by_video(rows, args.limit)

    if args.limit is not None:
        rows = rows[: args.limit]

    run_id = args.run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
    out_dir = args.out_dir or (DEFAULT_OUT_ROOT / run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = out_dir / "voc_dashboard_dataset.csv"
    jsonl_path = out_dir / "voc_dashboard_dataset.jsonl"
    topic_path = out_dir / "topic_distribution.csv"
    metadata_path = out_dir / "metadata.json"

    analyzed_rows: list[dict[str, Any]] = []
    batch_size = max(1, args.batch_size)
    batches = [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]
    _write_progress(
        out_dir,
        {
            "stage": "run",
            "status": "started",
            "input_rows": len(rows),
            "batch_size": batch_size,
            "batches": len(batches),
        },
    )

    for batch_index, batch in enumerate(batches, start=1):
        batch_path = _batch_path(out_dir, batch_index)
        if args.resume and batch_path.exists():
            batch_rows = _read_jsonl(batch_path)
            analyzed_rows.extend(batch_rows)
            _write_progress(
                out_dir,
                {
                    "stage": "batch",
                    "status": "reused",
                    "batch_index": batch_index,
                    "input_rows": len(batch),
                    "output_rows": len(batch_rows),
                    "cumulative_output_rows": len(analyzed_rows),
                },
            )
            continue

        _write_progress(out_dir, {"stage": "batch", "status": "started", "batch_index": batch_index, "input_rows": len(batch)})
        batch_rows = analyze_rows(
            batch,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            llm_concurrency=args.llm_concurrency,
        )
        batch_path.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(batch_rows, batch_path)
        analyzed_rows.extend(batch_rows)
        _write_csv_incremental(dataset_path, analyzed_rows)
        write_jsonl(analyzed_rows, jsonl_path)
        _topic_distribution(analyzed_rows).to_csv(topic_path, index=False, encoding="utf-8-sig")
        _write_metadata(metadata_path, args=args, input_rows=len(rows), output_rows=len(analyzed_rows))
        _write_progress(
            out_dir,
            {
                "stage": "batch",
                "status": "completed",
                "batch_index": batch_index,
                "input_rows": len(batch),
                "output_rows": len(batch_rows),
                "cumulative_input_rows": min(batch_index * batch_size, len(rows)),
                "cumulative_output_rows": len(analyzed_rows),
                "unique_videos": len({_safe_text(row.get("video_id")) for row in rows[: min(batch_index * batch_size, len(rows))]}),
            },
        )

    write_csv(analyzed_rows, dataset_path)
    write_jsonl(analyzed_rows, jsonl_path)
    _topic_distribution(analyzed_rows).to_csv(topic_path, index=False, encoding="utf-8-sig")
    _write_metadata(metadata_path, args=args, input_rows=len(rows), output_rows=len(analyzed_rows))
    if analyzed_rows:
        bundle_path = write_export_bundle(pd.DataFrame(analyzed_rows), out_dir / BUNDLE_FILENAME)
        write_bundle_metadata_marker(out_dir, bundle_path)
    _write_progress(out_dir, {"stage": "run", "status": "completed", "output_rows": len(analyzed_rows)})

    print(json.dumps({"out_dir": str(out_dir), "rows": len(analyzed_rows)}, ensure_ascii=False, indent=2))
    return out_dir


if __name__ == "__main__":
    run(build_parser().parse_args())
