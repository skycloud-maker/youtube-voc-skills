"""Observation-only CollectionRun finalization after successful legacy workflows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.application.shadow.contracts import ShadowSidecarFailureLog
from src.application.shadow.legacy_collection_mapper import FilesystemLegacyCollectionMapper
from src.domain.digests import dataset_fingerprint
from src.domain.runs import CollectionRun, RunStatus, utc_now
from src.infrastructure.storage.filesystem import (
    FilesystemCollectionRunRepository,
    FilesystemRawSnapshotRepository,
)
from src.infrastructure.storage.ports import RepositoryIntegrityError

LEGACY_COLLECTOR_VERSION = "legacy-youtube-client-v1"
UNKNOWN_CODE_COMMIT = "unknown"


class CollectionRunSidecar:
    """Finalize one immutable canonical collection record from observed snapshots."""

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        self._raw_repository = FilesystemRawSnapshotRepository(canonical_shadow_root)
        self._collection_repository = FilesystemCollectionRunRepository(canonical_shadow_root)
        self._mapper = FilesystemLegacyCollectionMapper(canonical_shadow_root)

    def finalize_legacy_collection(
        self,
        *,
        legacy_run_id: str,
        scope: dict[str, Any],
        quota: dict[str, Any],
    ) -> CollectionRun:
        """Publish one final manifest using an existing mapping and exact raw lineage."""

        mapping = self._mapper.resolve_existing(legacy_run_id)
        raw_snapshot_ids = self._raw_repository.list_snapshot_ids_for_collection(
            mapping.collection_run_id
        )
        if not raw_snapshot_ids:
            raise RepositoryIntegrityError("CollectionRun finalization requires observed raw snapshots")

        snapshots = [
            self._raw_repository.get_snapshot(raw_source_snapshot_id).snapshot
            for raw_source_snapshot_id in raw_snapshot_ids
        ]
        run = CollectionRun(
            collection_run_id=mapping.collection_run_id,
            source_system="youtube",
            scope=scope,
            collector_version=LEGACY_COLLECTOR_VERSION,
            code_commit=UNKNOWN_CODE_COMMIT,
            raw_snapshot_ids=raw_snapshot_ids,
            dataset_fingerprint=dataset_fingerprint(
                snapshot.model_dump(mode="json") for snapshot in snapshots
            ),
            quota=quota,
            status=RunStatus.SUCCEEDED,
            finished_at=utc_now(),
            legacy_ids=(legacy_run_id,),
        )
        return self._collection_repository.create_collection_run(run)


def finalize_legacy_collection_safely(
    *,
    sidecar: CollectionRunSidecar,
    logger: logging.Logger,
    legacy_run_id: str,
    scope: dict[str, Any],
    quota: dict[str, Any],
) -> CollectionRun | None:
    """Finalize shadow lineage without changing a successful legacy result."""

    try:
        run = sidecar.finalize_legacy_collection(
            legacy_run_id=legacy_run_id,
            scope=scope,
            quota=quota,
        )
    except Exception as exc:
        failure = ShadowSidecarFailureLog.from_exception(
            operation="collection_run_finalization",
            error=exc,
            legacy_run_id=legacy_run_id,
        )
        logger.warning(
            "CollectionRun sidecar finalization failed",
            extra={"shadow_failure": failure.model_dump(mode="json")},
        )
        return None

    logger.info(
        "CollectionRun sidecar finalization completed",
        extra={
            "legacy_run_id": legacy_run_id,
            "collection_run_id": run.collection_run_id,
            "raw_snapshot_count": len(run.raw_snapshot_ids),
        },
    )
    return run
