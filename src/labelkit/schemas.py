from typing import Literal

from pydantic import BaseModel, Field

TEXT_FIELDS = (
    "legal_name",
    "ingredients",
    "allergens",
    "net_quantity",
    "storage",
    "usage",
    "responsible_operator",
    "country_of_origin",
    "alcohol_by_volume",
)


class Nutrition(BaseModel):
    """Nutrition facts exactly as printed. Normalisation to per-100 happens in code."""

    basis: Literal["100g", "100ml", "portion"] = Field(
        default="100g", description="What the printed values refer to."
    )
    portion_size: float | None = Field(
        default=None, description="Portion size in g or ml, only when basis is 'portion'."
    )
    energy_kj: float | None = None
    energy_kcal: float | None = None
    fat_g: float | None = None
    saturated_fat_g: float | None = None
    carbohydrates_g: float | None = None
    sugars_g: float | None = Field(default=None, description="Total sugars, NOT added sugars.")
    fiber_g: float | None = None
    protein_g: float | None = None
    salt_g: float | None = None
    sodium_mg: float | None = None


class ProductLabel(BaseModel):
    """EU food-label fields. None means 'not on the label'; defaults are applied later."""

    legal_name: str | None = Field(default=None, description="Legal/commercial product name.")
    ingredients: str | None = Field(default=None, description="Ingredient list, label order.")
    allergens: str | None = Field(default=None, description="Allergen statements, verbatim.")
    net_quantity: str | None = Field(default=None, description="Net weight or volume.")
    storage: str | None = Field(default=None, description="Storage conditions.")
    usage: str | None = Field(default=None, description="Instructions for use / preparation.")
    responsible_operator: str | None = Field(
        default=None, description="Manufacturer, importer or distributor name and address."
    )
    country_of_origin: str | None = None
    alcohol_by_volume: str | None = None
    nutrition: Nutrition | None = None


class TextFields(BaseModel):
    """The translatable subset of ProductLabel."""

    legal_name: str | None = None
    ingredients: str | None = None
    allergens: str | None = None
    net_quantity: str | None = None
    storage: str | None = None
    usage: str | None = None
    responsible_operator: str | None = None
    country_of_origin: str | None = None
    alcohol_by_volume: str | None = None


class ProductResult(BaseModel):
    product_id: str
    images: list[str]
    ocr: dict[str, str]
    original: ProductLabel | None = Field(
        default=None, description="Fields as extracted, in the label's own language."
    )
    labels: dict[str, ProductLabel] = Field(description="Label per language code.")
    warnings: list[str] = Field(default_factory=list, description="Steps that need a review.")
