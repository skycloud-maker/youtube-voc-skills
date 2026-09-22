"""Read-only fail-closed validation for the M1 canonical shadow graph."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field, field_validator

from src.application.shadow.contracts import FilesystemLegacyCollectionMapper
from src.domain.digests import dataset_fingerprint
from src.domain.runs import FrozenContractModel, utc_now, _validate_timezone
from src.infrastructure.storage.filesystem import (
    FilesystemAnalysisRunRepository,
    FilesystemCollectionRunRepository,
    FilesystemRawSnapshotRepository,
)
from src.infrastructure.storage.ports import RepositoryIntegrityError


class M1ExitValidationReport(FrozenContractModel):
    """Summary emitted only after the entire persisted M1 graph validates."""

    valid: bool = True
    validated_at: datetime = Field(default_factory=utc_now)
    mapping_count: int = Field(ge=0)
    collection_run_count: int = Field(ge=0)
    raw_snapshot_count: int = Field(ge=0)
    analysis_run_count: int = Field(ge=0)
    collection_run_ids: tuple[str, ...]

    _validated_at = field_validator("validated_at")(_validate_timezone)


class CanonicalShadowGraphValidator:
    """Validate mappings, CollectionRuns, raw snapshots, and AnalysisRuns without writes."""

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        self._raw_repository = FilesystemRawSnapshotRepository(canonical_shadow_root)
        self._collection_repository = FilesystemCollectionRunRepository(canonical_shadow_root)
        self._analysis_repository = FilesystemAnalysisRunRepository(canonical_shadow_root)
        self._mapper = FilesystemLegacyCollectionMapper(canonical_shadow_root)

    def validate_all(self) -> M1ExitValidationReport:
        mappings = self._mapper.list_mappings()
        if not mappings:
            raise RepositoryIntegrityError("Canonical graph has no legacy collection mappings")

        mapping_by_collection_id = {}
        for mapping in mappings:
            if mapping.collection_run_id in mapping_by_collection_id:
                raise RepositoryIntegrityError("Multiple legacy mappings reference one CollectionRun")
            mapping_by_collection_id[mapping.collection_run_id] = mapping

        collection_run_ids = self._collection_repository.list_collection_run_ids()
        mapped_ids = set(mapping_by_collection_id)
        published_ids = set(collection_run_ids)
        if mapped_ids != published_ids:
            raise RepositoryIntegrityError("Legacy mappings and published CollectionRuns do not match")

        raw_snapshot_count = 0
        for collection_run_id in collection_run_ids:
            run = self._collection_repository.get_collection_run(collection_run_id)
            mapping = mapping_by_collection_id[collection_run_id]
            if mapping.legacy_run_id not in run.legacy_ids:
                raise RepositoryIntegrityError("CollectionRun does not preserve its legacy mapping alias")

            actual_snapshot_ids = self._raw_repository.list_snapshot_ids_for_collection(
                collection_run_id
            )
            if not actual_snapshot_ids:
                raise RepositoryIntegrityError("CollectionRun has no observed raw snapshots")
            if tuple(sorted(run.raw_snapshot_ids)) != actual_snapshot_ids:
                raise RepositoryIntegrityError("CollectionRun raw snapshot set does not match stored snapshots")

            snapshots = [
                self._raw_repository.get_snapshot(raw_source_snapshot_id).snapshot
                for raw_source_snapshot_id in actual_snapshot_ids
            ]
            expected_fingerprint = dataset_fingerprint(
                snapshot.model_dump(mode="json") for snapshot in snapshots
            )
            if run.dataset_fingerprint != expected_fingerprint:
                raise RepositoryIntegrityError("CollectionRun dataset fingerprint does not match raw snapshots")
            raw_snapshot_count += len(actual_snapshot_ids)

        analysis_run_ids = self._analysis_repository.list_analysis_run_ids()
        for analysis_run_id in analysis_run_ids:
            analysis_run = self._analysis_repository.get_analysis_run(analysis_run_id)
            if analysis_run.collection_run_id not in published_ids:
                raise RepositoryIntegrityError("AnalysisRun references a missing CollectionRun")

        return M1ExitValidationReport(
            mapping_count=len(mappings),
            collection_run_count=len(collection_run_ids),
            raw_snapshot_count=raw_snapshot_count,
            analysis_run_count=len(analysis_run_ids),
            collection_run_ids=collection_run_ids,
        )
