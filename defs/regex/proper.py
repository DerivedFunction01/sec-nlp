# proper_num.py
import re
import pandas as pd
from pathlib import Path
from defs.regex_lib import build_alternation


# =============================================================================
# NUMERIC FIRM NAMES
# =============================================================================
def _load_numeric_firms(path: str = "data/numeric_firm_names.csv") -> list[str]:
    try:
        df = pd.read_csv(path)
        # Assume first column is the firm name
        col = df.columns[0]
        return df[col].dropna().str.strip().tolist()
    except Exception as e:
        print(f"⚠️  Could not load numeric firms from {path}: {e}")
        return []


_NUMERIC_FIRMS_RAW = _load_numeric_firms()
_NUMERIC_FIRMS_ESCAPED = [re.escape(f) for f in _NUMERIC_FIRMS_RAW]

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
]

# =============================================================================
# COMBINED PATTERN
# =============================================================================
# Note: numeric firms use sort_longest_first to prevent partial matches
# (e.g. "7 Eleven" before "7")
_all_patterns = (
    _NUMERIC_FIRMS_ESCAPED  # longest-first sort handles partial match risk
    + [EQ_INDEX]  # already specific enough, order matters less
    + _OTHER_PROPER_NUM
)

PROPER_NUM_RE = re.compile(
    build_alternation(_all_patterns, sort_longest_first=True),
    re.IGNORECASE,
)
