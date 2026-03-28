from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

Number = int | float

Strategy = Literal[
    "random",
    "preserve",
    "shared_scale",
    "shared_offset",
    "shared_affine",
    "independent_scale",
    "independent_offset",
]

FormatStrategy = Literal[
    "raw", "commas", "words", "magnitude_long", "magnitude_short", "magnitude_financial"
]

MagnitudeStyle = Literal["long", "short", "financial"]

# Engineering scales: (divisor, long suffix, short suffix, financial suffix)
_SCALES = [
    (1_000_000_000_000, "trillion", "T", "T"),
    (1_000_000_000, "billion", "B", "B"),
    (1_000_000, "million", "M", "MM"),
    (1_000, "thousand", "K", "K"),
]

_ONES = [
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]

_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]


# ---------------------------------------------------------------------------
# Existing mutation helpers (unchanged)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumberMutationPlan:
    strategy: str
    scale: float | None = None
    offset: float | None = None


def _as_float(value: Number) -> float:
    if isinstance(value, bool):
        raise TypeError("bool is not a supported numeric input")
    return float(value)


def _is_int_like(value: Number) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _maybe_round(value: float, int_only: bool) -> Number:
    if int_only:
        return int(round(value))
    return value


def _enforce_constraints(
    value: float,
    *,
    allow_zero: bool,
    allow_negative: bool,
    min_magnitude: float = 1.0,
) -> float:
    if not allow_negative and value < 0:
        value = abs(value)
    if not allow_zero and value == 0:
        value = min_magnitude
        if not allow_negative and value < 0:
            value = abs(value)
    return value


def _pick_strategy(
    strategy: Strategy, numbers: Sequence[Number], rng: random.Random
) -> str:
    if strategy != "random":
        return strategy
    candidates = ["shared_scale", "shared_offset", "shared_affine"]
    if len(numbers) <= 1:
        candidates.extend(["independent_scale", "independent_offset"])
    return rng.choice(candidates)


def _shared_scale_factor(numbers: Sequence[Number], rng: random.Random) -> float:
    magnitudes = [abs(_as_float(n)) for n in numbers if _as_float(n) != 0]
    if not magnitudes:
        return rng.uniform(1.2, 4.0)
    max_mag = max(magnitudes)
    if max_mag < 10:
        return rng.uniform(1.5, 6.0)
    if max_mag < 100:
        return rng.uniform(1.2, 4.0)
    if max_mag < 1_000:
        return rng.uniform(0.75, 3.0)
    if max_mag < 100_000:
        return rng.uniform(0.25, 3.0)
    return rng.uniform(0.05, 2.0)


def _shared_offset_value(numbers: Sequence[Number], rng: random.Random) -> float:
    magnitudes = [abs(_as_float(n)) for n in numbers]
    scale = max(magnitudes, default=1.0)
    if scale < 10:
        scale = 10.0
    return rng.uniform(-0.75 * scale, 0.75 * scale)


def _independent_scale_factor(number: Number, rng: random.Random) -> float:
    magnitude = abs(_as_float(number))
    if magnitude < 10:
        return rng.uniform(1.5, 6.0)
    if magnitude < 100:
        return rng.uniform(1.2, 4.0)
    if magnitude < 1_000:
        return rng.uniform(0.75, 3.0)
    if magnitude < 100_000:
        return rng.uniform(0.25, 3.0)
    return rng.uniform(0.05, 2.0)


def _independent_offset_value(number: Number, rng: random.Random) -> float:
    magnitude = abs(_as_float(number))
    if magnitude < 10:
        magnitude = 10.0
    return rng.uniform(-0.75 * magnitude, 0.75 * magnitude)


def _apply_shared_scale(numbers, *, int_only, allow_zero, allow_negative, rng):
    factor = _shared_scale_factor(numbers, rng)
    mutated = []
    for number in numbers:
        new_value = _as_float(number) * factor
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(strategy="shared_scale", scale=factor)


def _apply_shared_offset(numbers, *, int_only, allow_zero, allow_negative, rng):
    offset = _shared_offset_value(numbers, rng)
    mutated = []
    for number in numbers:
        new_value = _as_float(number) + offset
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(strategy="shared_offset", offset=offset)


def _apply_shared_affine(numbers, *, int_only, allow_zero, allow_negative, rng):
    factor = _shared_scale_factor(numbers, rng)
    offset = _shared_offset_value(numbers, rng)
    mutated = []
    for number in numbers:
        new_value = (_as_float(number) * factor) + offset
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(
        strategy="shared_affine", scale=factor, offset=offset
    )


