from pathlib import Path

import pytest

from labelkit.config import Settings

SAMPLES = Path(__file__).parents[1] / "samples"


class FakeLLM:
    """Stands in for labelkit.llm.LLM: returns canned responses, records calls."""

    def __init__(self, structured_responses: list):
        self.settings = Settings(cache_dir=None)
        self.vision_model = self.text_model = "fake"
        self.responses = list(structured_responses)
        self.calls: list[tuple[str, str]] = []

    def describe_image(self, prompt, image):
        self.calls.append(("vision", str(image)))
        return f"text of {Path(image).name}"

    def structured(self, system, user, schema, retries=1):
        self.calls.append(("structured", schema.__name__))
        return schema.model_validate(self.responses.pop(0))


@pytest.fixture
def samples() -> Path:
    return SAMPLES
