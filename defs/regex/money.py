import re
from defs.regex_lib import build_alternation
from defs.labels import LABELS
from defs.region_regex import MAJOR_CURRENCIES

# =============================================================================
# MONEY REGEX (uses region_regex currency definitions)
# =============================================================================

_symbols: list[str] = []
_codes: list[str] = []
_adjs: list[str] = []

_unamb_names: list[str] = []
_amb_names: list[str] = []

for code, props in MAJOR_CURRENCIES.items():
    _codes.append(re.escape(code))
    for sym in props.get("symbols", []):
        if len(sym) > 0: _symbols.append(re.escape(sym))
    adj = props.get("adj")
    if adj:
        _adjs.append(re.escape(adj))
    amb = set(props.get("amb_names", []))
    for name in props.get("names", []):
        if name in amb:
            _amb_names.append(re.escape(name))
        else:
            _unamb_names.append(re.escape(name))

_UNAMB_NAMES = build_alternation(_unamb_names)
_AMB_NAMES = build_alternation(_amb_names)
_SYMBOLS = build_alternation(_symbols)
_ADJS = build_alternation(_adjs)

# Word-bounded codes: prevents "EUR" matching inside "Euro"
_CODES = r"(?:" + "|".join(_codes) + r")\b"

_NUM = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
_SCALE = r"(?:k|m|b|t|thousand|million|billion|trillion)"
_NUM_WITH_SCALE = rf"(?:{_NUM})(?:\s*{_SCALE})?"

# --------------------------------------------------------------------------
# Individual sub-patterns (each independently testable / tweakable)
# --------------------------------------------------------------------------

# -$10, -€2.5m
_NEG_SYMBOL = rf"-\s*(?:{_SYMBOLS})\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"

# -USD 10, -EUR (10)
_NEG_CODE = rf"-\s*{_CODES}\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"

# ($10), $(10)  — opening paren required, closing optional
_PAREN_SYMBOL = rf"\(\s*(?:{_SYMBOLS})\s*{_NUM_WITH_SCALE}\s*\)?"

# $10, €2.5m, $(10)
_SYMBOL_PREFIX = rf"(?:{_SYMBOLS})\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"

# USD 10, EUR (10)
_CODE_PREFIX = rf"{_CODES}\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"

# 10 USD, (10) EUR
_NUM_CODE_SUFFIX = rf"\(?\s*{_NUM_WITH_SCALE}\s*\)?\s*{_CODES}"

# 10 dollars, 10 million euros
_NUM_UNAMB_NAME = rf"\(?\s*{_NUM_WITH_SCALE}\s*\)?\s*(?:{_UNAMB_NAMES})"

# british pounds 5, japanese yen 10
_ADJ_AMB_NAME_PREFIX = (
    rf"(?:{_ADJS})\s+(?:{_AMB_NAMES})\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"
)

# 5 british pounds
_ADJ_AMB_NAME_SUFFIX = (
    rf"\(?\s*{_NUM_WITH_SCALE}\s*\)?\s*(?:{_ADJS})\s+(?:{_AMB_NAMES})"
)

# --------------------------------------------------------------------------
# Combined pattern — order matters: more specific before more general
# --------------------------------------------------------------------------
MONEY_RE = re.compile(
    rf"(?:"
    rf"{_NEG_SYMBOL}"
    rf"|{_NEG_CODE}"
    rf"|{_PAREN_SYMBOL}"
    rf"|{_SYMBOL_PREFIX}"
    rf"|{_CODE_PREFIX}"
    rf"|{_NUM_CODE_SUFFIX}"
    rf"|{_NUM_UNAMB_NAME}"
    rf"|{_ADJ_AMB_NAME_PREFIX}"
    rf"|{_ADJ_AMB_NAME_SUFFIX}"
    rf")",
    re.IGNORECASE,
)

PRICE_OF_RE = re.compile(
    rf"\bprice\s+of\s+(?:the\s+)?(?P<money>{MONEY_RE.pattern})",
    re.IGNORECASE,
)
PRICE_PER_RE = re.compile(
    rf"\b(?P<money>{MONEY_RE.pattern})\s+per\s+(?P<unit>[A-Za-z][\w-]*(?:\s+[A-Za-z][\w-]*){{0,2}})",
    re.IGNORECASE,
)
PRICE_SLASH_RE = re.compile(
    rf"\b(?P<money>{MONEY_RE.pattern})\s*/\s*(?P<unit>[A-Za-z][\w-]*(?:\s+[A-Za-z][\w-]*){{0,2}})",
    re.IGNORECASE,
)


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract MONEY spans from text using money-specific rules.
    Returns (match_text, start, end, label) tuples.
    """
    if not text:
        return []

    spans: list[tuple[str, int, int, str]] = []

    for m in MONEY_RE.finditer(text):
        spans.append((m.group(0), m.start(), m.end(), LABELS.MONEY.value))

    for m in PRICE_OF_RE.finditer(text):
        money_span = m.span("money")
        spans.append(
            (m.group("money"), money_span[0], money_span[1], LABELS.MONEY.value)
        )

    for m in PRICE_PER_RE.finditer(text):
        money_span = m.span("money")
        spans.append(
            (m.group("money"), money_span[0], money_span[1], LABELS.MONEY.value)
        )

    for m in PRICE_SLASH_RE.finditer(text):
        money_span = m.span("money")
        spans.append(
            (m.group("money"), money_span[0], money_span[1], LABELS.MONEY.value)
        )

    return spans
