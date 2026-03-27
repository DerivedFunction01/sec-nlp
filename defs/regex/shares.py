from __future__ import annotations
import re

from defs.labels import LABELS
from defs.regex_lib import (
    NUMBER_RANGE_STR,
    build_regex,
    build_compound,
    to_build_alternation,
    SENTENCE_SPLIT_RE,
    closest_distance_in_segment,
)

# =============================================================================
# SHARE TERMS
# =============================================================================

_SHARE_UNITS_PREFIXES = [
    "trust",
    "REIT",
    "operating",
    r"limited\s+partnership",
    "depositary",
    "fractional",
    "stock",
]

_SHARE_CORE: list[str] = [
    r"shares?",
    r"stocks?",
    r"warrants?",
    r"options?",
    r"rights?",
    r"RSUs?",
    r"PSUs?",
    r"DSUs?",
    r"SARs?",
    r"grants?",
    r"awards?",
]

_SHARE_QUALIFIERS: list[str] = [
    r"preferred",
    r"common",
    r"ordinary",
    r"treasury",
    r"restricted",
    r"outstanding",
]

_SHARE_QUALIFIED_CORE: list[str] = [
    r"stocks?",
    r"shares?",
]

_SHARE_QUALIFIED: list[str] = [
    build_compound(
        prefix=_SHARE_QUALIFIERS,
        core=_SHARE_QUALIFIED_CORE,
        sep_prefix=r"\s+",
    ),
    build_compound(
        prefix=r"restricted",
        core=r"units?",
        sep_prefix=r"\s+",
    ),
]

_SHARE_UNITS: str = build_compound(
    prefix=_SHARE_UNITS_PREFIXES,
    core=r"units?",
    sep_prefix=r"\s+",
)

# Unambiguous in any annual report context — reliable without local term support
_UNAMBIGUOUS_SHARE_TERMS: list[str] = [
    r"RSUs?",
    r"PSUs?",
    r"DSUs?",
    r"SARs?",
    r"warrants?",
]

# Terms that become unambiguous given strong paragraph equity context
_PARAGRAPH_RELIABLE_TERMS: list[str] = [
    r"stocks?",
    r"shares?",
    r"options?",
]

SHARE_TERMS: list[str] = _SHARE_CORE + _SHARE_QUALIFIED + [_SHARE_UNITS]

# =============================================================================
# EQUITY CONTEXT TERMS
# Ported from derivatives module (high-confidence only).
# Used to gate ambiguous share terms at sentence and paragraph level.
# =============================================================================

_EQUITY_COMP_CONTEXT: list[str] = [
    r"vest(?:ing|ed)",
    r"exercis(?:able|ed)?",
    r"grant\s+dates?",
    r"service\s+period",
    r"ESPP",
    r"share[- ]based\s+payments?",
    r"weighted[- ]average\s+(?:strike|exercise)\s+price",
    r"(?:benefit|incentive|treasury)\s+plans?",
    r"dilut(?:ed|ive|ion)",
    r"issu(?:ance|ed)\s+and\s+outstanding",
    r"authoriz(?:ed|ation)\s+(?:to\s+issue|of\s+shares?|of\s+stock)",
    r"buyback",
    r"repurchas(?:e|ed|ing|es)",
    r"(?:stock|equity|share)\s+repurchas(?:e|es|ed|ing)",
    # Corporate actions
    r"stock\s+splits?",
    r"stock\s+dividends?",
    r"(?:share|stock)\s+repurchase\s+programs?",
    r"capital\s+stock",
    r"(?:stock|share)holders?'?\s+equity",
    # Executive / governance — reliable comp disclosure signals
    r"chief\s+executive\s+officer",
    r"CEO",
    r"chief\s+financial\s+officer",
    r"CFO",
    r"named\s+executive\s+officers?",
    r"NEOs?",
    r"board\s+of\s+directors?",
    r"compensation\s+committees?",
    r"employees?\s+(?:stock|share|equity)",  # "employee stock/share/equity"
    r"(?:stock|share|equity)\s+compensation",  # "stock/equity compensation"
    r"(?:stock|share|equity)\s+(?:based|based[- ]compensation)",  # "stock-based compensation"
    r"employee\s+benefit\s+plans?",
    r"executive\s+compensations?",
    r"(?:long[- ]term|short[- ]term)\s+incentive",  # LTIP/STIP
    r"(?:equity|stock)\s+awards?",
    r"compensation\s+expense",  # almost always stock-based in this context
]
_EQUITY_COMPONENT_CONTEXT: list[str] = [
    r"(?:preferred|common|treasury|outstanding|restricted|capital|equity)\s+(?:stocks?|shares?)",
    r"outstanding\s+equity",
    r"(?:class\s+[A-D]|series\s+(?:[A-J]|\d+))\s+(?:preferred\s+)?(?:stocks?|shares?|units?)",
]

