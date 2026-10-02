from labelkit.evaluate import score, summary
from labelkit.schemas import Nutrition, ProductLabel


def test_score_tolerates_wording_and_rounding():
    expected = ProductLabel(
        legal_name="Mandioca congelada", nutrition=Nutrition(energy_kcal=163, salt_g=0.03)
    )
    predicted = ProductLabel(
        legal_name="mandioca  congelada", nutrition=Nutrition(energy_kcal=163.0, sodium_mg=12)
    )
    s = score(predicted, expected)
    assert s["legal_name"] and s["ingredients"]  # equal text; both missing
    assert s["nutrition.energy_kcal"]
    assert s["nutrition.salt_g"]  # 12 mg sodium -> 0.03 g salt


def test_score_flags_hallucinated_fields():
    s = score(ProductLabel(storage="Keep frozen"), ProductLabel())
    assert not s["storage"]


def test_summary_separates_label_fields_from_empty_ones():
    expected = ProductLabel(legal_name="Mandioca")
    always_null = summary({"x": (ProductLabel(), expected)})
    assert always_null["fields on the label"] == 0
    assert always_null["fields not on the label (should be empty)"] == 1
