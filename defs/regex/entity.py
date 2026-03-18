from __future__ import annotations
import re
from defs.regex_lib import NUMBER_PATTERN_STR, build_alternation, build_compound
from defs.labels import LABELS
from defs.regex.labor import GENERIC_WORKER_TERMS, WORKER_TERMS

# Unambiguously ENTITY_COUNT
ORGANIZATIONAL_TERMS = {
    r"compan(?:y|ies)",
    r"corporations?",
    r"subsidiar(?:y|ies)",
    r"affiliates?",
    r"airlines?",
    r"unions",
    r"partnerships?",
    r"ventures?",
    r"competitors?",
    r"suppliers?",
    r"customers?",
    r"clients?",
    r"contractors?",
    r"dealers?",
    r"distributors?",
    r"agenc(?:y|ies)",
}

PRODUCT_TERMS = {
    r"products?",
    r"brands?",
    r"lines?",  # product lines
    r"models?",
    r"patents?",
    r"licenses?",
    r"contracts?",
    r"agreements?",
    r"permits?",
}

# --- Ambiguous: context decides ---
AMBIGUOUS_TERMS = {
    r"segments?",  
    r"divisions?", 
    r"markets?",
    r"groups?", 
    r"networks?",  
    r"channels?",  
    r"portfolios?",
}

GENERIC_COUNT_NOUNS = {
    r"pieces?",
    r"parts?",
    r"components?",
    r"elements?",
    r"slots?",
    r"seats?",
    r"positions?",
    r"spaces?",
    r"trips?",
    r"visits?",
    r"calls?",
    r"transactions?",
    r"orders?",
    r"shipments?",
    r"deliveries?",
    r"packages?",
    r"containers?",
    r"loads?",
    r"sheets?",
    r"coils?",
    r"bundles?",
    r"pallets?",
    r"sacks?",
    r"bales?",
    r"heads?",
    r"carats?",
    r"ingots?",
    r"bars?",
    r"items?",
    r"units?",
    r"basis\s+points",
    r"bps",
    r"lots?",
    r"tranches?",
}

_ENTITY_TERMS = list(ORGANIZATIONAL_TERMS | PRODUCT_TERMS | AMBIGUOUS_TERMS | GENERIC_COUNT_NOUNS)
_ENTITY_TERM_PATTERN = build_alternation(_ENTITY_TERMS)
_GENERIC_WORKER_PATTERN = build_alternation(list(GENERIC_WORKER_TERMS))

_ENTITY_FILLER = build_alternation(
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
        r"third[-\s]party",
        r"trade",
        r"labo(?:u)r",
        r"union",
        r"(?:collective\s+)?bargaining",
    ]
)
_ENTITY_FILLER_GAP = rf"(?:{_ENTITY_FILLER}\s+){{0,2}}"
_ENTITY_GAP = r"(?:[^\W\d][\w\.-]*\s+){0,1}"
ENTITY_COUNT_RE = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+{_ENTITY_FILLER_GAP}{_ENTITY_GAP}"
    rf"(?:{_ENTITY_TERM_PATTERN})"
    rf"(?!\s+(?:{_GENERIC_WORKER_PATTERN})\b)\b",
    re.IGNORECASE,
)

# Standalone counts like "5 CBAs"
_STANDALONE_TERMS = [
    r"cba(?:s)?",
    r"nda(?:s)?",
    r"mou(?:s)?",
    r"(?:collective\s+)?bargaining\s+units",
]

_STANDALONE_PATTERN = build_alternation(_STANDALONE_TERMS)
ENTITY_STANDALONE_RE = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+(?:{_STANDALONE_PATTERN})\b",
    re.IGNORECASE,
)

# Bargaining units (treat as ENTITY_COUNT, not labor)
_BU_WORKER_PATTERN = build_alternation(list(WORKER_TERMS))
_BU_WORKER_PHRASE = r"(?:[^\W\d][\w-]{3,}\s+){0,1}" rf"(?:{_BU_WORKER_PATTERN})(?:['’]s?)?"
BARGAINING_UNIT_COUNT_RE = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+(?:{_BU_WORKER_PHRASE}\s+)?"
    rf"(?:collective\s+)?bargaining\s+units?\b",
    re.IGNORECASE,
)


def extract_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Extract ENTITY_COUNT spans from text using entity-specific rules.
    Returns (start, end, label) tuples.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []
    for m in ENTITY_COUNT_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ENTITY_COUNT.value))
    for m in ENTITY_STANDALONE_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ENTITY_COUNT.value))
    for m in BARGAINING_UNIT_COUNT_RE.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ENTITY_COUNT.value))

    return spans
