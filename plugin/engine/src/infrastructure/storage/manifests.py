"""Immutable raw snapshot and generated artifact manifests."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from src.domain.canonical_ids import (
    CanonicalIdPrefix,
    new_artifact_id,
    new_raw_snapshot_id,
    validate_canonical_id,
)
from src.domain.digests import validate_sha256_digest
from src.domain.runs import FrozenContractModel, utc_now, _validate_timezone


class RawSourceSnapshot(FrozenContractModel):
    raw_source_snapshot_id: str = Field(default_factory=new_raw_snapshot_id)
    collection_run_id: str
    source_system: str
    source_type: str
    endpoint: str
    source_id: str | None = None
    request_fingerprint: str
    page_token_digest: str | None = None
    captured_at: datetime = Field(default_factory=utc_now)
    media_type: str = "application/json"
    byte_length: int = Field(ge=0)
    content_digest: str
    access_class: str = "internal"
    parser_status: str = "unparsed"
    legacy_refs: tuple[str, ...] = ()

    @field_validator("raw_source_snapshot_id")
    @classmethod
    def _raw_source_snapshot_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT)

    @field_validator("collection_run_id")
    @classmethod
    def _collection_run_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.COLLECTION_RUN)

    _request_fingerprint = field_validator("request_fingerprint")(validate_sha256_digest)
    _page_token_digest = field_validator("page_token_digest")(lambda value: value if value is None else validate_sha256_digest(value))
    _content_digest = field_validator("content_digest")(validate_sha256_digest)
    _captured_at = field_validator("captured_at")(_validate_timezone)


class ArtifactManifest(FrozenContractModel):
    artifact_id: str = Field(default_factory=new_artifact_id)
    owning_run_type: Literal["analysis_run", "evaluation_run", "regression_run", "projection_build", "export"]
    owning_run_id: str
    artifact_type: str
    schema_version: str
    media_type: str
    byte_length: int = Field(ge=0)
    content_digest: str
    created_at: datetime = Field(default_factory=utc_now)
    producer_code_commit: str
    upstream_artifact_ids: tuple[str, ...] = ()
    access_class: str = "internal"
    retention_class: str = "standard"
    legacy_refs: tuple[str, ...] = ()

    @field_validator("artifact_id")
    @classmethod
    def _artifact_id(cls, value: str) -> str:
        return validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ARTIFACT)

    @field_validator("upstream_artifact_ids")
    @classmethod
    def _upstream_artifact_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(validate_canonical_id(value, expected_prefix=CanonicalIdPrefix.ARTIFACT) for value in values)

    _content_digest = field_validator("content_digest")(validate_sha256_digest)
    _created_at = field_validator("created_at")(_validate_timezone)


class StoredRawSnapshot(FrozenContractModel):
    snapshot: RawSourceSnapshot
    storage_uri: str


class StoredArtifact(FrozenContractModel):
    artifact: ArtifactManifest
    storage_uri: str
