"""Tool 2: OCR text -> ProductLabel (structured, validated, in the label's own language).

Translation is a separate step: small models copy reliably but get worse when asked to
extract and translate at the same time.
"""

from labelkit import prompts
from labelkit.llm import LLM
from labelkit.schemas import ProductLabel
from labelkit.tools.nutrition import normalize


def extract_label(llm: LLM, ocr: dict[str, str]) -> ProductLabel:
    ocr_text = "\n---\n".join(ocr.values())
    label = llm.structured(
        system=prompts.load("extract_system"),
        user=prompts.load("extract_user").format(ocr_text=ocr_text),
        schema=ProductLabel,
    )
    if label.nutrition:
        label.nutrition = normalize(label.nutrition)
    return label
