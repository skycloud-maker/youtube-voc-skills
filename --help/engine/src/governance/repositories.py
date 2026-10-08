"""Storage-neutral repository ports for governance metadata records."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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


class GovernanceRepositoryError(RuntimeError):
    """Base class for governance metadata repository failures."""


class GovernanceRepositoryConflictError(GovernanceRepositoryError):
    """Raised when a create-only governance metadata identity already exists."""


class GovernanceRepositoryNotFoundError(GovernanceRepositoryError):
    """Raised when requested governance metadata does not exist."""


class GovernanceRepositoryIntegrityError(GovernanceRepositoryError):
    """Raised when governance metadata fails storage-neutral integrity checks."""


@runtime_checkable
class PromptInvocationMetadataRepository(Protocol):
    def create(self, metadata: PromptInvocationMetadata) -> PromptInvocationMetadata: ...

    def get(self, prompt_metadata_id: str) -> PromptInvocationMetadata: ...


@runtime_checkable
class ModelInvocationMetadataRepository(Protocol):
    def create(self, metadata: ModelInvocationMetadata) -> ModelInvocationMetadata: ...

    def get(self, model_metadata_id: str) -> ModelInvocationMetadata: ...


@runtime_checkable
class CostMetadataRepository(Protocol):
    def create(self, metadata: CostMetadata) -> CostMetadata: ...

    def get(self, cost_metadata_id: str) -> CostMetadata: ...


@runtime_checkable
class EvaluationMetadataRepository(Protocol):
    def create(self, metadata: EvaluationMetadata) -> EvaluationMetadata: ...

    def get(self, evaluation_run_id: str) -> EvaluationMetadata: ...


@runtime_checkable
class RegressionMetadataRepository(Protocol):
    def create(self, metadata: RegressionMetadata) -> RegressionMetadata: ...

    def get(self, regression_run_id: str) -> RegressionMetadata: ...


@runtime_checkable
class ReviewMetadataRepository(Protocol):
    def create(self, metadata: ReviewMetadata) -> ReviewMetadata: ...

    def get(self, review_metadata_id: str) -> ReviewMetadata: ...


@runtime_checkable
class CorrectionMetadataRepository(Protocol):
    def create(self, metadata: CorrectionMetadata) -> CorrectionMetadata: ...

    def get(self, correction_id: str) -> CorrectionMetadata: ...


@runtime_checkable
class ReanalysisMetadataRepository(Protocol):
    def create(self, metadata: ReanalysisMetadata) -> ReanalysisMetadata: ...

    def get(self, reanalysis_metadata_id: str) -> ReanalysisMetadata: ...


@runtime_checkable
class ShadowEventMetadataRepository(Protocol):
    def create(self, metadata: ShadowEventMetadata) -> ShadowEventMetadata: ...

    def get(self, shadow_event_id: str) -> ShadowEventMetadata: ...
