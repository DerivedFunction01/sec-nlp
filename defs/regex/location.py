from __future__ import annotations
import re
from defs.regex_lib import NUMBER_RANGE_STR, build_compound, NUMBER_PATTERN_STR, build_alternation, make_gap
from defs.labels import LABELS

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
LOCATION_TERMS: set[str] = (
    PHYSICAL_LOCATION_TERMS | GEO_LOCATION_TERMS
)

# Optional: build compound patterns for multi-word physical locations if needed
PHYSICAL_COMPOUNDS: set[str] = {
    build_compound(
        [r"distribution", r"fulfillment", r"data", r"call", r"manufacturing"],
        [
            r"facilit(?:y|ies)",
            r"plants?",
            r"factor(?:y|ies)",
            r"warehouses?",
            r"centers?",
            r"sites?",
            r"locations?",
        ],
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
        r"affiliate",
        r"strategic",
        r"major",
        r"minor",
        r"different",
        r"similar",
        r"third[-\s]party",
        r"trade",
    ]
)
# optional 0-2 filler words, allowing connectors (and/or/,)
_LOCATION_FILLER_GAP = rf"(?:{_LOCATION_FILLER}\s*(?:and|or|,)?\s*){{0,2}}"

# optional 1-word gap before the location term
_OPTIONAL_WORD_BEFORE = make_gap(1, allow_digits=False, space="before")

LOCATION_COUNT_RE = re.compile(
    rf"\b{NUMBER_RANGE_STR}\s+{_LOCATION_FILLER_GAP}{_OPTIONAL_WORD_BEFORE}{_LOCATION_TERM_PATTERN}\b",
    re.IGNORECASE,
)


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Extract LOCATION_COUNT spans from text using location-specific rules.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []
    for m in LOCATION_COUNT_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.LOCATION_COUNT.value))

    return spans
