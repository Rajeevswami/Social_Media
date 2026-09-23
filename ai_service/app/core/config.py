"""Configuration via environment variables (pydantic-settings).

Nothing secret has a default: if a provider needs a key, the app refuses to
start rather than silently degrading in production.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # -- service identity ------------------------------------------------
    service_name: str = "social-media-ai"
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    # NoDecode: these come from the environment as comma separated strings
    # ("a,b,c"), not JSON arrays — see `_split_csv` below.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8000"]
    )

    # -- auth ------------------------------------------------------------
    # Comma separated list of internal API keys accepted in `X-API-Key`.
    api_keys: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["dev-internal-key-change-me"]
    )

    # -- rate limiting ---------------------------------------------------
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    max_text_length: int = 4000
    max_mood_texts: int = 50

    # -- provider selection ---------------------------------------------
    provider: Literal["openai", "huggingface", "heuristic"] = "heuristic"
    # When the configured provider fails, fall back to the local heuristic
    # model instead of erroring out (moderation must stay available).
    allow_heuristic_fallback: bool = True

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    hf_api_token: str | None = None
    hf_moderation_model: str = "unitary/toxic-bert"
    hf_generation_model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    hf_base_url: str = "https://api-inference.huggingface.co/models"

    # -- outbound HTTP ---------------------------------------------------
    request_timeout_seconds: float = 15.0
    connect_timeout_seconds: float = 3.0
    max_retries: int = 1

    # -- toxicity thresholds --------------------------------------------
    toxicity_threshold: float = 0.60
    spam_threshold: float = 0.70
    confidence_floor: float = 0.0

    @field_validator("api_keys", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("toxicity_threshold", "spam_threshold")
    @classmethod
    def _between_zero_and_one(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("thresholds must be between 0 and 1")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
