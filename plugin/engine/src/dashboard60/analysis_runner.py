"""In-dashboard first-pass analysis runner for the dashboard60 operating app.

The runner keeps Streamlit responsive by launching subprocesses that write
progress artifacts.  It supports three input modes:

1. an already-normalized processed run directory,
2. an uploaded raw VoC file, and
3. direct YouTube collection through the existing legacy collection pipeline.

The YouTube mode intentionally reuses ``src.cli.run_pipeline`` through the
wrapper script ``scripts/run_dashboard60_youtube_collect_and_analyze.py``.
No YouTube collection logic is duplicated in the dashboard layer.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import zipfile
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import dotenv_values
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover - optional Streamlit component import guard
    st_autorefresh = None

from src.api.quota import YOUTUBE_QUOTA_COSTS, estimate_quota_usage
from src.dashboard60.release_export import (
    ReleaseCheckFailed,
    build_release_workbook,
    release_filename,
)
from src.dashboard60.export_bundle import (
    BUNDLE_FILENAME,
    SHEET_RAW_VOC,
    write_export_bundle,
    write_bundle_metadata_marker,
)
from src.dashboard60.run_history import (
    JSONL_FILENAME,
    METADATA_FILENAME,
    PROGRESS_FILENAME,
    STDERR_FILENAME,
    STDOUT_FILENAME,
    history_table,
    merge_run_datasets,
    scan_run_history,
    write_merged_run,
)
from src.voc_rebuild import TARGET_COLUMNS


ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / "outputs" / "voc_dashboard_60" / "app_runs"
UPLOAD_ROOT = ROOT / "outputs" / "voc_dashboard_60" / "uploads"
RUN_LOG_PATH = ROOT / "outputs" / "voc_dashboard_60" / "analysis_run_log.jsonl"
SESSION_RUN_KEY = "dashboard60_active_analysis_run"
SESSION_UPLOAD_PATH_KEY = "dashboard60_uploaded_raw_path"
SESSION_UPLOAD_SIG_KEY = "dashboard60_uploaded_raw_signature"
SESSION_ANALYZED_UPLOAD_PATH_KEY = "dashboard60_uploaded_analyzed_path"
SESSION_ANALYZED_UPLOAD_SIG_KEY = "dashboard60_uploaded_analyzed_signature"
SESSION_REANALYSIS_UPLOAD_PATH_KEY = "dashboard60_reanalysis_upload_path"
SESSION_REANALYSIS_UPLOAD_SIG_KEY = "dashboard60_reanalysis_upload_signature"
SESSION_HISTORY_CONFIRM_MIXED_KEY = "dashboard60_history_confirm_mixed_schema"
AND_CANDIDATE_MULTIPLIER = 5
AND_CANDIDATE_MIN = 200
AND_CANDIDATE_CAP = 300
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
RECOVERABLE_RUN_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class ProgressSummary:
    events: list[dict[str, Any]]
    last_event: dict[str, Any]
    status: str
    input_rows: int
    output_rows: int
    completed_batches: int
    total_batches: int


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _safe_slug(value: str, default: str = "dashboard_run") -> str:
    text = _safe_text(value) or default
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")
    return slug or default


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _status_display(status: object) -> str:
    text = _safe_text(status) or "unknown"
    return {
        "completed": "정상",
        "completed_empty": "빈결과",
        "failed": "실패",
        "running": "실행중",
        "unknown": "상태미확인",
    }.get(text, text)


def _source_type_display(source_type: object) -> str:
    text = _safe_text(source_type) or "unknown"
    return {
        "youtube": "YouTube 수집",
        "processed": "processed run",
        "raw": "raw 업로드",
        "uploaded_result": "이전 분석 결과",
        "history_merge": "run 병합",
        "unknown": "입력 미확인",
    }.get(text, text)


def _history_keywords(record: Any) -> str:
    metadata = _read_json_file(record.metadata_path)
    youtube = metadata.get("youtube_collection")
    if isinstance(youtube, dict) and youtube:
        keywords = youtube.get("keywords") or [youtube.get("keyword")]
        keyword_text = ", ".join(_safe_text(item) for item in keywords if _safe_text(item))
        mode = _safe_text(youtube.get("keyword_mode")) or "OR"
        return f"{mode}: {keyword_text}" if keyword_text else "YouTube"
    merged_runs = metadata.get("merged_runs")
    if isinstance(merged_runs, list) and merged_runs:
        return f"{len(merged_runs)}개 run 병합"
    return record.input_summary or record.run_id


def _format_history_time(value: object) -> str:
    text = _safe_text(value)
    if not text:
        return "unknown time"
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return text


def _run_display_name(record: Any) -> str:
    metadata = _read_json_file(record.metadata_path)
    explicit_name = _safe_text(metadata.get("run_suffix") or metadata.get("run_name"))
    if explicit_name:
        return explicit_name
    match = re.match(r"^(?P<name>.+?)_(?P<date>\d{8})_(?P<time>\d{6})$", _safe_text(record.run_id))
    if not match:
        return ""
    name = match.group("name").strip("_-. ")
    if not name or name in {"run", "history_merge"}:
        return ""
    return name


def _history_display_table(records: list[Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                # ★ 셋만 영어로 남아 있었다 (sky 2026-08-20)
                "실행 이름": _run_display_name(record) or _format_history_time(record.created_at),
                "실행 시각": _format_history_time(record.created_at),
                "상태": _status_display(record.status),
                "입력 유형": _source_type_display(record.source_type),
                "검색/입력 요약": _history_keywords(record),
                "결과 행수": record.row_count,
                "스키마 판": record.schema_version,
                "실행 ID": record.run_id,
            }
            for record in records
        ]
    )


def _history_select_label(record: Any) -> str:
    name = _run_display_name(record)
    created = _format_history_time(record.created_at)
    head = f"{name} · {created}" if name else created
    return (
        # ★ 앞부분 순서는 시험이 지킨다. 뒤쪽 영어 단어만 옮긴다 (sky 2026-08-20)
        f"{head} · {_status_display(record.status)} · "
        f"{_source_type_display(record.source_type)} · {record.row_count:,}행 · "
        f"{_history_keywords(record)} · {record.schema_version or '스키마 미상'} · {record.run_id}"
    )


def _parse_keyword_terms(value: object) -> list[str]:
    """Parse the dashboard multi-keyword field.

    The UI deliberately uses one keyword per line instead of comma-separated
    text so users can see and edit the search terms as a small tag list.
    """

    text = _safe_text(value)
    if not text:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"[\r\n]+", text):
        item = raw.strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        terms.append(item)
    return terms


def _build_search_terms_for_mode(keywords: list[str], mode: str) -> list[str]:
    match_mode = _safe_text(mode).upper() or "OR"
    if match_mode == "AND" and len(keywords) > 1:
        return keywords
    return keywords


def _youtube_published_boundary(value: object, *, end_of_day: bool = False) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        current = value.date()
    elif isinstance(value, date):
        current = value
    else:
        text = _safe_text(value)
        if not text:
            return ""
        try:
            current = date.fromisoformat(text[:10])
        except ValueError:
            return ""
    time_suffix = "23:59:59Z" if end_of_day else "00:00:00Z"
    return f"{current.isoformat()}T{time_suffix}"


def _estimate_youtube_quota_for_keywords(
    *,
    max_videos: int,
    comments_per_video: int,
    include_replies: bool,
    keyword_count: int,
    keyword_mode: str,
    and_min_keyword_matches: int | None = None,
) -> dict[str, int]:
    keyword_count = max(1, int(keyword_count or 1))
    mode = _safe_text(keyword_mode).upper() or "OR"
    if mode == "AND" and keyword_count > 1:
        per_keyword_videos = max(
            max_videos,
            min(AND_CANDIDATE_CAP, max(AND_CANDIDATE_MIN, max_videos * AND_CANDIDATE_MULTIPLIER)),
        )
        collection_video_count = max_videos
    else:
        per_keyword_videos = max(1, max_videos)
        collection_video_count = max_videos
    per_keyword_search_calls = ceil(per_keyword_videos / 50) if per_keyword_videos else 0
    search_keyword_multiplier = 1 if mode == "AND" and keyword_count > 1 else keyword_count
    collection_quota = estimate_quota_usage(
        max_videos=collection_video_count,
        comments_per_video=comments_per_video,
        include_replies=include_replies,
    )
    quota = {
        "search.list": per_keyword_search_calls * search_keyword_multiplier,
        "videos.list": per_keyword_search_calls * search_keyword_multiplier,
        "commentThreads.list": collection_quota["commentThreads.list"],
        "comments.list": collection_quota["comments.list"],
    }
    quota["total_units"] = sum(YOUTUBE_QUOTA_COSTS[key] * value for key, value in quota.items())
    return quota


def _dotenv_candidates(root: Path | None = None) -> list[Path]:
    """Return local and shared-repository dotenv paths without hardcoding a drive."""

    project_root = (root or ROOT).resolve()
    candidates = [project_root / ".env"]
    if project_root.parent.name.lower() == ".worktrees":
        candidates.append(project_root.parent.parent / ".env")
    return list(dict.fromkeys(candidates))


def _secret_then_env(name: str) -> str:
    """Resolve a secret: Streamlit Secrets, environment, then local/shared .env."""

    try:
        value = st.secrets.get(name, "")  # type: ignore[attr-defined]
    except Exception:
        value = ""
    secret_value = _safe_text(value)
    if secret_value:
        return secret_value
    env_value = os.environ.get(name, "").strip()
    if env_value:
        return env_value
    for dotenv_path in _dotenv_candidates():
        if not dotenv_path.is_file():
            continue
        try:
            dotenv_value = _safe_text(dotenv_values(dotenv_path).get(name, ""))
        except Exception:
            dotenv_value = ""
        if dotenv_value:
            return dotenv_value
    return ""


def _resolve_openai_api_key() -> str:
    return _secret_then_env("OPENAI_API_KEY")


def _resolve_youtube_api_key() -> str:
    return _secret_then_env("YOUTUBE_API_KEY")


def _append_run_log(record: dict[str, Any]) -> None:
    RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **record}, ensure_ascii=False))
        handle.write("\n")


def _serializable_run_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return the server-persisted subset of a Streamlit run state.

    ``subprocess.Popen`` and monotonic timestamps are process-local and must not
    be serialized. Commands are persisted without environment variables, so API
    keys never enter the recovery manifest.
    """

    persisted: dict[str, Any] = {}
    for key, value in state.items():
        if key in {"process", "started_monotonic"}:
            continue
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            continue
        persisted[key] = value
    persisted["updated_at"] = datetime.now(timezone.utc).isoformat()
    return persisted


