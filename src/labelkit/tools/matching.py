"""Tool 5: match free-text product names (e.g. supplier invoice lines) to a catalog.

Fast fuzzy retrieval with rapidfuzz, then an optional LLM re-rank of the top candidates for
the ambiguous cases (different sizes, flavours, brands).
"""

import unicodedata

import pandas as pd
from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process

from labelkit.llm import LLM

DEFAULT_EXCLUDE = ("kit", "combo", "promo", "promoção", "promocao")


def normalize_name(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


class Candidate(BaseModel):
    catalog_id: str
    name: str
    score: float


class Choice(BaseModel):
    index: int | None = Field(description="Index of the matching candidate, or null if none.")
    confidence: float = Field(ge=0, le=1)


def candidates(
    query: str, catalog: pd.DataFrame, top_k: int = 5, exclude: tuple[str, ...] = DEFAULT_EXCLUDE
) -> list[Candidate]:
    """Top-k catalog entries by fuzzy similarity. `catalog` needs `id` and `name` columns."""
    usable = catalog[
        ~catalog["name"].map(normalize_name).str.contains("|".join(exclude), regex=True)
    ]
    choices = dict(zip(usable["id"].astype(str), usable["name"].map(normalize_name), strict=True))
    names = dict(zip(usable["id"].astype(str), usable["name"], strict=True))
    hits = process.extract(normalize_name(query), choices, scorer=fuzz.token_set_ratio, limit=top_k)
    return [Candidate(catalog_id=key, name=names[key], score=score / 100) for _, score, key in hits]


def rerank(llm: LLM, query: str, options: list[Candidate]) -> tuple[Candidate | None, float]:
    listing = "\n".join(f"{i}: {c.name}" for i, c in enumerate(options))
    choice = llm.structured(
        system="You match grocery product descriptions to catalog entries. Output JSON only.",
        user=(
            f'Which catalog entry is the same product as "{query}"? Size, flavour and brand must '
            f"match when they are given. Answer null if none match.\n\n{listing}"
        ),
        schema=Choice,
    )
    if choice.index is None or not 0 <= choice.index < len(options):
        return None, choice.confidence
    return options[choice.index], choice.confidence


def match_all(
    queries: list[str], catalog: pd.DataFrame, llm: LLM | None = None, threshold: float = 0.95
) -> pd.DataFrame:
    """Match every query. Confident fuzzy hits skip the LLM; the rest are re-ranked."""
    rows = []
    for query in queries:
        options = candidates(query, catalog)
        best, confidence, method = (
            (options[0], options[0].score, "fuzzy") if options else (None, 0.0, "none")
        )
        if llm and options and best.score < threshold:
            best, confidence = rerank(llm, query, options)
            method = "llm"
        rows.append(
            {
                "query": query,
                "match_id": best.catalog_id if best else None,
                "match_name": best.name if best else None,
                "confidence": round(confidence, 3),
                "method": method,
            }
        )
    return pd.DataFrame(rows)
