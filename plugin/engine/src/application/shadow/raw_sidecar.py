"""Observation-only raw snapshot sidecar invoked after authoritative legacy writes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.application.shadow.contracts import read_legacy_audit_bytes
from src.application.shadow.legacy_collection_mapper import FilesystemLegacyCollectionMapper
from src.domain.canonical_ids import new_raw_snapshot_id
from src.domain.digests import canonical_json_digest, sha256_digest
from src.infrastructure.storage.filesystem import FilesystemRawSnapshotRepository
from src.infrastructure.storage.manifests import RawSourceSnapshot, StoredRawSnapshot


class RawSnapshotSidecar:
    """Publish exact legacy audit bytes into isolated canonical shadow storage."""

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        self._repository = FilesystemRawSnapshotRepository(canonical_shadow_root)
        self._mapper = FilesystemLegacyCollectionMapper(canonical_shadow_root)

    def observe_legacy_audit(
        self,
        *,
        audit_path: str | Path,
        legacy_run_id: str,
        endpoint: str,
        source_id: str | None,
        page_token: str | None,
        request_context: dict[str, Any],
    ) -> StoredRawSnapshot:
        """Append one fresh raw snapshot for one successful legacy audit event."""

        mapping = self._mapper.resolve_or_create(legacy_run_id)
        payload = read_legacy_audit_bytes(audit_path)
        snapshot = RawSourceSnapshot(
            raw_source_snapshot_id=new_raw_snapshot_id(),
            collection_run_id=mapping.collection_run_id,
            source_system="youtube",
            source_type="api_page_audit",
            endpoint=endpoint,
            source_id=source_id,
            request_fingerprint=canonical_json_digest(request_context),
            page_token_digest=sha256_digest(page_token.encode("utf-8")) if page_token is not None else None,
            media_type="application/json",
            byte_length=len(payload),
            content_digest=sha256_digest(payload),
            legacy_refs=(legacy_run_id, str(Path(audit_path))),
        )
        return self._repository.create_snapshot(snapshot, payload)