def _apply_independent_scale(numbers, *, int_only, allow_zero, allow_negative, rng):
    mutated = []
    for number in numbers:
        factor = _independent_scale_factor(number, rng)
        new_value = _as_float(number) * factor
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(strategy="independent_scale")


def _apply_independent_offset(numbers, *, int_only, allow_zero, allow_negative, rng):
    mutated = []
    for number in numbers:
        offset = _independent_offset_value(number, rng)
        new_value = _as_float(number) + offset
        new_value = _enforce_constraints(
            new_value,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            min_magnitude=max(1.0, abs(_as_float(number))),
        )
        mutated.append(_maybe_round(new_value, int_only))
    return mutated, NumberMutationPlan(strategy="independent_offset")


def mutate_numbers(
    numbers: Sequence[Number],
    *,
    strategy: Strategy = "random",
    int_only: bool = True,
    allow_zero: bool = False,
    allow_negative: bool = False,
    rng: Optional[random.Random] = None,
    return_plan: bool = False,
) -> list[Number] | tuple[list[Number], NumberMutationPlan]:
    """Mutate a batch of numeric values in parallel."""
    if rng is None:
        rng = random.Random()

    values = list(numbers)
    if not values:
        empty_plan = NumberMutationPlan(strategy="preserve")
        return ([], empty_plan) if return_plan else []

    chosen = _pick_strategy(strategy, values, rng)

    if chosen == "preserve":
        mutated = [
            _maybe_round(
                _enforce_constraints(
                    _as_float(n),
                    allow_zero=allow_zero,
                    allow_negative=allow_negative,
                    min_magnitude=max(1.0, abs(_as_float(n))),
                ),
                int_only,
            )
            for n in values
        ]
        plan = NumberMutationPlan(strategy="preserve")
    elif chosen == "shared_scale":
        mutated, plan = _apply_shared_scale(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            rng=rng,
        )
    elif chosen == "shared_offset":
        mutated, plan = _apply_shared_offset(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            rng=rng,
        )
    elif chosen == "shared_affine":
        mutated, plan = _apply_shared_affine(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            rng=rng,
        )
    elif chosen == "independent_scale":
        mutated, plan = _apply_independent_scale(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            rng=rng,
        )
    elif chosen == "independent_offset":
        mutated, plan = _apply_independent_offset(
            values,
            int_only=int_only,
            allow_zero=allow_zero,
            allow_negative=allow_negative,
            rng=rng,
        )
    else:
        raise ValueError(f"Unknown strategy '{chosen}'.")

    return (mutated, plan) if return_plan else mutated


def mutate_number(
    number: Number,
    *,
    strategy: Strategy = "random",
    int_only: bool = True,
    allow_zero: bool = True,
    allow_negative: bool = True,
    rng: Optional[random.Random] = None,
    return_plan: bool = False,
) -> Number | tuple[Number, NumberMutationPlan]:
    """Convenience wrapper for a single number."""
    result = mutate_numbers(
        [number],
        strategy=strategy,
        int_only=int_only,
        allow_zero=allow_zero,
        allow_negative=allow_negative,
        rng=rng,
        return_plan=return_plan,
    )
    if return_plan:
        assert isinstance(result, tuple)
        mutated, plan = result
        return mutated[0], plan
    assert isinstance(result, list)
    return result[0] 


# ---------------------------------------------------------------------------
# Rounding
# ---------------------------------------------------------------------------


def _count_integer_digits(prefix: float) -> int:
    """Number of digits in the integer part of a prefix (e.g. 123.4 -> 3, 9.1 -> 1)."""
    return len(str(int(math.floor(abs(prefix)))))


def _rounding_steps(value: float, divisor: float) -> list[float]:
    """
    Return all valid rounded values for `value` at the given engineering scale.

    Produces candidates from finest (3 decimal places on prefix) to coarsest
    (rounding prefix to 10s or 100s), stopping before a leading significant
    figure would be lost.
    """
    prefix = value / divisor
    int_digits = _count_integer_digits(prefix)

    steps: list[float] = []

    # Fine rounding: decimal places on the prefix (3 → 0)
    for dp in (3, 2, 1, 0):
        factor = 10**dp
        rounded_prefix = math.floor(prefix * factor + 0.5) / factor
        rounded_value = rounded_prefix * divisor
        if not steps or abs(rounded_value - steps[-1]) > 0.5:
            steps.append(rounded_value)

    # Coarse rounding: round prefix to 10s, 100s — but never lose a leading digit
    # min_prefix_unit keeps at least 2 sig figs in the prefix integer part
    # e.g. prefix=123 (3 digits) → can round to nearest 10 (120) but not 100 (1xx)
    if int_digits >= 2:
        unit = 10
        while True:
            # Rounding prefix to `unit` must not reduce integer digit count
            rounded_prefix = math.floor(prefix / unit + 0.5) * unit
            if _count_integer_digits(rounded_prefix) < int_digits:
                break
            rounded_value = rounded_prefix * divisor
            if not steps or abs(rounded_value - steps[-1]) > 0.5:
                steps.append(rounded_value)
            unit *= 10

    return steps


