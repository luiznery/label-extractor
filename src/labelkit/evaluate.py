"""Field-level accuracy of extracted labels against hand-checked `expected.json` files."""

import pandas as pd
from rapidfuzz import fuzz

from labelkit.schemas import TEXT_FIELDS, Nutrition, ProductLabel
from labelkit.tools.matching import normalize_name
from labelkit.tools.nutrition import _NUTRIENTS, normalize

TEXT_THRESHOLD = 80  # token-set similarity (0-100) to count a text field as correct


def _text_ok(predicted: str | None, expected: str | None) -> bool:
    if predicted is None or expected is None:
        return predicted is expected
    return fuzz.token_set_ratio(normalize_name(predicted), normalize_name(expected)) >= (
        TEXT_THRESHOLD
    )


def _number_ok(predicted: float | None, expected: float | None) -> bool:
    if predicted is None or expected is None:
        return predicted is expected
    return abs(predicted - expected) <= max(0.02 * abs(expected), 0.01)


def score(predicted: ProductLabel, expected: ProductLabel) -> dict[str, bool]:
    scores = {f: _text_ok(getattr(predicted, f), getattr(expected, f)) for f in TEXT_FIELDS}
    if expected.nutrition is None or predicted.nutrition is None:
        scores["nutrition_present"] = predicted.nutrition is expected.nutrition
    p = normalize(predicted.nutrition or Nutrition())
    e = normalize(expected.nutrition or Nutrition())
    if expected.nutrition is not None:
        for nutrient in _NUTRIENTS:
            if nutrient != "sodium_mg":  # salt is the declared value; sodium is an input
                scores[f"nutrition.{nutrient}"] = _number_ok(
                    getattr(p, nutrient), getattr(e, nutrient)
                )
    return scores


def on_label(expected: ProductLabel) -> dict[str, bool]:
    """Which scored fields actually appear on the label (expected value is not null)."""
    present = {f: getattr(expected, f) is not None for f in TEXT_FIELDS}
    if expected.nutrition is None:
        present["nutrition_present"] = False
    else:
        n = normalize(expected.nutrition)
        for nutrient in _NUTRIENTS:
            if nutrient != "sodium_mg":
                present[f"nutrition.{nutrient}"] = getattr(n, nutrient) is not None
    return present


def report(pairs: dict[str, tuple[ProductLabel, ProductLabel]]) -> pd.DataFrame:
    """One row per field, one column per sample, plus overall accuracy."""
    table = pd.DataFrame({name: score(p, e) for name, (p, e) in pairs.items()})
    table["accuracy"] = table.mean(axis=1, skipna=True)
    return table


def summary(pairs: dict[str, tuple[ProductLabel, ProductLabel]]) -> dict[str, float]:
    """Overall accuracy, split into fields printed on the label vs. fields that should be null.

    The split matters: a model that always answers null scores well on the second number and
    zero on the first, while a model that hallucinates does the opposite.
    """
    on, off = [], []
    for predicted, expected in pairs.values():
        present = on_label(expected)
        for field, ok in score(predicted, expected).items():
            (on if present[field] else off).append(ok)
    return {
        "overall": sum(on + off) / len(on + off),
        "fields on the label": sum(on) / len(on),
        "fields not on the label (should be empty)": sum(off) / len(off),
    }
