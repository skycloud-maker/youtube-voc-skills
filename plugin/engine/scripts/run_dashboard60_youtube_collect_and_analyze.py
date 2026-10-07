"""Collect YouTube comments with the legacy pipeline, then build dashboard60 CSV.

This wrapper is used by ``src.dashboard60.analysis_runner`` for the
"YouTube에서 직접 수집" input mode.  It deliberately reuses the existing
collection stack (``src.cli.run_pipeline`` / ``YoutubeClient`` /
``VideoSearchCollector`` / ``CommentsCollector``) and then hands the resulting
``data/processed/<run_id>`` directory to ``scripts/run_voc_rebuild_dashboard.py``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api.quota import YOUTUBE_QUOTA_COSTS, estimate_quota_usage  # noqa: E402
from src.cli import build_parser as build_legacy_parser  # noqa: E402
from src.cli import run_pipeline  # noqa: E402
from src.voc_rebuild.engine import DEFAULT_LLM_CONCURRENCY  # noqa: E402

AND_CANDIDATE_MULTIPLIER = 5
AND_CANDIDATE_MIN = 200
AND_CANDIDATE_CAP = 300


def _write_progress(out_dir: Path, event: dict[str, Any]) -> None:
    payload = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    progress_path = out_dir / "progress.jsonl"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    with progress_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _safe_count_parquet(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(len(pd.read_parquet(path)))
    except Exception:
        return 0


def _safe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _estimate_quota_for_keywords(
    *,
    max_videos: int,
    comments_per_video: int,
    include_replies: bool,
    keyword_count: int,
    keyword_mode: str,
    and_min_keyword_matches: int | None = None,
) -> dict[str, int]:
    keyword_count = max(1, int(keyword_count or 1))
    mode = str(keyword_mode or "OR").upper()
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


def _build_legacy_args(args: argparse.Namespace) -> argparse.Namespace:
    legacy_parser = build_legacy_parser()
    legacy_tokens = [
        "run",
        "--keyword",
        args.keyword,
        "--max-videos",
        str(args.max_videos),
        "--comments-per-video",
        str(args.comments_per_video),
        "--comments-order",
        args.comments_order,
        "--language",
        args.language,
        "--region",
        args.region,
        "--include-replies",
        "true" if args.include_replies else "false",
        "--refresh-existing",
        "false",
        "--output-prefix",
        args.run_id,
        "--run-id",
        args.run_id,
    ]
    if args.keywords:
        legacy_tokens.extend(["--keywords", *args.keywords])
    legacy_tokens.extend(["--keyword-mode", args.keyword_mode])
    if args.and_min_keyword_matches is not None:
        legacy_tokens.extend(["--and-min-keyword-matches", str(args.and_min_keyword_matches)])
    if args.channel_id:
        legacy_tokens.extend(["--channel-id", args.channel_id])
    if args.published_after:
        legacy_tokens.extend(["--published-after", args.published_after])
    if args.published_before:
        legacy_tokens.extend(["--published-before", args.published_before])
    return legacy_parser.parse_args(legacy_tokens)


def _run_dashboard_builder(args: argparse.Namespace, processed_run_dir: Path) -> None:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_voc_rebuild_dashboard.py"),
        "--processed-run-dir",
        str(processed_run_dir),
        "--out-dir",
        str(args.out_dir),
        "--run-id",
        args.run_id,
        "--batch-size",
        str(args.batch_size),
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--llm-concurrency",
        str(args.llm_concurrency),
    ]
    if args.model:
        command.extend(["--model", args.model])
    if args.limit is not None and args.limit > 0:
        command.extend(["--limit", str(args.limit)])
    if args.resume:
        command.append("--resume")
    completed = subprocess.run(command, cwd=str(ROOT), text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"dashboard60 analysis failed with exit code {completed.returncode}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--keywords", nargs="*", default=[])
    parser.add_argument("--keyword-mode", choices=["AND", "OR"], default="OR")
    parser.add_argument("--and-min-keyword-matches", type=int, default=None)
    parser.add_argument("--region", default="KR")
    parser.add_argument("--language", default="ko")
    parser.add_argument("--max-videos", type=int, default=2)
    parser.add_argument("--comments-per-video", type=int, default=10)
    parser.add_argument("--comments-order", choices=["relevance", "time"], default="relevance")
    parser.add_argument("--include-replies", choices=["true", "false"], default="true")
    parser.add_argument("--channel-id", default="")
    parser.add_argument("--published-after", default="")
    parser.add_argument("--published-before", default="")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--llm-concurrency", type=int, default=DEFAULT_LLM_CONCURRENCY)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument(
        "--sample-across-videos",
        action="store_true",
        help="Deprecated/no-op: dashboard60 quality sampling is always applied.",
    )
    parser.add_argument("--resume", action="store_true", help="Reuse collected parquet and completed analysis batches.")
    return parser


def run(args: argparse.Namespace) -> Path:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.include_replies = str(args.include_replies).lower() in {"1", "true", "yes", "y"}
    quota = _estimate_quota_for_keywords(
        max_videos=args.max_videos,
        comments_per_video=args.comments_per_video,
        include_replies=args.include_replies,
        keyword_count=len([args.keyword, *args.keywords]),
        keyword_mode=args.keyword_mode,
        and_min_keyword_matches=args.and_min_keyword_matches,
    )

    _write_progress(
        args.out_dir,
        {
            "stage": "youtube_collection",
            "status": "started",
            "keyword": args.keyword,
            "keywords": [args.keyword, *args.keywords],
            "keyword_mode": args.keyword_mode,
            "and_min_keyword_matches": args.and_min_keyword_matches,
            "max_videos": args.max_videos,
            "comments_per_video": args.comments_per_video,
            "region": args.region,
            "language": args.language,
            "published_after": args.published_after,
            "published_before": args.published_before,
            "estimated_quota_units": quota["total_units"],
        },
    )

    processed_run_dir = ROOT / "data" / "processed" / args.run_id
    comments_path = processed_run_dir / "comments_normalized.parquet"
    manifest_path = processed_run_dir / "run_manifest.json"
    if args.resume and comments_path.exists():
        _write_progress(
            args.out_dir,
            {
                "stage": "youtube_collection",
                "status": "reused",
                "processed_run_dir": str(processed_run_dir),
                "reason": "resume_existing_processed_run",
            },
        )
    else:
        try:
            result = run_pipeline(_build_legacy_args(args))
        except Exception as exc:
            _write_progress(
                args.out_dir,
                {
                    "stage": "youtube_collection",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            raise
        manifest_path = Path(result.get("manifest_path", ""))
        processed_run_dir = manifest_path.parent if manifest_path.exists() else processed_run_dir
    videos_count = _safe_count_parquet(processed_run_dir / "videos_normalized.parquet")
    comments_count = _safe_count_parquet(processed_run_dir / "comments_normalized.parquet")
    manifest = _safe_load_json(processed_run_dir / "run_manifest.json")

    _write_progress(
        args.out_dir,
        {
            "stage": "youtube_collection",
            "status": "completed",
            "processed_run_dir": str(processed_run_dir),
            "videos_collected": videos_count,
            "comments_collected": comments_count,
            "actual_api_calls": manifest.get("api_calls_json", {}),
        },
    )

    _write_progress(args.out_dir, {"stage": "dashboard_analysis", "status": "started", "processed_run_dir": str(processed_run_dir)})
    try:
        _run_dashboard_builder(args, processed_run_dir)
    except Exception as exc:
        _write_progress(
            args.out_dir,
            {
                "stage": "dashboard_analysis",
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise

    metadata_path = args.out_dir / "metadata.json"
    metadata = _safe_load_json(metadata_path)
    metadata["youtube_collection"] = {
        "keyword": args.keyword,
        "keywords": [args.keyword, *args.keywords],
        "keyword_mode": args.keyword_mode,
        "and_min_keyword_matches": args.and_min_keyword_matches,
        "region": args.region,
        "language": args.language,
        "published_after": args.published_after,
        "published_before": args.published_before,
        "max_videos": args.max_videos,
        "comments_per_video": args.comments_per_video,
        "include_replies": args.include_replies,
        "processed_run_dir": str(processed_run_dir),
        "videos_collected": videos_count,
        "comments_collected": comments_count,
        "estimated_quota": quota,
        "actual_api_calls": manifest.get("api_calls_json", {}),
    }
    _write_json(metadata_path, metadata)
    _write_progress(args.out_dir, {"stage": "dashboard_analysis", "status": "completed", "processed_run_dir": str(processed_run_dir)})
    return args.out_dir


if __name__ == "__main__":
    run(build_parser().parse_args())
