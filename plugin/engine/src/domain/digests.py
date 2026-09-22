"""Deterministic SHA-256 helpers for canonical payloads and fingerprints."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any


_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_DATASET_DESCRIPTOR_FIELDS = (
    "raw_source_snapshot_id",
    "source_type",
    "content_digest",
    "byte_length",
)


def sha256_digest(payload: bytes) -> str:
    """Return the SHA-256 digest of exact stored bytes."""

    if not isinstance(payload, bytes):
        raise TypeError("SHA-256 payload must be bytes")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def validate_sha256_digest(value: str) -> str:
    """Validate and return a canonical SHA-256 digest string."""

    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError("Digest must use the format 'sha256:<64 lowercase hexadecimal characters>'")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize structured content to deterministic UTF-8 JSON bytes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_digest(value: Any) -> str:
    """Return the SHA-256 digest of canonical UTF-8 JSON bytes."""

    return sha256_digest(canonical_json_bytes(value))


def dataset_fingerprint(snapshot_descriptors: Iterable[Mapping[str, Any]]) -> str:
    """Fingerprint immutable snapshot descriptors independently of input order."""

    normalized: list[dict[str, Any]] = []
    for descriptor in snapshot_descriptors:
        missing = [field for field in _DATASET_DESCRIPTOR_FIELDS if field not in descriptor]
        if missing:
            raise ValueError(f"Snapshot descriptor is missing required fields: {', '.join(missing)}")
        content_digest = validate_sha256_digest(str(descriptor["content_digest"]))
        byte_length = descriptor["byte_length"]
        if not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length < 0:
            raise ValueError("Snapshot descriptor byte_length must be a non-negative integer")
        normalized.append(
            {
                "raw_source_snapshot_id": str(descriptor["raw_source_snapshot_id"]),
                "source_type": str(descriptor["source_type"]),
                "content_digest": content_digest,
                "byte_length": byte_length,
            }
        )

    normalized.sort(key=lambda descriptor: descriptor["raw_source_snapshot_id"])
    return canonical_json_digest(normalized)
