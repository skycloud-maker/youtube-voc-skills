"""Inactive governance persistence planning contracts.

This module defines configuration and dependency boundaries for future durable
governance metadata persistence. It does not construct adapters, connect to
databases, execute migrations, or write metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, model_validator

from src.governance.repositories import (
    CorrectionMetadataRepository,
    CostMetadataRepository,
    EvaluationMetadataRepository,
    GovernanceRepositoryConflictError,
    GovernanceRepositoryNotFoundError,
    ModelInvocationMetadataRepository,
    PromptInvocationMetadataRepository,
    ReanalysisMetadataRepository,
    RegressionMetadataRepository,
    ReviewMetadataRepository,
    ShadowEventMetadataRepository,
)


class GovernancePersistenceDisabledError(RuntimeError):
    """Raised when disabled persistence planning contracts are invoked."""


class GovernancePersistenceSettings(BaseModel):
    """Feature flags for future governance persistence wiring."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    backend: Literal["none", "memory", "external"] = "none"
    adapter_registration_enabled: bool = False
    repository_resolution_enabled: bool = False
    metadata_writes_enabled: bool = False
    bootstrap_enabled: bool = False

    @property
    def adapters_can_be_registered(self) -> bool:
        return self.enabled and self.adapter_registration_enabled

    @property
    def repositories_can_be_resolved(self) -> bool:
        return self.enabled and self.repository_resolution_enabled

    @property
    def writes_can_be_attempted(self) -> bool:
        return self.enabled and self.metadata_writes_enabled

    @model_validator(mode="after")
    def _disabled_settings_remain_inert(self) -> "GovernancePersistenceSettings":
        enabled_flags = (
            self.adapter_registration_enabled,
            self.repository_resolution_enabled,
            self.metadata_writes_enabled,
            self.bootstrap_enabled,
        )
        if not self.enabled and (self.backend != "none" or any(enabled_flags)):
            raise ValueError("Governance persistence flags require enabled=true")
        if self.enabled and self.backend == "none" and any(enabled_flags):
            raise ValueError("Enabled governance persistence flags require a non-none backend")
        return self


@dataclass(frozen=True)
class GovernanceRepositoryBundle:
    """Dependency bundle for governance metadata repository ports."""

    prompt_invocations: PromptInvocationMetadataRepository
    model_invocations: ModelInvocationMetadataRepository
    costs: CostMetadataRepository
    evaluations: EvaluationMetadataRepository
    regressions: RegressionMetadataRepository
    reviews: ReviewMetadataRepository
    corrections: CorrectionMetadataRepository
    reanalyses: ReanalysisMetadataRepository
    shadow_events: ShadowEventMetadataRepository


@runtime_checkable
class GovernanceRepositoryProvider(Protocol):
    """Provider boundary for future repository bundle factories."""

    def build_repository_bundle(self) -> GovernanceRepositoryBundle: ...


class GovernanceRepositoryProviderRegistry:
    """Inactive registry boundary for future governance repository providers."""

    def __init__(self, settings: GovernancePersistenceSettings) -> None:
        self._settings = settings
        self._providers: dict[str, GovernanceRepositoryProvider] = {}

    def register(self, name: str, provider: GovernanceRepositoryProvider) -> None:
        if not self._settings.adapters_can_be_registered:
            raise GovernancePersistenceDisabledError("Governance adapter registration is disabled")
        if name in self._providers:
            raise GovernanceRepositoryConflictError(f"Governance provider already registered: {name}")
        self._providers[name] = provider

    def get(self, name: str) -> GovernanceRepositoryProvider:
        if not self._settings.repositories_can_be_resolved:
            raise GovernancePersistenceDisabledError("Governance repository resolution is disabled")
        try:
            return self._providers[name]
        except KeyError as exc:
            raise GovernanceRepositoryNotFoundError(f"Governance provider not found: {name}") from exc


__all__ = [
    "GovernancePersistenceDisabledError",
    "GovernancePersistenceSettings",
    "GovernanceRepositoryBundle",
    "GovernanceRepositoryProvider",
    "GovernanceRepositoryProviderRegistry",
]