_EQUITY_STRUCTURE_CONTEXT: list[str] = [
    r"initial\s+public\s+offering",
    r"IPO",
    r"series\s+(?:A|B|C|D|E|F|G|H|I|J)",
    r"(?:primary|secondary)\s+markets?",
    r"acquisition\s+date",
]

EQUITY_CONTEXT_TERMS: list[str] = (
    _EQUITY_COMP_CONTEXT + _EQUITY_COMPONENT_CONTEXT + _EQUITY_STRUCTURE_CONTEXT
)

_EQUITY_CONTEXT_RE = build_regex(EQUITY_CONTEXT_TERMS)
_UNAMBIGUOUS_RE = build_regex(_UNAMBIGUOUS_SHARE_TERMS)
_PARAGRAPH_RELIABLE_RE = build_regex(_PARAGRAPH_RELIABLE_TERMS)

# =============================================================================
# SHARE COUNT PATTERNS
# Both directions:
#   "issued 1,000,000 shares of common stock"
#   "the stock units were 10,000,000"
# non_numeric_gap: allows a few intervening words without consuming digits
# =============================================================================

_non_numeric_gap = r"(?:[^\W\d][\w\.-]*\s+){0,3}"
_share_alt = to_build_alternation(SHARE_TERMS)

SHARE_COUNT_RE = build_regex(
    [
        rf"({NUMBER_RANGE_STR})\s+{_non_numeric_gap}(?:{_share_alt})",
        rf"(?:{_share_alt})\s+{_non_numeric_gap}({NUMBER_RANGE_STR})",
    ]
)


# =============================================================================
# EXTRACT SPANS
# =============================================================================


def _iter_sentences(src: str) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    start = 0
    for m in SENTENCE_SPLIT_RE.finditer(src):
        end = m.end()
        chunk = src[start:end]
        if chunk.strip():
            out.append((start, end, chunk))
        start = end
    tail = src[start:]
    if tail.strip():
        out.append((start, len(src), tail))
    return out


def _iter_paragraphs(src: str) -> list[tuple[int, int, str]]:
    """Split on blank lines for paragraph-level equity context checks."""
    out: list[tuple[int, int, str]] = []
    for m in re.finditer(r"(?:^|\n\n+)(.*?)(?=\n\n|\Z)", src, re.DOTALL):
        chunk = m.group(0)
        if chunk.strip():
            out.append((m.start(), m.end(), chunk))
    return out


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract SHARE spans from text.
    Returns (match_text, start, end, label) tuples.

    Gating logic:
    - All terms require equity context somewhere in the paragraph.
    - Unambiguous terms (RSUs, PSUs, DSUs, SARs, warrants) need only
      paragraph-level equity context.
    - Paragraph-reliable terms (stock, shares, options) also only need
      paragraph-level equity context — if the paragraph is strictly equity,
      these terms unambiguously refer to shares.
    - Remaining ambiguous terms require equity context in the same sentence
      segment (clause-scoped via closest_distance_in_segment).
    """
    if not text:
        return []

    spans: list[tuple[str, int, int, str]] = []
    span_set: set[tuple[int, int]] = set()

    def _add_span(match_text: str, start: int, end: int) -> None:
        if (start, end) in span_set:
            return
        span_set.add((start, end))
        spans.append((match_text, start, end, LABELS.SHARE.value))

    # Pre-compute paragraph equity context
    para_equity: list[tuple[int, int, bool]] = [
        (ps, pe, bool(_EQUITY_CONTEXT_RE.search(para)))
        for ps, pe, para in _iter_paragraphs(text)
    ]

    def _para_has_equity(abs_pos: int) -> bool:
        for ps, pe, has_eq in para_equity:
            if ps <= abs_pos < pe:
                return has_eq
        return False

    for sent_start, sent_end, sentence in _iter_sentences(text):
        if not _para_has_equity(sent_start):
            continue

        has_sentence_equity = bool(_EQUITY_CONTEXT_RE.search(sentence))

        for m in SHARE_COUNT_RE.finditer(sentence):
            if m.group(1):
                num_start, num_end = m.start(1), m.end(1)
            else:
                num_start, num_end = m.start(2), m.end(2)

            match_text = m.group(0)
            is_unambiguous = bool(_UNAMBIGUOUS_RE.search(match_text))
            is_para_reliable = bool(_PARAGRAPH_RELIABLE_RE.search(match_text))

            if is_unambiguous or is_para_reliable:
                # Paragraph equity already confirmed — tag directly
                _add_span(m.group(0), sent_start + m.start(), sent_start + m.end())
            else:
                # Remaining ambiguous terms need clause-level equity context
                if has_sentence_equity:
                    eq_matches = list(_EQUITY_CONTEXT_RE.finditer(sentence))
                    dist = closest_distance_in_segment(
                        sentence, num_start, num_end, eq_matches
                    )
                    if dist is not None:
                        _add_span(m.group(0), sent_start + m.start(), sent_start + m.end())

    return spans
