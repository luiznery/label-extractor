"""A small editable product catalog: extraction results plus manual edits, exported to CSV.

Stored as one JSON file per product, so work survives restarts and is easy to inspect.
With `directory=None` it lives in memory only (e.g. one per visitor on a public demo).
"""

import re
import time
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from labelkit.schemas import ProductResult
from labelkit.tools.shopify import Fields, result_fields, rows_from_fields


class CatalogItem(BaseModel):
    product_id: str
    fields: Fields
    edited: bool = False
    added_at: float = 0.0  # keeps catalog order stable across edits and restarts
    source: ProductResult | None = None  # the raw extraction, kept for traceability


def _filename(product_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", product_id) + ".json"


class Catalog:
    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory) if directory else None
        self.items: dict[str, CatalogItem] = {}
        if self.directory and self.directory.exists():
            loaded = [
                CatalogItem.model_validate_json(path.read_text(encoding="utf-8"))
                for path in self.directory.glob("*.json")
            ]
            self.items = {i.product_id: i for i in sorted(loaded, key=lambda i: i.added_at)}

    def _save(self, item: CatalogItem) -> None:
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / _filename(item.product_id)
            path.write_text(item.model_dump_json(indent=2), encoding="utf-8")

    def _remove_file(self, product_id: str) -> None:
        if self.directory:
            (self.directory / _filename(product_id)).unlink(missing_ok=True)

    def add(self, result: ProductResult, product_id: str | None = None) -> CatalogItem:
        """Add an extraction result; an existing product with the same ID is replaced."""
        product_id = (product_id or result.product_id).strip()
        item = CatalogItem(
            product_id=product_id,
            fields=result_fields(result),
            source=result,
            added_at=time.time(),
        )
        self.items.pop(product_id, None)  # re-adding moves it to the end
        self.items[product_id] = item
        self._save(item)
        return item

    def update(self, product_id: str, fields: Fields, new_id: str | None = None) -> CatalogItem:
        """Save manual edits, optionally renaming the product ID. Keeps the product's position."""
        new_id = (new_id or product_id).strip()
        item = self.items[product_id].model_copy(
            update={"product_id": new_id, "fields": fields, "edited": True}
        )
        if new_id != product_id:
            self._remove_file(product_id)
            if new_id in self.items:  # renaming onto another product replaces it
                self.delete(new_id)
        self.items = {
            (new_id if key == product_id else key): (item if key == product_id else value)
            for key, value in self.items.items()
        }
        self._save(item)
        return item

    def delete(self, product_id: str) -> None:
        self.items.pop(product_id, None)
        self._remove_file(product_id)

    def to_dataframe(self) -> pd.DataFrame:
        return rows_from_fields([(i.product_id, i.fields) for i in self.items.values()])
