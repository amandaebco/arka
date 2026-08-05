from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Manufacturing Knowledge Graph API"
    app_env: str = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "manufacturing_kg"
    postgres_user: str = "manufacturing"
    postgres_password: str = Field(default="manufacturing", repr=False)
    postgres_echo: bool = False

    age_graph_name: str = "manufacturing_kg"
    document_storage_path: Path = Path("data/documents")
    max_document_bytes: int = Field(default=25_000_000, gt=0)

    vertex_ai_project: str = "ebc-cloud-dev-03"
    vertex_ai_location: str = "global"
    vertex_ai_model: str = "gemini-2.5-flash"
    vertex_ai_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    vertex_ai_fallback_enabled: bool = True

    @property
    def database_url(self) -> str:
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
