"""Thin YouTube Data API v3 client with quota tracking and raw audit persistence."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import requests

from src.application.shadow.contracts import ShadowSidecarFailureLog
from src.application.shadow.raw_sidecar import RawSnapshotSidecar
from src.api.quota import QuotaLedger
from src.config import CanonicalShadowSettings
from src.models.schemas import ApiPageAudit
from src.utils.io import ensure_dir, write_json
from src.utils.retry import with_retry


class YoutubeApiError(RuntimeError):
    """Raised when the YouTube API returns a non-recoverable error."""


class YoutubeClient:
    """API wrapper for search, video metadata, comments, and replies."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: int,
        max_retries: int,
        backoff_seconds: float,
        raw_dir: Path,
        quota_ledger: QuotaLedger,
        logger: logging.Logger | None = None,
        canonical_shadow: CanonicalShadowSettings | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.raw_dir = ensure_dir(raw_dir)
        self.quota_ledger = quota_ledger
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        self.raw_snapshot_sidecar = self._build_raw_snapshot_sidecar(canonical_shadow)

    @staticmethod
    def _build_raw_snapshot_sidecar(
        canonical_shadow: CanonicalShadowSettings | None,
    ) -> RawSnapshotSidecar | None:
        if canonical_shadow is None or not canonical_shadow.raw_snapshot_sidecar_enabled:
            return None
        return RawSnapshotSidecar(canonical_shadow.root)

    def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        run_id: str,
        page_token: str | None = None,
        video_id: str | None = None,
        quota_method: str,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        query = {**params, "key": self.api_key}

        def call() -> dict[str, Any]:
            response = self.session.get(url, params=query, timeout=self.timeout_seconds)
            if response.status_code >= 400:
                if response.status_code in {403, 404}:
                    self.logger.warning("YouTube API returned a handled client error", extra={"endpoint": endpoint, "video_id": video_id, "page_token": page_token})
                response.raise_for_status()
            return response.json()

        try:
            payload = with_retry(call, logger=self.logger, max_retries=self.max_retries, backoff_seconds=self.backoff_seconds)
        except requests.HTTPError as exc:
            message = exc.response.text if exc.response is not None else str(exc)
            raise YoutubeApiError(message) from exc

        self.quota_ledger.record(quota_method)
        audit = ApiPageAudit(endpoint=quota_method, run_id=run_id, page_token=page_token, video_id=video_id, payload=payload)
        audit_path = self.raw_dir / run_id / quota_method.replace(".", "_") / f"{video_id or 'global'}_{self._audit_page_token_slug(page_token)}.json"
        write_json(audit_path, audit.model_dump(mode="json"))
        self._observe_raw_snapshot(
            audit_path=audit_path,
            legacy_run_id=run_id,
            endpoint=quota_method,
            source_id=video_id,
            page_token=page_token,
            request_context={"endpoint": endpoint, "params": params},
        )
        return payload

    @staticmethod
    def _audit_page_token_slug(page_token: str | None) -> str:
        if not page_token:
            return "first"
        digest = hashlib.sha256(page_token.encode("utf-8")).hexdigest()[:16]
        return f"pt_{digest}"

    def _observe_raw_snapshot(
        self,
        *,
        audit_path: Path,
        legacy_run_id: str,
        endpoint: str,
        source_id: str | None,
        page_token: str | None,
        request_context: dict[str, Any],
    ) -> None:
        if self.raw_snapshot_sidecar is None:
            return
        try:
            stored = self.raw_snapshot_sidecar.observe_legacy_audit(
                audit_path=audit_path,
                legacy_run_id=legacy_run_id,
                endpoint=endpoint,
                source_id=source_id,
                page_token=page_token,
                request_context=request_context,
            )
        except Exception as exc:
            failure = ShadowSidecarFailureLog.from_exception(
                operation="raw_snapshot_observation",
                error=exc,
                legacy_run_id=legacy_run_id,
                details={"audit_path": str(audit_path), "endpoint": endpoint},
            )
            self.logger.warning("Raw snapshot sidecar observation failed", extra={"shadow_failure": failure.model_dump(mode="json")})
            return
        self.logger.info(
            "Raw snapshot sidecar observation completed",
            extra={
                "legacy_run_id": legacy_run_id,
                "raw_source_snapshot_id": stored.snapshot.raw_source_snapshot_id,
                "collection_run_id": stored.snapshot.collection_run_id,
            },
        )

    def search_videos(self, *, run_id: str, **params: Any) -> dict[str, Any]:
        return self._request("search", params, run_id=run_id, page_token=params.get("pageToken"), quota_method="search.list")

    def list_videos(self, *, run_id: str, **params: Any) -> dict[str, Any]:
        return self._request("videos", params, run_id=run_id, quota_method="videos.list")

    def list_comment_threads(self, *, run_id: str, video_id: str, **params: Any) -> dict[str, Any]:
        return self._request("commentThreads", params, run_id=run_id, page_token=params.get("pageToken"), video_id=video_id, quota_method="commentThreads.list")

    def list_comments(self, *, run_id: str, video_id: str, **params: Any) -> dict[str, Any]:
        return self._request("comments", params, run_id=run_id, page_token=params.get("pageToken"), video_id=video_id, quota_method="comments.list")
