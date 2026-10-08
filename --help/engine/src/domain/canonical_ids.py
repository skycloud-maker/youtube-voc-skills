"""Opaque canonical identifier generation and validation."""

from __future__ import annotations

import re
from enum import StrEnum
from uuid import uuid4


class CanonicalIdPrefix(StrEnum):
    """Prefixes for canonical identities introduced in the storage foundation."""

    COLLECTION_RUN = "crun_"
    ANALYSIS_RUN = "arun_"
    RAW_SOURCE_SNAPSHOT = "raw_"
    ARTIFACT = "art_"
    ATOMIC_VOC = "avoc_"
    ATOMIC_VOC_REVISION = "avocr_"
    EVIDENCE_REF = "eref_"
    CEJ_ASSESSMENT = "cej_"
    TEES_ASSESSMENT = "tees_"
    ROOT_CAUSE_HYPOTHESIS = "rch_"
    ISSUE_CLUSTER = "icl_"
    IMPROVEMENT_CANDIDATE = "cand_"
    PRACTITIONER_ACTION = "pact_"


_UUID4_HEX_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _prefix_value(prefix: CanonicalIdPrefix | str) -> str:
    try:
        return CanonicalIdPrefix(prefix).value
    except ValueError as exc:
        raise ValueError(f"Unsupported canonical ID prefix: {prefix!r}") from exc


def new_canonical_id(prefix: CanonicalIdPrefix | str) -> str:
    """Create an opaque prefixed UUID4 identifier."""

    return f"{_prefix_value(prefix)}{uuid4().hex}"


def validate_canonical_id(value: str, *, expected_prefix: CanonicalIdPrefix | str) -> str:
    """Validate and return an opaque canonical identifier."""

    prefix = _prefix_value(expected_prefix)
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ValueError(f"Canonical ID must start with {prefix!r}")
    payload = value[len(prefix) :]
    if not _UUID4_HEX_PATTERN.fullmatch(payload):
        raise ValueError("Canonical ID payload must be 32 lowercase hexadecimal characters")
    return value


def new_collection_run_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.COLLECTION_RUN)


def new_analysis_run_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.ANALYSIS_RUN)


def new_raw_snapshot_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.RAW_SOURCE_SNAPSHOT)


def new_artifact_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.ARTIFACT)


def new_atomic_voc_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.ATOMIC_VOC)


def new_atomic_voc_revision_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.ATOMIC_VOC_REVISION)


def new_evidence_ref_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.EVIDENCE_REF)


def new_cej_assessment_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.CEJ_ASSESSMENT)


def new_tees_assessment_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.TEES_ASSESSMENT)


def new_root_cause_hypothesis_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.ROOT_CAUSE_HYPOTHESIS)


def new_issue_cluster_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.ISSUE_CLUSTER)


def new_improvement_candidate_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.IMPROVEMENT_CANDIDATE)


def new_practitioner_action_id() -> str:
    return new_canonical_id(CanonicalIdPrefix.PRACTITIONER_ACTION)
