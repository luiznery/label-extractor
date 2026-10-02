"""One OpenAI-compatible client for both OpenAI and Ollama, with a small disk cache."""

import base64
import hashlib
import io
import json
from pathlib import Path
from typing import TypeVar

from openai import OpenAI
from PIL import Image, ImageOps
from pydantic import BaseModel, ValidationError

from labelkit.config import Settings

T = TypeVar("T", bound=BaseModel)


def encode_image(path: str | Path, max_side: int) -> str:
    """Downscale (CPU models are slow on big images) and return a JPEG data URL."""
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    image.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


class LLM:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        api_key = self.settings.api_key.get_secret_value() if self.settings.api_key else None
        if self.settings.provider == "openai" and not api_key:
            raise ValueError("The OpenAI provider needs OPENAI_API_KEY (env var or .env file).")
        self.client = OpenAI(
            base_url=self.settings.resolved("base_url"),
            api_key=api_key or "ollama",  # Ollama ignores the key but the SDK requires one
            timeout=self.settings.timeout,
        )
        self.vision_model = self.settings.resolved("vision_model")
        self.text_model = self.settings.resolved("text_model")

    # -- caching ---------------------------------------------------------------
    def _cache_path(self, payload: dict) -> Path | None:
        if not self.settings.cache_dir:
            return None
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return Path(self.settings.cache_dir) / f"{key}.txt"

    def _complete(self, **request) -> str:
        cache = self._cache_path(request)
        if cache and cache.exists():
            return cache.read_text(encoding="utf-8")
        response = self.client.chat.completions.create(
            temperature=0, max_tokens=self.settings.max_tokens, **request
        )
        content = (response.choices[0].message.content or "").strip()
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(content, encoding="utf-8")
        return content

    # -- public API ------------------------------------------------------------
    def describe_image(self, prompt: str, image: str | Path) -> str:
        data_url = encode_image(image, self.settings.max_image_side)
        return self._complete(
            model=self.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )

    def structured(self, system: str, user: str, schema: type[T], retries: int = 1) -> T:
        """Ask for JSON matching `schema`; on invalid output, retry with the error message."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
        }
        extra = {}
        if self.settings.reasoning_effort:
            extra["reasoning_effort"] = self.settings.reasoning_effort
        for attempt in range(retries + 1):
            raw = self._complete(
                model=self.text_model, messages=messages, response_format=response_format, **extra
            )
            try:
                return schema.model_validate_json(raw)
            except ValidationError as error:
                if attempt == retries:
                    raise
                messages += [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": f"Invalid JSON for the schema: {error}. Fix it."},
                ]
        raise AssertionError("unreachable")
