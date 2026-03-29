from __future__ import annotations

import random

from defs.fx import find_fx_hits, mutate_fx_text
from defs.region_regex import MAJOR_CURRENCIES


SAMPLES = [
    "The company operates in Poland, through its Polish subsidiary, and reports in Polish zloty.",
    "Europe, Germany, Euro, Munich, German",
    "Korean won 500 british pounds of sand",
    "We generated revenue in USD and shipped from Shenzhen, China.",
    "The firm mentioned Japanese yen, Tokyo, and Japanese operations.",
    (
        "We manage FX risk through Euro forward contracts, cross-currency swaps, and "
        "derivatives tied to exchange rates between the euro, dollar, yen, and "
        "renminbi. As of quarter end, EUR/USD was 1.09, USD/JPY was 152.40, "
        "GBP/EUR was 1.17, and CNY/USD was 0.14. A German subsidiary in Munich "
        "hedges $125.4 million of exposures from Chinese operations in Shenzhen, "
        "while the treasury team monitors volatility against the Polish zloty, "
        "British pound, and ¥8.2 billion in short-term receivables. The hedge "
        "book also tracks €42.7 million, £31.5 million, and C$19.8 million in "
        "notional value across the quarter."
    ),
    (
        "The desk quoted USD/MXN at 16.78, EUR/CHF at 0.97, and JPY/USD at 0.0066 "
        "while funding ¥240 million in inventory, €8.4 million in receivables, "
        "and $11.2 million in payables across Frankfurt, Shanghai, and São Paulo."
    ),
]


def demo_sentence(sentence: str, seed: int = 0) -> None:
    rng = random.Random(seed)
    print("\n" + "=" * 80)
    print("INPUT")
    print(sentence)

    hits = find_fx_hits(sentence)
    print("\nHITS")
    for hit in hits:
        print(
            f"  - {hit.surface!r} | kind={hit.kind} | nation={hit.nation_code} | currency={hit.currency_code}"
        )

    mutated, metadata = mutate_fx_text(sentence, rng=rng, return_metadata=True)
    print("\nMUTATED")
    print(mutated)

    print("\nMETADATA")
    print(metadata)


def demo_metadata() -> None:
    print("\n" + "=" * 80)
    print("CURRENCY LOCATION TERMS")
    for code in ["PLN", "EUR", "USD", "CNY"]:
        terms = MAJOR_CURRENCIES[code].get("locations", [])
        print(f"{code}: {terms[:12]}")


def main() -> None:
    demo_metadata()
    for idx, sentence in enumerate(SAMPLES):
        demo_sentence(sentence, seed=idx)


if __name__ == "__main__":
    main()
