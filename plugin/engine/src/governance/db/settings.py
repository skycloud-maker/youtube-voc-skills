"""Settings for the optional governance database scaffold."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from src.governance.persistence import GovernancePersistenceSettings


class GovernanceDatabaseSettings(BaseModel):
    """Database settings that remain inert unless explicitly enabled."""

    enabled: bool = False
    migration_dir: Path = Path("migrations")
    migration_naming_convention: str = "YYYYMMDDHHMMSS_description.sql"
    bootstrap_on_startup: bool = False


class GovernanceSettings(BaseModel):
    """Top-level governance control-plane settings."""

    enabled: bool = False
    database: GovernanceDatabaseSettings = Field(default_factory=GovernanceDatabaseSettings)
    persistence: GovernancePersistenceSettings = Field(default_factory=GovernancePersistenceSettings)

    @property
    def database_runtime_enabled(self) -> bool:
        return self.enabled and self.database.enabled

    @property
    def database_bootstrap_enabled(self) -> bool:
        return self.database_runtime_enabled and self.database.bootstrap_on_startup

    @property
    def persistence_runtime_enabled(self) -> bool:
        return self.enabled and self.persistence.enabled
