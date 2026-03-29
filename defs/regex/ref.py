from __future__ import annotations
import re
import random
from typing import Optional, Sequence

from defs.regex_lib import build_alternation
from defs.labels import LABELS
from defs.text_cleaner import remap_span, strip_angle_brackets
from defs.number import Number, Strategy, format_number, mutate_number

# --- ACCOUNTING STANDARD ISSUERS ---
STANDARDS_TERMS = [
    r"SFAS",
    r"FAS",
    r"ASU",
    r"ASC",
    r"IFRS",
    r"IAS",
    r"IFRIC",
    r"SIC",
    r"EITF",
    r"SOP",
    r"FSP",
    r"FIN",
    r"APB",
    r"SFAC",
    r"GAAP",
    r"TB",
]

GUIDANCE_OBJECT_TYPES = [
    r"Guidance",
    r"Standards?",
    r"Amendments?",
    r"Statements?",
    r"Provisions?",
    r"Regulations?",
    r"Abstracts?",
    r"Opinions?",
    r"Codifications?",
    r"Pronouncements?",
    r"Interpretations?",
    r"Bulletins?",
    r"Frameworks?",
    r"Concept\s+Statements?",
    r"Clarifications?",
    r"Rules?",
    r"Principles?",
    r"Topic",    
    r"Subtopic",
    r"Paragraphs?",
    r"Sections?",
    r"Subsections?",
    r"Issue",
    r"Release",
]

# --- EXHIBIT / DOCUMENT REFERENCE NOUNS ---
EXHIBIT_NOUNS = [
    r"exhibits?",
    r"notes?",
    r"appendix",
    r"appendices",
    r"schedules?",
    r"sections?",
    r"subsections?",
    r"clauses?",
    r"articles?",
    r"items?",
    r"figures?",
    r"charts?",
    r"tables?",
    r"pages?",
    r"pp\.",
    r"p\.",
    r"chapters?",
    r"annexes?",
    r"addenda?",
    r"addendums?",
    r"files?",
    r"documents?",
    r"no.",
]

_STANDARDS_FRAGMENT = build_alternation(STANDARDS_TERMS)
_GUIDANCE_FRAGMENT = build_alternation(GUIDANCE_OBJECT_TYPES)
_EXHIBIT_FRAGMENT = build_alternation(EXHIBIT_NOUNS)

# Matches: ASC 842-10-25-1, SFAS 133, ASU 2016-13, EITF 00-19, FIN 48,
#          "Guidance No. 123", "Opinion No. 45-B"
_NUM_ID = r"(?:[A-Z]-)?\d+(?:[\.\-]\d+)*"
_PAREN_SUFFIX = r"(?:\s*\([A-Za-z0-9]+\))*"
_RANGE_CONNECTOR = r"(?:,?\s*(?:and|or|&)|,|to|through)"

_STANDARD_ID_PATTERN = (
    rf"(?:{_STANDARDS_FRAGMENT}|{_GUIDANCE_FRAGMENT})"
    rf"(?:\s+(?:{_STANDARDS_FRAGMENT}|{_GUIDANCE_FRAGMENT}))*"  # e.g. FASB ASC, FASB Statement
    r"(?:\s+Issue)?"
    r"(?:\s+No\.?)?"
    rf"\s*{_NUM_ID}"
    r"[A-Z]?"
    rf"{_PAREN_SUFFIX}"
)

# Matches: 10(a), b(9), 3(b)(2) with no required spaces
_SHORT_PAREN_REF = (
    r"(?:\d+[A-Za-z]?\([A-Za-z0-9]+\)(?:\([A-Za-z0-9]+\))*)"
    r"|(?:[A-Za-z]\(\d+\)(?:\(\d+\))*)"
    r"|(?:[A-Za-z]{1,3}\d*\([A-Za-z0-9]+\)(?:\([A-Za-z0-9]+\))*)"
)

# EX-123, EX-123.134, EX-123.ABC, EX-10.1 through EX-10.5
_EXHIBIT_PREFIX_CORE = r"EX-\d+(?:\.(?:\d+|[A-Za-z]{1,5}))?"
_EXHIBIT_PREFIX_PATTERN = rf"{_EXHIBIT_PREFIX_CORE}(?:\s*{_RANGE_CONNECTOR}\s*{_EXHIBIT_PREFIX_CORE})?"

# Matches: Exhibit 10.2, Note 5, Schedule A-3, Page 10, p. 5, pp. 20-25
_EXHIBIT_PATTERN = (
    rf"(?:{_EXHIBIT_FRAGMENT})"
    r"(?:\s*No\.?)?"
    rf"\s*{_NUM_ID}"
    r"[A-Z]?"
    rf"{_PAREN_SUFFIX}"
    r"(?:"
    rf"\s*{_RANGE_CONNECTOR}\s*"
    rf"{_NUM_ID}[A-Z]?"
    rf"{_PAREN_SUFFIX}"
    r")*"
)

# Matches: refer to Section 3.01, see document 123
_UNKNOWN_REF_PATTERN = (
    r"(?:refer\s+to|see)\s+"
    r"(?:[a-zA-Z][\w-]*\s+){1,2}"  # 1-2 words like "document", "the plan"
    rf"{_NUM_ID}{_PAREN_SUFFIX}"
)

# --- COMBINED REFERENCE PATTERN ---
REFERENCE_RE = re.compile(
    rf"\b(?:{_UNKNOWN_REF_PATTERN}|{_STANDARD_ID_PATTERN}|{_EXHIBIT_PATTERN}|{_SHORT_PAREN_REF}|{_EXHIBIT_PREFIX_PATTERN})",
    re.IGNORECASE,
)


