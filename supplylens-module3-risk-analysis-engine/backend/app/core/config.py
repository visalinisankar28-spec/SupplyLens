"""Environment-driven settings, shared across all SupplyLens modules."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://supplylens:supplylens@localhost:5432/supplylens"
    osv_api_base_url: str = "https://api.osv.dev/v1"
    scorecard_api_base_url: str = "https://api.securityscorecards.dev"
    environment: str = "development"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
