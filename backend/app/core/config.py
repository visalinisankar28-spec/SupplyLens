"""Central app configuration, loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "SupplyLens"
    database_url: str = "postgresql+psycopg2://supplylens:supplylens@localhost:5432/supplylens"
    max_sbom_upload_size_mb: int = 20
    cors_allowed_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_prefix = "SUPPLYLENS_"


settings = Settings()
