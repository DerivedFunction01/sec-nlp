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
        _symbols.append(re.escape(sym))
    adj = props.get("adj")
    if adj:
        _adjs.append(re.escape(adj))
    amb = set(props.get("amb_names", []))
    for name in props.get("names", []):
        if name in amb:
            _amb_names.append(re.escape(name))
        else:
            _unamb_names.append(re.escape(name))

_UNAMB_NAMES = build_alternation(_unamb_names)  # safe alone: "dollar", "euro"
_AMB_NAMES = build_alternation(_amb_names)  # only safe with adj: "pound", "yen"

_SYMBOLS = build_alternation(_symbols)
_CODES = build_alternation(_codes)
_ADJS = build_alternation(_adjs)

_NUM = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
_SCALE = r"(?:k|m|b|t|thousand|million|billion|trillion)"
_NUM_WITH_SCALE = rf"(?:{_NUM})(?:\s*{_SCALE})?"

# Examples matched:
#   $5, €2.5m, USD 10, 10 USD, 10 dollars, US dollars 10, British pounds 5
MONEY_RE = re.compile(
    rf"(?:"
    # Negative with minus sign: -$10, -USD 10
    rf"-\s*(?:{_SYMBOLS})\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"
    rf"|-\s*(?:{_CODES})\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"
    rf"|"
    # Parenthetical negative or plain symbol prefix: ($10), $10, $(10)
    rf"(?:\()\s*(?:{_SYMBOLS})\s*{_NUM_WITH_SCALE}\s*(?:\))?"
    rf"|"
    rf"(?:{_SYMBOLS})\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"
    rf"|"
    # Code prefix: USD 10, EUR (10)
    rf"(?:{_CODES})\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?" rf"|"
    # Number + code suffix: 10 USD, (10) EUR
    rf"\(?\s*{_NUM_WITH_SCALE}\s*\)?\s*(?:{_CODES})" rf"|"
    # Number + scale + unambiguous name: 10 dollars, 10 million euros
    rf"\(?\s*{_NUM_WITH_SCALE}\s*\)?\s*(?:{_UNAMB_NAMES})" rf"|"
    # Number + scale + code + scale: 10 million USD (scale before code)
    rf"\(?\s*{_NUM_WITH_SCALE}\s*\)?\s*(?:{_CODES})" rf"|"
    # Adj + ambiguous name + number: british pounds 5, japanese yen 10
    rf"(?:{_ADJS})\s+(?:{_AMB_NAMES})\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?" rf"|"
    # Adj + ambiguous name (suffix number): 5 british pounds
    rf"\(?\s*{_NUM_WITH_SCALE}\s*\)?\s*(?:{_ADJS})\s+(?:{_AMB_NAMES})" rf")",
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


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Extract MONEY spans from text using money-specific rules.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []

    for m in MONEY_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.MONEY.value))

    for m in PRICE_OF_RE.finditer(text):
        money_span = m.span("money")
        spans.append((money_span[0], money_span[1], LABELS.MONEY.value))

    for m in PRICE_PER_RE.finditer(text):
        money_span = m.span("money")
        spans.append((money_span[0], money_span[1], LABELS.MONEY.value))

    for m in PRICE_SLASH_RE.finditer(text):
        money_span = m.span("money")
        spans.append((money_span[0], money_span[1], LABELS.MONEY.value))

    return spans
