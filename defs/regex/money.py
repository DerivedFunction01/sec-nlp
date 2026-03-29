import math
import re
import random
from typing import Literal, Optional, Sequence

from defs.regex_lib import build_alternation
from defs.labels import LABELS
from defs.regex.entity import FINANCIAL_INSTRUMENTS
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


def _surface_regex(surface: str) -> re.Pattern[str]:
    escaped = re.escape(surface)
    if any(ch.isalpha() for ch in surface):
        return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
    return re.compile(escaped)


def _titlecase_currency_surface(surface: str) -> str:
    parts = re.split(r"(\s+|-)", surface)
    titled: list[str] = []
    for part in parts:
        if part == "" or part.isspace() or part == "-":
            titled.append(part)
            continue
        if part.isupper():
            titled.append(part)
        elif part.lower() == "us":
            titled.append("US")
        else:
            titled.append(part[:1].upper() + part[1:].lower())
    return "".join(titled)


_CURRENCY_SURFACES: list[dict[str, object]] = []
for _code, _props in MAJOR_CURRENCIES.items():
    _symbols_for_code = [sym for sym in _props.get("symbols", []) if sym]
    _names_for_code = [name for name in _props.get("names", []) if name]
    _adj = _props.get("adj")
    _amb_names = [name for name in _props.get("amb_names", []) if name]

    for _sym in _symbols_for_code:
        _CURRENCY_SURFACES.append(
            {
                "code": _code,
                "kind": "symbol",
                "surface": _sym,
            }
        )

    _CURRENCY_SURFACES.append(
        {
            "code": _code,
            "kind": "code",
            "surface": _code,
        }
    )

    for _name in _names_for_code:
        if _name in _amb_names:
            if _adj:
                _CURRENCY_SURFACES.append(
                    {
                        "code": _code,
                        "kind": "adj_name",
                        "surface": f"{_adj} {_name}",
                    }
                )
        else:
            _CURRENCY_SURFACES.append(
                {
                    "code": _code,
                    "kind": "name",
                    "surface": _name,
                }
            )

_CURRENCY_SURFACES.sort(key=lambda entry: len(entry["surface"]), reverse=True)
for _entry in _CURRENCY_SURFACES:
    _entry["pattern"] = _surface_regex(_entry["surface"])

_CURRENCY_SURFACES_BY_KIND: dict[str, list[dict[str, object]]] = {}
for _entry in _CURRENCY_SURFACES:
    _CURRENCY_SURFACES_BY_KIND.setdefault(_entry["kind"], []).append(_entry)

_CURRENCY_DATA_BY_CODE = MAJOR_CURRENCIES

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+"
_SCALE = r"(?:k|m|mm|b|t|thousand|million|billion|trillion)"
_NUM_CORE = rf"(?:{_NUM})"
_NUM_WITH_SCALE = rf"(?:\(?\s*{_NUM_CORE}(?:\s*{_SCALE})?\s*\)?|\(?\s*{_NUM_CORE}\s*\)?\s*{_SCALE})"

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
        list(FINANCIAL_INSTRUMENTS["core"])
        + list(FINANCIAL_INSTRUMENTS["ending"])
        + [r"denominated", r"coupon", r"strike", r"notional"]
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


def _find_currency_surface(text: str) -> tuple[re.Match[str], dict[str, object]] | None:
    for entry in _CURRENCY_SURFACES:
        pattern = entry["pattern"]
        assert isinstance(pattern, re.Pattern)
        match = pattern.search(text)
        if match is not None:
            return match, entry
    return None


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
    if re.search(r"\b(?:exchange|currency|forward)\s+rate\b", window, re.IGNORECASE):
        return True

    return False


def _has_financial_instrument_suffix(text: str, end: int) -> bool:
    tail = text[end : min(len(text), end + 48)]
    return bool(_FI_CONTEXT_RE.search(tail))


def _pick_currency_name(props: dict, value: int | float, rng: random.Random) -> str | None:
    names = [name for name in props.get("names", []) if name]
    if not names:
        return None

    amb_names = set(props.get("amb_names", []))
    plural = not math.isclose(abs(float(value)), 1.0)

    preferred = []
    fallback = []
    for name in names:
        if name in amb_names:
            continue
        fallback.append(name)
        if plural and name.endswith("s"):
            preferred.append(name)
        elif not plural and not name.endswith("s"):
            preferred.append(name)

    if preferred:
        return rng.choice(preferred)
    if fallback:
        return rng.choice(fallback)
    return rng.choice(names)


def _pick_currency_adj_name(props: dict, value: int | float, rng: random.Random) -> str | None:
    adj = props.get("adj")
    if not adj:
        return None

    amb_names = [name for name in props.get("amb_names", []) if name]
    if not amb_names:
        return None

    plural = not math.isclose(abs(float(value)), 1.0)
    preferred = []
    fallback = []
    for name in amb_names:
        fallback.append(name)
        if plural and name.endswith("s"):
            preferred.append(name)
        elif not plural and not name.endswith("s"):
            preferred.append(name)

    name = rng.choice(preferred or fallback)
    return f"{adj} {name}"


def _pick_replacement_currency(
    current_entry: dict[str, object], value: int | float, rng: random.Random
) -> str | None:
    current_code = str(current_entry["code"])
    current_kind = str(current_entry["kind"])

    candidate_codes = [code for code in _CURRENCY_DATA_BY_CODE.keys() if code != current_code]
    if not candidate_codes:
        return None

    rng.shuffle(candidate_codes)

    for code in candidate_codes:
        props = _CURRENCY_DATA_BY_CODE[code]
        if current_kind == "symbol":
            symbols = [sym for sym in props.get("symbols", []) if sym]
            if symbols:
                return rng.choice(symbols)
        elif current_kind == "code":
            return code
        elif current_kind == "adj_name":
            adj_name = _pick_currency_adj_name(props, value, rng)
            if adj_name is not None:
                return _titlecase_currency_surface(adj_name)
        elif current_kind == "name":
            name = _pick_currency_name(props, value, rng)
            if name is not None:
                return _titlecase_currency_surface(name)

    for code in candidate_codes:
        props = _CURRENCY_DATA_BY_CODE[code]
        symbols = [sym for sym in props.get("symbols", []) if sym]
        if symbols:
            return rng.choice(symbols)
        name = _pick_currency_name(props, value, rng)
        if name is not None:
            return _titlecase_currency_surface(name)
        adj_name = _pick_currency_adj_name(props, value, rng)
        if adj_name is not None:
            return _titlecase_currency_surface(adj_name)
        return code

    return None


def _swap_currency_surface(text: str, value: int | float, rng: random.Random) -> str:
    found = _find_currency_surface(text)
    if found is None:
        return text

    match, current_entry = found
    replacement = _pick_replacement_currency(current_entry, value, rng)
    if replacement is None:
        return text

    return text[: match.start()] + replacement + text[match.end() :]


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
        mutated_text = _swap_currency_surface(mutated_text, mutated, rng)
    return mutated_text


def mutate_money_spans(
    spans: Sequence[str],
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    format_strategy: MoneyFormatStrategy = "random",
    pad_magnitude_decimals: bool = False,
    mutate_currency: bool = True,
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
            mutated_span = _swap_currency_surface(mutated_span, mutated, rng)
        out.append(mutated_span)

    return out
