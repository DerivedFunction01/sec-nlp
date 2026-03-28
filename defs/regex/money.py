import re
import random
from typing import Literal, Optional, Sequence

from defs.regex_lib import build_alternation
from defs.labels import LABELS
from defs.region_regex import MAJOR_CURRENCIES
from defs.number import Number, Strategy, mutate_number, mutate_numbers, format_number

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
        if len(sym) > 0:
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

_UNAMB_NAMES = build_alternation(_unamb_names)
_AMB_NAMES = build_alternation(_amb_names)
_ADJS = build_alternation(_adjs)

_ALPHA_SYM_RE = re.compile(r"[A-Za-z]")

_safe_symbols: list[str] = []
for _sym in _symbols:
    _unescaped = re.sub(r"\\(.)", r"\1", _sym)
    if _ALPHA_SYM_RE.search(_unescaped):
        _safe_symbols.append(rf"(?<!\w){_sym}(?!\w)")
    else:
        _safe_symbols.append(_sym)

_SYMBOLS = build_alternation(_safe_symbols)

_safe_codes: list[str] = []
for _code in _codes:
    _unescaped = re.sub(r"\\(.)", r"\1", _code)
    if _unescaped[-1].isalpha():
        _safe_codes.append(rf"{_code}\b")
    else:
        _safe_codes.append(rf"{_code}(?![A-Za-z])")

_CODES = r"(?:" + "|".join(_safe_codes) + r")"

_NUM = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
_SCALE = r"(?:k|m|mm|b|t|thousand|million|billion|trillion)"
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

_NUMERIC_CORE_RE = re.compile(r"(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)")

MoneyFormatStrategy = Literal[
    "random",
    "raw",
    "commas",
    "magnitude_long",
    "magnitude_short",
    "magnitude_financial",
]

_MONEY_FORMATS_SMALL = ("raw", "commas")
_MONEY_FORMATS_MEDIUM = ("commas", "magnitude_long")
_MONEY_FORMATS_LARGE = ("commas", "magnitude_long", "magnitude_short", "magnitude_financial")

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

def extract_numeric_value(text: str) -> tuple[int | float, str] | None:
    """
    Extract the first numeric literal from a money span.

    Returns (value, matched_text) or None if no numeric core is found.
    """
    if not text:
        return None

    m = _NUMERIC_CORE_RE.search(text)
    if not m:
        return None

    raw = m.group("num")
    value = float(raw.replace(",", ""))
    if value.is_integer():
        return int(value), raw
    return value, raw


def _replace_first_numeric(text: str, new_value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return new_value

    return _NUMERIC_CORE_RE.sub(repl, text, count=1)


def _pick_money_format(value: int | float, rng: random.Random) -> tuple[str, bool]:
    """
    Choose a money formatting style that still looks natural.

    Words are intentionally excluded.
    Returns (strategy, pad_magnitude_decimals).
    """
    magnitude = abs(float(value))
    pad_magnitude_decimals = rng.random() < 0.5

    if magnitude < 1_000:
        return rng.choice(_MONEY_FORMATS_SMALL), False
    if magnitude < 100_000:
        return rng.choice(_MONEY_FORMATS_MEDIUM), pad_magnitude_decimals
    return rng.choice(_MONEY_FORMATS_LARGE), pad_magnitude_decimals


def _normalize_format_strategy(
    value: int | float,
    format_strategy: MoneyFormatStrategy,
    rng: random.Random,
) -> tuple[str, bool]:
    if format_strategy != "random":
        return format_strategy, False
    return _pick_money_format(value, rng)


def mutate_money_span(
    text: str,
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: MoneyFormatStrategy = "random",
    pad_magnitude_decimals: bool = False,
) -> str:
    """
    Mutate the numeric portion of a single money span and reinsert it.
    """
    if rng is None:
        rng = random.Random()

    extracted = extract_numeric_value(text)
    if extracted is None:
        return text

    value, _ = extracted
    mutated = mutate_number(value, strategy=strategy, rng=rng)
    assert isinstance(mutated, Number)
    chosen_format, chosen_pad = _normalize_format_strategy(
        mutated, format_strategy, rng
    )
    formatted = format_number(
        mutated,
        strategy=chosen_format,  # type: ignore
        numeric_only=True,
        pad_magnitude_decimals=pad_magnitude_decimals or chosen_pad,
    )
    return _replace_first_numeric(text, formatted)


def mutate_money_spans(
    spans: Sequence[str],
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: MoneyFormatStrategy = "random",
    pad_magnitude_decimals: bool = False,
) -> list[str]:
    """
    Mutate a batch of money spans.

    When strategy="random", a single paragraph-level strategy is chosen inside
    defs.number.mutate_numbers so related spans stay coherent.
    """
    if rng is None:
        rng = random.Random()

    values: list[int | float] = []
    for span in spans:
        extracted = extract_numeric_value(span)
        if extracted is None:
            continue
        value, raw = extracted
        values.append(value)

    if not values:
        return list(spans)

    mutated_values = mutate_numbers(
        values,
        strategy=strategy,
        int_only=False,
        allow_zero=False,
        allow_negative=False,
        rng=rng,
    )
    if isinstance(mutated_values, tuple):
        mutated_values = mutated_values[0]

    chosen_format, chosen_pad = _normalize_format_strategy(
        mutated_values[0], format_strategy, rng
    )

    out: list[str] = []
    idx = 0
    for span in spans:
        extracted = extract_numeric_value(span)
        if extracted is None:
            out.append(span)
            continue

        mutated = mutated_values[idx]
        idx += 1
        formatted = format_number(
            mutated,
            strategy=chosen_format, # type: ignore
            numeric_only=True,
            pad_magnitude_decimals=pad_magnitude_decimals or chosen_pad,
        )
        out.append(_replace_first_numeric(span, formatted))

    return out
