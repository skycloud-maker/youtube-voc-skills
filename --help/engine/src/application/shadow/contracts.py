"""Pre-integration contracts for legacy collection mapping and failure logs."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import Field, ValidationError, field_validator, model_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_collection_run_id,
    validate_canonical_id,
)
from src.domain.digests import canonical_json_bytes, sha256_digest, validate_sha256_digest
from src.domain.runs import FrozenContractModel, utc_now, _validate_timezone
from src.infrastructure.storage.filesystem import validate_canonical_shadow_root
from src.infrastructure.storage.ports import RepositoryIntegrityError, RepositoryNotFoundError


class LegacyCollectionMapping(FrozenContractModel):
    """Append-only compatibility mapping from one legacy run to one CollectionRun."""

    legacy_run_id: str = Field(min_length=1)
    legacy_run_id_digest: str
    collection_run_id: str = Field(default_factory=new_collection_run_id)
    mapper_version: str = "legacy-collection-mapper-v1"
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("collection_run_id")
    @classmethod
    def _collection_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    _legacy_digest = field_validator("legacy_run_id_digest")(validate_sha256_digest)
    _created_at = field_validator("created_at")(_validate_timezone)

    @model_validator(mode="after")
    def _digest_matches_legacy_id(self) -> "LegacyCollectionMapping":
        expected = sha256_digest(self.legacy_run_id.encode("utf-8"))
        if self.legacy_run_id_digest != expected:
            raise ValueError("Legacy run ID digest does not match legacy_run_id")
        return self


class ShadowSidecarFailureLog(FrozenContractModel):
    """Structured observation-mode failure contract without production invocation."""

    operation: str
    error_type: str
    error_message: str
    legacy_run_id: str | None = None
    collection_run_id: str | None = None
    raw_source_snapshot_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)

    _occurred_at = field_validator("occurred_at")(_validate_timezone)

    @field_validator("collection_run_id")
    @classmethod
    def _collection_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    @field_validator("raw_source_snapshot_id")
    @classmethod
    def _raw_source_snapshot_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT)

    @classmethod
    def from_exception(
        cls,
        *,
        operation: str,
        error: Exception,
        legacy_run_id: str | None = None,
        collection_run_id: str | None = None,
        raw_source_snapshot_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> "ShadowSidecarFailureLog":
        return cls(
            operation=operation,
            error_type=type(error).__name__,
            error_message=str(error),
            legacy_run_id=legacy_run_id,
            collection_run_id=collection_run_id,
            raw_source_snapshot_id=raw_source_snapshot_id,
            details=details or {},
        )


class FilesystemLegacyCollectionMapper:
    """Resolve or append one digest-keyed compatibility mapping per legacy run."""

    _MAPPING_FILENAME = "mapping.json"

    def __init__(self, canonical_shadow_root: str | Path) -> None:
        self._root = validate_canonical_shadow_root(canonical_shadow_root)
        self._mapping_root = self._root / "compatibility" / "legacy_collection_runs"
        self._staging_root = self._mapping_root / ".staging"

    @staticmethod
    def mapping_key(legacy_run_id: str) -> str:
        if not isinstance(legacy_run_id, str) or not legacy_run_id:
            raise ValueError("legacy_run_id must be a non-empty string")
        return sha256_digest(legacy_run_id.encode("utf-8")).removeprefix("sha256:")

    def mapping_path(self, legacy_run_id: str) -> Path:
        target = self._mapping_root / self.mapping_key(legacy_run_id)
        self._ensure_within_root(target)
        return target

    def resolve_or_create(self, legacy_run_id: str) -> LegacyCollectionMapping:
        target = self.mapping_path(legacy_run_id)
        if target.exists():
            return self._read_mapping(target, legacy_run_id)

        mapping = LegacyCollectionMapping(
            legacy_run_id=legacy_run_id,
            legacy_run_id_digest=sha256_digest(legacy_run_id.encode("utf-8")),
        )
        self._staging_root.mkdir(parents=True, exist_ok=True)
        staging_dir = self._staging_root / f"{self.mapping_key(legacy_run_id)}.{uuid4().hex}"
        self._ensure_within_root(staging_dir)
        staging_dir.mkdir(exist_ok=False)

        try:
            self._write_exclusive(
                staging_dir / self._MAPPING_FILENAME,
                canonical_json_bytes(mapping.model_dump(mode="json")),
            )
            if self._read_mapping(staging_dir, legacy_run_id, verify_target_key=False) != mapping:
                raise RepositoryIntegrityError("Staged legacy collection mapping failed round-trip validation")

            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                self._discard_staging_dir(staging_dir)
                return self._read_mapping(target, legacy_run_id)
            try:
                os.rename(staging_dir, target)
            except OSError:
                if target.exists():
                    self._discard_staging_dir(staging_dir)
                    return self._read_mapping(target, legacy_run_id)
                raise
        except Exception:
            self._discard_staging_dir(staging_dir)
            raise

        return self._read_mapping(target, legacy_run_id)

    def resolve_existing(self, legacy_run_id: str) -> LegacyCollectionMapping:
        """Return an existing mapping without creating compatibility state."""

        target = self.mapping_path(legacy_run_id)
        if not target.exists():
            raise RepositoryNotFoundError(f"Legacy collection mapping does not exist: {legacy_run_id}")
        return self._read_mapping(target, legacy_run_id)

    def list_mappings(self) -> tuple[LegacyCollectionMapping, ...]:
        """Read every published mapping without changing compatibility state."""

        if not self._mapping_root.exists():
            return ()

        mappings: list[LegacyCollectionMapping] = []
        for target in sorted(self._mapping_root.iterdir()):
            if target == self._staging_root:
                continue
            if not target.is_dir():
                raise RepositoryIntegrityError("Legacy collection mapping root contains an unexpected entry")
            try:
                mapping = LegacyCollectionMapping.model_validate_json(
                    (target / self._MAPPING_FILENAME).read_bytes()
                )
            except (OSError, ValidationError, ValueError) as exc:
                raise RepositoryIntegrityError("Legacy collection mapping could not be read") from exc
            if self.mapping_path(mapping.legacy_run_id) != target:
                raise RepositoryIntegrityError("Legacy collection mapping path does not match its digest key")
            mappings.append(mapping)
        return tuple(mappings)

    def _read_mapping(
        self,
        target: Path,
        expected_legacy_run_id: str,
        *,
        verify_target_key: bool = True,
    ) -> LegacyCollectionMapping:
        try:
            mapping = LegacyCollectionMapping.model_validate_json(
                (target / self._MAPPING_FILENAME).read_bytes()
            )
        except (OSError, ValidationError, ValueError) as exc:
            raise RepositoryIntegrityError("Legacy collection mapping could not be read") from exc
        if mapping.legacy_run_id != expected_legacy_run_id:
            raise RepositoryIntegrityError("Legacy collection mapping key collision detected")
        if verify_target_key and self.mapping_path(mapping.legacy_run_id) != target:
            raise RepositoryIntegrityError("Legacy collection mapping path does not match its digest key")
        return mapping

    def _ensure_within_root(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self._root)
        except ValueError as exc:
            raise RepositoryIntegrityError("Legacy collection mapping path escapes canonical root") from exc

    @staticmethod
    def _write_exclusive(path: Path, payload: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def _discard_staging_dir(self, staging_dir: Path) -> None:
        self._ensure_within_root(staging_dir)
        try:
            (staging_dir / self._MAPPING_FILENAME).unlink()
        except FileNotFoundError:
            pass
        try:
            staging_dir.rmdir()
        except FileNotFoundError:
            pass


def read_legacy_audit_bytes(audit_path: str | Path) -> bytes:
    """Return exact bytes from an already-written authoritative legacy audit file."""

    return Path(audit_path).read_bytes()
