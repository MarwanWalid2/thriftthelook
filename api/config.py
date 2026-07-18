"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration with a safe, zero-key offline default."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    demo_mode: Literal["offline", "live"] = "offline"
    openai_api_key: str | None = None
    openai_sol_model: str | None = None
    openai_luna_model: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ebay_client_id: str | None = None
    ebay_client_secret: str | None = None
    ebay_marketplace: str = "EBAY_US"
    ebay_delivery_zip: str | None = None
    use_gpt_boxes: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
