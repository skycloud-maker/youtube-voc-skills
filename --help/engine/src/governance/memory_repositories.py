"""In-memory governance metadata repositories.

These implementations exist to prove the storage-neutral repository ports can
be satisfied before any durable adapter is introduced.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from src.governance.metadata import (
    CorrectionMetadata,
    CostMetadata,
    EvaluationMetadata,
    ModelInvocationMetadata,
    PromptInvocationMetadata,
    ReanalysisMetadata,
    RegressionMetadata,
    ReviewMetadata,
    ShadowEventMetadata,
)
from src.governance.repositories import (
    GovernanceRepositoryConflictError,
    GovernanceRepositoryNotFoundError,
)


MetadataT = TypeVar("MetadataT")


class _InMemoryGovernanceRepository(Generic[MetadataT]):
    def __init__(self, id_attribute: str) -> None:
        self._id_attribute = id_attribute
        self._records: dict[str, MetadataT] = {}

    def create(self, metadata: MetadataT) -> MetadataT:
        metadata_id = self._metadata_id(metadata)
        if metadata_id in self._records:
            raise GovernanceRepositoryConflictError(
                f"Governance metadata already exists: {metadata_id}"
            )
        self._records[metadata_id] = metadata
        return metadata

    def get(self, metadata_id: str) -> MetadataT:
        try:
            return self._records[metadata_id]
        except KeyError as exc:
            raise GovernanceRepositoryNotFoundError(
                f"Governance metadata not found: {metadata_id}"
            ) from exc

    def _metadata_id(self, metadata: MetadataT) -> str:
        value = getattr(metadata, self._id_attribute)
        if not isinstance(value, str):
            raise TypeError(f"{self._id_attribute} must be a string")
        return value


class InMemoryPromptInvocationMetadataRepository(
    _InMemoryGovernanceRepository[PromptInvocationMetadata]
):
    def __init__(self) -> None:
        super().__init__("prompt_metadata_id")


class InMemoryModelInvocationMetadataRepository(
    _InMemoryGovernanceRepository[ModelInvocationMetadata]
):
    def __init__(self) -> None:
        super().__init__("model_metadata_id")


class InMemoryCostMetadataRepository(_InMemoryGovernanceRepository[CostMetadata]):
    def __init__(self) -> None:
        super().__init__("cost_metadata_id")


class InMemoryEvaluationMetadataRepository(
    _InMemoryGovernanceRepository[EvaluationMetadata]
):
    def __init__(self) -> None:
        super().__init__("evaluation_run_id")


class InMemoryRegressionMetadataRepository(
    _InMemoryGovernanceRepository[RegressionMetadata]
):
    def __init__(self) -> None:
        super().__init__("regression_run_id")


class InMemoryReviewMetadataRepository(_InMemoryGovernanceRepository[ReviewMetadata]):
    def __init__(self) -> None:
        super().__init__("review_metadata_id")


class InMemoryCorrectionMetadataRepository(
    _InMemoryGovernanceRepository[CorrectionMetadata]
):
    def __init__(self) -> None:
        super().__init__("correction_id")


class InMemoryReanalysisMetadataRepository(
    _InMemoryGovernanceRepository[ReanalysisMetadata]
):
    def __init__(self) -> None:
        super().__init__("reanalysis_metadata_id")


class InMemoryShadowEventMetadataRepository(
    _InMemoryGovernanceRepository[ShadowEventMetadata]
):
    def __init__(self) -> None:
        super().__init__("shadow_event_id")


__all__ = [
    "InMemoryCorrectionMetadataRepository",
    "InMemoryCostMetadataRepository",
    "InMemoryEvaluationMetadataRepository",
    "InMemoryModelInvocationMetadataRepository",
    "InMemoryPromptInvocationMetadataRepository",
    "InMemoryReanalysisMetadataRepository",
    "InMemoryRegressionMetadataRepository",
    "InMemoryReviewMetadataRepository",
    "InMemoryShadowEventMetadataRepository",
]