_REF_NUMERIC_CORE_RE = re.compile(
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
)


def _extract_numeric_fragments(text: str) -> list[tuple[Number, int, bool]]:
    """
    Extract numeric fragments and whether each fragment is terminal.

    The original digit width is preserved so formatting can stay realistic
    for short fragments while avoiding odd-looking decimals on long IDs.
    """
    if not text:
        return []

    matches = list(_REF_NUMERIC_CORE_RE.finditer(text))
    fragments: list[tuple[Number, int, bool]] = []
    for idx, num_match in enumerate(matches):
        raw = num_match.group("num").replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        tail = text[num_match.end() :]
        is_terminal = idx == len(matches) - 1 and bool(
            re.fullmatch(r"[\s\)\]\}\.,;:]*", tail)
        )
        digits = len(re.sub(r"\D", "", raw))
        fragments.append((int(value) if value.is_integer() else value, digits, is_terminal))
    return fragments


def extract_numeric_values(text: str) -> list[Number]:
    """
    Extract numeric values from a reference span or fragment.

    Reference identifiers can contain multiple numeric fragments, so we mutate
    the numbers in place and keep the surrounding reference syntax intact.
    """
    if not text:
        return []

    return [value for value, _, _ in _extract_numeric_fragments(text)]


def _replace_numeric_cores(text: str, replacements: Sequence[str]) -> str:
    """
    Replace numeric cores in a reference span while preserving punctuation.
    """
    it = iter(replacements)

    def repl(match: re.Match[str]) -> str:
        try:
            return next(it)
        except StopIteration:
            return match.group(0)

    return _REF_NUMERIC_CORE_RE.sub(repl, text)


def _format_reference_value(
    value: Number,
    *,
    original_digits: int,
    terminal_int: bool,
    rng: random.Random,
) -> str:
    """
    Format a mutated reference value.

    Short integer fragments may render with a single decimal place.
    Longer fragments stay integer-like.
    """
    if original_digits > 2:
        return format_number(value, strategy="raw", numeric_only=True)

    bounded = min(abs(float(value)), 99.9)
    if terminal_int and rng.random() < 0.5:
        tenths = rng.randint(0, 9)
        whole = int(bounded)
        return f"{whole}.{tenths}"
    if bounded == round(bounded):
        return str(int(round(bounded)))
    return f"{bounded:.1f}"


def _mutate_reference_number(
    value: Number,
    *,
    rng: random.Random,
    strategy: Strategy,
    allow_negative: bool,
) -> Number:
    """
    Mutate a reference number and guarantee a visible change.

    The generic number mutator can occasionally preserve the original value.
    For references we want the fragment to move so the mutation is obvious.
    """
    original = int(value) if float(value).is_integer() else float(value)
    for _ in range(4):
        mutated = mutate_number(
            value,
            strategy=strategy,
            int_only=True,
            allow_zero=False,
            allow_negative=allow_negative,
            rng=rng,
        )
        assert isinstance(mutated, Number)
        if mutated != original:
            return mutated

    magnitude = abs(float(value))
    if magnitude < 100:
        candidates = [n for n in range(1, 100) if n != int(round(magnitude))]
        return rng.choice(candidates) if candidates else max(1, int(round(magnitude)) + 1)

    step = max(1, int(round(magnitude * 0.1)))
    direction = -1 if rng.random() < 0.5 else 1
    fallback = int(round(magnitude)) + (direction * step)
    if fallback <= 0:
        fallback = int(round(magnitude)) + step
    return fallback


def mutate_reference_span(
    text: str,
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    allow_negative: bool = False,
) -> str:
    """
    Mutate the numeric fragments inside a single reference span.

    This intentionally avoids any structural edits and only changes the
    in-place numbers.
    """
    if rng is None:
        rng = random.Random()

    fragments = _extract_numeric_fragments(text)
    if not fragments:
        return text

    formatted: list[str] = []
    for value, digits, terminal_int in fragments:
        mutated = _mutate_reference_number(
            value,
            rng=rng,
            strategy=strategy,
            allow_negative=allow_negative,
        )
        assert isinstance(mutated, Number)
        formatted.append(
            _format_reference_value(
                mutated,
                original_digits=digits,
                terminal_int=terminal_int,
                rng=rng,
            )
        )
    return _replace_numeric_cores(text, formatted)


def mutate_reference_spans(
    spans: Sequence[str],
    *,
    rng: Optional[random.Random] = None,
    strategy: Strategy = "random",
    allow_negative: bool = False,
) -> list[str]:
    """
    Mutate a batch of reference spans.

    A single numeric mutation strategy is chosen for the whole batch so
    related reference strings stay coherent.
    """
    if rng is None:
        rng = random.Random()

    if not spans:
        return []

    if not any(_extract_numeric_fragments(span) for span in spans):
        return list(spans)

    out: list[str] = []
    for span in spans:
        out.append(
            mutate_reference_span(
                span,
                rng=rng,
                strategy=strategy,
                allow_negative=allow_negative,
            )
        )

    return out


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    if not text:
        return []

    stripped, pos_map = strip_angle_brackets(text)

    results: list[tuple[str, int, int, str]] = []
    for m in REFERENCE_RE.finditer(stripped):
        orig_start, orig_end = remap_span(pos_map, m.start(), m.end())
        results.append(
            (text[orig_start:orig_end], orig_start, orig_end, LABELS.REFERENCE.value)
        )

    return results
