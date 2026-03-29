import math
import re
import random
from typing import Literal, Optional, Sequence

from defs.regex_lib import build_alternation, build_compound, build_regex
from defs.labels import LABELS
from defs.fx import swap_currency_surface
from defs.regex.entity import FINANCIAL_INSTRUMENTS
from defs.region_regex import MAJOR_CURRENCIES
from defs.number import Number, Strategy, mutate_number, mutate_numbers, format_number

# =============================================================================
# MONEY REGEX (uses region_regex currency definitions)
# =============================================================================

_prefix_symbols: list[str] = []
_prefix_amb_symbols: list[str] = []
_prefix_exact_symbols: list[str] = []
_suffix_symbols: list[str] = []
_suffix_amb_symbols: list[str] = []
_suffix_exact_symbols: list[str] = []
_codes: list[str] = []
_adjs: list[str] = []

_unamb_names: list[str] = []
_amb_names: list[str] = []

for code, props in MAJOR_CURRENCIES.items():
    _codes.append(re.escape(code))
    amb_symbols = set(props.get("amb_symbols", []))
    suffix_currency = bool(props.get("suffix"))
    for sym in props.get("exact_symbols", []):
        if len(sym) > 0:
            if suffix_currency:
                _suffix_exact_symbols.append(re.escape(sym))
            else:
                _prefix_exact_symbols.append(re.escape(sym))
    for sym in props.get("symbols", []):
        if len(sym) > 0:
            if sym in amb_symbols:
                if suffix_currency:
                    _suffix_amb_symbols.append(re.escape(sym))
                else:
                    _prefix_amb_symbols.append(re.escape(sym))
            else:
                if suffix_currency:
                    _suffix_symbols.append(re.escape(sym))
                else:
                    _prefix_symbols.append(re.escape(sym))
    for sym in props.get("amb_symbols", []):
        if len(sym) > 0 and sym not in props.get("symbols", []):
            if suffix_currency:
                _suffix_amb_symbols.append(re.escape(sym))
            else:
                _prefix_amb_symbols.append(re.escape(sym))
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

def _symbol_surface_pattern(
    surface: str, *, ambiguous: bool = False, exact: bool = False
) -> str:
    escaped = re.escape(surface)
    if exact:
        return rf"(?<![\w/])(?-i:{escaped})(?![\w/])"
    if ambiguous or "/" in surface:
        return rf"(?<![\w/]){escaped}(?![\w/])"
    if _ALPHA_SYM_RE.search(surface):
        return rf"(?<!\w){escaped}(?!\w)"
    return escaped

_safe_prefix_symbols: list[str] = []
for _sym in _prefix_symbols:
    _unescaped = re.sub(r"\\(.)", r"\1", _sym)
    _safe_prefix_symbols.append(_symbol_surface_pattern(_unescaped))

_safe_prefix_amb_symbols: list[str] = []
for _sym in _prefix_amb_symbols:
    _unescaped = re.sub(r"\\(.)", r"\1", _sym)
    _safe_prefix_amb_symbols.append(_symbol_surface_pattern(_unescaped, ambiguous=True))

_safe_prefix_exact_symbols: list[str] = []
for _sym in _prefix_exact_symbols:
    _unescaped = re.sub(r"\\(.)", r"\1", _sym)
    _safe_prefix_exact_symbols.append(_symbol_surface_pattern(_unescaped, exact=True))

_safe_suffix_symbols: list[str] = []
for _sym in _suffix_symbols:
    _unescaped = re.sub(r"\\(.)", r"\1", _sym)
    _safe_suffix_symbols.append(_symbol_surface_pattern(_unescaped))

_safe_suffix_amb_symbols: list[str] = []
for _sym in _suffix_amb_symbols:
    _unescaped = re.sub(r"\\(.)", r"\1", _sym)
    _safe_suffix_amb_symbols.append(_symbol_surface_pattern(_unescaped, ambiguous=True))

_safe_suffix_exact_symbols: list[str] = []
for _sym in _suffix_exact_symbols:
    _unescaped = re.sub(r"\\(.)", r"\1", _sym)
    _safe_suffix_exact_symbols.append(_symbol_surface_pattern(_unescaped, exact=True))

