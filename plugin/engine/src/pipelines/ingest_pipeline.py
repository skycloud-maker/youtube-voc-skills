"""Ingestion pipeline orchestrating search and comment collection."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.collectors.comments_collector import CommentsCollector
from src.collectors.video_search import VideoSearchCollector
from src.models.schemas import RunConfig, RunManifest, utc_now_iso
from src.utils.io import ensure_dir, write_dataframe, write_json


class IngestPipeline:
    """Run search and raw comment collection with rerun safety."""

    AND_CANDIDATE_MULTIPLIER = 5
    AND_CANDIDATE_MIN = 200
    AND_CANDIDATE_CAP = 300

    def __init__(self, video_search: VideoSearchCollector, comments_collector: CommentsCollector, processed_dir: Path, logger: logging.Logger | None = None) -> None:
        self.video_search = video_search
        self.comments_collector = comments_collector
        self.processed_dir = ensure_dir(processed_dir)
        self.logger = logger or logging.getLogger(__name__)

    def run(self, config: RunConfig, manifest: RunManifest) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Path]:
        run_dir = ensure_dir(self.processed_dir / manifest.run_id)
        videos_path = run_dir / "videos_raw.parquet"
        comments_path = run_dir / "comments_raw.parquet"
        errors_path = run_dir / "errors.csv"
        manifest_path = run_dir / "run_manifest.json"

        search_keywords = [kw for kw in (config.keywords if config.keywords else [config.keyword]) if kw]
        keyword_mode = str(config.keyword_mode or "OR").upper()
        if keyword_mode == "AND" and len(search_keywords) > 1:
            all_videos = self._search_keyword_intersection(config, manifest, search_keywords)
        else:
            all_videos = self._search_keyword_union(config, manifest, search_keywords)
        videos = all_videos
        videos_df = pd.DataFrame(videos)
        comment_rows: list[dict] = []
        error_rows: list[dict] = []

        existing_comments = self._load_existing_comments(comments_path)
        collected_video_ids = set(existing_comments["video_id"].unique().tolist()) if not existing_comments.empty else set()

        for video in videos:
            video_id = video["video_id"]
            if video_id in collected_video_ids and not config.refresh_existing:
                self.logger.info("Skipping previously collected video", extra={"run_id": manifest.run_id, "video_id": video_id, "stage": "ingest"})
                continue
            rows, video_errors = self.comments_collector.collect_video_comments(
                run_id=manifest.run_id,
                video_id=video_id,
                comments_per_video=config.comments_per_video,
                include_replies=config.include_replies,
                comments_order=config.comments_order,
            )
            comment_rows.extend(rows)
            error_rows.extend(video_errors)

        comments_df = self._merge_comments(existing_comments, pd.DataFrame(comment_rows))
        comments_df = self._filter_comments_by_published_at(
            comments_df,
            published_after=config.comment_published_after,
            published_before=config.comment_published_before,
        )
        errors_df = pd.DataFrame(error_rows)

        manifest.finished_at = utc_now_iso()
        manifest.videos_collected = int(len(videos_df))
        manifest.comments_collected = int(len(comments_df))
        manifest.error_count = int(len(errors_df))
        manifest.failed_video_ids = errors_df["video_id"].dropna().astype(str).unique().tolist() if not errors_df.empty else []

        write_dataframe(videos_df, videos_path)
        final_comments_path = write_dataframe(comments_df, comments_path)
        if not errors_df.empty:
            write_dataframe(errors_df, errors_path)
        write_json(manifest_path, manifest.model_dump(mode="json"))
        self.logger.info("Ingestion stage completed", extra={"run_id": manifest.run_id, "stage": "ingest"})
        return videos_df, comments_df, errors_df, final_comments_path.parent

    def _search_keyword_union(self, config: RunConfig, manifest: RunManifest, search_keywords: list[str]) -> list[dict]:
        all_videos: list[dict] = []
        by_video_id: dict[str, dict] = {}
        for kw in search_keywords:
            kw_config = config.model_copy(update={"keyword": kw, "max_videos": max(1, int(config.max_videos or 1))})
            kw_results = self.video_search.search(manifest.run_id, kw_config)
            for video in kw_results:
                video_id = self._normalize_video_id(video.get("video_id"))
                if not video_id:
                    continue
                if video_id in by_video_id:
                    existing = by_video_id[video_id]
                    matched_keywords = list(existing.get("matched_keywords") or [])
                    if kw not in matched_keywords:
                        matched_keywords.append(kw)
                    existing["matched_keywords"] = matched_keywords
                    existing["matched_keyword"] = " OR ".join(matched_keywords)
                    existing["keyword_match_count"] = len(matched_keywords)
                    continue
                merged = dict(video)
                merged["video_id"] = video_id
                merged["keyword_match_mode"] = "OR"
                merged["matched_keyword"] = kw
                merged["matched_keywords"] = [kw]
                merged["keyword_match_count"] = 1
                by_video_id[video_id] = merged
                all_videos.append(merged)
            self.logger.info(
                "OR keyword '%s': %d videos (total unique: %d)",
                kw,
                len(kw_results),
                len(all_videos),
                extra={
                    "run_id": manifest.run_id,
                    "stage": "ingest",
                    "keyword": kw,
                    "keyword_match_mode": "OR",
                    "keyword_candidate_videos": len(kw_results),
                    "unique_videos": len(all_videos),
                    "per_keyword_limit": max(1, int(config.max_videos or 1)),
                },
            )
        return self._sort_videos_for_selection(all_videos)[: max(1, int(config.max_videos or 1))]

    @classmethod
    def _sort_videos_for_selection(cls, videos: list[dict]) -> list[dict]:
        return sorted(
            videos,
            key=lambda item: (
                bool(item.get("video_selection_excluded", False)),
                -float(item.get("selection_score") or 0.0),
                -cls._safe_int(item.get("comment_count")),
                cls._safe_int(item.get("search_rank"), default=999999),
                cls._normalize_video_id(item.get("video_id")),
            ),
        )

    def _search_keyword_intersection(self, config: RunConfig, manifest: RunManifest, search_keywords: list[str]) -> list[dict]:
        base_keyword = search_keywords[0]
        candidate_limit = self._and_candidate_limit(config.max_videos)
        min_keyword_matches = self._and_min_keyword_matches(search_keywords, config.and_min_keyword_matches)
        kw_config = config.model_copy(update={"keyword": base_keyword, "max_videos": candidate_limit})
        base_results = self.video_search.search(manifest.run_id, kw_config)
        candidate_ids = [self._normalize_video_id(video.get("video_id")) for video in base_results]
        self.logger.info(
            "AND keyword base '%s': %d/%d videos before metadata filtering (candidates: %s)",
            base_keyword,
            len(base_results),
            candidate_limit,
            ", ".join(candidate_ids[:20]),
        )
        metadata_filtered = self._intersect_keyword_results(
            search_keywords,
            base_results,
            max_videos=len(base_results),
            min_keyword_matches=min_keyword_matches,
        )
        selected = metadata_filtered[: config.max_videos]
        self.logger.info(
            "AND keyword metadata filter completed: base='%s', min_matches=%d/%d, candidates=%d, filtered=%d, selected=%s",
            base_keyword,
            min_keyword_matches,
            len(search_keywords),
            len(base_results),
            len(metadata_filtered),
            ", ".join(str(video.get("video_id", "")) for video in selected[:20]),
            extra={
                "run_id": manifest.run_id,
                "stage": "ingest",
                "base_keyword": base_keyword,
                "keywords": search_keywords,
                "and_min_keyword_matches": min_keyword_matches,
                "candidate_videos": len(base_results),
                "metadata_filtered_videos": len(metadata_filtered),
                "selected_video_ids": [str(video.get("video_id", "")) for video in selected],
                "videos": len(selected),
            },
        )
        return selected

    @classmethod
    def _intersect_keyword_results(
        cls,
        search_keywords: list[str],
        base_results: list[dict],
        max_videos: int,
        min_keyword_matches: int | None = None,
    ) -> list[dict]:
        if not search_keywords or not base_results:
            return []

        remaining_keywords = search_keywords[1:]
        required_matches = cls._and_min_keyword_matches(search_keywords, min_keyword_matches)
        filtered: list[dict] = []
        for video in base_results:
            video_id = cls._normalize_video_id(video.get("video_id"))
            if not video_id:
                continue
            matched_keywords = [search_keywords[0]]
            for keyword in remaining_keywords:
                if cls._keyword_matches_video_metadata(keyword, video):
                    matched_keywords.append(keyword)
            if len(matched_keywords) < required_matches:
                continue
            merged = dict(video)
            merged["video_id"] = video_id
            merged["matched_keyword"] = " AND ".join(matched_keywords)
            merged["matched_keywords"] = list(matched_keywords)
            merged["keyword_match_mode"] = "AND" if required_matches >= len(search_keywords) else "AND_MIN"
            merged["keyword_match_count"] = len(matched_keywords)
            merged["keyword_match_min_required"] = required_matches
            merged["and_base_keyword"] = search_keywords[0]
            filtered.append(merged)

        return cls._sort_videos_for_selection(filtered)[:max_videos]

    @classmethod
    def _and_candidate_limit(cls, max_videos: int) -> int:
        requested = max(1, int(max_videos or 1))
        expanded = max(cls.AND_CANDIDATE_MIN, requested * cls.AND_CANDIDATE_MULTIPLIER)
        return max(requested, min(cls.AND_CANDIDATE_CAP, expanded))

    @staticmethod
    def _and_min_keyword_matches(search_keywords: list[str], configured: int | None) -> int:
        keyword_count = len(search_keywords)
        if keyword_count <= 0:
            return 0
        if configured is None:
            return keyword_count
        return max(1, min(keyword_count, int(configured)))

    @classmethod
    def _keyword_matches_video_metadata(cls, keyword: object, video: dict) -> bool:
        normalized_keyword = cls._normalize_match_text(keyword)
        if not normalized_keyword:
            return True
        metadata_text = cls._video_metadata_text(video)
        return normalized_keyword in metadata_text or normalized_keyword.replace(" ", "") in metadata_text.replace(" ", "")

    @classmethod
    def _video_metadata_text(cls, video: dict) -> str:
        parts: list[str] = []
        for field in ("title", "description", "channel_title", "channel_name"):
            parts.append(cls._normalize_match_text(video.get(field)))
        tags = video.get("tags")
        if isinstance(tags, (list, tuple, set)):
            parts.extend(cls._normalize_match_text(tag) for tag in tags)
        else:
            parts.append(cls._normalize_match_text(tags))
        return " ".join(part for part in parts if part)

    @staticmethod
    def _normalize_match_text(value: object) -> str:
        return " ".join(str(value or "").casefold().split())

    @staticmethod
    def _safe_int(value: object, *, default: int = 0) -> int:
        try:
            return int(float(str(value).replace(",", "")))
        except Exception:
            return default

    @staticmethod
    def _normalize_video_id(value: object) -> str:
        return str(value or "").strip()

    @staticmethod
    def _load_existing_comments(comments_path: Path) -> pd.DataFrame:
        if comments_path.exists():
            try:
                return pd.read_parquet(comments_path)
            except Exception:
                pass
        csv_path = comments_path.with_suffix(".csv")
        if csv_path.exists():
            return pd.read_csv(csv_path)
        return pd.DataFrame()

    @staticmethod
    def _merge_comments(existing_comments: pd.DataFrame, new_comments: pd.DataFrame) -> pd.DataFrame:
        frames = [frame for frame in [existing_comments, new_comments] if not frame.empty]
        if not frames:
            return pd.DataFrame()
        merged = pd.concat(frames, ignore_index=True)
        return merged.drop_duplicates(subset=["video_id", "comment_id"], keep="last").reset_index(drop=True)

    @staticmethod
    def _filter_comments_by_published_at(
        comments: pd.DataFrame,
        *,
        published_after: str | None,
        published_before: str | None,
    ) -> pd.DataFrame:
        if comments.empty or "published_at" not in comments.columns:
            return comments
        if not published_after and not published_before:
            return comments

        published_at = pd.to_datetime(comments["published_at"], errors="coerce", utc=True)
        mask = pd.Series(True, index=comments.index)
        if published_after:
            after = pd.to_datetime(published_after, errors="coerce", utc=True)
            if not pd.isna(after):
                mask &= published_at >= after
        if published_before:
            before = pd.to_datetime(published_before, errors="coerce", utc=True)
            if not pd.isna(before):
                mask &= published_at <= before
        return comments.loc[mask].reset_index(drop=True)