def round_number(
    value: Number,
    *,
    rng: Optional[random.Random] = None,
) -> float:
    """
    Randomly round `value` using engineering-scale significant-figure rounding.

    - Values < 1,000: returned exact (no rounding applied).
    - Values >= 1,000: a random step is chosen from the valid rounding options
      at the appropriate engineering scale (E3, E6, E9, E12).
      Never drops a leading significant figure.

    Returns a float >= 0. Sign handling belongs to the caller.
    """
    if rng is None:
        rng = random.Random()

    v = abs(_as_float(value))

    divisor = None
    for div, *_ in _SCALES:
        if v >= div:
            divisor = div
            break

    if divisor is None:
        return v  # below E3 — exact

    steps = _rounding_steps(v, divisor)
    return float(rng.choice(steps))


# ---------------------------------------------------------------------------
# Word spelling helpers
# ---------------------------------------------------------------------------


def _spell_integer(n: int) -> str:
    """Spell out an integer 0–99."""
    if n == 0:
        return "zero"
    if n < 0 or n >= 100:
        raise ValueError(f"Cannot spell integer outside 0–99: {n}")
    if n < 20:
        return _ONES[n]
    tens = _TENS[n // 10]
    ones = _ONES[n % 10]
    return f"{tens}-{ones}" if ones else tens


def _magnitude_prefix_word(prefix: float) -> str | None:
    """
    Return a word/digit token for a magnitude prefix if it is word-eligible
    (1 <= prefix < 10, strictly less than 10). Returns None otherwise.

    - Whole numbers 1–9  → spelled out  ("one", "nine")
    - 1.1 – 9.9          → digit string ("1.5", "9.9")
    - 10 and above       → None (would add a third word: "ten million")
    """
    if prefix < 1.0 or prefix >= 10.0:
        return None
    if prefix == math.floor(prefix):
        n = int(prefix)
        if n < 1 or n > 9:
            return None
        return _spell_integer(n)
    # One decimal place only; reject finer precision
    rounded = round(prefix, 1)
    if abs(rounded - prefix) < 1e-9 and rounded < 10.0:
        return f"{rounded:g}"
    return None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_commas(value: float) -> str:
    """Thousands-separated digits. Drops unnecessary trailing zeros on decimals."""
    if value == math.floor(value):
        return f"{int(value):,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def _format_magnitude(value: float, style: MagnitudeStyle) -> str | None:
    """
    Format value as a magnitude string. Returns None if value is below E3.

    style:
        "long"        -> "2.5 million"
        "short"       -> "2.5M"
        "financial"   -> "2.5MM" / "2.5B"
    """
    for divisor, long_sfx, short_sfx, fin_sfx in _SCALES:
        if value >= divisor:
            prefix = value / divisor
            prefix_str = (
                f"{int(prefix):,}"
                if prefix == math.floor(prefix)
                else f"{prefix:.2f}".rstrip("0").rstrip(".")
            )
            if style == "long":
                return f"{prefix_str} {long_sfx}"
            elif style == "short":
                return f"{prefix_str}{short_sfx}"
            elif style == "financial":
                return f"{prefix_str}{fin_sfx}"
    return None


def _format_magnitude_prefix(prefix: float, *, pad_decimals: bool = False) -> str:
    """
    Format the prefix for a magnitude string.

    Default behavior trims trailing zeros. When pad_decimals=True, keep two
    decimal places always (e.g. 2 -> 2.00, 2.5 -> 2.50, 2.123 -> 2.12).
    """
    if pad_decimals:
        return f"{prefix:.2f}"
    if prefix == math.floor(prefix):
        return f"{int(prefix):,}"
    return f"{prefix:.2f}".rstrip("0").rstrip(".")


def _try_words(value: float, numeric_only: bool) -> str | None:
    """
    Attempt to produce a <= 2-word form for value.
    Returns None if no eligible form exists.

    Word-eligible cases:
      - zero                              -> "zero"           (counts only)
      - integers 1–99                     -> spelled out      (counts only)
      - exact multiples of 100 (100–900)  -> "X hundred"      (counts only)
      - magnitude prefix 1–9              -> "X million" etc. (counts + currency)
    """
    v = value

    # Zero
    if v == 0:
        return None if numeric_only else "zero"

    # Small integers 1–99 (counts only)
    if not numeric_only and v < 100 and v == math.floor(v):
        return _spell_integer(int(v))

    # Exact hundreds: 100, 200, … 900 (counts only)
    if not numeric_only and 100 <= v <= 900 and v % 100 == 0:
        return f"{_spell_integer(int(v) // 100)} hundred"

    # Magnitude forms (both counts and currency)
    for divisor, long_sfx, *_ in _SCALES:
        if v >= divisor:
            prefix = v / divisor
            word = _magnitude_prefix_word(prefix)
            if word is not None:
                return f"{word} {long_sfx}"
            # prefix >= 10 or has too many decimal places: not word-eligible.
            # Return None so the caller uses commas fallback, NOT magnitude fallback.
            return None

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_number(
    value: Number,
    strategy: FormatStrategy = "commas",
    *,
    numeric_only: bool = False,
    magnitude_style: MagnitudeStyle = "long",
    pad_magnitude_decimals: bool = False,
) -> str:
    """
    Format a non-negative number as a string.

    Parameters
    ----------
    value :
        A non-negative number. Sign handling is the caller's responsibility
        (currency.py strips and re-applies the sign).
    strategy :
        ``raw``                  bare number as Python would print it
        ``commas``               thousands-separated digits  (default)
        ``words``                word form when <= 2 words, else commas fallback
        ``magnitude_long``       "2.5 million"
        ``magnitude_short``      "2.5M"
        ``magnitude_financial``  "2.5MM" / "2.5B"
    numeric_only :
        Suppress spelling of small integers (1–99) and exact hundreds/thousands.
        Use for currency contexts where "$ three" is invalid.
        Magnitude word forms like "3 million" remain allowed.
    magnitude_style :
        Suffix style used when ``strategy="words"`` falls through to a
        magnitude form. Has no effect on explicit magnitude strategies.
    """
    v = abs(_as_float(value))

    if strategy == "raw":
        return str(int(v)) if v == math.floor(v) else str(v)

    if strategy == "commas":
        return _format_commas(v)

    if strategy == "words":
        word_form = _try_words(v, numeric_only)
        if word_form is not None:
            return word_form
        # No word form possible — use commas for everything
        return _format_commas(v)

    if strategy == "magnitude_long":
        if v < 1_000:
            return _format_commas(v)
        for divisor, long_sfx, *_ in _SCALES:
            if v >= divisor:
                prefix = v / divisor
                return f"{_format_magnitude_prefix(prefix, pad_decimals=pad_magnitude_decimals)} {long_sfx}"
        return _format_commas(v)

    if strategy == "magnitude_short":
        if v < 1_000:
            return _format_commas(v)
        for divisor, _, short_sfx, _ in _SCALES:
            if v >= divisor:
                prefix = v / divisor
                return f"{_format_magnitude_prefix(prefix, pad_decimals=pad_magnitude_decimals)}{short_sfx}"
        return _format_commas(v)

    if strategy == "magnitude_financial":
        if v < 1_000:
            return _format_commas(v)
        for divisor, _, _, fin_sfx in _SCALES:
            if v >= divisor:
                prefix = v / divisor
                return f"{_format_magnitude_prefix(prefix, pad_decimals=pad_magnitude_decimals)}{fin_sfx}"
        return _format_commas(v)

    raise ValueError(f"Unknown format strategy: {strategy!r}")


def format_numbers(
    values: Sequence[Number],
    strategy: FormatStrategy = "commas",
    *,
    numeric_only: bool = False,
    magnitude_style: MagnitudeStyle = "long",
    pad_magnitude_decimals: bool = False,
) -> list[str]:
    """
    Format a list of non-negative numbers with the same strategy.
    Mirrors the batch interface of mutate_numbers.
    """
    return [
        format_number(
            v,
            strategy,
            numeric_only=numeric_only,
            magnitude_style=magnitude_style,
            pad_magnitude_decimals=pad_magnitude_decimals,
        )
        for v in values
    ]