_PREFIX_SYMBOLS = build_alternation(_safe_prefix_symbols)
_PREFIX_AMB_SYMBOLS = build_alternation(_safe_prefix_amb_symbols)
_PREFIX_EXACT_SYMBOLS = build_alternation(_safe_prefix_exact_symbols)
_SUFFIX_SYMBOLS = build_alternation(_safe_suffix_symbols)
_SUFFIX_AMB_SYMBOLS = build_alternation(_safe_suffix_amb_symbols)
_SUFFIX_EXACT_SYMBOLS = build_alternation(_safe_suffix_exact_symbols)


def _combine_nonempty(*patterns: str) -> str:
    items = [pattern for pattern in patterns if pattern]
    if not items:
        return r"(?!.)"
    if len(items) == 1:
        return items[0]
    return rf"(?:{'|'.join(items)})"


_PREFIX_SYMBOL_GROUP = _combine_nonempty(
    _PREFIX_SYMBOLS, _PREFIX_AMB_SYMBOLS, _PREFIX_EXACT_SYMBOLS
)
_SUFFIX_SYMBOL_GROUP = _combine_nonempty(
    _SUFFIX_SYMBOLS, _SUFFIX_AMB_SYMBOLS, _SUFFIX_EXACT_SYMBOLS
)

_safe_codes: list[str] = []
for _code in _codes:
    _unescaped = re.sub(r"\\(.)", r"\1", _code)
    if _unescaped[-1].isalpha():
        _safe_codes.append(rf"{_code}\b")
    else:
        _safe_codes.append(rf"{_code}(?![A-Za-z])")

_CODES = r"(?:" + "|".join(_safe_codes) + r")"


def _surface_regex(surface: str) -> re.Pattern[str]:
    escaped = re.escape(surface)
    if any(ch.isalpha() for ch in surface):
        return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
    return re.compile(escaped)


_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
_SCALE = r"(?:k|m|mm|b|t|thousand|million|billion|trillion)"
_NUM_CORE = rf"(?:{_NUM})"
_NUM_WITH_SCALE = rf"(?:\(?\s*{_NUM_CORE}(?:\s*{_SCALE})?\s*\)?|\(?\s*{_NUM_CORE}\s*\)?\s*{_SCALE})"

# --------------------------------------------------------------------------
# Individual sub-patterns (each independently testable / tweakable)
# --------------------------------------------------------------------------

# -$10, -€2.5m
_NEG_SYMBOL = rf"-\s*{_PREFIX_SYMBOL_GROUP}\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"

# -USD 10, -EUR (10)
_NEG_CODE = rf"-\s*{_CODES}\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"

# ($10), $(10)  — opening paren required, closing optional
_PAREN_SYMBOL = rf"\(\s*{_PREFIX_SYMBOL_GROUP}\s*{_NUM_WITH_SCALE}\s*\)?"

# $10, €2.5m, $(10)
_SYMBOL_PREFIX = rf"{_PREFIX_SYMBOL_GROUP}\s*\(?\s*{_NUM_WITH_SCALE}\s*\)?"

# 10 Ft, 100 kr, 100 S/
_SYMBOL_SUFFIX = rf"\(?\s*{_NUM_WITH_SCALE}\s*\)?\s*{_SUFFIX_SYMBOL_GROUP}"

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
    rf"|{_SYMBOL_SUFFIX}"
    rf"|{_NUM_UNAMB_NAME}"
    rf"|{_ADJ_AMB_NAME_PREFIX}"
    rf"|{_ADJ_AMB_NAME_SUFFIX}"
    rf")",
    re.IGNORECASE,
)

_NUMERIC_CORE_RE = re.compile(r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)")

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
_DROP_DECIMALS_ABOVE = 10_000

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

