from __future__ import annotations
import re
from defs.regex_lib import NUMBER_RANGE_STR, build_alternation, build_regex
from defs.labels import LABELS
from defs.text_cleaner import _NUMERIC_FIRM_CLEANER


# =============================================================================
# EQUITY INDICES
# =============================================================================
_EQ_INDEX_BRANDS = [
    # US
    "S&P",
    "Nasdaq",
    "Dow Jones",
    "Russell",
    "Wilshire",
    "Fortune",
    # Global
    "MSCI",
    "FTSE",
    "Nikkei",
    "TOPIX",
    "Hang Seng",
    "HSI",
    "DAX",
    "Euro Stoxx",
    "CAC",
    "IBEX",
    "SMI",
    "ASX",
    "TSX",
    "Hang Seng",
    "KOSPI",
    "Nifty",
    "Sensex",
    "Bovespa",
    "IPC",
    "MOEX",
    "RTSI",
    "SET",
    "STI",
    "KLCI",
    "PSEi",
    "JCI",
    "VN-Index",
    "TASI",
    "EGX",
    "JSE",
]

_EQ_INDEX_DESCRIPTORS = [
    "Composite",
    "Industrial Average",
    "Total Return",
    "Value",
    "Growth",
    "Developed",
    "Emerging",
    "Frontier",
    r"All[-\s]?Share",
    r"Asia[-\s]?Pacific",
    "World",
    "ACWI",
    "EAFE",
    "Europe",
]

_BRANDS = build_alternation(_EQ_INDEX_BRANDS, sort_longest_first=True)
_DESCRIPTORS = build_alternation(_EQ_INDEX_DESCRIPTORS, sort_longest_first=True)

EQ_INDEX = (
    rf"\b(?:{_BRANDS})"  # brand name
    rf"(?:[-\s]\d+)"  # number (500, 100, 225)
    rf"(?:\s+(?:{_DESCRIPTORS}))?"  # optional descriptor
    rf"(?:\s+index)?\b"  # optional trailing "index"
)

# =============================================================================
# OTHER PROPER_NUM PATTERNS
# =============================================================================
_OTHER_PROPER_NUM = [
    r"\bCOVID[-\s]?\d+\b",  # COVID-19
    r"\b401\(k\)",  # 401(k)
    r"\b403\(b\)",  # 403(b)
    r"\b(?:10|6|8)[-\s]?[KkQq]\b",  # 10-K, 10-Q (as proper form names)
    r"\b[24]0[-\s]?F\b",
    r"\b10[-\s]?K405\b",
    r"\b10[-\s]?KSB\b",
    r"\b10[-\s]?KSB40\b",
    r"\bForever\s+21\b",
]

TITLE_PROPER_NUM = [
    rf"Locals?\s+{NUMBER_RANGE_STR}",
    r"Propositions?\s+{NUMBER_RANGE_STR}",
    r"[Bb]ranch(?:es)?\s+{NUMBER_RANGE_STR}",
    r"Chapters?\s+{NUMBER_RANGE_STR}",
]
# =============================================================================
# COMBINED PATTERN
# =============================================================================
_all_patterns = (
    [EQ_INDEX]  # already specific enough, order matters less
    + _OTHER_PROPER_NUM
)

PROPER_NUM_RE = re.compile(
    build_alternation(_all_patterns, sort_longest_first=True),
    re.IGNORECASE,
)

TITLE_PROPER_NUM_RE = build_regex(TITLE_PROPER_NUM)

def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract PROPER_NUM spans from text.
    Returns (match_text, start, end, label) tuples.
    """
    if not text:
        return []

    results = []
    numeric_firm_spans = _NUMERIC_FIRM_CLEANER.mask_numeric_names(text, mask_text=False)
    for start, end, match_text in numeric_firm_spans:
        results.append((match_text, start, end, LABELS.PROPER_NUM.value))

    for m in PROPER_NUM_RE.finditer(text):
        results.append((m.group(0), m.start(), m.end(), LABELS.PROPER_NUM.value))
    for m in TITLE_PROPER_NUM_RE.finditer(text):
        results.append((m.group(0), m.start(), m.end(), LABELS.PROPER_NUM.value))
    return results
