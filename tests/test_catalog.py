from labelkit.catalog import Catalog
from labelkit.schemas import ProductLabel, ProductResult

NAME_PT = "Metafield: custom.legal_name_pt [multi_line_text_field]"


def _result(pid="tmp", name="Mandioca"):
    return ProductResult(
        product_id=pid, images=[], ocr={}, labels={"pt": ProductLabel(legal_name=name)}
    )


def test_products_accumulate_and_export_in_order(tmp_path):
    catalog = Catalog(tmp_path)
    catalog.add(_result(name="Mandioca"), "101")
    catalog.add(_result(name="Coxinha"), "102")
    df = catalog.to_dataframe()
    assert df["ID"].tolist() == ["101", "102"]
    assert df[NAME_PT].tolist() == ["Mandioca", "Coxinha"]


def test_same_id_replaces_product(tmp_path):
    catalog = Catalog(tmp_path)
    catalog.add(_result(name="old"), "101")
    catalog.add(_result(name="new"), "101")
    assert catalog.to_dataframe()[NAME_PT].tolist() == ["new"]


def test_edits_and_renames_persist_across_restarts(tmp_path):
    catalog = Catalog(tmp_path)
    item = catalog.add(_result(), "101")
    fields = {"pt": {**item.fields["pt"], "legal_name": "Mandioca congelada"}}
    catalog.update("101", fields, new_id="201")

    reloaded = Catalog(tmp_path)
    assert list(reloaded.items) == ["201"]
    assert reloaded.items["201"].edited
    assert reloaded.items["201"].fields["pt"]["legal_name"] == "Mandioca congelada"


def test_delete(tmp_path):
    catalog = Catalog(tmp_path)
    catalog.add(_result(), "101")
    catalog.delete("101")
    assert Catalog(tmp_path).items == {}


def test_memory_only_catalog_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Catalog(None).add(_result(), "101")
    assert list(tmp_path.iterdir()) == []


def test_edit_keeps_position(tmp_path):
    catalog = Catalog(tmp_path)
    for pid in ("101", "102", "103"):
        item = catalog.add(_result(), pid)
    catalog.update("102", item.fields, new_id="202")
    assert list(catalog.items) == ["101", "202", "103"]
    assert list(Catalog(tmp_path).items) == ["101", "202", "103"]
