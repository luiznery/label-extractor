from labelkit.pipeline import process_folder
from tests.conftest import FakeLLM

EXTRACTED = {
    "legal_name": "Polpa de morango",
    "ingredients": "polpa integral de morango",
    "nutrition": {"basis": "100ml", "energy_kcal": 11, "sodium_mg": 0.33},
}
TRANSLATED_PT = {
    "legal_name": "Polpa de morango",
    "ingredients": "polpa integral de morango",
}
TRANSLATED_FR = {
    "legal_name": "Pulpe de fraise",
    "ingredients": "pulpe intégrale de fraise",
    "storage": "invented by the model",  # was null in the source: must be dropped
}


def test_pipeline_runs_tools_in_order_and_saves(samples, tmp_path):
    llm = FakeLLM([EXTRACTED, TRANSLATED_PT, TRANSLATED_FR])
    result = process_folder(llm, samples / "strawberry-pulp", tmp_path)

    assert [c[0] for c in llm.calls] == ["vision"] * 3 + ["structured"] * 3
    assert result.product_id == "strawberry-pulp"
    assert result.original.legal_name == "Polpa de morango"
    assert result.labels["pt"].nutrition.salt_g == 0.001  # derived from sodium in code
    fr = result.labels["fr"]
    assert fr.legal_name == "Pulpe de fraise"
    assert fr.storage is None
    assert fr.nutrition == result.labels["pt"].nutrition
    assert (tmp_path / "strawberry-pulp.json").exists()


def test_existing_results_are_not_reprocessed(samples, tmp_path):
    process_folder(
        FakeLLM([EXTRACTED, TRANSLATED_PT, TRANSLATED_FR]), samples / "strawberry-pulp", tmp_path
    )
    llm = FakeLLM([])
    process_folder(llm, samples / "strawberry-pulp", tmp_path)
    assert llm.calls == []


def test_failed_translation_keeps_the_product(samples, tmp_path):
    llm = FakeLLM([EXTRACTED, TRANSLATED_PT, {"legal_name": ["not", "a", "string"]}])
    result = process_folder(llm, samples / "strawberry-pulp", tmp_path)
    assert result.labels["fr"].legal_name == "Polpa de morango"  # original text kept
    assert result.warnings and "fr" in result.warnings[0]
