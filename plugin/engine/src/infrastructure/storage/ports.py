"""Storage-neutral repository protocols for immutable canonical records."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.runs import AnalysisRun, CollectionRun
from src.infrastructure.storage.manifests import (
    ArtifactManifest,
    RawSourceSnapshot,
    StoredArtifact,
    StoredRawSnapshot,
)


class RepositoryError(RuntimeError):
    """Base class for canonical repository failures."""


class RepositoryConflictError(RepositoryError):
    """Raised when a create-only canonical identity already exists."""


class RepositoryNotFoundError(RepositoryError):
    """Raised when a requested canonical identity does not exist."""


class RepositoryIntegrityError(RepositoryError):
    """Raised when stored bytes, digest, or lineage fail verification."""


@runtime_checkable
class RawSnapshotRepository(Protocol):
    def create_snapshot(self, snapshot: RawSourceSnapshot, payload: bytes) -> StoredRawSnapshot: ...

    def get_snapshot(self, raw_source_snapshot_id: str) -> StoredRawSnapshot: ...


@runtime_checkable
class ArtifactRepository(Protocol):
    def create_artifact(self, artifact: ArtifactManifest, payload: bytes) -> StoredArtifact: ...

    def get_artifact(self, artifact_id: str) -> StoredArtifact: ...


@runtime_checkable
class CollectionRunRepository(Protocol):
    def create_collection_run(self, run: CollectionRun) -> CollectionRun: ...

    def get_collection_run(self, collection_run_id: str) -> CollectionRun: ...


@runtime_checkable
class AnalysisRunRepository(Protocol):
    def create_analysis_run(self, run: AnalysisRun) -> AnalysisRun: ...

    def get_analysis_run(self, analysis_run_id: str) -> AnalysisRun: ...
