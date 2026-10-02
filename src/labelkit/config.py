from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["ollama", "openai"]

_DEFAULTS: dict[str, dict[str, str]] = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "vision_model": "qwen2.5vl:3b",  # reads the photos
        "text_model": "qwen2.5:3b",  # extraction + translation (beat qwen3:4b on the samples)
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "vision_model": "gpt-4o-mini",
        "text_model": "gpt-4o-mini",
    },
}


def check_languages(languages: list[str]) -> list[str]:
    """Normalise and validate target language codes (see labelkit.i18n)."""
    from labelkit.i18n import LANGUAGE_NAMES

    codes = list(dict.fromkeys(code.strip().lower() for code in languages if code.strip()))
    unknown = [code for code in codes if code not in LANGUAGE_NAMES]
    if unknown or not codes:
        supported = ", ".join(LANGUAGE_NAMES)
        raise ValueError(f"Unsupported or no target language {unknown}; choose from: {supported}")
    return codes


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
    # Target languages, first one first. Env var: LABELKIT_LANGUAGES='["pt","fr","de"]'
    languages: list[str] = ["pt", "fr"]

    @field_validator("languages")
    @classmethod
    def _supported_languages(cls, value: list[str]) -> list[str]:
        return check_languages(value)

    def resolved(self, key: str) -> str:
        value = getattr(self, key)
        return value if value else _DEFAULTS[self.provider][key]
