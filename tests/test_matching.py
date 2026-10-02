import pandas as pd

from labelkit.tools.matching import candidates, match_all, normalize_name
from tests.conftest import FakeLLM

CATALOG = pd.DataFrame(
    {
        "id": ["1", "2", "3", "4"],
        "name": ["Guaraná 350ml", "Guaraná 2L", "Kit Guaraná 6x350ml", "Pão de Queijo 1kg"],
    }
)


def test_normalize_strips_accents_and_case():
    assert normalize_name("  Pão  de QUEIJO ") == "pao de queijo"


def test_kits_are_excluded_from_candidates():
    assert "3" not in [c.catalog_id for c in candidates("guarana 350ml", CATALOG)]


def test_exact_match_skips_the_llm():
    llm = FakeLLM([])
    result = match_all(["pao de queijo 1kg"], CATALOG, llm)
    assert result.iloc[0]["match_id"] == "4"
    assert result.iloc[0]["method"] == "fuzzy"
    assert llm.calls == []


def test_ambiguous_match_is_reranked_by_llm():
    llm = FakeLLM([{"index": 1, "confidence": 0.9}])
    result = match_all(["guarana lata 2 litros"], CATALOG, llm)
    assert result.iloc[0]["method"] == "llm"
    assert llm.calls == [("structured", "Choice")]
