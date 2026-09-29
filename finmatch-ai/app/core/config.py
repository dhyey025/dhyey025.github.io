"""Application settings loaded from environment variables (prefix ``FINMATCH_``)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Runtime configuration.

    Values are read from environment variables and, if present, a local ``.env``
    file. No secrets are required in Milestone 1; future API keys must be supplied
    via the environment and never committed to source control.
    """

    model_config = SettingsConfigDict(
        env_prefix="FINMATCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "FinMatch AI"
    service_name: str = "finmatch-api"
    environment: Literal["development", "test", "production"] = "development"
    log_level: LogLevel = "INFO"
    # Resolved relative to the working directory (the project root locally, /app in Docker).
    investor_data_path: Path = Path("data/investor_mandates.json")
