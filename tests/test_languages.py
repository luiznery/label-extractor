import pytest
from pydantic import ValidationError

from labelkit.catalog import Catalog
from labelkit.config import Settings
from labelkit.i18n import LANGUAGE_NAMES, TEXT
from labelkit.schemas import Nutrition, ProductLabel, ProductResult
from labelkit.tools.nutrition import render


def test_every_language_has_every_fixed_string():
    assert set(TEXT) == set(LANGUAGE_NAMES)
    for language in TEXT:
        assert TEXT[language].keys() == TEXT["en"].keys(), language


def test_languages_are_normalised_and_validated():
    assert Settings(languages=[" DE", "pt", "de"]).languages == ["de", "pt"]
    with pytest.raises(ValidationError, match="choose from"):
        Settings(languages=["xx"])
    with pytest.raises(ValidationError):
        Settings(languages=[])


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("de", "Fett: 0,28 g"),
        ("es", "Grasas: 0,28 g"),
        ("it", "Grassi: 0,28 g"),
        ("nl", "Vetten: 0,28 g"),
    ],
)
def test_nutrition_block_in_new_languages(language, expected):
    assert expected in render(Nutrition(fat_g=0.28), language)


def test_catalog_mixes_products_with_different_languages(tmp_path):
    def result(languages):
        labels = {lang: ProductLabel(legal_name=f"name-{lang}") for lang in languages}
        return ProductResult(product_id="x", images=[], ocr={}, labels=labels)

    catalog = Catalog(tmp_path)
    catalog.add(result(["pt", "fr"]), "101")
    catalog.add(result(["de"]), "102")
    df = catalog.to_dataframe()
    de_name = "Metafield: custom.legal_name_de [multi_line_text_field]"
    pt_name = "Metafield: custom.legal_name_pt [multi_line_text_field]"
    assert df[de_name].tolist()[1] == "name-de"
    assert df[pt_name].tolist()[0] == "name-pt"
    assert df[pt_name].isna().tolist() == [False, True]  # 102 has no Portuguese
