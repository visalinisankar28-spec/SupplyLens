"""
Application configuration.

All configuration is sourced from environment variables (with sane local
defaults) so the same image can be promoted across environments without
code changes. Never hardcode secrets here.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized, typed application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql+psycopg://stp_user:stp_pass@localhost:5432/stp_db"

    # --- External APIs ---
    scorecard_api_base_url: str = "https://api.scorecard.dev"
    npm_registry_base_url: str = "https://registry.npmjs.org"
    pypi_registry_base_url: str = "https://pypi.org/pypi"
    maven_search_base_url: str = "https://search.maven.org/solrsearch/select"

    # --- HTTP client behaviour ---
    external_api_timeout_seconds: float = 8.0
    external_api_max_retries: int = 2

    # --- Dependency Health Index weights (must sum to 1.0) ---
    dhi_weight_maintenance_activity: float = 0.35
    dhi_weight_release_cadence: float = 0.25
    dhi_weight_community_resilience: float = 0.20
    dhi_weight_security_hygiene: float = 0.20

    # --- DHI category thresholds (0-100 scale) ---
    dhi_threshold_healthy: float = 80.0
    dhi_threshold_stable: float = 60.0
    dhi_threshold_needs_attention: float = 40.0


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (avoids re-parsing env on every call)."""
    return Settings()
