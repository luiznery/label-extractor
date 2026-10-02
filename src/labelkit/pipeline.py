"""Glue: run the tools in order for one product folder."""

from pathlib import Path

from labelkit.config import Settings
from labelkit.llm import LLM
from labelkit.schemas import ProductResult
from labelkit.tools.extract import extract_label
from labelkit.tools.ocr import list_images, transcribe
from labelkit.tools.translate import translate_label


def process_product(
    llm: LLM, images: list[Path], product_id: str, languages: list[str] | None = None
) -> ProductResult:
    languages = languages or Settings().languages
    ocr = transcribe(llm, images)
    original = extract_label(llm, ocr)
    labels, warnings = {}, []
    for lang in languages:
        try:
            labels[lang] = translate_label(llm, original, lang)
        except ValueError as error:  # includes pydantic ValidationError
            # Keep the product: untranslated text is easy to fix by hand, a lost product isn't.
            labels[lang] = original.model_copy()
            warnings.append(f"Translation to {lang} failed, original text kept: {error}")
    return ProductResult(
        product_id=product_id,
        images=[p.name for p in images],
        ocr=ocr,
        original=original,
        labels=labels,
        warnings=warnings,
    )


def process_folder(
    llm: LLM, folder: Path, output_dir: Path, force: bool = False
) -> ProductResult | None:
    """Process one product folder (named after the product id); resumable via result files."""
    out = output_dir / f"{folder.name}.json"
    if out.exists() and not force:
        return ProductResult.model_validate_json(out.read_text(encoding="utf-8"))
    images = list_images(folder)
    if not images:
        return None
    result = process_product(llm, images, folder.name, llm.settings.languages)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result
