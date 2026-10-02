"""Tool 3: translate a ProductLabel's text fields; nutrition numbers are copied as-is."""

from labelkit import prompts
from labelkit.i18n import LANGUAGE_NAMES
from labelkit.llm import LLM
from labelkit.schemas import ProductLabel, TextFields


def translate_label(llm: LLM, label: ProductLabel, target: str) -> ProductLabel:
    fields = TextFields.model_validate(label.model_dump(exclude={"nutrition"}))
    if not any(fields.model_dump().values()):
        return label.model_copy()
    # Plain lines in, JSON out: given JSON in, small models tend to echo it untranslated.
    lines = "\n".join(f"{key}: {value}" for key, value in fields if value is not None)
    target_name = LANGUAGE_NAMES[target]
    translated = llm.structured(
        system=prompts.load("translate_system").format(target=target_name),
        user=prompts.load("translate_user").format(target=target_name, fields=lines),
        schema=TextFields,
    )
    # Never let the model fill a field that was empty in the source.
    values = {k: v if getattr(fields, k) is not None else None for k, v in translated}
    return ProductLabel(**values, nutrition=label.nutrition)