def _run_state_path(out_dir: Path) -> Path:
    return out_dir / RUN_STATE_FILENAME


def _persist_run_state(state: dict[str, Any]) -> Path:
    out_dir = Path(_safe_text(state.get("out_dir")))
    if not _safe_text(out_dir):
        raise ValueError("run state requires out_dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _run_state_path(out_dir)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(_serializable_run_state(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def _load_run_state(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _pid_is_running(pid: object) -> bool:
    try:
        pid_value = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if pid_value <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            process_query_limited_information = 0x1000
            still_active = 259
            handle = kernel32.OpenProcess(process_query_limited_information, False, pid_value)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            try:
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid_value, 0)
    except OSError:
        return False
    return True


def _terminate_run_process(state: dict[str, Any], *, timeout: float = 5.0) -> tuple[bool, str]:
    """Stop the subprocess for a dashboard run without deleting checkpoints."""

    process = state.get("process")
    pid_text = _safe_text(state.get("pid"))
    if process is not None:
        try:
            if process.poll() is not None:
                return True, "process already exited"
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=timeout)
            return True, "process terminated"
        except Exception as exc:
            return False, f"process termination failed: {exc}"

    if not pid_text:
        return True, "no pid recorded"
    try:
        pid = int(pid_text)
    except ValueError:
        return False, f"invalid pid: {pid_text}"
    if not _pid_is_running(pid):
        return True, "pid already exited"

    if sys.platform == "win32":
        try:
            graceful = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if graceful.returncode != 0 and _pid_is_running(pid):
                forced = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                if forced.returncode != 0 and _pid_is_running(pid):
                    return False, (forced.stderr or forced.stdout or "taskkill failed").strip()
            return True, "pid terminated"
        except Exception as exc:
            return False, f"pid termination failed: {exc}"

    try:
        import signal

        os.kill(pid, signal.SIGTERM)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not _pid_is_running(pid):
                return True, "pid terminated"
            time.sleep(0.1)
        os.kill(pid, signal.SIGKILL)
        return True, "pid killed"
    except Exception as exc:
        return False, f"pid termination failed: {exc}"


def _cancel_run_state(state: dict[str, Any], *, write_log: bool = True) -> tuple[bool, str]:
    ok, message = _terminate_run_process(state)
    state["status"] = "cancelled" if ok else "cancel_failed"
    state["cancelled_at"] = datetime.now(timezone.utc).isoformat()
    state["cancel_message"] = message
    _persist_run_state(state)
    if write_log:
        _append_run_log(
            {
                "status": state["status"],
                "run_id": state.get("run_id", ""),
                "out_dir": state.get("out_dir", ""),
                "pid": state.get("pid", ""),
                "message": message,
                "source_type": state.get("source_type", ""),
            }
        )
    return ok, message


def _parse_state_time(value: object) -> datetime | None:
    text = _safe_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_recent_recovery_state(state: dict[str, Any], *, now: datetime | None = None) -> bool:
    status = _safe_text(state.get("status"))
    if status == "running":
        return True
    if status not in {"interrupted", "cancelled", "failed"}:
        return True
    timestamp = _parse_state_time(state.get("updated_at") or state.get("cancelled_at") or state.get("started_at"))
    if timestamp is None:
        return False
    reference = now or datetime.now(timezone.utc)
    return reference - timestamp <= RECOVERABLE_RUN_TTL


def _find_recoverable_run(run_root: Path = RUN_ROOT) -> dict[str, Any] | None:
    """Find the newest incomplete or just-completed dashboard run on disk."""

    if not run_root.exists():
        return None
    candidates: list[dict[str, Any]] = []
    for path in run_root.glob(f"*/{RUN_STATE_FILENAME}"):
        state = _load_run_state(path)
        if not state:
            continue
        if state.get("recovery_dismissed"):
            continue
        out_dir = Path(_safe_text(state.get("out_dir")))
        summary = _read_progress(out_dir)
        if summary.status == "completed" and (out_dir / "voc_dashboard_dataset.csv").exists():
            state["status"] = "completed"
        elif _safe_text(state.get("status")) == "running" and not _pid_is_running(state.get("pid")):
            state["status"] = "interrupted"
        if not _is_recent_recovery_state(state):
            continue
        if state.get("status") in {"running", "interrupted", "cancelled", "failed", "completed"}:
            candidates.append(state)
    if not candidates:
        return None
    status_priority = {"running": 3, "interrupted": 2, "cancelled": 2, "failed": 1, "completed": 0}
    return max(
        candidates,
        key=lambda item: (
            status_priority.get(_safe_text(item.get("status")), -1),
            _safe_text(item.get("updated_at") or item.get("started_at")),
        ),
    )


def _resume_command(command: list[str]) -> list[str]:
    resumed = [str(value) for value in command]
    if "--resume" not in resumed:
        resumed.append("--resume")
    return resumed


def _read_progress(out_dir: Path) -> ProgressSummary:
    progress_path = out_dir / "progress.jsonl"
    events: list[dict[str, Any]] = []
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    last_event = events[-1] if events else {}
    run_started_events = [
        event for event in events if event.get("stage") == "run" and event.get("status") == "started"
    ]
    run_started = run_started_events[-1] if run_started_events else {}
    completed_batches = sum(
        1 for event in events if event.get("stage") == "batch" and event.get("status") in {"completed", "reused"}
    )
    latest_output_event = next(
        (event for event in reversed(events) if event.get("output_rows") or event.get("cumulative_output_rows")),
        {},
    )
    latest_input_event = next(
        (event for event in reversed(events) if event.get("input_rows") or event.get("cumulative_input_rows")),
        {},
    )
    output_rows = int(latest_output_event.get("output_rows") or latest_output_event.get("cumulative_output_rows") or 0)
    input_rows = int(
        run_started.get("input_rows")
        or latest_input_event.get("cumulative_input_rows")
        or latest_input_event.get("input_rows")
        or 0
    )
    total_batches = int(run_started.get("batches") or 0)
    status = "completed" if (
        last_event.get("stage") == "run"
        and last_event.get("status") == "completed"
        or last_event.get("stage") == "dashboard_analysis"
        and last_event.get("status") == "completed"
    ) else "running"
    if last_event.get("status") == "failed":
        status = "failed"
    return ProgressSummary(events, last_event, status, input_rows, output_rows, completed_batches, total_batches)


