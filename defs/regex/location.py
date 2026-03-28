from __future__ import annotations
import re
from typing import Optional
from defs.regex_lib import (
    NUMBER_RANGE_STR,
    build_compound,
    NUMBER_PATTERN_STR,
    build_alternation,
    make_gap,
    build_regex,
    SENTENCE_SPLIT_RE,
)
from defs.labels import LABELS
from defs.regex.labor import INDUSTRY_PREFIX_TERMS_FLAT, _WORKER_CONTEXT_RE
from defs.region_regex import RegionMatcher
from defs.text_cleaner import remap_span, strip_angle_brackets

# =============================================================================
# LOCATION TERMS
# =============================================================================

# Physical assets / facilities
PHYSICAL_LOCATION_TERMS: set[str] = {
    # Facilities
    r"facilit(?:y|ies)",
    r"plants?",
    r"factor(?:y|ies)",
    r"warehouses?",
    r"laborator(?:y|ies)",
    r"labs?",
    # Offices / Commercial
    r"offices?",
    r"stores?",
    r"outlets?",
    r"showrooms?",
    r"branch(?:es)?",
    r"headquarters?",
    # Industrial / Energy
    r"mines?",
    r"refiner(?:ies|y)",
    r"terminals?",
    r"depots?",
    r"wells?",
    r"rigs?",
    r"pipelines?",
    # Land / Agriculture
    r"farms?",
    r"ranches?",
    r"fields?",
    r"fisher(?:y|ies)",
    # General
    r"sites?",
    r"locations?",
    r"centers?",
    r"propert(?:ies|y)",
    r"premises",
    r"campuses?",
}

# Geographic coverage
GEO_LOCATION_TERMS: set[str] = {
    # Top-level
    r"continents?",
    r"countr(?:ies|y)",
    r"nations?",
    # Sub-national
    r"states?",
    r"provinces?",
    r"territor(?:ies|y)",
    r"regions?",
    r"districts?",
    r"count(?:y|ies)",
    r"parishes?",
    r"prefectures?",
    # Municipal
    r"municipalit(?:ies|y)",
    r"cit(?:ies|y)",
    r"towns?",
    r"villages?",
    r"boroughs?",
    # General
    r"areas?",
    r"zones?",
    r"sectors?",
    r"jurisdictions?",
}

# =============================================================================
# REGEX-CONCATENATED TERMS
# =============================================================================

# Flat union for matching "number + location term" patterns
LOCATION_TERMS: set[str] = PHYSICAL_LOCATION_TERMS | GEO_LOCATION_TERMS

# Optional: build compound patterns for multi-word physical locations if needed
PHYSICAL_COMPOUNDS: set[str] = {
    build_compound(
        set(
            [
                r"distribution",
                r"fulfillment",
                r"data",
                r"call",
                r"manufacturing",
                r"production",
                r"supply",
                r"assembly",
            ]
            + INDUSTRY_PREFIX_TERMS_FLAT
        ),
        PHYSICAL_LOCATION_TERMS,
    ),
}


_LOCATION_TERMS = list(LOCATION_TERMS | PHYSICAL_COMPOUNDS)
_LOCATION_TERM_PATTERN = build_alternation(_LOCATION_TERMS)

_LOCATION_FILLER = build_alternation(
    [
        r"independent",
        r"international",
        r"national",
        r"dependent",
        r"domestic",
        r"foreign",
        r"global",
        r"regional",
        r"local",
        r"regional",
        r"affiliate",
        r"strategic",
        r"major",
        r"minor",
        r"different",
        r"similar",
        r"several",
        r"third[-\s]party",
        r"trade",
        r"company",
        r"[A-Z][a-z]+(?:ese|ian|ish|an|ic)",
    ]
)
# optional 0-2 filler words, allowing connectors (and/or/,)
_LOCATION_FILLER_GAP = rf"(?:{_LOCATION_FILLER}\s*(?:and|or|,)?\s*){{0,4}}"

# optional 1-word gap before the location term
_OPTIONAL_WORD_BEFORE = make_gap(1, allow_digits=False, space="before")

_FUNCTION_WORDS = build_alternation(
    [r"of", r"our", r"(?:company|registrant)(?:'?s)?", r"the", r"an", r"a", r"out", r"that", r"this"]
)
_FUNCTION_WORD_GAP = rf"(?:{_FUNCTION_WORDS}\s+){{0,3}}"

_LOCATION_RE = build_regex(_LOCATION_TERMS)

LOCATION_COUNT_RE = re.compile(
    rf"\b{NUMBER_RANGE_STR}\s+{_FUNCTION_WORD_GAP}{_LOCATION_FILLER_GAP}{_OPTIONAL_WORD_BEFORE}\s*{_LOCATION_FILLER_GAP}{_LOCATION_TERM_PATTERN}\b",
    re.IGNORECASE,
)

RegionMatcher._compile()
_region_patterns = [pat.pattern[2:-2] for pat in RegionMatcher.location_regexes]
_REGION_PATTERN = "|".join(_region_patterns)

# Match "[num] in [Region/Country]" (e.g. "5 in the US", "2 in China")
_NUM_IN_REGION_RE = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+in\s+(?:the\s+)?(?:{_REGION_PATTERN})\b",
    re.IGNORECASE
)

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


def _number_value(num_text: str) -> int:
    if not num_text:
        return 0
    # If a range, take the first number as a proxy
    first = re.split(r"[-–—]|\bto\b", num_text, maxsplit=1)[0]
    try:
        return int(float(first.replace(",", "")))
    except ValueError:
        return 0


def extract_spans(text: str) -> list[tuple[str, int, int, str]]:
    """
    Extract LOCATION_COUNT spans from text using location-specific rules.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    stripped_text, pos_map = strip_angle_brackets(text)
    spans: list[tuple[str, int, int, str]] = []
    span_set: set[tuple[str, int, int, str]] = set()
    stripped_spans: list[tuple[int, int]] = []

    def _add_span(start: int, end: int, num_val: Optional[int] = None, label: str = LABELS.LOCATION_COUNT.value) -> None:
        orig_start, orig_end = remap_span(pos_map, start, end)
        item = (text[orig_start:orig_end], orig_start, orig_end, label)
        
        if item in span_set:
            return
        span_set.add(item)
        spans.append(item)
        stripped_spans.append((start, end))

    def _overlaps_existing(start: int, end: int) -> bool:
        for s, e in stripped_spans:
            if not (end <= s or start >= e):
                return True
        return False

    for sent_start, _, sentence in _iter_sentences(stripped_text):
        for m in LOCATION_COUNT_RE.finditer(sentence):
            if not _overlaps_existing(sent_start + m.start(), sent_start + m.end()):
                _add_span(sent_start + m.start(), sent_start + m.end())

        # Disambiguate "[num] in [Region]" between Labor and Location
        has_worker_context = bool(_WORKER_CONTEXT_RE.search(sentence))
        has_location_context = bool(_LOCATION_RE.search(sentence))

        # If there are NO worker terms, and there IS location context, claim it for location.
        if not has_worker_context and has_location_context:
            for m in _NUM_IN_REGION_RE.finditer(sentence):
                if not _overlaps_existing(sent_start + m.start(), sent_start + m.end()):
                    _add_span(sent_start + m.start(), sent_start + m.end())

    return spans