_FI_CONTEXT_TERMS = sorted(
    set(
        list(FINANCIAL_INSTRUMENTS["prefix"])
        + list(FINANCIAL_INSTRUMENTS["core"])
        + list(FINANCIAL_INSTRUMENTS["ending"])
        + [r"denominated", r"coupon", r"strike", r"notional", r"fx", r"spot", r"forex"]
    ),
    key=len,
    reverse=True,
)
_FI_CONTEXT_RE = re.compile(
    rf"^\s*(?:[-\s,]*)(?:{'|'.join(_FI_CONTEXT_TERMS)})\b",
    re.IGNORECASE,
)


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract MONEY spans from text using money-specific rules.
    Returns (match_text, start, end, label) tuples.
    """
    if not text:
        return []

    from defs.text_cleaner import remap_span, strip_angle_brackets

    stripped, pos_map = strip_angle_brackets(text)
    spans: list[tuple[str, int, int, str]] = []

    for m in MONEY_RE.finditer(stripped):
        orig_start, orig_end = remap_span(pos_map, m.start(), m.end())
        if _is_bracketed_year_like(text, orig_start, orig_end):
            continue
        if _has_financial_instrument_suffix(text, orig_end):
            continue
        spans.append((text[orig_start:orig_end], orig_start, orig_end, LABELS.MONEY.value))

    for m in PRICE_OF_RE.finditer(stripped):
        money_span = m.span("money")
        orig_start, orig_end = remap_span(pos_map, money_span[0], money_span[1])
        if _is_bracketed_year_like(text, orig_start, orig_end):
            continue
        if _has_financial_instrument_suffix(text, orig_end):
            continue
        spans.append((text[orig_start:orig_end], orig_start, orig_end, LABELS.MONEY.value))

    for m in PRICE_PER_RE.finditer(stripped):
        money_span = m.span("money")
        orig_start, orig_end = remap_span(pos_map, money_span[0], money_span[1])
        if _is_bracketed_year_like(text, orig_start, orig_end):
            continue
        if _has_financial_instrument_suffix(text, orig_end):
            continue
        spans.append((text[orig_start:orig_end], orig_start, orig_end, LABELS.MONEY.value))

    for m in PRICE_SLASH_RE.finditer(stripped):
        money_span = m.span("money")
        orig_start, orig_end = remap_span(pos_map, money_span[0], money_span[1])
        if _is_bracketed_year_like(text, orig_start, orig_end):
            continue
        if _has_financial_instrument_suffix(text, orig_end):
            continue
        spans.append((text[orig_start:orig_end], orig_start, orig_end, LABELS.MONEY.value))

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


_FX_RATE_RE = build_regex(
    build_compound(
        prefix=[r"exchange", r"currency", r"forward", r"spot", r"cross"],
        core=[r"rates?", r"prices?", r"points?", r"benchmarks?"],
    ),
    use_sep=False,
)

def _is_bracketed_year_like(text: str, start: int, end: int) -> bool:
    """Return True when a year-like span is really part of an FX/rate mention."""
    span_text = text[start:end]
    numeric = _NUMERIC_CORE_RE.search(span_text)
    if numeric is None:
        return False

    raw = numeric.group("num").replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return False

    if not value.is_integer():
        return False

    year = int(value)
    if year < 1900 or year > 2099:
        return False

    window_start = max(0, start - 32)
    window_end = min(len(text), end + 48)
    window = text[window_start:window_end]

    if re.search(_CODES, window):
        return True
    if re.search(r"\b[A-Z]{3}\s*/\s*[A-Z]{3}\b", window):
        return True
    if _FX_RATE_RE.search(window):
        return True
    return False


def _has_financial_instrument_suffix(text: str, end: int) -> bool:
    tail = text[end : min(len(text), end + 48)]
    return bool(_FI_CONTEXT_RE.search(tail))


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


def _normalize_money_value(
    value: int | float,
    *,
    drop_decimals_above: int = _DROP_DECIMALS_ABOVE,
) -> int | float:
    """
    Remove non-informational decimals for large money values.

    For example:
      2,899,868.89 -> 2,899,869
    """
    if abs(float(value)) >= drop_decimals_above:
        return int(round(float(value)))
    return value


def mutate_money_span(
    text: str,
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: MoneyFormatStrategy = "random",
    pad_magnitude_decimals: bool = False,
    mutate_currency: bool = True,
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
    mutated = _normalize_money_value(mutated)
    chosen_format, chosen_pad = _normalize_format_strategy(
        mutated, format_strategy, rng
    )
    formatted = format_number(
        mutated,
        strategy=chosen_format,  # type: ignore
        numeric_only=True,
        pad_magnitude_decimals=pad_magnitude_decimals or chosen_pad,
    )
    mutated_text = _replace_first_numeric(text, formatted)
    if mutate_currency:
        mutated_text = swap_currency_surface(mutated_text, mutated, rng)
    return mutated_text


def mutate_money_spans(
    spans: Sequence[str],
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: MoneyFormatStrategy = "random",
    pad_magnitude_decimals: bool = False,
    mutate_currency: bool = False,
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

    mutated_values = [_normalize_money_value(v) for v in mutated_values]

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
        mutated_span = _replace_first_numeric(span, formatted)
        if mutate_currency:
            mutated_span = swap_currency_surface(mutated_span, mutated, rng)
        out.append(mutated_span)

    return out
