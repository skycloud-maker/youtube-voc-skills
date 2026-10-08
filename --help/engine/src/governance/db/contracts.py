"""Storage-neutral contracts for optional governance database bootstrap."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from src.governance.db.settings import GovernanceSettings


class GovernanceDatabaseDisabledError(RuntimeError):
    """Raised when code attempts to bootstrap a disabled governance database."""


class GovernanceDatabaseBootstrapRequest(BaseModel):
    """Explicit bootstrap request; creating it does not touch the filesystem."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    migration_dir: Path
    migration_naming_convention: str
    bootstrap_on_startup: bool


@runtime_checkable
class GovernanceDatabaseBootstrapper(Protocol):
    """Abstraction boundary for future database bootstrap implementations."""

    def bootstrap(self, request: GovernanceDatabaseBootstrapRequest) -> None: ...


def build_bootstrap_request(settings: GovernanceSettings) -> GovernanceDatabaseBootstrapRequest:
    """Build a bootstrap request only when governance database runtime is enabled."""

    if not settings.database_runtime_enabled:
        raise GovernanceDatabaseDisabledError("Governance database is disabled")
    return GovernanceDatabaseBootstrapRequest(
        migration_dir=settings.database.migration_dir,
        migration_naming_convention=settings.database.migration_naming_convention,
        bootstrap_on_startup=settings.database.bootstrap_on_startup,
    )
