from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["ollama", "openai"]

_DEFAULTS: dict[str, dict[str, str]] = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "vision_model": "qwen2.5vl:3b",  # reads the photos
        "text_model": "qwen2.5:3b",  # extraction + translation: see README "Results"
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "vision_model": "gpt-4o-mini",
        "text_model": "gpt-4o-mini",
    },
}


class Settings(BaseSettings):
    """Runtime settings, read from env vars (prefix LABELKIT_) or a .env file."""

    model_config = SettingsConfigDict(
        env_prefix="LABELKIT_", env_file=".env", extra="ignore", populate_by_name=True
    )

    provider: Provider = "ollama"
    base_url: str | None = None
    api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LABELKIT_API_KEY", "OPENAI_API_KEY")
    )
    vision_model: str | None = None
    text_model: str | None = None
    # e.g. "none" to switch off "thinking" in reasoning models such as qwen3, which can loop
    # for minutes when combined with JSON-schema output. Not sent when unset.
    reasoning_effort: str | None = None
    # Small models at temperature 0 can get stuck repeating a phrase; cap the output so a
    # loop fails fast (and is retried) instead of running until the timeout.
    max_tokens: int = 2048
    max_image_side: int = 1024
    timeout: float = 600.0
    cache_dir: Path | None = Path(".cache/labelkit")
    languages: list[str] = ["pt", "fr"]

    def resolved(self, key: str) -> str:
        value = getattr(self, key)
        return value if value else _DEFAULTS[self.provider][key]
