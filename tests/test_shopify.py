import pandas as pd

from labelkit.schemas import ProductLabel, ProductResult
from labelkit.tools.shopify import load_mapping, merge_into_export, to_rows

COL = "Metafield: custom.legal_name_{lang} [multi_line_text_field]"


def _result(pid="101"):
    return ProductResult(
        product_id=pid,
        images=[],
        ocr={},
        labels={"pt": ProductLabel(legal_name="Mandioca"), "fr": ProductLabel(legal_name="Manioc")},
    )


def test_rows_have_one_column_per_field_and_language():
    row = to_rows([_result()]).iloc[0]
    mapping = load_mapping()
    assert len(row) == 1 + 2 * len(mapping["columns"])
    assert row[COL.format(lang="fr")] == "Manioc"
    assert row["Metafield: custom.allergens_pt [multi_line_text_field]"] == (
        "Nenhum alérgeno mencionado"
    )


def test_merge_keeps_only_updated_products_and_activates_them():
    store = pd.DataFrame(
        {
            "ID": [101, 102],
            "Title": ["Cassava 1kg", "Other"],
            COL.format(lang="pt"): ["old", "keep"],
            "Status": ["Draft", "Draft"],
        }
    )
    merged = merge_into_export(store, to_rows([_result("101")]))
    assert merged["ID"].tolist() == ["101"]
    assert merged["Title"].iloc[0] == "Cassava 1kg"
    assert merged[COL.format(lang="pt")].iloc[0] == "Mandioca"
    assert merged["Status"].iloc[0] == "Active"
