"""Deterministic nutrition rules: unit conversion and per-language rendering.

These used to live in the prompt. Doing them in code makes them exact and testable.
"""

from labelkit.i18n import TEXT
from labelkit.schemas import Nutrition

SODIUM_TO_SALT = 2.5
_NUTRIENTS = (
    "energy_kj",
    "energy_kcal",
    "fat_g",
    "saturated_fat_g",
    "carbohydrates_g",
    "sugars_g",
    "fiber_g",
    "protein_g",
    "salt_g",
    "sodium_mg",
)


def normalize(nutrition: Nutrition) -> Nutrition:
    """Return a copy expressed per 100 g/ml, with salt derived from sodium if needed."""
    n = nutrition.model_copy()
    if n.basis == "portion" and n.portion_size:
        factor = 100 / n.portion_size
        for field in _NUTRIENTS:
            value = getattr(n, field)
            if value is not None:
                setattr(n, field, round(value * factor, 3))
        n.basis, n.portion_size = "100g", None
    if n.salt_g is None and n.sodium_mg is not None:
        n.salt_g = round(n.sodium_mg * SODIUM_TO_SALT / 1000, 3)
    return n


def _fmt(value: float | None, unit: str, language: str) -> str:
    if value is None:
        return TEXT[language]["not_specified"]
    number = f"{value:g}"
    if language != "en":
        number = number.replace(".", ",")
    return f"{number} {unit}"


def render(nutrition: Nutrition | None, language: str) -> str:
    """Render the EU 'average nutrition declaration' block as plain text."""
    t = TEXT[language]
    if nutrition is None:
        return t["not_specified"]
    n = normalize(nutrition)
    if n.energy_kj is not None and n.energy_kcal is not None:
        energy = f"{_fmt(n.energy_kj, 'kJ', language)} / {_fmt(n.energy_kcal, 'kcal', language)}"
    elif n.energy_kcal is not None:
        energy = _fmt(n.energy_kcal, "kcal", language)
    else:
        energy = _fmt(n.energy_kj, "kJ", language)
    lines = [
        t["nutrition_title"],
        t["per_100ml"] if n.basis == "100ml" else t["per_100g"],
        f"{t['energy']}: {energy}",
        f"{t['fat']}: {_fmt(n.fat_g, 'g', language)}",
        f"- {t['saturated_fat']}: {_fmt(n.saturated_fat_g, 'g', language)}",
        f"{t['carbohydrates']}: {_fmt(n.carbohydrates_g, 'g', language)}",
        f"- {t['sugars']}: {_fmt(n.sugars_g, 'g', language)}",
        f"{t['protein']}: {_fmt(n.protein_g, 'g', language)}",
        f"{t['salt']}: {_fmt(n.salt_g, 'g', language)}",
    ]
    if n.fiber_g is not None:  # optional in the EU declaration
        lines.append(f"{t['fiber']}: {_fmt(n.fiber_g, 'g', language)}")
    return "\n".join(lines)
