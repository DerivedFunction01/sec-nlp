import re
from defs.regex_lib import NUMBER_PATTERN_STR, build_alternation
from defs.labels import LABELS
from defs.regex.labor import GENERIC_WORKER_TERMS

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

_ENTITY_TERMS = list(ORGANIZATIONAL_TERMS | PRODUCT_TERMS | AMBIGUOUS_TERMS)
_ENTITY_TERM_PATTERN = build_alternation(_ENTITY_TERMS)
_GENERIC_WORKER_PATTERN = build_alternation(list(GENERIC_WORKER_TERMS))

_ENTITY_GAP = r"(?:[^\W\d][\w\.-]*\s+){0,3}"
ENTITY_COUNT_REGEX = re.compile(
    rf"\b({NUMBER_PATTERN_STR})\s+{_ENTITY_GAP}"
    rf"(?:{_ENTITY_TERM_PATTERN})"
    rf"(?!\s+(?:{_GENERIC_WORKER_PATTERN})\b)\b",
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
    for m in ENTITY_COUNT_REGEX.finditer(text):
        spans.append((m.start(), m.end(), LABELS.ENTITY_COUNT.value))

    return spans