def _build_command(
    *,
    source_type: str,
    source_path: Path | None,
    out_dir: Path,
    run_id: str,
    model: str,
    limit: int,
    batch_size: int,
    timeout_seconds: int,
    sample_across_videos: bool,
    youtube_keyword: str = "",
    youtube_keywords: list[str] | None = None,
    youtube_keyword_mode: str = "OR",
    youtube_and_min_keyword_matches: int | None = None,
    youtube_region: str = "KR",
    youtube_language: str = "ko",
    youtube_max_videos: int = 3,
    youtube_comments_per_video: int = 20,
    youtube_include_replies: bool = True,
    youtube_channel_id: str = "",
    youtube_published_after: str = "",
    youtube_published_before: str = "",
) -> list[str]:
    if source_type == "youtube":
        keyword_terms = _build_search_terms_for_mode(
            youtube_keywords if youtube_keywords is not None else _parse_keyword_terms(youtube_keyword),
            youtube_keyword_mode,
        )
        primary_keyword = keyword_terms[0] if keyword_terms else _safe_text(youtube_keyword)
        command = [
            sys.executable,
            str(ROOT / "scripts" / "run_dashboard60_youtube_collect_and_analyze.py"),
            "--out-dir",
            str(out_dir),
            "--run-id",
            run_id,
            "--keyword",
            primary_keyword,
            "--region",
            _safe_text(youtube_region) or "KR",
            "--language",
            _safe_text(youtube_language) or "ko",
            "--max-videos",
            str(max(1, int(youtube_max_videos))),
            "--comments-per-video",
            str(max(0, int(youtube_comments_per_video))),
            "--batch-size",
            str(max(1, int(batch_size))),
            "--timeout-seconds",
            str(max(1, int(timeout_seconds))),
        ]
        if _safe_text(youtube_keyword_mode):
            command.extend(["--keyword-mode", _safe_text(youtube_keyword_mode).upper()])
        if youtube_and_min_keyword_matches is not None:
            command.extend(["--and-min-keyword-matches", str(int(youtube_and_min_keyword_matches))])
        if keyword_terms[1:]:
            command.extend(["--keywords", *keyword_terms[1:]])
        if _safe_text(youtube_channel_id):
            command.extend(["--channel-id", _safe_text(youtube_channel_id)])
        if _safe_text(youtube_published_after):
            command.extend(["--published-after", _safe_text(youtube_published_after)])
        if _safe_text(youtube_published_before):
            command.extend(["--published-before", _safe_text(youtube_published_before)])
        command.extend(["--include-replies", "true" if youtube_include_replies else "false"])
        if _safe_text(model):
            command.extend(["--model", _safe_text(model)])
        if int(limit or 0) > 0:
            command.extend(["--limit", str(int(limit))])
        return command

    if source_path is None:
        raise ValueError("source_path is required for processed/raw analysis")

    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_voc_rebuild_dashboard.py"),
        "--out-dir",
        str(out_dir),
        "--run-id",
        run_id,
        "--batch-size",
        str(max(1, int(batch_size))),
        "--timeout-seconds",
        str(max(1, int(timeout_seconds))),
    ]
    if source_type == "processed":
        command.extend(["--processed-run-dir", str(source_path)])
    else:
        command.extend(["--raw-file", str(source_path)])
    if _safe_text(model):
        command.extend(["--model", _safe_text(model)])
    if int(limit or 0) > 0:
        command.extend(["--limit", str(int(limit))])
    return command


def _start_subprocess(command: list[str], out_dir: Path) -> subprocess.Popen[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = out_dir / "_runner_stdout.log"
    stderr_path = out_dir / "_runner_stderr.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) if not env.get("PYTHONPATH") else os.pathsep.join([str(ROOT), env["PYTHONPATH"]])

    openai_key = _resolve_openai_api_key()
    if openai_key:
        env["OPENAI_API_KEY"] = openai_key

    youtube_key = _resolve_youtube_api_key()
    if youtube_key:
        env["YOUTUBE_API_KEY"] = youtube_key

    stdout_handle = stdout_path.open("a", encoding="utf-8", newline="\n")
    stderr_handle = stderr_path.open("a", encoding="utf-8", newline="\n")
    try:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            env=env,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    return process


def _save_uploaded_file(uploaded_file: Any) -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = _safe_slug(getattr(uploaded_file, "name", "") or "uploaded_raw_voc.csv")
    path = UPLOAD_ROOT / f"{suffix}_{safe_name}"
    path.write_bytes(uploaded_file.getvalue())
    return path


def _read_analyzed_result_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, keep_default_na=False)
    if suffix in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(path, sheet_name=SHEET_RAW_VOC, keep_default_na=False)
        except ValueError:
            return pd.read_excel(path, sheet_name=0, keep_default_na=False)
    raise ValueError("지원하지 않는 분석 결과 파일 형식입니다. CSV 또는 6-Sheet Excel을 업로드해 주세요.")


def _validate_analyzed_result_frame(frame: pd.DataFrame) -> tuple[bool, str]:
    if frame.empty:
        return False, "업로드 파일에 데이터 행이 없습니다."
    required = {"source_id", "original_voc", "topic", "cej", "confidence_rating"}
    missing_required = sorted(required - set(frame.columns))
    if missing_required:
        return False, "분석 완료 스키마 필수 컬럼이 없습니다: " + ", ".join(missing_required)
    matched = sum(1 for column in TARGET_COLUMNS if column in frame.columns)
    if matched < MIN_ANALYZED_RESULT_COLUMNS:
        return False, (
            "66컬럼 분석 완료본으로 보기 어렵습니다. "
            f"목표 컬럼 매칭 {matched}개/{len(TARGET_COLUMNS)}개"
        )
    return True, ""


