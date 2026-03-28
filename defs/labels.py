from enum import Enum

class LABELS(Enum):
    # --- Counts ---
    LABOR = "LABOR"  # employee counts, union members, hires/fires, job cuts
    LOCATION_COUNT = "LOCATION_COUNT"  # facilities + geographic coverage (stores, regions, offices)
    ENTITY_COUNT =  "ENTITY_COUNT"  # products, customers, segments, companies, unions, debts, markets
    SHARE = "SHARE"  # shares, stock units, equity counts

    # --- Quantities ---
    MONEY = "MONEY"  # $100, EUR 50, 10 per barrel/hour
    QUANTITY = "QUANTITY"  # barrels, tons, sq ft, basis points, meters

    # --- Time ---
    TIME = "TIME"  # 2001, January 1 2020, 10 days, 5-year, Q3 2002, fiscal 1997

    # --- Percentages ---
    PCT_CHANGE = "PCT_CHANGE"  # 10% increase, reduction of 5%
    PCT_RATE = "PCT_RATE"  # 10% interest rate, exchange rate of 5%
    PCT_OTHER = "PCT_OTHER"  # 10% coverage, 5% unionized, 10% turnover

    # --- Location / Info ---
    REFERENCE = "REFERENCE"  # Exhibit 10.2, Note 5, ASC 845-12, Page 10, p. 5
    ADDRESS = "ADDRESS"  # 123 Main St, Suite 200, zip codes, phone numbers

    # --- Discard ---
    NOISE = "NOISE"  # standalone artifacts with no semantic value, bullets, etc
    PROPER_NUM = "PROPER_NUM"  # 3M, 7-Eleven, Fortune 500, B-52, COVID-19, 401(k), Zero Corp, Local 50, proposition 50


from typing import Optional, Union
from defs.text_cleaner import clean_text
import inspect

# Import modules
import defs.regex.money as money
import defs.regex.percent as percent
import defs.regex.quantity as quantity
import defs.regex.address as address
import defs.regex.ref as ref
import defs.regex.proper as proper
import defs.regex.shares as shares
import defs.regex.time as time
import defs.regex.labor as labor
import defs.regex.entity as entity
import defs.regex.location as location

EXTRACTION_PIPELINE = [
    (proper.extract_spans, 1),  # 7 Eleven employees
    (ref.extract_spans, 1),
    (money.extract_spans, 1),
    (percent.extract_spans, 1),
    (quantity.extract_spans, 1),
    (location.extract_spans, 2),  # 18102 in China
    (entity.extract_spans, 3),  # 200 programs , 1000 employee contracts
    (shares.extract_spans, 4),  # 18102 shares of common stock, 2024 shares
    (labor.extract_high_confidence_spans, 5),  # 1000 employees
    (address.extract_spans, 6),  # Bethlehem, 18102
    (time.extract_spans, 7),  # 2024, 2024 contract, 2024 interest rate swap.
    (labor.extract_spans, 8),
]


def _mask_claimed(text: str, claimed: list[tuple[str, int, int, str, int]]) -> str:
    """Replace already-claimed character ranges with spaces so later extractors can't overlap them."""
    chars = list(text)
    for _, start, end, _, _ in claimed:
        for i in range(start, end):
            chars[i] = "~"
    return "".join(chars)


def process_match(text: str, cik: Optional[Union[str, int]] = None, max_emp_count: Optional[int] = None):
    text = clean_text(text, cik)
    print(text)
    all_spans: list[tuple[str, int, int, str, int]] = []

    context_kwargs = {
        "max_emp_count": max_emp_count,
        "already_claimed": all_spans,
    }

    for extract_func, tier in EXTRACTION_PIPELINE:
        sig = inspect.signature(extract_func)
        valid_kwargs = {k: v for k, v in context_kwargs.items() if k in sig.parameters}

        # Mask claimed regions so extractors never see already-tagged text
        masked_text = _mask_claimed(text, all_spans)
        extracted = extract_func(masked_text, **valid_kwargs)

        for match_text, start, end, label in extracted:
            if not any(not (end <= s or start >= e) for _, s, e, _, _ in all_spans):
                # Slice from original text so the real characters are preserved
                span_text = text[start:end].replace("<", "").replace(">", "")
                all_spans.append((span_text, start, end, label, tier))

    all_spans.sort(key=lambda x: x[1])

    # Create a reverse map to translate indices to match the text without angle brackets
    reverse_map = []
    stripped_idx = 0
    for char in text:
        reverse_map.append(stripped_idx)
        if char not in "<>":
            stripped_idx += 1
    reverse_map.append(stripped_idx)  # Cover the length of the string

    return [(t, reverse_map[s], reverse_map[e], l) for t, s, e, l, _ in all_spans]
