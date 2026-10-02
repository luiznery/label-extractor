from labelkit.schemas import Nutrition
from labelkit.tools.nutrition import normalize, render


def test_salt_is_derived_from_sodium():
    assert normalize(Nutrition(sodium_mg=400)).salt_g == 1.0


def test_declared_salt_wins_over_sodium():
    assert normalize(Nutrition(salt_g=1.2, sodium_mg=400)).salt_g == 1.2


def test_portion_values_are_scaled_to_100g():
    n = normalize(Nutrition(basis="portion", portion_size=25, energy_kcal=50, fat_g=1.5))
    assert (n.basis, n.portion_size, n.energy_kcal, n.fat_g) == ("100g", None, 200, 6)


def test_render_uses_decimal_comma_and_defaults():
    text = render(Nutrition(energy_kj=694, energy_kcal=163, fat_g=0.28), "pt")
    assert "Valor energético: 694 kJ / 163 kcal" in text
    assert "Gorduras totais: 0,28 g" in text
    assert "Proteínas: Não especificado" in text
    assert "Fibras" not in text  # optional line omitted when unknown


def test_render_french_per_100ml():
    text = render(Nutrition(basis="100ml", energy_kcal=11, fiber_g=0.6), "fr")
    assert text.splitlines()[:2] == ["Déclaration nutritionnelle moyenne", "Pour 100 ml :"]
    assert "Fibres alimentaires: 0,6 g" in text


def test_render_without_nutrition():
    assert render(None, "en") == "Not specified"