def _prepare_exact_reanalysis_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Reduce an analyzed atomic dataset back to one row per original comment."""

    if "original_voc" not in frame.columns:
        raise ValueError("분석 완료본에 original_voc 컬럼이 없습니다.")
    source_columns = [
        "source_id",
        "raw_row_index",
        "original_voc",
        "video_id",
        "video_title",
        "video_url",
        "channel_id",
        "parent_voc_id",
        "comment_relation",
        "is_reply",
        "market",
        "language",
        "published_at",
        "video_tags",
        "video_description",
    ]
    selected = [column for column in source_columns if column in frame.columns]
    result = frame.loc[:, selected].copy()
    result["original_voc"] = result["original_voc"].map(_safe_text)
    result = result[result["original_voc"] != ""].copy()
    if "source_id" not in result.columns:
        result["source_id"] = ""
    result["source_id"] = result["source_id"].map(_safe_text)
    result["_reanalysis_key"] = result.apply(
        lambda row: f"source:{row['source_id']}" if row["source_id"] else f"text:{row['original_voc']}",
        axis=1,
    )
    result = result.drop_duplicates(subset=["_reanalysis_key"], keep="first").drop(columns=["_reanalysis_key"])
    result["raw_row_index"] = range(1, len(result) + 1)
    return result.reset_index(drop=True)


def _save_exact_reanalysis_source(frame: pd.DataFrame, *, source_name: str) -> Path:
    output_dir = UPLOAD_ROOT / "exact_reanalysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = _safe_slug(Path(source_name).stem or "analyzed_result")
    path = output_dir / f"{stem}_originals_{timestamp}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _write_uploaded_analyzed_result(uploaded_file: Any) -> tuple[Path | None, str, dict[str, Any]]:
    upload_bytes = uploaded_file.getvalue()
    original_name = getattr(uploaded_file, "name", "") or "uploaded_result.csv"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"uploaded_result_{timestamp}_{_safe_slug(original_name, 'result')}"
    out_dir = RUN_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    source_path = out_dir / original_name
    source_path.write_bytes(upload_bytes)
    try:
        frame = _read_analyzed_result_file(source_path)
    except Exception as exc:
        return None, f"업로드 파일을 읽지 못했습니다: {type(exc).__name__}: {exc}", {}

    ok, message = _validate_analyzed_result_frame(frame)
    if not ok:
        return None, message, {"source_path": str(source_path)}

    for column in TARGET_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    extra_columns = [column for column in frame.columns if column not in TARGET_COLUMNS]
    dataset_path = out_dir / "voc_dashboard_dataset.csv"
    frame[[*TARGET_COLUMNS, *extra_columns]].to_csv(dataset_path, index=False, encoding="utf-8-sig")

    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "schema_version": "uploaded-analysis-result",
        "parser_version": "dashboard60-uploaded-result-loader",
        "data_source": "dashboard60_uploaded_analyzed_result",
        "created_at": now,
        "run_suffix": _safe_slug(original_name, "uploaded_result"),
        "output_rows": int(len(frame)),
        "source_filename": original_name,
        "input": {"uploaded_analysis_result": str(source_path)},
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "progress.jsonl").write_text(
        json.dumps({"ts": now, "stage": "run", "status": "completed", "output_rows": int(len(frame))}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "_runner_stdout.log").write_text(f"{now} uploaded analysis result loaded without reanalysis\n", encoding="utf-8")
    (out_dir / "_runner_stderr.log").write_text("", encoding="utf-8")
    _ensure_jsonl_from_csv(dataset_path)
    bundle_path = _ensure_export_bundle(dataset_path)
    _append_run_log(
        {
            "status": "completed",
            "run_id": run_id,
            "out_dir": str(out_dir),
            "dataset_path": str(dataset_path),
            "export_bundle_path": str(bundle_path or ""),
            "source_type": "uploaded_result",
            "source_path": str(source_path),
            "input_rows": int(len(frame)),
            "output_rows": int(len(frame)),
        }
    )
    return dataset_path, "", metadata


def _download_file(label: str, path: Path, *, mime: str = "text/plain") -> None:
    if path.exists():
        st.download_button(label, data=path.read_bytes(), file_name=path.name, mime=mime, width="stretch")


def _ensure_export_bundle(dataset_path: Path) -> Path | None:
    if not dataset_path.exists():
        return None
    bundle_path = dataset_path.parent / BUNDLE_FILENAME
    if bundle_path.exists():
        return bundle_path
    try:
        frame = pd.read_csv(dataset_path, keep_default_na=False)
        write_export_bundle(frame, bundle_path)
        write_bundle_metadata_marker(dataset_path.parent, bundle_path)
        return bundle_path
    except Exception as exc:
        _append_run_log(
            {
                "status": "export_bundle_failed",
                "run_id": dataset_path.parent.name,
                "out_dir": str(dataset_path.parent),
                "dataset_path": str(dataset_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        return None


def _ensure_jsonl_from_csv(dataset_path: Path) -> Path | None:
    if not dataset_path.exists():
        return None
    jsonl_path = dataset_path.parent / JSONL_FILENAME
    if jsonl_path.exists():
        return jsonl_path
    try:
        frame = pd.read_csv(dataset_path, keep_default_na=False)
        jsonl_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in frame.to_dict(orient="records")),
            encoding="utf-8",
        )
        return jsonl_path
    except Exception as exc:
        _append_run_log(
            {
                "status": "jsonl_backfill_failed",
                "run_id": dataset_path.parent.name,
                "out_dir": str(dataset_path.parent),
                "dataset_path": str(dataset_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        return None


def _ensure_history_artifacts(dataset_path: Path) -> dict[str, Path | None]:
    """Backfill lightweight downloadable artifacts for historical runs.

    This keeps old run-history entries aligned with new runs without rerunning
    OpenAI. The Excel bundle is rebuilt from the stored CSV; L2 narrative is
    cache-only inside ``write_export_bundle``.
    """

    out_dir = dataset_path.parent
    now = datetime.now(timezone.utc).isoformat()
    try:
        frame = pd.read_csv(dataset_path, keep_default_na=False) if dataset_path.exists() else pd.DataFrame()
    except Exception:
        frame = pd.DataFrame()
    artifacts: dict[str, Path | None] = {
        "csv": dataset_path if dataset_path.exists() else None,
        "jsonl": _ensure_jsonl_from_csv(dataset_path),
        "metadata": out_dir / METADATA_FILENAME,
        "progress": out_dir / PROGRESS_FILENAME,
        "stdout": out_dir / STDOUT_FILENAME,
        "stderr": out_dir / STDERR_FILENAME,
        "excel": None,
    }
    if not artifacts["metadata"].exists():
        try:
            metadata = {
                "schema_version": "unknown",
                "parser_version": "dashboard60-run-history-backfill",
                "data_source": "dashboard60_run_history_backfill",
                "created_at": now,
                "output_rows": int(len(frame)),
            }
            artifacts["metadata"].write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            artifacts["metadata"] = None
    if artifacts["progress"] is not None and not artifacts["progress"].exists():
        artifacts["progress"].write_text(
            json.dumps({"ts": now, "stage": "run", "status": "completed", "output_rows": int(len(frame))}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if artifacts["stdout"] is not None and not artifacts["stdout"].exists():
        artifacts["stdout"].write_text(f"{now} dashboard60 historical artifact backfill\n", encoding="utf-8")
    if artifacts["stderr"] is not None and not artifacts["stderr"].exists():
        artifacts["stderr"].write_text("", encoding="utf-8")
    artifacts["excel"] = _ensure_export_bundle(dataset_path)
    return artifacts


# ★ 처음 보는 사람 기준으로 적는다 (sky 2026-08-20).
#   내용을 직접 열어 확인하고 붙인 설명이다.
ARTIFACT_MAIN: list[tuple[str, str, str, str]] = [
    # key, 버튼 이름, 언제 쓰는지, mime
    (
        "excel",
        "최종 데이터 받기",
        "이 분석의 결과물입니다. 웬만한 일은 이것 하나면 됩니다.",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    (
        "csv",
        "표만 받기 (CSV)",
        "엑셀 말고 다른 프로그램에 넣을 때.",
        "text/csv",
    ),
    (
        "jsonl",
        "표만 받기 (JSONL)",
        "프로그램으로 읽을 때 쓰는 형식입니다.",
        "application/jsonl",
    ),
]

# ★ 문제가 생겼을 때 보는 것들. 하나하나 설명하지 않는다 —
#   실무자가 이걸 열어 읽을 일은 없고, 통째로 넘겨 주면 되는 것들이다 (sky 2026-08-20).
ARTIFACT_DIAGNOSTIC_KEYS = ("metadata", "progress", "stdout", "stderr")


def _build_diagnostic_zip(artifacts: dict[str, Path | None]) -> tuple[bytes, list[str]]:
    """진단용 파일들을 zip 하나로 묶는다. (바이트, 담긴 파일 이름들)"""

    names: list[str] = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for key in ARTIFACT_DIAGNOSTIC_KEYS:
            path = artifacts.get(key)
            if path is None or not Path(path).exists():
                continue
            archive.write(path, arcname=Path(path).name)
            names.append(Path(path).name)
    return buffer.getvalue(), names


def _render_diagnostic_download(artifacts: dict[str, Path | None], prefix: str) -> None:
    """문제가 생겼을 때 넘길 것 — 낱개가 아니라 한 묶음으로 (sky 2026-08-20).

    ★ 낱개로 두면 「어느 것을 받아야 하나」 를 또 고민하게 된다.
      네 개를 다 받아 그대로 넘기는 것이 답이므로, 애초에 한 묶음으로 준다.
    """

    payload, names = _build_diagnostic_zip(artifacts)
    if not names:
        return

    st.markdown("**잘 안 될 때**")
    st.caption(
        "아래를 받아서 **파일 그대로** 담당자나 AI 에게 주고 "
        "「이 분석이 잘 안 됐는데 원인을 찾아 달라」 고 하시면 됩니다. "
        "열어 보실 필요는 없습니다."
    )
    st.download_button(
        f"{prefix}기록 묶음 받기 ({' · '.join(names)})",
        data=payload,
        file_name="분석기록.zip",
        mime="application/zip",
        key=f"dl_diag::{id(artifacts)}",
        width="stretch",
    )


def _download_artifact_set(
    artifacts: dict[str, Path | None],
    *,
    prefix: str = "",
    release_source: Path | None = None,
    release_note: str = "",
) -> None:
    """받을 수 있는 파일을 「언제 쓰는지」 로 보여 준다.

    ★ 겉모습만 바꾼다. 어떤 파일을 만들지·어디에 두는지는 건드리지 않는다.
    """

    available = [item for item in ARTIFACT_MAIN if artifacts.get(item[0]) is not None]
    if not available and not any(
        artifacts.get(key) is not None for key in ARTIFACT_DIAGNOSTIC_KEYS
    ):
        st.caption("내려받을 수 있는 파일이 아직 없습니다.")
        return

    columns = st.columns(2)
    for index, (key, label, note, mime) in enumerate(available):
        with columns[index % 2]:
            _download_file(f"{prefix}{label}", artifacts[key], mime=mime)
            st.caption(note)

    st.divider()
    _render_diagnostic_download(artifacts, prefix)

    # ★ 사외용의 원본은 「올린 파일 그 자체」 일 수도 있다 (sky 2026-08-20).
    _render_release_download(
        release_source or artifacts.get("excel"), prefix=prefix, note=release_note
    )


def _uploaded_source_path(dataset_path: Path) -> Path | None:
    """업로드 자리에서 「올린 파일 그 자체」 를 찾아 준다 (sky 2026-08-20).

    ★ 올린 원본은 지워지지 않고 같은 폴더에 남아 있다.
      그 경로가 metadata.json 의 input.uploaded_analysis_result 에 적힌다.
    ★ 못 찾으면 None 을 돌려준다. 부르는 쪽이 지금까지 쓰던 것으로 되돌아간다 —
      기능이 조용히 사라지지 않게.
    """

    metadata_path = Path(dataset_path).parent / METADATA_FILENAME
    if not metadata_path.exists():
        return None
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw = _safe_text(str((payload.get("input") or {}).get("uploaded_analysis_result", "")))
    if not raw:
        return None
    candidate = Path(raw)
    # 엑셀이 아니면(예: CSV 업로드) 사외용 원본으로 쓸 수 없다
    if candidate.suffix.lower() not in (".xlsx", ".xls") or not candidate.exists():
        return None
    return candidate


def _render_release_download(
    excel_path: Path | None, *, prefix: str = "", note: str = ""
) -> None:
    """사외로 낼 때 쓰는 판본. 누를 때 그 자리에서 만든다 (sky 2026-08-20).

    ★ 위 버튼들과 나란히 두지 않고 한 칸 띄운다. 성격이 다르기 때문이다 —
      위는 사내 작업용, 이것은 사외로 나가는 것이다.
    ★ 만들다가 검사에 걸리면 파일을 내주지 않는다.
    """

    if excel_path is None or not Path(excel_path).exists():
        return

    st.divider()
    st.markdown("**회사 밖으로 보낼 때**")
    st.caption("영상 링크·아이디·댓글 작성자 이름을 지운 판본을 만듭니다. 댓글 내용은 그대로 남습니다.")
    # ★ 두 버튼이 만드는 것이 다른데 화면에 그 말이 없었다 (sky 2026-08-20).
    #   받는 사람이 2차 판독 결과까지 들었다고 생각할 수 있다
    # ★ 자리마다 만들어지는 것이 다르다. 그 말을 부르는 쪽에서 준다
    st.caption(
        note
        or (
            "★ 2차 판독 결과(수정로그·분리제안·구조적결함·기준서개정후보)는 들어 있지 않습니다. "
            "그쪽은 2차 판독을 돌려야 나오며 대시보드가 만드는 산출물이 아닙니다."
        )
    )

    source = Path(excel_path)
    state_key = f"dashboard60_release_bytes::{source}"
    if st.button(f"{prefix}안전한 판본 만들기", key=f"make_release::{source}", width="stretch"):
        try:
            payload, counts = build_release_workbook(source)
        except ReleaseCheckFailed as exc:
            st.session_state.pop(state_key, None)
            st.error("다 지워졌는지 확인이 안 돼서 파일을 만들지 않았습니다.\n\n" + str(exc))
        except Exception as exc:  # noqa: BLE001
            st.session_state.pop(state_key, None)
            st.error(f"만들지 못했습니다: {exc}")
        else:
            st.session_state[state_key] = (payload, counts)

    stored = st.session_state.get(state_key)
    if stored:
        payload, counts = stored
        st.success(
            f"다 지웠는지 확인했습니다 · 작성자 이름 {counts['사용자명']:,}곳 · "
            f"메일 {counts['메일']:,}곳 · 링크 {counts['링크']:,}곳"
        )
        st.download_button(
            f"{prefix}안전한 판본 내려받기",
            data=payload,
            file_name=release_filename(source),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_release::{source}",
            width="stretch",
        )


def _mark_complete_if_needed(state: dict[str, Any], dataset_session_key: str) -> None:
    out_dir = Path(state.get("out_dir", ""))
    dataset_path = out_dir / "voc_dashboard_dataset.csv"
    summary = _read_progress(out_dir)
    process = state.get("process")
    returncode = process.poll() if process is not None else None

    if summary.status == "completed" and dataset_path.exists():
        if summary.output_rows <= 0:
            if not state.get("empty_logged"):
                elapsed = max(0.0, time.time() - float(state.get("started_monotonic", time.time())))
                _append_run_log(
                    {
                        "status": "completed_empty",
                        "run_id": state.get("run_id", ""),
                        "out_dir": str(out_dir),
                        "dataset_path": str(dataset_path),
                        "elapsed_seconds": round(elapsed, 1),
                        "input_rows": summary.input_rows,
                        "output_rows": summary.output_rows,
                        "source_type": state.get("source_type", ""),
                        "message": "No rows were produced; dashboard dataset path was not changed.",
                    }
                )
                state["empty_logged"] = True
            state["status"] = "completed_empty"
            state["empty_result_message"] = (
                "입력한 조건을 만족하는 분석 결과가 0건입니다. "
                "기존 대시보드 데이터는 유지했습니다. AND 키워드를 줄이거나 OR로 변경해 보세요."
            )
            state["dataset_path_applied"] = ""
            _persist_run_state(state)
            return
        bundle_path = _ensure_export_bundle(dataset_path)
        if bundle_path is not None:
            state["export_bundle_path"] = str(bundle_path)
        if not state.get("completion_logged"):
            elapsed = max(0.0, time.time() - float(state.get("started_monotonic", time.time())))
            _append_run_log(
                {
                    "status": "completed",
                    "run_id": state.get("run_id", ""),
                    "out_dir": str(out_dir),
                    "dataset_path": str(dataset_path),
                    "elapsed_seconds": round(elapsed, 1),
                    "input_rows": summary.input_rows,
                    "output_rows": summary.output_rows,
                    "source_type": state.get("source_type", ""),
                }
            )
            state["completion_logged"] = True
        state["status"] = "completed"
        _persist_run_state(state)
        if st.session_state.get(dataset_session_key) != str(dataset_path):
            st.session_state[dataset_session_key] = str(dataset_path)
            state["dataset_path_applied"] = str(dataset_path)
            if not state.get("rerun_after_dataset_apply"):
                state["rerun_after_dataset_apply"] = True
                st.rerun()
    elif returncode is not None and returncode != 0:
        if not state.get("failure_logged"):
            _append_run_log(
                {
                    "status": "failed",
                    "run_id": state.get("run_id", ""),
                    "out_dir": str(out_dir),
                    "returncode": returncode,
                    "last_event": summary.last_event,
                    "source_type": state.get("source_type", ""),
                }
            )
            state["failure_logged"] = True
        state["status"] = "failed"
        _persist_run_state(state)
    elif state.get("status") == "running" and process is None and not _pid_is_running(state.get("pid")):
        state["status"] = "interrupted"
        _persist_run_state(state)


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


def _render_run_history_panel(*, dataset_session_key: str) -> None:
    records = scan_run_history(RUN_ROOT)
    # ★ 접이식 제목이 이미 같은 말이라 소제목을 뺐다 (sky 2026-08-20)
    if not records:
        st.info("이 서버에 저장된 분석 결과가 아직 없습니다. 「새로 분석 돌리기」 로 먼저 만들어 주세요.")
        return

    table = _history_display_table(records)
    st.caption(
        "이 서버에 이미 저장된 분석 결과 목록입니다. 파일을 올릴 필요 없이 골라서 바로 봅니다."
    )
    st.dataframe(table, width="stretch", hide_index=True)

    label_to_record = {_history_select_label(record): record for record in records}
    completed_labels = [
        _history_select_label(record)
        for record in records
        if record.dataset_path.exists() and record.status in {"completed", "completed_empty", "unknown"}
    ]
    if completed_labels:
        selected_label = st.selectbox("불러올 실행 하나 고르기", completed_labels, index=0)
        selected_record = label_to_record[selected_label]
        selected_artifacts = _ensure_history_artifacts(selected_record.dataset_path)
        cols = st.columns([1, 2])
        with cols[0]:
            if st.button("이 실행으로 화면 바꾸기", type="primary", width="stretch"):
                st.session_state[dataset_session_key] = str(selected_record.dataset_path)
                st.success(f"`{selected_record.run_id}` 로 바뀌었습니다. 위 네 개 탭에서 바로 볼 수 있습니다.")
                st.rerun()
        with cols[1]:
            with st.expander("이 실행의 산출물 내려받기", expanded=False):
                _download_artifact_set(
                    selected_artifacts,
                    prefix="선택 실행 ",
                    release_note=(
                        "여기서는 분석 결과만 담깁니다. 2차 판독으로 고친 내역은 "
                        "들어가지 않습니다."
                    ),
                )

    st.markdown("##### 여러 실행을 합쳐서 보기")
    merge_labels = st.multiselect(
        "합칠 실행 고르기 (2개 이상)",
        completed_labels,
        default=[],
        placeholder="고르지 않음",
        help="고른 결과를 한 표로 합칩니다. 각 행에 어느 실행에서 왔는지(source_run)가 붙습니다.",
    )
    deduplicate = st.checkbox("같은 댓글이 여러 실행에 있으면 하나만 남기기", value=True)
    selected_records = [label_to_record[label] for label in merge_labels]
    schema_versions = sorted({record.schema_version for record in selected_records if record.schema_version})
    mixed_schema = len(schema_versions) > 1
    if mixed_schema:
        st.warning("고른 실행들의 스키마 판이 서로 다릅니다: " + ", ".join(schema_versions))
        st.checkbox(
            "스키마 판이 달라도 합치겠습니다. 칸이 어긋날 수 있음을 확인했습니다.",
            key=SESSION_HISTORY_CONFIRM_MIXED_KEY,
            value=False,
        )
    else:
        st.session_state[SESSION_HISTORY_CONFIRM_MIXED_KEY] = False

    can_merge = len(selected_records) >= 2 and (
        not mixed_schema or bool(st.session_state.get(SESSION_HISTORY_CONFIRM_MIXED_KEY))
    )
    # ★ 잠긴 이유를 적는다 (sky 2026-08-20). 판정식은 그대로 두고 값만 읽는다.
    #   전에는 왜 안 눌리는지 화면에 없어 고장 난 것처럼 보였다.
    if not can_merge:
        if len(selected_records) < 2:
            st.caption(
                f"합치려면 실행을 2개 이상 골라야 합니다 (지금 {len(selected_records)}개)."
            )
        else:
            st.caption("스키마가 서로 다릅니다. 위 확인 상자를 체크해야 합칠 수 있습니다.")
    if st.button("고른 실행 합쳐서 화면 바꾸기", width="stretch", disabled=not can_merge):
        merged = merge_run_datasets(selected_records, deduplicate=deduplicate)
        run_id = f"history_merge_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir = RUN_ROOT / run_id
        dataset_path = write_merged_run(
            records=selected_records,
            merged=merged,
            out_dir=out_dir,
            deduplicate=deduplicate,
        )
        bundle_path = _ensure_export_bundle(dataset_path)
        _append_run_log(
            {
                "status": "completed",
                "run_id": run_id,
                "out_dir": str(out_dir),
                "dataset_path": str(dataset_path),
                "export_bundle_path": str(bundle_path or ""),
                "source_type": "history_merge",
                "input_rows": sum(record.row_count for record in selected_records),
                "output_rows": int(len(merged)),
                "merged_runs": [record.run_id for record in selected_records],
                "deduplicate": bool(deduplicate),
            }
        )
        st.session_state[dataset_session_key] = str(dataset_path)
        st.success(f"실행 {len(selected_records)}개를 합쳐 `{run_id}` 로 저장하고 화면에 반영했습니다.")
        st.rerun()

    cleanup_candidates = [record for record in records if record.cleanup_candidate]
    with st.expander("오래된 실행 목록 (자동으로 지우지 않습니다)", expanded=False):
        if cleanup_candidates:
            st.caption("30일 이상 지난 실행입니다. 목록만 보여줄 뿐 자동으로 지우지 않습니다.")
            st.dataframe(
                history_table(cleanup_candidates)[["created_at", "rows", "source_type", "run_id", "dataset_path"]],
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("30일 이상 지난 실행이 없습니다.")


def _render_analyzed_result_upload(*, dataset_session_key: str) -> None:
    # ★ 접이식 제목이 이미 같은 말이라 소제목을 뺐다 (sky 2026-08-20)
    st.caption(
        "이미 분석이 끝난 파일을 올립니다. 다시 분석하지 않고 바로 화면에 띄웁니다. "
        "분석 전 원본 파일은 여기가 아니라 「새로 분석 돌리기」 로 가야 합니다."
    )
    uploaded = st.file_uploader(
        "분석이 끝난 CSV / Excel",
        type=["csv", "xlsx", "xls"],
        key="dashboard60_analyzed_result_uploader",
        help="분석 전 원본이 아니라 분석 결과 파일입니다. 헷갈리면 파일 이름에 dashboard_dataset 이 있는지 보세요.",
    )
    if uploaded is None:
        return

    upload_bytes = uploaded.getvalue()
    upload_sig = f"{getattr(uploaded, 'name', '')}:{len(upload_bytes)}"
    if st.session_state.get(SESSION_ANALYZED_UPLOAD_SIG_KEY) != upload_sig:
        dataset_path, error, metadata = _write_uploaded_analyzed_result(uploaded)
        st.session_state[SESSION_ANALYZED_UPLOAD_SIG_KEY] = upload_sig
        st.session_state[SESSION_ANALYZED_UPLOAD_PATH_KEY] = str(dataset_path or "")
        st.session_state["dashboard60_analyzed_upload_error"] = error
        st.session_state["dashboard60_analyzed_upload_rows"] = int(metadata.get("output_rows") or 0)

    error = _safe_text(st.session_state.get("dashboard60_analyzed_upload_error"))
    dataset_path_text = _safe_text(st.session_state.get(SESSION_ANALYZED_UPLOAD_PATH_KEY))
    if error:
        st.error(error)
        return
    if not dataset_path_text:
        st.warning("업로드 파일을 아직 분석 완료본으로 확인하지 못했습니다.")
        return

    st.success(
        f"분석이 끝난 파일이 맞습니다 · {int(st.session_state.get('dashboard60_analyzed_upload_rows') or 0):,}행"
    )
    # ★ 올리기만 하면 화면이 안 바뀐다. 한 번 더 눌러야 한다는 것을 말해 준다
    st.caption("아직 화면은 바뀌지 않았습니다. 아래 버튼을 눌러야 이 파일로 바뀝니다.")
    dataset_path = Path(dataset_path_text)
    if st.button("이 파일로 화면 바꾸기", type="primary", width="stretch"):
        st.session_state[dataset_session_key] = str(dataset_path)
        st.success("이 파일로 바뀌었습니다. 위 네 개 탭에서 바로 볼 수 있습니다.")
        st.rerun()
    with st.expander("이 파일의 산출물 내려받기", expanded=False):
        upload_artifacts = _ensure_history_artifacts(dataset_path)
        # ★ 올린 파일 그대로 돌려준다 (sky 2026-08-20).
        #   전에는 대시보드가 CSV 로 다시 만든 6시트짜리를 줬다 —
        #   12시트를 올려도 6시트가 돌아왔다.
        uploaded_source = _uploaded_source_path(dataset_path)
        if uploaded_source is not None:
            upload_artifacts["excel"] = uploaded_source
        _download_artifact_set(
            upload_artifacts,
            prefix="업로드 결과 ",
            # ★ 올린 파일 그 자체를 원본으로 삼는다. 12시트를 올리면 12시트 기준으로,
            #   6시트를 올리면 6시트 기준으로 만들어진다
            release_source=uploaded_source,
            release_note=(
                "올리신 파일에 들어 있는 것을 그대로 씁니다. "
                "2차 판독으로 고친 내역이 들어 있다면 그것도 함께 담깁니다."
            ),
        )


def _render_exact_reanalysis_panel(*, dataset_session_key: str, run_is_active: bool) -> None:
    st.caption(
        "예전 결과 파일에서 「댓글 원문」 만 꺼내 지금 엔진으로 다시 판정합니다. "
        "예전 판정값(주제·감정·원인)은 쓰지 않으므로, 엔진이 바뀐 뒤 같은 댓글을 다시 볼 때 씁니다. "
        "OpenAI 를 부르므로 시간과 비용이 듭니다."
    )
    uploaded = st.file_uploader(
        "다시 분석할 예전 결과 파일",
        type=["csv", "xlsx", "xls"],
        key="dashboard60_exact_reanalysis_upload_widget",
        help="댓글 원문이 들어 있는 결과 파일이어야 합니다(Excel 은 raw_voc 시트).",
    )
    if uploaded is None:
        return

    payload = uploaded.getvalue()
    signature = f"{getattr(uploaded, 'name', '')}:{len(payload)}"
    if st.session_state.get(SESSION_REANALYSIS_UPLOAD_SIG_KEY) != signature:
        uploaded_path = _save_uploaded_file(uploaded)
        st.session_state[SESSION_REANALYSIS_UPLOAD_SIG_KEY] = signature
        st.session_state[SESSION_REANALYSIS_UPLOAD_PATH_KEY] = str(uploaded_path)
    else:
        uploaded_path = Path(st.session_state.get(SESSION_REANALYSIS_UPLOAD_PATH_KEY, ""))

    try:
        analyzed_frame = _read_analyzed_result_file(uploaded_path)
        ok, message = _validate_analyzed_result_frame(analyzed_frame)
        if not ok:
            st.error(message)
            return
        source_frame = _prepare_exact_reanalysis_frame(analyzed_frame)
    except Exception as exc:
        st.error(f"재분석 원문을 준비하지 못했습니다: {type(exc).__name__}: {exc}")
        return

    st.success(f"Atomic {len(analyzed_frame):,}행에서 원문 댓글 {len(source_frame):,}건을 복원했습니다.")
    st.caption("예상 OpenAI 분석 대상은 원문 댓글 수와 비슷하며 atomic 분리 결과에 따라 최종 행 수는 늘어날 수 있습니다.")
    # ★ 이미 재분석 상자 안이라 「재분석」 접두어는 군더더기다 (sky 2026-08-20)
    batch_size = int(
        st.number_input(
            "한 번에 묶어 처리할 건수",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
            help="이 건수마다 중간 저장합니다.",
        )
    )
    timeout_seconds = int(
        st.number_input(
            "한 묶음 최대 대기 시간(초)", min_value=30, max_value=300, value=120, step=10
        )
    )
    model = st.text_input("모델", value="", placeholder="비워 두면 기본값", help="보통 비워 둡니다.")
    run_suffix = st.text_input(
        "실행 이름",
        value="dashboard60_exact_reanalysis",
        help="저장될 폴더 이름 앞부분입니다. 뒤에 날짜·시각이 자동으로 붙습니다.",
    )
    confirmed = st.checkbox(
        f"원문 {len(source_frame):,}건을 OpenAI API로 다시 분석하는 비용을 확인했습니다.",
        value=False,
        key="dashboard60_exact_reanalysis_confirm",
    )
    disabled = run_is_active or source_frame.empty or not confirmed or not _resolve_openai_api_key()
    if st.button("다시 분석 시작", type="primary", width="stretch", disabled=disabled):
        source_path = _save_exact_reanalysis_source(source_frame, source_name=getattr(uploaded, "name", "result"))
        run_id = f"{_safe_slug(run_suffix)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        out_dir = RUN_ROOT / run_id
        command = _build_command(
            source_type="raw",
            source_path=source_path,
            out_dir=out_dir,
            run_id=run_id,
            model=model,
            limit=0,
            batch_size=batch_size,
            timeout_seconds=timeout_seconds,
            sample_across_videos=False,
        )
        process = _start_subprocess(command, out_dir)
        state = {
            "status": "running",
            "run_id": run_id,
            "out_dir": str(out_dir),
            "source_type": "exact_reanalysis",
            "source_path": str(source_path),
            "command": command,
            "pid": process.pid,
            "process": process,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "started_monotonic": time.time(),
            "started_by": "dashboard60_exact_reanalysis",
            "dataset_session_key": dataset_session_key,
        }
        st.session_state[SESSION_RUN_KEY] = state
        _persist_run_state(state)
        _append_run_log(
            {
                "status": "started",
                "run_id": run_id,
                "out_dir": str(out_dir),
                "source_type": "exact_reanalysis",
                "source_path": str(source_path),
                "pid": process.pid,
                "input_rows": len(source_frame),
                "batch_size": batch_size,
            }
        )
        st.success(f"원문 재분석을 백그라운드로 시작했습니다. PID={process.pid}")
        st.rerun()


def render_analysis_runner(*, dataset_session_key: str) -> None:
    """Render first-pass execution and historical run reuse controls."""

    active_state = st.session_state.get(SESSION_RUN_KEY)
    if not isinstance(active_state, dict):
        recoverable_state = _find_recoverable_run()
        if isinstance(recoverable_state, dict):
            active_state = recoverable_state
            st.session_state[SESSION_RUN_KEY] = active_state
    run_is_active = False

    # ★ E — 지금 무엇을 보고 있는지 (sky 2026-08-20).
    #   전에는 「새로 분석 돌리기」 를 열어야만 보였다. 상자 맨 위로 꺼낸다.
    current_dataset = _safe_text(str(st.session_state.get(dataset_session_key, "")))
    if current_dataset:
        # ★ 파일 이름은 어느 실행이든 voc_dashboard_dataset.csv 로 똑같다.
        #   실행을 가르는 것은 상위 폴더 이름이다 (sky 2026-08-20)
        _path = Path(current_dataset)
        st.caption(f"지금 보는 실행 · **{_path.parent.name or _path.name}**")
    else:
        st.caption("아직 아무 자료도 열지 않았습니다.")
    # ★ 넷 중 둘은 OpenAI 를 불러 시간과 비용이 들고, 둘은 즉시 열린다.
    #   그 갈림이 화면에 없어 넷이 똑같아 보였다. 아이콘으로 가른다.
    #   ★ 순서는 바꾸지 않았으므로(A 제외) 아이콘이 엇갈려 놓인다.
    #     그래서 묶음 소제목 대신 범례 한 줄을 둔다 — 소제목은 틀린 말이 된다.
    st.caption("⏱ 시간과 비용이 드는 작업  ·  📂 바로 열리는 작업")

    # ★ 이름·아이콘만 바꾼다. 호출 순서와 인자는 그대로다 (sky 2026-08-20).
    #   ⏱ 는 「오래 걸리고 비용이 든다」 는 표시다. 📂 는 즉시·무료.
    with st.expander("새로 분석 돌리기", expanded=False, icon="⏱"):
        st.caption(
            "댓글을 새로 모으거나 아직 분석하지 않은 파일을 분석합니다. "
            "OpenAI 를 부르므로 시간과 비용이 듭니다 — 이미 분석한 것을 다시 보려면 "
            "위의 「저장된 실행에서 고르기」 나 「결과 파일 올려서 보기」 를 쓰세요."
        )
        if not _resolve_openai_api_key():
            st.warning("OPENAI_API_KEY가 감지되지 않았습니다. Streamlit Secrets 또는 환경변수에 추가가 필요합니다.")

        if isinstance(active_state, dict):
            _mark_complete_if_needed(active_state, dataset_session_key)
            _render_running_or_completed_state(active_state, dataset_session_key)
            run_is_active = active_state.get("status") == "running"

            if active_state.get("status") in {"interrupted", "cancelled"}:
                summary = _read_progress(Path(active_state.get("out_dir", "")))
                st.warning(
                    "브라우저 세션과 분리된 분석을 발견했습니다. 이미 완료된 batch는 보존되어 있습니다."
                )
                st.caption(
                    f"보존 batch {summary.completed_batches}/{summary.total_batches or '?'} · "
                    "재개하면 완료 batch는 건너뛰고 남은 batch부터 실행합니다."
                )
                if st.button("마지막 체크포인트부터 재개", width="stretch"):
                    command = _resume_command(list(active_state.get("command") or []))
                    process = _start_subprocess(command, Path(active_state["out_dir"]))
                    active_state.update(
                        {
                            "status": "running",
                            "command": command,
                            "pid": process.pid,
                            "process": process,
                            "resumed_at": datetime.now(timezone.utc).isoformat(),
                            "started_monotonic": time.time(),
                        }
                    )
                    _persist_run_state(active_state)
                    st.session_state[SESSION_RUN_KEY] = active_state
                    st.success(f"체크포인트 재개를 시작했습니다. PID={process.pid}")
                    st.rerun()
                if st.button("이 복구 알림 숨기기", width="stretch"):
                    active_state["recovery_dismissed"] = True
                    _persist_run_state(active_state)
                    st.session_state.pop(SESSION_RUN_KEY, None)
                    st.rerun()

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

        if st.button("분석 시작", type="primary", width="stretch", disabled=disabled):
            if source_type != "youtube":
                if source_path is None:
                    st.warning("입력 경로 또는 업로드 파일을 먼저 지정해 주세요.")
                    return
                if not source_path.exists():
                    st.error(f"입력 경로를 찾지 못했습니다: {source_path}")
                    return
            run_id = f"{_safe_slug(run_suffix)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            out_dir = RUN_ROOT / run_id
            command = _build_command(
                source_type=source_type,
                source_path=source_path,
                out_dir=out_dir,
                run_id=run_id,
                model=model,
                limit=int(limit),
                batch_size=int(batch_size),
                timeout_seconds=int(timeout_seconds),
                sample_across_videos=sample_across_videos,
                youtube_keyword="\n".join(youtube_params.get("keywords", [])),
                youtube_keywords=list(youtube_params.get("keywords", [])),
                youtube_keyword_mode=_safe_text(youtube_params.get("keyword_mode", "OR")) or "OR",
                youtube_and_min_keyword_matches=youtube_params.get("and_min_keyword_matches"),
                youtube_region=_safe_text(youtube_params.get("region", "KR")) or "KR",
                youtube_language=_safe_text(youtube_params.get("language", "ko")) or "ko",
                youtube_max_videos=int(youtube_params.get("max_videos", 2)),
                youtube_comments_per_video=int(youtube_params.get("comments_per_video", 10)),
                youtube_include_replies=bool(youtube_params.get("include_replies", True)),
                youtube_channel_id=_safe_text(youtube_params.get("channel_id", "")),
                youtube_published_after=_safe_text(youtube_params.get("published_after", "")),
                youtube_published_before=_safe_text(youtube_params.get("published_before", "")),
            )
            process = _start_subprocess(command, out_dir)
            state = {
                "status": "running",
                "run_id": run_id,
                "out_dir": str(out_dir),
                "source_type": source_type,
                "source_path": str(source_path or ", ".join(youtube_params.get("keywords", []))),
                "command": command,
                "pid": process.pid,
                "process": process,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "started_monotonic": time.time(),
            }
            st.session_state[SESSION_RUN_KEY] = state
            _persist_run_state(state)
            _append_run_log(
                {
                    "status": "started",
                    "run_id": run_id,
                    "out_dir": str(out_dir),
                    "source_type": source_type,
                    "source_path": str(source_path or ", ".join(youtube_params.get("keywords", []))),
                    "pid": process.pid,
                    "limit": int(limit),
                    "batch_size": int(batch_size),
                }
            )
            st.success(f"실분석 실행을 백그라운드로 시작했습니다. PID={process.pid}")
            st.rerun()

    with st.expander("결과 파일 올려서 보기", expanded=False, icon="📂"):
        _render_analyzed_result_upload(dataset_session_key=dataset_session_key)

    with st.expander("같은 원문으로 다시 분석", expanded=False, icon="⏱"):
        _render_exact_reanalysis_panel(dataset_session_key=dataset_session_key, run_is_active=run_is_active)

    with st.expander("저장된 실행에서 고르기", expanded=False, icon="📂"):
        _render_run_history_panel(dataset_session_key=dataset_session_key)


def _render_running_or_completed_state(state: dict[str, Any], dataset_session_key: str) -> None:
    out_dir = Path(state.get("out_dir", ""))
    summary = _read_progress(out_dir)
    dataset_path = out_dir / "voc_dashboard_dataset.csv"
    jsonl_path = out_dir / "voc_dashboard_dataset.jsonl"
    metadata_path = out_dir / "metadata.json"
    bundle_path = out_dir / BUNDLE_FILENAME
    progress_path = out_dir / "progress.jsonl"
    stdout_path = out_dir / "_runner_stdout.log"
    stderr_path = out_dir / "_runner_stderr.log"

    st.markdown(f"**최근 실행** `{state.get('run_id', '')}` · PID `{state.get('pid', '')}`")
    if summary.total_batches:
        st.progress(min(1.0, summary.completed_batches / max(1, summary.total_batches)))
        st.caption(
            f"batch {summary.completed_batches}/{summary.total_batches} · "
            f"입력 {summary.input_rows:,} · 산출 {summary.output_rows:,}"
        )
    elif state.get("status") == "running":
        stage = _safe_text(summary.last_event.get("stage")) or "준비"
        status = _safe_text(summary.last_event.get("status")) or "started"
        st.info(f"진행 중입니다: {stage}/{status}. 분석 batch가 시작되면 progress bar가 표시됩니다.")

    if state.get("status") == "completed":
        st.success("실분석 실행 완료 — 현재 세션 데이터셋으로 즉시 반영했습니다.")
        st.caption(f"현재 데이터셋: `{st.session_state.get(dataset_session_key, '')}`")
    elif state.get("status") == "completed_empty":
        st.warning(
            state.get(
                "empty_result_message",
                "분석 결과가 0건입니다. 기존 대시보드 데이터는 유지했습니다.",
            )
        )
        st.caption(f"유지 중인 데이터셋: `{st.session_state.get(dataset_session_key, '')}`")
    elif state.get("status") == "failed":
        st.error("실분석 실행 실패 — stderr/log를 확인해 주세요.")
    elif state.get("status") == "interrupted":
        st.warning("실행 프로세스는 종료됐지만 완료된 batch와 중간 산출물은 보존되어 있습니다.")
    elif state.get("status") == "cancelled":
        st.warning("분석이 취소되었습니다. 완료된 batch와 중간 산출물은 보존되어 있습니다.")
    else:
        st.info("실행 중입니다. 화면은 멈추지 않으며, 새로고침/상호작용 시 progress.jsonl을 다시 읽습니다.")
        cancel_key = f"dashboard60_cancel_confirm_{_safe_slug(_safe_text(state.get('run_id')))}"
        st.checkbox(
            "분석 취소 확인",
            key=cancel_key,
            help="실행 중인 프로세스만 종료하고 이미 완료된 batch 산출물은 삭제하지 않습니다.",
        )
        if st.button(
            "분석 취소",
            width="stretch",
            disabled=not bool(st.session_state.get(cancel_key)),
        ):
            ok, message = _cancel_run_state(state)
            st.session_state[SESSION_RUN_KEY] = state
            if ok:
                st.warning("분석이 취소되었습니다. 완료된 batch와 중간 산출물은 보존되어 있습니다.")
            else:
                st.error(f"분석 취소에 실패했습니다: {message}")
            st.rerun()
        auto_refresh = st.checkbox("실행 중 5초마다 자동 새로고침", value=True, key="dashboard60_analysis_auto_refresh")
        if st.button("진행 상태 새로고침", width="stretch"):
            st.rerun()
        if auto_refresh:
            if st_autorefresh is not None:
                st_autorefresh(
                    interval=AUTO_REFRESH_INTERVAL_MS,
                    key="dashboard60_analysis_autorefresh_timer",
                )
            else:
                st.caption("자동 새로고침 컴포넌트를 불러오지 못했습니다. 수동 새로고침을 사용해 주세요.")

    with st.expander("실행 로그/다운로드", expanded=False):
        _download_file(
            "전체 결과 Excel 다운로드(6-Sheet)",
            bundle_path,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        for label, path, mime in (
            ("CSV 다운로드", dataset_path, "text/csv"),
            ("JSONL 다운로드", jsonl_path, "application/jsonl"),
            ("metadata 다운로드", metadata_path, "application/json"),
            ("progress 다운로드", progress_path, "application/jsonl"),
            ("stdout 로그", stdout_path, "text/plain"),
            ("stderr 로그", stderr_path, "text/plain"),
        ):
            _download_file(label, path, mime=mime)
