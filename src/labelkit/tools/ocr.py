"""Tool 1: image -> raw text, using a vision LLM."""

from pathlib import Path

from labelkit import prompts
from labelkit.llm import LLM

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def list_images(folder: str | Path) -> list[Path]:
    return sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


def transcribe(llm: LLM, images: list[str | Path]) -> dict[str, str]:
    """Transcribe each image separately (small models do better with one image at a time)."""
    prompt = prompts.load("ocr")
    return {Path(image).name: llm.describe_image(prompt, image) for image in images}
