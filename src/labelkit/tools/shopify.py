"""Tool 4: ProductResults -> Shopify import CSV, and merge into a store product export."""

from importlib.resources import files
from pathlib import Path

import pandas as pd
import yaml

from labelkit.i18n import TEXT
from labelkit.schemas import ProductLabel, ProductResult
from labelkit.tools.nutrition import render


def load_mapping(path: str | Path | None = None) -> dict:
    source = Path(path) if path else files("labelkit").joinpath("shopify_columns.yaml")
    return yaml.safe_load(source.read_text(encoding="utf-8"))


def label_to_fields(label: ProductLabel, language: str) -> dict[str, str]:
    """Final display strings, with the per-language defaults for missing fields."""
    t = TEXT[language]
    defaults = {
        "allergens": t["no_allergens"],
        "storage": t["default_storage"],
        "usage": t["default_usage"],
        "alcohol_by_volume": "0%",
    }
    fields = {
        key: value or defaults.get(key, t["not_specified"])
        for key, value in label.model_dump(exclude={"nutrition"}).items()
    }
    fields["nutrition"] = render(label.nutrition, language)
    return fields


Fields = dict[str, dict[str, str]]  # language -> field -> display text


def result_fields(result: ProductResult) -> Fields:
    return {language: label_to_fields(label, language) for language, label in result.labels.items()}


def rows_from_fields(
    products: list[tuple[str, Fields]], mapping: dict | None = None
) -> pd.DataFrame:
    """One import row per (product_id, fields); fields may have been edited by hand."""
    mapping = mapping or load_mapping()
    rows = []
    for product_id, fields in products:
        row = {mapping["id_column"]: product_id}
        for language, values in fields.items():
            for field, value in values.items():
                row[mapping["columns"][field].format(lang=language)] = value
        rows.append(row)
    return pd.DataFrame(rows)


def to_rows(results: list[ProductResult], mapping: dict | None = None) -> pd.DataFrame:
    return rows_from_fields([(r.product_id, result_fields(r)) for r in results], mapping)


def merge_into_export(
    store_export: pd.DataFrame, new: pd.DataFrame, mapping: dict | None = None
) -> pd.DataFrame:
    """Copy the new label columns into the store export, keeping only the updated products.

    Shopify only overwrites the columns present in an import file, so the output can be
    re-imported directly.
    """
    mapping = mapping or load_mapping()
    id_col, status_col = mapping["id_column"], mapping["status_column"]
    store = store_export.copy()
    store[id_col] = store[id_col].astype(str)
    new = new.copy()
    new[id_col] = new[id_col].astype(str)

    missing = set(new[id_col]) - set(store[id_col])
    if missing:
        print(f"Warning: {len(missing)} product(s) not in the store export: {sorted(missing)}")

    merged = store[store[id_col].isin(new[id_col])].drop(
        columns=[c for c in new.columns if c != id_col and c in store.columns]
    )
    merged = merged.merge(new, on=id_col, how="left")
    merged[status_col] = "Active"
    return merged
