"""Append-only filesystem adapter for immutable raw source snapshots."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable
from uuid import uuid4

from pydantic import ValidationError

from src.domain.canonical_ids import CanonicalIdPrefix, validate_canonical_id
from src.domain.digests import canonical_json_bytes, sha256_digest
from src.domain.runs import AnalysisRun, CollectionRun
from src.infrastructure.storage.manifests import (
    ArtifactManifest,
    RawSourceSnapshot,
    StoredArtifact,
    StoredRawSnapshot,
)
from src.infrastructure.storage.ports import (
    RepositoryConflictError,
    RepositoryIntegrityError,
    RepositoryNotFoundError,
)


def validate_canonical_shadow_root(
    canonical_shadow_root: str | Path,
    *,
    legacy_raw_dir: str | Path = Path("data/raw"),
    legacy_processed_dir: str | Path = Path("data/processed"),
) -> Path:
    """Reject canonical storage roots nested below authoritative legacy paths."""

    root = Path(canonical_shadow_root).resolve()
    for legacy_dir in (legacy_raw_dir, legacy_processed_dir):
        legacy_root = Path(legacy_dir).resolve()
        try:
            root.relative_to(legacy_root)
        except ValueError:
            continue
        raise ValueError(f"Canonical shadow root must not be nested below legacy path: {legacy_root}")
    return root


class FilesystemRawSnapshotRepository:
    """Publish and retrieve raw snapshot bytes below one canonical shadow root."""

    _METADATA_FILENAME = "metadata.json"
    _PAYLOAD_FILENAME = "payload.json"

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        self._root = validate_canonical_shadow_root(canonical_shadow_root)
        self._raw_root = self._root / "raw"
        self._collection_runs_root = self._raw_root / "collection_runs"
        self._staging_root = self._raw_root / ".staging"

    def create_snapshot(self, snapshot: RawSourceSnapshot, payload: bytes) -> StoredRawSnapshot:
        """Publish one immutable snapshot or reject an existing canonical identity."""

        target = self._snapshot_dir(snapshot.collection_run_id, snapshot.raw_source_snapshot_id)
        if target.exists():
            raise RepositoryConflictError(f"Raw snapshot already exists: {snapshot.raw_source_snapshot_id}")

        payload_digest = sha256_digest(payload)
        if payload_digest != snapshot.content_digest:
            raise RepositoryIntegrityError("Raw snapshot payload digest does not match manifest")
        if len(payload) != snapshot.byte_length:
            raise RepositoryIntegrityError("Raw snapshot payload byte length does not match manifest")

        self._staging_root.mkdir(parents=True, exist_ok=True)
        staging_dir = self._staging_root / f"{snapshot.raw_source_snapshot_id}.{uuid4().hex}"
        self._ensure_within_root(staging_dir)
        staging_dir.mkdir(exist_ok=False)

        try:
            self._write_exclusive(staging_dir / self._PAYLOAD_FILENAME, payload)
            metadata = canonical_json_bytes(snapshot.model_dump(mode="json"))
            self._write_exclusive(staging_dir / self._METADATA_FILENAME, metadata)

            stored_payload = (staging_dir / self._PAYLOAD_FILENAME).read_bytes()
            if sha256_digest(stored_payload) != snapshot.content_digest:
                raise RepositoryIntegrityError("Staged raw snapshot payload failed digest verification")
            if len(stored_payload) != snapshot.byte_length:
                raise RepositoryIntegrityError("Staged raw snapshot payload failed byte-length verification")

            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise RepositoryConflictError(f"Raw snapshot already exists: {snapshot.raw_source_snapshot_id}")
            try:
                os.rename(staging_dir, target)
            except OSError as exc:
                if target.exists():
                    raise RepositoryConflictError(
                        f"Raw snapshot already exists: {snapshot.raw_source_snapshot_id}"
                    ) from exc
                raise
        except Exception:
            self._discard_staging_dir(staging_dir)
            raise

        return StoredRawSnapshot(snapshot=snapshot, storage_uri=target.resolve().as_uri())

    def get_snapshot(self, raw_source_snapshot_id: str) -> StoredRawSnapshot:
        """Read one snapshot and verify its identity, location, and exact bytes."""

        raw_source_snapshot_id = validate_canonical_id(
            raw_source_snapshot_id,
            expected_prefix=CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT,
        )
        matches = self._find_snapshot_dirs(raw_source_snapshot_id)
        if not matches:
            raise RepositoryNotFoundError(f"Raw snapshot does not exist: {raw_source_snapshot_id}")
        if len(matches) > 1:
            raise RepositoryIntegrityError(f"Raw snapshot identity is not unique: {raw_source_snapshot_id}")

        target = matches[0]
        metadata_path = self._checked_child(target, self._METADATA_FILENAME)
        payload_path = self._checked_child(target, self._PAYLOAD_FILENAME)
        try:
            metadata = metadata_path.read_bytes()
            payload = payload_path.read_bytes()
            snapshot = RawSourceSnapshot.model_validate_json(metadata)
        except (OSError, ValidationError, ValueError) as exc:
            raise RepositoryIntegrityError(f"Raw snapshot could not be read: {raw_source_snapshot_id}") from exc

        if snapshot.raw_source_snapshot_id != raw_source_snapshot_id:
            raise RepositoryIntegrityError("Stored raw snapshot metadata identity does not match its key")
        expected_target = self._snapshot_dir(snapshot.collection_run_id, snapshot.raw_source_snapshot_id)
        if target.resolve() != expected_target.resolve():
            raise RepositoryIntegrityError("Stored raw snapshot location does not match its metadata")
        if sha256_digest(payload) != snapshot.content_digest:
            raise RepositoryIntegrityError("Stored raw snapshot payload failed digest verification")
        if len(payload) != snapshot.byte_length:
            raise RepositoryIntegrityError("Stored raw snapshot payload failed byte-length verification")

        return StoredRawSnapshot(snapshot=snapshot, storage_uri=target.resolve().as_uri())

    def list_snapshot_ids_for_collection(self, collection_run_id: str) -> tuple[str, ...]:
        """List and verify every immutable snapshot belonging to one collection."""

        collection_run_id = validate_canonical_id(
            collection_run_id,
            expected_prefix=CanonicalIdPrefix.COLLECTION_RUN,
        )
        snapshots_root = self._collection_runs_root / collection_run_id / "snapshots"
        self._ensure_within_root(snapshots_root)
        if not snapshots_root.exists():
            return ()

        snapshot_ids: list[str] = []
        for target in sorted(snapshots_root.iterdir()):
            if not target.is_dir():
                raise RepositoryIntegrityError("Raw snapshot root contains an unexpected entry")
            raw_source_snapshot_id = validate_canonical_id(
                target.name,
                expected_prefix=CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT,
            )
            stored = self.get_snapshot(raw_source_snapshot_id)
            if stored.snapshot.collection_run_id != collection_run_id:
                raise RepositoryIntegrityError("Raw snapshot does not belong to the requested collection run")
            snapshot_ids.append(raw_source_snapshot_id)
        return tuple(snapshot_ids)

    def _snapshot_dir(self, collection_run_id: str, raw_source_snapshot_id: str) -> Path:
        collection_run_id = validate_canonical_id(
            collection_run_id,
            expected_prefix=CanonicalIdPrefix.COLLECTION_RUN,
        )
        raw_source_snapshot_id = validate_canonical_id(
            raw_source_snapshot_id,
            expected_prefix=CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT,
        )
        target = (
            self._collection_runs_root
            / collection_run_id
            / "snapshots"
            / raw_source_snapshot_id
        )
        self._ensure_within_root(target)
        return target

    def _find_snapshot_dirs(self, raw_source_snapshot_id: str) -> list[Path]:
        if not self._collection_runs_root.exists():
            return []

        matches: list[Path] = []
        for collection_dir in self._collection_runs_root.iterdir():
            candidate = collection_dir / "snapshots" / raw_source_snapshot_id
            self._ensure_within_root(candidate)
            if candidate.is_dir():
                matches.append(candidate)
        return matches

    def _checked_child(self, parent: Path, filename: str) -> Path:
        child = parent / filename
        self._ensure_within_root(child)
        return child

    def _ensure_within_root(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self._root)
        except ValueError as exc:
            raise RepositoryIntegrityError("Canonical snapshot path escapes its configured root") from exc

    @staticmethod
    def _write_exclusive(path: Path, payload: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def _discard_staging_dir(self, staging_dir: Path) -> None:
        self._ensure_within_root(staging_dir)
        for filename in (self._METADATA_FILENAME, self._PAYLOAD_FILENAME):
            try:
                (staging_dir / filename).unlink()
            except FileNotFoundError:
                pass
        try:
            staging_dir.rmdir()
        except FileNotFoundError:
            pass


class _AppendOnlyFilesystemPublisher:
    """Publish immutable record directories below one storage namespace."""

    def __init__(self, canonical_shadow_root: str | Path, namespace: str) -> None:
        self._root = validate_canonical_shadow_root(canonical_shadow_root)
        self._storage_root = self._root / namespace
        self._staging_root = self._storage_root / ".staging"

    def _record_dir(self, record_id: str, *, expected_prefix: CanonicalIdPrefix) -> Path:
        record_id = validate_canonical_id(record_id, expected_prefix=expected_prefix)
        target = self._storage_root / record_id
        self._ensure_within_root(target)
        return target

    def _publish(
        self,
        target: Path,
        record_id: str,
        files: dict[str, bytes],
        *,
        validate_staged: Callable[[Path], None] | None = None,
    ) -> Path:
        if target.exists():
            raise RepositoryConflictError(f"Canonical record already exists: {record_id}")

        self._staging_root.mkdir(parents=True, exist_ok=True)
        staging_dir = self._staging_root / f"{record_id}.{uuid4().hex}"
        self._ensure_within_root(staging_dir)
        staging_dir.mkdir(exist_ok=False)

        try:
            for filename, payload in files.items():
                self._write_exclusive(self._checked_child(staging_dir, filename), payload)
            if validate_staged is not None:
                validate_staged(staging_dir)

            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise RepositoryConflictError(f"Canonical record already exists: {record_id}")
            try:
                os.rename(staging_dir, target)
            except OSError as exc:
                if target.exists():
                    raise RepositoryConflictError(f"Canonical record already exists: {record_id}") from exc
                raise
        except Exception:
            self._discard_staging_dir(staging_dir)
            raise

        return target

    def _read_bytes(self, target: Path, filename: str, record_id: str) -> bytes:
        try:
            return self._checked_child(target, filename).read_bytes()
        except OSError as exc:
            raise RepositoryIntegrityError(f"Canonical record could not be read: {record_id}") from exc

    def _list_record_ids(self, *, expected_prefix: CanonicalIdPrefix) -> tuple[str, ...]:
        if not self._storage_root.exists():
            return ()

        record_ids: list[str] = []
        for target in sorted(self._storage_root.iterdir()):
            if target == self._staging_root:
                continue
            if not target.is_dir():
                raise RepositoryIntegrityError("Canonical record root contains an unexpected entry")
            record_ids.append(validate_canonical_id(target.name, expected_prefix=expected_prefix))
        return tuple(record_ids)

    def _checked_child(self, parent: Path, filename: str) -> Path:
        child = parent / filename
        self._ensure_within_root(child)
        return child

    def _ensure_within_root(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self._root)
        except ValueError as exc:
            raise RepositoryIntegrityError("Canonical record path escapes its configured root") from exc

    @staticmethod
    def _write_exclusive(path: Path, payload: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def _discard_staging_dir(self, staging_dir: Path) -> None:
        self._ensure_within_root(staging_dir)
        if not staging_dir.exists():
            return
        for child in staging_dir.iterdir():
            child.unlink()
        staging_dir.rmdir()


class FilesystemArtifactRepository(_AppendOnlyFilesystemPublisher):
    """Publish and retrieve immutable generated artifact bytes."""

    _MANIFEST_FILENAME = "manifest.json"
    _PAYLOAD_FILENAME = "payload.bin"

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        super().__init__(canonical_shadow_root, namespace="artifacts")

    def create_artifact(self, artifact: ArtifactManifest, payload: bytes) -> StoredArtifact:
        target = self._record_dir(artifact.artifact_id, expected_prefix=CanonicalIdPrefix.ARTIFACT)
        if sha256_digest(payload) != artifact.content_digest:
            raise RepositoryIntegrityError("Artifact payload digest does not match manifest")
        if len(payload) != artifact.byte_length:
            raise RepositoryIntegrityError("Artifact payload byte length does not match manifest")

        target = self._publish(
            target,
            artifact.artifact_id,
            {
                self._MANIFEST_FILENAME: canonical_json_bytes(artifact.model_dump(mode="json")),
                self._PAYLOAD_FILENAME: payload,
            },
            validate_staged=lambda staging_dir: self._validate_artifact_dir(staging_dir, artifact.artifact_id),
        )
        stored_artifact = self._validate_artifact_dir(target, artifact.artifact_id)
        return StoredArtifact(artifact=stored_artifact, storage_uri=target.resolve().as_uri())

    def get_artifact(self, artifact_id: str) -> StoredArtifact:
        target = self._record_dir(artifact_id, expected_prefix=CanonicalIdPrefix.ARTIFACT)
        if not target.is_dir():
            raise RepositoryNotFoundError(f"Artifact does not exist: {artifact_id}")

        artifact = self._validate_artifact_dir(target, artifact_id)
        return StoredArtifact(artifact=artifact, storage_uri=target.resolve().as_uri())

    def _validate_artifact_dir(self, target: Path, artifact_id: str) -> ArtifactManifest:
        try:
            artifact = ArtifactManifest.model_validate_json(
                self._read_bytes(target, self._MANIFEST_FILENAME, artifact_id)
            )
        except (ValidationError, ValueError) as exc:
            raise RepositoryIntegrityError(f"Artifact manifest could not be read: {artifact_id}") from exc
        if artifact.artifact_id != artifact_id:
            raise RepositoryIntegrityError("Stored artifact manifest identity does not match its key")
        payload = self._read_bytes(target, self._PAYLOAD_FILENAME, artifact_id)
        if sha256_digest(payload) != artifact.content_digest:
            raise RepositoryIntegrityError("Stored artifact payload failed digest verification")
        if len(payload) != artifact.byte_length:
            raise RepositoryIntegrityError("Stored artifact payload failed byte-length verification")
        return artifact


class FilesystemCollectionRunRepository(_AppendOnlyFilesystemPublisher):
    """Publish and retrieve immutable collection run manifests."""

    _MANIFEST_FILENAME = "manifest.json"

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        super().__init__(canonical_shadow_root, namespace="collection_runs")

    def create_collection_run(self, run: CollectionRun) -> CollectionRun:
        target = self._record_dir(run.collection_run_id, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)
        self._publish(
            target,
            run.collection_run_id,
            {self._MANIFEST_FILENAME: canonical_json_bytes(run.model_dump(mode="json"))},
            validate_staged=lambda staging_dir: self._validate_collection_run_dir(
                staging_dir,
                run.collection_run_id,
            ),
        )
        return run

    def get_collection_run(self, collection_run_id: str) -> CollectionRun:
        target = self._record_dir(collection_run_id, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)
        if not target.is_dir():
            raise RepositoryNotFoundError(f"Collection run does not exist: {collection_run_id}")
        return self._validate_collection_run_dir(target, collection_run_id)

    def list_collection_run_ids(self) -> tuple[str, ...]:
        return self._list_record_ids(expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    def _validate_collection_run_dir(self, target: Path, collection_run_id: str) -> CollectionRun:
        try:
            run = CollectionRun.model_validate_json(
                self._read_bytes(target, self._MANIFEST_FILENAME, collection_run_id)
            )
        except (ValidationError, ValueError) as exc:
            raise RepositoryIntegrityError(f"Collection run manifest could not be read: {collection_run_id}") from exc
        if run.collection_run_id != collection_run_id:
            raise RepositoryIntegrityError("Stored collection run identity does not match its key")
        return run


class FilesystemAnalysisRunRepository(_AppendOnlyFilesystemPublisher):
    """Publish and retrieve immutable analysis run manifests."""

    _MANIFEST_FILENAME = "manifest.json"

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        super().__init__(canonical_shadow_root, namespace="analysis_runs")

    def create_analysis_run(self, run: AnalysisRun) -> AnalysisRun:
        target = self._record_dir(run.analysis_run_id, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)
        self._publish(
            target,
            run.analysis_run_id,
            {self._MANIFEST_FILENAME: canonical_json_bytes(run.model_dump(mode="json"))},
            validate_staged=lambda staging_dir: self._validate_analysis_run_dir(
                staging_dir,
                run.analysis_run_id,
            ),
        )
        return run

    def get_analysis_run(self, analysis_run_id: str) -> AnalysisRun:
        target = self._record_dir(analysis_run_id, expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)
        if not target.is_dir():
            raise RepositoryNotFoundError(f"Analysis run does not exist: {analysis_run_id}")
        return self._validate_analysis_run_dir(target, analysis_run_id)

    def list_analysis_run_ids(self) -> tuple[str, ...]:
        return self._list_record_ids(expected_prefix=CanonicalIdPrefix.ANALYSIS_RUN)

    def _validate_analysis_run_dir(self, target: Path, analysis_run_id: str) -> AnalysisRun:
        try:
            run = AnalysisRun.model_validate_json(
                self._read_bytes(target, self._MANIFEST_FILENAME, analysis_run_id)
            )
        except (ValidationError, ValueError) as exc:
            raise RepositoryIntegrityError(f"Analysis run manifest could not be read: {analysis_run_id}") from exc
        if run.analysis_run_id != analysis_run_id:
            raise RepositoryIntegrityError("Stored analysis run identity does not match its key")
        return run
