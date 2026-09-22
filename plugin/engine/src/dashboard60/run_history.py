"""Run history utilities for dashboard60 analysis outputs.

This module deliberately manages completed dashboard output artifacts only.
It does not start or modify any of the three analysis input paths
(processed run dir / raw upload / YouTube collection).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from pandas.errors import EmptyDataError


DATASET_FILENAME = "voc_dashboard_dataset.csv"
JSONL_FILENAME = "voc_dashboard_dataset.jsonl"
METADATA_FILENAME = "metadata.json"
PROGRESS_FILENAME = "progress.jsonl"
STDOUT_FILENAME = "_runner_stdout.log"
STDERR_FILENAME = "_runner_stderr.log"


@dataclass(frozen=True)
class RunHistoryRecord:
    run_id: str
    out_dir: Path
    dataset_path: Path
    metadata_path: Path
    progress_path: Path
    status: str
    created_at: str
    source_type: str
    input_summary: str
    row_count: int
    schema_version: str
    parser_version: str
    modified_at: float
    cleanup_candidate: bool = False

    @property
    def label(self) -> str:
        status = self.status or "unknown"
        created = self.created_at or "unknown time"
        rows = f"{self.row_count:,} rows"
        schema = self.schema_version or "schema unknown"
        source = self.input_summary or self.source_type or "input unknown"
        return f"{created} · {status} · {rows} · {schema} · {source} · {self.run_id}"


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _safe_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _progress_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _status_from_progress(events: list[dict[str, Any]]) -> str:
    if not events:
        return "unknown"
    for event in reversed(events):
        status = _safe_text(event.get("status"))
        stage = _safe_text(event.get("stage"))
        if status == "failed":
            return "failed"
        if status == "completed" and stage in {"run", "dashboard_analysis"}:
            return "completed"
    return _safe_text(events[-1].get("status")) or "running"


def _rows_from_progress(events: list[dict[str, Any]]) -> int:
    for event in reversed(events):
        value = event.get("output_rows") or event.get("cumulative_output_rows")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
    return 0


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return max(0, sum(1 for _ in path.open("r", encoding="utf-8-sig")) - 1)
    except OSError:
        return 0


def _source_from_metadata(metadata: dict[str, Any]) -> tuple[str, str]:
    youtube = metadata.get("youtube_collection")
    if isinstance(youtube, dict) and youtube:
        keywords = youtube.get("keywords") or [youtube.get("keyword")]
        keyword_text = ", ".join(_safe_text(item) for item in keywords if _safe_text(item))
        mode = _safe_text(youtube.get("keyword_mode")) or "OR"
        return "youtube", f"YouTube {mode}: {keyword_text}" if keyword_text else "YouTube"

    input_info = metadata.get("input")
    if isinstance(input_info, dict):
        uploaded_result = _safe_text(input_info.get("uploaded_analysis_result"))
        raw_file = _safe_text(input_info.get("raw_file"))
        processed = _safe_text(input_info.get("processed_run_dir"))
        if uploaded_result:
            return "uploaded_result", f"이전 분석 결과: {Path(uploaded_result).name}"
        if raw_file:
            return "raw", f"raw file: {Path(raw_file).name}"
        if processed:
            return "processed", f"processed: {Path(processed).name}"
    return "unknown", ""


def _created_at(metadata: dict[str, Any], events: list[dict[str, Any]], out_dir: Path) -> str:
    created = _safe_text(metadata.get("created_at"))
    if created:
        return created
    for event in events:
        ts = _safe_text(event.get("ts"))
        if ts:
            return ts
    try:
        return datetime.fromtimestamp(out_dir.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return ""


def _is_cleanup_candidate(out_dir: Path, *, now: float | None = None, max_age_days: int = 30) -> bool:
    current = now if now is not None else datetime.now(tz=timezone.utc).timestamp()
    try:
        age_seconds = current - out_dir.stat().st_mtime
    except OSError:
        return False
    return age_seconds > max_age_days * 24 * 60 * 60


def scan_run_history(run_root: Path, *, max_age_days: int = 30) -> list[RunHistoryRecord]:
    """Scan completed run artifact directories without loading full CSV bodies."""

    if not run_root.exists():
        return []
    records: list[RunHistoryRecord] = []
    for out_dir in sorted((path for path in run_root.iterdir() if path.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True):
        dataset_path = out_dir / DATASET_FILENAME
        metadata_path = out_dir / METADATA_FILENAME
        progress_path = out_dir / PROGRESS_FILENAME
        if not dataset_path.exists():
            continue
        metadata = _safe_json(metadata_path)
        events = _progress_events(progress_path)
        status = _status_from_progress(events)
        row_count = int(metadata.get("output_rows") or _rows_from_progress(events) or _count_csv_rows(dataset_path))
        source_type, input_summary = _source_from_metadata(metadata)
        try:
            modified_at = out_dir.stat().st_mtime
        except OSError:
            modified_at = 0.0
        records.append(
            RunHistoryRecord(
                run_id=out_dir.name,
                out_dir=out_dir,
                dataset_path=dataset_path,
                metadata_path=metadata_path,
                progress_path=progress_path,
                status=status,
                created_at=_created_at(metadata, events, out_dir),
                source_type=source_type,
                input_summary=input_summary,
                row_count=row_count,
                schema_version=_safe_text(metadata.get("schema_version")),
                parser_version=_safe_text(metadata.get("parser_version")),
                modified_at=modified_at,
                cleanup_candidate=_is_cleanup_candidate(out_dir, max_age_days=max_age_days),
            )
        )
    return records


def history_table(records: Iterable[RunHistoryRecord]) -> pd.DataFrame:
    rows = [
        {
            "run_id": record.run_id,
            "created_at": record.created_at,
            "status": record.status,
            "rows": record.row_count,
            "source_type": record.source_type,
            "input_summary": record.input_summary,
            "schema_version": record.schema_version,
            "cleanup_candidate": record.cleanup_candidate,
            "dataset_path": str(record.dataset_path),
        }
        for record in records
    ]
    return pd.DataFrame(rows)


def read_run_dataset(record: RunHistoryRecord) -> pd.DataFrame:
    try:
        frame = pd.read_csv(record.dataset_path, keep_default_na=False)
    except EmptyDataError:
        frame = pd.DataFrame()
    frame["source_run"] = record.run_id
    return frame


def merge_run_datasets(
    records: Iterable[RunHistoryRecord],
    *,
    deduplicate: bool = True,
) -> pd.DataFrame:
    frames = [read_run_dataset(record) for record in records]
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True, sort=False)
    if deduplicate and not merged.empty:
        if "source_id" in merged.columns:
            key_columns = ["source_id"]
        else:
            key_columns = [column for column in ["video_id", "original_voc"] if column in merged.columns]
        if key_columns:
            merged = merged.drop_duplicates(subset=key_columns, keep="first").reset_index(drop=True)
    return merged


def write_merged_run(
    *,
    records: Iterable[RunHistoryRecord],
    merged: pd.DataFrame,
    out_dir: Path,
    deduplicate: bool,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = out_dir / DATASET_FILENAME
    merged.to_csv(dataset_path, index=False, encoding="utf-8-sig")
    now = datetime.now(timezone.utc).isoformat()
    (out_dir / JSONL_FILENAME).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in merged.to_dict(orient="records")),
        encoding="utf-8",
    )

    selected = list(records)
    schema_versions = sorted({record.schema_version for record in selected if record.schema_version})
    metadata = {
        "schema_version": schema_versions[0] if len(schema_versions) == 1 else "mixed",
        "parser_version": "dashboard60-run-history",
        "data_source": "dashboard60_run_history_merge",
        "created_at": now,
        "input_rows": sum(record.row_count for record in selected),
        "output_rows": int(len(merged)),
        "merged_runs": [
            {
                "run_id": record.run_id,
                "dataset_path": str(record.dataset_path),
                "schema_version": record.schema_version,
                "rows": record.row_count,
            }
            for record in selected
        ],
        "deduplicate": bool(deduplicate),
    }
    (out_dir / METADATA_FILENAME).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / PROGRESS_FILENAME).write_text(
        json.dumps({"ts": now, "stage": "run", "status": "completed", "output_rows": int(len(merged))}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (out_dir / STDOUT_FILENAME).write_text(
        f"{now} dashboard60 run-history merge completed: output_rows={len(merged)}\n",
        encoding="utf-8",
    )
    (out_dir / STDERR_FILENAME).write_text("", encoding="utf-8")
    return dataset_path
